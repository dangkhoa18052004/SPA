"""Gemini AI booking agent và tóm tắt kinh doanh (giai đoạn 5).

AI chỉ điều phối: đọc dữ liệu qua tool, mọi ghi DB đi qua business service.
- Lịch hẹn chỉ được tạo bởi confirm_booking_tool, gọi từ API xác nhận của chính khách
  (nút "Xác nhận đặt lịch"); model không có tool xác nhận.
- Giá/dịch vụ/khung giờ luôn lấy từ DB; không gửi tên/SĐT/email khách cho Gemini.
- GEMINI_API_KEY/GEMINI_MODEL chỉ đọc từ môi trường; không log key, không log nội dung chat.
"""
import json
import time
import re
import uuid
from datetime import datetime, timedelta

import requests
from flask import current_app

from ..extensions import db
from ..models import AIBookingDraft, DichVu, NhanVien
from . import appointment_service, analytics_service
from .appointment_service import AppointmentServiceError

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
MAX_MESSAGE_CHARS = 1000
MAX_HISTORY = 10
MAX_TOOL_ROUNDS = 5
DRAFT_TTL_MINUTES = 30


class AIError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        if status_code:
            self.status_code = status_code


class AINotConfigured(AIError):
    status_code = 503


class AIUpstreamError(AIError):
    status_code = 502


class ToolError(Exception):
    """Lỗi nghiệp vụ trả về cho model dưới dạng kết quả tool (model sẽ hỏi lại khách)."""

    def __init__(self, message, need=None):
        super().__init__(message)
        self.message, self.need = message, need


# ---------------------------------------------------------------------------
# Cấu hình & gọi Gemini
# ---------------------------------------------------------------------------

def is_configured():
    return bool((current_app.config.get('GEMINI_API_KEY') or '').strip())


def model_name():
    return (current_app.config.get('GEMINI_MODEL') or 'gemini-3.8-flash').strip()


def fallback_models():
    raw = current_app.config.get('GEMINI_FALLBACK_MODELS') or ''
    return [m.strip() for m in raw.split(',') if m.strip() and m.strip() != model_name()]


def status():
    return dict(configured=is_configured(), model=model_name() if is_configured() else None)


OVERLOADED = (429, 500, 503)


def call_gemini(payload):
    """POST generateContent. Tách riêng để test mock; không bao giờ log key/payload.
    Model chính quá tải (429/5xx): thử lại 1 lần rồi chuyển lần lượt sang GEMINI_FALLBACK_MODELS."""
    if not is_configured():
        raise AINotConfigured('Trợ lý AI chưa được cấu hình (thiếu GEMINI_API_KEY). Các chức năng khác vẫn hoạt động bình thường.')
    attempts = [model_name(), model_name()] + fallback_models()
    for index, model in enumerate(attempts):
        try:
            response = requests.post(
                GEMINI_URL.format(model=model), json=payload,
                headers={'x-goog-api-key': current_app.config['GEMINI_API_KEY'].strip(), 'Content-Type': 'application/json'},
                timeout=current_app.config.get('GEMINI_TIMEOUT', 30))
        except requests.RequestException as error:
            current_app.logger.warning('[ai] Gemini request failed (%s): %s', model, type(error).__name__)
            if index + 1 < len(attempts):
                continue
            raise AIUpstreamError('Không kết nối được dịch vụ AI, vui lòng thử lại sau.')
        if response.status_code not in OVERLOADED or index + 1 == len(attempts):
            break
        current_app.logger.info('[ai] %s HTTP %s, thử model kế tiếp', model, response.status_code)
        if index == 0:
            time.sleep(1.0)
    if response.status_code != 200:
        try:
            reason = response.json().get('error', {}).get('status', '')
        except ValueError:
            reason = ''
        current_app.logger.warning('[ai] Gemini HTTP %s %s', response.status_code, reason)
        if response.status_code in (401, 403):
            raise AINotConfigured('GEMINI_API_KEY không hợp lệ hoặc không có quyền dùng model đã cấu hình.')
        raise AIUpstreamError('Dịch vụ AI tạm thời không phản hồi, vui lòng thử lại sau.')
    return response.json()


def _parts(response):
    candidates = response.get('candidates') or []
    if not candidates:
        return None, []
    content = candidates[0].get('content') or {'role': 'model', 'parts': []}
    content.setdefault('role', 'model')
    return content, content.get('parts') or []


# ---------------------------------------------------------------------------
# Ẩn PII trước khi gửi ra ngoài
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+(\.[\w-]+)+')
PHONE_RE = re.compile(r'(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?!\d)')


def scrub(text, names=()):
    """Thay email, số điện thoại và tên khách bằng nhãn trung tính."""
    text = EMAIL_RE.sub('[email đã ẩn]', str(text or ''))
    text = PHONE_RE.sub('[SĐT đã ẩn]', text)
    for name in names:
        if name and len(name.strip()) >= 2:
            text = re.sub(re.escape(name.strip()), '[tên khách]', text, flags=re.IGNORECASE)
    return text


def _scrub_value(value, names=()):
    if isinstance(value, str):
        return scrub(value, names)
    if isinstance(value, dict):
        return {k: _scrub_value(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v, names) for v in value]
    return value


# ---------------------------------------------------------------------------
# Tools (chỉ đọc qua service; ghi DB đi qua appointment_service)
# ---------------------------------------------------------------------------

def _vnd(value):
    return int(round(float(value or 0)))


def _parse_datetime(value):
    """Chỉ chấp nhận ngày giờ cụ thể YYYY-MM-DDTHH:MM; mơ hồ/thiếu giờ → yêu cầu hỏi lại."""
    if not value or not isinstance(value, str):
        raise ToolError('Thiếu ngày và giờ cụ thể. Hãy hỏi khách ngày nào và mấy giờ.', need='ngaygio')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?', value.strip()):
        raise ToolError('Ngày giờ chưa rõ (cần dạng YYYY-MM-DDTHH:MM). Hãy hỏi lại khách giờ cụ thể.', need='ngaygio')
    try:
        dt = datetime.fromisoformat(value.strip().replace(' ', 'T'))
    except ValueError:
        raise ToolError('Ngày giờ không hợp lệ. Hãy hỏi lại khách.', need='ngaygio')
    if dt <= appointment_service.vn_now():
        raise ToolError('Thời điểm này đã qua. Hãy hỏi khách chọn thời gian khác.', need='ngaygio')
    return dt.replace(second=0, microsecond=0)


def _services(madv_list):
    if not isinstance(madv_list, list) or not madv_list:
        raise ToolError('Chưa chọn dịch vụ. Hãy hỏi khách muốn dùng dịch vụ nào.', need='madv_list')
    try:
        ids = list(dict.fromkeys(int(m) for m in madv_list))
    except (TypeError, ValueError):
        raise ToolError('Mã dịch vụ không hợp lệ; dùng madv từ get_available_services_tool.', need='madv_list')
    services = DichVu.query.filter(DichVu.madv.in_(ids), DichVu.active.isnot(False)).all()
    if len(services) != len(ids):
        raise ToolError('Có dịch vụ không tồn tại hoặc đã ngừng; dùng madv từ get_available_services_tool.', need='madv_list')
    order = {m: i for i, m in enumerate(ids)}
    return sorted(services, key=lambda s: order[s.madv])


def get_available_services_tool(actor=None, **_):
    services = DichVu.query.filter(DichVu.active.isnot(False)).order_by(DichVu.tendv).all()
    return dict(services=[dict(madv=s.madv, tendv=s.tendv, gia_vnd=_vnd(s.gia), thoiluong_phut=s.thoiluong or 60,
                               mota=(s.mota or '')[:200]) for s in services])


def check_availability_tool(madv_list=None, ngaygio=None, manv=None, actor=None, **_):
    services = _services(madv_list)
    start = _parse_datetime(ngaygio)
    ids = [s.madv for s in services]
    duration = appointment_service.calculate_total_duration(ids)
    if manv:
        ok, _, reason = appointment_service.check_staff_availability(int(manv), start, duration)
        staff = db.session.get(NhanVien, int(manv))
        available_staff = [dict(manv=staff.manv, hoten=staff.hoten)] if ok and staff else []
        message = appointment_service.AVAILABILITY_MESSAGES.get(reason, reason)
    else:
        rows = appointment_service.get_available_staff_for_booking(start, ids)
        available_staff = [dict(manv=r['manv'], hoten=r['hoten']) for r in rows if r['available']]
        message = 'Còn kỹ thuật viên trống' if available_staff else 'Không còn kỹ thuật viên trống'
    other = [s['time'] for s in appointment_service.get_available_slots(start.date(), madv_list=ids) if s['available']]
    return dict(available=bool(available_staff), ngaygio=start.strftime('%Y-%m-%dT%H:%M'), thoiluong_phut=duration,
                ket_thuc=(start + timedelta(minutes=duration)).strftime('%H:%M'), message=message,
                ky_thuat_vien_trong=available_staff, gio_con_trong_trong_ngay=other[:8])


def create_booking_draft_tool(madv_list=None, ngaygio=None, manv=None, note=None, actor=None, **_):
    """Tạo bản nháp (KHÔNG tạo LichHen). Khách phải bấm xác nhận để thành lịch hẹn."""
    if not actor or actor.get('kind') != 'customer':
        raise ToolError('Khách cần đăng nhập để đặt lịch. Hãy mời khách đăng nhập rồi thử lại.', need='login')
    availability = check_availability_tool(madv_list=madv_list, ngaygio=ngaygio, manv=manv)
    if not availability['available']:
        raise ToolError(f"Khung giờ này không còn chỗ. Giờ còn trống trong ngày: "
                        f"{', '.join(availability['gio_con_trong_trong_ngay']) or 'không có'}.", need='ngaygio')
    services = _services(madv_list)
    staff = db.session.get(NhanVien, int(manv)) if manv else None
    draft = AIBookingDraft(id=str(uuid.uuid4()), makh=actor['makh'], madv_list=[s.madv for s in services],
                           ngaygio=_parse_datetime(ngaygio), manv=staff.manv if staff else None,
                           note=(scrub(note) or '')[:300] or None, status='draft',
                           expires_at=datetime.utcnow() + timedelta(minutes=DRAFT_TTL_MINUTES))
    db.session.add(draft)
    db.session.commit()
    return serialize_draft(draft)


def serialize_draft(draft):
    services = _ordered_services(draft.madv_list)
    staff = db.session.get(NhanVien, draft.manv) if draft.manv else None
    duration = sum((s.thoiluong or 60) for s in services)
    return dict(draft_id=draft.id, status=draft.status, malh=draft.malh,
                ngaygio=draft.ngaygio.strftime('%Y-%m-%dT%H:%M'),
                ket_thuc=(draft.ngaygio + timedelta(minutes=duration)).strftime('%H:%M'),
                dich_vu=[dict(madv=s.madv, tendv=s.tendv, gia_vnd=_vnd(s.gia), thoiluong_phut=s.thoiluong or 60) for s in services],
                tong_tien_vnd=sum(_vnd(s.gia) for s in services), thoiluong_phut=duration,
                ky_thuat_vien=staff.hoten if staff else 'Spa tự sắp xếp',
                can_xac_nhan=draft.status == 'draft',
                het_han_luc_utc=draft.expires_at.strftime('%Y-%m-%dT%H:%M'))


def _ordered_services(ids):
    found = {s.madv: s for s in DichVu.query.filter(DichVu.madv.in_(ids)).all()}
    return [found[i] for i in ids if i in found]


def confirm_booking_tool(draft_id, makh):
    """Tạo đúng một LichHen từ bản nháp của chính khách. Gọi lại trả về cùng lịch hẹn (idempotent)."""
    updated = AIBookingDraft.query.filter_by(id=str(draft_id)).update(
        {AIBookingDraft.id: AIBookingDraft.id}, synchronize_session=False)  # khóa dòng
    if not updated:
        db.session.rollback()
        raise AIError('Không tìm thấy bản nháp đặt lịch.', 404)
    draft = AIBookingDraft.query.filter_by(id=str(draft_id)).populate_existing().one()
    if draft.makh != makh:
        db.session.rollback()
        raise AIError('Bạn không có quyền xác nhận bản nháp này.', 403)
    if draft.status == 'confirmed':
        db.session.rollback()
        if not draft.malh:
            raise AIError('Bản nháp đang được xác nhận, vui lòng thử lại sau giây lát.', 409)
        return dict(created=False, draft=serialize_draft(draft))
    if draft.status != 'draft' or draft.expires_at < datetime.utcnow():
        draft.status = 'expired'
        db.session.commit()
        raise AIError('Bản nháp đã hết hạn. Hãy nhờ trợ lý tạo lại bản nháp mới.', 410)
    # Đánh dấu trước khi tạo lịch: create_appointment commit cùng lúc nên request song song không tạo trùng.
    draft.status, draft.confirmed_at = 'confirmed', datetime.utcnow()
    try:
        result = appointment_service.create_appointment(
            customer_id=draft.makh, madv_list=draft.madv_list, start_dt=draft.ngaygio,
            manv=draft.manv, note=draft.note or 'Đặt qua trợ lý AI', source='ai')
    except AppointmentServiceError as error:
        db.session.rollback()
        raise AIError(error.message, error.status_code)
    draft = db.session.get(AIBookingDraft, str(draft_id))
    draft.malh = result['appointment']['malh']
    db.session.commit()
    return dict(created=True, draft=serialize_draft(draft), appointment=result['appointment'])


def _metric_range(from_date=None, to_date=None, **_):
    summary = analytics_service.dashboard_summary(from_date, to_date)
    top = analytics_service.top_services(summary['from_date'], summary['to_date'], limit=5)
    return dict(
        from_date=summary['from_date'], to_date=summary['to_date'],
        revenue=dict(total_vnd=_vnd(summary['revenue']['total']), service_vnd=_vnd(summary['revenue']['service']),
                     package_vnd=_vnd(summary['revenue']['package']), transactions=summary['revenue']['transactions']),
        appointments=dict(total=summary['appointments']['total'], completed=summary['appointments']['completed'],
                          cancelled=summary['appointments']['cancelled']),
        cancellation_rate_percent=summary['appointments']['cancel_rate'],
        avg_invoice_vnd=_vnd(summary['revenue']['average_transaction']),
        new_customers=summary['new_customers'],
        top_services=[dict(tendv=s['tendv'], booking_count=s['booking_count']) for s in top['top_services']],
    )


def get_business_metrics_tool(from_date=None, to_date=None, actor=None, **_):
    if not actor or actor.get('kind') != 'staff' or actor.get('role') not in ('admin', 'manager'):
        raise ToolError('Chỉ quản lý/admin xem được số liệu kinh doanh.', need='permission')
    return _metric_range(from_date, to_date)


TOOLS = {
    'get_available_services_tool': get_available_services_tool,
    'check_availability_tool': check_availability_tool,
    'create_booking_draft_tool': create_booking_draft_tool,
    'get_business_metrics_tool': get_business_metrics_tool,
}

_SVC_ARGS = {'madv_list': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'Danh sách madv lấy từ get_available_services_tool'},
             'ngaygio': {'type': 'string', 'description': 'Ngày giờ cụ thể theo giờ Việt Nam, định dạng YYYY-MM-DDTHH:MM'},
             'manv': {'type': 'integer', 'description': 'Mã kỹ thuật viên nếu khách chọn; bỏ trống để spa tự xếp'}}
DECLARATIONS = {
    'get_available_services_tool': dict(name='get_available_services_tool',
        description='Danh sách dịch vụ đang hoạt động của Bin Spa với giá (VNĐ) và thời lượng lấy từ cơ sở dữ liệu.',
        parameters={'type': 'object', 'properties': {}}),
    'check_availability_tool': dict(name='check_availability_tool',
        description='Kiểm tra còn chỗ cho các dịch vụ tại một ngày giờ cụ thể; trả KTV trống và giờ trống khác trong ngày.',
        parameters={'type': 'object', 'properties': _SVC_ARGS, 'required': ['madv_list', 'ngaygio']}),
    'create_booking_draft_tool': dict(name='create_booking_draft_tool',
        description='Tạo BẢN NHÁP đặt lịch cho khách đã đăng nhập (chưa đặt lịch). Khách phải tự bấm nút xác nhận.',
        parameters={'type': 'object', 'properties': {**_SVC_ARGS, 'note': {'type': 'string', 'description': 'Ghi chú ngắn của khách (không chứa SĐT/email)'}},
                    'required': ['madv_list', 'ngaygio']}),
    'get_business_metrics_tool': dict(name='get_business_metrics_tool',
        description='Số liệu kinh doanh (doanh thu, lịch hẹn, tỷ lệ hủy, top dịch vụ...) trong khoảng ngày. Chỉ cho quản lý.',
        parameters={'type': 'object', 'properties': {'from_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
                                                     'to_date': {'type': 'string', 'description': 'YYYY-MM-DD'}}}),
}


def allowed_tools(actor):
    names = ['get_available_services_tool', 'check_availability_tool']
    if actor.get('kind') == 'customer':
        names.append('create_booking_draft_tool')
    if actor.get('kind') == 'staff' and actor.get('role') in ('admin', 'manager'):
        names.append('get_business_metrics_tool')
    return names


def run_tool(name, args, actor):
    if name not in allowed_tools(actor):
        return {'ok': False, 'message': 'Công cụ này không được phép cho người dùng hiện tại.'}
    try:
        return {'ok': True, **TOOLS[name](actor=actor, **(args or {}))}
    except ToolError as error:
        db.session.rollback()
        return {'ok': False, 'message': error.message, 'need': error.need}
    except (AppointmentServiceError, ValueError, TypeError) as error:
        db.session.rollback()
        return {'ok': False, 'message': getattr(error, 'message', 'Tham số không hợp lệ')}


# ---------------------------------------------------------------------------
# Hội thoại
# ---------------------------------------------------------------------------

OUT_OF_SCOPE_RE = re.compile(
    r'(kê\s*(đơn\s*)?thuốc|đơn\s*thuốc|uống\s*thuốc\s*gì|bôi\s*thuốc\s*gì|chẩn\s*đoán|'
    r'(tôi|em|mình)\s*bị\s*(bệnh|nấm|viêm|vảy nến|chàm|zona)|kháng\s*sinh|corticoid)', re.IGNORECASE)
MEDICAL_REFUSAL = ('Xin lỗi, Bin Spa không thể chẩn đoán bệnh da hay kê thuốc. Bạn nên gặp bác sĩ da liễu để được thăm khám. '
                   'Mình có thể giúp bạn tìm hiểu dịch vụ chăm sóc da phổ thông hoặc đặt lịch tại spa nhé!')


def system_prompt(actor):
    now = appointment_service.vn_now()
    weekdays = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
    lines = [
        'Bạn là trợ lý đặt lịch của Bin Spa (spa chăm sóc sắc đẹp). Trả lời ngắn gọn, thân thiện, bằng tiếng Việt.',
        f'Bây giờ là {now:%H:%M} {weekdays[now.weekday()]} ngày {now:%d/%m/%Y} (giờ Việt Nam).',
        'PHẠM VI: chỉ tư vấn dịch vụ của Bin Spa, chăm sóc làm đẹp phổ thông và đặt lịch. Câu hỏi ngoài phạm vi: từ chối ngắn gọn rồi gợi ý dịch vụ spa.',
        'Không chẩn đoán bệnh da, không kê hoặc gợi ý thuốc; khuyên gặp bác sĩ da liễu khi có dấu hiệu bệnh.',
        'GIÁ, dịch vụ, thời lượng, giờ trống: CHỈ dùng kết quả tool; không tự đoán. Luôn gọi get_available_services_tool trước khi nói về dịch vụ/giá.',
        'NGÀY GIỜ: chuyển "mai", "thứ bảy tới" thành ngày cụ thể theo ngày hôm nay. Nếu khách chưa nói giờ cụ thể (ví dụ chỉ nói "buổi chiều", "cuối tuần") thì HỎI LẠI, không tự chọn.',
        'ĐẶT LỊCH: kiểm tra bằng check_availability_tool, rồi gọi create_booking_draft_tool để tạo bản nháp. '
        'Bản nháp CHƯA phải lịch hẹn; nói khách kiểm tra rồi bấm nút "Xác nhận đặt lịch" bên dưới. Không bao giờ nói đã đặt xong.',
        'Không hỏi hoặc nhắc lại số điện thoại, email của khách.',
    ]
    if actor.get('kind') != 'customer':
        lines.append('Người dùng chưa đăng nhập tài khoản khách: có thể tư vấn và kiểm tra giờ trống, nhưng muốn đặt lịch phải đăng nhập.')
    if 'get_business_metrics_tool' in allowed_tools(actor):
        lines.append('Người dùng là quản lý: có thể dùng get_business_metrics_tool; chỉ nêu số có trong kết quả tool.')
    return '\n'.join(lines)


def _history(history, names):
    contents = []
    for item in (history or [])[-MAX_HISTORY:]:
        if not isinstance(item, dict) or item.get('role') not in ('user', 'model'):
            continue
        text = str(item.get('text') or '')[:MAX_MESSAGE_CHARS]
        if text.strip():
            contents.append({'role': item['role'], 'parts': [{'text': scrub(text, names)}]})
    return contents


def chat(message, history=None, actor=None):
    actor = actor or {'kind': 'anonymous'}
    message = str(message or '').strip()
    if not message:
        raise AIError('Vui lòng nhập câu hỏi.')
    if len(message) > MAX_MESSAGE_CHARS:
        raise AIError(f'Tin nhắn tối đa {MAX_MESSAGE_CHARS} ký tự.')
    if OUT_OF_SCOPE_RE.search(message):
        return dict(reply=MEDICAL_REFUSAL, draft=None, tools_used=[], guarded=True)
    if not is_configured():
        raise AINotConfigured('Trợ lý AI chưa được cấu hình (thiếu GEMINI_API_KEY). Các chức năng khác vẫn hoạt động bình thường.')

    names = [actor.get('name')] if actor.get('name') else []
    contents = _history(history, names) + [{'role': 'user', 'parts': [{'text': scrub(message, names)}]}]
    tools = [{'function_declarations': [DECLARATIONS[n] for n in allowed_tools(actor)]}]
    used, draft, reply = [], None, ''
    for _ in range(MAX_TOOL_ROUNDS):
        response = call_gemini({
            'system_instruction': {'parts': [{'text': system_prompt(actor)}]},
            'contents': contents, 'tools': tools,
            'generationConfig': {'temperature': 0.3, 'maxOutputTokens': 1024},
        })
        content, parts = _parts(response)
        calls = [p['functionCall'] for p in parts if 'functionCall' in p]
        if not calls:
            reply = ''.join(p.get('text', '') for p in parts).strip()
            break
        for part in parts:  # tham số tool được gửi lại ở vòng sau: cũng ẩn PII
            if 'functionCall' in part:
                part['functionCall']['args'] = _scrub_value(part['functionCall'].get('args') or {}, names)
        contents.append(content)
        results = []
        for call in calls:
            name = call.get('name')
            result = run_tool(name, call.get('args') or {}, actor)
            used.append(name)
            if name == 'create_booking_draft_tool' and result.get('ok'):
                draft = {k: v for k, v in result.items() if k != 'ok'}
            results.append({'functionResponse': {'name': name, 'response': {'result': result}}})
        contents.append({'role': 'user', 'parts': results})
    else:
        reply = 'Xin lỗi, mình chưa xử lý xong yêu cầu. Bạn có thể nói rõ dịch vụ và thời gian mong muốn không?'
    if not reply:
        reply = 'Mình đã chuẩn bị bản nháp, bạn kiểm tra và bấm "Xác nhận đặt lịch" nhé.' if draft else \
            'Xin lỗi, mình chưa hiểu yêu cầu. Bạn muốn tìm hiểu dịch vụ hay đặt lịch?'
    return dict(reply=reply, draft=draft, tools_used=used, guarded=False)


# ---------------------------------------------------------------------------
# Tóm tắt kinh doanh: FACTS do server tạo, SUGGESTIONS do AI viết và được kiểm số
# ---------------------------------------------------------------------------

def _fmt_money(v):
    return f"{int(v):,}".replace(',', '.') + 'đ'


def build_facts(m):
    facts = [
        f"Thực thu {_fmt_money(m['revenue']['total_vnd'])} (dịch vụ {_fmt_money(m['revenue']['service_vnd'])}, "
        f"bán gói {_fmt_money(m['revenue']['package_vnd'])}) từ {m['revenue']['transactions']} giao dịch.",
        f"Giá trị trung bình mỗi giao dịch {_fmt_money(m['avg_invoice_vnd'])}.",
        f"{m['appointments']['total']} lịch hẹn, {m['appointments']['completed']} đã hoàn thành, "
        f"{m['appointments']['cancelled']} bị hủy (tỷ lệ hủy {m['cancellation_rate_percent']}%).",
        f"{m['new_customers']} khách hàng mới.",
    ]
    if m['top_services']:
        facts.append('Dịch vụ được đặt nhiều nhất: ' + ', '.join(f"{s['tendv']} ({s['booking_count']} lượt)" for s in m['top_services']) + '.')
    return facts


NUMBER_RE = re.compile(r'\d[\d.,]*')


def _number_keys(text):
    keys = set()
    for raw in NUMBER_RE.findall(text):
        raw = raw.rstrip('.,')
        digits = re.sub(r'[.,]', '', raw)
        if digits:
            keys.add(digits.lstrip('0') or '0')
    return keys


def _allowed_numbers(metrics):
    allowed = {str(n) for n in range(0, 11)}
    def walk(value):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            for form in (str(int(value)), f'{value:.1f}', f'{value:g}', f'{round(value)}'):
                allowed.add(re.sub(r'[.,]', '', form).lstrip('0') or '0')
        elif isinstance(value, str):
            allowed.update(_number_keys(value))
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(metrics)
    return allowed


def verify_numbers(text, allowed):
    """Bỏ câu có số không nằm trong dữ liệu (chống AI bịa số). Trả (văn bản đã lọc, số câu bị bỏ)."""
    kept, removed = [], 0
    for sentence in re.split(r'(?<=[.!?])\s+', text.strip()):
        if not sentence:
            continue
        if _number_keys(sentence) - allowed:
            removed += 1
        else:
            kept.append(sentence)
    return ' '.join(kept), removed


def business_summary(from_date=None, to_date=None):
    metrics = _metric_range(from_date, to_date)
    facts = build_facts(metrics)
    if not is_configured():
        raise AINotConfigured('Trợ lý AI chưa được cấu hình (thiếu GEMINI_API_KEY). Số liệu thực tế vẫn xem được ở dashboard.')
    prompt = (
        'Bạn là chuyên viên phân tích vận hành spa. Dưới đây là DỮ LIỆU JSON đã được hệ thống tính.\n'
        'Yêu cầu:\n'
        '- "summary": 2-3 câu nhận xét tình hình, CHỈ dùng số có trong JSON (có thể không dùng số).\n'
        '- "suggestions": 3-5 gợi ý hành động cụ thể, ghi rõ đây là đề xuất; không đưa số dự báo hay số không có trong JSON.\n'
        '- Không bịa dữ liệu, không nêu tên/số điện thoại khách.\n'
        'Trả về đúng JSON: {"summary": "...", "suggestions": ["...", "..."]}\n\n'
        f'DỮ LIỆU: {json.dumps(metrics, ensure_ascii=False)}'
    )
    response = call_gemini({
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.4, 'responseMimeType': 'application/json', 'maxOutputTokens': 1024},
    })
    _, parts = _parts(response)
    text = ''.join(p.get('text', '') for p in parts).strip()
    try:
        data = json.loads(re.sub(r'^```(json)?|```$', '', text).strip())
    except ValueError:
        data = {'summary': '', 'suggestions': []}
    allowed = _allowed_numbers(metrics)
    summary, removed = verify_numbers(str(data.get('summary') or ''), allowed)
    suggestions = []
    for item in data.get('suggestions') or []:
        cleaned, dropped = verify_numbers(str(item), allowed)
        removed += dropped
        if cleaned:
            suggestions.append(cleaned)
    return dict(success=True, from_date=metrics['from_date'], to_date=metrics['to_date'], metrics=metrics,
                facts=facts, summary=summary, suggestions=suggestions[:5], removed_unverified=removed,
                model=model_name())

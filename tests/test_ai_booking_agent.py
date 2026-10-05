"""Giai đoạn 5: Gemini booking agent + business summary. Gemini luôn được mock; không gọi mạng."""
import json
from datetime import timedelta, time

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import AIBookingDraft, LichHen, KhachHang, DichVu, CaLam, nhanvien_calam, HoaDon, ThanhToan
from app.services import ai_service, appointment_service, package_service as ps


class FakeGemini:
    """Trả lần lượt các response dựng sẵn và ghi lại payload để kiểm tra."""

    def __init__(self, *responses):
        self.responses, self.payloads = list(responses), []

    def __call__(self, payload):
        self.payloads.append(json.loads(json.dumps(payload)))
        if not self.responses:
            return text('Xong.')
        item = self.responses.pop(0)
        return item(payload) if callable(item) else item


def text(value):
    return {'candidates': [{'content': {'role': 'model', 'parts': [{'text': value}]}}]}


def call(name, **args):
    return {'candidates': [{'content': {'role': 'model', 'parts': [{'functionCall': {'name': name, 'args': args}}]}}]}


def tool_results(payload):
    """functionResponse cuối cùng mà server gửi lại cho model."""
    return [p['functionResponse'] for p in payload['contents'][-1]['parts'] if 'functionResponse' in p]


@pytest.fixture
def ai_app(app, monkeypatch):
    app.config['GEMINI_API_KEY'] = 'test-key-not-real'
    monkeypatch.setattr(appointment_service, 'send_appointment_confirmation_email_async', lambda *a: None)
    with app.app_context():
        services = [DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=60, active=True, mota='Massage body'),
                    DichVu(tendv='Chăm sóc da mụn', gia=450000, thoiluong=60, active=True),
                    DichVu(tendv='Dịch vụ đã ngừng', gia=1, thoiluong=30, active=False)]
        db.session.add_all(services)
        day = ps.local_now().date() + timedelta(days=2)
        shift = CaLam(ngay=day, giobatdau=time(8), gioketthuc=time(18), sogio=10)
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'], maca=shift.maca))
        customer = db.session.get(KhachHang, app.config['TEST_CUSTOMER_ID'])
        customer.hoten, customer.sdt, customer.email = 'Nguyễn Thị Lan', '0912345678', 'lan@example.com'
        db.session.commit()
        return dict(massage=services[0].madv, acne=services[1].madv, stopped=services[2].madv,
                    slot=f'{day.isoformat()}T09:00', day=day.isoformat())


def chat(client, headers, message, history=None):
    return client.post('/api/ai/chat', headers=headers, json={'message': message, 'history': history or []})


# 1) Không key -> báo cấu hình rõ; app core vẫn chạy
def test_without_key_ai_reports_configuration_and_core_still_works(app, client, customer_auth_headers, admin_auth_headers):
    app.config['GEMINI_API_KEY'] = ''
    r = chat(client, customer_auth_headers, 'Có dịch vụ gì?')
    assert r.status_code == 503 and 'GEMINI_API_KEY' in r.json['msg'] and r.json['configured'] is False
    assert client.get('/api/ai/status').json == {'success': True, 'configured': False, 'model': None}
    assert client.post('/api/ai/business-summary', headers=admin_auth_headers, json={}).status_code == 503
    assert client.get('/api/services').status_code == 200
    assert client.get('/api/dashboard/stats', headers=admin_auth_headers).status_code == 200


# 2) Tool danh sách dịch vụ đúng DB
def test_service_tool_matches_database(ai_app, app, client, customer_auth_headers, monkeypatch):
    fake = FakeGemini(call('get_available_services_tool'), text('Bin Spa có Massage thư giãn 300.000đ.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = chat(client, customer_auth_headers, 'Spa có dịch vụ gì, giá bao nhiêu?')
    assert r.status_code == 200 and r.json['tools_used'] == ['get_available_services_tool']
    result = tool_results(fake.payloads[1])[0]['response']['result']
    with app.app_context():
        expected = {s.madv: int(s.gia) for s in DichVu.query.filter(DichVu.active.isnot(False)).all()}
    assert {s['madv']: s['gia_vnd'] for s in result['services']} == expected
    assert ai_app['stopped'] not in expected


# 3) Ngoài scope -> không gọi booking
def test_medical_question_is_refused_without_gemini_or_booking(ai_app, app, client, customer_auth_headers, monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = chat(client, customer_auth_headers, 'Tôi bị nấm da, kê thuốc gì để bôi?')
    assert r.status_code == 200 and r.json['guarded'] and 'bác sĩ da liễu' in r.json['reply']
    assert fake.payloads == [] and r.json['draft'] is None


def test_off_topic_answer_from_model_does_not_book(ai_app, app, client, customer_auth_headers, monkeypatch):
    fake = FakeGemini(text('Xin lỗi, mình chỉ hỗ trợ dịch vụ Bin Spa. Bạn muốn tìm hiểu massage không?'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = chat(client, customer_auth_headers, 'Giá vàng hôm nay bao nhiêu?')
    assert r.json['tools_used'] == [] and r.json['draft'] is None
    assert 'PHẠM VI' in fake.payloads[0]['system_instruction']['parts'][0]['text']
    with app.app_context():
        assert AIBookingDraft.query.count() == 0 and LichHen.query.count() == 0


# 4) Thiếu giờ -> hỏi lại, không ghi DB
def test_missing_time_asks_again_and_writes_nothing(ai_app, app, client, customer_auth_headers, monkeypatch):
    fake = FakeGemini(call('create_booking_draft_tool', madv_list=[ai_app['massage']], ngaygio=ai_app['day']),
                      text('Bạn muốn đến lúc mấy giờ?'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = chat(client, customer_auth_headers, 'Đặt massage chiều mai')
    result = tool_results(fake.payloads[1])[0]['response']['result']
    assert result['ok'] is False and result['need'] == 'ngaygio'
    assert r.json['draft'] is None and 'mấy giờ' in r.json['reply']
    with app.app_context():
        assert AIBookingDraft.query.count() == 0 and LichHen.query.count() == 0


def _make_draft(client, headers, ai_app, monkeypatch, services=None):
    fake = FakeGemini(call('create_booking_draft_tool', madv_list=services or [ai_app['massage']], ngaygio=ai_app['slot']),
                      text('Mình đã tạo bản nháp, bạn bấm Xác nhận đặt lịch nhé.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = chat(client, headers, 'Đặt massage 9 giờ sáng ngày kia')
    assert r.status_code == 200 and r.json['draft'], r.json
    return r.json['draft']


# 5) Draft -> chưa có LichHen; giá lấy DB
def test_draft_does_not_create_appointment(ai_app, app, client, customer_auth_headers, monkeypatch):
    draft = _make_draft(client, customer_auth_headers, ai_app, monkeypatch, [ai_app['massage'], ai_app['acne']])
    assert draft['tong_tien_vnd'] == 750000 and draft['can_xac_nhan'] is True
    with app.app_context():
        assert LichHen.query.count() == 0
        assert db.session.get(AIBookingDraft, draft['draft_id']).status == 'draft'


# 6 + 7) Confirm -> đúng 1 LichHen; confirm lại idempotent
def test_confirm_creates_exactly_one_appointment_and_is_idempotent(ai_app, app, client, customer_auth_headers, monkeypatch):
    draft = _make_draft(client, customer_auth_headers, ai_app, monkeypatch)
    first = client.post('/api/ai/booking/confirm', headers=customer_auth_headers, json={'draft_id': draft['draft_id']})
    assert first.status_code == 201, first.json
    second = client.post('/api/ai/booking/confirm', headers=customer_auth_headers, json={'draft_id': draft['draft_id']})
    assert second.status_code == 200 and second.json['created'] is False
    assert second.json['draft']['malh'] == first.json['appointment']['malh']
    with app.app_context():
        assert LichHen.query.count() == 1
        apt = LichHen.query.one()
        assert apt.booking_source == 'ai' and apt.makh == app.config['TEST_CUSTOMER_ID']


# 8) Customer A không confirm draft B
def test_other_customer_cannot_confirm_draft(ai_app, app, client, customer_auth_headers, monkeypatch):
    draft = _make_draft(client, customer_auth_headers, ai_app, monkeypatch)
    with app.app_context():
        other = KhachHang(hoten='Khách B', taikhoan='khach_b_ai', matkhau='x')
        db.session.add(other); db.session.commit()
        token = create_access_token(identity=f'customer:{other.makh}')
    r = client.post('/api/ai/booking/confirm', headers={'Authorization': f'Bearer {token}'}, json={'draft_id': draft['draft_id']})
    assert r.status_code == 403
    with app.app_context():
        assert LichHen.query.count() == 0


def test_expired_draft_and_anonymous_cannot_book(ai_app, app, client, customer_auth_headers, monkeypatch):
    draft = _make_draft(client, customer_auth_headers, ai_app, monkeypatch)
    with app.app_context():
        row = db.session.get(AIBookingDraft, draft['draft_id'])
        row.expires_at = row.created_at - timedelta(minutes=1)
        db.session.commit()
    assert client.post('/api/ai/booking/confirm', headers=customer_auth_headers, json={'draft_id': draft['draft_id']}).status_code == 410
    fake = FakeGemini(call('create_booking_draft_tool', madv_list=[ai_app['massage']], ngaygio=ai_app['slot']), text('Bạn cần đăng nhập.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = client.post('/api/ai/chat', json={'message': 'Đặt massage'})
    assert r.status_code == 200 and r.json['draft'] is None
    # Khách ẩn danh: model thậm chí không được khai báo tool tạo nháp.
    declared = [d['name'] for d in fake.payloads[0]['tools'][0]['function_declarations']]
    assert 'create_booking_draft_tool' not in declared


# 9) availability dùng appointment_service
def test_availability_tool_uses_appointment_service(ai_app, app, client, customer_auth_headers, monkeypatch):
    seen = []
    real = appointment_service.get_available_staff_for_booking
    monkeypatch.setattr(appointment_service, 'get_available_staff_for_booking',
                        lambda *a, **k: seen.append(a) or real(*a, **k))
    fake = FakeGemini(call('check_availability_tool', madv_list=[ai_app['massage']], ngaygio=ai_app['slot']), text('Còn chỗ.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    chat(client, customer_auth_headers, 'Ngày kia 9h còn chỗ không?')
    result = tool_results(fake.payloads[1])[0]['response']['result']
    assert seen and result['available'] is True and result['ky_thuat_vien_trong']
    assert '09:00' in result['gio_con_trong_trong_ngay']


# 10) business-summary chặn customer; tool số liệu không mở cho khách
def test_business_summary_blocks_customer(ai_app, app, client, customer_auth_headers, staff_auth_headers, monkeypatch):
    assert client.post('/api/ai/business-summary', headers=customer_auth_headers, json={}).status_code == 403
    assert client.post('/api/ai/business-summary', headers=staff_auth_headers, json={}).status_code == 403
    fake = FakeGemini(call('get_business_metrics_tool'), text('Không có quyền.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    chat(client, customer_auth_headers, 'Doanh thu tháng này bao nhiêu?')
    declared = [d['name'] for d in fake.payloads[0]['tools'][0]['function_declarations']]
    assert 'get_business_metrics_tool' not in declared
    result = tool_results(fake.payloads[1])[0]['response']['result']
    assert result['ok'] is False and 'revenue' not in result


def test_business_summary_separates_facts_and_drops_invented_numbers(ai_app, app, client, admin_auth_headers, monkeypatch):
    with app.app_context():
        invoice = HoaDon(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'], tongtien=300000, trangthai='Đã thanh toán')
        db.session.add(invoice); db.session.flush()
        db.session.add(ThanhToan(mahd=invoice.mahd, sotien=300000, phuongthuc='Tiền mặt', ngaythanhtoan=ps.local_now()))
        db.session.commit()
    answer = {'summary': 'Thực thu đạt 300.000đ. Doanh thu sẽ tăng 45% tháng sau.',
              'suggestions': ['Đẩy mạnh combo massage cho khách mới.', 'Mục tiêu đạt 9.999.999đ trong tuần.']}
    fake = FakeGemini(text(json.dumps(answer, ensure_ascii=False)))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    today = ps.local_now().date().isoformat()
    r = client.post('/api/ai/business-summary', headers=admin_auth_headers, json={'from': today, 'to': today})
    assert r.status_code == 200, r.json
    body = r.json
    assert any('300.000đ' in f for f in body['facts'])
    assert body['summary'] == 'Thực thu đạt 300.000đ.'           # câu chứa 45% bị loại
    assert body['suggestions'] == ['Đẩy mạnh combo massage cho khách mới.']
    assert body['removed_unverified'] == 2
    sent = fake.payloads[0]['contents'][0]['parts'][0]['text']
    for key in ('revenue', 'appointments', 'cancellation_rate_percent', 'top_services', 'avg_invoice_vnd', 'new_customers'):
        assert key in sent
    assert 'Nguyễn Thị Lan' not in sent and '0912345678' not in sent


# 11) Không gửi raw PII cho Gemini
def test_no_raw_pii_sent_to_gemini(ai_app, app, client, customer_auth_headers, monkeypatch):
    fake = FakeGemini(call('create_booking_draft_tool', madv_list=[ai_app['massage']], ngaygio=ai_app['slot'],
                           note='gọi 0912345678'), text('Đã tạo bản nháp.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    chat(client, customer_auth_headers, 'Tôi là Nguyễn Thị Lan, sđt 0912 345 678, email lan@example.com, đặt massage',
         history=[{'role': 'user', 'text': 'Liên hệ +84912345678'}])
    sent = json.dumps(fake.payloads, ensure_ascii=False)
    for secret in ('Nguyễn Thị Lan', '0912345678', '0912 345 678', 'lan@example.com', '+84912345678'):
        assert secret not in sent, secret
    assert '[SĐT đã ẩn]' in sent and '[email đã ẩn]' in sent and '[tên khách]' in sent
    with app.app_context():
        assert '0912345678' not in (AIBookingDraft.query.one().note or '')


def test_manager_can_use_metrics_tool_in_chat(ai_app, app, client, admin_auth_headers, monkeypatch):
    fake = FakeGemini(call('get_business_metrics_tool'), text('Tóm tắt.'))
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    r = chat(client, admin_auth_headers, 'Doanh thu 30 ngày qua?')
    result = tool_results(fake.payloads[1])[0]['response']['result']
    assert r.status_code == 200 and result['ok'] is True and 'revenue' in result


def test_upstream_auth_error_is_reported_without_key(ai_app, app, client, customer_auth_headers, monkeypatch, caplog):
    class Resp:
        status_code = 403
        def json(self):
            return {'error': {'status': 'PERMISSION_DENIED'}}
    monkeypatch.setattr(ai_service.requests, 'post', lambda *a, **k: Resp())
    r = chat(client, customer_auth_headers, 'Có dịch vụ gì?')
    assert r.status_code == 503 and 'không hợp lệ' in r.json['msg']
    assert 'test-key-not-real' not in caplog.text and 'test-key-not-real' not in json.dumps(r.json)


def test_input_validation(ai_app, client, customer_auth_headers):
    assert chat(client, customer_auth_headers, '').status_code == 400
    assert chat(client, customer_auth_headers, 'x' * 1001).status_code == 400


def test_overloaded_model_falls_back(ai_app, app, client, customer_auth_headers, monkeypatch):
    app.config['GEMINI_FALLBACK_MODELS'] = 'backup-model'
    calls = []

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._body = code, body
        def json(self):
            return self._body

    def fake_post(url, **kwargs):
        calls.append(url.split('/models/')[1].split(':')[0])
        if 'backup-model' in url:
            return Resp(200, text('Xin chào từ model dự phòng.'))
        return Resp(503, {'error': {'status': 'UNAVAILABLE'}})
    monkeypatch.setattr(ai_service.requests, 'post', fake_post)
    monkeypatch.setattr(ai_service.time, 'sleep', lambda s: None)
    r = chat(client, customer_auth_headers, 'Xin chào')
    assert r.status_code == 200 and 'dự phòng' in r.json['reply']
    assert calls[-1] == 'backup-model' and len(calls) == 3

# app/services/appointment_service.py
"""
Appointment Service - Core Business Logic for Spa Appointment Management.
Dùng chung cho Customer Booking, Admin Management, và AI Assistant.
"""

import re
from datetime import datetime, date, time, timedelta
import threading
from flask import current_app
from sqlalchemy import func, and_, or_

from ..extensions import db
from ..models import (
    LichHen,
    ChiTietLichHen,
    NhanVien,
    KhachHang,
    DichVu,
    CaLam,
    nhanvien_calam,
    AppointmentStatus,
)
from .email_service import send_email


# ==========================================
# CUSTOM EXCEPTIONS
# ==========================================
class AppointmentServiceError(Exception):
    """Lỗi cơ sở cho các thao tác lịch hẹn."""
    def __init__(self, message, status_code=400, extra=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}


class AppointmentNotFoundError(AppointmentServiceError):
    def __init__(self, message="Không tìm thấy lịch hẹn"):
        super().__init__(message, status_code=404)


class AppointmentPermissionError(AppointmentServiceError):
    def __init__(self, message="Bạn không có quyền thực hiện thao tác này"):
        super().__init__(message, status_code=403)


class AppointmentValidationError(AppointmentServiceError):
    def __init__(self, message):
        super().__init__(message, status_code=400)


class AppointmentConflictError(AppointmentServiceError):
    def __init__(self, message="Khung giờ hoặc nhân viên đã bận", conflicts=None):
        super().__init__(message, status_code=409, extra={"conflicts": conflicts or []})
        self.conflicts = conflicts or []


class NoStaffAvailableError(AppointmentConflictError):
    def __init__(self, message="Không có nhân viên rảnh vào khung giờ này. Vui lòng chọn giờ khác!"):
        super().__init__(message)


# ==========================================
# ASYNC EMAIL HELPERS
# ==========================================
def _send_async_email(app, recipient, subject, html_content):
    """Chạy background thread gửi email để không block request."""
    with app.app_context():
        try:
            send_email(recipient, subject, html_content)
            current_app.logger.info(f"Đã gửi email thành công tới {recipient}")
        except Exception as e:
            current_app.logger.error(f"Lỗi khi gửi email: {e}")


def send_appointment_confirmation_email_async(customer_email, customer_name, appointment_data):
    """Gửi email xác nhận đặt lịch hẹn."""
    if not customer_email:
        return
    try:
        app = current_app._get_current_object()
        subject = f"🌸 Bin Spa - Xác nhận đặt lịch hẹn #{appointment_data['malh']}"
        start_dt = appointment_data.get("start_dt")
        end_time_str = appointment_data.get("end_time_str", "")
        services_html = "".join([
            f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee;'>{s['tendv']}</td>"
            f"<td style='padding: 8px; border-bottom: 1px solid #eee; text-align: right;'>{s['thoiluong']} phút</td></tr>"
            for s in appointment_data.get("services", [])
        ])

        html_content = f"""
        <p>Xin chào <strong>{customer_name}</strong>,</p>
        <p>Cảm ơn bạn đã đặt lịch tại <strong>Bin Spa</strong>. Dưới đây là thông tin lịch hẹn của bạn:</p>
        <div style="background: #faf8f5; padding: 15px; border-radius: 8px; margin: 15px 0;">
            <p><strong>Mã lịch hẹn:</strong> #{appointment_data['malh']}</p>
            <p><strong>Ngày:</strong> {start_dt.strftime('%d/%m/%Y')}</p>
            <p><strong>Giờ:</strong> {start_dt.strftime('%H:%M')} - {end_time_str}</p>
            <p><strong>Kỹ thuật viên:</strong> {appointment_data.get('staff_name', 'Được chỉ định bởi Spa')}</p>
            <p><strong>Trạng thái:</strong> <span style="color: #28a745; font-weight: bold;">{AppointmentStatus.to_vietnamese(appointment_data.get('trangthai', 'confirmed'))}</span></p>
        </div>
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <thead>
                <tr style="background: #f1ebd9;">
                    <th style="padding: 8px; text-align: left;">Dịch vụ</th>
                    <th style="padding: 8px; text-align: right;">Thời lượng</th>
                </tr>
            </thead>
            <tbody>{services_html}</tbody>
        </table>
        <p style="margin-top: 20px;">Trân trọng,<br><strong>Bin Spa</strong></p>
        """
        thr = threading.Thread(target=_send_async_email, args=[app, customer_email, subject, html_content])
        thr.daemon = True
        thr.start()
    except Exception as e:
        current_app.logger.error(f"Lỗi khởi tạo gửi mail xác nhận: {e}")


# ==========================================
# CORE APPOINTMENT LOGIC
# ==========================================

def calculate_total_duration(madv_list):
    """
    Tính tổng thời lượng (phút) của danh sách mã dịch vụ.
    Nếu rỗng hoặc <= 0, mặc định là 60 phút.
    """
    if not madv_list:
        return 60
    
    madv_ids = []
    for item in madv_list:
        try:
            madv_ids.append(int(item))
        except (ValueError, TypeError):
            continue

    if not madv_ids:
        return 60

    services = DichVu.query.filter(DichVu.madv.in_(madv_ids)).all()
    total_minutes = sum(s.thoiluong for s in services if s.thoiluong and s.thoiluong > 0)
    return total_minutes if total_minutes > 0 else 60


def get_staff_working_at(start_dt, duration_minutes):
    """
    Lấy danh sách nhân viên kỹ thuật viên (trangthai=True, role='staff')
    có ca làm việc bao phủ trọn vẹn khung giờ [start_dt, start_dt + duration].
    """
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)

    end_dt = start_dt + timedelta(minutes=duration_minutes)
    target_date = start_dt.date()
    if end_dt.date() != target_date:
        return []
    start_time = start_dt.time()
    end_time = end_dt.time()

    staff_list = db.session.query(NhanVien).join(
        nhanvien_calam, NhanVien.manv == nhanvien_calam.c.manv
    ).join(
        CaLam, CaLam.maca == nhanvien_calam.c.maca
    ).filter(
        NhanVien.trangthai == True,
        NhanVien.role == 'staff',
        CaLam.ngay == target_date,
        CaLam.giobatdau <= start_time,
        CaLam.gioketthuc >= end_time
    ).distinct().order_by(NhanVien.manv.asc()).all()

    return staff_list


# Standard availability reasons
AVAILABILITY_REASON_AVAILABLE = "available"
AVAILABILITY_REASON_CONFLICT = "appointment_conflict"
AVAILABILITY_REASON_NOT_WORKING = "not_working"
AVAILABILITY_REASON_INACTIVE = "inactive"
AVAILABILITY_REASON_INVALID = "invalid_staff"
AVAILABILITY_REASON_API_ERROR = "api_error"

AVAILABILITY_MESSAGES = {
    AVAILABILITY_REASON_AVAILABLE: "Nhân viên khả dụng",
    AVAILABILITY_REASON_CONFLICT: "Nhân viên đã có lịch hẹn trong khung giờ này",
    AVAILABILITY_REASON_NOT_WORKING: "Nhân viên không có ca làm việc bao phủ khung giờ này",
    AVAILABILITY_REASON_INACTIVE: "Nhân viên không hoạt động hoặc đã nghỉ việc",
    AVAILABILITY_REASON_INVALID: "Nhân viên không tồn tại hoặc không phải kỹ thuật viên",
    AVAILABILITY_REASON_API_ERROR: "Lỗi kiểm tra lịch",
}


def check_staff_availability(manv, start_dt, duration_minutes, exclude_malh=None):
    """
    Kiểm tra nhân viên `manv` có khả dụng trong khoảng [start_dt, start_dt + duration] hay không.
    Điều kiện:
    1. Nhân viên tồn tại, active (trangthai=True), role='staff'.
    2. Có ca làm việc bao phủ khoảng thời gian này.
    3. Không overlap với bất kỳ lịch hẹn nào đang ở trạng thái pending, confirmed, in_progress.
    
    Returns:
        (is_available: bool, conflicts: list[dict], reason: str)
    """
    if not manv:
        return False, [], AVAILABILITY_REASON_INVALID

    try:
        manv = int(manv)
    except (ValueError, TypeError):
        return False, [], AVAILABILITY_REASON_INVALID

    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except ValueError:
            return False, [], AVAILABILITY_REASON_API_ERROR

    staff = db.session.get(NhanVien, manv) if hasattr(db.session, "get") else NhanVien.query.get(manv)
    if not staff:
        return False, [], AVAILABILITY_REASON_INVALID

    if not staff.trangthai:
        return False, [], AVAILABILITY_REASON_INACTIVE

    if staff.role != 'staff':
        return False, [], AVAILABILITY_REASON_INVALID

    end_dt = start_dt + timedelta(minutes=duration_minutes)
    target_date = start_dt.date()
    start_time = start_dt.time()
    end_time = end_dt.time()

    if end_dt.date() != target_date:
        return False, [], AVAILABILITY_REASON_NOT_WORKING

    # 1. Kiểm tra ca làm việc bao phủ
    has_covering_shift = db.session.query(CaLam).join(
        nhanvien_calam, CaLam.maca == nhanvien_calam.c.maca
    ).filter(
        nhanvien_calam.c.manv == manv,
        CaLam.ngay == target_date,
        CaLam.giobatdau <= start_time,
        CaLam.gioketthuc >= end_time
    ).first() is not None

    if not has_covering_shift:
        return False, [], AVAILABILITY_REASON_NOT_WORKING

    # 2. Kiểm tra xung đột lịch hẹn
    start_of_day = datetime.combine(target_date - timedelta(days=1), time.min)
    end_of_day = datetime.combine(target_date + timedelta(days=1), time.max)

    query = LichHen.query.filter(
        LichHen.manv == manv,
        LichHen.ngaygio >= start_of_day,
        LichHen.ngaygio <= end_of_day,
        LichHen.trangthai.in_(AppointmentStatus.ACTIVE_STATUSES)
    )
    if exclude_malh:
        query = query.filter(LichHen.malh != exclude_malh)

    existing_apts = query.all()
    conflicts = []

    for apt in existing_apts:
        apt_duration = 0
        service_names = []
        for detail in apt.chitiet:
            if detail.dichvu:
                service_names.append(detail.dichvu.tendv)
                if detail.dichvu.thoiluong:
                    apt_duration += detail.dichvu.thoiluong
        if apt_duration <= 0:
            apt_duration = 60

        apt_start = apt.ngaygio
        apt_end = apt_start + timedelta(minutes=apt_duration)

        # Xung đột khi khoảng thời gian giao nhau: start_dt < apt_end AND end_dt > apt_start
        if start_dt < apt_end and end_dt > apt_start:
            conflicts.append({
                'malh': apt.malh,
                'ngaygio': apt_start.strftime('%H:%M'),
                'ketthuc': apt_end.strftime('%H:%M'),
                'services': service_names,
                'khachhang': apt.khachhang.hoten if apt.khachhang else "Khách hàng",
            })

    if conflicts:
        return False, conflicts, AVAILABILITY_REASON_CONFLICT

    return True, [], AVAILABILITY_REASON_AVAILABLE


def get_available_staff_for_booking(start_dt, madv_list):
    """
    Lấy kỹ thuật viên active có ca bao phủ toàn bộ khung giờ và dịch vụ yêu cầu,
    kèm trạng thái rảnh hoặc trùng lịch.
    Dùng cho form booking khách hàng.
    """
    if isinstance(start_dt, str):
        try:
            start_dt = datetime.fromisoformat(start_dt)
        except ValueError:
            raise AppointmentValidationError("Định dạng ngày giờ không hợp lệ (ISO format: YYYY-MM-DDTHH:MM)")

    if not madv_list:
        raise AppointmentValidationError("Vui lòng chọn ít nhất một dịch vụ")

    duration = calculate_total_duration(madv_list)

    technicians = get_staff_working_at(start_dt, duration)

    staff_results = []
    for tech in technicians:
        is_avail, conflicts, reason = check_staff_availability(tech.manv, start_dt, duration)
        position = tech.chucvu.tencv if tech.chucvu else "Kỹ thuật viên"
        staff_results.append({
            "manv": tech.manv,
            "hoten": tech.hoten,
            "chucvu": position,
            "chuyenmon": position,
            "anhdaidien": tech.anhnhanvien if hasattr(tech, 'anhnhanvien') else None,
            "available": is_avail,
            "reason": reason,
            "message": AVAILABILITY_MESSAGES.get(reason, reason),
            "conflicts": conflicts,
        })

    return staff_results


def find_available_staff(start_dt, madv_list):
    """
    Tìm nhân viên khả dụng cho khung giờ và dịch vụ yêu cầu.
    Quy tắc auto-assign:
    - Có ca làm việc bao phủ khung giờ.
    - Không overlap lịch hẹn.
    - Ít lịch hẹn nhất trong ngày (đếm trạng thái active: pending, confirmed, in_progress).
    - Tie-break ổn định: manv ASC.
    
    Returns:
        (best_staff: NhanVien | None, available_candidates: list[dict])
    """
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)

    duration = calculate_total_duration(madv_list)
    working_staff_list = get_staff_working_at(start_dt, duration)

    if not working_staff_list:
        return None, []

    target_date = start_dt.date()
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date + timedelta(days=1), time.min)

    # Đếm số lịch active trong ngày của từng nhân viên
    daily_counts = db.session.query(
        LichHen.manv,
        func.count(LichHen.malh).label('apt_count')
    ).filter(
        LichHen.ngaygio >= start_of_day,
        LichHen.ngaygio < end_of_day,
        LichHen.trangthai.in_(AppointmentStatus.ACTIVE_STATUSES)
    ).group_by(LichHen.manv).all()

    count_map = {row.manv: row.apt_count for row in daily_counts}

    available_candidates = []
    for staff in working_staff_list:
        is_avail, _, _ = check_staff_availability(staff.manv, start_dt, duration)
        if is_avail:
            count = count_map.get(staff.manv, 0)
            available_candidates.append({
                'staff': staff,
                'manv': staff.manv,
                'hoten': staff.hoten,
                'chucvu': staff.chucvu.tencv if staff.chucvu else "Kỹ thuật viên",
                'appointment_count': count
            })

    if not available_candidates:
        return None, []

    # Sort: ít lịch nhất trước, tie-break theo manv nhỏ hơn
    available_candidates.sort(key=lambda x: (x['appointment_count'], x['manv']))
    best_staff = available_candidates[0]['staff']

    return best_staff, available_candidates


def create_appointment(customer_id, madv_list, start_dt, manv=None, note=None, source='web', package_usages=None,
                       created_by_staff=None):
    """
    Tạo lịch hẹn mới (Atomic transaction).
    Dùng chung cho Customer Booking API, Admin Booking API, và AI Assistant.
    """
    booking_source = 'customer' if source == 'web' else source
    if booking_source not in ('customer', 'admin', 'ai'):
        raise AppointmentValidationError('Nguồn đặt lịch không hợp lệ')
    if booking_source != 'admin':
        created_by_staff = None

    # 1. Parse & validate start_dt
    if isinstance(start_dt, str):
        try:
            start_dt = datetime.strptime(start_dt, "%Y-%m-%dT%H:%M")
        except ValueError:
            try:
                start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    start_dt = datetime.fromisoformat(start_dt)
                except ValueError:
                    raise AppointmentValidationError("Định dạng ngày giờ không hợp lệ (cần YYYY-MM-DDTHH:MM)")

    if start_dt < datetime.now():
        raise AppointmentValidationError("Không thể đặt lịch trong quá khứ")

    # 2. Validate customer
    if not customer_id:
        raise AppointmentValidationError("Thiếu thông tin khách hàng")
    customer = KhachHang.query.get(customer_id)
    if not customer:
        raise AppointmentValidationError("Không tìm thấy thông tin khách hàng")

    # 3. Validate services
    if not madv_list:
        raise AppointmentValidationError("Vui lòng chọn ít nhất một dịch vụ")

    madv_ids = []
    for m in madv_list:
        try:
            madv_ids.append(int(m))
        except (ValueError, TypeError):
            continue

    if not madv_ids:
        raise AppointmentValidationError("Danh sách dịch vụ không hợp lệ")

    services = DichVu.query.filter(DichVu.madv.in_(madv_ids)).all()
    if len(services) != len(set(madv_ids)):
        raise AppointmentValidationError("Một số dịch vụ không tồn tại trong hệ thống")

    # Kiểm tra dịch vụ có đang active không
    for s in services:
        if hasattr(s, 'active') and s.active is False:
            raise AppointmentValidationError(f"Dịch vụ '{s.tendv}' hiện đang tạm ngừng cung cấp")

    total_duration = sum(s.thoiluong for s in services if s.thoiluong and s.thoiluong > 0)
    if total_duration <= 0:
        total_duration = 60

    # 4. Kiểm tra hoặc tự động gán nhân viên
    assigned_manv = None
    if manv:
        try:
            manv = int(manv)
        except (ValueError, TypeError):
            raise AppointmentValidationError("Mã nhân viên không hợp lệ")

        is_avail, conflicts, reason = check_staff_availability(manv, start_dt, total_duration)
        if not is_avail:
            staff = db.session.get(NhanVien, manv) if hasattr(db.session, "get") else NhanVien.query.get(manv)
            staff_name = staff.hoten if staff else "Nhân viên"
            reason_msg = AVAILABILITY_MESSAGES.get(reason, reason)
            raise AppointmentConflictError(
                f"{staff_name} không khả dụng trong khung giờ này: {reason_msg}",
                conflicts=conflicts
            )
        assigned_manv = manv
    else:
        best_staff, _ = find_available_staff(start_dt, madv_ids)
        if not best_staff:
            raise NoStaffAvailableError("Không có nhân viên rảnh vào khung giờ này. Vui lòng chọn giờ khác!")
        assigned_manv = best_staff.manv

    # 5. Lưu vào database (Atomic Transaction)
    try:
        new_appointment = LichHen(
            makh=customer_id,
            ngaygio=start_dt,
            manv=assigned_manv,
            trangthai=AppointmentStatus.CONFIRMED,
            ghichu=note.strip() if note and isinstance(note, str) else None,
            booking_source=booking_source,
            created_by_staff=created_by_staff,
        )
        db.session.add(new_appointment)
        db.session.flush()

        for madv in madv_ids:
            detail = ChiTietLichHen(
                malh=new_appointment.malh,
                madv=madv
            )
            db.session.add(detail)

        db.session.flush()
        from .package_service import reserve_usages
        from .notification_service import sync_appointment_jobs
        reserve_usages(new_appointment, [] if package_usages is None else package_usages,
                       require_item_id=booking_source == 'admin')
        sync_appointment_jobs(new_appointment)
        db.session.commit()
    except AppointmentValidationError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi database khi tạo lịch hẹn: {e}", exc_info=True)
        raise AppointmentServiceError("Lỗi hệ thống khi lưu lịch hẹn. Vui lòng thử lại sau!", status_code=500)

    # 6. Gửi email xác nhận
    assigned_staff = NhanVien.query.get(assigned_manv) if assigned_manv else None
    end_time_dt = start_dt + timedelta(minutes=total_duration)
    appointment_data = {
        'malh': new_appointment.malh,
        'ngaygio': new_appointment.ngaygio,
        'start_dt': start_dt,
        'end_time_str': end_time_dt.strftime('%H:%M'),
        'trangthai': new_appointment.trangthai,
        'staff_name': assigned_staff.hoten if assigned_staff else "Chưa chỉ định",
        'services': [{
            'madv': s.madv,
            'tendv': s.tendv,
            'thoiluong': s.thoiluong if s.thoiluong else 60,
            'gia': float(s.gia)
        } for s in services]
    }

    if customer.email:
        send_appointment_confirmation_email_async(
            customer.email,
            customer.hoten,
            appointment_data
        )

    return {
        "success": True,
        "message": "Đặt lịch thành công!",
        "appointment": {
            "malh": new_appointment.malh,
            "ngaygio": new_appointment.ngaygio.isoformat(),
            "trangthai": new_appointment.trangthai,
            "trangthai_vi": AppointmentStatus.to_vietnamese(new_appointment.trangthai),
            "nhanvien": assigned_staff.hoten if assigned_staff else None,
            "manv": assigned_manv,
            "total_duration": total_duration,
            "end_time": end_time_dt.strftime('%H:%M'),
            "ghichu": new_appointment.ghichu,
            "booking_source": new_appointment.booking_source,
            "created_by_staff": new_appointment.created_by_staff,
            "services": [s['tendv'] for s in appointment_data['services']]
        }
    }


CUSTOMER_EDITABLE_STATUSES = (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)
NO_SHOW_GRACE_MINUTES = 30
NO_SHOW_EMAIL_MAX_AGE_HOURS = 24


def vn_now():
    """Giờ Việt Nam dạng naive, cùng quy ước với LichHen.ngaygio (không phụ thuộc múi giờ máy chủ)."""
    return datetime.utcnow() + timedelta(hours=7)


def customer_can_modify(apt, now=None):
    """Khách được hủy/đổi dịch vụ khi lịch chưa bắt đầu và chưa tới giờ hẹn."""
    return apt.trangthai in CUSTOMER_EDITABLE_STATUSES and apt.ngaygio > (now or vn_now())


def _lock_appointment(appointment_id):
    LichHen.query.filter_by(malh=appointment_id).update({LichHen.malh: LichHen.malh}, synchronize_session=False)
    apt = LichHen.query.filter_by(malh=appointment_id).populate_existing().first()
    if not apt:
        raise AppointmentNotFoundError("Không tìm thấy lịch hẹn")
    return apt


SYSTEM_NOTE_KINDS = ('Đổi dịch vụ', 'Check-in', 'Tự động hủy')
_SYSTEM_NOTE_RE = re.compile(r'\[(Đổi dịch vụ|Check-in|Tự động hủy)\s+(\d{2}:\d{2} \d{2}/\d{2}/\d{4})([^\]]*)\]')


def set_system_note(apt, kind, text):
    """Ghi chú hệ thống dạng "[kind ...]": mỗi loại chỉ giữ bản mới nhất để ghi chú không dài thêm."""
    pattern = re.compile(r'\s*\[' + re.escape(kind) + r'\s+\d{2}:\d{2} \d{2}/\d{2}/\d{4}[^\]]*\]')
    base = pattern.sub('', apt.ghichu or '').strip()
    note = f'[{kind} {text}]'
    apt.ghichu = f'{base}\n{note}' if base else note


def split_notes(ghichu):
    """Tách ghi chú của khách/nhân viên khỏi ghi chú hệ thống. Lấy bản mới nhất của từng loại."""
    events = {}
    for kind, at, rest in _SYSTEM_NOTE_RE.findall(ghichu or ''):
        events[kind] = dict(at=at, detail=rest.lstrip(':').strip())
    remaining = _SYSTEM_NOTE_RE.sub('', ghichu or '')
    user_note = '\n'.join(line.strip() for line in remaining.splitlines() if line.strip())
    return user_note, events


def change_appointment_services(appointment_id, madv_list, user_id=None, role='customer', package_usages=None,
                                actor_name=None):
    """
    Đổi danh sách dịch vụ của một lịch hẹn chưa kết thúc.
    - Khách: chỉ lịch của mình, trạng thái chờ xác nhận/đã xác nhận, trước giờ hẹn.
    - KTV (role staff): chỉ lịch được phân cho mình; lễ tân/quản lý/admin: mọi lịch đang hoạt động
      (kể cả đang thực hiện, khi khách yêu cầu đổi tại quầy).
    - Giữ nguyên giờ hẹn và KTV; kiểm tra lại ca làm/trùng lịch với tổng thời lượng mới.
    - Buổi gói đang giữ cho dịch vụ còn lại được giữ nguyên; dịch vụ bị bỏ thì trả lại buổi.
      package_usages (tùy chọn) chỉ áp cho dịch vụ chưa có buổi gói đang giữ.
    """
    apt = _lock_appointment(appointment_id)
    if role == 'customer':
        if user_id is not None and apt.makh != user_id:
            raise AppointmentPermissionError("Bạn không có quyền sửa lịch hẹn này")
        if not customer_can_modify(apt):
            raise AppointmentValidationError(
                "Chỉ đổi dịch vụ được trước giờ hẹn. Vui lòng liên hệ spa nếu cần hỗ trợ!")
    elif role == 'staff' and apt.manv != user_id:
        raise AppointmentPermissionError("Bạn chỉ đổi dịch vụ cho lịch được phân cho mình")
    if apt.trangthai not in AppointmentStatus.ACTIVE_STATUSES:
        raise AppointmentValidationError(
            f"Không thể đổi dịch vụ của lịch hẹn đã {AppointmentStatus.to_vietnamese(apt.trangthai)}")

    try:
        new_ids = list(dict.fromkeys(int(m) for m in (madv_list or [])))
    except (ValueError, TypeError):
        raise AppointmentValidationError("Danh sách dịch vụ không hợp lệ")
    if not new_ids:
        raise AppointmentValidationError("Vui lòng chọn ít nhất một dịch vụ")
    services = DichVu.query.filter(DichVu.madv.in_(new_ids)).all()
    if len(services) != len(new_ids):
        raise AppointmentValidationError("Một số dịch vụ không tồn tại trong hệ thống")
    old_ids = [d.madv for d in apt.chitiet]
    for service in services:
        if service.active is False and service.madv not in old_ids:
            raise AppointmentValidationError(f"Dịch vụ '{service.tendv}' hiện đang tạm ngừng cung cấp")
    if set(new_ids) == set(old_ids) and not package_usages:
        raise AppointmentValidationError("Danh sách dịch vụ không thay đổi")

    duration = sum(s.thoiluong for s in services if s.thoiluong and s.thoiluong > 0) or 60
    if apt.manv:
        is_avail, conflicts, reason = check_staff_availability(apt.manv, apt.ngaygio, duration, exclude_malh=apt.malh)
        if not is_avail:
            staff = db.session.get(NhanVien, apt.manv)
            raise AppointmentConflictError(
                f"{staff.hoten if staff else 'Kỹ thuật viên'} không đủ thời gian cho dịch vụ mới "
                f"({duration} phút): {AVAILABILITY_MESSAGES.get(reason, reason)}",
                conflicts=conflicts)

    from ..models import LieuTrinhUsage
    from .package_service import reserve_usages, lock_treatment
    from .notification_service import sync_appointment_jobs
    names = {s.madv: s.tendv for s in services}
    try:
        usages = LieuTrinhUsage.query.filter_by(malh=apt.malh).all()
        for usage in usages:
            if usage.madv not in new_ids:
                if usage.state != 'reserved':
                    raise AppointmentValidationError("Không thể bỏ dịch vụ đã trừ buổi liệu trình")
                lock_treatment(usage.mathe)
                db.session.delete(usage)  # buổi đang giữ quay lại số buổi khả dụng
        covered = {u.madv for u in usages if u.madv in new_ids}
        for detail in list(apt.chitiet):
            if detail.madv not in new_ids:
                db.session.delete(detail)
        for madv in new_ids:
            if madv not in old_ids:
                db.session.add(ChiTietLichHen(malh=apt.malh, madv=madv))
        db.session.flush()
        db.session.expire(apt, ['chitiet'])
        if package_usages:
            if not isinstance(package_usages, list) or any(
                    not isinstance(row, dict) or row.get('madv') in covered for row in package_usages):
                raise AppointmentValidationError("Dịch vụ này đã dùng buổi gói trong lịch hẹn")
            reserve_usages(apt, package_usages, require_item_id=role != 'customer')
        set_system_note(apt, 'Đổi dịch vụ', f"{vn_now():%H:%M %d/%m/%Y}"
                        f"{' bởi ' + actor_name if actor_name else ''}: {', '.join(names[m] for m in new_ids)}")
        sync_appointment_jobs(apt)
        db.session.commit()
    except AppointmentServiceError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi đổi dịch vụ lịch hẹn {appointment_id}: {e}", exc_info=True)
        raise AppointmentServiceError("Lỗi hệ thống khi đổi dịch vụ", status_code=500)

    return {
        "success": True,
        "message": "Đã cập nhật dịch vụ của lịch hẹn",
        "malh": apt.malh,
        "services": [names[m] for m in new_ids],
        "total_duration": duration,
        "end_time": (apt.ngaygio + timedelta(minutes=duration)).strftime('%H:%M'),
    }


def can_check_in(apt, now=None):
    """Check-in được khi lịch chờ/đã xác nhận và trong ngày hẹn (khách đến sớm hoặc trễ trong ngày)."""
    now = now or vn_now()
    return apt.trangthai in CUSTOMER_EDITABLE_STATUSES and apt.ngaygio.date() == now.date()


def check_in_appointment(appointment_id, user_id=None, role='letan', actor_name=None):
    """
    Ghi nhận khách đã đến: chuyển lịch sang "Đang thực hiện" (in_progress).
    Lịch đã check-in không bị tự hủy vì không đến; nhắc lịch còn chờ được hủy.
    KTV chỉ check-in lịch được phân cho mình; lễ tân/quản lý/admin check-in mọi lịch.
    """
    from .notification_service import sync_appointment_jobs
    apt = _lock_appointment(appointment_id)
    if role == 'staff' and apt.manv != user_id:
        raise AppointmentPermissionError("Bạn chỉ check-in lịch được phân cho mình")
    if apt.trangthai not in CUSTOMER_EDITABLE_STATUSES:
        raise AppointmentValidationError(
            f"Không thể check-in lịch hẹn {AppointmentStatus.to_vietnamese(apt.trangthai).lower()}")
    now = vn_now()
    if apt.ngaygio.date() != now.date():
        raise AppointmentValidationError("Chỉ check-in được trong ngày hẹn")
    try:
        apt.trangthai = AppointmentStatus.IN_PROGRESS
        set_system_note(apt, 'Check-in', f"{now:%H:%M %d/%m/%Y}{' bởi ' + actor_name if actor_name else ''}")
        sync_appointment_jobs(apt)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi check-in lịch hẹn {appointment_id}: {e}", exc_info=True)
        raise AppointmentServiceError("Lỗi hệ thống khi check-in", status_code=500)
    late = int((now - apt.ngaygio).total_seconds() // 60)
    return {
        "success": True,
        "message": "Đã check-in, lịch chuyển sang Đang thực hiện"
                   + (f" (trễ {late} phút)" if late > 0 else ""),
        "malh": apt.malh,
        "trangthai": apt.trangthai,
        "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
        "checked_in_at": now.isoformat(timespec='minutes'),
    }


def auto_cancel_no_shows(now=None, grace_minutes=None, limit=200):
    """
    Tự hủy lịch chờ xác nhận/đã xác nhận mà khách không đến sau `grace_minutes` (mặc định 30 phút):
    trả lại buổi gói đang giữ, hủy nhắc lịch và xếp email thông báo vào outbox (worker gửi, có retry).
    Mỗi lịch xử lý trong transaction riêng; chạy lặp lại không hủy/gửi trùng.
    """
    from ..models import LieuTrinhUsage
    from .package_service import transition_usages
    from .notification_service import sync_appointment_jobs, enqueue_no_show_cancelled
    now = now or vn_now()
    if grace_minutes is None:
        grace_minutes = current_app.config.get('NO_SHOW_GRACE_MINUTES', NO_SHOW_GRACE_MINUTES)
    cutoff = now - timedelta(minutes=grace_minutes)
    ids = [row[0] for row in db.session.query(LichHen.malh).filter(
        LichHen.trangthai.in_(CUSTOMER_EDITABLE_STATUSES), LichHen.ngaygio <= cutoff,
    ).order_by(LichHen.ngaygio).limit(limit).all()]
    db.session.commit()
    cancelled = []
    for malh in ids:
        try:
            apt = _lock_appointment(malh)
            if apt.trangthai not in CUSTOMER_EDITABLE_STATUSES or apt.ngaygio > cutoff:
                db.session.rollback()
                continue  # đã check-in/hủy ở nơi khác trong lúc chờ khóa
            released = LieuTrinhUsage.query.filter_by(malh=malh, state='reserved').count()
            apt.trangthai = AppointmentStatus.CANCELLED
            transition_usages(apt.malh, 'released')
            sync_appointment_jobs(apt)
            set_system_note(apt, 'Tự động hủy', f"{now:%H:%M %d/%m/%Y}: khách không đến sau {grace_minutes} phút")
            # Chỉ báo email cho lịch vừa lỡ; lịch tồn đọng lâu ngày chỉ hủy, tránh gửi thư cho lịch đã cũ.
            max_age = current_app.config.get('NO_SHOW_EMAIL_MAX_AGE_HOURS', NO_SHOW_EMAIL_MAX_AGE_HOURS)
            if apt.ngaygio >= now - timedelta(hours=max_age):
                enqueue_no_show_cancelled(apt, released_sessions=released, grace_minutes=grace_minutes)
            db.session.commit()
            cancelled.append(malh)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Lỗi tự hủy lịch không đến #{malh}: {e}", exc_info=True)
    if cancelled:
        current_app.logger.info(f"[no-show] Tự hủy {len(cancelled)} lịch: {cancelled}")
    return cancelled


def cancel_appointment(appointment_id, user_id=None, role='customer', reason=None):
    """
    Hủy lịch hẹn:
    - Nếu role='customer':
      + Phải là chủ lịch hẹn (apt.makh == user_id).
      + Chỉ hủy lịch chờ xác nhận/đã xác nhận và trước giờ hẹn.
        Quá giờ hẹn mà khách không đến: hệ thống tự hủy sau NO_SHOW_GRACE_MINUTES.
    - Nếu role in ('admin', 'manager', 'letan', 'staff'):
      + Không được hủy nếu đã completed hoặc cancelled.
    """
    apt = _lock_appointment(appointment_id)

    # Kiểm tra quyền
    if role == 'customer':
        if user_id is not None and apt.makh != user_id:
            raise AppointmentPermissionError("Bạn không có quyền hủy lịch hẹn này")

    # Kiểm tra trạng thái hiện tại
    if apt.trangthai in AppointmentStatus.FINAL_STATUSES:
        raise AppointmentValidationError(
            f"Không thể hủy lịch hẹn đã {AppointmentStatus.to_vietnamese(apt.trangthai)}"
        )

    # Khách chỉ tự hủy trước giờ hẹn; lịch đang thực hiện phải liên hệ spa.
    if role == 'customer':
        if apt.trangthai not in CUSTOMER_EDITABLE_STATUSES:
            raise AppointmentValidationError("Lịch hẹn đang được thực hiện, vui lòng liên hệ spa để được hỗ trợ!")
        if apt.ngaygio <= vn_now():
            raise AppointmentValidationError(
                "Đã đến hoặc quá giờ hẹn nên không thể tự hủy. Vui lòng liên hệ spa để được hỗ trợ!"
            )

    try:
        apt.trangthai = AppointmentStatus.CANCELLED
        from .package_service import transition_usages
        from .notification_service import sync_appointment_jobs
        transition_usages(apt.malh, 'released')
        sync_appointment_jobs(apt)
        if reason:
            cancel_str = f"[Lý do hủy: {reason.strip()}]"
            apt.ghichu = f"{apt.ghichu}\n{cancel_str}" if apt.ghichu else cancel_str

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi hủy lịch hẹn {appointment_id}: {e}", exc_info=True)
        raise AppointmentServiceError("Lỗi hệ thống khi hủy lịch hẹn", status_code=500)

    return {
        "success": True,
        "message": "Hủy lịch hẹn thành công",
        "malh": apt.malh,
        "trangthai": apt.trangthai,
        "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai)
    }


def update_appointment_status(appointment_id, new_status, user_id=None, role='staff', commit=True):
    """
    Cập nhật trạng thái lịch hẹn:
    - new_status: 'pending', 'confirmed', 'in_progress', 'completed', 'cancelled'
    - Kiểm tra transition hợp lệ.
    - Enqueue post-care cùng transaction nếu hoàn thành; worker gửi sau commit.
    """
    LichHen.query.filter_by(malh=appointment_id).update({LichHen.malh:LichHen.malh}, synchronize_session=False)
    apt = LichHen.query.filter_by(malh=appointment_id).populate_existing().first()
    if not apt:
        raise AppointmentNotFoundError("Không tìm thấy lịch hẹn")

    # Nhân viên role='staff' chỉ được cập nhật lịch của chính mình
    if role == 'staff' and apt.manv != user_id:
        raise AppointmentPermissionError("Bạn không có quyền sửa lịch hẹn này")

    norm_status = AppointmentStatus.normalize(new_status)
    if norm_status not in AppointmentStatus.ALL:
        raise AppointmentValidationError(f"Trạng thái '{new_status}' không hợp lệ")

    from ..models import LieuTrinhUsage
    if apt.trangthai in AppointmentStatus.FINAL_STATUSES and norm_status != apt.trangthai:
        if LieuTrinhUsage.query.filter_by(malh=apt.malh).first():
            raise AppointmentValidationError('Không mở lại hoặc đổi trạng thái kết thúc lịch hẹn đã dùng liệu trình')

    # Không thể cập nhật lịch đã ở trạng thái kết thúc (completed/cancelled) trừ khi là admin/manager
    if apt.trangthai in AppointmentStatus.FINAL_STATUSES and norm_status != apt.trangthai and role not in ('admin', 'manager'):
        raise AppointmentValidationError(
            f"Không thể cập nhật lịch hẹn đã {AppointmentStatus.to_vietnamese(apt.trangthai)}"
        )

    try:
        previous_status = apt.trangthai
        apt.trangthai = norm_status
        from .package_service import transition_usages
        from .notification_service import sync_appointment_jobs
        from . import commission_service
        if norm_status == AppointmentStatus.COMPLETED:
            transition_usages(apt.malh, 'consumed')
            commission_service.record_for_appointment(apt)
        elif norm_status == AppointmentStatus.CANCELLED:
            transition_usages(apt.malh, 'released')
        if previous_status == AppointmentStatus.COMPLETED and norm_status != AppointmentStatus.COMPLETED:
            commission_service.void_for_appointment(apt.malh)
        sync_appointment_jobs(apt)
        if commit:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi cập nhật trạng thái lịch hẹn {appointment_id}: {e}", exc_info=True)
        raise AppointmentServiceError("Lỗi hệ thống khi cập nhật trạng thái", status_code=500)

    return {
        "success": True,
        "message": f"Cập nhật trạng thái thành '{AppointmentStatus.to_vietnamese(norm_status)}' thành công",
        "malh": apt.malh,
        "trangthai": apt.trangthai,
        "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai)
    }


def assign_staff_to_appointment(appointment_id, manv):
    """Gán nhân viên cho lịch hẹn, kiểm tra ca làm và trùng lịch."""
    apt = LichHen.query.get(appointment_id)
    if not apt:
        raise AppointmentNotFoundError("Không tìm thấy lịch hẹn")

    staff = NhanVien.query.get(manv)
    if not staff:
        raise AppointmentNotFoundError("Không tìm thấy nhân viên")

    # Tính tổng thời lượng của lịch hẹn này
    duration = 0
    for detail in apt.chitiet:
        if detail.dichvu and detail.dichvu.thoiluong:
            duration += detail.dichvu.thoiluong
    if duration <= 0:
        duration = 60

    is_avail, conflicts, reason = check_staff_availability(
        manv, apt.ngaygio, duration, exclude_malh=apt.malh
    )
    if not is_avail:
        reason_msg = AVAILABILITY_MESSAGES.get(reason, reason)
        raise AppointmentConflictError(
            f"Nhân viên {staff.hoten} không khả dụng: {reason_msg}",
            conflicts=conflicts
        )

    try:
        apt.manv = manv
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi gán nhân viên cho lịch hẹn {appointment_id}: {e}", exc_info=True)
        raise AppointmentServiceError("Lỗi hệ thống khi gán nhân viên", status_code=500)

    return {
        "success": True,
        "message": f"Đã gán nhân viên {staff.hoten} cho lịch hẹn #{apt.malh}",
        "malh": apt.malh,
        "manv": manv,
        "nhanvien_hoten": staff.hoten
    }


SLOT_FIRST = time(7, 30)
SLOT_LAST = time(18, 30)
SLOT_STEP_MINUTES = 30


def slot_times():
    """Các giờ bắt đầu hợp lệ trong ngày (07:30 → 18:30, bước 30 phút), không trùng lặp."""
    current = datetime.combine(date.min, SLOT_FIRST)
    last = datetime.combine(date.min, SLOT_LAST)
    times = []
    while current <= last:
        times.append(current.time())
        current += timedelta(minutes=SLOT_STEP_MINUTES)
    return times


def _slot_available(slot_dt, duration, manv=None):
    if manv:
        return check_staff_availability(manv, slot_dt, duration)[0]
    return any(check_staff_availability(staff.manv, slot_dt, duration)[0]
               for staff in get_staff_working_at(slot_dt, duration))


def get_available_slots(target_date, madv=None, manv=None, madv_list=None):
    """
    Khung giờ trong ngày cho tổng thời lượng các dịch vụ đã chọn.
    - madv_list (ưu tiên) hoặc madv: tính tổng thời lượng; không có → 60 phút.
    - reason: 'past' | 'unavailable' | 'available'.
    - Có manv: xét riêng nhân viên đó; không có: cần ít nhất 1 KTV có ca phủ hết và không trùng lịch.
    Server vẫn kiểm tra lại khi tạo lịch; đây chỉ là gợi ý cho giao diện.
    """
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    ids = madv_list if madv_list else ([madv] if madv else [])
    duration = calculate_total_duration(ids)
    try:
        manv_int = int(manv) if manv else None
    except (ValueError, TypeError):
        manv_int = None

    slots = []
    now = datetime.now()
    for slot_time in slot_times():
        slot_dt = datetime.combine(target_date, slot_time)
        if slot_dt < now:
            available, reason = False, "past"
        else:
            available = _slot_available(slot_dt, duration, manv_int)
            reason = "available" if available else "unavailable"
        slots.append({"time": slot_time.strftime("%H:%M"), "available": available, "reason": reason})
    return slots


def suggest_next_slots(after_date, madv_list=None, manv=None, days=14, limit=3):
    """Gợi ý tối đa `limit` ngày tiếp theo còn chỗ, mỗi ngày lấy giờ sớm nhất."""
    if isinstance(after_date, str):
        after_date = datetime.strptime(after_date, "%Y-%m-%d").date()
    suggestions = []
    for offset in range(1, days + 1):
        day = after_date + timedelta(days=offset)
        first = next((s for s in get_available_slots(day, manv=manv, madv_list=madv_list) if s["available"]), None)
        if first:
            suggestions.append({"date": day.isoformat(), "time": first["time"]})
            if len(suggestions) >= limit:
                break
    return suggestions

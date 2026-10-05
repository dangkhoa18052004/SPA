import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..decorators import customer_required
from flask import g
from ..models import (
    ChucVu,
    LichHen,
    KhachHang,
    DichVu,
    NhanVien,
    ChiTietLichHen,
    LieuTrinhUsage,
    AppointmentStatus,
)
from ..services import appointment_service, prepay_service
from ..services.appointment_service import (
    AppointmentServiceError,
    AppointmentNotFoundError,
    AppointmentPermissionError,
    AppointmentValidationError,
    AppointmentConflictError,
    NoStaffAvailableError,
)

appointment_bp = Blueprint("appointment", __name__)


def _parse_jwt_user_id(identity):
    """Trích xuất ID người dùng và loại tài khoản từ JWT identity."""
    if identity is None:
        return None, None
    identity_str = str(identity)
    if ":" in identity_str:
        parts = identity_str.split(":", 1)
        role = parts[0]
        try:
            user_id = int(parts[1])
            return user_id, role
        except ValueError:
            return None, None
    try:
        return int(identity_str), "customer"
    except ValueError:
        return None, None


# =========================================================================
# CUSTOMER APPOINTMENT ROUTES
# =========================================================================

@appointment_bp.route("/create", methods=["POST"])
@customer_required
def create_appointment():
    """Tạo lịch hẹn mới (khách hàng tự đặt qua web)."""
    identity = get_jwt_identity()
    makh, role = _parse_jwt_user_id(identity)

    if not makh:
        return jsonify({"success": False, "message": "Không tìm thấy mã khách hàng hợp lệ trong token"}), 401

    data = request.get_json() or {}
    dichvu_ids = data.get("madv_list", [])
    manv = data.get("manv")
    ngaygio_str = data.get("ngaygio")
    ghichu = data.get("ghichu") or data.get("note")

    if not dichvu_ids or not ngaygio_str:
        return jsonify({"success": False, "message": "Thiếu thông tin dịch vụ hoặc thời gian hẹn"}), 400

    payment_option = data.get("payment_option") or "at_spa"
    if payment_option not in ("at_spa", "prepay"):
        return jsonify({"success": False, "message": "Hình thức thanh toán không hợp lệ"}), 400
    if payment_option == "prepay":
        from ..services.vietqr_service import vietqr_available
        if not vietqr_available():
            return jsonify({"success": False, "message": "Thanh toán VietQR tạm thời chưa khả dụng, vui lòng chọn thanh toán tại spa"}), 503

    try:
        result = appointment_service.create_appointment(
            customer_id=makh,
            madv_list=dichvu_ids,
            start_dt=ngaygio_str,
            manv=manv,
            note=ghichu,
            source="web",
            package_usages=data.get('package_usages', []),
            prepay=payment_option == "prepay",
        )
        return jsonify(result), 201

    except NoStaffAvailableError as e:
        return jsonify({
            "success": False,
            "message": e.message,
            "conflicts": e.conflicts
        }), 409

    except AppointmentConflictError as e:
        return jsonify({
            "success": False,
            "message": e.message,
            "conflicts": e.conflicts
        }), 409

    except AppointmentValidationError as e:
        return jsonify({"success": False, "message": e.message}), 400

    except AppointmentServiceError as e:
        return jsonify({"success": False, "message": e.message}), e.status_code

    except Exception as e:
        current_app.logger.error(f"Lỗi không xác định khi tạo lịch hẹn: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Đặt lịch thất bại. Vui lòng thử lại!"}), 500


def _customer_notes(ghichu):
    """Khách chỉ thấy ghi chú của mình + lần đổi dịch vụ/check-in gần nhất (không bao gồm "bởi" nhân viên)."""
    note, events = appointment_service.split_notes(ghichu)
    change = events.get('Đổi dịch vụ')
    checkin = events.get('Check-in')
    return {
        "ghichu": note,
        "last_service_change_at": change['at'] if change else None,
        "checked_in_at": checkin['at'] if checkin else None,
        "auto_cancelled_at": events.get('Tự động hủy', {}).get('at'),
    }


@appointment_bp.route("/my-appointments", methods=["GET"])
@jwt_required()
def get_my_appointments():
    """Lấy danh sách lịch hẹn của khách hàng hiện tại."""
    identity = get_jwt_identity()
    makh, _ = _parse_jwt_user_id(identity)

    if not makh:
        return jsonify({"success": False, "message": "Không tìm thấy mã khách hàng trong token"}), 401

    try:
        appointments = (
            LichHen.query.filter_by(makh=makh)
            .order_by(LichHen.ngaygio.desc())
            .all()
        )

        result = []
        for apt in appointments:
            services = [
                detail.dichvu.tendv
                for detail in apt.chitiet
                if detail.dichvu
            ]

            staff_name = "Chưa phân công"
            if apt.manv:
                if apt.nhanvien:
                    staff_name = apt.nhanvien.hoten
                else:
                    staff = NhanVien.query.get(apt.manv)
                    if staff:
                        staff_name = staff.hoten

            covered = {u.madv for u in LieuTrinhUsage.query.filter(
                LieuTrinhUsage.malh == apt.malh, LieuTrinhUsage.state.in_(('reserved', 'consumed'))).all()}
            editable = appointment_service.customer_can_modify(apt)
            invoice = prepay_service.summary(apt)
            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "dichvu": ", ".join(services) if services else "Không có dịch vụ",
                "services": [dict(madv=d.madv, tendv=d.dichvu.tendv, gia=str(d.dichvu.gia),
                                  thoiluong=d.dichvu.thoiluong, package=d.madv in covered)
                             for d in apt.chitiet if d.dichvu],
                "can_cancel": editable,
                "can_change_services": editable and not (invoice and invoice['trangthai'] == prepay_service.PAID),
                "invoice": invoice,
                "nhanvien": staff_name,
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
                **_customer_notes(apt.ghichu),
            })

        return jsonify({"success": True, "appointments": result}), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy danh sách lịch hẹn: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi lấy danh sách lịch hẹn"}), 500


@appointment_bp.route("/<int:malh>/cancel", methods=["PUT", "POST"])
@jwt_required()
def cancel_my_appointment(malh):
    """Khách hàng hoặc nhân viên hủy lịch hẹn."""
    identity = get_jwt_identity()
    user_id, role = _parse_jwt_user_id(identity)

    if not user_id:
        return jsonify({"success": False, "message": "Không tìm thấy danh tính người dùng trong token"}), 401

    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")

    try:
        result = appointment_service.cancel_appointment(
            appointment_id=malh,
            user_id=user_id,
            role=role or "customer",
            reason=reason,
        )
        return jsonify(result), 200

    except AppointmentNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404

    except AppointmentPermissionError as e:
        return jsonify({"success": False, "message": e.message}), 403

    except AppointmentValidationError as e:
        return jsonify({"success": False, "message": e.message}), 400

    except AppointmentServiceError as e:
        return jsonify({"success": False, "message": e.message}), e.status_code

    except Exception as e:
        current_app.logger.error(f"Lỗi khi hủy lịch hẹn #{malh}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Hủy lịch hẹn thất bại"}), 500


@appointment_bp.route("/<int:malh>/services", methods=["PUT"])
@jwt_required()
def change_my_appointment_services(malh):
    """Khách đổi dịch vụ của lịch hẹn trước giờ hẹn."""
    user_id, role = _parse_jwt_user_id(get_jwt_identity())
    if not user_id or (role or "customer") != "customer":
        return jsonify({"success": False, "message": "Chỉ khách hàng dùng chức năng này"}), 403
    data = request.get_json(silent=True) or {}
    try:
        result = appointment_service.change_appointment_services(
            malh, data.get("madv_list"), user_id=user_id, role="customer",
            package_usages=data.get("package_usages"))
        return jsonify(result), 200
    except AppointmentConflictError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except AppointmentServiceError as e:
        return jsonify({"success": False, "message": e.message}), e.status_code


@appointment_bp.route("/available-slots", methods=["GET"])
def get_available_slots():
    """
    Khung giờ còn trống trong ngày theo tổng thời lượng dịch vụ (madv_list=1,2 hoặc madv=1).
    suggest=1: khi ngày đã chọn hết chỗ, trả thêm các ngày/giờ gần nhất còn trống.
    """
    date_str = request.args.get("date")
    madv = request.args.get("madv")
    manv = request.args.get("manv")
    raw_list = request.args.get("madv_list", "")
    madv_list = [x for x in raw_list.split(",") if x.strip().isdigit()] if raw_list else None

    if not date_str:
        return jsonify({"success": False, "message": "Thiếu ngày cần xem"}), 400
    try:
        target = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "message": "Ngày không hợp lệ"}), 400

    try:
        slots = appointment_service.get_available_slots(target, madv=madv, manv=manv, madv_list=madv_list)
        result = {
            "success": True,
            "date": target.isoformat(),
            "duration_minutes": appointment_service.calculate_total_duration(madv_list or ([madv] if madv else [])),
            "slots": slots,
        }
        if request.args.get("suggest") == "1" and not any(s["available"] for s in slots):
            result["suggestions"] = appointment_service.suggest_next_slots(target, madv_list=madv_list or ([madv] if madv else None), manv=manv)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy available slots: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi lấy danh sách khung giờ trống"}), 500


@appointment_bp.route("/available-staff", methods=["POST"])
@jwt_required(optional=True)
def get_available_staff():
    """
    Lấy kỹ thuật viên active có ca phù hợp, kèm trạng thái rảnh/trùng lịch cho booking.
    Business logic được xử lý tập trung trong appointment_service.
    """
    data = request.get_json(silent=True) or {}
    ngaygio_str = data.get("ngaygio")
    dichvu_ids = data.get("madv_list", [])

    if not ngaygio_str or not dichvu_ids:
        return jsonify({
            "success": False,
            "message": "Thiếu ngày giờ hoặc danh sách dịch vụ",
        }), 400

    try:
        staff_data = appointment_service.get_available_staff_for_booking(ngaygio_str, dichvu_ids)
        return jsonify({
            "success": True,
            "staff": staff_data,
        }), 200
    except AppointmentValidationError as e:
        return jsonify({"success": False, "message": e.message}), 400
    except Exception as e:
        current_app.logger.error(f"Lỗi kiểm tra danh sách nhân viên khả dụng: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "Lỗi hệ thống khi kiểm tra nhân viên khả dụng",
        }), 500


@appointment_bp.route("/check-availability", methods=["POST"])
@jwt_required(optional=True)
def api_check_staff_availability():
    """API kiểm tra nhân viên có khả dụng trong khung giờ hay không."""
    data = request.get_json(silent=True) or {}
    manv = data.get("manv")
    ngaygio_str = data.get("ngaygio")
    dichvu_ids = data.get("madv_list", [])

    if not all([manv, ngaygio_str, dichvu_ids]):
        return jsonify({
            "success": False,
            "available": False,
            "reason": appointment_service.AVAILABILITY_REASON_INVALID,
            "message": "Thiếu thông tin nhân viên, ngày giờ hoặc dịch vụ",
        }), 400

    try:
        duration = appointment_service.calculate_total_duration(dichvu_ids)
        is_available, conflicts, reason = appointment_service.check_staff_availability(
            manv=manv,
            start_dt=ngaygio_str,
            duration_minutes=duration,
        )

        message = appointment_service.AVAILABILITY_MESSAGES.get(reason, reason)
        return jsonify({
            "success": True,
            "available": is_available,
            "reason": reason,
            "message": message,
            "conflicts": conflicts,
            "duration": duration,
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi kiểm tra tính khả dụng: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "available": False,
            "reason": appointment_service.AVAILABILITY_REASON_API_ERROR,
            "message": "Lỗi hệ thống khi kiểm tra",
        }), 500


# =========================================================================
# COMPATIBILITY ENDPOINTS (Hỗ trợ frontend dashboard admin)
# =========================================================================

@appointment_bp.route("/<int:malh>/confirm", methods=["POST"])
@jwt_required(optional=True)
def confirm_appointment_compat(malh):
    """API xác nhận lịch hẹn (tương thích dashboard)."""
    identity = get_jwt_identity()
    user_id, role = _parse_jwt_user_id(identity)
    try:
        result = appointment_service.update_appointment_status(
            appointment_id=malh,
            new_status="confirmed",
            user_id=user_id,
            role=role or "admin",
        )
        return jsonify(result), 200
    except AppointmentServiceError as e:
        return jsonify({"success": False, "message": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi confirm lịch hẹn: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500


@appointment_bp.route("/<int:malh>/complete", methods=["POST"])
@jwt_required(optional=True)
def complete_appointment_compat(malh):
    """API hoàn thành lịch hẹn (tương thích dashboard)."""
    identity = get_jwt_identity()
    user_id, role = _parse_jwt_user_id(identity)
    try:
        result = appointment_service.update_appointment_status(
            appointment_id=malh,
            new_status="completed",
            user_id=user_id,
            role=role or "admin",
        )
        return jsonify(result), 200
    except AppointmentServiceError as e:
        return jsonify({"success": False, "message": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi complete lịch hẹn: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500

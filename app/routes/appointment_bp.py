import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import (
    ChucVu,
    LichHen,
    KhachHang,
    DichVu,
    NhanVien,
    ChiTietLichHen,
    AppointmentStatus,
)
from ..services import appointment_service
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
@jwt_required()
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

    try:
        result = appointment_service.create_appointment(
            customer_id=makh,
            madv_list=dichvu_ids,
            start_dt=ngaygio_str,
            manv=manv,
            note=ghichu,
            source="web",
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

            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "dichvu": ", ".join(services) if services else "Không có dịch vụ",
                "nhanvien": staff_name,
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
                "ghichu": apt.ghichu or "",
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


@appointment_bp.route("/available-slots", methods=["GET"])
def get_available_slots():
    """Lấy danh sách các khung giờ còn trống."""
    date_str = request.args.get("date")
    madv = request.args.get("madv")
    manv = request.args.get("manv")

    if not date_str:
        return jsonify({"success": False, "message": "Thiếu ngày cần xem"}), 400

    try:
        slots = appointment_service.get_available_slots(date_str, madv=madv, manv=manv)
        return jsonify({"success": True, "slots": slots}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy available slots: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi lấy danh sách khung giờ trống"}), 500


@appointment_bp.route("/check-availability", methods=["POST"])
@jwt_required(optional=True)
def api_check_staff_availability():
    """API kiểm tra nhân viên có khả dụng trong khung giờ hay không."""
    data = request.get_json() or {}
    manv = data.get("manv")
    ngaygio_str = data.get("ngaygio")
    dichvu_ids = data.get("madv_list", [])

    if not all([manv, ngaygio_str, dichvu_ids]):
        return jsonify({
            "success": False,
            "available": False,
            "message": "Thiếu thông tin nhân viên, ngày giờ hoặc dịch vụ",
        }), 400

    try:
        duration = appointment_service.calculate_total_duration(dichvu_ids)
        is_available, conflicts, reason = appointment_service.check_staff_availability(
            manv=manv,
            start_dt=ngaygio_str,
            duration_minutes=duration,
        )

        if is_available:
            return jsonify({
                "success": True,
                "available": True,
                "message": "Nhân viên rảnh trong khung giờ này",
                "duration": duration,
            }), 200
        else:
            return jsonify({
                "success": True,
                "available": False,
                "message": f"Nhân viên không khả dụng: {reason}",
                "conflicts": conflicts,
                "duration": duration,
            }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi kiểm tra tính khả dụng: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "available": False,
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
import os
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, current_app, g
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import (
    LichHen,
    KhachHang,
    DichVu,
    NhanVien,
    ChiTietLichHen,
    ChucVu,
    AppointmentStatus,
)
from ..decorators import roles_required
from ..services import appointment_service
from ..services.appointment_service import (
    AppointmentServiceError,
    AppointmentNotFoundError,
    AppointmentPermissionError,
    AppointmentValidationError,
    AppointmentConflictError,
    NoStaffAvailableError,
)

appointment_manage_bp = Blueprint("appointment_manage", __name__)


# =========================================================================
# HELPER MAPPINGS
# =========================================================================

def get_appointment_status_text(status):
    """Map mã trạng thái sang tiếng Việt hiển thị."""
    return AppointmentStatus.to_vietnamese(status)


# =========================================================================
# STAFF AVAILABILITY APIS
# =========================================================================

@appointment_manage_bp.route("/staff/available", methods=["GET"])
@roles_required("admin", "manager", "letan")
def get_available_staff_for_appointment():
    """Tìm nhân viên rảnh cho một ngày giờ và danh sách dịch vụ cụ thể."""
    try:
        ngaygio_str = request.args.get("ngaygio")
        madv_list_str = request.args.get("madv_list")

        if not ngaygio_str or not madv_list_str:
            return jsonify({"success": False, "msg": "Thiếu ngày giờ hoặc danh sách dịch vụ (madv_list)."}), 400

        try:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            try:
                ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return jsonify({"success": False, "msg": "Định dạng ngày giờ không hợp lệ (cần YYYY-MM-DDTHH:MM)."}), 400

        madv_list = [int(madv.strip()) for madv in madv_list_str.split(",") if madv.strip().isdigit()]
        total_duration = appointment_service.calculate_total_duration(madv_list)

        _, available_candidates = appointment_service.find_available_staff(ngaygio, madv_list)

        staff_results = [
            {
                "manv": c["manv"],
                "hoten": c["hoten"],
                "chuyenmon": c["chucvu"],
                "appointment_count": c["appointment_count"],
            }
            for c in available_candidates
        ]

        return jsonify({
            "success": True,
            "available_staff": staff_results,
            "total_duration": total_duration,
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi khi tìm nhân viên rảnh: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống khi tìm kiếm nhân viên rảnh"}), 500


@appointment_manage_bp.route("/appointments/check-availability", methods=["POST"])
def check_appointment_availability():
    """Kiểm tra tính khả dụng của nhân viên theo ngày giờ và dịch vụ."""
    try:
        data = request.get_json() or {}
        manv = data.get("manv")
        ngaygio_str = data.get("ngaygio")
        madv_list = data.get("madv_list", [])

        if not all([ngaygio_str, madv_list]):
            return jsonify({"msg": "Thiếu thông tin bắt buộc"}), 400

        try:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%d %H:%M:%S")

        total_duration = appointment_service.calculate_total_duration(madv_list)

        services = DichVu.query.filter(DichVu.madv.in_(madv_list)).all()
        services_info = [
            {"tendv": s.tendv, "thoiluong": s.thoiluong or 60}
            for s in services
        ]

        end_time_str = (ngaygio + timedelta(minutes=total_duration)).strftime("%H:%M")

        if manv:
            is_available, conflicts, reason = appointment_service.check_staff_availability(
                manv=int(manv),
                start_dt=ngaygio,
                duration_minutes=total_duration,
            )

            if not is_available:
                nhanvien = NhanVien.query.get(manv)
                staff_name = nhanvien.hoten if nhanvien else "Nhân viên"
                return jsonify({
                    "success": False,
                    "available": False,
                    "message": f"{staff_name} không khả dụng trong khung giờ {ngaygio.strftime('%H:%M')} - {end_time_str}: {reason}",
                    "conflicts": conflicts,
                    "suggestion": "Vui lòng chọn khung giờ khác hoặc chọn nhân viên khác",
                    "total_duration": total_duration,
                    "services": services_info,
                }), 200

        return jsonify({
            "success": True,
            "available": True,
            "message": "Khung giờ này còn trống",
            "duration": total_duration,
            "services": services_info,
            "end_time": end_time_str,
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi kiểm tra tính khả dụng: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống"}), 500


# =========================================================================
# APPOINTMENT CRUD (ADMIN & DESK)
# =========================================================================

@appointment_manage_bp.route("/appointments", methods=["POST"])
@roles_required("admin", "manager", "letan")
def create_appointment():
    """Admin / Lễ tân tạo lịch hẹn mới cho khách hàng."""
    try:
        data = request.get_json() or {}
        makh = data.get("makh")
        madv_list = data.get("madv_list", [])
        ngaygio_str = data.get("ngaygio")
        manv = data.get("manv")
        ghichu = data.get("ghichu") or data.get("note")

        if not all([makh, madv_list, ngaygio_str]):
            return jsonify({"msg": "Thiếu thông tin bắt buộc"}), 400

        res = appointment_service.create_appointment(
            customer_id=makh,
            madv_list=madv_list,
            start_dt=ngaygio_str,
            manv=manv,
            note=ghichu,
            source="admin",
        )

        return jsonify({
            "success": True,
            "msg": "Đặt lịch hẹn thành công",
            "malh": res["appointment"]["malh"],
            "manv_assigned": res["appointment"]["manv"],
            "appointment": res["appointment"],
        }), 201

    except NoStaffAvailableError as e:
        return jsonify({"success": False, "msg": e.message, "conflicts": e.conflicts}), 409
    except AppointmentConflictError as e:
        return jsonify({"success": False, "msg": e.message, "conflicts": e.conflicts}), 409
    except AppointmentValidationError as e:
        return jsonify({"success": False, "msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"success": False, "msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi tạo lịch hẹn (admin): {e}", exc_info=True)
        return jsonify({"msg": "Đặt lịch hẹn thất bại"}), 500


@appointment_manage_bp.route("/appointments/book", methods=["POST"])
def book_appointment_customer():
    """Endpoint khách hàng đặt lịch trên session web (g.current_user)."""
    try:
        customer = g.get("current_user")
        if not customer or not hasattr(customer, "makh"):
            return jsonify({"msg": "Vui lòng đăng nhập với tài khoản khách hàng"}), 401

        data = request.get_json() or {}
        madv_list = data.get("madv_list", [])
        ngaygio_str = data.get("ngaygio")
        manv = data.get("manv")
        ghichu = data.get("ghichu") or data.get("note")

        if not all([madv_list, ngaygio_str]):
            return jsonify({"msg": "Thiếu thông tin bắt buộc"}), 400

        res = appointment_service.create_appointment(
            customer_id=customer.makh,
            madv_list=madv_list,
            start_dt=ngaygio_str,
            manv=manv,
            note=ghichu,
            source="web",
        )

        return jsonify({
            "success": True,
            "msg": "Đặt lịch hẹn thành công! Chúng tôi đã gửi email xác nhận đến bạn.",
            "malh": res["appointment"]["malh"],
            "appointment": res["appointment"],
        }), 201

    except NoStaffAvailableError as e:
        return jsonify({"success": False, "msg": e.message, "conflicts": e.conflicts}), 409
    except AppointmentConflictError as e:
        return jsonify({"success": False, "msg": e.message, "conflicts": e.conflicts}), 409
    except AppointmentValidationError as e:
        return jsonify({"success": False, "msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"success": False, "msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi đặt lịch hẹn (book): {e}", exc_info=True)
        return jsonify({"msg": "Đặt lịch hẹn thất bại. Vui lòng thử lại"}), 500


@appointment_manage_bp.route("/appointments", methods=["GET"])
@roles_required("admin", "manager", "letan")
def get_all_appointments_admin():
    """Lấy danh sách lịch hẹn cho trang quản trị, hỗ trợ lọc theo ngày và trạng thái."""
    try:
        query = db.session.query(LichHen).outerjoin(
            KhachHang, LichHen.makh == KhachHang.makh
        )

        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        status = request.args.get("status")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(LichHen.ngaygio >= start_date)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)
            query = query.filter(LichHen.ngaygio < end_date)

        if status:
            norm_status = AppointmentStatus.normalize(status)
            query = query.filter(LichHen.trangthai == norm_status)

        appointments = (
            query.options(
                joinedload(LichHen.khachhang),
                joinedload(LichHen.nhanvien),
                joinedload(LichHen.chitiet).joinedload(ChiTietLichHen.dichvu),
            )
            .order_by(LichHen.ngaygio.desc())
            .all()
        )

        result = []
        for apt in appointments:
            dichvu_ten = "N/A"
            dichvu_count = len(apt.chitiet)
            if dichvu_count > 0:
                first_detail = apt.chitiet[0]
                if first_detail and first_detail.dichvu:
                    dichvu_ten = first_detail.dichvu.tendv
                    if dichvu_count > 1:
                        dichvu_ten += f" (+{dichvu_count - 1})"

            nhanvien_ten = apt.nhanvien.hoten if apt.nhanvien else "Chưa gán"

            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "khachhang_hoten": apt.khachhang.hoten if apt.khachhang else "N/A",
                "dichvu_ten": dichvu_ten,
                "nhanvien_hoten": nhanvien_ten,
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
                "ghichu": apt.ghichu or "",
            })

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy lịch hẹn (admin): {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/appointments/my-appointments", methods=["GET"])
def get_my_appointments():
    """Lấy danh sách lịch hẹn của khách hàng đang đăng nhập bằng session."""
    try:
        customer = g.get("current_user")
        if not customer or not hasattr(customer, "makh"):
            return jsonify({"success": False, "msg": "Vui lòng đăng nhập"}), 401

        appointments = (
            LichHen.query.filter_by(makh=customer.makh)
            .order_by(LichHen.ngaygio.desc())
            .all()
        )

        result = []
        for apt in appointments:
            services = []
            total_duration = 0
            for detail in apt.chitiet:
                if detail.dichvu:
                    services.append({
                        "madv": detail.madv,
                        "tendv": detail.dichvu.tendv,
                        "gia": str(detail.dichvu.gia),
                        "thoiluong": detail.dichvu.thoiluong,
                    })
                    if detail.dichvu.thoiluong:
                        total_duration += detail.dichvu.thoiluong

            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "dichvu": ", ".join([s["tendv"] for s in services]),
                "services": services,
                "nhanvien": apt.nhanvien.hoten if apt.nhanvien else "Chưa phân công",
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
                "total_duration": total_duration,
                "ghichu": apt.ghichu or "",
            })

        return jsonify({"success": True, "appointments": result}), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy danh sách lịch hẹn khách hàng: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/my-schedule-list", methods=["GET"])
@roles_required("staff", "letan")
def get_my_schedule_by_date_range():
    """Nhân viên kỹ thuật xem lịch hẹn được phân công của mình."""
    try:
        staff = g.current_user

        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = date.today()

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)
        else:
            end_date = start_date + timedelta(days=1)

        query = LichHen.query.filter(
            LichHen.manv == staff.manv,
            LichHen.ngaygio >= start_date,
            LichHen.ngaygio < end_date,
        )

        appointments = (
            query.options(
                joinedload(LichHen.khachhang),
                joinedload(LichHen.chitiet).joinedload(ChiTietLichHen.dichvu),
            )
            .order_by(LichHen.ngaygio)
            .all()
        )

        result = []
        for apt in appointments:
            dichvu_ten = "N/A"
            dichvu_count = len(apt.chitiet)
            if dichvu_count > 0 and apt.chitiet[0].dichvu:
                dichvu_ten = apt.chitiet[0].dichvu.tendv
                if dichvu_count > 1:
                    dichvu_ten += f" (+{dichvu_count - 1})"

            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "khachhang_hoten": apt.khachhang.hoten if apt.khachhang else "Khách vãng lai",
                "dichvu_ten": dichvu_ten,
                "nhanvien_hoten": staff.hoten,
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
                "ghichu": apt.ghichu if apt.ghichu else "",
            })

        return jsonify({"success": True, "appointments": result}), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy lịch của tôi: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>", methods=["GET"])
@roles_required("admin", "manager", "letan", "staff")
def get_appointment_detail(malh):
    """Xem thông tin chi tiết một lịch hẹn."""
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404

        staff = g.current_user
        if staff.role == "staff" and apt.manv != staff.manv:
            return jsonify({"msg": "Bạn không có quyền xem lịch hẹn này"}), 403

        services = []
        for detail in apt.chitiet:
            if detail.dichvu:
                services.append({
                    "madv": detail.madv,
                    "tendv": detail.dichvu.tendv,
                    "gia": str(detail.dichvu.gia),
                    "thoiluong": detail.dichvu.thoiluong,
                })

        result = {
            "malh": apt.malh,
            "ngaygio": apt.ngaygio.isoformat(),
            "khachhang": {
                "makh": apt.khachhang.makh,
                "hoten": apt.khachhang.hoten,
                "sdt": apt.khachhang.sdt,
                "email": apt.khachhang.email,
            } if apt.khachhang else None,
            "nhanvien": {
                "manv": apt.nhanvien.manv,
                "hoten": apt.nhanvien.hoten,
            } if apt.nhanvien else None,
            "services": services,
            "trangthai": apt.trangthai,
            "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
            "ghichu": apt.ghichu or "",
        }

        return jsonify({"success": True, "appointment": result}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy chi tiết lịch hẹn: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>", methods=["PUT"])
@roles_required("admin", "manager", "letan", "staff")
def update_appointment(malh):
    """Cập nhật ngày giờ, nhân viên hoặc trạng thái lịch hẹn."""
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404

        staff = g.current_user
        if staff.role == "staff" and apt.manv != staff.manv:
            return jsonify({"msg": "Bạn không có quyền sửa lịch hẹn này"}), 403

        data = request.get_json() or {}

        # Nếu thay đổi trạng thái
        if "trangthai" in data:
            appointment_service.update_appointment_status(
                appointment_id=malh,
                new_status=data["trangthai"],
                user_id=staff.manv,
                role=staff.role,
            )

        # Nếu thay đổi ngày giờ hoặc nhân viên
        new_ngaygio = apt.ngaygio
        new_manv = apt.manv

        if "ngaygio" in data:
            new_ngaygio = datetime.strptime(data["ngaygio"], "%Y-%m-%dT%H:%M")
        if "manv" in data:
            new_manv = data["manv"]
        if "ghichu" in data:
            apt.ghichu = data["ghichu"]

        if "ngaygio" in data or "manv" in data:
            duration = appointment_service.calculate_total_duration([d.madv for d in apt.chitiet])
            if new_manv:
                is_avail, conflicts, reason = appointment_service.check_staff_availability(
                    new_manv, new_ngaygio, duration, exclude_malh=apt.malh
                )
                if not is_avail:
                    return jsonify({
                        "success": False,
                        "msg": f"Không thể cập nhật: {reason}",
                        "conflicts": conflicts
                    }), 409

            apt.ngaygio = new_ngaygio
            apt.manv = new_manv

        db.session.commit()
        return jsonify({"success": True, "msg": "Cập nhật lịch hẹn thành công"}), 200

    except AppointmentValidationError as e:
        return jsonify({"msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"msg": e.message}), e.status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi cập nhật lịch hẹn: {e}", exc_info=True)
        return jsonify({"msg": "Cập nhật thất bại"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>/confirm", methods=["POST"])
@roles_required("admin", "manager", "letan", "staff")
def confirm_appointment(malh):
    """Xác nhận lịch hẹn."""
    staff = g.current_user
    try:
        res = appointment_service.update_appointment_status(
            appointment_id=malh,
            new_status="confirmed",
            user_id=staff.manv,
            role=staff.role,
        )
        return jsonify({"success": True, "msg": "Xác nhận lịch hẹn thành công", "appointment": res}), 200
    except AppointmentValidationError as e:
        return jsonify({"msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi xác nhận lịch hẹn: {e}", exc_info=True)
        return jsonify({"msg": "Xác nhận thất bại"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>/cancel", methods=["POST"])
@roles_required("admin", "manager", "letan")
def cancel_appointment(malh):
    """Admin / Lễ tân hủy lịch hẹn."""
    staff = g.current_user
    data = request.get_json(silent=True) or {}
    cancel_reason = data.get("reason", "")
    try:
        res = appointment_service.cancel_appointment(
            appointment_id=malh,
            user_id=staff.manv,
            role=staff.role,
            reason=cancel_reason,
        )
        return jsonify({"success": True, "msg": "Hủy lịch hẹn thành công", "appointment": res}), 200
    except AppointmentValidationError as e:
        return jsonify({"msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi hủy lịch hẹn: {e}", exc_info=True)
        return jsonify({"msg": "Hủy thất bại"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>/cancel-customer", methods=["PUT"])
def cancel_my_appointment(malh):
    """Khách hàng hủy lịch của mình qua session admin/customer router."""
    customer = g.get("current_user")
    if not customer or not hasattr(customer, "makh"):
        return jsonify({"msg": "Vui lòng đăng nhập"}), 401

    try:
        res = appointment_service.cancel_appointment(
            appointment_id=malh,
            user_id=customer.makh,
            role="customer",
        )
        return jsonify({"success": True, "msg": "Hủy lịch hẹn thành công", "appointment": res}), 200
    except AppointmentPermissionError as e:
        return jsonify({"msg": e.message}), 403
    except AppointmentValidationError as e:
        return jsonify({"msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi hủy lịch hẹn customer: {e}", exc_info=True)
        return jsonify({"msg": "Hủy lịch hẹn thất bại"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>/complete", methods=["POST"])
@roles_required("admin", "manager", "letan", "staff")
def complete_appointment(malh):
    """Hoàn thành lịch hẹn (gửi email cảm ơn tự động)."""
    staff = g.current_user
    try:
        res = appointment_service.update_appointment_status(
            appointment_id=malh,
            new_status="completed",
            user_id=staff.manv,
            role=staff.role,
        )
        return jsonify({"success": True, "msg": "Hoàn thành lịch hẹn", "appointment": res}), 200
    except AppointmentValidationError as e:
        return jsonify({"msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi hoàn thành lịch hẹn: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>/assign", methods=["POST"])
@roles_required("admin", "manager", "letan")
def assign_staff_to_appointment(malh):
    """Gán nhân viên kỹ thuật cho lịch hẹn."""
    data = request.get_json() or {}
    manv = data.get("manv")
    if not manv:
        return jsonify({"msg": "Thiếu mã nhân viên (manv)"}), 400

    try:
        res = appointment_service.assign_staff_to_appointment(malh, int(manv))
        return jsonify({"success": True, "msg": res["message"], "data": res}), 200
    except AppointmentConflictError as e:
        return jsonify({"success": False, "msg": e.message, "conflicts": e.conflicts}), 409
    except AppointmentValidationError as e:
        return jsonify({"msg": e.message}), 400
    except AppointmentServiceError as e:
        return jsonify({"msg": e.message}), e.status_code
    except Exception as e:
        current_app.logger.error(f"Lỗi gán nhân viên: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống"}), 500


# =========================================================================
# STATISTICS API
# =========================================================================

@appointment_manage_bp.route("/appointments/statistics", methods=["GET"])
@roles_required("admin", "manager", "letan", "staff")
def get_appointment_statistics():
    """Thống kê lịch hẹn theo các trạng thái chuẩn."""
    try:
        staff = g.current_user

        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")

        if staff.role == "staff":
            query = LichHen.query.filter(LichHen.manv == staff.manv)
        else:
            query = LichHen.query

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(LichHen.ngaygio >= start_date)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)
            query = query.filter(LichHen.ngaygio < end_date)

        total = query.count()
        pending = query.filter(LichHen.trangthai == AppointmentStatus.PENDING).count()
        confirmed = query.filter(LichHen.trangthai == AppointmentStatus.CONFIRMED).count()
        in_progress = query.filter(LichHen.trangthai == AppointmentStatus.IN_PROGRESS).count()
        completed = query.filter(LichHen.trangthai == AppointmentStatus.COMPLETED).count()
        cancelled = query.filter(LichHen.trangthai == AppointmentStatus.CANCELLED).count()

        return jsonify({
            "success": True,
            "statistics": {
                "total": total,
                "pending": pending,
                "confirmed": confirmed,
                "in_progress": in_progress,
                "completed": completed,
                "cancelled": cancelled,
            },
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê lịch hẹn: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500
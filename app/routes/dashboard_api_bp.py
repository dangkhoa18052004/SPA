from flask import Blueprint, jsonify, current_app, g
from ..extensions import db
from ..models import LichHen, HoaDon, NhanVien, KhachHang, CaLam, nhanvien_calam, AppointmentStatus
from ..decorators import roles_required
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, extract
from ..services import analytics_service

dashboard_api_bp = Blueprint("dashboard_api", __name__)


@dashboard_api_bp.route("/stats", methods=["GET"])
@roles_required("admin", "manager")
def get_dashboard_stats():
    """Lấy thống kê tổng quan KPI cho Admin/Manager."""
    try:
        today = date.today()
        kpis = analytics_service.get_kpi_cards(today)

        # 4. Thống kê tuần này
        week_start = today - timedelta(days=today.weekday())
        week_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) >= week_start,
            func.date(LichHen.ngaygio) <= today,
        ).count()

        # 7. Lịch hẹn sắp tới (24h tiếp theo)
        upcoming_appointments = LichHen.query.filter(
            and_(
                LichHen.ngaygio >= datetime.now(),
                LichHen.ngaygio <= datetime.now() + timedelta(hours=24),
                LichHen.trangthai.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            )
        ).count()

        # 8. Thống kê theo tháng
        month_start = today.replace(day=1)
        month_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) >= month_start,
            func.date(LichHen.ngaygio) <= today,
        ).count()

        return jsonify({
            "success": True,
            "stats": {
                "today": {
                    "total_appointments": kpis["today"]["total_appointments"],
                    "appointments_by_status": kpis["today"]["appointments_by_status"],
                    "revenue": kpis["today"]["revenue"],
                    "service_revenue": kpis["today"]["service_revenue"],
                    "package_revenue": kpis["today"]["package_revenue"],
                    "working_staff": kpis["today"]["working_staff"],
                    "upcoming_appointments": upcoming_appointments,
                },
                "week": {
                    "appointments": week_appointments,
                },
                "month": {
                    "appointments": month_appointments,
                    "revenue": kpis["month"]["revenue"],
                    "service_revenue": kpis["month"]["service_revenue"],
                    "package_revenue": kpis["month"]["package_revenue"],
                    "average_invoice": kpis["month"]["average_invoice"],
                    "new_customers": kpis["month"]["new_customers"],
                },
                "general": {
                    "total_customers": kpis["general"]["total_customers"],
                    "active_staff": kpis["general"]["active_staff"],
                },
            },
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê dashboard: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/appointments/today", methods=["GET"])
@roles_required("admin", "manager", "letan")
def get_today_appointments():
    """Lấy danh sách lịch hẹn hôm nay."""
    try:
        today = date.today()

        appointments = (
            LichHen.query.filter(func.date(LichHen.ngaygio) == today)
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
                "nhanvien_hoten": apt.nhanvien.hoten if apt.nhanvien else "Chưa gán",
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
            })

        return jsonify({"success": True, "appointments": result}), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy lịch hẹn hôm nay: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/appointments/my-schedule-today", methods=["GET"])
@roles_required("staff", "letan")
def get_my_schedule_today():
    """Lấy lịch làm việc của nhân viên hôm nay."""
    try:
        staff = g.current_user
        today = date.today()

        appointments = (
            LichHen.query.filter(
                LichHen.manv == staff.manv,
                func.date(LichHen.ngaygio) == today,
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
                "trangthai": apt.trangthai,
                "trangthai_vi": AppointmentStatus.to_vietnamese(apt.trangthai),
            })

        return jsonify({"success": True, "appointments": result}), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy lịch cá nhân hôm nay: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/letan-stats", methods=["GET"])
@roles_required("letan")
def get_letan_stats():
    """Thống kê đơn giản cho lễ tân."""
    try:
        today = date.today()

        today_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) == today
        ).count()

        pending_appointments = LichHen.query.filter(
            LichHen.trangthai == AppointmentStatus.PENDING
        ).count()

        month_start = datetime.combine(today.replace(day=1), datetime.min.time())
        new_customers = KhachHang.query.filter(
            KhachHang.ngaytao >= month_start
        ).count()

        return jsonify({
            "success": True,
            "stats": {
                "today_appointments": today_appointments,
                "pending_appointments": pending_appointments,
                "new_customers": new_customers,
            },
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê lễ tân: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/staff-stats", methods=["GET"])
@roles_required("staff")
def get_staff_stats():
    """Thống kê cho nhân viên."""
    try:
        staff = g.current_user
        today = date.today()

        today_schedule = LichHen.query.filter(
            LichHen.manv == staff.manv,
            func.date(LichHen.ngaygio) == today,
        ).count()

        week_start = today - timedelta(days=today.weekday())
        week_schedule = LichHen.query.filter(
            LichHen.manv == staff.manv,
            func.date(LichHen.ngaygio) >= week_start,
            func.date(LichHen.ngaygio) <= today,
        ).count()

        month_shifts = (
            db.session.query(func.count(nhanvien_calam.c.maca))
            .filter(nhanvien_calam.c.manv == staff.manv)
            .join(CaLam, nhanvien_calam.c.maca == CaLam.maca)
            .filter(
                extract("month", CaLam.ngay) == today.month,
                extract("year", CaLam.ngay) == today.year,
            )
            .scalar()
            or 0
        )

        return jsonify({
            "success": True,
            "stats": {
                "today_schedule": today_schedule,
                "week_schedule": week_schedule,
                "month_shifts": month_shifts,
            },
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê nhân viên: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500
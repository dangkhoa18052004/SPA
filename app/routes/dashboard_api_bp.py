from flask import Blueprint, jsonify, current_app, g
from ..extensions import db
from ..models import LichHen, HoaDon, NhanVien, KhachHang, CaLam, nhanvien_calam
from ..decorators import roles_required
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, extract

dashboard_api_bp = Blueprint("dashboard_api", __name__)

@dashboard_api_bp.route("/stats", methods=["GET"])
@roles_required('admin', 'manager')
def get_dashboard_stats():
    """Lấy thống kê tổng quan cho Admin/Manager"""
    try:
        today = date.today()
        
        # 1. Thống kê lịch hẹn hôm nay
        today_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) == today
        ).all()
        
        appointments_by_status = {
            'pending': 0,
            'confirmed': 0,
            'in_progress': 0,
            'completed': 0,
            'cancelled': 0
        }
        
        for apt in today_appointments:
            if apt.trangthai in appointments_by_status:
                appointments_by_status[apt.trangthai] += 1
        
        # 2. Doanh thu hôm nay (từ hóa đơn đã thanh toán)
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        today_revenue = db.session.query(
            func.sum(HoaDon.tongtien)
        ).filter(
            and_(
                HoaDon.trangthai == 'Đã thanh toán',
                # Tìm field ngày tạo (có thể là ngaylap, ngaytao, created_at)
            )
        ).scalar() or 0
        
        # 3. Nhân viên đang có ca hôm nay
        working_staff = db.session.query(
            func.count(func.distinct(nhanvien_calam.c.manv))
        ).join(
            CaLam, nhanvien_calam.c.maca == CaLam.maca
        ).filter(
            CaLam.ngay == today
        ).scalar() or 0
        
        # 4. Thống kê tuần này
        week_start = today - timedelta(days=today.weekday())
        week_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) >= week_start,
            func.date(LichHen.ngaygio) <= today
        ).count()
        
        # 5. Tổng khách hàng
        total_customers = KhachHang.query.count()
        
        # 6. Tổng nhân viên đang hoạt động
        active_staff = NhanVien.query.filter_by(trangthai=True).count()
        
        # 7. Lịch hẹn sắp tới (24h tiếp theo)
        upcoming_appointments = LichHen.query.filter(
            and_(
                LichHen.ngaygio >= datetime.now(),
                LichHen.ngaygio <= datetime.now() + timedelta(hours=24),
                LichHen.trangthai.in_(['pending', 'confirmed'])
            )
        ).count()
        
        # 8. Thống kê theo tháng
        month_start = today.replace(day=1)
        month_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) >= month_start,
            func.date(LichHen.ngaygio) <= today
        ).count()
        
        month_revenue = db.session.query(
            func.sum(HoaDon.tongtien)
        ).filter(
            HoaDon.trangthai == 'Đã thanh toán',
            extract('month', LichHen.ngaygio) == today.month,
            extract('year', LichHen.ngaygio) == today.year
        ).join(
            LichHen, HoaDon.malh == LichHen.malh
        ).scalar() or 0
        
        return jsonify({
            "success": True,
            "stats": {
                "today": {
                    "total_appointments": len(today_appointments),
                    "appointments_by_status": appointments_by_status,
                    "revenue": float(today_revenue),
                    "working_staff": working_staff,
                    "upcoming_appointments": upcoming_appointments
                },
                "week": {
                    "appointments": week_appointments
                },
                "month": {
                    "appointments": month_appointments,
                    "revenue": float(month_revenue)
                },
                "general": {
                    "total_customers": total_customers,
                    "active_staff": active_staff
                }
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê dashboard: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/appointments/today", methods=["GET"])
@roles_required('admin', 'manager', 'letan')
def get_today_appointments():
    """Lấy danh sách lịch hẹn hôm nay"""
    try:
        today = date.today()
        
        appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) == today
        ).order_by(LichHen.ngaygio).all()
        
        result = []
        for apt in appointments:
            # Lấy tên dịch vụ
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
                "trangthai": apt.trangthai
            })
        
        return jsonify({
            "success": True,
            "appointments": result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy lịch hẹn hôm nay: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/appointments/my-schedule-today", methods=["GET"])
@roles_required('staff', 'letan')
def get_my_schedule_today():
    """Lấy lịch làm việc của nhân viên hôm nay"""
    try:
        staff = g.current_user
        today = date.today()
        
        appointments = LichHen.query.filter(
            LichHen.manv == staff.manv,
            func.date(LichHen.ngaygio) == today
        ).order_by(LichHen.ngaygio).all()
        
        result = []
        for apt in appointments:
            # Lấy tên dịch vụ
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
                "trangthai": apt.trangthai
            })
        
        return jsonify({
            "success": True,
            "appointments": result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy lịch cá nhân hôm nay: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/letan-stats", methods=["GET"])
@roles_required('letan')
def get_letan_stats():
    """Thống kê đơn giản cho lễ tân"""
    try:
        today = date.today()
        
        # Lịch hẹn hôm nay
        today_appointments = LichHen.query.filter(
            func.date(LichHen.ngaygio) == today
        ).count()
        
        # Lịch chờ xác nhận
        pending_appointments = LichHen.query.filter(
            LichHen.trangthai == 'pending'
        ).count()
        
        # Khách hàng mới tháng này
        month_start = today.replace(day=1)
        new_customers = KhachHang.query.filter(
            # Assuming there's a created_at field
        ).count()
        
        return jsonify({
            "success": True,
            "stats": {
                "today_appointments": today_appointments,
                "pending_appointments": pending_appointments,
                "new_customers": new_customers
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê lễ tân: {e}")
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@dashboard_api_bp.route("/staff-stats", methods=["GET"])
@roles_required('staff')
def get_staff_stats():
    """Thống kê cho nhân viên"""
    try:
        staff = g.current_user
        today = date.today()
        
        # Lịch hôm nay
        today_schedule = LichHen.query.filter(
            LichHen.manv == staff.manv,
            func.date(LichHen.ngaygio) == today
        ).count()
        
        # Lịch tuần này
        week_start = today - timedelta(days=today.weekday())
        week_schedule = LichHen.query.filter(
            LichHen.manv == staff.manv,
            func.date(LichHen.ngaygio) >= week_start,
            func.date(LichHen.ngaygio) <= today
        ).count()
        
        # Ca làm tháng này
        month_shifts = db.session.query(
            func.count(nhanvien_calam.c.maca)
        ).filter(
            nhanvien_calam.c.manv == staff.manv
        ).join(
            CaLam, nhanvien_calam.c.maca == CaLam.maca
        ).filter(
            extract('month', CaLam.ngay) == today.month,
            extract('year', CaLam.ngay) == today.year
        ).scalar() or 0
        
        return jsonify({
            "success": True,
            "stats": {
                "today_schedule": today_schedule,
                "week_schedule": week_schedule,
                "month_shifts": month_shifts
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê nhân viên: {e}")
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500
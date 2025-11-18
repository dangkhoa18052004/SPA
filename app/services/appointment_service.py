# app/services/appointment_service.py
from flask import current_app
from ..extensions import db
from ..models import NhanVien, LichHen, ChiTietLichHen, CaLam, nhanvien_calam
from sqlalchemy import func, case, outerjoin
from datetime import datetime

def get_available_staff_by_date(booking_date):
    """
    Lấy danh sách nhân viên Kỹ thuật viên (role='staff') làm việc trong ngày, 
    sắp xếp theo số lịch hẹn ít nhất.
    """
    try:
        # 1. Subquery để đếm số lịch hẹn của mỗi NV trong ngày đó
        appointment_counts_sub = db.session.query(
            ChiTietLichHen.manv,
            func.count(LichHen.malh).label('appointment_count')
        ).join(LichHen).filter(
            db.func.date(LichHen.ngaygio) == booking_date,
            LichHen.trangthai.in_(['Đã xác nhận', 'Chờ xác nhận'])
        ).group_by(ChiTietLichHen.manv).subquery()

        # 2. Query chính: Lấy NV làm việc VÀ LỌC THEO VAI TRÒ
        working_staff_with_counts = db.session.query(
            NhanVien,
            func.coalesce(appointment_counts_sub.c.appointment_count, 0).label('total_appointments')
        ).join(nhanvien_calam).join(CaLam).filter(
            CaLam.ngay == booking_date,
            NhanVien.trangthai == True,
            NhanVien.role == 'staff' 
        ).outerjoin(
            appointment_counts_sub, NhanVien.manv == appointment_counts_sub.c.manv
        ).order_by(
            'total_appointments' # Sắp xếp theo NV ít việc nhất
        ).all()

        # 3. Trả về kết quả
        available_staff = [
            {"manv": staff.manv, "hoten": staff.hoten, "appointment_count": count}
            for staff, count in working_staff_with_counts
        ]
        
        return available_staff
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy NV khả dụng: {e}", exc_info=True)
        raise e

def auto_assign_staff(booking_date):
    """
    Tìm và trả về 1 nhân viên Kỹ thuật viên (role='staff') rảnh nhất.
    """
    try:
        appointment_counts_sub = db.session.query(
            ChiTietLichHen.manv,
            func.count(LichHen.malh).label('appointment_count')
        ).join(LichHen).filter(
            db.func.date(LichHen.ngaygio) == booking_date,
            LichHen.trangthai.in_(['Đã xác nhận', 'Chờ xác nhận'])
        ).group_by(ChiTietLichHen.manv).subquery()
        
        least_busy_staff_tuple = db.session.query(
            NhanVien,
            func.coalesce(appointment_counts_sub.c.appointment_count, 0).label('total_appointments')
        ).join(nhanvien_calam).join(CaLam).filter(
            CaLam.ngay == booking_date,
            NhanVien.trangthai == True,
            NhanVien.role == 'staff'
        ).outerjoin(
            appointment_counts_sub, NhanVien.manv == appointment_counts_sub.c.manv
        ).order_by(
            'total_appointments'
        ).first() # Chỉ lấy NV ít bận nhất

        if not least_busy_staff_tuple:
            return None 
        
        return least_busy_staff_tuple[0] 
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi tự động xếp lịch NV: {e}", exc_info=True)
        raise e
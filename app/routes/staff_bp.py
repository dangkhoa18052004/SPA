from flask import Blueprint, jsonify, current_app
from ..models import NhanVien
from ..extensions import db

staff_bp = Blueprint("staff", __name__)

@staff_bp.route("/staff", methods=["GET"])
def get_all_staff():
    """
    Lấy danh sách tất cả kỹ thuật viên (public API - không cần đăng nhập).
    Chỉ lấy KTV đang hoạt động (role='staff', trangthai=True) cho form đặt lịch hẹn.
    Không trả về email, sdt, diachi hay thông tin nhạy cảm.
    """
    try:
        staff_list = NhanVien.query.filter(
            NhanVien.role == 'staff',
            NhanVien.trangthai == True
        ).order_by(NhanVien.manv.asc()).all()
        
        result = []
        for staff in staff_list:
            position = staff.chucvu.tencv if staff.chucvu else "Kỹ thuật viên"
            result.append({
                "manv": staff.manv,
                "hoten": staff.hoten,
                "chuyenmon": position,
                "chucvu": position,
                "anhdaidien": staff.anhnhanvien if hasattr(staff, 'anhnhanvien') else None,
            })
        
        return jsonify({
            "success": True,
            "staff": result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error loading staff list: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": "Không thể tải danh sách nhân viên"
        }), 500


@staff_bp.route("/staff/<int:manv>", methods=["GET"])
def get_staff_detail(manv):
    """
    Lấy thông tin chi tiết 1 kỹ thuật viên (role='staff', trangthai=True).
    Không trả về email, sdt, diachi hay thông tin nhạy cảm.
    """
    try:
        staff = NhanVien.query.filter(
            NhanVien.manv == manv,
            NhanVien.role == 'staff',
            NhanVien.trangthai == True
        ).first()
        
        if not staff:
            return jsonify({
                "success": False,
                "message": "Không tìm thấy nhân viên"
            }), 404
        
        position = staff.chucvu.tencv if staff.chucvu else "Kỹ thuật viên"
        result = {
            "manv": staff.manv,
            "hoten": staff.hoten,
            "chuyenmon": position,
            "chucvu": position,
            "anhdaidien": staff.anhnhanvien if hasattr(staff, 'anhnhanvien') else None,
        }
        
        return jsonify({
            "success": True,
            "staff": result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error loading staff detail: {e}")
        return jsonify({
            "success": False,
            "message": "Lỗi hệ thống"
        }), 500

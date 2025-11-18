from flask import Blueprint, jsonify, current_app
from ..models import NhanVien
from ..extensions import db

staff_bp = Blueprint("staff", __name__)

@staff_bp.route("/staff", methods=["GET"])
def get_all_staff():
    """
    Lấy danh sách tất cả nhân viên (public API - không cần đăng nhập)
    Dùng cho form đặt lịch hẹn
    """
    try:
        # Lấy tất cả nhân viên đang active
        staff_list = NhanVien.query.filter(
            NhanVien.role.in_(['staff', 'letan'])  # Chỉ lấy nhân viên và lễ tân
        ).all()
        
        result = []
        for staff in staff_list:
            result.append({
                "manv": staff.manv,
                "hoten": staff.hoten,
                "email": staff.email,
                "sdt": staff.sdt,
                "chuyenmon": staff.chuyenmon if hasattr(staff, 'chuyenmon') else None,
                "anhdaidien": staff.anhnhanvien if hasattr(staff, 'anhnhanvien') else None,
                "role": staff.role
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
    Lấy thông tin chi tiết 1 nhân viên
    """
    try:
        staff = NhanVien.query.get(manv)
        
        if not staff:
            return jsonify({
                "success": False,
                "message": "Không tìm thấy nhân viên"
            }), 404
        
        result = {
            "manv": staff.manv,
            "hoten": staff.hoten,
            "email": staff.email,
            "sdt": staff.sdt,
            "diachi": staff.diachi,
            "chuyenmon": staff.chuyenmon if hasattr(staff, 'chuyenmon') else None,
            "anhdaidien": staff.anhnhanvien if hasattr(staff, 'anhnhanvien') else None,
            "role": staff.role,
            "chucvu": staff.chucvu.tencv if staff.chucvu else None
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
# app/routes/profile_bp.py
import datetime
from flask import Blueprint, request, jsonify, current_app, g, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import CaLam, Luong, nhanvien_calam, NhanVien, KhachHang
from ..decorators import login_required, roles_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from datetime import datetime

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

def get_current_user_from_jwt():
    """Helper function to get current user from JWT token"""
    identity = get_jwt_identity()
    
    if identity.startswith("customer:"):
        user_id = int(identity.split(":")[1])
        user = KhachHang.query.get(user_id)
        return user, 'customer'
    elif identity.startswith("staff:"):
        user_id = int(identity.split(":")[1])
        user = NhanVien.query.get(user_id)
        return user, 'staff'
    
    return None, None

@profile_bp.route("", methods=["GET"])
@jwt_required()
def get_my_profile():
    user, user_type = get_current_user_from_jwt()
    
    if not user:
        return jsonify({"success": False, "message": "Người dùng không tồn tại"}), 404

    if user_type == 'customer':
        return jsonify({
            "success": True,
            "user": {
                "makh": user.makh,
                "hoten": user.hoten,
                "sdt": user.sdt,
                "diachi": user.diachi,
                "email": user.email,
                "taikhoan": user.taikhoan,
                "anhdaidien": user.anhdaidien
            }
        }), 200
    
    elif user_type == 'staff':
        return jsonify({
            "success": True,
            "user": {
                "manv": user.manv,
                "hoten": user.hoten,
                "sdt": user.sdt,
                "diachi": user.diachi,
                "email": user.email,
                "taikhoan": user.taikhoan,
                "anhnhanvien": user.anhnhanvien,
                "role": user.role,
                "chucvu": user.chucvu.tencv if user.chucvu else None
            }
        }), 200

@profile_bp.route("/update", methods=["PUT"])
@jwt_required()
def update_my_profile():
    user, user_type = get_current_user_from_jwt()
    data = request.get_json() or {}

    try:
        user.hoten = data.get("hoten", user.hoten)
        user.sdt = data.get("sdt", user.sdt)
        user.diachi = data.get("diachi", user.diachi)
        user.email = data.get("email", user.email)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Cập nhật thông tin thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi cập nhật profile {user_type} {user.taikhoan}: {e}")
        return jsonify({"success": False, "message": "Cập nhật thất bại, có thể email/sđt đã tồn tại"}), 500

@profile_bp.route("/upload-avatar", methods=["POST"])
@jwt_required()
def upload_avatar():
    user, user_type = get_current_user_from_jwt()
    
    if "file" not in request.files:
        return jsonify({"success": False, "message": "Không tìm thấy file ảnh"}), 400
        
    file = request.files["file"]
    if file.filename == '':
        return jsonify({"success": False, "message": "Không chọn file nào"}), 400

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        current_app.logger.error("UPLOAD_FOLDER không được cấu hình!")
        return jsonify({"success": False, "message": "Lỗi cấu hình máy chủ"}), 500
    
    os.makedirs(upload_folder, exist_ok=True)

    if file:
        filename = secure_filename(f"{user_type}_{user.taikhoan}_{file.filename}")
        path = os.path.join(upload_folder, filename)
        
        try:
            file.save(path)
            if user_type == 'customer':
                user.anhdaidien = filename
            elif user_type == 'staff':
                user.anhnhanvien = filename
            db.session.commit()
            return jsonify({"success": True, "message": "Upload ảnh thành công", "filename": filename}), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Lỗi lưu file avatar: {e}")
            return jsonify({"success": False, "message": "Lưu file thất bại"}), 500

@profile_bp.route("/avatar/<path:filename>", methods=["GET"])
def get_avatar(filename):
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    return send_from_directory(upload_folder, filename)

@profile_bp.route("/change-password", methods=["PUT"])
@jwt_required()
def change_password():
    user, user_type = get_current_user_from_jwt()
    data = request.get_json()
    
    current_password = data.get("matkhau_cu")
    new_password = data.get("matkhau_moi")
    
    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Vui lòng cung cấp mật khẩu cũ và mật khẩu mới"}), 400
    
    if not check_password_hash(user.matkhau, current_password):
        return jsonify({"success": False, "message": "Mật khẩu hiện tại không chính xác"}), 401
    
    try:
        user.matkhau = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({"success": True, "message": "Đổi mật khẩu thành công!"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi đổi mật khẩu: {e}")
        return jsonify({"success": False, "message": "Đổi mật khẩu thất bại"}), 500

@profile_bp.route("/my-salary", methods=["GET"])
@jwt_required()
@roles_required('staff', 'letan', 'manager', 'admin')
def get_my_salary_history():
    staff = g.current_user
    try:
        salaries = Luong.query.filter_by(manv=staff.manv).order_by(Luong.nam.desc(), Luong.thang.desc()).all()
        result = [{"maluong": s.maluong, "thang": s.thang, "nam": s.nam, "luongcoban": str(s.luongcoban), "thuong": str(s.thuong), "khautru": str(s.khautru), "tongluong": str(s.tongluong)} for s in salaries]
        return jsonify({"success": True, "salaries": result}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy LS lương cá nhân: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500

@profile_bp.route("/my-schedule", methods=["GET"])
@jwt_required()
@roles_required('staff', 'letan', 'manager', 'admin')
def get_my_schedule():
    staff = g.current_user
    start_date_str, end_date_str = request.args.get("start_date"), request.args.get("end_date")
    if not start_date_str or not end_date_str:
        return jsonify({"success": False, "message": "Vui lòng cung cấp start_date và end_date"}), 400
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        my_shifts = db.session.query(CaLam).join(nhanvien_calam).filter(
            nhanvien_calam.c.manv == staff.manv,
            CaLam.ngay.between(start_date, end_date)
        ).order_by(CaLam.ngay, CaLam.giobatdau).all()
        
        schedule_data = {}
        for shift in my_shifts:
            date_str = shift.ngay.isoformat()
            if date_str not in schedule_data:
                schedule_data[date_str] = []
            
            schedule_data[date_str].append({
                "maca": shift.maca,
                "start_time": shift.giobatdau.strftime('%H:%M'),
                "end_time": shift.gioketthuc.strftime('%H:%M'),
            })
        return jsonify({"success": True, "schedule": schedule_data}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy lịch làm việc cá nhân: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500

@profile_bp.route("/my-schedule-with-colleagues", methods=["GET"])
@jwt_required()
@roles_required('staff', 'letan', 'manager', 'admin')
def get_my_schedule_with_colleagues():
    staff = g.current_user
    start_date_str, end_date_str = request.args.get("start_date"), request.args.get("end_date")
    if not start_date_str or not end_date_str:
        return jsonify({"success": False, "message": "Vui lòng cung cấp start_date và end_date"}), 400
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        my_shifts = db.session.query(CaLam).join(nhanvien_calam).filter(
            nhanvien_calam.c.manv == staff.manv,
            CaLam.ngay.between(start_date, end_date)
        ).order_by(CaLam.ngay, CaLam.giobatdau).all()
        
        schedule_data = {}
        for shift in my_shifts:
            date_str = shift.ngay.isoformat()
            if date_str not in schedule_data:
                schedule_data[date_str] = []
            
            colleagues = [{"manv": c.manv, "hoten": c.hoten} for c in shift.nhanvien if c.manv != staff.manv]
            schedule_data[date_str].append({
                "maca": shift.maca,
                "start_time": shift.giobatdau.strftime('%H:%M'),
                "end_time": shift.gioketthuc.strftime('%H:%M'),
                "colleagues": colleagues
            })
        return jsonify({"success": True, "schedule": schedule_data}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy lịch làm việc (chi tiết): {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500
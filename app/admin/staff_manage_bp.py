import os
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import KhachHang, NhanVien, ChucVu
from ..decorators import roles_required
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

staff_manage_bp = Blueprint("staff_manage", __name__)

def save_staff_avatar(file):
    if not file:
        return None
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        current_app.logger.error("UPLOAD_FOLDER chưa được cấu hình trong Config.")
        return None
        
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_folder, f"staff_{filename}")
    
    file.save(file_path)
    return f"staff_{filename}"

@staff_manage_bp.route("/staff/add", methods=["POST"])
@roles_required('admin')
def add_staff():
    # SỬA: Đổi từ get_json() sang request.form và request.files
    data = request.form
    taikhoan, matkhau, hoten, macv, role = data.get("taikhoan"), data.get("matkhau"), data.get("hoten"), data.get("macv"), data.get("role")
    
    if not all([taikhoan, matkhau, hoten, macv, role]):
        return jsonify({"msg": "Thiếu thông tin bắt buộc"}), 400
        
    if NhanVien.query.filter_by(taikhoan=taikhoan).first(): 
        return jsonify({"msg": "Tài khoản đã tồn tại"}), 409
    
    allowed_roles = ['manager', 'staff', 'admin', 'letan']
    if role not in allowed_roles: 
        return jsonify({"msg": f"Vai trò không hợp lệ."}), 400
    
    avatar_file = request.files.get('anhnhanvien')
    avatar_filename = None
    if avatar_file:
        avatar_filename = save_staff_avatar(avatar_file)
    trangthai_str = data.get("trangthai", "true") 
    trangthai_bool = trangthai_str.lower() == 'true'
    try:
        new_staff = NhanVien(
            taikhoan=taikhoan, 
            matkhau=generate_password_hash(matkhau), 
            hoten=hoten, 
            macv=macv, 
            role=role, 
            trangthai=trangthai_bool,
            email=data.get("email") or None,
            sdt=data.get("sdt") or None,
            anhnhanvien=avatar_filename
        )
        db.session.add(new_staff)
        db.session.commit()
        return jsonify({"msg": "Đã tạo tài khoản thành công", "manv": new_staff.manv}), 201
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi tạo nhân viên: {e}"); return jsonify({"msg": "Tạo tài khoản thất bại"}), 500

@staff_manage_bp.route("/staff/<int:manv>", methods=["PUT"])
@roles_required('admin')
def update_staff(manv):
    staff = NhanVien.query.get(manv)
    if not staff: return jsonify({"msg": "Không tìm thấy nhân viên"}), 404
    
    data = request.form
    
    new_taikhoan = data.get("taikhoan")
    if new_taikhoan and new_taikhoan != staff.taikhoan:
        if NhanVien.query.filter(NhanVien.taikhoan == new_taikhoan, NhanVien.manv != manv).first():
            return jsonify({"msg": "Tên tài khoản mới đã tồn tại"}), 409
        staff.taikhoan = new_taikhoan
    try:
        staff.hoten = data.get("hoten", staff.hoten)
        staff.email = data.get("email", staff.email) or None
        staff.sdt = data.get("sdt", staff.sdt) or None
        staff.macv = data.get("macv", staff.macv)
        
        if "role" in data:
            new_role = data.get("role")
            allowed_roles = ['manager', 'staff', 'admin', 'letan']
            if new_role not in allowed_roles:
                return jsonify({"msg": f"Vai trò mới không hợp lệ."}), 400
            staff.role = new_role
            
        if "trangthai" in data:
            staff.trangthai = data.get("trangthai").lower() == 'true'

        avatar_file = request.files.get('anhnhanvien')
        if avatar_file:
            staff.anhnhanvien = save_staff_avatar(avatar_file)

        db.session.commit()
        return jsonify({"msg": "Cập nhật thông tin nhân viên thành công"}), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi cập nhật nhân viên: {e}"); return jsonify({"msg": "Cập nhật thất bại"}), 500

@staff_manage_bp.route("/staff/<int:manv>", methods=["DELETE"])
@roles_required('admin')
def deactivate_staff(manv):
    staff = NhanVien.query.get(manv)
    if not staff: return jsonify({"msg": "Không tìm thấy nhân viên"}), 404
    try:
        staff.trangthai = False
        db.session.commit()
        return jsonify({"msg": "Đã vô hiệu hóa tài khoản nhân viên thành công"}), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi vô hiệu hóa nhân viên: {e}"); return jsonify({"msg": "Vô hiệu hóa thất bại"}), 500

@staff_manage_bp.route("/staff/list-all", methods=["GET"])
@roles_required('admin', 'manager')
def get_all_staff():
    try:

        staff_list = db.session.query(NhanVien, ChucVu)\
            .outerjoin(ChucVu, NhanVien.macv == ChucVu.macv).all()
            
        result = [
            {"manv": nv.manv, "hoten": nv.hoten, "email": nv.email, "sdt": nv.sdt,
             "taikhoan": nv.taikhoan, "role": nv.role, "trangthai": nv.trangthai,
             "chucvu": cv.tencv if cv else "N/A",
             "anhnhanvien": nv.anhnhanvien
            } 
            for nv, cv in staff_list
        ]
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy DS nhân viên (admin): {e}")
        return jsonify({"msg": "Không thể lấy danh sách nhân viên"}), 500

@staff_manage_bp.route("/staff", methods=["GET"])
def get_staff_for_booking():
    """API public để khách hàng chọn nhân viên khi đặt lịch (ĐÃ SỬA: Chỉ lấy KTV)"""
    try:
        staff_list = db.session.query(NhanVien).join(
            ChucVu, NhanVien.macv == ChucVu.macv
        ).filter(
            NhanVien.trangthai == True,
            NhanVien.role == 'staff',
            ChucVu.tencv == 'Kỹ thuật viên' 
        ).order_by(NhanVien.hoten).all()
        
        result = []
        for staff in staff_list:
            result.append({
                'manv': staff.manv,
                'hoten': staff.hoten,
                'sdt': staff.sdt,
                'email': staff.email,
                'chuyenmon': staff.chucvu.tencv if staff.chucvu else 'Kỹ thuật viên',
                'anhdaidien': staff.anhnhanvien,
                'role': staff.role
            })
        
        return jsonify({
            'success': True,
            'staff': result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy danh sách nhân viên cho booking: {e}")
        return jsonify({
            'success': False,
            'msg': 'Lỗi hệ thống',
            'staff': []
        }), 500

@staff_manage_bp.route("/staff/list-public", methods=["GET"])
def get_public_staff_list():
    """API public cho khách xem (từ staff.py/get_list)."""
    try:
        staff_list = db.session.query(NhanVien, ChucVu).join(ChucVu, NhanVien.macv == ChucVu.macv).filter(NhanVien.trangthai.is_(True)).all()
        result = [{"manv": nv.manv, "hoten": nv.hoten, "chucvu": cv.tencv if cv else None, "anhnhanvien": nv.anhnhanvien} for nv, cv in staff_list]
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy danh sách nhân viên: {e}")
        return jsonify({"msg": "Không thể lấy danh sách nhân viên"}), 500
    

@staff_manage_bp.route("/customers/list", methods=["GET"])
@roles_required('admin', 'manager', 'letan','staff') 
def get_all_customers():
    """API: Lấy danh sách tất cả khách hàng."""
    try:
        customers = KhachHang.query.all()
        
        result = [
            {
                "makh": c.makh,
                "hoten": c.hoten,
                "sdt": c.sdt,
                "email": c.email,
                "trangthai": c.trangthai,
                "anhdaidien": c.anhdaidien
            } for c in customers
        ]
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy danh sách khách hàng: {e}")
        return jsonify({"msg": "Không thể lấy danh sách khách hàng"}), 500

@staff_manage_bp.route("/customers/add-quick", methods=["POST"])
@roles_required('letan', 'manager', 'admin') 
def quick_add_customer():

    data = request.get_json()
    hoten = data.get("hoten")
    sdt = data.get("sdt") 
    
    if not hoten or not sdt:
        return jsonify({"msg": "Cần họ tên và SĐT"}), 400
        
    existing_customer = KhachHang.query.filter_by(sdt=sdt).first()
    if existing_customer:

        return jsonify({
            "msg": "Khách hàng đã tồn tại.", 
            "makh": existing_customer.makh
        }), 200

    try:

        new_customer = KhachHang(
            hoten=hoten,
            sdt=sdt,
            email=data.get("email"), 
            taikhoan=sdt,
            matkhau=generate_password_hash(sdt), 
            trangthai='active'
        )
        db.session.add(new_customer)
        db.session.commit()
        
        return jsonify({
            "msg": "Tạo nhanh khách hàng thành công", 
            "makh": new_customer.makh
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi tạo nhanh khách hàng: {e}")
        return jsonify({"msg": "Lỗi hệ thống khi tạo khách"}), 500
    
@staff_manage_bp.route("/customers/detail/<int:makh>", methods=["GET"])
@roles_required('admin', 'manager', 'letan')
def get_customer_detail(makh):
    """API: Lấy thông tin chi tiết của 1 khách hàng."""
    try:
        customer = KhachHang.query.get(makh)
        if not customer:
            return jsonify({"msg": "Không tìm thấy khách hàng"}), 404
            
        result = {
            "makh": customer.makh,
            "hoten": customer.hoten,
            "sdt": customer.sdt,
            "email": customer.email,
            "diachi": customer.diachi, 
            "taikhoan": customer.taikhoan, 
            "trangthai": customer.trangthai
        }
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy chi tiết khách hàng {makh}: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@staff_manage_bp.route("/customers/add", methods=["POST"])
@roles_required('admin', 'manager') # Chỉ admin/manager được thêm
def add_customer():
    """API: Thêm một khách hàng mới (đầy đủ)."""
    data = request.get_json()
    hoten = data.get("hoten")
    sdt = data.get("sdt")
    taikhoan = data.get("taikhoan")
    matkhau = data.get("matkhau")
    
    email = data.get("email")
    if email == '':
        email = None

    if not all([hoten, sdt, taikhoan, matkhau]):
        return jsonify({"msg": "Thiếu thông tin bắt buộc (hoten, sdt, taikhoan, matkhau)"}), 400

    # Kiểm tra SĐT hoặc tài khoản
    query = KhachHang.query.filter(
        (KhachHang.sdt == sdt) | (KhachHang.taikhoan == taikhoan)
    )
    
    #CHỈ kiểm tra email nếu nó được cung cấp
    if email:
        if KhachHang.query.filter(KhachHang.email == email).first():
             return jsonify({"msg": "Email đã tồn tại"}), 409
        
    if query.first():
        return jsonify({"msg": "SĐT hoặc Tên tài khoản đã tồn tại"}), 409

    try:
        new_customer = KhachHang(
            hoten=hoten,
            sdt=sdt,
            email=email, # Gán giá trị đã được xử lý (None hoặc email thật)
            diachi=data.get("diachi"),
            taikhoan=taikhoan,
            matkhau=generate_password_hash(matkhau),
            trangthai=data.get("trangthai", "active")
        )
        db.session.add(new_customer)
        db.session.commit()
        
        return jsonify({
            "msg": "Thêm khách hàng thành công", 
            "makh": new_customer.makh
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi thêm khách hàng: {e}")
        return jsonify({"msg": "Lỗi hệ thống khi thêm khách"}), 500

@staff_manage_bp.route("/customers/edit/<int:makh>", methods=["PUT"])
@roles_required('admin', 'manager') # Chỉ admin/manager được sửa
def edit_customer(makh):
    """API: Cập nhật thông tin khách hàng."""
    customer = KhachHang.query.get(makh)
    if not customer:
        return jsonify({"msg": "Không tìm thấy khách hàng"}), 404

    data = request.get_json()
    
    # Kiểm tra SĐT, Email, Tài khoản 
    if data.get("sdt") and data.get("sdt") != customer.sdt and KhachHang.query.filter_by(sdt=data.get("sdt")).first():
        return jsonify({"msg": "SĐT đã tồn tại"}), 409
    if data.get("taikhoan") and data.get("taikhoan") != customer.taikhoan and KhachHang.query.filter_by(taikhoan=data.get("taikhoan")).first():
        return jsonify({"msg": "Tên tài khoản đã tồn tại"}), 409

    try:
        customer.hoten = data.get("hoten", customer.hoten)
        customer.sdt = data.get("sdt", customer.sdt)
        customer.email = data.get("email", customer.email)
        customer.diachi = data.get("diachi", customer.diachi)
        customer.taikhoan = data.get("taikhoan", customer.taikhoan)
        customer.trangthai = data.get("trangthai", customer.trangthai)
        
        # Chỉ cập nhật mật khẩu nếu có nhập
        if data.get("matkhau"):
            customer.matkhau = generate_password_hash(data.get("matkhau"))

        db.session.commit()
        return jsonify({"msg": "Cập nhật khách hàng thành công"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi sửa khách hàng {makh}: {e}")
        return jsonify({"msg": "Lỗi hệ thống khi cập nhật"}), 500

@staff_manage_bp.route("/customers/update-status/<int:makh>", methods=["PATCH"])
@roles_required('admin', 'manager')
def update_customer_status(makh):
    """API: Cập nhật trạng thái (khóa/mở khóa)."""
    customer = KhachHang.query.get(makh)
    if not customer:
        return jsonify({"msg": "Không tìm thấy khách hàng"}), 404
        
    data = request.get_json()
    new_status = data.get("trangthai")
    
    if new_status not in ['active', 'pending', 'blocked']:
        return jsonify({"msg": "Trạng thái không hợp lệ"}), 400

    try:
        customer.trangthai = new_status
        db.session.commit()
        action_text = "khóa" if new_status == 'blocked' else ("mở khóa" if new_status == 'active' else "cập nhật")
        return jsonify({"msg": f"Đã {action_text} khách hàng thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi cập nhật trạng thái KH {makh}: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500
    


from app.services.email_service import send_email
from requests import session
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import KhachHang, NhanVien
from ..utils import generate_code

from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import or_

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    """Lấy thông tin user hiện tại (ĐÃ SỬA LỖI 500)"""
    try:
        identity_str = get_jwt_identity() 
        
        if not identity_str:
            return jsonify({"msg": "Không tìm thấy identity trong token"}), 401

        user = None
        role = None
        name = None
        username = None

        try:
            user_type, user_id_str = identity_str.split(':')
            user_id = int(user_id_str)
        except (ValueError, TypeError):
             return jsonify({"msg": "Định dạng identity không hợp lệ"}), 401

        if user_type == 'staff':
            user = NhanVien.query.get(user_id)
            if user:
                role = user.role
                name = user.hoten
                username = user.taikhoan
        elif user_type == 'customer':
            user = KhachHang.query.get(user_id)
            if user:
                role = 'customer' 
                name = user.hoten
                username = user.taikhoan
        
        if not user:
            return jsonify({"msg": f"Không tìm thấy user {user_type} với ID {user_id}"}), 404
        
        # Trả về thông tin chính xác
        return jsonify({
            "role": role,
            "username": username,
            "name": name
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi nghiêm trọng trong get_profile: {e}")
        return jsonify({"msg": "Lỗi hệ thống khi lấy thông tin profile"}), 500

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    taikhoan = data.get("taikhoan")
    matkhau = data.get("matkhau")
    hoten = data.get("hoten")
    email = data.get("email")
    sdt = data.get("sdt")
    
    if not all([taikhoan, matkhau, hoten, email, sdt]): 
        return jsonify({"success": False, "message": "Thiếu trường bắt buộc"}), 400
    
    #  Ưu tiên kiểm tra SĐT
    existing_customer_sdt = KhachHang.query.filter_by(sdt=sdt).first()
    
    if existing_customer_sdt:
        
        if existing_customer_sdt.trangthai == 'active':
            return jsonify({
                "success": False, 
                "message": "SĐT này đã được đăng ký. Vui lòng Đăng nhập hoặc dùng chức năng 'Quên mật khẩu'."
            }), 409 
            
        elif existing_customer_sdt.trangthai == 'pending':
            try:
                otp_code, otp_expire = generate_code(6), datetime.utcnow() + timedelta(minutes=10)
                existing_customer_sdt.otp_code = otp_code
                existing_customer_sdt.otp_expire = otp_expire
                existing_customer_sdt.hoten = hoten
                existing_customer_sdt.email = email
                existing_customer_sdt.taikhoan = taikhoan
                existing_customer_sdt.matkhau = generate_password_hash(matkhau)
                db.session.commit()
                
                send_email(email, "Xác nhận tài khoản", f"Mã OTP kích hoạt tài khoản: {otp_code}. Hiệu lực 10 phút.")
                return jsonify({"success": True, "message": "SĐT này đang chờ xác thực. Mã OTP mới đã được gửi đến email của bạn."}), 200
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Lỗi gửi lại OTP khi register: {e}")
                return jsonify({"success": False, "message": "Lỗi khi gửi lại OTP."}), 500
        
        elif existing_customer_sdt.trangthai == 'blocked':
            return jsonify({"success": False, "message": "Tài khoản này đã bị khóa. Vui lòng liên hệ spa."}), 403

    if KhachHang.query.filter(
        (KhachHang.taikhoan == taikhoan) | (KhachHang.email == email)
    ).first(): 
        return jsonify({"success": False, "message": "Tên tài khoản hoặc Email đã tồn tại"}), 409

    try:
        otp_code, otp_expire = generate_code(6), datetime.utcnow() + timedelta(minutes=10)
        user = KhachHang(
            taikhoan=taikhoan, 
            matkhau=generate_password_hash(matkhau), 
            hoten=hoten, 
            email=email, 
            sdt=sdt, 
            trangthai='pending', 
            otp_code=otp_code, 
            otp_expire=otp_expire
        )
        db.session.add(user)
        db.session.commit()

        email_subject = "Bin Spa - Xác nhận đăng ký tài khoản"

        email_body = f"""
        Xin chào <strong>{hoten}</strong>,<br><br>

        Cảm ơn bạn đã đăng ký tài khoản tại <strong>Bin Spa</strong>.<br>
        Để hoàn tất quá trình tạo tài khoản, vui lòng nhập mã xác thực (OTP) dưới đây:<br><br>

        <h2 style="color: #C9A961; letter-spacing: 2px;">{otp_code}</h2>

        Mã OTP này có hiệu lực trong <strong>10 phút</strong> kể từ khi nhận email.<br><br>

        Nếu bạn không thực hiện đăng ký tài khoản, vui lòng bỏ qua email này.<br><br>

        Trân trọng,<br>
        <strong>Bin Spa</strong>
        """

        send_email(email, email_subject, email_body)

        return jsonify({"success": True, "message": "Đăng ký thành công, vui lòng kiểm tra email để xác nhận OTP"}), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gửi OTP thất bại: {e}")

        return jsonify({"success": False, "message": "Đăng ký thành công nhưng gửi OTP thất bại"}), 500

@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json() or {}
    otp_code = data.get("otp_code")
    
    if not otp_code: 
        return jsonify({"success": False, "message": "Thiếu mã OTP"}), 400
    
    # Tìm user có OTP code này
    user = KhachHang.query.filter_by(otp_code=otp_code).first()
    
    if not user: 
        return jsonify({"success": False, "message": "Mã OTP không hợp lệ"}), 404
    
    if user.trangthai != 'pending': 
        return jsonify({"success": False, "message": "Tài khoản không ở trạng thái chờ kích hoạt"}), 400
    
    if user.otp_expire < datetime.utcnow(): 
        return jsonify({"success": False, "message": "Mã OTP đã hết hạn"}), 400

    user.trangthai = 'active'
    user.otp_code = None
    user.otp_expire = None
    db.session.commit()
    
    return jsonify({"success": True, "message": "Kích hoạt tài khoản thành công"}), 200

@auth_bp.route("/login/customer", methods=["POST"])
def customer_login():
    from flask import session
    
    data = request.get_json() or {}
    
    identifier_raw = data.get("taikhoan") or data.get("email") or data.get("sdt")
    matkhau_raw = data.get("matkhau")
    
    identifier = identifier_raw.strip() if identifier_raw else None
    matkhau = matkhau_raw.strip() if matkhau_raw else None
    
    if not identifier or not matkhau: 
        return jsonify({"success": False, "message": "Thiếu thông tin đăng nhập"}), 400

    user = KhachHang.query.filter(
        or_(
            KhachHang.taikhoan == identifier, 
            KhachHang.email == identifier, 
            KhachHang.sdt == identifier
        )
    ).first()
    
    if not user: 
        return jsonify({"success": False, "message": "Tài khoản không tồn tại"}), 404
    
    if not check_password_hash(user.matkhau, matkhau): 
        return jsonify({"success": False, "message": "Mật khẩu không đúng"}), 401
    
    if user.trangthai != 'active': 
        return jsonify({"success": False, "message": "Tài khoản chưa được kích hoạt hoặc đã bị khóa"}), 403

    session.clear()  
    session['user_id'] = user.makh
    session['user_type'] = 'customer'
    session['user_name'] = user.hoten
    session['avatar'] = user.avatar if hasattr(user, 'avatar') else None
    session.permanent = True  
    
    access_token = create_access_token(identity=f"customer:{user.makh}")
    
    current_app.logger.info(f"Login successful for user {user.makh}, session set: {session}")
    
    return jsonify({
        "success": True,
        "message": "Đăng nhập thành công",
        "access_token": access_token,
        "redirect_url": "/",
        "user": {
            "makh": user.makh, 
            "taikhoan": user.taikhoan, 
            "hoten": user.hoten
        }
    }), 200

@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    
    identifier = data.get("identifier") 
    
    if not identifier: 
        return jsonify({"success": False, "message": "Vui lòng nhập Email hoặc Số điện thoại"}), 400
    
    # Tìm người dùng bằng Email HOẶC SĐT
    user = KhachHang.query.filter(
        or_(
            KhachHang.email == identifier, 
            KhachHang.sdt == identifier
        )
    ).first()
    
    if not user: 
        # Không tìm thấy bằng cả email lẫn sđt
        return jsonify({"success": False, "message": "Email hoặc Số điện thoại không tồn tại"}), 404
    if not user.email:
        return jsonify({
            "success": False, 
            "message": "Tài khoản này được tạo bằng SĐT và không có email. Vui lòng đăng nhập bằng SĐT của bạn (mật khẩu mặc định là SĐT)."
        }), 400 

    # Nếu họ có email, tiếp tục như cũ
    code = generate_code(6)
    user.resettoken = code
    user.resettokenexpire = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()

    try:
        # Gửi email đến user.email (chứ không phải identifier)
        send_email(user.email, "Đặt lại mật khẩu", f"Mã đặt lại mật khẩu: {code}. Hiệu lực 15 phút.")
        return jsonify({"success": True, "message": "Mã đặt lại mật khẩu đã được gửi đến email của bạn"}), 200
    except Exception as e:
        current_app.logger.error(str(e))
        return jsonify({"success": False, "message": "Gửi email thất bại"}), 500
    
@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    # Lấy user từ session hoặc từ email trong request
    data = request.get_json() or {}
    email = data.get("email")
    
    if not email:
        return jsonify({"success": False, "message": "Thiếu email"}), 400
    
    user = KhachHang.query.filter_by(email=email, trangthai='pending').first()
    
    if not user:
        return jsonify({"success": False, "message": "Không tìm thấy tài khoản chờ xác thực"}), 404
    
    # Tạo OTP mới
    otp_code = generate_code(6)
    user.otp_code = otp_code
    user.otp_expire = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    
    try:
        send_email(email, "Mã OTP mới", f"Mã OTP kích hoạt tài khoản: {otp_code}. Hiệu lực 10 phút.")
        return jsonify({"success": True, "message": "Đã gửi lại mã OTP"}), 200
    except Exception as e:
        current_app.logger.error(str(e))
        return jsonify({"success": False, "message": "Gửi OTP thất bại"}), 500

# API CHO NHÂN VIÊN              
@auth_bp.route("/login/staff", methods=["POST"])
def staff_login():
    from flask import session
    
    data = request.get_json() or {}
    taikhoan = data.get("taikhoan")
    matkhau = data.get("matkhau")
    
    if not taikhoan or not matkhau: 
        return jsonify({"success": False, "message": "Thiếu tài khoản hoặc mật khẩu"}), 400
    
    staff = NhanVien.query.filter_by(taikhoan=taikhoan).first()
    
    if not staff or not check_password_hash(staff.matkhau, matkhau): 
        return jsonify({"success": False, "message": "Tài khoản hoặc mật khẩu không chính xác"}), 401
    
    if not staff.trangthai: 
        return jsonify({"success": False, "message": "Tài khoản này đã bị vô hiệu hóa"}), 403
    
    session.clear()
    session['user_id'] = staff.manv
    session['user_type'] = 'staff'
    session['user_name'] = staff.hoten
    session['user_role'] = staff.role
    session.permanent = True
    
    access_token = create_access_token(identity=f"staff:{staff.manv}")
    
    return jsonify({
        "success": True,
        "message": "Đăng nhập thành công",
        "access_token": access_token,
        "redirect_url": "/admin",
        "user": {
            "manv": staff.manv, 
            "hoten": staff.hoten, 
            "role": staff.role
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    from flask import session
    session.clear()
    current_app.logger.info("User logged out, session cleared")
    return jsonify({'success': True, 'message': 'Đăng xuất thành công'})

@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Đặt lại mật khẩu bằng mã khôi phục."""
    data = request.get_json() or {}
    
    reset_code = data.get("reset_code")  
    new_password = data.get("matkhau")  
    
    if not reset_code or not new_password: 
        return jsonify({"success": False, "message": "Thiếu mã khôi phục hoặc mật khẩu mới"}), 400
    
    user = KhachHang.query.filter_by(resettoken=reset_code).first()
    
    if not user: 
        return jsonify({"success": False, "message": "Mã khôi phục không hợp lệ hoặc đã được sử dụng"}), 404
        
    if user.resettokenexpire < datetime.utcnow(): 
        return jsonify({"success": False, "message": "Mã khôi phục đã hết hạn"}), 400

    try:
        user.matkhau = generate_password_hash(new_password)
        user.resettoken = None
        user.resettokenexpire = None
        db.session.commit()
        
        return jsonify({"success": True, "message": "Đặt lại mật khẩu thành công"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi đặt lại mật khẩu: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống khi cập nhật mật khẩu"}), 500
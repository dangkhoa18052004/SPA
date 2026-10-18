# app/decorators.py
from functools import wraps
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask import jsonify, g, current_app
from .models import NhanVien, KhachHang

def get_current_user():
    """
    Hàm tiện ích lấy thông tin user (KhachHang hoặc NhanVien) từ JWT.
    Trả về (user_object, user_type)
    """
    identity = get_jwt_identity()
    if not identity or ':' not in identity:
        return None, None

    try:
        user_type, user_id_str = identity.split(':', 1)
        user_id = int(user_id_str)

        if user_type == 'customer':
            user = KhachHang.query.get(user_id)
            return user, 'customer'
        elif user_type == 'staff':
            user = NhanVien.query.get(user_id)
            return user, 'staff'
        
        return None, None
        
    except ValueError:
        return None, None

def login_required(fn):
    """
    Decorator yêu cầu đăng nhập (cả Customer hoặc Staff).
    Lưu user và user_type vào flask.g (global context)
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user, user_type = get_current_user()
        
        if not user:
            return jsonify({"msg": "Token không hợp lệ hoặc người dùng không tồn tại"}), 401
        if user_type == 'staff' and not user.trangthai:
            return jsonify({"msg": "Tài khoản nhân viên đã bị vô hiệu hóa"}), 403
        
        # Lưu vào global context 'g' của Flask, để API có thể truy cập
        g.current_user = user
        g.current_user_type = user_type
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    """
    Decorator kiểm tra vai trò (dành cho Staff).
    ADMIN (role='admin') LUÔN ĐƯỢC PHÉP TRUY CẬP.
    """
    def wrapper(fn):
        @wraps(fn)
        @login_required  # Tự động yêu cầu đăng nhập trước
        def decorator(*args, **kwargs):
            # g.current_user và g.current_user_type đã được set bởi @login_required
            user = g.current_user
            user_type = g.current_user_type

            # Log để debug
            current_app.logger.debug(f"🔐 roles_required check: user_type={user_type}, user={user}")

            # CHỈ KIỂM TRA NẾU LÀ STAFF
            if user_type != 'staff':
                return jsonify({"msg": "Chức năng này chỉ dành cho nhân viên!"}), 403
            
            # Nếu là staff, kiểm tra role
            if not user:
                return jsonify({"msg": "Không tìm thấy thông tin nhân viên"}), 403
            
            # ADMIN LUÔN ĐƯỢC PHÉP (quan trọng!)
            if hasattr(user, 'role') and user.role == 'admin':
                current_app.logger.debug(f"✅ Admin được phép truy cập")
                return fn(*args, **kwargs)
            
            # Kiểm tra role khác
            if hasattr(user, 'role') and user.role not in roles:
                current_app.logger.warning(f"⚠️ User role '{user.role}' không được phép. Cần: {roles}")
                return jsonify({"msg": f"Bạn không có quyền truy cập. Cần vai trò: {', '.join(roles)}"}), 403
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def admin_required(fn):
    """
    Decorator CHỈ cho phép Admin.
    """
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        user = g.current_user
        user_type = g.current_user_type
        
        if user_type != 'staff':
            return jsonify({"msg": "Chức năng này chỉ dành cho Admin"}), 403
        
        if not hasattr(user, 'role') or user.role != 'admin':
            return jsonify({"msg": "Chức năng này chỉ dành cho Admin"}), 403
        
        return fn(*args, **kwargs)
    return wrapper

def admin_or_roles_required(*roles):
    """
    Decorator linh hoạt: cho phép Admin HOẶC các role cụ thể.
    Dùng cho các API cần phân quyền nhưng Admin luôn được phép.
    
    Usage:
        @admin_or_roles_required('manager', 'letan')
    """
    def wrapper(fn):
        @wraps(fn)
        @login_required
        def decorator(*args, **kwargs):
            user = g.current_user
            user_type = g.current_user_type

            if user_type != 'staff':
                return jsonify({"msg": "Chức năng này chỉ dành cho nhân viên!"}), 403
            
            if not user:
                return jsonify({"msg": "Không tìm thấy thông tin nhân viên"}), 403
            
            # Admin luôn được phép
            if hasattr(user, 'role') and user.role == 'admin':
                return fn(*args, **kwargs)
            
            # Hoặc role trong danh sách cho phép
            if hasattr(user, 'role') and user.role in roles:
                return fn(*args, **kwargs)
            
            return jsonify({
                "msg": f"Bạn không có quyền truy cập. Cần vai trò: {', '.join(roles)} hoặc Admin"
            }), 403
            
        return decorator
    return wrapper

def customer_required(fn):
    """
    Decorator kiểm tra có phải là Khách hàng không.
    """
    @wraps(fn)
    @login_required  # Tự động yêu cầu đăng nhập trước
    def wrapper(*args, **kwargs):
        user_type = g.current_user_type # Lấy từ @login_required

        if user_type != 'customer':
            return jsonify({"msg": "Chức năng này chỉ dành cho khách hàng!"}), 403
        
        return fn(*args, **kwargs)
    return wrapper

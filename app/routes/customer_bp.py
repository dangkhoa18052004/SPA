from flask import (
    Blueprint,
    current_app,
    redirect,
    jsonify,
    render_template,
    send_from_directory,
    session,
    url_for,
    request,
)

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/')
def index():
    return render_template('customer/index.html')


@customer_bp.route('/google0835245852bdc722.html')
def google_verification():
    return send_from_directory(
        current_app.static_folder,
        'google0835245852bdc722.html'
    )


@customer_bp.route('/services/<int:service_id>')
def service_detail_page(service_id):
    """Trang chi tiết dịch vụ - HTML page"""
    return render_template('customer/service_detail.html')

@customer_bp.route('/auth/login')
def login_page():
    if session.get('user_id') and session.get('user_type') == 'customer':
        target = request.args.get('redirect', '/')
        if not target.startswith('/') or target.startswith('//') or '\\' in target or any(ord(c)<32 for c in target):
            target = '/'
        return redirect(target)
    
    return render_template('customer/login.html')

@customer_bp.route('/auth/register')
def register_page():
    if session.get('user_id') and session.get('user_type') == 'customer':
        return redirect(url_for('customer.index'))
    
    return render_template('customer/register.html')

@customer_bp.route('/auth/verify-otp')
def verify_otp_page():
    email = session.get('registration_email', 'your-email@example.com') 
    return render_template('customer/verify_otp.html', email=email)

@customer_bp.route('/auth/forgot-password')
def forgot_password_page():
    return render_template('customer/forgot_password.html')

@customer_bp.route('/auth/reset-password')
def reset_password_page():
    return render_template('customer/reset_password.html')

@customer_bp.route('/appointments/create')
def appointment_create():
    return render_template('customer/appointment_create.html')

@customer_bp.route('/services')
def services():
    return render_template('customer/services.html')

@customer_bp.route('/profile')
def profile():
    return render_template('customer/profile.html')

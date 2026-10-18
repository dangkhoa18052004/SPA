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
from ..ui_assets import portal_assets, customer_public_assets, customer_account_assets

customer_bp = Blueprint('customer', __name__)


@customer_bp.app_context_processor
def customer_ui_context():
    # Package pages belong to a separate blueprint but share the customer layout.
    eligible = request.blueprint == 'customer' or request.endpoint == 'packages.package_page'
    account = customer_account_assets() if request.endpoint == 'customer.profile' else None
    assets = account if request.endpoint == 'customer.profile' else customer_public_assets() if eligible else None
    return {'customer_ui_assets': assets, 'customer_account_enabled': bool(account)}

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
    service = None
    if current_app.config.get('CUSTOMER_PUBLIC_UI_ENABLED') and request.args.get('ui') != 'legacy':
        from sqlalchemy.exc import SQLAlchemyError
        from ..models import DichVu
        from ..extensions import db
        try:
            service = DichVu.query.filter_by(madv=service_id, active=True).first()
        except SQLAlchemyError:
            db.session.rollback()
    return render_template('customer/service_detail.html', public_service=service)

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
    email = session.get('registration_email')  # None: JS lấy từ sessionStorage (otp_email)
    return render_template('customer/verify_otp.html', email=email)

@customer_bp.route('/auth/forgot-password')
def forgot_password_page():
    return render_template('customer/forgot_password.html')

@customer_bp.route('/auth/reset-password')
def reset_password_page():
    return render_template('customer/reset_password.html')

@customer_bp.route('/appointments/create')
def appointment_create():
    if current_app.config.get('CUSTOMER_BOOKING_REACT_ENABLED') and request.args.get('ui') != 'legacy':
        assets = portal_assets('src/booking-main.tsx')
        if assets:
            return render_template('customer/booking_react.html', **assets)
    return render_template('customer/appointment_create.html')

@customer_bp.route('/services')
def services():
    return render_template('customer/services.html')

@customer_bp.route('/profile')
def profile():
    return render_template('customer/profile.html')

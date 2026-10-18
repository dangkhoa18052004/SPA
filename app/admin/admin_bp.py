from flask import Blueprint, render_template, current_app, redirect, request, abort
from ..ui_assets import admin_portal_page, portal_assets

admin_bp = Blueprint('admin_pages', __name__)


@admin_bp.route('/reports')
def reports_page():
    if not current_app.config.get('BI_REPORTS_ENABLED'):
        abort(404)
    assets = portal_assets('src/main.tsx')
    if not assets:
        return 'Vui lòng build giao diện trước khi mở Báo cáo.', 503
    return render_template('operations/portal.html', portal_title='Báo cáo kinh doanh', **assets)


@admin_bp.route('/crm')
def crm_page():
    if not current_app.config.get('CRM_ENABLED'):
        abort(404)
    assets = portal_assets('src/main.tsx')
    if not assets:
        return 'Vui lòng build giao diện trước khi mở Chăm sóc khách hàng.', 503
    return render_template('operations/portal.html', portal_title='Chăm sóc khách hàng', **assets)


@admin_bp.route('/reviews')
def admin_reviews_page():
    return admin_portal_page('Đánh giá khách hàng', 'ADMIN_CARE_REACT_ENABLED') or render_template('admin/reviews.html')

_admin_portal = admin_portal_page


@admin_bp.route('/login')
def admin_login_page():
    """Trang đăng nhập của nhân viên."""
    return _admin_portal('Đăng nhập nhân viên') or render_template('admin/login.html')

@admin_bp.route('/dashboard')
def admin_dashboard_page():
    """Trang dashboard (yêu cầu JS xác thực)."""
    return _admin_portal('Tổng quan công việc') or render_template('admin/dashboard.html')

@admin_bp.route('/appointments')
def admin_appointments_page():
    """Trang quản lý lịch hẹn (yêu cầu JS xác thực)."""
    return _admin_portal('Lịch hẹn', 'ADMIN_BOOKING_REACT_ENABLED') or render_template('admin/appointments.html')

@admin_bp.route('/staff')
def admin_staff_page():
    """Trang quản lý nhân viên (yêu cầu JS xác thực)."""
    return _admin_portal('Nhân viên', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template('admin/staff.html')

@admin_bp.route('/shifts')
def admin_shifts_page():
    """Trang quản lý ca làm (yêu cầu JS xác thực)."""
    return _admin_portal('Ca làm', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template('admin/shifts.html')

@admin_bp.route('/salary')
def admin_salary_page():
    """Trang quản lý lương (yêu cầu JS xác thực)."""
    return _admin_portal('Lịch sử lương', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template('admin/salaries.html')

@admin_bp.route('/services')
def admin_services_page():
    """Trang quản lý dịch vụ (yêu cầu JS xác thực)."""
    return _admin_portal('Dịch vụ', 'ADMIN_CATALOG_REACT_ENABLED') or render_template('admin/services.html')

@admin_bp.route('/chat')
def admin_chat_page():
    """Trang chat (yêu cầu JS xác thực)."""
    return _admin_portal('Tin nhắn', 'ADMIN_CARE_REACT_ENABLED') or render_template('admin/chat.html')

@admin_bp.route('/roles')
def admin_roles_page():
    """Trang quản lý chức vụ (yêu cầu JS xác thực)."""
    return _admin_portal('Chức vụ', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template('admin/roles.html')

@admin_bp.route('/customers')
def admin_customers_page():
    """Trang quản lý khách hàng (yêu cầu JS xác thực)."""
    return _admin_portal('Khách hàng', 'ADMIN_BOOKING_REACT_ENABLED') or render_template('admin/customers.html')

@admin_bp.route('/my-schedule')
def staff_schedule_page():
    """Trang lịch làm của tôi (yêu cầu JS xác thực)."""
    return _admin_portal('Lịch làm của tôi', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template('admin/my_schedule.html')

@admin_bp.route('/my-salary')
def staff_salary_page():
    """Trang lương của tôi (yêu cầu JS xác thực)."""
    if current_app.config.get('EMPLOYEE_PORTAL_ENABLED') and current_app.config.get('PAYROLL_V2_ENABLED'):
        return redirect('/employee/income')
    return render_template('admin/my_salary.html')

@admin_bp.route('/register-shift')
def staff_register_shift_page():
    """Trang đăng ký ca (yêu cầu JS xác thực)."""
    return _admin_portal('Đăng ký ca', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template('admin/register_shift.html')

@admin_bp.route("/approve-shifts")
def approve_shifts_page():
    """Trang duyệt ca làm (yêu cầu JS xác thực)."""
    return _admin_portal('Duyệt đăng ký ca', 'ADMIN_PEOPLE_REACT_ENABLED') or render_template("admin/approve_shifts.html")

@admin_bp.route("/invoices")
def admin_invoices_page():
    """Trang quản lý hóa đơn (yêu cầu JS xác thực)."""
    return _admin_portal('Hóa đơn', 'ADMIN_BILLING_REACT_ENABLED') or render_template("admin/invoices.html")

@admin_bp.route("/profile")
def staff_profile_page():
    """Trang xem hồ sơ cá nhân (yêu cầu JS xác thực)."""
    return _admin_portal('Trang cá nhân') or render_template('admin/profile.html')


@admin_bp.route('/<path:unknown_path>')
def unknown_admin_page(unknown_path):
    page = _admin_portal('Không tìm thấy trang', 'ADMIN_CARE_REACT_ENABLED')
    if page:
        return page, 404
    abort(404)


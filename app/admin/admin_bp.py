from flask import Blueprint, render_template

admin_bp = Blueprint('admin_pages', __name__)

@admin_bp.route('/login')
def admin_login_page():
    """Trang đăng nhập của nhân viên."""
    return render_template('admin/login.html')

@admin_bp.route('/dashboard')
def admin_dashboard_page():
    """Trang dashboard (yêu cầu JS xác thực)."""
    return render_template('admin/dashboard.html')

@admin_bp.route('/appointments')
def admin_appointments_page():
    """Trang quản lý lịch hẹn (yêu cầu JS xác thực)."""
    return render_template('admin/appointments.html')

@admin_bp.route('/staff')
def admin_staff_page():
    """Trang quản lý nhân viên (yêu cầu JS xác thực)."""
    return render_template('admin/staff.html')

@admin_bp.route('/shifts')
def admin_shifts_page():
    """Trang quản lý ca làm (yêu cầu JS xác thực)."""
    return render_template('admin/shifts.html')

@admin_bp.route('/salary')
def admin_salary_page():
    """Trang quản lý lương (yêu cầu JS xác thực)."""
    return render_template('admin/salaries.html')

@admin_bp.route('/services')
def admin_services_page():
    """Trang quản lý dịch vụ (yêu cầu JS xác thực)."""
    return render_template('admin/services.html')

@admin_bp.route('/chat')
def admin_chat_page():
    """Trang chat (yêu cầu JS xác thực)."""
    return render_template('admin/chat.html')

@admin_bp.route('/roles')
def admin_roles_page():
    """Trang quản lý chức vụ (yêu cầu JS xác thực)."""
    return render_template('admin/roles.html')

@admin_bp.route('/customers')
def admin_customers_page():
    """Trang quản lý khách hàng (yêu cầu JS xác thực)."""
    return render_template('admin/customers.html')

@admin_bp.route('/my-schedule')
def staff_schedule_page():
    """Trang lịch làm của tôi (yêu cầu JS xác thực)."""
    return render_template('admin/my_schedule.html')

@admin_bp.route('/my-salary')
def staff_salary_page():
    """Trang lương của tôi (yêu cầu JS xác thực)."""
    return render_template('admin/my_salary.html')

@admin_bp.route('/register-shift')
def staff_register_shift_page():
    """Trang đăng ký ca (yêu cầu JS xác thực)."""
    return render_template('admin/register_shift.html')

@admin_bp.route("/approve-shifts")
def approve_shifts_page():
    """Trang duyệt ca làm (yêu cầu JS xác thực)."""
    return render_template("admin/approve_shifts.html")

@admin_bp.route("/invoices")
def admin_invoices_page():
    """Trang quản lý hóa đơn (yêu cầu JS xác thực)."""
    return render_template("admin/invoices.html")

@admin_bp.route("/profile")
def staff_profile_page():
    """Trang xem hồ sơ cá nhân (yêu cầu JS xác thực)."""
    return render_template('admin/profile.html')


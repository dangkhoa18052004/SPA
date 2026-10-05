"""F09–F12: dashboard không ép 2 cột, menu theo tần suất, hồ sơ mở Lịch hẹn trước, rating trong danh sách nhân viên."""
import re
from datetime import datetime, timedelta

from app.extensions import db
from app.models import DanhGia, LichHen, AppointmentStatus


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_dashboard_has_no_inline_two_column_grid():
    html = _read('app/templates/admin/dashboard.html')
    assert '2fr 1fr' not in html
    assert 'class="analytics-row"' in html and 'id="dash-range-preset"' in html
    css = _read('app/static/css/admin/dashboard.css')
    # Một cột mặc định, nhiều cột chỉ từ màn hình rộng.
    block = css[css.index('.analytics-row {'):]
    assert 'grid-template-columns: 1fr;' in block.split('}')[0]
    assert '.chart-panel { min-width: 0; }' in css


def test_admin_menu_order_follows_daily_tasks():
    js = _read('app/static/js/admin/admin_layout.js')
    admin = js[js.index('    admin: ['):js.index('    manager: [')]
    keys = re.findall(r"menuItem\('(\w+)'", admin)
    assert keys[:5] == ['dashboard', 'appointments', 'invoices', 'package_sales', 'customers']
    assert keys[-1] == 'profile'
    letan = js[js.index('    letan: ['):js.index('    staff: [')]
    assert 'Đổi quà / Tra mã' in letan  # nhãn dùng bởi kiểm thử quầy quà


def test_customer_profile_tabs_order_and_default():
    html = _read('app/templates/customer/profile.html')
    menu = html[html.index('<ul class="profile-menu"'):html.index('</ul>')]
    assert re.findall(r'data-section="(\w+)"', menu) == ['appointments', 'treatments', 'loyalty', 'invoices', 'reviews', 'info']
    assert 'data-goto-section="edit"' in html and 'data-goto-section="password"' in html
    assert 'class="profile-section active" id="appointments-section"' in html
    js = _read('app/static/js/customers/profile.js')
    assert "history.replaceState(null, '', `${location.pathname}${location.search}#${sectionName}`)" in js


def test_staff_list_includes_rating_average_and_count(app, client, admin_auth_headers, staff_auth_headers):
    staff_id = app.config['TEST_STAFF_ID']
    with app.app_context():
        for rating in (5, 4):
            apt = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=staff_id,
                          ngaygio=datetime.now() - timedelta(days=rating), trangthai=AppointmentStatus.COMPLETED)
            db.session.add(apt); db.session.flush()
            db.session.add(DanhGia(malh=apt.malh, makh=app.config['TEST_CUSTOMER_ID'], manv=staff_id, rating=rating))
        db.session.commit()
    rows = client.get('/api/admin/staff/list-all', headers=admin_auth_headers).json
    me = next(r for r in rows if r['manv'] == staff_id)
    assert me['rating_average'] == 4.5 and me['rating_count'] == 2
    other = next(r for r in rows if r['manv'] == app.config['TEST_STAFF2_ID'])
    assert other['rating_average'] is None and other['rating_count'] == 0
    assert client.get('/api/admin/staff/list-all', headers=staff_auth_headers).status_code == 403


def test_cancel_uses_accessible_danger_dialog():
    js = _read('app/static/js/admin/appointments.js')
    assert "prompt('Lý do hủy" not in js
    body = js[js.index('function showConfirm('):js.index('function exportAppointments()')]
    assert 'role="alertdialog"' in body and "e.key === 'Escape'" in body and 'btn-danger' in body

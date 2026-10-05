"""F05/F12: bộ lọc lịch hẹn admin đủ trạng thái, nút Xóa bộ lọc luôn hiện, hồ sơ không lộ mã trạng thái."""
import re
from datetime import date, datetime, time

from app.extensions import db
from app.models import LichHen, AppointmentStatus


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_status_dropdown_has_all_five_statuses():
    html = _read('app/templates/admin/appointments.html')
    select = re.search(r'<select id="filter-status-select".*?</select>', html, re.S).group(0)
    values = re.findall(r'<option value="(\w*)"', select)
    assert values == ['', 'pending', 'confirmed', 'in_progress', 'completed', 'cancelled']


def test_reset_button_is_never_hidden_by_utility_classes():
    html = _read('app/templates/admin/appointments.html')
    button = re.search(r'<button[^>]*id="reset-filters-btn"[^>]*>', html).group(0)
    assert 'd-none' not in button and 'onclick="resetFilters()"' in button
    assert 'd-lg-flex' not in html  # lớp không tồn tại trong utilities.css


def test_reset_clears_search_state_and_reloads_table_and_stats():
    js = _read('app/static/js/admin/appointments.js')
    body = js[js.index('function resetFilters()'):js.index('function openAddAppointmentModal()')]
    assert "appointmentSearchText = ''" in body
    assert 'loadAppointments({}, emptyRange)' in body and 'loadStatistics(emptyRange)' in body
    # Search áp dụng qua visibleAppointments nên phân trang không mất kết quả tìm kiếm.
    assert 'Math.ceil(visibleAppointments().length' in js


def test_api_filters_pending_and_in_progress(app, client, admin_auth_headers):
    today = date.today()
    with app.app_context():
        for status in (AppointmentStatus.PENDING, AppointmentStatus.IN_PROGRESS, AppointmentStatus.CONFIRMED):
            db.session.add(LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'],
                                   ngaygio=datetime.combine(today, time(10)), trangthai=status))
        db.session.commit()
    for status in ('pending', 'in_progress'):
        r = client.get(f'/api/admin/appointments?start_date={today}&end_date={today}&status={status}',
                       headers=admin_auth_headers)
        assert r.status_code == 200
        rows = r.get_json()
        assert len(rows) == 1 and rows[0]['trangthai'] == status


def test_customer_profile_maps_in_progress_without_exposing_code():
    js = _read('app/static/js/customers/profile.js')
    block = js[js.index('function displayAppointments'):]
    assert "'in_progress': { text: 'Đang thực hiện'" in block
    assert 'apt.trangthai_vi' in block
    assert "text: apt.trangthai, class" not in block


def test_my_appointments_returns_vietnamese_label(app, client, customer_auth_headers):
    with app.app_context():
        db.session.add(LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'],
                               ngaygio=datetime.combine(date.today(), time(11)), trangthai=AppointmentStatus.IN_PROGRESS))
        db.session.commit()
    rows = client.get('/api/appointments/my-appointments', headers=customer_auth_headers).get_json()['appointments']
    assert rows[0]['trangthai_vi'] == 'Đang thực hiện'

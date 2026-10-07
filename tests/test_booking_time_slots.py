"""F06/F07: giờ đặt lịch lấy từ API theo tổng thời lượng; không trùng giờ; gợi ý ngày khác; liệu trình trước xác nhận."""
import re
from datetime import date, datetime, time, timedelta

import pytest

from app.extensions import db
from app.models import CaLam, DichVu, LichHen, ChiTietLichHen, nhanvien_calam, AppointmentStatus
from app.services import appointment_service


@pytest.fixture
def slot_data(app):
    with app.app_context():
        day = date.today() + timedelta(days=2)
        s60 = DichVu(tendv='Massage 60', gia=300000, thoiluong=60, active=True)
        s90 = DichVu(tendv='Facial 90', gia=500000, thoiluong=90, active=True)
        db.session.add_all([s60, s90])
        shift = CaLam(ngay=day, giobatdau=time(9), gioketthuc=time(12))
        db.session.add(shift)
        db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'], maca=shift.maca))
        db.session.commit()
        return dict(day=day, s60=s60.madv, s90=s90.madv)


def _slots(client, data, ids, **extra):
    query = '&'.join([f"date={data['day']}", 'madv_list=' + ','.join(map(str, ids))] + [f'{k}={v}' for k, v in extra.items()])
    r = client.get(f'/api/appointments/available-slots?{query}')
    assert r.status_code == 200, r.json
    return r.json


def test_slot_times_follow_technician_shifts(app, slot_data):
    with app.app_context():
        times = [t.strftime('%H:%M') for t in appointment_service.slot_times(slot_data['day'], 60)]
        assert times == ['09:00', '09:30', '10:00', '10:30', '11:00']  # ca 09:00–12:00, dịch vụ 60 phút
        assert len(times) == len(set(times))
        assert appointment_service.slot_times(slot_data['day'] + timedelta(days=1), 60) == []


def test_manager_only_shift_reports_no_technician(app, client, slot_data):
    from app.models import NhanVien
    with app.app_context():
        day = slot_data['day'] + timedelta(days=1)
        shift = CaLam(ngay=day, giobatdau=time(7), gioketthuc=time(19))
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_ADMIN_ID'], maca=shift.maca))
        db.session.commit()
    r = client.get(f"/api/appointments/available-slots?date={day}&madv_list={slot_data['s60']}&suggest=1").json
    assert r['day_status'] == 'no_technician' and r['slots'] == []
    assert r['suggestions'] == []  # ngày slot_data['day'] đã qua so với 'ngày sau' → không gợi ý ngược


def test_total_duration_limits_start_times(client, slot_data):
    one = _slots(client, slot_data, [slot_data['s60']])
    assert one['duration_minutes'] == 60
    open_one = [s['time'] for s in one['slots'] if s['available']]
    assert open_one == ['09:00', '09:30', '10:00', '10:30', '11:00']
    both = _slots(client, slot_data, [slot_data['s60'], slot_data['s90']])
    assert both['duration_minutes'] == 150
    assert [s['time'] for s in both['slots'] if s['available']] == ['09:00', '09:30']
    assert {s['reason'] for s in both['slots']} <= {'available', 'full', 'past'}
    assert both['day_status'] == 'ok'


def test_existing_booking_blocks_overlapping_slots(app, client, slot_data):
    with app.app_context():
        apt = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'],
                      ngaygio=datetime.combine(slot_data['day'], time(10)), trangthai=AppointmentStatus.CONFIRMED)
        db.session.add(apt); db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=slot_data['s60']))
        db.session.commit()
    open_slots = [s['time'] for s in _slots(client, slot_data, [slot_data['s60']])['slots'] if s['available']]
    assert '10:00' not in open_slots and '09:30' not in open_slots
    assert '09:00' in open_slots and '11:00' in open_slots


def test_full_day_returns_suggestions(app, client, slot_data):
    with app.app_context():
        later = slot_data['day'] + timedelta(days=3)
        shift = CaLam(ngay=later, giobatdau=time(14), gioketthuc=time(18))
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'], maca=shift.maca))
        db.session.commit()
    # 4 tiếng dịch vụ không vừa ca 09:00-12:00 → không còn chỗ trong ngày, gợi ý ngày có ca 14:00-18:00.
    with app.app_context():
        db.session.get(DichVu, slot_data['s90']).thoiluong = 240
        db.session.commit()
    res = _slots(client, slot_data, [slot_data['s90']], suggest=1)
    assert not any(s['available'] for s in res['slots'])
    assert res['day_status'] == 'too_long'  # 4 tiếng không vừa ca 3 tiếng
    assert res['suggestions'][0] == {'date': later.isoformat(), 'time': '14:00'}


def test_invalid_date_is_400(client):
    assert client.get('/api/appointments/available-slots?date=2026-13-40').status_code == 400
    assert client.get('/api/appointments/available-slots').status_code == 400


def test_booking_template_has_no_static_time_list_and_source_before_confirm():
    with open('app/templates/customer/appointment_create.html', encoding='utf-8') as f:
        html = f.read()
    select = re.search(r'<select id="appointmentTime".*?</select>', html, re.S).group(0)
    assert 'id="slotPicker"' in html
    assert re.findall(r'<option value="(\d\d:\d\d)"', select) == []
    # Lựa chọn dùng buổi gói nằm ở bước 1, trước nút "Xác nhận đặt lịch".
    assert html.index('id="bookingTreatments"') < html.index('id="step2"') < html.index('Xác nhận đặt lịch')
    assert 'id="confirmRecap"' in html and html.index('id="confirmRecap"') < html.index('Xác nhận đặt lịch')


def test_booking_js_guards_stale_slot_responses_and_api_errors():
    with open('app/static/js/customers/appointments.js', encoding='utf-8') as f:
        js = f.read()
    body = js[js.index('async function loadTimeSlots()'):js.index('// ==================== LOAD AVAILABLE STAFF')]
    assert 'version !== slotRequestVersion' in body
    assert 'data-retry-slots' in body and 'hết chỗ' in body
    assert 'Lỗi kiểm tra lịch (không phải do kín lịch)' in js


def test_manager_with_technician_position_takes_bookings(app, client, slot_data):
    """Tài khoản quản lý nhưng chức vụ "Kỹ thuật viên" (như hiện trong ca làm) vẫn nhận khách; lễ tân thì không."""
    from app.models import NhanVien, ChucVu
    with app.app_context():
        ktv = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
        reception_role = ChucVu(tencv='Lễ tân', dongiagio=80000)
        db.session.add_all([ktv, reception_role]); db.session.flush()
        manager_ktv = NhanVien(hoten='Quản lý kiêm KTV', taikhoan='ql_ktv', matkhau='x', macv=ktv.macv, role='manager', trangthai=True)
        reception = NhanVien(hoten='Lễ tân', taikhoan='le_tan_x', matkhau='x', macv=reception_role.macv, role='letan', trangthai=True)
        db.session.add_all([manager_ktv, reception]); db.session.flush()
        day = slot_data['day'] + timedelta(days=2)
        shift = CaLam(ngay=day, giobatdau=time(7), gioketthuc=time(19))
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=reception.manv, maca=shift.maca))
        db.session.commit()
        ids = (manager_ktv.manv, shift.maca)
    r = client.get(f"/api/appointments/available-slots?date={day}&madv_list={slot_data['s60']}").json
    assert r['day_status'] == 'no_technician'  # chỉ có lễ tân
    with app.app_context():
        db.session.execute(nhanvien_calam.insert().values(manv=ids[0], maca=ids[1]))
        db.session.commit()
    r = client.get(f"/api/appointments/available-slots?date={day}&madv_list={slot_data['s60']}").json
    assert r['day_status'] == 'ok' and r['slots'][0]['time'] == '07:00'
    staff = client.post('/api/appointments/available-staff', json={'ngaygio': f'{day}T09:00', 'madv_list': [slot_data['s60']]}).json['staff']
    assert [s['manv'] for s in staff if s['available']] == [ids[0]]

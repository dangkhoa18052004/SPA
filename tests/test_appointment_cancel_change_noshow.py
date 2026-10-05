"""Khách hủy trước giờ hẹn, đổi dịch vụ (khách/nhân viên) và tự hủy khi khách không đến sau 30 phút."""
from datetime import timedelta, time, datetime

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import (LichHen, ChiTietLichHen, LieuTrinhUsage, NotificationJob, NhanVien, CaLam,
                        nhanvien_calam, TheLieuTrinhItem, AppointmentStatus, KhachHang)
from app.services import appointment_service, notification_service, package_service as ps

from test_phase4_packages_care import package_data, activate, book  # noqa: F401


def _appointment(app, data, start, services=None, status=AppointmentStatus.CONFIRMED, staff_key='TEST_STAFF_ID'):
    with app.app_context():
        if not CaLam.query.filter_by(ngay=start.date()).first():
            shift = CaLam(ngay=start.date(), giobatdau=time(0), gioketthuc=time(23, 59))
            db.session.add(shift); db.session.flush()
            for key in ('TEST_STAFF_ID', 'TEST_STAFF2_ID'):
                db.session.execute(nhanvien_calam.insert().values(manv=app.config[key], maca=shift.maca))
        apt = LichHen(makh=data['customer'], manv=app.config[staff_key], ngaygio=start.replace(second=0, microsecond=0),
                      trangthai=status)
        db.session.add(apt); db.session.flush()
        for madv in services or [data['service']]:
            db.session.add(ChiTietLichHen(malh=apt.malh, madv=madv))
        db.session.commit()
        return apt.malh


def _reserve(app, malh, record, madv):
    with app.app_context():
        ps.reserve_usages(db.session.get(LichHen, malh), [dict(mathe=record, madv=madv, quantity=1)])
        db.session.commit()


def _available(app, record):
    with app.app_context():
        item = TheLieuTrinhItem.query.filter_by(mathe=record, source_type='package').one()
        return ps.item_counts(item)['available_sessions']


def _headers_for(app, role):
    with app.app_context():
        staff = NhanVien(hoten=f'{role} test', taikhoan=f'{role}_cc', matkhau='x',
                         macv=db.session.get(NhanVien, app.config['TEST_STAFF_ID']).macv, role=role, trangthai=True)
        db.session.add(staff); db.session.commit()
        return {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{staff.manv}')}


# ---------------------------------------------------------------- hủy lịch
def test_customer_can_cancel_shortly_before_start_and_session_returns(app, client, customer_auth_headers,
                                                                     admin_auth_headers, package_data):
    record = activate(client, customer_auth_headers, admin_auth_headers, package_data)
    malh = _appointment(app, package_data, ps.local_now() + timedelta(minutes=40))
    _reserve(app, malh, record, package_data['service'])
    assert _available(app, record) == 4
    r = client.put(f'/api/appointments/{malh}/cancel', headers=customer_auth_headers)
    assert r.status_code == 200, r.json
    assert _available(app, record) == 5


def test_customer_cannot_cancel_after_start_and_gets_reason(app, client, customer_auth_headers, package_data):
    malh = _appointment(app, package_data, ps.local_now() - timedelta(minutes=5))
    r = client.put(f'/api/appointments/{malh}/cancel', headers=customer_auth_headers)
    assert r.status_code == 400
    assert 'quá giờ hẹn' in r.json['message']


def test_my_appointments_flags(app, client, customer_auth_headers, package_data):
    future = _appointment(app, package_data, ps.local_now() + timedelta(hours=1))
    past = _appointment(app, package_data, ps.local_now() - timedelta(minutes=10), staff_key='TEST_STAFF2_ID')
    rows = {a['malh']: a for a in client.get('/api/appointments/my-appointments', headers=customer_auth_headers).json['appointments']}
    assert rows[future]['can_cancel'] and rows[future]['can_change_services']
    assert not rows[past]['can_cancel'] and not rows[past]['can_change_services']
    assert rows[future]['services'][0]['madv'] == package_data['service']


# ---------------------------------------------------------------- đổi dịch vụ
def test_customer_changes_services_and_package_session_follows(app, client, customer_auth_headers,
                                                              admin_auth_headers, package_data):
    record = activate(client, customer_auth_headers, admin_auth_headers, package_data)
    malh = _appointment(app, package_data, ps.local_now() + timedelta(days=1))
    _reserve(app, malh, record, package_data['service'])
    # Bỏ dịch vụ dùng gói, chọn dịch vụ khác → buổi gói hoàn lại.
    r = client.put(f'/api/appointments/{malh}/services', headers=customer_auth_headers,
                   json={'madv_list': [package_data['other_service']]})
    assert r.status_code == 200, r.json
    assert _available(app, record) == 5
    # Thêm lại dịch vụ và dùng buổi gói cho dịch vụ mới thêm.
    r = client.put(f'/api/appointments/{malh}/services', headers=customer_auth_headers, json={
        'madv_list': [package_data['other_service'], package_data['service']],
        'package_usages': [dict(mathe=record, madv=package_data['service'], quantity=1)]})
    assert r.status_code == 200, r.json
    assert r.json['total_duration'] == 90
    assert _available(app, record) == 4
    with app.app_context():
        apt = db.session.get(LichHen, malh)
        assert {d.madv for d in apt.chitiet} == {package_data['service'], package_data['other_service']}
        assert 'Đổi dịch vụ' in apt.ghichu


def test_change_rejected_when_new_duration_overlaps_next_booking(app, client, customer_auth_headers, package_data):
    start = (ps.local_now() + timedelta(days=1)).replace(hour=10, minute=0)
    malh = _appointment(app, package_data, start)
    _appointment(app, package_data, start + timedelta(minutes=50))  # cùng KTV, bắt đầu sau 50 phút
    r = client.put(f'/api/appointments/{malh}/services', headers=customer_auth_headers,
                   json={'madv_list': [package_data['service'], package_data['other_service']]})
    assert r.status_code == 409
    with app.app_context():
        assert len(db.session.get(LichHen, malh).chitiet) == 1


def test_customer_change_rules(app, client, customer_auth_headers, package_data):
    past = _appointment(app, package_data, ps.local_now() - timedelta(minutes=1))
    r = client.put(f'/api/appointments/{past}/services', headers=customer_auth_headers,
                   json={'madv_list': [package_data['other_service']]})
    assert r.status_code == 400
    future = _appointment(app, package_data, ps.local_now() + timedelta(days=1), staff_key='TEST_STAFF2_ID')
    for body in ({'madv_list': []}, {'madv_list': [package_data['service']]}, {'madv_list': [999999]}):
        assert client.put(f'/api/appointments/{future}/services', headers=customer_auth_headers, json=body).status_code == 400
    with app.app_context():
        other = KhachHang(hoten='Khác', taikhoan='other_cc', matkhau='x')
        db.session.add(other); db.session.commit()
        token = create_access_token(identity=f'customer:{other.makh}')
    r = client.put(f'/api/appointments/{future}/services', headers={'Authorization': f'Bearer {token}'},
                   json={'madv_list': [package_data['other_service']]})
    assert r.status_code == 403


def test_staff_can_change_on_customer_request_even_in_progress(app, client, staff_auth_headers, package_data):
    malh = _appointment(app, package_data, ps.local_now() - timedelta(minutes=10), status=AppointmentStatus.IN_PROGRESS)
    reception = _headers_for(app, 'letan')
    r = client.put(f'/api/admin/appointments/{malh}/services', headers=reception,
                   json={'madv_list': [package_data['other_service']]})
    assert r.status_code == 200, r.json
    # KTV được phân lịch cũng đổi được; KTV khác thì không.
    r = client.put(f'/api/admin/appointments/{malh}/services', headers=staff_auth_headers,
                   json={'madv_list': [package_data['service']]})
    assert r.status_code == 200, r.json
    with app.app_context():
        staff2 = create_access_token(identity=f"staff:{app.config['TEST_STAFF2_ID']}")
    r = client.put(f'/api/admin/appointments/{malh}/services', headers={'Authorization': f'Bearer {staff2}'},
                   json={'madv_list': [package_data['other_service']]})
    assert r.status_code == 403
    rows = client.get('/api/admin/appointments', headers=reception).json
    assert next(a for a in rows if a['malh'] == malh)['permissions']['canChangeServices'] is True


# ---------------------------------------------------------------- tự hủy khi không đến
def test_no_show_auto_cancel_releases_session_and_emails_once(app, client, customer_auth_headers,
                                                             admin_auth_headers, package_data, monkeypatch):
    record = activate(client, customer_auth_headers, admin_auth_headers, package_data)
    now = ps.local_now()
    late = _appointment(app, package_data, now - timedelta(minutes=31))
    _reserve(app, late, record, package_data['service'])
    grace = _appointment(app, package_data, now - timedelta(minutes=20), staff_key='TEST_STAFF2_ID')
    started = _appointment(app, package_data, now - timedelta(hours=2), status=AppointmentStatus.IN_PROGRESS)
    with app.app_context():
        db.session.get(KhachHang, package_data['customer']).email = 'customer@example.test'
        db.session.commit()
    assert _available(app, record) == 4

    with app.app_context():
        assert appointment_service.auto_cancel_no_shows(now=now) == [late]
        assert appointment_service.auto_cancel_no_shows(now=now) == []  # chạy lại không xử lý trùng
        assert db.session.get(LichHen, late).trangthai == AppointmentStatus.CANCELLED
        assert 'Tự động hủy' in db.session.get(LichHen, late).ghichu
        assert db.session.get(LichHen, grace).trangthai == AppointmentStatus.CONFIRMED
        assert db.session.get(LichHen, started).trangthai == AppointmentStatus.IN_PROGRESS
        assert LieuTrinhUsage.query.filter_by(malh=late).one().state == 'released'
        jobs = NotificationJob.query.filter_by(malh=late, type='appointment_no_show').all()
        assert len(jobs) == 1 and jobs[0].status == 'pending'
        assert 'đặt lịch mới' in jobs[0].payload_json['body'] and 'hoàn trả' in jobs[0].payload_json['body']
    assert _available(app, record) == 5

    sent = []
    monkeypatch.setattr(notification_service.email_service, 'send_email',
                        lambda to, subject, body, **kw: sent.append((to, subject)) or {'id': 'mock'})
    with app.app_context():
        notification_service.process_jobs()
        notification_service.process_jobs()
        assert NotificationJob.query.filter_by(malh=late, type='appointment_no_show').one().status == 'sent'
    assert sent == [('customer@example.test', f'Bin Spa - Lịch hẹn #{late} đã bị hủy')]


def test_no_show_grace_is_configurable(app, package_data):
    now = ps.local_now()
    malh = _appointment(app, package_data, now - timedelta(minutes=12))
    with app.app_context():
        assert appointment_service.auto_cancel_no_shows(now=now, grace_minutes=15) == []
        assert appointment_service.auto_cancel_no_shows(now=now, grace_minutes=10) == [malh]


def test_auto_cancel_cli(app, package_data):
    malh = _appointment(app, package_data, ps.local_now() - timedelta(hours=1))
    result = app.test_cli_runner().invoke(args=['auto-cancel-no-shows'])
    assert result.exit_code == 0 and str(malh) in result.output


def test_old_backlog_is_cancelled_without_email(app, package_data):
    now = ps.local_now()
    old = _appointment(app, package_data, now - timedelta(days=3))
    with app.app_context():
        db.session.get(KhachHang, package_data['customer']).email = 'customer@example.test'
        db.session.commit()
        assert appointment_service.auto_cancel_no_shows(now=now) == [old]
        assert NotificationJob.query.filter_by(malh=old, type='appointment_no_show').count() == 0


# ---------------------------------------------------------------- check-in
def test_check_in_moves_to_in_progress_and_blocks_no_show(app, client, staff_auth_headers, package_data):
    now = ps.local_now()
    if now.hour == 0 and now.minute < 40:
        pytest.skip('cần lịch hẹn trong cùng ngày')
    malh = _appointment(app, package_data, now - timedelta(minutes=35))
    reception = _headers_for(app, 'letan')
    row = next(a for a in client.get('/api/admin/appointments', headers=reception).json if a['malh'] == malh)
    assert row['permissions']['canCheckIn'] is True
    with app.app_context():
        staff2 = create_access_token(identity=f"staff:{app.config['TEST_STAFF2_ID']}")
    assert client.post(f'/api/admin/appointments/{malh}/check-in',
                       headers={'Authorization': f'Bearer {staff2}'}).status_code == 403
    r = client.post(f'/api/admin/appointments/{malh}/check-in', headers=reception)
    assert r.status_code == 200, r.json
    assert 'trễ' in r.json['msg']
    with app.app_context():
        apt = db.session.get(LichHen, malh)
        assert apt.trangthai == AppointmentStatus.IN_PROGRESS and 'Check-in' in apt.ghichu
        assert appointment_service.auto_cancel_no_shows(now=now) == []
    row = next(a for a in client.get('/api/admin/appointments', headers=reception).json if a['malh'] == malh)
    assert row['permissions']['canCheckIn'] is False and row['permissions']['canComplete'] is True
    assert client.post(f'/api/admin/appointments/{malh}/check-in', headers=reception).status_code == 400


def test_assigned_staff_can_check_in_but_not_other_day(app, client, staff_auth_headers, package_data):
    today = _appointment(app, package_data, ps.local_now() + timedelta(minutes=5))
    tomorrow = _appointment(app, package_data, ps.local_now() + timedelta(days=1))
    assert client.post(f'/api/admin/appointments/{tomorrow}/check-in', headers=staff_auth_headers).status_code == 400
    if ps.local_now().date() == (ps.local_now() + timedelta(minutes=5)).date():
        assert client.post(f'/api/admin/appointments/{today}/check-in', headers=staff_auth_headers).status_code == 200


# ---------------------------------------------------------------- ghi chú gọn
def test_system_notes_keep_only_latest_and_customer_sees_clean_note(app, client, customer_auth_headers, package_data):
    malh = _appointment(app, package_data, ps.local_now() + timedelta(days=1))
    with app.app_context():
        apt = db.session.get(LichHen, malh)
        apt.ghichu = 'Khách dị ứng tinh dầu'
        db.session.commit()
    for ids in ([package_data['service'], package_data['other_service']], [package_data['other_service']]):
        assert client.put(f'/api/appointments/{malh}/services', headers=customer_auth_headers,
                          json={'madv_list': ids}).status_code == 200
    with app.app_context():
        note = db.session.get(LichHen, malh).ghichu
        assert note.count('[Đổi dịch vụ') == 1 and note.startswith('Khách dị ứng tinh dầu')
    row = next(a for a in client.get('/api/appointments/my-appointments', headers=customer_auth_headers).json['appointments']
               if a['malh'] == malh)
    assert row['ghichu'] == 'Khách dị ứng tinh dầu'
    assert row['last_service_change_at'] and row['checked_in_at'] is None

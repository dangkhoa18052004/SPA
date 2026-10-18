"""Acceptance tests for real GPS decisions, ownership, corrections and immutable payroll."""
from datetime import datetime, timedelta, time
from decimal import Decimal

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import CaLam, NhanVien, DichVu, LichHen, CommissionEntry
from app.operations_models import (Branch, BranchMembership, BranchGeoPolicy, AttendanceEvent,
    AttendanceSession, AttendancePeriod, PayrollPeriod, PayrollLine, OperationsAudit)
from app.services import attendance_service as att, payroll_service as pay


@pytest.fixture()
def operations(app, monkeypatch):
    current = datetime(2026, 10, 14, 3, 0, tzinfo=att.UTC)  # 10:00 Saigon
    clock = {'now': current}
    monkeypatch.setattr(att, 'now_utc', lambda: clock['now'])
    app.config.update(ATTENDANCE_ENABLED=True, PAYROLL_V2_ENABLED=True, PAYROLL_V2_CUTOVER_DATE='2026-10-01')
    with app.app_context():
        branch = Branch(name='Bin Spa', address='Cơ sở test')
        other = Branch(name='Cơ sở khác', address='')
        db.session.add_all([branch, other]); db.session.flush()
        staff = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        manager = db.session.get(NhanVien, app.config['TEST_STAFF2_ID'])
        manager.role = 'manager'
        db.session.add_all([BranchMembership(branch_id=branch.id, staff_id=staff.manv),
            BranchMembership(branch_id=branch.id, staff_id=manager.manv, can_manage=True)])
        policy = BranchGeoPolicy(branch_id=branch.id, version=1,
            settings=dict(att.DEFAULT_POLICY, enabled=True), created_by=app.config['TEST_ADMIN_ID'])
        shift = CaLam(ngay=current.astimezone(att.LOCAL).date(), giobatdau=time(9), gioketthuc=time(17),
            sogio=8, hesoluong=1, branch_id=branch.id)
        db.session.add_all([policy, shift]); db.session.flush(); staff.calam.append(shift)
        db.session.commit()
        ids = dict(branch=branch.id, other=other.id, shift=shift.maca, staff=staff.manv, manager=manager.manv,
            manager_headers={'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{manager.manv}')})
    return dict(ids, clock=clock)


def payload(ops, key='check-in-request', **changes):
    return dict(shift_assignment_id=ops['shift'], latitude=att.DEFAULT_POLICY['latitude'],
        longitude=att.DEFAULT_POLICY['longitude'], accuracy=25,
        location_timestamp=ops['clock']['now'].isoformat(), idempotency_key=key, **changes)


def punch(client, headers, ops, action='check-in', key=None, **changes):
    data = payload(ops, key or action + '-request')
    data.update(changes)
    return client.post('/api/attendance/' + action, headers=headers, json=data)


def finish(client, headers, ops):
    response = punch(client, headers, ops)
    assert response.status_code == 200, response.json
    ops['clock']['now'] += timedelta(hours=7)
    response = punch(client, headers, ops, 'check-out')
    assert response.status_code == 200, response.json
    return response.json['session']


def approve(client, headers, session, **changes):
    data = dict(version=session['version'], decision='approve', paid_minutes=480,
        overtime_minutes=0, reason='Đối chiếu công thực tế và duyệt đủ ca')
    data.update(changes)
    return client.post(f"/api/admin/attendance/{session['id']}/approve", headers=headers, json=data)


def close_period(app, client, headers, ops, session):
    response = approve(client, headers, session)
    assert response.status_code == 200, response.json
    work_date = session['work_date']
    ops['clock']['now'] += timedelta(days=1)
    response = client.post('/api/admin/attendance-periods', headers=headers,
        json=dict(branch_id=ops['branch'], from_date=work_date, to_date=work_date))
    period_id = response.json['id']
    response = client.post(f'/api/admin/attendance-periods/{period_id}/lock', headers=headers, json=dict(reason='Đã đối soát toàn bộ ca'))
    assert response.status_code == 200, response.json
    response = client.post('/api/admin/payroll-periods', headers=headers, json=dict(attendance_period_id=period_id))
    assert response.status_code == 201, response.json
    return client.get(f"/api/admin/payroll-periods/{response.json['id']}", headers=headers).json


def test_server_time_ownership_and_idempotency(app, client, staff_auth_headers, operations):
    ops = operations
    response = punch(client, staff_auth_headers, ops, location_timestamp=(ops['clock']['now'] - timedelta(seconds=5)).isoformat())
    assert response.status_code == 200, response.json
    assert response.json['server_at'] == ops['clock']['now'].isoformat()
    request = payload(ops)
    request['location_timestamp'] = (ops['clock']['now'] - timedelta(seconds=5)).isoformat()
    ops['clock']['now'] += timedelta(minutes=2)
    replay = client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request)
    assert replay.json == response.json
    conflict = client.post('/api/attendance/check-in', headers=staff_auth_headers, json={**request, 'accuracy': 20})
    assert conflict.status_code == 409 and conflict.json['code'] == 'idempotency_conflict'
    assert punch(client, staff_auth_headers, ops, key='second-check-in').status_code == 409
    with app.app_context():
        assert AttendanceSession.query.count() == 1
        assert AttendanceEvent.query.count() == 2


@pytest.mark.parametrize('changes,code', [
    ({'latitude': 10.80}, 'outside_geofence'), ({'accuracy': 151}, 'inaccurate_location'),
    ({'location_timestamp': '2026-10-14T02:59:29+00:00'}, 'stale_location'),
    ({'location_timestamp': '2026-10-14T03:00:06+00:00'}, 'stale_location')])
def test_gps_rejections_are_audited_not_payable(app, client, staff_auth_headers, operations, changes, code):
    response = punch(client, staff_auth_headers, operations, **changes)
    assert response.status_code == 409 and response.json['code'] == code
    with app.app_context():
        assert AttendanceSession.query.count() == 0
        assert AttendanceEvent.query.one().verdict == 'rejected'


@pytest.mark.parametrize('changes', [{'latitude': 91}, {'longitude': float('inf')}, {'accuracy': -1},
    {'accuracy': True}, {'shift_assignment_id': True}, {'location_timestamp': '2026-10-14T10:00:00'}, {'staff_id': 3}])
def test_invalid_and_spoofed_payloads(client, staff_auth_headers, operations, changes):
    assert punch(client, staff_auth_headers, operations, **changes).status_code == 400


def test_other_staff_customer_and_disabled_account_cannot_punch(app, client, staff_auth_headers, customer_auth_headers, operations):
    assert punch(client, operations['manager_headers'], operations).status_code == 403
    assert punch(client, customer_auth_headers, operations).status_code == 403
    with app.app_context():
        db.session.get(NhanVien, operations['staff']).trangthai = False
        db.session.commit()
    assert punch(client, staff_auth_headers, operations).status_code == 403


def test_checkout_requires_checkin_and_review(app, client, staff_auth_headers, operations):
    assert punch(client, staff_auth_headers, operations, 'check-out', key='checkout-before-checkin').json['code'] == 'not_checked_in'
    session = finish(client, staff_auth_headers, operations)
    assert session['approval_status'] == 'SUBMITTED' and session['worked_minutes'] == 420
    assert session['paid_minutes'] == 0
    assert punch(client, staff_auth_headers, operations, 'check-out', key='new-checkout-key').json['code'] == 'already_checked_out'


def test_window_and_overnight_shift(app, client, staff_auth_headers, operations):
    ops = operations
    with app.app_context():
        shift = db.session.get(CaLam, ops['shift'])
        shift.giobatdau, shift.gioketthuc = time(22), time(6)
        db.session.commit()
    ops['clock']['now'] = datetime(2026, 10, 14, 14, 29, tzinfo=att.UTC)
    assert punch(client, staff_auth_headers, ops).json['code'] == 'outside_window'
    ops['clock']['now'] = datetime(2026, 10, 14, 15, 0, tzinfo=att.UTC)
    assert punch(client, staff_auth_headers, ops, key='night-check-in').status_code == 200
    ops['clock']['now'] += timedelta(hours=8)
    today = client.get('/api/me/shifts/today', headers=staff_auth_headers).json
    assert len(today['items']) == 1
    response = punch(client, staff_auth_headers, ops, 'check-out')
    assert response.json['session']['worked_minutes'] == 480
    assert response.json['session']['work_date'] == '2026-10-14'


def test_branch_scope_and_stale_review(app, client, staff_auth_headers, admin_auth_headers, operations):
    session = finish(client, staff_auth_headers, operations)
    assert approve(client, staff_auth_headers, session).status_code == 403
    response = approve(client, operations['manager_headers'], session)
    assert response.status_code == 200, response.json
    assert response.json['paid_minutes'] == 480  # late GPS does not silently cut wages
    assert approve(client, admin_auth_headers, session).status_code == 409
    with app.app_context():
        membership = db.session.get(BranchMembership, (operations['branch'], operations['manager']))
        membership.can_manage = False
        db.session.commit()
    assert approve(client, operations['manager_headers'], response.json).status_code == 403
    assert client.get('/api/admin/attendance', headers=operations['manager_headers']).json['total'] == 0


def test_manager_cannot_approve_own_timesheet(app, client, operations):
    ops = operations
    with app.app_context():
        staff = db.session.get(NhanVien, ops['manager'])
        staff.calam.append(db.session.get(CaLam, ops['shift'])); db.session.commit()
    session = finish(client, ops['manager_headers'], ops)
    assert approve(client, ops['manager_headers'], session).status_code == 403


def test_correction_preserves_events_and_requires_separate_review(app, client, staff_auth_headers, admin_auth_headers, operations):
    ops = operations
    assert punch(client, staff_auth_headers, ops).status_code == 200
    response = client.post('/api/me/attendance-adjustments', headers=staff_auth_headers, json=dict(
        shift_assignment_id=ops['shift'], proposed_start='2026-10-14T09:00:00+07:00',
        proposed_end='2026-10-14T17:00:00+07:00', reason='Quên chấm ra, quản lý có mặt đối chiếu'))
    assert response.status_code == 201, response.json
    r = client.post(f"/api/admin/attendance-adjustments/{response.json['id']}/decide", headers=admin_auth_headers,
        json=dict(decision='approve', reason='Đã đối chiếu lịch và xác nhận'))
    assert r.status_code == 200, r.json
    with app.app_context():
        session = AttendanceSession.query.one()
        assert session.approval_status == 'SUBMITTED' and session.worked_minutes == 480
        assert AttendanceEvent.query.count() == 1
        assert AttendanceEvent.query.one().server_at.replace(tzinfo=att.UTC) == ops['clock']['now']
        assert OperationsAudit.query.filter_by(action='attendance_corrected').count() == 1


def test_locked_payroll_is_snapshot_and_employee_private(app, client, staff_auth_headers, admin_auth_headers, operations):
    session = finish(client, staff_auth_headers, operations)
    period = close_period(app, client, admin_auth_headers, operations, session)
    assert Decimal(period['lines'][0]['base']) == 800000
    assert client.get('/api/me/payslips', headers=staff_auth_headers).json['total'] == 0
    # Maker cannot approve own generated payroll.
    assert client.post(f"/api/admin/payroll-periods/{period['id']}/approve", headers=admin_auth_headers,
        json=dict(version=period['version'], reason='Tự kiểm tra')).status_code == 403
    r = client.post(f"/api/admin/payroll-periods/{period['id']}/approve", headers=operations['manager_headers'],
        json=dict(version=period['version'], reason='Đối soát với bảng công và hoa hồng'))
    assert r.status_code == 200, r.json
    r = client.post(f"/api/admin/payroll-periods/{period['id']}/lock", headers=admin_auth_headers,
        json=dict(version=r.json['version'], reason='Chốt kỳ và phát phiếu lương'))
    assert r.status_code == 200, r.json
    slips = client.get('/api/me/payslips', headers=staff_auth_headers).json
    assert slips['total'] == 1 and Decimal(slips['items'][0]['net']) == 800000
    assert client.get(f"/api/me/payslips/{period['lines'][0]['id']}", headers=operations['manager_headers']).status_code == 403
    assert approve(client, admin_auth_headers, session).status_code == 409
    assert client.post(f"/api/admin/payroll-lines/{period['lines'][0]['id']}/adjust", headers=admin_auth_headers,
        json=dict(version=r.json['version'], allowance_delta=10000, reason='Không được sửa bản chốt')).status_code == 409
    with app.app_context():
        staff = db.session.get(NhanVien, operations['staff']); staff.chucvu.dongiagio = 200000
        db.session.commit()
    assert Decimal(client.get('/api/me/payslips', headers=staff_auth_headers).json['items'][0]['net']) == 800000


@pytest.mark.parametrize('kind,night,ot,night_ot,expected', [
    ('weekday', 0, 60, 0, 150000), ('rest_day', 0, 60, 0, 200000), ('holiday', 0, 60, 0, 300000),
    ('weekday', 0, 60, 60, 200000), ('rest_day', 0, 60, 60, 270000), ('holiday', 0, 60, 60, 390000)])
def test_overtime_components(app, client, staff_auth_headers, admin_auth_headers, operations, kind, night, ot, night_ot, expected):
    session = finish(client, staff_auth_headers, operations)
    response = approve(client, admin_auth_headers, session, day_kind=kind,
        night_minutes=night, overtime_minutes=ot, night_overtime_minutes=night_ot)
    assert response.status_code == 200
    with app.app_context():
        base, overtime = pay.amounts(db.session.get(AttendanceSession, session['id']))
        assert base == 800000 and overtime == expected


def test_cannot_close_unresolved_or_current_period(app, client, admin_auth_headers, operations):
    day = '2026-10-14'
    r = client.post('/api/admin/attendance-periods', headers=admin_auth_headers,
        json=dict(branch_id=operations['branch'], from_date=day, to_date=day))
    period_id = r.json['id']
    assert client.post(f'/api/admin/attendance-periods/{period_id}/lock', headers=admin_auth_headers,
        json=dict(reason='Chưa kết thúc ngày')).status_code == 409
    operations['clock']['now'] += timedelta(days=1)
    r = client.post(f'/api/admin/attendance-periods/{period_id}/lock', headers=admin_auth_headers, json=dict(reason='Thiếu công'))
    assert r.status_code == 409 and r.json['code'] == 'unresolved_attendance'
    assert client.post('/api/admin/payroll-periods', headers=admin_auth_headers, json=dict(attendance_period_id=period_id)).status_code == 409


def test_retention_purges_only_expired_coordinates(app, client, staff_auth_headers, operations):
    punch(client, staff_auth_headers, operations)
    operations['clock']['now'] += timedelta(days=91)
    runner = app.test_cli_runner()
    assert runner.invoke(args=['attendance-purge-gps', '--dry-run']).exit_code == 0
    with app.app_context():
        assert AttendanceEvent.query.one().latitude is not None
    assert runner.invoke(args=['attendance-purge-gps']).exit_code == 0
    with app.app_context():
        event = AttendanceEvent.query.one()
        assert event.latitude is None and event.longitude is None and event.verdict == 'accepted'


def test_legacy_shift_mutations_cannot_rewrite_attendance(app, client, staff_auth_headers, admin_auth_headers, operations):
    punch(client, staff_auth_headers, operations)
    shift_id = operations['shift']
    assert client.put(f'/api/admin/shifts/{shift_id}', headers=admin_auth_headers, json=dict(giobatdau='11:00')).status_code == 409
    assert client.delete(f'/api/admin/shifts/{shift_id}', headers=admin_auth_headers).status_code == 409
    assert client.delete('/api/admin/shifts/unassign', headers=admin_auth_headers,
        json=dict(maca=shift_id, manv=operations['staff'])).status_code == 409


def test_rollout_flags_and_policy_version(app, client, staff_auth_headers, admin_auth_headers, operations):
    app.config['ATTENDANCE_ENABLED'] = False
    assert punch(client, staff_auth_headers, operations).status_code == 503
    r = client.post(f"/api/admin/branches/{operations['branch']}/policy", headers=admin_auth_headers,
        json=dict(settings=dict(att.DEFAULT_POLICY, enabled=True, radius_m=120), reason='Điều chỉnh sau khảo sát GPS'))
    assert r.status_code == 201 and r.json['version'] == 2
    with app.app_context():
        assert BranchGeoPolicy.query.count() == 2
    assert client.post(f"/api/admin/branches/{operations['branch']}/policy", headers=operations['manager_headers'],
        json=dict(settings=att.DEFAULT_POLICY, reason='Quản lý không được đổi policy')).status_code == 403


def test_absence_exception_resolves_period_without_fake_gps(app, client, admin_auth_headers, operations):
    operations['clock']['now'] += timedelta(hours=8)
    r = client.post('/api/admin/attendance/exceptions', headers=admin_auth_headers, json=dict(
        staff_id=operations['staff'], shift_assignment_id=operations['shift'], decision='absence', reason='Đã liên hệ xác nhận vắng mặt'))
    assert r.status_code == 201 and r.json['approval_status'] == 'REJECTED'
    with app.app_context():
        assert AttendanceEvent.query.count() == 0
        assert AttendanceSession.query.one().paid_minutes == 0
    operations['clock']['now'] += timedelta(days=1)
    day = '2026-10-14'
    period = client.post('/api/admin/attendance-periods', headers=admin_auth_headers,
        json=dict(branch_id=operations['branch'], from_date=day, to_date=day)).json
    assert client.post(f"/api/admin/attendance-periods/{period['id']}/lock", headers=admin_auth_headers,
        json=dict(reason='Đã giải quyết ca vắng mặt')).status_code == 200


def test_commission_void_after_lock_becomes_next_period_delta(app, client, staff_auth_headers, admin_auth_headers, operations):
    ops = operations
    session = finish(client, staff_auth_headers, ops)
    with app.app_context():
        service = DichVu(tendv='Massage', gia=300000, thoiluong=60)
        appointment = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=ops['staff'],
            ngaygio=datetime(2026, 10, 14, 10), trangthai='completed')
        db.session.add_all([service, appointment]); db.session.flush()
        entry = CommissionEntry(malh=appointment.malh, madv=service.madv, manv=ops['staff'],
            service_name=service.tendv, source_type='regular', base_amount=300000,
            rate_percent=10, amount=30000, earned_at=datetime(2026, 10, 14, 17), status='active')
        db.session.add(entry); db.session.commit(); entry_id = entry.id
    period = close_period(app, client, admin_auth_headers, ops, session)
    assert Decimal(period['lines'][0]['commission']) == 30000
    # Repeated build is idempotent; no second line/claim.
    with app.app_context():
        ap_id = db.session.get(PayrollPeriod, period['id']).attendance_period_id
    assert client.post('/api/admin/payroll-periods', headers=admin_auth_headers, json=dict(attendance_period_id=ap_id)).json['id'] == period['id']
    r = client.post(f"/api/admin/payroll-periods/{period['id']}/approve", headers=ops['manager_headers'], json=dict(version=period['version'], reason='Đã kiểm tra hoa hồng'))
    client.post(f"/api/admin/payroll-periods/{period['id']}/lock", headers=admin_auth_headers, json=dict(version=r.json['version'], reason='Chốt thu nhập kỳ này'))
    with app.app_context():
        db.session.get(CommissionEntry, entry_id).status = 'voided'; db.session.commit()
    assert Decimal(client.get('/api/me/payslips', headers=staff_auth_headers).json['items'][0]['commission']) == 30000
    ops['clock']['now'] += timedelta(days=2)
    ap = client.post('/api/admin/attendance-periods', headers=admin_auth_headers,
        json=dict(branch_id=ops['branch'], from_date='2026-10-15', to_date='2026-10-15')).json
    assert client.post(f"/api/admin/attendance-periods/{ap['id']}/lock", headers=admin_auth_headers, json=dict(reason='Đã đối soát kỳ tiếp')).status_code == 200
    next_period = client.post('/api/admin/payroll-periods', headers=admin_auth_headers, json=dict(attendance_period_id=ap['id'])).json
    detail = client.get(f"/api/admin/payroll-periods/{next_period['id']}", headers=admin_auth_headers).json
    assert Decimal(detail['lines'][0]['commission']) == -30000
    assert detail['lines'][0]['source_snapshot']['commission_deltas'][0]['commission_id'] == entry_id


def test_missing_cutover_prevents_historical_double_pay(app, client, staff_auth_headers, admin_auth_headers, operations):
    session = finish(client, staff_auth_headers, operations)
    period = close_period(app, client, admin_auth_headers, operations, session)
    with app.app_context():
        attendance_period_id = db.session.get(PayrollPeriod, period['id']).attendance_period_id
    app.config['PAYROLL_V2_CUTOVER_DATE'] = '2026-11-01'
    r = client.post('/api/admin/payroll-periods', headers=admin_auth_headers, json=dict(attendance_period_id=attendance_period_id))
    assert r.status_code == 409 and r.json['code'] == 'cutover_required'


def test_night_premium_and_daytime_overtime_in_other_shift(app, client, staff_auth_headers, admin_auth_headers, operations):
    session = finish(client, staff_auth_headers, operations)
    r = approve(client, admin_auth_headers, session, night_minutes=120,
        overtime_minutes=60, night_overtime_minutes=60, daytime_overtime=True)
    assert r.status_code == 200, r.json
    with app.app_context():
        base, overtime = pay.amounts(db.session.get(AttendanceSession, session['id']))
        assert base == 860000 and overtime == 210000


def test_draft_commission_changes_require_explicit_reconciliation(app, client, staff_auth_headers, admin_auth_headers, operations):
    ops = operations
    session = finish(client, staff_auth_headers, ops)
    with app.app_context():
        service = DichVu(tendv='Test massage', gia=300000, thoiluong=60)
        appointment = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=ops['staff'],
            ngaygio=datetime(2026, 10, 14, 10), trangthai='completed')
        db.session.add_all([service, appointment]); db.session.flush()
        entry = CommissionEntry(malh=appointment.malh, madv=service.madv, manv=ops['staff'],
            service_name=service.tendv, source_type='regular', base_amount=300000,
            rate_percent=10, amount=30000, earned_at=datetime(2026, 10, 14, 17), status='active')
        db.session.add(entry); db.session.commit(); entry_id = entry.id
    period = close_period(app, client, admin_auth_headers, ops, session)
    with app.app_context():
        db.session.get(CommissionEntry, entry_id).status = 'voided'; db.session.commit()
    endpoint = f"/api/admin/payroll-periods/{period['id']}"
    detail = client.get(endpoint, headers=admin_auth_headers).json
    assert len(detail['warnings']) == 1
    r = client.post(endpoint + '/approve', headers=ops['manager_headers'],
        json=dict(version=period['version'], reason='Chưa đối soát thay đổi'))
    assert r.status_code == 409 and r.json['code'] == 'commission_changed'
    r = client.post(endpoint + '/reconcile', headers=admin_auth_headers,
        json=dict(version=period['version'], reason='Đối soát trạng thái bị hủy trước chốt'))
    assert r.status_code == 200, r.json
    detail = client.get(endpoint, headers=admin_auth_headers).json
    assert not detail['warnings'] and Decimal(detail['lines'][0]['commission']) == 0
    assert Decimal(detail['lines'][0]['net']) == 800000
    repeat = client.post(endpoint + '/reconcile', headers=admin_auth_headers,
        json=dict(version=detail['version'], reason='Gửi đối soát lại không cộng trùng'))
    assert repeat.json['version'] == detail['version']
    with app.app_context():
        assert OperationsAudit.query.filter_by(action='payroll_commission_reconciled').count() == 1


def test_manager_cannot_use_legacy_paths_to_read_other_branch(app, client, operations):
    ops = operations
    with app.app_context():
        shift = CaLam(ngay=datetime(2026, 10, 14).date(), giobatdau=time(8), gioketthuc=time(12),
            sogio=4, hesoluong=1, branch_id=ops['other'])
        db.session.add(shift); db.session.commit(); other_id = shift.maca
    shifts = client.get('/api/admin/shifts', headers=ops['manager_headers']).json
    assert other_id not in [s['maca'] for s in shifts]
    assert client.get('/api/admin/salaries', headers=ops['manager_headers']).status_code == 403
    assert client.get('/api/admin/salaries/export-pdf', headers=ops['manager_headers']).status_code == 403


def test_shift_cannot_be_moved_into_locked_period(app, client, admin_auth_headers, operations):
    with app.app_context():
        day = datetime(2026, 10, 13).date()
        db.session.add(AttendancePeriod(branch_id=operations['branch'], from_date=day, to_date=day,
            status='LOCKED', locked_by=app.config['TEST_ADMIN_ID']))
        db.session.commit()
    r = client.put(f"/api/admin/shifts/{operations['shift']}", headers=admin_auth_headers, json=dict(ngay='2026-10-13'))
    assert r.status_code == 409, r.json
    with app.app_context():
        assert db.session.get(CaLam, operations['shift']).ngay.isoformat() == '2026-10-14'


def test_disabling_current_policy_stops_new_punch_for_open_snapshot(app, client, staff_auth_headers, admin_auth_headers, operations):
    assert punch(client, staff_auth_headers, operations).status_code == 200
    r = client.post(f"/api/admin/branches/{operations['branch']}/policy", headers=admin_auth_headers,
        json=dict(settings=dict(att.DEFAULT_POLICY, enabled=False), reason='Tạm tắt GPS để khảo sát cửa hàng'))
    assert r.status_code == 201
    response = punch(client, staff_auth_headers, operations, 'check-out')
    assert response.status_code == 409 and response.json['code'] == 'policy_disabled'
    assert response.json['policy_id'] != response.json['active_policy_id']


def test_assigning_gps_shift_does_not_pay_before_review(app, client, admin_auth_headers, operations, monkeypatch):
    from app.models import BangLuongChiTiet
    from app.admin import shift_manage_bp as shifts
    monkeypatch.setattr(shifts, 'send_shift_notification_email', lambda *args: None)
    with app.app_context():
        staff = db.session.get(NhanVien, operations['staff'])
        shift = CaLam(ngay=datetime(2026, 10, 15).date(), giobatdau=time(9), gioketthuc=time(17),
            sogio=8, hesoluong=1, branch_id=operations['branch'])
        db.session.add(shift); db.session.commit(); shift_id = shift.maca
    r = client.post('/api/admin/shifts/assign', headers=admin_auth_headers, json=dict(maca=shift_id, manv=operations['staff']))
    assert r.status_code == 200, r.json
    with app.app_context():
        assert BangLuongChiTiet.query.filter_by(maca=shift_id).count() == 0

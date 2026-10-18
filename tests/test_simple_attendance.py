"""Single-site attendance without assigning branches or staff to shifts."""
from datetime import datetime, timedelta, time
from decimal import Decimal
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import CaLam, NhanVien, nhanvien_calam
from app.operations_models import Branch, BranchGeoPolicy, AttendanceSession, AttendanceEvent, AttendancePeriod
from app.services import attendance_service as att


@pytest.fixture
def simple(app, monkeypatch):
    clock = {'now': datetime(2026, 10, 14, 3, 0, tzinfo=att.UTC)}
    monkeypatch.setattr(att, 'now_utc', lambda: clock['now'])
    with app.app_context():
        branch = Branch(name='Bin Spa', address='')
        db.session.add(branch); db.session.flush()
        shift = CaLam(ngay=clock['now'].astimezone(att.LOCAL).date(), giobatdau=time(9), gioketthuc=time(17), sogio=8, hesoluong=1)
        manager = db.session.get(NhanVien, app.config['TEST_STAFF2_ID'])
        manager.role = 'manager'
        db.session.add(shift)
        db.session.add(BranchGeoPolicy(branch_id=branch.id, version=1,
            settings=dict(att.DEFAULT_POLICY, enabled=True), created_by=app.config['TEST_ADMIN_ID']))
        db.session.commit()
        app.config.update(ATTENDANCE_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True,
            ATTENDANCE_SIMPLE_MODE=True, ATTENDANCE_BRANCH_ID=branch.id)
        yield_data = dict(branch=branch.id, shift=shift.maca, clock=clock,
            manager_headers={'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{manager.manv}')})
    return yield_data


def gps(simple, key='simple-punch-1', **changes):
    return dict(shift_assignment_id=simple['shift'], latitude=att.DEFAULT_POLICY['latitude'],
        longitude=att.DEFAULT_POLICY['longitude'], accuracy=20,
        location_timestamp=simple['clock']['now'].isoformat(), idempotency_key=key, **changes)


@pytest.mark.parametrize('role', ['staff', 'letan', 'manager', 'admin'])
def test_login_keeps_profile_and_old_menu(app, client, simple, role):
    with app.app_context():
        db.session.get(NhanVien, app.config['TEST_STAFF_ID']).role = role
        db.session.commit()
    result = client.post('/api/auth/login/staff', json={'taikhoan': 'staff_test', 'matkhau': 'password'})
    assert result.status_code == 200 and result.json['redirect_url'] == '/admin/profile'
    profile = client.get(result.json['redirect_url'])
    assert profile.status_code == 200
    assert client.get('/employee/attendance').status_code == 200


def test_unassigned_shift_punches_at_fixed_site_without_changing_assignments(app, client, staff_auth_headers, simple):
    listed = client.get('/api/me/shifts/today', headers=staff_auth_headers)
    assert listed.status_code == 200 and len(listed.json['items']) == 1
    assert listed.json['items'][0]['gps_enabled']
    request = gps(simple)
    result = client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request)
    assert result.status_code == 200 and result.json['session']['branch_id'] == simple['branch']
    assert client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request).json == result.json
    simple['clock']['now'] += timedelta(hours=6)
    result = client.post('/api/attendance/check-out', headers=staff_auth_headers, json=gps(simple, 'simple-checkout'))
    assert result.status_code == 200 and result.json['session']['approval_status'] == 'SUBMITTED'
    with app.app_context():
        assert db.session.execute(db.select(db.func.count()).select_from(nhanvien_calam)).scalar_one() == 0
        assert db.session.get(CaLam, simple['shift']).branch_id is None
        assert AttendanceSession.query.count() == 1 and AttendanceEvent.query.count() == 2


def test_failed_gps_manual_checkin_and_checkout_requests(app, client, staff_auth_headers, simple):
    request = gps(simple); request['latitude'] += .01
    assert client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request).status_code == 409
    requested = client.post('/api/me/attendance-adjustments', headers=staff_auth_headers, json=dict(
        shift_assignment_id=simple['shift'], request_kind='check-in', proposed_start=simple['clock']['now'].isoformat(), reason='GPS không chính xác'))
    assert requested.status_code == 201 and requested.json['proposed_end'] is None
    request_id = requested.json['id']
    assert client.post(f'/api/admin/attendance-adjustments/{request_id}/decide', headers=staff_auth_headers,
        json=dict(decision='approve', reason='Tự duyệt')).status_code == 403
    pending = client.get('/api/admin/attendance-adjustments', headers=simple['manager_headers'])
    assert pending.status_code == 200 and pending.json['total'] == 1
    approved = client.post(f'/api/admin/attendance-adjustments/{request_id}/decide', headers=simple['manager_headers'],
        json=dict(decision='approve', reason='Đã thấy nhân viên tại cơ sở'))
    assert approved.status_code == 200
    history = client.get('/api/me/attendance', headers=staff_auth_headers).json['items']
    assert len(history) == 1 and history[0]['actual_end'] is None and history[0]['approval_status'] == 'OPEN'
    simple['clock']['now'] += timedelta(hours=1)
    requested = client.post('/api/me/attendance-adjustments', headers=staff_auth_headers, json=dict(
        shift_assignment_id=simple['shift'], request_kind='check-out', proposed_end=simple['clock']['now'].isoformat(), reason='Thiết bị không lấy được GPS'))
    assert requested.status_code == 201
    approved = client.post(f"/api/admin/attendance-adjustments/{requested.json['id']}/decide", headers=simple['manager_headers'],
        json=dict(decision='approve', reason='Đối chiếu giờ ra thực tế'))
    assert approved.status_code == 200
    history = client.get('/api/me/attendance', headers=staff_auth_headers).json['items']
    assert history[0]['actual_end'] and history[0]['worked_minutes'] == 60
    with app.app_context():
        assert AttendanceEvent.query.filter_by(verdict='accepted').count() == 0  # Manual approval is not a GPS success.


def test_manual_checkin_can_use_normal_gps_checkout(client, staff_auth_headers, simple):
    requested = client.post('/api/me/attendance-adjustments', headers=staff_auth_headers, json=dict(
        shift_assignment_id=simple['shift'], request_kind='check-in', proposed_start=simple['clock']['now'].isoformat(), reason='Chưa cấp quyền vị trí'))
    result = client.post(f"/api/admin/attendance-adjustments/{requested.json['id']}/decide", headers=simple['manager_headers'],
        json=dict(decision='approve', reason='Đã xác nhận trực tiếp'))
    assert result.status_code == 200
    simple['clock']['now'] += timedelta(hours=1)
    assert client.post('/api/attendance/check-out', headers=staff_auth_headers, json=gps(simple)).status_code == 200


def test_pending_request_cannot_overwrite_new_gps_punch(client, staff_auth_headers, simple):
    requested = client.post('/api/me/attendance-adjustments', headers=staff_auth_headers, json=dict(
        shift_assignment_id=simple['shift'], request_kind='check-in', proposed_start=simple['clock']['now'].isoformat(), reason='GPS lỗi tạm thời'))
    assert client.post('/api/attendance/check-in', headers=staff_auth_headers, json=gps(simple)).status_code == 200
    assert client.post(f"/api/admin/attendance-adjustments/{requested.json['id']}/decide", headers=simple['manager_headers'],
        json=dict(decision='approve', reason='Duyệt yêu cầu cũ')).status_code == 409


def test_cannot_checkin_multiple_open_shifts(app, client, staff_auth_headers, simple):
    assert client.post('/api/attendance/check-in', headers=staff_auth_headers, json=gps(simple)).status_code == 200
    with app.app_context():
        other = CaLam(ngay=simple['clock']['now'].date(), giobatdau=time(9), gioketthuc=time(18), sogio=9)
        db.session.add(other); db.session.commit(); other_id = other.maca
    request = gps(simple, 'another-shift-punch'); request['shift_assignment_id'] = other_id
    result = client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request)
    assert result.status_code == 409 and result.json['code'] == 'open_session'


def test_manager_creates_shift_without_branch_and_locked_dates_stay_protected(app, client, simple):
    result = client.post('/api/admin/shifts', headers=simple['manager_headers'], json=dict(
        ngay='2026-10-15', giobatdau='09:00', gioketthuc='17:00'))
    assert result.status_code == 201
    with app.app_context():
        db.session.add(AttendancePeriod(branch_id=simple['branch'], from_date=datetime(2026, 10, 16).date(),
            to_date=datetime(2026, 10, 16).date(), status='LOCKED'))
        db.session.commit()
    result = client.put(f"/api/admin/shifts/{simple['shift']}", headers=simple['manager_headers'], json=dict(ngay='2026-10-16'))
    assert result.status_code == 409
    assert client.get('/api/admin/shifts', headers=simple['manager_headers']).status_code == 200


@pytest.mark.parametrize('change', [dict(proposed_start='2026-10-14T04:00:00+00:00'),
    dict(proposed_start='2026-10-13T12:00:00+00:00'), dict(request_kind='unknown')])
def test_invalid_requests_do_not_create_sessions(client, staff_auth_headers, simple, change):
    request = dict(shift_assignment_id=simple['shift'], request_kind='check-in',
        proposed_start=simple['clock']['now'].isoformat(), reason='Không chấm được')
    request.update(change)
    assert client.post('/api/me/attendance-adjustments', headers=staff_auth_headers, json=request).status_code == 400


def test_fixed_site_does_not_allow_other_location_or_coordinate_change(app, client, staff_auth_headers, admin_auth_headers, simple):
    with app.app_context():
        foreign = Branch(name='Other', address='')
        db.session.add(foreign); db.session.flush()
        shift = CaLam(ngay=simple['clock']['now'].date(), giobatdau=time(9), gioketthuc=time(17), sogio=8, branch_id=foreign.id)
        db.session.add(shift); db.session.commit(); shift_id = shift.maca
    assert len(client.get('/api/me/shifts/today', headers=staff_auth_headers).json['items']) == 1
    request = gps(simple); request['shift_assignment_id'] = shift_id
    assert client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request).status_code == 403
    result = client.post(f"/api/admin/branches/{simple['branch']}/policy", headers=admin_auth_headers,
        json=dict(settings=dict(att.DEFAULT_POLICY, latitude=11), reason='Đổi địa điểm'))
    assert result.status_code == 400


def test_simple_initialization_does_not_require_memberships(app):
    result = app.test_cli_runner().invoke(args=['operations-init-branch', '--admin-id', str(app.config['TEST_ADMIN_ID']), '--simple'])
    assert result.exit_code == 0, result.output
    with app.app_context():
        branch = Branch.query.one()
        policy = att.policy_for(branch.id)
        assert policy.settings['enabled'] and policy.settings['latitude'] == 10.78686228650495
        assert policy.settings['longitude'] == 106.5794979291708
        assert app.config['ATTENDANCE_BRANCH_ID'] == branch.id


def test_radius_500_accepts_400m_but_still_rejects_poor_accuracy(client, staff_auth_headers, simple):
    request = gps(simple); request['latitude'] += .0036
    request['accuracy'] = 151
    result = client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request)
    assert result.status_code == 409 and result.json['code'] == 'inaccurate_location'
    request['accuracy'] = 20; request['idempotency_key'] = 'radius-500-accepted'
    result = client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request)
    assert result.status_code == 200 and 390 < result.json['distance_m'] < 410


@pytest.mark.parametrize('accuracy', [103, 112, 127, 150])
def test_accuracy_within_150m_can_punch(client, staff_auth_headers, simple, accuracy):
    request = gps(simple); request['accuracy'] = accuracy
    result = client.post('/api/attendance/check-in', headers=staff_auth_headers, json=request)
    assert result.status_code == 200 and result.json['session']['approval_status'] == 'OPEN'


def test_pending_hours_preview_and_payroll_ignore_unused_legacy_assignments(app, client, staff_auth_headers, admin_auth_headers, simple):
    assert client.post('/api/attendance/check-in', headers=staff_auth_headers, json=gps(simple)).status_code == 200
    simple['clock']['now'] += timedelta(hours=6)
    result = client.post('/api/attendance/check-out', headers=staff_auth_headers, json=gps(simple, 'summary-checkout'))
    session = result.json['session']
    assert result.status_code == 200
    with app.app_context():
        old_shift = CaLam(ngay=simple['clock']['now'].date(), giobatdau=time(8), gioketthuc=time(12), sogio=4, branch_id=simple['branch'])
        db.session.add(old_shift)
        db.session.get(NhanVien, app.config['TEST_STAFF2_ID']).calam.append(old_shift)
        app.config.update(PAYROLL_V2_ENABLED=True, PAYROLL_V2_CUTOVER_DATE='2026-10-01')
        db.session.commit()
    summary = client.get('/api/me/income-summary', headers=staff_auth_headers).json
    assert summary['worked_minutes'] == summary['pending_minutes'] == 360
    assert summary['approved_minutes'] == 0 and Decimal(summary['pending_estimate']) == 600000
    assert client.get('/api/me/income-summary', headers=admin_auth_headers).json['worked_minutes'] == 0
    simple['clock']['now'] += timedelta(days=1)
    result = client.post('/api/admin/attendance-periods', headers=simple['manager_headers'],
        json=dict(branch_id=simple['branch'], from_date='2026-10-01', to_date='2026-10-14'))
    assert result.status_code == 201
    period_id = result.json['id']
    readiness = client.get('/api/admin/attendance-periods', headers=simple['manager_headers']).json['items'][0]['readiness']
    assert readiness['submitted'] == 1 and readiness['missing'] == 0 and not readiness['can_lock']
    result = client.post(f'/api/admin/attendance-periods/{period_id}/lock', headers=simple['manager_headers'], json=dict(reason='Kiểm tra công'))
    assert result.status_code == 409 and result.json['code'] == 'unresolved_attendance'
    result = client.post(f"/api/admin/attendance/{session['id']}/approve", headers=simple['manager_headers'],
        json=dict(version=session['version'], decision='approve', paid_minutes=360, reason='Đối chiếu 6 giờ thực tế'))
    assert result.status_code == 200
    summary = client.get('/api/me/income-summary', headers=staff_auth_headers).json
    assert summary['approved_minutes'] == 360 and summary['pending_minutes'] == 0
    assert Decimal(summary['approved_earnings']) == 600000
    assert client.post(f'/api/admin/attendance-periods/{period_id}/lock', headers=simple['manager_headers'],
        json=dict(reason='Đã duyệt toàn bộ công đã phát sinh')).status_code == 200
    result = client.post('/api/admin/payroll-periods', headers=simple['manager_headers'], json=dict(attendance_period_id=period_id))
    assert result.status_code == 201
    payroll_id = result.json['id']
    detail = client.get(f'/api/admin/payroll-periods/{payroll_id}', headers=simple['manager_headers']).json
    assert len(detail['lines']) == 1 and Decimal(detail['lines'][0]['base']) == 600000
    assert client.post(f'/api/admin/payroll-periods/{payroll_id}/approve', headers=admin_auth_headers,
        json=dict(version=detail['version'], reason='Người khác đối chiếu bảng lương')).status_code == 200
    detail = client.get(f'/api/admin/payroll-periods/{payroll_id}', headers=simple['manager_headers']).json
    assert client.post(f'/api/admin/payroll-periods/{payroll_id}/lock', headers=simple['manager_headers'],
        json=dict(version=detail['version'], reason='Chốt phiếu lương kiểm thử')).status_code == 200
    assert client.get('/api/me/payslips', headers=staff_auth_headers).json['total'] == 1

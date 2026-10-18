"""MFA is a prerequisite, never a substitute for current DB permissions."""
import base64
from datetime import datetime, timedelta
import json
import pytest
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import NhanVien, ChucVu, StaffMFA, StaffStepUp, StaffRecoveryCode, StaffSecurityAudit
from app.services import staff_security_service as security
from test_attendance_payroll import operations, finish, close_period  # noqa: F401


@pytest.fixture
def secured(app, monkeypatch):
    app.config.update(STAFF_SECURITY_ENABLED=True, STAFF_MFA_ENCRYPTION_KEY=Fernet.generate_key().decode())
    clock = [datetime(2026, 10, 15, 8)]
    monkeypatch.setattr(security, 'now', lambda: clock[0])
    return clock


def otp(secret, clock):
    import calendar
    return security.otp_at(secret, calendar.timegm(clock.utctimetuple()) // 30)


def enroll(client, headers, clock):
    started = client.post('/api/me/security/enroll', json={'password': 'password'}, headers=headers)
    assert started.status_code == 200, started.json
    secret = started.json['secret']
    result = client.post('/api/me/security/confirm', json={'code': otp(secret, clock[0])}, headers=headers)
    assert result.status_code == 200, result.json
    return secret, result.json['recovery_codes']


@pytest.mark.parametrize('stamp,expected', [(59, '94287082'), (1111111109, '07081804'),
    (1111111111, '14050471'), (1234567890, '89005924'), (2000000000, '69279037'), (20000000000, '65353130')])
def test_rfc_6238_sha1_vectors(stamp, expected):
    secret = base64.b32encode(b'12345678901234567890').decode()
    assert security.otp_at(secret, stamp // 30, digits=8) == expected


def test_flag_off_preserves_login_and_hides_security(client, admin_auth_headers):
    assert client.get('/api/me/security', headers=admin_auth_headers).status_code == 404
    assert client.get('/admin/security').status_code == 404
    assert client.post('/api/auth/login/staff', json={'taikhoan': 'admin_test', 'matkhau': 'password'}).json['access_token']


def test_setup_requires_password_and_confirmed_factor(secured, app, client, admin_auth_headers):
    assert client.post('/api/me/security/enroll', json={'password': 'wrong'}, headers=admin_auth_headers).status_code == 400
    initial = client.post('/api/me/security/enroll', json={'password': 'password'}, headers=admin_auth_headers)
    secret = initial.json['secret']
    assert initial.headers['Cache-Control'].endswith('no-store')
    assert initial.json['provisioning_uri'].startswith('otpauth://totp/Bin%20Spa%3A')
    state = client.get('/api/me/security', headers=admin_auth_headers).json
    assert not state['enabled'] and state['verified_until'] is None
    assert 'secret' not in json.dumps(state) and 'provisioning_uri' not in state
    with app.app_context():
        stored = StaffMFA.query.one()
        assert stored.secret_ciphertext is None and secret not in stored.pending_ciphertext
    assert client.post('/api/me/security/confirm', json={'code': 'wrong'}, headers=admin_auth_headers).status_code == 400
    good = client.post('/api/me/security/confirm', json={'code': otp(secret, secured[0])}, headers=admin_auth_headers)
    assert len(good.json['recovery_codes']) == 10 and len(set(good.json['recovery_codes'])) == 10
    assert client.get('/api/me/security', headers=admin_auth_headers).json['enabled']
    with app.app_context():
        assert StaffRecoveryCode.query.count() == 10 and StaffStepUp.query.count() == 1
        assert all(c.replace('-', '') not in r.code_hash for c in good.json['recovery_codes'] for r in StaffRecoveryCode.query)
        actions = [r.action for r in StaffSecurityAudit.query]
        assert 'enrollment_started' in actions and 'mfa_enabled' in actions
        assert 'password' not in json.dumps(actions) and secret not in json.dumps(actions)


def test_pending_setup_expires_and_is_replaced(secured, client, admin_auth_headers):
    old = client.post('/api/me/security/enroll', json={'password': 'password'}, headers=admin_auth_headers).json['secret']
    secured[0] += timedelta(minutes=11)
    assert client.post('/api/me/security/confirm', json={'code': otp(old, secured[0])}, headers=admin_auth_headers).status_code == 409
    new, _ = enroll(client, admin_auth_headers, secured)
    assert new != old
    assert client.post('/api/me/security/enroll', json={'password': 'password'}, headers=admin_auth_headers).status_code == 409


@pytest.mark.parametrize('path,method', [('/api/admin/attendance-periods/999/lock', 'POST'),
    ('/api/admin/payroll-periods/999/approve', 'POST'), ('/api/admin/payroll-periods/999/lock', 'POST'),
    ('/api/admin/payroll-lines/999/adjust', 'POST'), ('/api/admin/payroll-periods/999/reconcile', 'POST'),
    ('/api/admin/payroll-periods', 'POST'), ('/api/admin/branches/999/policy', 'POST'),
    ('/api/admin/branches/999/members/1', 'PUT'), ('/api/admin/payroll-periods/999/export.csv', 'GET'),
    ('/api/admin/staff/add', 'POST'), ('/api/admin/staff/999', 'PUT'), ('/api/admin/staff/999', 'DELETE'),
    ('/api/admin/roles', 'POST'), ('/api/admin/roles/999', 'PUT'), ('/api/admin/roles/999', 'DELETE')])
def test_sensitive_routes_require_enrollment_before_any_mutation(secured, client, admin_auth_headers, path, method):
    result = client.open(path, method=method, json={}, headers=admin_auth_headers)
    assert result.status_code == 403 and result.json['code'] == 'mfa_enrollment_required', (path, result.json)


def test_elevation_bound_to_jwt_current_password_role_and_expiry(secured, app, client, admin_auth_headers):
    secret, _ = enroll(client, admin_auth_headers, secured)
    assert client.get('/api/me/security', headers=admin_auth_headers).json['verified_until']
    with app.app_context():
        other = {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{app.config["TEST_ADMIN_ID"]}')}
    assert client.get('/api/me/security', headers=other).json['verified_until'] is None
    # A used OTP cannot elevate another token, even inside the skew window.
    result = client.post('/api/me/security/verify', json={'code': otp(secret, secured[0])}, headers=other)
    assert result.status_code == 400 and result.json['code'] == 'code_invalid'
    secured[0] += timedelta(seconds=30)
    assert client.post('/api/me/security/verify', json={'code': otp(secret, secured[0])}, headers=other).status_code == 200
    with app.app_context():
        actor = db.session.get(NhanVien, app.config['TEST_ADMIN_ID']); actor.role = 'manager'; db.session.commit()
    assert client.get('/api/me/security', headers=other).json['verified_until'] is None
    secured[0] += timedelta(seconds=30)
    assert client.post('/api/me/security/verify', json={'code': otp(secret, secured[0])}, headers=other).status_code == 200
    with app.app_context():
        actor = db.session.get(NhanVien, app.config['TEST_ADMIN_ID']); actor.matkhau += 'changed'; db.session.commit()
    assert client.get('/api/me/security', headers=other).json['verified_until'] is None
    secured[0] += timedelta(seconds=30)
    assert client.post('/api/me/security/verify', json={'code': otp(secret, secured[0])}, headers=other).status_code == 200
    secured[0] += timedelta(seconds=601)
    assert client.get('/api/me/security', headers=other).json['verified_until'] is None


def test_expired_elevation_rejects_before_business_validation(secured, client, admin_auth_headers):
    enroll(client, admin_auth_headers, secured)
    client.post('/api/me/security/lock', headers=admin_auth_headers)
    response = client.post('/api/admin/payroll-periods/999/lock', headers=admin_auth_headers, json={})
    assert response.status_code == 403 and response.json['code'] == 'mfa_required'


def test_logout_revokes_elevation_for_that_token(secured, client, admin_auth_headers):
    enroll(client, admin_auth_headers, secured)
    assert client.post('/api/auth/logout', headers=admin_auth_headers).status_code == 200
    assert client.get('/api/me/security', headers=admin_auth_headers).json['verified_until'] is None
    assert client.post('/api/auth/logout', headers={'Authorization': 'Bearer invalid'}).status_code == 200


def test_access_changes_permanently_revoke_even_when_restored(secured, app, client, admin_auth_headers, staff_auth_headers):
    _, codes = enroll(client, staff_auth_headers, secured)
    enroll(client, admin_auth_headers, secured)
    path = f'/api/admin/staff/{app.config["TEST_STAFF_ID"]}'
    assert client.put(path, data={'role': 'manager'}, headers=admin_auth_headers).status_code == 200
    assert client.put(path, data={'role': 'staff'}, headers=admin_auth_headers).status_code == 200
    assert client.get('/api/me/security', headers=staff_auth_headers).json['verified_until'] is None
    assert client.post('/api/me/security/verify', json={'code': codes[0]}, headers=staff_auth_headers).status_code == 200
    assert client.delete(path, headers=admin_auth_headers).status_code == 200
    assert client.put(path, data={'trangthai': 'true'}, headers=admin_auth_headers).status_code == 200
    assert client.get('/api/me/security', headers=staff_auth_headers).json['verified_until'] is None
    assert client.post('/api/me/security/verify', json={'code': codes[1]}, headers=staff_auth_headers).status_code == 200
    result = client.put('/api/profile/change-password', json={'matkhau_cu': 'password', 'matkhau_moi': 'new-password'}, headers=staff_auth_headers)
    assert result.status_code == 200
    with app.app_context(): assert StaffStepUp.query.filter_by(staff_id=app.config['TEST_STAFF_ID']).count() == 0


def test_role_rate_write_happens_only_after_proof_and_stops_after_expiry(secured, app, client, admin_auth_headers):
    with app.app_context():
        role = ChucVu.query.filter_by(tencv='Kỹ thuật viên').one(); role_id = role.macv
    path = f'/api/admin/roles/{role_id}'
    assert client.put(path, json={'dongiagio': 120000}, headers=admin_auth_headers).status_code == 403
    with app.app_context(): assert db.session.get(ChucVu, role_id).dongiagio == 100000
    enroll(client, admin_auth_headers, secured)
    assert client.put(path, json={'dongiagio': 120000}, headers=admin_auth_headers).status_code == 200
    secured[0] += timedelta(minutes=11)
    assert client.put(path, json={'dongiagio': 990000}, headers=admin_auth_headers).status_code == 403
    with app.app_context(): assert db.session.get(ChucVu, role_id).dongiagio == 120000


def test_recovery_codes_single_use_and_scoped_to_actor(secured, client, admin_auth_headers, staff_auth_headers):
    _, codes = enroll(client, admin_auth_headers, secured)
    enroll(client, staff_auth_headers, secured)
    assert client.post('/api/me/security/verify', json={'code': codes[0]}, headers=staff_auth_headers).status_code == 400
    assert client.post('/api/me/security/verify', json={'code': codes[0]}, headers=admin_auth_headers).status_code == 200
    assert client.post('/api/me/security/verify', json={'code': codes[0]}, headers=admin_auth_headers).status_code == 400
    assert client.get('/api/me/security', headers=admin_auth_headers).json['recovery_codes_remaining'] == 9


def test_disable_and_regenerate_require_password_and_new_proof(secured, app, client, admin_auth_headers):
    secret, codes = enroll(client, admin_auth_headers, secured)
    assert client.post('/api/me/security/disable', json={'password': 'wrong', 'code': codes[0]}, headers=admin_auth_headers).status_code == 400
    regenerated = client.post('/api/me/security/recovery-codes', json={'password': 'password', 'code': codes[0]}, headers=admin_auth_headers)
    assert regenerated.status_code == 200
    assert client.post('/api/me/security/verify', json={'code': codes[1]}, headers=admin_auth_headers).status_code == 400
    new = regenerated.json['recovery_codes']
    disabled = client.post('/api/me/security/disable', json={'password': 'password', 'code': new[0]}, headers=admin_auth_headers)
    assert disabled.status_code == 200
    assert not client.get('/api/me/security', headers=admin_auth_headers).json['enabled']
    with app.app_context():
        assert StaffStepUp.query.count() == StaffRecoveryCode.query.count() == 0
        assert StaffMFA.query.one().secret_ciphertext is None
    replacement, _ = enroll(client, admin_auth_headers, secured)
    assert replacement != secret


def test_customer_inactive_and_role_guards_cannot_be_bypassed(secured, app, client, customer_auth_headers, staff_auth_headers, admin_auth_headers):
    assert client.get('/api/me/security', headers=customer_auth_headers).status_code == 403
    enroll(client, staff_auth_headers, secured)
    denied = client.put('/api/admin/roles/999', headers=staff_auth_headers, json={})
    assert denied.status_code == 403 and denied.json.get('code') not in ('mfa_required', 'mfa_enrollment_required')
    with app.app_context():
        actor = db.session.get(NhanVien, app.config['TEST_ADMIN_ID']); actor.trangthai = False; db.session.commit()
    assert client.post('/api/me/security/enroll', headers=admin_auth_headers, json={'password': 'password'}).status_code == 403


def test_verification_throttled_by_actor_across_peer_addresses(secured, client, admin_auth_headers):
    for n in range(10):
        r = client.post('/api/me/security/verify', json={'code': 'wrong'}, headers=admin_auth_headers,
                        environ_overrides={'REMOTE_ADDR': f'192.0.2.{n}'})
        assert r.status_code == 403
    limited = client.post('/api/me/security/verify', json={'code': 'wrong'}, headers=admin_auth_headers)
    assert limited.status_code == 429 and int(limited.headers['Retry-After']) > 0


def test_cipher_failure_is_closed_and_response_does_not_expose_secrets(secured, app, client, admin_auth_headers):
    secret, _ = enroll(client, admin_auth_headers, secured)
    app.config['STAFF_MFA_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    failed = client.post('/api/me/security/verify', json={'code': otp(secret, secured[0])}, headers=admin_auth_headers)
    assert failed.status_code == 503 and secret not in failed.get_data(as_text=True)


def test_missing_key_rejected_before_application_starts():
    with pytest.raises(RuntimeError, match='STAFF_MFA_ENCRYPTION_KEY'):
        create_app(dict(APP_ENV='testing', STAFF_SECURITY_ENABLED=True, STAFF_MFA_ENCRYPTION_KEY='bad'))


def test_cross_origin_and_non_object_requests_rejected(secured, client, admin_auth_headers):
    assert client.post('/api/me/security/enroll', headers={**admin_auth_headers, 'Origin': 'https://bad.example'}, json={}).status_code == 403
    assert client.post('/api/me/security/enroll', headers=admin_auth_headers, json=[]).status_code == 400


def test_prune_removes_only_expired_elevation_and_pending_setup(secured, app, client, admin_auth_headers):
    enroll(client, admin_auth_headers, secured)
    secured[0] += timedelta(minutes=11)
    result = app.test_cli_runner().invoke(args=['staff-security', 'prune', '--dry-run'])
    assert result.exit_code == 0 and 'Expired elevations: 1' in result.output
    assert app.test_cli_runner().invoke(args=['staff-security', 'prune']).exit_code == 0
    with app.app_context():
        assert StaffStepUp.query.count() == 0 and StaffMFA.query.one().enabled_at and StaffRecoveryCode.query.count() == 10


def test_real_attendance_payroll_flow_and_branch_scope_with_mfa(secured, app, client, admin_auth_headers, staff_auth_headers, operations):
    enroll(client, admin_auth_headers, secured)
    session = finish(client, staff_auth_headers, operations)
    payroll = close_period(app, client, admin_auth_headers, operations, session)
    assert payroll['status'] == 'DRAFT' and payroll['lines'][0]['paid_minutes'] > 0
    # An elevated manager still cannot edit another branch or admin-only policy.
    manager_headers = operations['manager_headers']
    enroll(client, manager_headers, secured)
    result = client.post('/api/admin/attendance-periods', headers=manager_headers,
        json=dict(branch_id=operations['other'], from_date='2026-10-14', to_date='2026-10-14'))
    assert result.status_code == 403
    result = client.post(f'/api/admin/branches/{operations["branch"]}/policy', headers=manager_headers, json={})
    assert result.status_code == 403

"""BI receipt time, customer cohorts, immutable payroll scope and operating visibility."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import text
from app.extensions import db
from app.models import (KhachHang, NhanVien, DichVu, LichHen, HoaDon, ThanhToan, CaLam,
    Branch, BranchMembership, BranchGeoPolicy, AttendanceSession, AttendancePeriod, PayrollPeriod, PayrollLine,
    CommissionEntry, ReportExportAudit, AppointmentOutcome, AuthRateBucket, WorkerHeartbeat, NotificationJob)
from app.services import bi_service, runtime_service, package_service as ps, appointment_service

RANGE = 'from=2026-10-01&to=2026-10-15'


@pytest.fixture
def bi_records(app):
    app.config.update(BI_REPORTS_ENABLED=True, OBSERVABILITY_ENABLED=True)
    with app.app_context():
        admin, sid = app.config['TEST_ADMIN_ID'], app.config['TEST_STAFF_ID']
        manager = db.session.get(NhanVien, app.config['TEST_STAFF2_ID']); manager.role = 'manager'
        b1, b2 = Branch(name='Bin Spa'), Branch(name='Cơ sở khác')
        new = KhachHang(hoten='Khách mới', taikhoan='bi-new', matkhau='hash', trangthai='active')
        old = KhachHang(hoten='Khách kỳ trước', taikhoan='bi-old', matkhau='hash', trangthai='active')
        svc = DichVu(tendv='Massage kiểm thử', gia=100000, thoiluong=30, active=True)
        db.session.add_all([b1, b2, new, old, svc]); db.session.flush()
        db.session.add(BranchMembership(branch_id=b1.id, staff_id=manager.manv, can_manage=True))
        customer = app.config['TEST_CUSTOMER_ID']
        apts = []
        for cid, stamp, state in [(customer, '2026-09-20', 'completed'), (old.makh, '2026-09-22', 'completed'),
            (customer, '2026-10-10', 'completed'), (customer, '2026-10-11', 'completed'), (new.makh, '2026-10-12', 'completed'),
            (old.makh, '2026-10-13', 'cancelled'), (new.makh, '2026-10-14', 'cancelled')]:
            apt = LichHen(makh=cid, manv=sid, ngaygio=datetime.fromisoformat(stamp + 'T10:00'), trangthai=state)
            db.session.add(apt); db.session.flush(); apts.append(apt)
        db.session.add(AppointmentOutcome(malh=apts[-2].malh, outcome='no_show'))
        invoice = HoaDon(makh=customer, manv=sid, tongtien=900000, trangthai='Chưa thanh toán')
        db.session.add(invoice); db.session.flush()
        for stamp, amount in [('2026-10-01T00:00', 100000), ('2026-10-15T23:59:59', 200000), ('2026-10-16T00:00', 300000)]:
            db.session.add(ThanhToan(mahd=invoice.mahd, sotien=amount, ngaythanhtoan=datetime.fromisoformat(stamp)))
        db.session.add(CommissionEntry(malh=apts[2].malh, madv=svc.madv, manv=sid, service_name=svc.tendv,
            source_type='regular', base_amount=100000, amount=30000, rate_percent=30, status='active', earned_at=datetime(2026, 10, 10)))
        for branch in (b1, b2):
            policy = BranchGeoPolicy(branch_id=branch.id, version=1, created_by=admin, settings={})
            db.session.add(policy); db.session.flush()
            for offset, state, minutes in [(0, 'APPROVED', 480 if branch == b1 else 360), (1, 'SUBMITTED', 240)]:
                start = datetime(2026, 10, 13 + offset, 2, tzinfo=timezone.utc)
                shift = CaLam(ngay=start.date(), giobatdau=time(9), gioketthuc=time(17), branch_id=branch.id)
                db.session.add(shift); db.session.flush()
                db.session.add(AttendanceSession(staff_id=sid, shift_id=shift.maca, branch_id=branch.id, work_date=start.date(),
                    planned_start=start, planned_end=start + timedelta(hours=8), actual_start=start, actual_end=start + timedelta(minutes=minutes),
                    policy_id=policy.id, worked_minutes=minutes, paid_minutes=minutes, overtime_minutes=30 if state == 'APPROVED' else 0,
                    hourly_rate=100000, shift_multiplier=1, approval_status=state))
            ap = AttendancePeriod(branch_id=branch.id, from_date=date(2026, 10, 6), to_date=date(2026, 10, 14), status='LOCKED')
            db.session.add(ap); db.session.flush()
            pp = PayrollPeriod(attendance_period_id=ap.id, branch_id=branch.id, from_date=ap.from_date, to_date=ap.to_date, status='LOCKED', created_by=admin, policy_snapshot={})
            db.session.add(pp); db.session.flush()
            db.session.add(PayrollLine(period_id=pp.id, staff_id=sid, paid_minutes=480, base=800000, overtime=50000,
                commission=30000, allowance=0, deduction=0, net=880000, source_snapshot={}))
        partial = AttendancePeriod(branch_id=b1.id, from_date=date(2026, 9, 26), to_date=date(2026, 10, 5), status='LOCKED')
        db.session.add(partial); db.session.flush()
        db.session.add(PayrollPeriod(attendance_period_id=partial.id, branch_id=b1.id, from_date=partial.from_date, to_date=partial.to_date, status='LOCKED', created_by=admin, policy_snapshot={}))
        db.session.commit()
        package = ps.save_package(dict(tengoi='Gói kiểm thử BI', giagoi=250000, items=[dict(madv=svc.madv, total_sessions=3)]))
        purchase = ps.create_purchase(package.magoi, customer, 'cash')
        ps.confirm_purchase(purchase.id, 250000, method='cash')
        purchase.paid_at = datetime(2026, 10, 9)
        db.session.commit()
        return dict(branch=b1.id, other_branch=b2.id, staff=sid,
            manager_headers={'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{manager.manv}')})


def test_bi_receipts_cohorts_and_no_show_are_not_inferred_from_cancelled(app, client, bi_records, admin_auth_headers):
    data = client.get('/api/admin/bi/report?' + RANGE, headers=admin_auth_headers)
    assert data.status_code == 200, data.json
    b = data.json['business']
    assert b['revenue'] == dict(total='550000.00', service='300000.00', package='250000.00')
    assert b['appointments']['total'] == 5
    assert b['appointments']['no_show_recorded'] == 1 and b['appointments']['cancelled_without_outcome'] == 1
    assert b['customers']['completed'] == 2 and b['customers']['returning_rate'] == 50
    assert b['customers']['cohort'] == 2 and b['customers']['retention_rate'] == 50
    assert b['earned_commission'] == '30000.00'
    w = data.json['workforce']
    assert w['approved_minutes'] == 840 and w['overtime_minutes'] == 60
    assert w['locked_payroll'] == '1760000.00' and w['excluded_partial_periods'] == 1


def test_manager_branch_filter_never_leaks_global_legacy_finances(client, bi_records):
    data = client.get('/api/admin/bi/report?' + RANGE, headers=bi_records['manager_headers']).json
    assert data['business'] is None and data['business_scope'] == 'unavailable'
    assert data['branch_ids'] == [bi_records['branch']]
    assert data['workforce']['approved_minutes'] == 480
    assert data['workforce']['locked_payroll'] == '880000.00'
    assert client.get('/api/admin/bi/report?' + RANGE + f'&branch_id={bi_records["other_branch"]}', headers=bi_records['manager_headers']).status_code == 403


def test_single_site_manager_can_view_site_business_and_export_is_audited(app, client, bi_records):
    app.config.update(ATTENDANCE_SIMPLE_MODE=True, ATTENDANCE_BRANCH_ID=bi_records['branch'])
    headers = bi_records['manager_headers']
    data = client.get('/api/admin/bi/report?' + RANGE, headers=headers).json
    assert data['business_scope'] == 'single_site' and data['business']['revenue']['total'] == '550000.00'
    response = client.get('/api/admin/bi/export.csv?' + RANGE, headers=headers)
    assert response.status_code == 200 and response.data.startswith(b'\xef\xbb\xbf')
    assert '550000.00' in response.get_data(as_text=True)
    with app.app_context():
        audit = ReportExportAudit.query.one()
        assert audit.branch_ids == [bi_records['branch']] and audit.request_id == response.headers['X-Request-ID']


@pytest.mark.parametrize('query', ['from=2026-10-16&to=2026-10-01', 'from=2020-01-01&to=2026-10-15', 'from=2026-02-30', 'branch_id=1.0'])
def test_bi_validates_dates_and_scope(client, bi_records, admin_auth_headers, query):
    assert client.get('/api/admin/bi/report?' + query, headers=admin_auth_headers).status_code == 400


def test_bi_flags_rbac_empty_and_zero_denominator(app, client, admin_auth_headers, staff_auth_headers, customer_auth_headers):
    assert client.get('/api/admin/bi/report', headers=admin_auth_headers).status_code == 404
    app.config['BI_REPORTS_ENABLED'] = True
    for headers in (staff_auth_headers, customer_auth_headers):
        assert client.get('/api/admin/bi/report', headers=headers).status_code == 403
        assert client.get('/api/admin/bi/export.csv', headers=headers).status_code == 403
    data = client.get('/api/admin/bi/report?' + RANGE, headers=admin_auth_headers).json
    assert data['business']['customers']['returning_rate'] is None
    assert data['business']['revenue']['total'] == '0.00'


def test_runtime_is_admin_only_and_never_exposes_payloads(app, client, bi_records, admin_auth_headers):
    assert client.get('/api/admin/runtime/status', headers=bi_records['manager_headers']).status_code == 403
    with app.app_context(): runtime_service.heartbeat()
    response = client.get('/api/admin/runtime/status?' + RANGE, headers=admin_auth_headers)
    assert response.status_code == 200 and response.json['worker']['state'] == 'ok'
    assert 'payload' not in json.dumps(response.json)
    assert client.get('/health/live').json == {'status': 'ok'}


def test_auth_limit_is_shared_atomic_and_has_retry_after(app, client):
    app.config['AUTH_RATE_LIMIT_ENABLED'] = True
    for _ in range(30): assert client.post('/api/auth/login/staff', json={}).status_code != 429
    response = client.post('/api/auth/login/staff', json={})
    assert response.status_code == 429 and int(response.headers['Retry-After']) > 0
    # A spoofed forwarding header cannot bypass the direct-peer limit.
    assert client.post('/api/auth/login/staff', json={}, headers={'X-Forwarded-For': 'different-ip'}).status_code == 429
    with app.app_context():
        assert len(AuthRateBucket.query.one().key) == 64


def test_measurements_are_bounded_and_logs_exclude_sensitive_values(app, client, caplog):
    app.config['OBSERVABILITY_ENABLED'] = True
    with caplog.at_level('INFO'):
        response = client.get('/api/services?private=NEVER_LOG_THIS', headers={'Authorization': 'Bearer SECRET_TOKEN'})
    assert response.status_code in (401, 422)
    entries = [r.message for r in caplog.records if 'http_request' in r.message]
    assert entries and 'NEVER_LOG_THIS' not in ''.join(entries) and 'SECRET_TOKEN' not in ''.join(entries)
    assert json.loads(entries[-1])['request_id'] == response.headers['X-Request-ID']
    m = runtime_service.RequestMeasurements(capacity=3)
    for n in range(5): m.record('/api/test/<id>', 'GET', 500 if n == 4 else 200, n * 10)
    data = m.snapshot()
    assert data['requests'] == 3 and data['server_errors'] == 1 and data['routes'][0]['p95_ms'] == 40


def test_no_show_outcome_is_canonical_and_idempotent(app, bi_records):
    with app.app_context():
        apt = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=bi_records['staff'], ngaygio=datetime(2026, 10, 15, 8), trangthai='confirmed')
        db.session.add(apt); db.session.commit(); aid = apt.malh
        appointment_service.auto_cancel_no_shows(now=datetime(2026, 10, 15, 10))
        appointment_service.auto_cancel_no_shows(now=datetime(2026, 10, 15, 10))
        assert AppointmentOutcome.query.filter_by(malh=aid, outcome='no_show').count() == 1


def test_readiness_requires_schema_and_never_reveals_connection_errors(app, client):
    assert client.get('/health/ready').json == {'status': 'unavailable'}
    assert client.get('/health/ready').status_code == 503
    with app.app_context():
        db.session.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32))'))
        from test_fresh_migration import _head
        db.session.execute(text('INSERT INTO alembic_version VALUES (:head)'), {'head': _head()}); db.session.commit()
    assert client.get('/health/ready').status_code == 200
    check = app.test_cli_runner().invoke(args=['release', 'check'])
    assert check.exit_code == 0 and 'PASS schema_and_assets' in check.output
    production = app.test_cli_runner().invoke(args=['release', 'check', '--production'])
    assert production.exit_code == 1 and 'FAIL production_environment' in production.output


def test_cookie_session_endpoints_reject_cross_site_posts(client):
    for url in ('/api/auth/restore-session', '/api/auth/logout'):
        assert client.post(url, headers={'Origin': 'https://untrusted.example'}).status_code == 403
        assert client.post(url, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert client.post('/api/auth/restore-session', headers={'Origin': 'http://localhost'}).status_code == 401


def test_auth_storage_failure_does_not_allow_login(app, client):
    with app.app_context():
        db.session.execute(text('DROP TABLE auth_rate_bucket')); db.session.commit()
    app.config['AUTH_RATE_LIMIT_ENABLED'] = True
    assert client.post('/api/auth/login/staff', json={}).status_code == 503


def test_auth_bucket_expiry_is_utc_and_releases_next_window(app):
    with app.app_context():
        now = datetime(2026, 10, 15, 9)
        assert runtime_service.consume_limit('test', 'peer', 1, 60, now)[0]
        assert not runtime_service.consume_limit('test', 'peer', 1, 60, now)[0]
        assert runtime_service.consume_limit('test', 'peer', 1, 60, now + timedelta(minutes=1))[0]
        assert AuthRateBucket.query.order_by(AuthRateBucket.bucket).first().expires_at == now + timedelta(minutes=1)

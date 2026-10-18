"""Separate connections exercise idempotency and transition locks in SQLite/PostgreSQL."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, text
from app import create_app
from app.extensions import db
from app.models import NhanVien, ChucVu, CaLam
from app.operations_models import Branch, BranchMembership, BranchGeoPolicy, AttendanceSession, AttendanceEvent
from app.services import attendance_service as att


@pytest.fixture(params=['sqlite', 'postgresql'])
def concurrent_operations(request, tmp_path):
    schema = 'attendance_test_' + uuid4().hex
    engine = None
    if request.param == 'postgresql':
        url = os.environ.get('TEST_LOYALTY_POSTGRES_URL')
        if not url:
            pytest.skip('TEST_LOYALTY_POSTGRES_URL not configured')
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {schema}'))
        options = dict(connect_args={'options': f'-csearch_path={schema}'})
    else:
        url = f"sqlite:///{(tmp_path / 'attendance.db').as_posix()}"
        options = dict(connect_args={'timeout': 30})
    app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI=url,
        SQLALCHEMY_ENGINE_OPTIONS=options, SECRET_KEY='concurrency-only',
        JWT_SECRET_KEY='attendance-concurrency-at-least-32-characters', ATTENDANCE_ENABLED=True))
    with app.app_context():
        db.create_all()
        role = ChucVu(tencv='Test', dongiagio=30000)
        branch = Branch(name='Test branch', address='')
        db.session.add_all([role, branch]); db.session.flush()
        staff = NhanVien(hoten='Test Staff', taikhoan='staff', matkhau='hash', macv=role.macv, role='staff', trangthai=True)
        admin = NhanVien(hoten='Admin', taikhoan='admin', matkhau='hash', macv=role.macv, role='admin', trangthai=True)
        db.session.add_all([staff, admin]); db.session.flush()
        local = att.now_utc().astimezone(att.LOCAL)
        shift = CaLam(ngay=(local - timedelta(minutes=5)).date(), giobatdau=(local - timedelta(minutes=5)).time().replace(microsecond=0),
            gioketthuc=(local + timedelta(hours=2)).time().replace(microsecond=0), sogio=2, hesoluong=1, branch_id=branch.id)
        db.session.add(shift); db.session.flush(); staff.calam.append(shift)
        db.session.add(BranchMembership(branch_id=branch.id, staff_id=staff.manv))
        db.session.add(BranchGeoPolicy(branch_id=branch.id, version=1, created_by=admin.manv,
            settings=dict(att.DEFAULT_POLICY, enabled=True)))
        db.session.commit()
        app.config['RACE_SHIFT'] = shift.maca
        app.config['RACE_HEADERS'] = {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{staff.manv}')}
    yield app
    with app.app_context():
        db.session.remove(); db.engine.dispose()
    if engine:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()


def race(app, keys, action='check-in'):
    barrier = Barrier(len(keys))
    captured = att.iso(att.now_utc())
    def call(key):
        barrier.wait(timeout=10)
        with app.test_client() as client:
            r = client.post('/api/attendance/' + action, headers=app.config['RACE_HEADERS'], json=dict(
                shift_assignment_id=app.config['RACE_SHIFT'], latitude=att.DEFAULT_POLICY['latitude'],
                longitude=att.DEFAULT_POLICY['longitude'], accuracy=25, location_timestamp=captured, idempotency_key=key))
            return r.status_code, r.json
    with ThreadPoolExecutor(max_workers=len(keys)) as executor:
        return list(executor.map(call, keys))


def test_concurrent_identical_retries_return_same_record(concurrent_operations):
    app = concurrent_operations
    responses = race(app, ['same-request-key', 'same-request-key'])
    assert responses[0] == responses[1] and responses[0][0] == 200, responses
    with app.app_context():
        assert AttendanceSession.query.count() == 1 and AttendanceEvent.query.count() == 1


def test_concurrent_different_keys_cannot_double_checkin(concurrent_operations):
    app = concurrent_operations
    responses = race(app, ['first-request-key', 'second-request-key'])
    assert sorted(code for code, _ in responses) == [200, 409], responses
    with app.app_context():
        assert AttendanceSession.query.count() == 1
        assert AttendanceEvent.query.filter_by(verdict='accepted').count() == 1


def test_concurrent_checkout_submits_once(concurrent_operations):
    app = concurrent_operations
    assert race(app, ['one-checkin-request'])[0][0] == 200
    responses = race(app, ['first-checkout-key', 'second-checkout-key'], 'check-out')
    assert sorted(code for code, _ in responses) == [200, 409], responses
    with app.app_context():
        session = AttendanceSession.query.one()
        assert session.approval_status == 'SUBMITTED'
        assert AttendanceEvent.query.filter_by(verdict='accepted', event_type='check-out').count() == 1

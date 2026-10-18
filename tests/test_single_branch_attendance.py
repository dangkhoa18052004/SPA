"""Per-shift attendance (ATTENDANCE_SIMPLE_MODE off) for a spa with a single active branch.

The shift page does not ask for a branch, so a shift without one belongs to the only active branch;
only staff assigned to the shift may punch it. With several branches there is no default.
"""
from datetime import datetime, time, timedelta

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import CaLam, NhanVien
from app.operations_models import Branch, BranchMembership, BranchGeoPolicy
from app.services import attendance_service as att


@pytest.fixture()
def spa(app, monkeypatch):
    now = datetime(2026, 10, 16, 8, 30, tzinfo=att.UTC)  # 15:30 Saigon
    monkeypatch.setattr(att, 'now_utc', lambda: now)
    app.config.update(ATTENDANCE_ENABLED=True, ATTENDANCE_SIMPLE_MODE=False, EMPLOYEE_PORTAL_ENABLED=True)
    with app.app_context():
        branch = Branch(name='Bin Spa', address='')
        db.session.add(branch); db.session.flush()
        db.session.add(BranchGeoPolicy(branch_id=branch.id, version=1, settings=dict(att.DEFAULT_POLICY, enabled=True),
                                       created_by=app.config['TEST_ADMIN_ID']))
        staff = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        other = db.session.get(NhanVien, app.config['TEST_STAFF2_ID'])
        manager = NhanVien(hoten='Quản lý', taikhoan='ql_single', matkhau='x', macv=staff.macv, role='manager', trangthai=True)
        db.session.add(manager); db.session.flush()
        db.session.add_all([BranchMembership(branch_id=branch.id, staff_id=staff.manv), BranchMembership(branch_id=branch.id, staff_id=other.manv),
                            BranchMembership(branch_id=branch.id, staff_id=manager.manv, can_manage=True)])
        # Created on the old shift page: no branch.
        shift = CaLam(ngay=now.astimezone(att.LOCAL).date(), giobatdau=time(15), gioketthuc=time(18), sogio=3, hesoluong=1)
        db.session.add(shift); db.session.flush(); staff.calam.append(shift)
        db.session.commit()
        token = lambda person: {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{person.manv}')}
        return dict(now=now, branch=branch.id, shift=shift.maca, staff=token(staff), other=token(other), manager=token(manager))


def check_in(client, headers, spa):
    return client.post('/api/attendance/check-in', headers=headers, json=dict(shift_assignment_id=spa['shift'],
        latitude=att.DEFAULT_POLICY['latitude'], longitude=att.DEFAULT_POLICY['longitude'], accuracy=20,
        location_timestamp=spa['now'].isoformat(), idempotency_key='single-branch-check-in'))


def test_assigned_staff_sees_and_punches_a_shift_saved_without_branch(client, spa):
    today = client.get('/api/me/shifts/today', headers=spa['staff']).json['items']
    assert [s['shift_id'] for s in today] == [spa['shift']] and today[0]['branch_id'] == spa['branch']
    response = check_in(client, spa['staff'], spa)
    assert response.status_code == 200, response.json


def test_unassigned_staff_cannot_punch_in_per_shift_mode(client, spa):
    response = check_in(client, spa['other'], spa)
    assert response.status_code == 403 and response.json['code'] == 'shift_forbidden'


def test_manager_creates_shift_without_choosing_branch(client, spa):
    response = client.post('/api/admin/shifts', headers=spa['manager'], json=dict(ngay='2026-10-17', giobatdau='09:00', gioketthuc='17:00'))
    assert response.status_code in (200, 201), response.json
    with client.application.app_context():
        assert CaLam.query.filter_by(ngay=datetime(2026, 10, 17).date()).one().branch_id == spa['branch']


def test_no_default_branch_when_spa_has_several(client, spa):
    with client.application.app_context():
        db.session.add(Branch(name='Cơ sở 2', address='')); db.session.commit()
    assert check_in(client, spa['staff'], spa).json['code'] == 'branch_missing'
    response = client.post('/api/admin/shifts', headers=spa['manager'], json=dict(ngay='2026-10-18', giobatdau='09:00', gioketthuc='17:00'))
    assert response.status_code == 400

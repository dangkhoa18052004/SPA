"""F03: hoa hồng KTV theo dịch vụ, snapshot ghi một lần và được cộng vào bảng lương."""
from datetime import timedelta, time, datetime
from decimal import Decimal

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import (CommissionEntry, DichVu, LichHen, ChiTietLichHen, Luong, BangLuongChiTiet,
                        CaLam, TheLieuTrinhItem, AppointmentStatus)
from app.services import commission_service, package_service as ps

from test_phase4_packages_care import package_data, activate  # noqa: F401


def _set_policy(app, madv, percent=None, fixed=None):
    with app.app_context():
        service = db.session.get(DichVu, madv)
        service.commission_percent, service.commission_fixed = percent, fixed
        db.session.commit()


def _direct_appointment(app, services, staff_key='TEST_STAFF_ID', status=AppointmentStatus.CONFIRMED):
    with app.app_context():
        apt = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config[staff_key],
                      ngaygio=ps.local_now().replace(microsecond=0), trangthai=status)
        db.session.add(apt)
        db.session.flush()
        for madv in services:
            db.session.add(ChiTietLichHen(malh=apt.malh, madv=madv))
        db.session.commit()
        return apt.malh


def _complete(client, headers, malh):
    return client.post(f'/api/admin/appointments/{malh}/complete', headers=headers)


def _entries(app, malh=None):
    with app.app_context():
        q = CommissionEntry.query
        if malh is not None:
            q = q.filter_by(malh=malh)
        return [(e.madv, e.source_type, e.base_amount, e.amount, e.status) for e in q.order_by(CommissionEntry.id)]


def test_percent_commission_recorded_once(app, client, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], percent=Decimal('10'))
    malh = _direct_appointment(app, [package_data['service'], package_data['other_service']])
    assert _complete(client, admin_auth_headers, malh).status_code == 200
    for _ in range(2):
        _complete(client, admin_auth_headers, malh)  # hoàn thành lặp
    rows = _entries(app, malh)
    assert len(rows) == 2
    assert rows[0] == (package_data['service'], 'regular', Decimal('300000.00'), Decimal('30000.00'), 'active')
    # Dịch vụ không có chính sách: vẫn ghi để đối soát nhưng 0đ.
    assert rows[1][3] == 0


def test_fixed_takes_priority_and_history_is_snapshot(app, client, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], percent=Decimal('10'), fixed=Decimal('50000'))
    first = _direct_appointment(app, [package_data['service']])
    _complete(client, admin_auth_headers, first)
    # Đổi giá và tỷ lệ sau khi đã ghi: lịch sử giữ nguyên.
    with app.app_context():
        service = db.session.get(DichVu, package_data['service'])
        service.gia, service.commission_percent, service.commission_fixed = 500000, Decimal('20'), None
        db.session.commit()
    second = _direct_appointment(app, [package_data['service']])
    _complete(client, admin_auth_headers, second)
    assert _entries(app, first)[0][2:4] == (Decimal('300000.00'), Decimal('50000.00'))
    assert _entries(app, second)[0][2:4] == (Decimal('500000.00'), Decimal('100000.00'))


def test_package_session_uses_allocated_value(app, client, customer_auth_headers, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], percent=Decimal('10'))
    record = activate(client, customer_auth_headers, admin_auth_headers, package_data)
    r = client.post('/api/appointments/create', headers=customer_auth_headers, json={
        'madv_list': [package_data['service']], 'ngaygio': package_data['slot'].strftime('%Y-%m-%dT%H:%M'),
        'package_usages': [dict(mathe=record, madv=package_data['service'], quantity=1)]})
    assert r.status_code == 201, r.json
    malh = r.json['appointment']['malh']
    with app.app_context():
        assert db.session.get(LichHen, malh).manv is not None
        unit = TheLieuTrinhItem.query.filter_by(source_type='package').one().unit_value_snapshot
    assert _complete(client, admin_auth_headers, malh).status_code == 200
    (madv, source, base, amount, status), = _entries(app, malh)
    assert source == 'package' and base == unit == Decimal('240000.00') and amount == Decimal('24000.00')


def test_gift_session_uses_regular_price_snapshot(app, client, customer_auth_headers, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], fixed=Decimal('20000'))
    record = activate(client, customer_auth_headers, admin_auth_headers, package_data)
    item = client.post(f'/api/admin/packages/treatments/{record}/gifts', headers=admin_auth_headers,
                       json=dict(madv=package_data['service'], quantity=1, gift_note='Quà')).json['item_id']
    r = client.post('/api/appointments/create', headers=customer_auth_headers, json=dict(
        madv_list=[package_data['service']], ngaygio=package_data['slot'].isoformat(),
        package_usages=[dict(mathe=record, madv=package_data['service'], the_item_id=item, quantity=1)]))
    assert r.status_code == 201, r.json
    malh = r.json['appointment']['malh']
    _complete(client, admin_auth_headers, malh)
    (_, source, base, amount, _), = _entries(app, malh)
    assert source == 'gift' and base == Decimal('300000.00') and amount == Decimal('20000.00')


def test_reopen_voids_and_recomplete_restores_same_snapshot(app, client, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], percent=Decimal('10'))
    malh = _direct_appointment(app, [package_data['service']])
    _complete(client, admin_auth_headers, malh)
    r = client.put(f'/api/admin/appointments/{malh}', headers=admin_auth_headers, json={'trangthai': 'confirmed'})
    assert r.status_code == 200, r.json
    assert _entries(app, malh)[0][4] == 'voided'
    _set_policy(app, package_data['service'], percent=Decimal('50'))
    _complete(client, admin_auth_headers, malh)
    assert _entries(app, malh) == [(package_data['service'], 'regular', Decimal('300000.00'), Decimal('30000.00'), 'active')]


def test_unassigned_appointment_has_no_commission(app, client, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], percent=Decimal('10'))
    malh = _direct_appointment(app, [package_data['service']])
    with app.app_context():
        db.session.get(LichHen, malh).manv = None
        db.session.commit()
    _complete(client, admin_auth_headers, malh)
    assert _entries(app, malh) == []


def test_payroll_includes_commission(app, client, admin_auth_headers, package_data):
    _set_policy(app, package_data['service'], percent=Decimal('10'))
    staff_id = app.config['TEST_STAFF_ID']
    now = ps.local_now()
    with app.app_context():
        shift = CaLam(ngay=now.date(), giobatdau=time(8), gioketthuc=time(12), sogio=4)
        db.session.add(shift); db.session.flush()
        db.session.add(BangLuongChiTiet(manv=staff_id, maca=shift.maca, ngay_lam=now.date(), sogio_lam=4,
                                        dongia_gio=100000, luong_ca=400000, thuong_ca=50000, khautru_ca=20000))
        db.session.commit()
    malh = _direct_appointment(app, [package_data['service']])
    _complete(client, admin_auth_headers, malh)

    r = client.post('/api/admin/salaries/calculate', headers=admin_auth_headers, json={'thang': now.month, 'nam': now.year})
    assert r.status_code == 200, r.json
    rows = client.get(f'/api/admin/salaries?filter_type=month&month_year={now:%Y-%m}', headers=admin_auth_headers).json
    row = next(x for x in rows if x['manv'] == staff_id)
    assert Decimal(row['luongcoban']) == 400000 and Decimal(row['hoahong']) == 30000
    assert Decimal(row['tongluong']) == 400000 + 30000 + 50000 - 20000

    detail = client.get(f"/api/admin/salaries/{row['maluong']}/commissions", headers=admin_auth_headers).json
    assert Decimal(detail['total']) == 30000 and detail['entries'][0]['source_label'] == 'Trả lẻ'

    # Điều chỉnh thưởng tháng vẫn giữ hoa hồng trong tổng.
    r = client.put(f"/api/admin/salaries/{row['maluong']}", headers=admin_auth_headers, json={'thuong': 0, 'khautru': 0})
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Luong, row['maluong']).tongluong == 430000

    day = client.get(f'/api/admin/salaries?filter_type=day&day={now:%Y-%m-%d}', headers=admin_auth_headers).json
    assert Decimal(next(x for x in day if x['manv'] == staff_id)['hoahong_ngay']) == 30000


def test_commission_policy_validation_and_visibility(app, client, admin_auth_headers, staff_auth_headers, package_data):
    madv = package_data['service']
    r = client.put(f'/api/admin/services/{madv}', headers=admin_auth_headers, data={'commission_percent': '150'})
    assert r.status_code == 400
    r = client.put(f'/api/admin/services/{madv}', headers=admin_auth_headers,
                   data={'commission_percent': '12.5', 'commission_fixed': ''})
    assert r.status_code == 200, r.json
    admin_view = next(s for s in client.get('/api/admin/services', headers=admin_auth_headers).json if s['madv'] == madv)
    assert admin_view['commission_percent'] == '12.50' and admin_view['commission_fixed'] is None
    staff_view = next(s for s in client.get('/api/admin/services', headers=staff_auth_headers).json if s['madv'] == madv)
    assert 'commission_percent' not in staff_view


def test_commission_detail_requires_manager(client, staff_auth_headers):
    assert client.get('/api/admin/salaries/1/commissions', headers=staff_auth_headers).status_code == 403


def test_compute_amount_rounds_to_vnd():
    assert commission_service.compute_amount(Decimal('333333'), Decimal('7.5'), None) == Decimal('25000')
    assert commission_service.compute_amount(Decimal('100'), None, None) == 0

"""Staff booking uses the existing exact-item entitlement and billing lifecycle."""
import importlib.util
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory
from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import (NhanVien, KhachHang, LichHen, LieuTrinhUsage, TheLieuTrinh,
                        TheLieuTrinhItem, HoaDon, NotificationJob)
from app.services import package_service as ps, appointment_service as appointments
from test_phase4_packages_care import package_data, phase4_temp_dir


@pytest.fixture
def entitlements(app, package_data):
    with app.app_context():
        admin = db.session.get(NhanVien, app.config['TEST_ADMIN_ID'])
        actors = {}
        for role in ('manager', 'letan'):
            staff = NhanVien(hoten=role, taikhoan=f'booking_{role}', matkhau='test',
                            macv=admin.macv, role=role, trangthai=True)
            db.session.add(staff)
            db.session.flush()
            actors[role] = dict(id=staff.manv, headers={'Authorization': 'Bearer ' +
                create_access_token(identity=f'staff:{staff.manv}')})
        other = KhachHang(hoten='Other booking customer', taikhoan='booking_other', matkhau='test', trangthai='active')
        db.session.add(other)
        db.session.flush()
        records = []
        for customer in (package_data['customer'], package_data['customer'], other.makh):
            purchase = ps.create_purchase(package_data['id'], customer, 'cash')
            _, record, _ = ps.confirm_purchase(purchase.id, purchase.amount, method='cash')
            records.append(record)
        gift = ps.gift_service(records[0].mathe, dict(madv=package_data['service'], total_sessions=2,
            gift_note='<b>Gift note</b>', validity_days=10), admin)[1]
        extra_gift = ps.gift_service(records[0].mathe, dict(madv=package_data['other_service'],
            total_sessions=2), admin)[1]
        db.session.commit()
        return dict(record=records[0].mathe, original=records[0].items[0].id, gift=gift.id,
            extra_gift=extra_gift.id, second=records[1].mathe, second_item=records[1].items[0].id,
            other_record=records[2].mathe, other_item=records[2].items[0].id, other_customer=other.makh,
            actors=actors)


def payload(data, entitlements, item=None, **changes):
    result = dict(makh=data['customer'], madv_list=[data['service']], ngaygio=data['slot'].strftime('%Y-%m-%dT%H:%M'),
        manv=None, ghichu='CSKH đặt giúp khách', package_usages=[dict(mathe=entitlements['record'],
            the_item_id=item or entitlements['original'], madv=data['service'], quantity=1)])
    result.update(changes)
    return result


@pytest.mark.parametrize('role', ['admin', 'manager', 'letan'])
@pytest.mark.parametrize('source', ['package', 'gift'])
def test_exact_item_booking_audit_customer_view_jobs_email(app, client, admin_auth_headers,
        customer_auth_headers, package_data, entitlements, monkeypatch, role, source):
    headers = admin_auth_headers if role == 'admin' else entitlements['actors'][role]['headers']
    actor = app.config['TEST_ADMIN_ID'] if role == 'admin' else entitlements['actors'][role]['id']
    calls = []
    monkeypatch.setattr(appointments, 'send_appointment_confirmation_email_async', lambda *args: calls.append(args))
    item_id = entitlements['original'] if source == 'package' else entitlements['gift']
    response = client.post('/api/admin/appointments', headers=headers,
        json=payload(package_data, entitlements, item_id, created_by_staff=999, booking_source='customer'))
    assert response.status_code == 201, response.json
    apt_id = response.json['malh']
    assert response.json['appointment']['booking_source'] == 'admin'
    assert response.json['appointment']['created_by_staff'] == actor
    with app.app_context():
        usage = LieuTrinhUsage.query.filter_by(malh=apt_id).one()
        assert (usage.the_item_id, usage.state) == (item_id, 'reserved')
        assert ps.item_counts(db.session.get(TheLieuTrinhItem, item_id))['reserved'] == 1
        assert NotificationJob.query.filter_by(malh=apt_id).count() == 2
        assert {j.type for j in NotificationJob.query.filter_by(malh=apt_id)} == {'appointment_reminder_24h', 'appointment_reminder_2h'}
    assert len(calls) == 1 and calls[0][0] == 'customer@example.com'
    assert calls[0][2]['staff_name'] and calls[0][2]['services'][0]['madv'] == package_data['service']
    customer = client.get('/api/appointments/my-appointments', headers=customer_auth_headers)
    apt = next(a for a in customer.json['appointments'] if a['malh'] == apt_id)
    assert apt['ngaygio'].startswith(package_data['slot'].strftime('%Y-%m-%dT%H:%M'))
    assert apt['trangthai'] == 'confirmed'
    detail = client.get(f'/api/admin/appointments/{apt_id}', headers=headers).json['appointment']
    assert detail['services'][0]['coverage']['the_item_id'] == item_id
    assert detail['services'][0]['coverage']['source_type'] == source


def test_booking_read_only_exact_customer_and_existing_filters(app, client, admin_auth_headers,
        staff_auth_headers, customer_auth_headers, package_data, entitlements):
    url = f"/api/admin/appointments/customers/{package_data['customer']}/treatments"
    for headers in (admin_auth_headers, entitlements['actors']['manager']['headers'], entitlements['actors']['letan']['headers']):
        result = client.get(url, headers=headers)
        assert result.status_code == 200, result.json
        assert {t['mathe'] for t in result.json['treatments']} == {entitlements['record'], entitlements['second']}
        serialized = str(result.json)
        for field in ('unit_value_snapshot', 'regular_price_snapshot', 'history', 'phone', 'purchase_id'):
            assert field not in serialized
        items = result.json['treatments'][1]['items']
        assert {i['source_type'] for i in items} == {'package', 'gift'}
    assert client.get(url, headers=staff_auth_headers).status_code == 403
    assert client.get(url, headers=customer_auth_headers).status_code == 403
    assert client.post('/api/admin/appointments', headers=staff_auth_headers, json=payload(package_data, entitlements)).status_code == 403
    receptionist = entitlements['actors']['letan']['headers']
    for endpoint in ('/api/admin/packages/treatments', f"/api/admin/packages/treatments/{entitlements['record']}"):
        assert client.get(endpoint, headers=receptionist).status_code == 403
    assert client.post(f"/api/admin/packages/treatments/{entitlements['record']}/gifts", headers=receptionist, json={}).status_code == 403
    assert client.put(f"/api/admin/packages/{package_data['id']}", headers=receptionist, json={}).status_code == 403
    assert client.get('/api/admin/appointments/customers/99999/treatments', headers=receptionist).status_code == 404
    result = client.get(f"/api/admin/packages/treatments?makh={entitlements['other_customer']}&search=Other&status=active", headers=admin_auth_headers)
    assert [t['mathe'] for t in result.json['treatments']] == [entitlements['other_record']]
    for value in ('bad', '', '0', '-1'):
        assert client.get('/api/admin/packages/treatments?makh=' + value, headers=admin_auth_headers).status_code == 400
    with app.app_context():
        db.session.get(NhanVien, entitlements['actors']['letan']['id']).trangthai = False
        db.session.commit()
    assert client.get(url, headers=receptionist).status_code == 403
    assert client.post('/api/admin/appointments', headers=receptionist, json=payload(package_data, entitlements)).status_code == 403


@pytest.mark.parametrize('invalid', ['customer', 'treatment', 'item', 'service', 'appointment_service',
    'quantity', 'duplicate', 'missing_item', 'expired_package', 'expired_gift', 'future_expiry',
    'future_start', 'sold_out', 'cancelled', 'inactive_service', 'invalid_source'])
def test_invalid_entitlement_rolls_back_booking(app, client, admin_auth_headers, package_data, entitlements, invalid):
    body = payload(package_data, entitlements)
    row = body['package_usages'][0]
    with app.app_context():
        record = db.session.get(TheLieuTrinh, entitlements['record'])
        item = db.session.get(TheLieuTrinhItem, entitlements['original'])
        if invalid == 'customer': row.update(mathe=entitlements['other_record'], the_item_id=entitlements['other_item'])
        elif invalid == 'treatment': row['mathe'] = 9999
        elif invalid == 'item': row['the_item_id'] = entitlements['second_item']
        elif invalid == 'service': row['the_item_id'] = entitlements['extra_gift']
        elif invalid == 'appointment_service': row['madv'] = package_data['other_service']
        elif invalid == 'quantity': row['quantity'] = 2
        elif invalid == 'duplicate': body['package_usages'].append(dict(row))
        elif invalid == 'missing_item': row.pop('the_item_id')
        elif invalid == 'expired_package': record.expires_at = ps.local_now() - timedelta(days=1)
        elif invalid == 'expired_gift':
            row['the_item_id'] = entitlements['gift']
            db.session.get(TheLieuTrinhItem, entitlements['gift']).expires_at = ps.local_now() - timedelta(days=1)
        elif invalid == 'future_expiry': record.expires_at = package_data['slot'] - timedelta(days=1)
        elif invalid == 'future_start': item.valid_from = package_data['slot'] + timedelta(days=1)
        elif invalid == 'sold_out':
            item.total_sessions = 1
            apt = LichHen(makh=package_data['customer'], ngaygio=package_data['slot'], trangthai='completed')
            db.session.add(apt); db.session.flush()
            db.session.add(LieuTrinhUsage(mathe=record.mathe, the_item_id=item.id, madv=item.madv,
                malh=apt.malh, state='consumed', reserved_at=ps.local_now()))
        elif invalid == 'cancelled': record.status = 'cancelled'
        elif invalid == 'inactive_service': item.service.active = False
        elif invalid == 'invalid_source':
            # DB constraint protects persisted data; exercise the shared validity predicate too.
            item.source_type = 'invalid'
            assert not ps.is_treatment_item_usable(item, record, package_data['slot'])
            db.session.rollback()
            return
        db.session.commit()
        before = (LichHen.query.count(), LieuTrinhUsage.query.count(), NotificationJob.query.count(), record.version)
    response = client.post('/api/admin/appointments', headers=admin_auth_headers, json=body)
    assert response.status_code == 400, response.json
    with app.app_context():
        assert (LichHen.query.count(), LieuTrinhUsage.query.count(), NotificationJob.query.count(),
            db.session.get(TheLieuTrinh, entitlements['record']).version) == before


def test_gift_survives_package_expiry_and_cancel_restores_session(app, client, package_data, entitlements):
    headers = entitlements['actors']['letan']['headers']
    with app.app_context():
        record = db.session.get(TheLieuTrinh, entitlements['record'])
        record.expires_at = ps.local_now() - timedelta(days=1)
        record.status = 'expired'
        db.session.commit()
    response = client.post('/api/admin/appointments', headers=headers, json=payload(package_data, entitlements, entitlements['gift']))
    assert response.status_code == 201, response.json
    apt_id = response.json['malh']
    with app.app_context():
        assert ps.item_counts(db.session.get(TheLieuTrinhItem, entitlements['gift']))['available_sessions'] == 1
    assert client.post(f'/api/admin/appointments/{apt_id}/cancel', headers=headers, json={'reason': 'Khách đổi lịch'}).status_code == 200
    with app.app_context():
        assert LieuTrinhUsage.query.filter_by(malh=apt_id).one().state == 'released'
        assert ps.item_counts(db.session.get(TheLieuTrinhItem, entitlements['gift']))['available_sessions'] == 2
        assert {j.status for j in NotificationJob.query.filter_by(malh=apt_id)} == {'cancelled'}


@pytest.mark.parametrize('mixed', [False, True])
def test_complete_idempotent_full_or_mixed_invoice(app, client, admin_auth_headers, package_data, entitlements, mixed):
    body = payload(package_data, entitlements, madv_list=[package_data['service'], package_data['other_service']])
    if not mixed:
        body['package_usages'].append(dict(mathe=entitlements['record'], the_item_id=entitlements['extra_gift'],
            madv=package_data['other_service'], quantity=1))
    booked = client.post('/api/admin/appointments', headers=admin_auth_headers, json=body)
    assert booked.status_code == 201, booked.json
    apt_id = booked.json['malh']
    for _ in range(2):
        assert client.post(f'/api/admin/appointments/{apt_id}/complete', headers=admin_auth_headers).status_code == 200
    with app.app_context():
        assert LieuTrinhUsage.query.filter_by(malh=apt_id, state='consumed').count() == (1 if mixed else 2)
        assert ps.item_counts(db.session.get(TheLieuTrinhItem, entitlements['original']))['consumed'] == 1
        assert HoaDon.query.count() == 0
    invoice = client.post(f'/api/admin/appointments/{apt_id}/create-invoice', headers=admin_auth_headers)
    assert invoice.status_code == (201 if mixed else 400), invoice.json
    with app.app_context():
        if mixed:
            row = HoaDon.query.filter_by(malh=apt_id).one()
            assert row.tongtien == 300000
            assert [item.madv for item in row.chitiet] == [package_data['other_service']]
        else:
            assert HoaDon.query.count() == 0


def test_customer_legacy_payload_keeps_self_booking_and_audit(app, client, customer_auth_headers, package_data, entitlements):
    body = payload(package_data, entitlements, booking_source='admin', created_by_staff=app.config['TEST_ADMIN_ID'])
    body['package_usages'][0].pop('the_item_id')
    response = client.post('/api/appointments/create', headers=customer_auth_headers, json=body)
    assert response.status_code == 201, response.json
    with app.app_context():
        apt = db.session.get(LichHen, response.json['appointment']['malh'])
        assert apt.booking_source == 'customer' and apt.created_by_staff is None
        assert LieuTrinhUsage.query.filter_by(malh=apt.malh).one().the_item_id == entitlements['original']


def test_admin_last_session_concurrent_booking(app, admin_auth_headers, package_data, entitlements, phase4_temp_dir):
    target = create_engine(f'sqlite:///{phase4_temp_dir / "admin_booking.sqlite"}', connect_args={'timeout': 10})
    with app.app_context():
        db.session.get(TheLieuTrinhItem, entitlements['original']).total_sessions = 1
        db.session.commit()
        db.metadata.create_all(target)
        with target.begin() as connection:
            for table in db.metadata.sorted_tables:
                rows = [dict(row._mapping) for row in db.session.execute(table.select())]
                if rows: connection.execute(table.insert(), rows)
    from app import create_app
    config = dict(app.config, SQLALCHEMY_DATABASE_URI=str(target.url))
    concurrent_app = create_app(config)
    barrier = threading.Barrier(2)
    def reserve(index):
        with concurrent_app.test_client() as client:
            barrier.wait(timeout=10)
            body = payload(package_data, entitlements,
                ngaygio=(package_data['slot'] + timedelta(hours=index * 2)).strftime('%Y-%m-%dT%H:%M'))
            return client.post('/api/admin/appointments', headers=admin_auth_headers, json=body).status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(reserve, (0, 1)))
        assert sorted(results) == [201, 400], results
        with Session(target) as session:
            assert session.query(LieuTrinhUsage).filter_by(the_item_id=entitlements['original'], state='reserved').count() == 1
            assert session.query(LichHen).count() == 1
    finally:
        with concurrent_app.app_context(): db.engine.dispose()
        target.dispose()


def test_audit_migration_preserves_existing_appointments_and_fk():
    path = Path('migrations/versions/20261004_0010_appointment_booking_audit.py')
    spec = importlib.util.spec_from_file_location('booking_audit', path)
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    config = Config(); config.set_main_option('script_location', 'migrations')
    assert revision.revision in {r.revision for r in ScriptDirectory.from_config(config).walk_revisions()}
    assert revision.down_revision == '20261003_0009'
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE lichhen (malh INTEGER PRIMARY KEY, manv INTEGER REFERENCES nhanvien(manv), ghichu TEXT)'))
        connection.execute(text('INSERT INTO nhanvien VALUES (7)'))
        connection.execute(text("INSERT INTO lichhen VALUES (12, 7, 'Legacy appointment')"))
        with Operations.context(MigrationContext.configure(connection)): revision.upgrade()
        assert connection.execute(text('SELECT malh, manv, ghichu, booking_source, created_by_staff FROM lichhen')).one() == (12, 7, 'Legacy appointment', 'legacy', None)
        assert any(fk['name'] == 'fk_lichhen_booking_creator' for fk in inspect(connection).get_foreign_keys('lichhen'))
        connection.execute(text("INSERT INTO lichhen (malh, manv, booking_source, created_by_staff) VALUES (13,7,'admin',7)"))
        with Operations.context(MigrationContext.configure(connection)): revision.downgrade()
        assert connection.execute(text('SELECT COUNT(*) FROM lichhen')).scalar() == 2

"""Channel isolation, payment snapshots and existing treatment rights."""
from copy import deepcopy
from itertools import product
import json

import pytest

from app.extensions import db
from app.models import GoiDichVu, GoiDichVuPurchase, TheLieuTrinh, TheLieuTrinhItem, DichVu, NhanVien, LieuTrinhUsage
from app.services import package_service as ps
from app.services.appointment_service import AppointmentValidationError
from test_package_completion import catalog


def set_flags(app, catalog, active=True, customer=True, staff=True):
    with app.app_context():
        package = db.session.get(GoiDichVu, catalog['package'])
        package.active = active
        package.customer_sale_enabled = customer
        package.staff_sale_enabled = staff
        db.session.commit()


def package_body(catalog, **flags):
    return dict(tengoi='Gói kiểm thử kênh bán', giagoi=1200000, validity_months=8,
        items=[dict(madv=catalog['service'], total_sessions=5)], **flags)


@pytest.mark.parametrize('active,customer,staff', list(product([True, False], repeat=3)))
def test_channel_matrix_and_customer_cannot_override_channel(app, client, catalog,
        customer_auth_headers, active, customer, staff):
    set_flags(app, catalog, active, customer, staff)
    package_id = catalog['package']
    online = active and customer
    counter = active and staff
    public = client.get('/api/packages').json['packages']
    assert (package_id in [p['magoi'] for p in public]) == online
    for path in (f'/packages/{package_id}', f'/api/packages/{package_id}'):
        assert client.get(path).status_code == (200 if online else 404)
    response = client.post(f'/api/packages/{package_id}/purchase', headers=customer_auth_headers,
        json=dict(payment_method='cash', sale_channel='staff', created_by_staff=catalog['receptionist']))
    assert response.status_code == (201 if online else 400), response.json
    if online:
        assert response.json['purchase']['created_by_staff'] is None
    else:
        assert response.json['success'] is False
        with app.app_context():
            assert GoiDichVuPurchase.query.count() == 0
    available = client.get('/api/admin/package-sales/packages', headers=catalog['headers'])
    assert available.status_code == 200
    assert (package_id in [p['magoi'] for p in available.json['packages']]) == counter
    if counter:
        assert available.json['packages'][0]['customer_sale_enabled'] == customer
        for search in ('Test package', str(package_id), f'#{package_id}'):
            found = client.get('/api/admin/package-sales/packages', headers=catalog['headers'],
                query_string={'search': search}).json['packages']
            assert [p['magoi'] for p in found] == [package_id]
    response = client.post('/api/admin/package-sales', headers=catalog['headers'],
        json=dict(makh=catalog['customer'], magoi=package_id, payment_method='cash', sale_channel='customer'))
    assert response.status_code == (201 if counter else 400), response.json
    if counter:
        assert response.json['purchase']['created_by_staff'] == catalog['receptionist']
    with app.app_context():
        assert GoiDichVuPurchase.query.count() == int(online) + int(counter)


@pytest.mark.parametrize('method', ['cash', 'vietqr'])
def test_staff_only_payment_activates_snapshot_after_archive(app, client, catalog, method, customer_auth_headers):
    set_flags(app, catalog, customer=False)
    response = client.post('/api/admin/package-sales', headers=catalog['headers'],
        json=dict(makh=catalog['customer'], magoi=catalog['package'], payment_method=method))
    assert response.status_code == 201, response.json
    purchase = response.json['purchase']
    assert purchase['status'] == 'pending' and purchase['mathe'] is None
    with app.app_context():
        row = db.session.get(GoiDichVuPurchase, purchase['id'])
        snapshot = deepcopy(row.snapshot_json)
        assert snapshot['tengoi'] == 'Test package'
        assert snapshot['giagoi'] == '1200000.00'
        assert snapshot['validity_months'] == 8
        assert snapshot['items'][0]['total_sessions'] == 5
        assert snapshot['items'][0]['madv'] == catalog['service']
        assert snapshot['items'][0]['package_unit_value'] == '240000.00'
        package = db.session.get(GoiDichVu, catalog['package'])
        package.tengoi = 'Changed after purchase'
        package.giagoi = 999999
        package.validity_months = 1
        package.items[0].total_sessions = 1
        package.active = package.customer_sale_enabled = package.staff_sale_enabled = False
        db.session.commit()
    if method == 'cash':
        response = client.post(f"/api/admin/packages/purchases/{purchase['id']}/confirm-payment",
            headers=catalog['headers'], json={'cash_received': 1500000})
        assert response.status_code == 200, response.json
        assert response.json['purchase']['change'] == '300000.00'
    else:
        assert purchase['payment']['amount'] == 1200000
        for _ in range(2):
            response = client.post('/api/payment/webhook/sepay', headers={'Authorization': 'Apikey test-sepay-key'},
                json=dict(id='staff-only-payment', content=f"PKG{purchase['id']}", transferAmount=1200000, transferType='in'))
            assert response.status_code == 200, response.json
    response = client.get(f"/api/packages/purchases/{purchase['id']}/status", headers=customer_auth_headers)
    assert response.json['purchase']['status'] == 'paid'
    assert response.json['purchase']['tengoi'] == 'Test package'
    with app.app_context():
        row = db.session.get(GoiDichVuPurchase, purchase['id'])
        assert row.snapshot_json == snapshot
        record = TheLieuTrinh.query.filter_by(purchase_id=row.id).one()
        assert record.expires_at == ps.add_months(record.activated_at, 8)
        assert record.items[0].total_sessions == 5
        assert row.created_by_staff == catalog['receptionist']
        if method == 'cash':
            assert row.confirmed_by_staff == catalog['receptionist']


@pytest.mark.parametrize('field', ['customer_sale_enabled', 'staff_sale_enabled'])
@pytest.mark.parametrize('value', ['abc', 'false', 0, 1, None, [], {}])
@pytest.mark.parametrize('method', ['POST', 'PUT'])
def test_sales_flags_require_json_booleans(app, client, catalog, admin_auth_headers, field, value, method):
    path = '/api/admin/packages' + (f"/{catalog['package']}" if method == 'PUT' else '')
    response = client.open(path, method=method, headers=admin_auth_headers,
        json=package_body(catalog, **{field: value}))
    assert response.status_code == 400, response.json
    assert f'{field} phải là boolean' in response.json['message']
    with app.app_context():
        assert GoiDichVu.query.count() == 1
        assert db.session.get(GoiDichVu, catalog['package']).customer_sale_enabled is True
        assert db.session.get(GoiDichVu, catalog['package']).staff_sale_enabled is True


@pytest.mark.parametrize('multipart', [False, True])
def test_admin_flags_round_trip_defaults_and_omitted_flags(app, client, catalog, admin_auth_headers, multipart):
    def send(method, url, body):
        kwargs = {'data': {'data': json.dumps(body)}} if multipart else {'json': body}
        return client.open(url, method=method, headers=admin_auth_headers, **kwargs)
    created = send('POST', '/api/admin/packages', package_body(catalog))
    assert created.status_code == 201, created.json
    assert created.json['package']['customer_sale_enabled'] is True
    assert created.json['package']['staff_sale_enabled'] is True
    url = f"/api/admin/packages/{catalog['package']}"
    saved = send('PUT', url, package_body(catalog, customer_sale_enabled=False, staff_sale_enabled=True))
    assert saved.status_code == 200, saved.json
    reloaded = client.get(url, headers=admin_auth_headers).json['package']
    assert reloaded['active'] is True
    assert reloaded['customer_sale_enabled'] is False
    assert reloaded['staff_sale_enabled'] is True
    saved = send('PUT', url, package_body(catalog))
    assert saved.json['package']['customer_sale_enabled'] is False
    assert saved.json['package']['staff_sale_enabled'] is True
    assert catalog['package'] not in [p['magoi'] for p in client.get('/api/packages').json['packages']]
    assert catalog['package'] in [p['magoi'] for p in client.get('/api/admin/package-sales/packages', headers=catalog['headers']).json['packages']]


def test_sale_permissions_do_not_grant_package_management(app, client, catalog, customer_auth_headers, staff_auth_headers):
    for headers in (customer_auth_headers, staff_auth_headers):
        for path in ('/api/admin/package-sales/packages', '/api/admin/package-sales'):
            assert client.get(path, headers=headers).status_code == 403
        assert client.post('/api/admin/package-sales', headers=headers,
            json=dict(makh=catalog['customer'], magoi=catalog['package'], payment_method='cash')).status_code == 403
    for method, url in [('POST', '/api/admin/packages'), ('PUT', f"/api/admin/packages/{catalog['package']}")]:
        assert client.open(url, method=method, headers=catalog['headers'],
            json=package_body(catalog, customer_sale_enabled=False)).status_code == 403
    with app.app_context():
        db.session.get(NhanVien, catalog['receptionist']).trangthai = False
        db.session.commit()
    assert client.get('/api/admin/package-sales/packages', headers=catalog['headers']).status_code == 403
    assert client.get('/api/admin/package-sales/packages').status_code == 401


@pytest.mark.parametrize('channel', ['customer', 'staff'])
def test_inactive_service_blocks_both_sale_channels(app, catalog, channel):
    with app.app_context():
        db.session.get(DichVu, catalog['service']).active = False
        with pytest.raises(AppointmentValidationError, match='dịch vụ đã ngừng cung cấp'):
            ps.create_purchase(catalog['package'], catalog['customer'], 'cash', sale_channel=channel)
        assert GoiDichVuPurchase.query.count() == 0


def test_unknown_sale_channel_is_rejected(app, catalog):
    with app.app_context():
        with pytest.raises(AppointmentValidationError, match='Kênh bán gói không hợp lệ'):
            ps.create_purchase(catalog['package'], catalog['customer'], 'cash', sale_channel='other')
        assert GoiDichVuPurchase.query.count() == 0


@pytest.mark.parametrize('state', ['web_off', 'stopped', 'archived'])
@pytest.mark.parametrize('source', ['package', 'gift'])
@pytest.mark.parametrize('action', ['cancel', 'complete'])
def test_existing_treatment_booking_gift_and_ledger_ignore_sale_flags(app, client, catalog,
        customer_auth_headers, admin_auth_headers, state, source, action):
    with app.app_context():
        purchase = ps.create_purchase(catalog['package'], catalog['customer'], 'cash')
        _, record, _ = ps.confirm_purchase(purchase.id, 1200000, method='cash')
        record_id, item_id = record.mathe, record.items[0].id
        db.session.commit()
    set_flags(app, catalog, active=state != 'archived', customer=False, staff=state == 'web_off')
    if source == 'gift':
        response = client.post(f'/api/admin/packages/treatments/{record_id}/gifts', headers=admin_auth_headers,
            json=dict(madv=catalog['service'], quantity=2, gift_note='Quà tặng sau khi ngừng bán'))
        assert response.status_code == 201, response.json
        item_id = response.json['item_id']
    listing = client.get('/api/packages/my-treatments', headers=customer_auth_headers).json['treatments']
    assert [t['mathe'] for t in listing] == [record_id]
    detail = client.get(f'/api/packages/my-treatments/{record_id}', headers=customer_auth_headers).json['treatment']
    item = next(i for i in detail['items'] if i['id'] == item_id)
    assert item['usable'] is True and item['available_sessions'] > 0
    response = client.post('/api/appointments/create', headers=customer_auth_headers,
        json=dict(madv_list=[catalog['service']], ngaygio=catalog['slot'].isoformat(),
            package_usages=[dict(mathe=record_id, madv=catalog['service'], the_item_id=item_id, quantity=1)]))
    assert response.status_code == 201, response.json
    appointment_id = response.json['appointment']['malh']
    with app.app_context():
        assert LieuTrinhUsage.query.one().state == 'reserved'
    response = client.post(f'/api/admin/appointments/{appointment_id}/{action}', headers=admin_auth_headers, json={})
    assert response.status_code == 200, response.json
    with app.app_context():
        assert LieuTrinhUsage.query.one().state == ('released' if action == 'cancel' else 'consumed')
        counts = ps.item_counts(db.session.get(TheLieuTrinhItem, item_id))
        assert counts['reserved'] == 0
        assert counts['available_sessions'] == item['available_sessions'] - int(action == 'complete')


def test_package_form_explains_independent_sale_flags(client):
    page = client.get('/admin/packages/new').get_data(as_text=True)
    for text in ('name="customer_sale_enabled"', 'name="staff_sale_enabled"',
            'Cho phép bán trên website', 'Cho phép nhân viên bán tại quầy', 'Gói đang hoạt động',
            'Liệu trình đã mua vẫn được sử dụng.'):
        assert text in page
    assert 'id="salePackageSearch"' in client.get('/admin/package-sales').get_data(as_text=True)

from datetime import datetime
from decimal import Decimal

import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import (DichVu, HoaDon, ChiTietHoaDon, GoiDichVuPurchase, LichHen,
                        GoiDichVu, ThanhToan, NhanVien, TheLieuTrinh)
from app.services import package_service


@pytest.fixture
def billing_records(app):
    with app.app_context():
        service = DichVu(tendv='Massage receipt', gia=300000, thoiluong=60, active=True)
        db.session.add(service)
        db.session.flush()
        package = package_service.save_package(dict(tengoi='Combo 10 buổi', giagoi=230000,
            validity_months=None, items=[dict(madv=service.madv, total_sessions=10)]))
        purchase = package_service.create_purchase(package.magoi, app.config['TEST_CUSTOMER_ID'], 'cash')
        invoice = HoaDon(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_ADMIN_ID'],
            tongtien=300000, ngaylap=datetime(2026, 10, 3, 0, 16), trangthai='Chưa thanh toán')
        db.session.add(invoice)
        db.session.flush()
        db.session.add(ChiTietHoaDon(mahd=invoice.mahd, madv=service.madv, soluong=1,
            dongia=300000, thanhtien=300000))
        purchase.created_at = datetime(2026, 10, 3, 7, 17)
        package_service.confirm_purchase(purchase.id, purchase.amount, method='cash', cash_received=240000)
        purchase.paid_at = datetime(2026, 10, 3, 7, 18)
        db.session.commit()
        return dict(service=invoice.mahd, package=purchase.id, catalog=package.magoi)


def listing(client, headers, query=''):
    response = client.get('/api/admin/billing/transactions' + query, headers=headers)
    assert response.status_code == 200, response.json
    return response.json


def test_unified_sources_identity_sort_stats(app, client, admin_auth_headers, billing_records):
    result = listing(client, admin_auth_headers)
    assert len(result['transactions']) == 2
    assert result['stats'] == dict(total=2, paid=1, unpaid=1, revenue='230000.00')
    package, invoice = result['transactions']
    assert package['transaction_type'] == 'package'
    assert invoice['transaction_type'] == 'service'
    assert invoice['code'] == f"HD{billing_records['service']:06d}"
    assert package['code'] == f"PG{billing_records['package']:06d}"
    assert package['source_label'] == 'Khách mua online'
    assert package['cash_received'] == '240000.00'
    assert Decimal(package['change']) == 10000
    assert invoice['created_at'] == '2026-10-03T07:16:00+07:00'
    for row in result['transactions']:
        detail = client.get(row['detail_url'], headers=admin_auth_headers)
        assert detail.status_code == 200
        assert detail.json['transaction'] == row
    with app.app_context():
        assert HoaDon.query.count() == GoiDichVuPurchase.query.count() == 1
        assert ThanhToan.query.count() == 0  # Merely reading cannot generate payments.


@pytest.mark.parametrize('query,kind,total,paid,unpaid,revenue', [
    ('?type=service', 'service', 1, 0, 1, '0'),
    ('?type=package', 'package', 1, 1, 0, '230000.00'),
    ('?status=paid', 'package', 1, 1, 0, '230000.00'),
    ('?status=unpaid', 'service', 1, 0, 1, '0'),
    ('?type=all&status=Chưa thanh toán', 'service', 1, 0, 1, '0'),
])
def test_filters_and_stats(client, admin_auth_headers, billing_records, query, kind, total, paid, unpaid, revenue):
    result = listing(client, admin_auth_headers, query)
    assert {row['transaction_type'] for row in result['transactions']} == {kind}
    assert result['stats'] == dict(total=total, paid=paid, unpaid=unpaid, revenue=revenue)


def test_search_both_sources_and_codes(client, admin_auth_headers, billing_records):
    for query in ['Test', '0900000002']:
        assert len(listing(client, admin_auth_headers, '?search=' + query)['transactions']) == 2
    for prefix, key in [('HD', 'service'), ('PG', 'package')]:
        rows = listing(client, admin_auth_headers, f"?search={prefix}{billing_records[key]:06d}")['transactions']
        assert len(rows) == 1
        assert rows[0]['transaction_type'] == key
    assert len(listing(client, admin_auth_headers, '?search=Combo')['transactions']) == 1
    assert listing(client, admin_auth_headers, '?search=does-not-exist')['stats']['total'] == 0


def test_local_date_boundaries(client, admin_auth_headers, billing_records):
    assert len(listing(client, admin_auth_headers, '?start_date=2026-10-03&end_date=2026-10-03')['transactions']) == 2
    assert listing(client, admin_auth_headers, '?end_date=2026-10-02')['transactions'] == []
    assert listing(client, admin_auth_headers, '?start_date=2026-10-04')['transactions'] == []
    for query in ['?type=invalid', '?status=invalid', '?start_date=wrong', '?start_date=2026-10-04&end_date=2026-10-03']:
        assert client.get('/api/admin/billing/transactions' + query, headers=admin_auth_headers).status_code == 400


def test_snapshot_and_failed_receipts_preserved(app, client, admin_auth_headers, billing_records):
    with app.app_context():
        db.session.get(GoiDichVu, billing_records['catalog']).tengoi = 'Changed catalog name'
        db.session.get(GoiDichVuPurchase, billing_records['package']).status = 'failed'
        db.session.commit()
    result = listing(client, admin_auth_headers, '?type=package')
    row = result['transactions'][0]
    assert row['package_name'] == 'Combo 10 buổi'
    assert row['status'] == 'Thất bại'
    assert row['can_pay'] is False
    assert result['stats']['revenue'] == '0'


def test_service_cash_receipt_and_legacy_notes(app, client, admin_auth_headers, billing_records):
    invoice_id = billing_records['service']
    assert client.post(f'/api/admin/invoices/{invoice_id}/record-payment', headers=admin_auth_headers,
                       json=dict(sotien=350000, phuongthuc='Tiền mặt')).status_code == 201
    url = f'/api/admin/billing/transactions/service/{invoice_id}'
    transaction = client.get(url, headers=admin_auth_headers).json['transaction']
    assert Decimal(transaction['cash_received']) == 350000
    assert Decimal(transaction['change']) == 50000
    assert transaction['paid_at']
    assert transaction['can_pay'] is False
    for note in ('Old free-text note', '{"cash_received":"invalid"}', '{"cash_received":"NaN"}'):
        with app.app_context():
            ThanhToan.query.filter_by(mahd=invoice_id).one().ghichu = note
            db.session.commit()
        assert client.get(url, headers=admin_auth_headers).json['transaction']['cash_received'] is None


def test_pending_package_can_resume_existing_payment(app, client, admin_auth_headers):
    with app.app_context():
        service = DichVu(tendv='Package cash', gia=100000, active=True)
        db.session.add(service)
        db.session.flush()
        package = package_service.save_package(dict(tengoi='Pending package', giagoi=100000,
            validity_months=8, items=[dict(madv=service.madv, total_sessions=2)]))
        purchase = package_service.create_purchase(package.magoi, app.config['TEST_CUSTOMER_ID'], 'cash')
        db.session.commit()
        purchase_id = purchase.id
    row = listing(client, admin_auth_headers)['transactions'][0]
    assert row['can_pay'] and row['status'] == 'Chưa thanh toán'
    endpoint = f'/api/admin/packages/purchases/{purchase_id}/confirm-payment'
    for _ in range(2):
        assert client.post(endpoint, headers=admin_auth_headers, json={'cash_received': 110000}).status_code == 200
    row = listing(client, admin_auth_headers)['transactions'][0]
    assert row['status'] == 'Đã thanh toán' and not row['can_pay']
    with app.app_context():
        assert GoiDichVuPurchase.query.count() == TheLieuTrinh.query.count() == 1


def test_permissions_and_missing_details(client, staff_auth_headers, customer_auth_headers, admin_auth_headers, billing_records):
    for headers in (staff_auth_headers, customer_auth_headers):
        assert client.get('/api/admin/billing/transactions', headers=headers).status_code == 403
        assert client.get('/api/admin/billing/transactions/package/1', headers=headers).status_code == 403
    assert client.get('/api/admin/billing/transactions').status_code == 401
    for suffix in ('service/9999', 'package/9999', 'unknown/1'):
        assert client.get('/api/admin/billing/transactions/' + suffix, headers=admin_auth_headers).status_code == 404


def test_invoice_page_uses_unified_receipt(client):
    response = client.get('/admin/invoices')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="typeFilter"' in html
    assert '<dialog id="invoiceDetailModal"' in html
    assert 'invoice-receipt.js' in html and 'invoice-receipt.css' in html
    assert 'id="receiptPrint"' in html and 'id="receiptPay"' in html
    assert 'info-card' not in html


@pytest.mark.parametrize('role', ['manager', 'letan'])
def test_billing_allowed_staff_roles(app, client, billing_records, role):
    with app.app_context():
        staff = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        staff.role = role
        db.session.commit()
        token = create_access_token(identity=f'staff:{staff.manv}')
    headers = {'Authorization': f'Bearer {token}'}
    assert len(listing(client, headers)['transactions']) == 2
    assert client.get('/api/admin/billing/transactions/package/' + str(billing_records['package']), headers=headers).status_code == 200


def test_search_appointment_id(app, client, admin_auth_headers, billing_records):
    with app.app_context():
        appointment = LichHen(malh=56, makh=app.config['TEST_CUSTOMER_ID'],
            manv=app.config['TEST_STAFF_ID'], ngaygio=datetime(2026, 10, 3, 10), trangthai='completed')
        db.session.add(appointment)
        db.session.flush()
        db.session.get(HoaDon, billing_records['service']).malh = appointment.malh
        db.session.commit()
    rows = listing(client, admin_auth_headers, '?search=56')['transactions']
    assert len(rows) == 1 and rows[0]['transaction_type'] == 'service'
    assert rows[0]['appointment_id'] == 56

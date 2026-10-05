"""Đặt lịch có thanh toán ngay bằng VietQR; khách mua gói online chỉ VietQR."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import HoaDon, LichHen, ChiTietHoaDon, KhachHang
from app.services import vietqr_service, package_service as ps

from test_phase4_packages_care import package_data, activate  # noqa: F401


@pytest.fixture
def qr(app, package_data):
    app.config.update(VIETQR_BANK_ID='970416', VIETQR_ACCOUNT_NO='27572201', VIETQR_ACCOUNT_NAME='DANG VAN KHOA')
    return package_data


def book(client, headers, data, services=None, option='prepay', usages=None):
    return client.post('/api/appointments/create', headers=headers, json={
        'madv_list': services or [data['service'], data['other_service']],
        'ngaygio': data['slot'].strftime('%Y-%m-%dT%H:%M'),
        'package_usages': usages or [], 'payment_option': option})


def sepay(client, mahd, amount, tx='TX1'):
    return client.post('/api/payment/webhook/sepay', headers={'Authorization': 'Apikey test-sepay-key'},
                       json={'id': tx, 'content': f'HD{mahd}', 'transferAmount': amount, 'transferType': 'in'})


def test_prepay_creates_invoice_and_completion_needs_no_new_payment(app, client, customer_auth_headers, admin_auth_headers, qr):
    r = book(client, customer_auth_headers, qr)
    assert r.status_code == 201, r.json
    mahd, malh = r.json['appointment']['invoice_id'], r.json['appointment']['malh']
    with app.app_context():
        invoice = db.session.get(HoaDon, mahd)
        assert invoice.malh == malh and invoice.trangthai == 'Chưa thanh toán' and invoice.tongtien == 600000
        assert ChiTietHoaDon.query.filter_by(mahd=mahd).count() == 2
    qr_res = client.post(f'/api/payment/invoices/{mahd}/generate-qr', headers=customer_auth_headers)
    assert qr_res.status_code == 200 and '970416-27572201' in qr_res.json['qrCodeUrl'] and qr_res.json['description'] == f'HD{mahd}'
    assert sepay(client, mahd, 600000).status_code == 200
    row = next(a for a in client.get('/api/appointments/my-appointments', headers=customer_auth_headers).json['appointments'] if a['malh'] == malh)
    assert row['invoice']['trangthai'] == 'Đã thanh toán' and row['can_change_services'] is False
    admin_row = next(a for a in client.get('/api/admin/appointments', headers=admin_auth_headers).json if a['malh'] == malh)
    assert admin_row['prepaid'] is True and admin_row['permissions']['canChangeServices'] is False
    # Hoàn thành dịch vụ: không phải tạo/thu hóa đơn mới.
    assert client.post(f'/api/admin/appointments/{malh}/complete', headers=admin_auth_headers).status_code == 200
    detail = client.get(f'/api/admin/appointments/{malh}', headers=admin_auth_headers).json['appointment']
    assert detail['payment_status'] == 'Đã thanh toán'
    assert detail['permissions']['canViewInvoice'] and not detail['permissions']['canCreateInvoice'] and not detail['permissions']['canPayInvoice']
    created = client.post(f'/api/admin/appointments/{malh}/create-invoice', headers=admin_auth_headers)
    assert created.json.get('invoice_id', mahd) == mahd
    with app.app_context():
        assert HoaDon.query.filter_by(malh=malh).count() == 1


def test_at_spa_keeps_old_flow(app, client, customer_auth_headers, qr):
    r = book(client, customer_auth_headers, qr, option='at_spa')
    assert r.status_code == 201 and r.json['appointment']['invoice_id'] is None
    with app.app_context():
        assert HoaDon.query.count() == 0
    assert book(client, customer_auth_headers, qr, option='bitcoin').status_code == 400


def test_prepay_excludes_package_sessions(app, client, customer_auth_headers, admin_auth_headers, qr):
    record = activate(client, customer_auth_headers, admin_auth_headers, qr)
    r = book(client, customer_auth_headers, qr, usages=[dict(mathe=record, madv=qr['service'], quantity=1)])
    assert r.status_code == 201, r.json
    with app.app_context():
        invoice = db.session.get(HoaDon, r.json['appointment']['invoice_id'])
        assert invoice.tongtien == 300000 and [d.madv for d in invoice.chitiet] == [qr['other_service']]
    only_package = book(client, customer_auth_headers, qr, services=[qr['service']],
                        usages=[dict(mathe=record, madv=qr['service'], quantity=1)])
    assert only_package.status_code == 201 and only_package.json['appointment']['invoice_id'] is None


def test_prepay_requires_vietqr(app, client, customer_auth_headers, package_data):
    app.config.update(VIETQR_BANK_ID='', VIETQR_ACCOUNT_NO='', VIETQR_ACCOUNT_NAME='')
    assert book(client, customer_auth_headers, package_data).status_code == 503


def test_unpaid_prepay_follows_service_change_and_cancel(app, client, customer_auth_headers, qr):
    r = book(client, customer_auth_headers, qr)
    mahd, malh = r.json['appointment']['invoice_id'], r.json['appointment']['malh']
    assert client.put(f'/api/appointments/{malh}/services', headers=customer_auth_headers,
                      json={'madv_list': [qr['service']]}).status_code == 200
    with app.app_context():
        assert db.session.get(HoaDon, mahd).tongtien == 300000
    r = client.put(f'/api/appointments/{malh}/cancel', headers=customer_auth_headers)
    assert r.status_code == 200 and r.json['refund_required'] is False
    with app.app_context():
        assert db.session.get(HoaDon, mahd).trangthai == 'Đã hủy'
    assert client.post(f'/api/payment/invoices/{mahd}/generate-qr', headers=customer_auth_headers).status_code == 400
    # Tiền về sau khi đã hủy: không tự đánh dấu đã thanh toán.
    res = sepay(client, mahd, 300000, tx='LATE')
    assert res.json['status'] == 'failed'
    with app.app_context():
        assert db.session.get(HoaDon, mahd).trangthai == 'Đã hủy'


def test_paid_prepay_cancel_flags_refund(app, client, customer_auth_headers, qr):
    r = book(client, customer_auth_headers, qr)
    mahd, malh = r.json['appointment']['invoice_id'], r.json['appointment']['malh']
    sepay(client, mahd, 600000)
    assert client.put(f'/api/appointments/{malh}/services', headers=customer_auth_headers,
                      json={'madv_list': [qr['service']]}).status_code == 400
    r = client.put(f'/api/appointments/{malh}/cancel', headers=customer_auth_headers)
    assert r.status_code == 200 and r.json['refund_required'] is True and 'hoàn tiền' in r.json['message']
    with app.app_context():
        assert db.session.get(HoaDon, mahd).trangthai == 'Đã thanh toán'
        assert 'Cần hoàn tiền' in db.session.get(LichHen, malh).ghichu


def test_customer_package_purchase_is_vietqr_only(app, client, customer_auth_headers, qr):
    app.config['PACKAGE_CUSTOMER_CASH_ENABLED'] = False
    r = client.post(f"/api/packages/{qr['id']}/purchase", headers=customer_auth_headers, json={'payment_method': 'cash'})
    assert r.status_code == 400 and 'VietQR' in r.json['message']
    r = client.post(f"/api/packages/{qr['id']}/purchase", headers=customer_auth_headers, json={'payment_method': 'vietqr'})
    assert r.status_code == 201 and r.json['purchase']['payment']['qrCodeUrl'].startswith('https://img.vietqr.io/image/970416-27572201')
    with open('app/static/js/packages.js', encoding='utf-8') as f:
        js = f.read()
    assert '<option value="cash"' not in js.split('async function loadCustomerPackages')[1].split('function treatmentHtml')[0]

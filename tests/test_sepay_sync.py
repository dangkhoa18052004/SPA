"""Đồng bộ giao dịch SePay khi webhook không tới máy chủ (mock userapi)."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import HoaDon, ThanhToan, PaymentWebhookEvent
from app.services import sepay_sync_service, package_service as ps


class Resp:
    def __init__(self, transactions, status=200):
        self.status_code, self._t = status, transactions

    def json(self):
        return {'status': 200, 'transactions': self._t}


def tx(tx_id, content, amount, minutes_ago=1):
    when = ps.local_now() - timedelta(minutes=minutes_ago)
    return {'id': str(tx_id), 'transaction_date': when.strftime('%Y-%m-%d %H:%M:%S'), 'account_number': '27572201',
            'amount_in': f'{amount}.00', 'amount_out': '0.00', 'transaction_content': content, 'reference_number': 'R'}


@pytest.fixture
def invoice(app, monkeypatch):
    app.config.update(SEPAY_POLL_ENABLED=True, SEPAY_API_KEY='test-sepay-key', VIETQR_ACCOUNT_NO='27572201')
    monkeypatch.setattr(sepay_sync_service, '_last_run', 0.0)
    with app.app_context():
        row = HoaDon(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'], tongtien=150000,
                     trangthai='Chưa thanh toán')
        db.session.add(row); db.session.commit()
        return row.mahd


def test_sync_pays_invoice_once_and_is_idempotent(app, invoice, monkeypatch):
    calls = []
    data = [tx(87190190, f'150183800144 HD{invoice} CHUYEN TIEN MOMO', 150000), tx(87173779, 'chuyen tien qua MoMo', 10000)]
    monkeypatch.setattr(sepay_sync_service.requests, 'get', lambda url, **kw: calls.append(kw) or Resp(data))
    with app.app_context():
        assert sepay_sync_service.sync() == 2
        assert sepay_sync_service.sync() == 0          # đã xử lý: không lặp
        assert db.session.get(HoaDon, invoice).trangthai == 'Đã thanh toán'
        assert ThanhToan.query.filter_by(mahd=invoice).count() == 1
        assert PaymentWebhookEvent.query.filter_by(provider='sepay').count() == 2
    assert calls[0]['headers']['Authorization'] == 'Bearer test-sepay-key'
    assert calls[0]['params']['account_number'] == '27572201'


def test_webhook_and_sync_do_not_double_count(app, client, invoice, monkeypatch):
    item = tx(555, f'HD{invoice}', 150000)
    r = client.post('/api/payment/webhook/sepay', headers={'Authorization': 'Apikey test-sepay-key'},
                    json={'id': '555', 'content': f'HD{invoice}', 'transferAmount': 150000, 'transferType': 'in'})
    assert r.status_code == 200
    monkeypatch.setattr(sepay_sync_service.requests, 'get', lambda url, **kw: Resp([item]))
    with app.app_context():
        assert sepay_sync_service.sync() == 0
        assert ThanhToan.query.filter_by(mahd=invoice).count() == 1


def test_old_and_underpaid_transactions_are_not_applied(app, invoice, monkeypatch):
    data = [tx(1, f'HD{invoice}', 150000, minutes_ago=60 * 72), tx(2, f'HD{invoice}', 100000)]
    monkeypatch.setattr(sepay_sync_service.requests, 'get', lambda url, **kw: Resp(data))
    with app.app_context():
        sepay_sync_service.sync()
        assert db.session.get(HoaDon, invoice).trangthai == 'Chưa thanh toán'


def test_customer_invoice_polling_triggers_sync(app, client, customer_auth_headers, invoice, monkeypatch):
    monkeypatch.setattr(sepay_sync_service.requests, 'get', lambda url, **kw: Resp([tx(9, f'HD{invoice}', 150000)]))
    r = client.get(f'/api/payment/invoices/{invoice}', headers=customer_auth_headers)
    assert r.status_code == 200 and r.json['trangthai'] == 'Đã thanh toán'


def test_disabled_or_network_error_is_safe(app, invoice, monkeypatch):
    def boom(*a, **k):
        raise sepay_sync_service.requests.ConnectionError()
    monkeypatch.setattr(sepay_sync_service.requests, 'get', boom)
    with app.app_context():
        assert sepay_sync_service.sync() == 0
        app.config['SEPAY_POLL_ENABLED'] = False
        assert sepay_sync_service.maybe_sync(min_interval=0) == 0

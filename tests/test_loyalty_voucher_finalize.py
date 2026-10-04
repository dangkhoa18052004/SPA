"""Payment finalization with voucher + direct points: cash, VietQR/SePay, zero payable, receipt, earn."""
import json
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (HoaDon, GoiDichVuPurchase, ThanhToan, TheLieuTrinh, LoyaltyPointTransaction,
                        LoyaltyRedemptionReservation, LoyaltyRewardRedemption, LoyaltyWallet)
from app.services import loyalty_service as loyalty
from test_loyalty_payments import package_id  # noqa: F401  (fixture)
from test_loyalty_service import fund, invariant

SEPAY = {'Authorization': 'Apikey test-sepay-key'}


@pytest.fixture
def setup(app):
    app.config.update(VIETQR_BANK_ID='970407', VIETQR_ACCOUNT_NO='1234', VIETQR_ACCOUNT_NAME='BIN SPA')
    with app.app_context():
        fund(app, 1000)
        db.session.commit()
    keys = iter(range(1000))

    def voucher(value=50000):
        with app.app_context():
            reward = loyalty.save_reward(dict(name=f'Voucher {value}', reward_type='voucher_amount', points_cost=50, reward_value=value))
            redemption = loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], reward.id, f'k{next(keys)}')
            db.session.commit()
            return redemption.id
    return voucher


def discount(client, headers, base, redemption_id=None, points=0):
    if redemption_id:
        assert client.post(base + '/reward', headers=headers, json={'redemption_id': redemption_id}).status_code == 200
    if points:
        assert client.post(base + '/loyalty', headers=headers, json={'points': points}).status_code == 200
    return client.get(base + '/loyalty', headers=headers).json


def ledger(app, kind, source_id):
    with app.app_context():
        rows = LoyaltyPointTransaction.query.filter_by(source_type=kind, source_id=source_id).order_by(LoyaltyPointTransaction.id).all()
        return [(row.type, row.points_delta) for row in rows]


def voucher_state(app, rid):
    with app.app_context():
        row = db.session.get(LoyaltyRewardRedemption, rid)
        return row.status, row.used_at is not None


def reservation_status(app):
    with app.app_context():
        return [row.status for row in LoyaltyRedemptionReservation.query.all()]


def test_cash_voucher_and_points_finalize_once(app, client, admin_auth_headers, create_invoice, setup):
    invoice, rid = create_invoice(500000), setup(50000)
    base = f'/api/admin/invoices/{invoice}'
    state = discount(client, admin_auth_headers, base, rid, 100)
    assert [Decimal(state[k]) for k in ('original_total', 'reward_discount', 'loyalty_discount', 'payable_amount')] == [500000, 50000, 100000, 350000]
    short = client.post(base + '/record-payment', headers=admin_auth_headers, json={'sotien': 349999, 'phuongthuc': 'Tiền mặt'})
    assert short.status_code == 400 and voucher_state(app, rid) == ('reserved', False)
    paid = client.post(base + '/record-payment', headers=admin_auth_headers, json={'sotien': 400000, 'phuongthuc': 'Tiền mặt'})
    assert paid.status_code == 201, paid.json
    again = client.post(base + '/record-payment', headers=admin_auth_headers, json={'sotien': 400000, 'phuongthuc': 'Tiền mặt'})
    assert again.status_code in (400, 409)
    with app.app_context():
        payment = ThanhToan.query.one()
        assert payment.sotien == 350000 and json.loads(payment.ghichu)['cash_received'] == '400000'
        assert db.session.get(HoaDon, invoice).trangthai == 'Đã thanh toán'
        invariant(app)
    assert voucher_state(app, rid) == ('used', True)
    assert reservation_status(app) == ['consumed']
    assert ledger(app, 'service_invoice', invoice) == [('redeem', -100), ('earn', 30)]
    row = client.get(f'/api/admin/billing/transactions/service/{invoice}', headers=admin_auth_headers).json['transaction']
    assert (Decimal(row['original_total']), Decimal(row['reward_discount']), Decimal(row['loyalty_discount'])) == (500000, 50000, 100000)
    assert (Decimal(row['payable_amount']), Decimal(row['cash_received']), Decimal(row['change'])) == (350000, 400000, 50000)
    assert (row['points_used'], row['points_earned'], row['payment_method']) == (100, 30, 'Tiền mặt')
    assert row['reward_redemption_id'] == rid and row['reward_code'].startswith('BIN-')
    # A used voucher can never be applied again, and the paid invoice cannot change discounts.
    assert client.post(f'/api/admin/invoices/{create_invoice(500000)}/reward', headers=admin_auth_headers,
                       json={'redemption_id': rid}).status_code == 400
    assert client.delete(base + '/reward', headers=admin_auth_headers).status_code == 400


def test_qr_uses_payable_and_unconfirmed_payment_keeps_reservations(app, client, admin_auth_headers, customer_auth_headers,
                                                                    create_invoice, setup):
    invoice, rid = create_invoice(500000), setup(50000)
    discount(client, customer_auth_headers, f'/api/payment/invoices/{invoice}', rid, 100)
    for headers, url in ((admin_auth_headers, f'/api/admin/invoices/{invoice}/generate-qr'),
                         (customer_auth_headers, f'/api/payment/invoices/{invoice}/generate-qr')):
        qr = client.post(url, headers=headers, json={})
        assert qr.status_code == 200 and qr.json['amount'] == 350000 and 'amount=350000' in qr.json['qrCodeUrl']
    # QR generation is not payment: nothing is finalized yet.
    with app.app_context():
        assert db.session.get(HoaDon, invoice).trangthai == 'Chưa thanh toán' and ThanhToan.query.count() == 0
        wallet = LoyaltyWallet.query.one()
        assert (wallet.available_points, wallet.reserved_points) == (850, 100)
    assert voucher_state(app, rid) == ('reserved', False) and reservation_status(app) == ['reserved']
    assert ledger(app, 'service_invoice', invoice) == []
    # An underpaid transfer is rejected and leaves every reservation in place.
    short = client.post('/api/payment/webhook/sepay', headers=SEPAY, json=dict(id='bank-short', content=f'HD{invoice}', transferAmount=349000))
    assert short.json['status'] == 'failed'
    assert voucher_state(app, rid) == ('reserved', False) and reservation_status(app) == ['reserved']


def test_sepay_finalizes_exactly_once_on_duplicates(app, client, customer_auth_headers, create_invoice, setup):
    invoice, rid = create_invoice(500000), setup(50000)
    discount(client, customer_auth_headers, f'/api/payment/invoices/{invoice}', rid, 100)
    payload = dict(id='bank-1', content=f'HD{invoice}', transferAmount=350000)
    assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=payload).json['status'] == 'success'
    assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=payload).json['status'] == 'duplicate'
    # A second bank transaction for the already-paid invoice is not a second payment either.
    other = dict(payload, id='bank-2')
    assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=other).json['status'] == 'duplicate'
    with app.app_context():
        assert [(p.sotien, p.phuongthuc) for p in ThanhToan.query.all()] == [(350000, 'VietQR (SePay)')]
        assert LoyaltyRewardRedemption.query.filter_by(status='used').count() == 1
        invariant(app)
    assert voucher_state(app, rid) == ('used', True) and reservation_status(app) == ['consumed']
    assert ledger(app, 'service_invoice', invoice) == [('redeem', -100), ('earn', 30)]


@pytest.mark.parametrize('method', ['cash', 'vietqr'])
def test_package_voucher_and_points_finalize(app, client, customer_auth_headers, admin_auth_headers, setup, package_id, method):
    created = client.post(f'/api/packages/{package_id}/purchase', headers=customer_auth_headers, json={'payment_method': method})
    pid = created.json['purchase']['id']
    rid = setup(50000)
    state = discount(client, customer_auth_headers, f'/api/packages/purchases/{pid}', rid, 200)
    assert Decimal(state['payable_amount']) == 950000
    if method == 'cash':
        for _ in range(2):
            result = client.post(f'/api/admin/packages/purchases/{pid}/confirm-payment', headers=admin_auth_headers,
                                 json={'cash_received': 1000000})
            assert result.status_code == 200, result.json
        assert Decimal(result.json['purchase']['change']) == 50000
    else:
        detail = client.get(f'/api/packages/purchases/{pid}', headers=customer_auth_headers).json
        assert detail['purchase']['payment']['amount'] == 950000
        payload = dict(id='pkg-1', content=f'PKG{pid}', transferAmount=950000)
        assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=payload).json['status'] == 'success'
        assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=payload).json['status'] == 'duplicate'
    with app.app_context():
        assert db.session.get(GoiDichVuPurchase, pid).status == 'paid' and TheLieuTrinh.query.count() == 1
        invariant(app)
    assert voucher_state(app, rid) == ('used', True) and reservation_status(app) == ['consumed']
    assert ledger(app, 'package_purchase', pid) == [('redeem', -200), ('earn', 90)]


def test_zero_payable_uses_points_payment_and_earns_nothing(app, client, customer_auth_headers, admin_auth_headers, create_invoice, setup):
    with app.app_context():
        loyalty.update_config({'maximum_redeem_percent': 100})
        db.session.commit()
    invoice, rid = create_invoice(500000), setup(50000)
    base = f'/api/payment/invoices/{invoice}'
    assert Decimal(discount(client, customer_auth_headers, base, rid, 450)['payable_amount']) == 0
    assert client.post(base + '/generate-qr', headers=customer_auth_headers, json={}).status_code == 400
    assert client.post(f'/api/admin/invoices/{invoice}/generate-qr', headers=admin_auth_headers, json={}).status_code == 400
    assert client.post(f'/api/admin/invoices/{invoice}/record-payment', headers=admin_auth_headers,
                       json={'sotien': 0, 'phuongthuc': 'Tiền mặt'}).status_code == 400
    for _ in range(2):
        result = client.post(base + '/pay-points', headers=customer_auth_headers, json={})
        assert result.status_code == 200 and result.json['points_earned'] == 0
    with app.app_context():
        assert db.session.get(HoaDon, invoice).trangthai == 'Đã thanh toán'
        assert [(p.sotien, p.phuongthuc) for p in ThanhToan.query.all()] == [(0, 'Điểm thưởng')]
        invariant(app)
    assert voucher_state(app, rid) == ('used', True) and reservation_status(app) == ['consumed']
    assert ledger(app, 'service_invoice', invoice) == [('redeem', -450)]


def test_zero_payable_package_by_voucher_only(app, client, customer_auth_headers, setup, package_id):
    pid = client.post(f'/api/packages/{package_id}/purchase', headers=customer_auth_headers,
                      json={'payment_method': 'vietqr'}).json['purchase']['id']
    rid = setup(1500000)
    base = f'/api/packages/purchases/{pid}'
    assert Decimal(discount(client, customer_auth_headers, base, rid)['payable_amount']) == 0
    assert 'payment' not in client.get(base, headers=customer_auth_headers).json['purchase']
    assert client.post(base + '/pay-points', headers=customer_auth_headers, json={}).status_code == 200
    with app.app_context():
        purchase = db.session.get(GoiDichVuPurchase, pid)
        assert (purchase.status, purchase.payment_method) == ('paid', 'points') and TheLieuTrinh.query.count() == 1
    assert voucher_state(app, rid) == ('used', True) and ledger(app, 'package_purchase', pid) == []


@pytest.mark.parametrize('method', ['cash', 'vietqr'])
def test_invoice_without_voucher_or_points_is_unchanged(app, client, admin_auth_headers, create_invoice, setup, method):
    invoice = create_invoice(500000)
    if method == 'cash':
        assert client.post(f'/api/admin/invoices/{invoice}/record-payment', headers=admin_auth_headers,
                           json={'sotien': 500000, 'phuongthuc': 'Tiền mặt'}).status_code == 201
    else:
        assert client.post(f'/api/admin/invoices/{invoice}/generate-qr', headers=admin_auth_headers, json={}).json['amount'] == 500000
        assert client.post('/api/payment/webhook/sepay', headers=SEPAY,
                           json=dict(id='plain', content=f'HD{invoice}', transferAmount=500000)).json['status'] == 'success'
    row = client.get(f'/api/admin/billing/transactions/service/{invoice}', headers=admin_auth_headers).json['transaction']
    assert (Decimal(row['reward_discount']), Decimal(row['loyalty_discount']), Decimal(row['payable_amount'])) == (0, 0, 500000)
    assert row['reward_redemption_id'] is None and row['points_earned'] == 50
    assert ledger(app, 'service_invoice', invoice) == [('earn', 50)]


def test_package_cash_without_voucher_is_unchanged(app, client, customer_auth_headers, admin_auth_headers, setup, package_id):
    pid = client.post(f'/api/packages/{package_id}/purchase', headers=customer_auth_headers,
                      json={'payment_method': 'cash'}).json['purchase']['id']
    result = client.post(f'/api/admin/packages/purchases/{pid}/confirm-payment', headers=admin_auth_headers, json={'cash_received': 1200000})
    assert result.status_code == 200 and Decimal(result.json['purchase']['change']) == 0
    assert ledger(app, 'package_purchase', pid) == [('earn', 120)]

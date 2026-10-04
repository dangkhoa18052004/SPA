"""Applying fixed-amount vouchers to payments: scope, minimum spend, ownership, reservation, points."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import HoaDon, KhachHang, LoyaltyRewardRedemption
from app.services import loyalty_service as loyalty
from test_loyalty_payments import package_id  # noqa: F401  (fixture)
from test_loyalty_service import fund, invariant

INVOICE = '/api/payment/invoices/{}'
PACKAGE = '/api/packages/purchases/{}'


@pytest.fixture
def funded(app):
    with app.app_context():
        fund(app, 1000)
        db.session.commit()


@pytest.fixture
def voucher(app, funded):
    """Redeem a voucher for a customer (default: the test customer) and return its redemption id."""
    count = iter(range(1000))

    def factory(value=50000, makh=None, points=50, **terms):
        with app.app_context():
            makh = makh or app.config['TEST_CUSTOMER_ID']
            reward = loyalty.save_reward(dict(name=f'Voucher {value}', reward_type='voucher_amount', points_cost=points,
                                              reward_value=value, **terms))
            redemption = loyalty.redeem_reward(makh, reward.id, f'key-{next(count)}')
            db.session.commit()
            return redemption.id
    return factory


def purchase(client, headers, package):
    result = client.post(f'/api/packages/{package}/purchase', headers=headers, json={'payment_method': 'cash'})
    assert result.status_code == 201, result.json
    return result.json['purchase']['id']


def apply(client, headers, base, redemption_id):
    return client.post(base + '/reward', headers=headers, json={'redemption_id': redemption_id})


def state_of(app, redemption_id):
    with app.app_context():
        row = db.session.get(LoyaltyRewardRedemption, redemption_id)
        return row.status, row.target_type, row.target_id


def test_a_g_apply_reserves_voucher_and_reduces_payable(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(50000)
    result = apply(client, customer_auth_headers, INVOICE.format(invoice), rid)
    assert result.status_code == 200, result.json
    assert Decimal(result.json['reward_discount']) == 50000 and Decimal(result.json['payable_amount']) == 450000
    assert result.json['reward_redemption_id'] == rid
    assert state_of(app, rid) == ('reserved', 'service_invoice', invoice)
    with app.app_context():
        row = db.session.get(HoaDon, invoice)
        assert (row.reward_discount, row.payable_amount, row.trangthai) == (50000, 450000, 'Chưa thanh toán')
        assert db.session.get(LoyaltyRewardRedemption, rid).used_at is None
        invariant(app)


def test_voucher_discount_never_exceeds_original_total(client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(600000)
    result = apply(client, customer_auth_headers, INVOICE.format(invoice), rid)
    assert Decimal(result.json['reward_discount']) == 500000 and Decimal(result.json['payable_amount']) == 0


def test_b_minimum_spend_checks_original_total(app, client, customer_auth_headers, create_invoice, voucher):
    rid = voucher(50000, minimum_spend=300000)
    short = create_invoice(250000)
    result = apply(client, customer_auth_headers, INVOICE.format(short), rid)
    assert result.status_code == 400
    assert result.json['msg'] == 'Hóa đơn chưa đạt giá trị tối thiểu 300.000đ để sử dụng ưu đãi này.'
    assert state_of(app, rid) == ('available', None, None)
    with app.app_context():
        assert db.session.get(HoaDon, short).reward_discount == 0
    # Exactly the minimum qualifies.
    exact = create_invoice(300000)
    assert apply(client, customer_auth_headers, INVOICE.format(exact), rid).status_code == 200


def test_minimum_spend_message_for_package(client, customer_auth_headers, voucher, package_id):
    pid = purchase(client, customer_auth_headers, package_id)
    rid = voucher(50000, minimum_spend=2000000)
    result = apply(client, customer_auth_headers, PACKAGE.format(pid), rid)
    assert result.status_code == 400
    assert result.json['msg'] == 'Giao dịch mua gói chưa đạt giá trị tối thiểu 2.000.000đ để sử dụng ưu đãi này.'


def test_c_service_only_voucher_rejected_on_package(app, client, customer_auth_headers, voucher, package_id):
    pid = purchase(client, customer_auth_headers, package_id)
    rid = voucher(50000, apply_to='service_invoice')
    result = apply(client, customer_auth_headers, PACKAGE.format(pid), rid)
    assert result.status_code == 400 and result.json['msg'] == 'Voucher này chỉ dùng cho hóa đơn dịch vụ'
    assert state_of(app, rid) == ('available', None, None)


def test_d_package_only_voucher_rejected_on_invoice(app, client, customer_auth_headers, create_invoice, voucher):
    rid = voucher(50000, apply_to='package_purchase')
    result = apply(client, customer_auth_headers, INVOICE.format(create_invoice(500000)), rid)
    assert result.status_code == 400 and result.json['msg'] == 'Voucher này chỉ dùng cho giao dịch mua gói'
    assert state_of(app, rid) == ('available', None, None)


def test_e_both_and_legacy_snapshot_work_on_invoice_and_package(app, client, customer_auth_headers, admin_auth_headers,
                                                               create_invoice, voucher, package_id):
    invoice, pid = create_invoice(500000), purchase(client, customer_auth_headers, package_id)
    first, second = voucher(50000, apply_to='both'), voucher(100000)
    with app.app_context():
        # A redemption issued before voucher terms existed carries no apply_to/minimum_spend.
        row = db.session.get(LoyaltyRewardRedemption, second)
        row.reward_snapshot_json = {k: v for k, v in row.reward_snapshot_json.items() if k not in ('apply_to', 'minimum_spend')}
        db.session.commit()
    assert Decimal(apply(client, customer_auth_headers, INVOICE.format(invoice), first).json['payable_amount']) == 450000
    result = apply(client, admin_auth_headers, f'/api/admin/packages/purchases/{pid}', second)
    assert result.status_code == 200 and Decimal(result.json['payable_amount']) == 1100000
    assert state_of(app, second) == ('reserved', 'package_purchase', pid)


def test_f_voucher_of_another_customer_is_rejected(app, client, customer_auth_headers, admin_auth_headers, create_invoice, voucher):
    with app.app_context():
        other = KhachHang(hoten='Khách B', sdt='0900000099', email='b@example.com', taikhoan='customer_b',
                          matkhau=generate_password_hash('password'), trangthai='active')
        db.session.add(other)
        db.session.commit()
        loyalty.admin_adjust_points(other.makh, 500, 'Quà', app.config['TEST_ADMIN_ID'], 'b-initial')
        db.session.commit()
        other_id = other.makh
    foreign = voucher(50000, makh=other_id)
    invoice = create_invoice(500000)
    for headers, base in ((customer_auth_headers, INVOICE.format(invoice)), (admin_auth_headers, f'/api/admin/invoices/{invoice}')):
        result = apply(client, headers, base, foreign)
        assert result.status_code == 400 and result.json['msg'] == 'Không tìm thấy ưu đãi của khách hàng'
    # A makh sent by the client is ignored: ownership comes from the invoice.
    assert client.post(INVOICE.format(invoice) + '/reward', headers=customer_auth_headers,
                       json={'redemption_id': foreign, 'makh': other_id}).status_code == 400
    assert state_of(app, foreign) == ('available', None, None)
    with app.app_context():
        other_invoice = HoaDon(tongtien=500000, makh=other_id, manv=app.config['TEST_STAFF_ID'], trangthai='Chưa thanh toán')
        db.session.add(other_invoice)
        db.session.commit()
        other_invoice_id = other_invoice.mahd
    denied = apply(client, customer_auth_headers, INVOICE.format(other_invoice_id), voucher(50000))
    assert denied.status_code == 400 and denied.json['msg'] == 'Không tìm thấy thanh toán của khách hàng'


def test_h_reload_keeps_reservation_and_reports_voucher(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(50000)
    apply(client, customer_auth_headers, INVOICE.format(invoice), rid)
    for _ in range(2):
        state = client.get(INVOICE.format(invoice) + '/loyalty', headers=customer_auth_headers).json
        assert state['reward_redemption_id'] == rid and state['reward_name'] == 'Voucher 50000'
        assert state['reward_code'].startswith('BIN-') and Decimal(state['payable_amount']) == 450000
    detail = client.get(INVOICE.format(invoice), headers=customer_auth_headers).json
    assert Decimal(detail['payable_amount']) == 450000 and detail['reward_redemption_id'] == rid
    # Re-applying the same voucher to the same invoice is a no-op, not a second reservation.
    assert apply(client, customer_auth_headers, INVOICE.format(invoice), rid).status_code == 200
    applied = client.get('/api/loyalty/my-rewards?status=applied', headers=customer_auth_headers).json['items']
    assert [(r['id'], r['status'], r['target_id']) for r in applied] == [(rid, 'reserved', invoice)]
    assert state_of(app, rid) == ('reserved', 'service_invoice', invoice)


def test_i_remove_returns_voucher_and_restores_payable(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(50000)
    apply(client, customer_auth_headers, INVOICE.format(invoice), rid)
    result = client.delete(INVOICE.format(invoice) + '/reward', headers=customer_auth_headers)
    assert result.status_code == 200 and result.json['reward_redemption_id'] is None
    assert Decimal(result.json['reward_discount']) == 0 and Decimal(result.json['payable_amount']) == 500000
    assert state_of(app, rid) == ('available', None, None)
    # The same voucher can then be used for another payment.
    assert apply(client, customer_auth_headers, INVOICE.format(create_invoice(400000)), rid).status_code == 200


def test_remove_after_expiry_closes_voucher(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(50000, validity_days=1)
    apply(client, customer_auth_headers, INVOICE.format(invoice), rid)
    with app.app_context():
        db.session.get(LoyaltyRewardRedemption, rid).expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    result = client.delete(INVOICE.format(invoice) + '/reward', headers=customer_auth_headers)
    assert result.status_code == 200 and Decimal(result.json['payable_amount']) == 500000
    assert state_of(app, rid) == ('expired', None, None)
    closed = client.get('/api/loyalty/my-rewards?status=closed', headers=customer_auth_headers).json['items']
    assert [(r['id'], r['status']) for r in closed] == [(rid, 'expired')]


def test_j_expired_voucher_is_rejected(app, client, customer_auth_headers, create_invoice, voucher):
    rid = voucher(50000, validity_days=1)
    with app.app_context():
        db.session.get(LoyaltyRewardRedemption, rid).expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    result = apply(client, customer_auth_headers, INVOICE.format(create_invoice(500000)), rid)
    assert result.status_code == 400 and result.json['msg'] == 'Voucher đã hết hạn'
    assert state_of(app, rid) == ('available', None, None)


def test_k_point_cap_is_computed_after_voucher(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(50000)
    base = INVOICE.format(invoice)
    assert client.get(base + '/loyalty', headers=customer_auth_headers).json['max_points_allowed'] == 250
    state = apply(client, customer_auth_headers, base, rid).json
    assert state['max_points_allowed'] == 225
    preview = client.post(base + '/loyalty/preview', headers=customer_auth_headers, json={'points': 250}).json
    assert preview['points_allowed'] == 225 and Decimal(preview['payable_amount']) == 225000
    assert client.post(base + '/loyalty', headers=customer_auth_headers, json={'points': 250}).status_code == 400
    state = client.post(base + '/loyalty', headers=customer_auth_headers, json={'points': 225}).json
    assert Decimal(state['loyalty_discount']) == 225000 and Decimal(state['payable_amount']) == 225000
    with app.app_context():
        invariant(app)


def test_voucher_after_points_rejects_instead_of_shrinking_points(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, rid = create_invoice(500000), voucher(50000)
    base = INVOICE.format(invoice)
    assert client.post(base + '/loyalty', headers=customer_auth_headers, json={'points': 250}).status_code == 200
    result = apply(client, customer_auth_headers, base, rid)
    assert result.status_code == 400
    assert result.json['msg'] == 'Hãy giảm hoặc bỏ số điểm đang áp dụng trước khi sử dụng Voucher này.'
    assert state_of(app, rid) == ('available', None, None)
    state = client.get(base + '/loyalty', headers=customer_auth_headers).json
    assert state['points_used'] == 250 and Decimal(state['reward_discount']) == 0 and Decimal(state['payable_amount']) == 250000
    # Points within the post-voucher cap can stay while the voucher is applied.
    client.post(base + '/loyalty', headers=customer_auth_headers, json={'points': 200})
    state = apply(client, customer_auth_headers, base, rid).json
    assert state['points_used'] == 200 and Decimal(state['payable_amount']) == 250000
    with app.app_context():
        invariant(app)


def test_l_second_voucher_on_same_invoice_is_rejected(app, client, customer_auth_headers, create_invoice, voucher):
    invoice, first, second = create_invoice(500000), voucher(50000), voucher(30000)
    assert apply(client, customer_auth_headers, INVOICE.format(invoice), first).status_code == 200
    result = apply(client, customer_auth_headers, INVOICE.format(invoice), second)
    assert result.status_code == 400 and result.json['msg'] == 'Hãy bỏ voucher hiện tại trước khi áp dụng voucher khác'
    assert state_of(app, first) == ('reserved', 'service_invoice', invoice)
    assert state_of(app, second) == ('available', None, None)
    # The database also refuses two reserved vouchers for one payment.
    with app.app_context():
        row = db.session.get(LoyaltyRewardRedemption, second)
        row.status, row.target_type, row.target_id = 'reserved', 'service_invoice', invoice
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()


def test_voucher_reserved_elsewhere_or_physical_gift_is_rejected(app, client, customer_auth_headers, create_invoice, voucher):
    rid = voucher(50000)
    apply(client, customer_auth_headers, INVOICE.format(create_invoice(500000)), rid)
    result = apply(client, customer_auth_headers, INVOICE.format(create_invoice(500000)), rid)
    assert result.status_code == 400 and result.json['msg'] == 'Voucher đang được áp dụng cho giao dịch khác'
    with app.app_context():
        gift = loyalty.save_reward(dict(name='Khăn', reward_type='physical_gift', points_cost=50))
        gift_id = loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], gift.id, 'gift').id
        db.session.commit()
    result = apply(client, customer_auth_headers, INVOICE.format(create_invoice(500000)), gift_id)
    assert result.status_code == 400 and result.json['msg'] == 'Ưu đãi này không phải voucher giảm tiền'


def test_payment_voucher_lists_match_transaction_type(app, client, customer_auth_headers, admin_auth_headers, voucher):
    service_only, package_only, both = (voucher(50000, apply_to=scope) for scope in ('service_invoice', 'package_purchase', 'both'))
    legacy, expired = voucher(20000), voucher(10000, validity_days=1)
    with app.app_context():
        row = db.session.get(LoyaltyRewardRedemption, legacy)
        row.reward_snapshot_json = {k: v for k, v in row.reward_snapshot_json.items() if k not in ('apply_to', 'minimum_spend')}
        db.session.get(LoyaltyRewardRedemption, expired).expires_at = datetime.utcnow() - timedelta(minutes=1)
        gift = loyalty.save_reward(dict(name='Khăn', reward_type='physical_gift', points_cost=50))
        loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], gift.id, 'gift')
        db.session.commit()
        makh = app.config['TEST_CUSTOMER_ID']
    expected = dict(service_invoice={service_only, both, legacy}, package_purchase={package_only, both, legacy})
    for kind, ids in expected.items():
        mine = client.get(f'/api/loyalty/my-rewards?status=usable&usable_for={kind}&per_page=100', headers=customer_auth_headers).json
        staff = client.get(f'/api/admin/loyalty/customers/{makh}/vouchers?usable_for={kind}&per_page=100', headers=admin_auth_headers).json
        assert {r['id'] for r in mine['items']} == ids and mine['total'] == len(ids)
        assert {r['id'] for r in staff['items']} == ids and staff['total'] == len(ids)
    assert client.get('/api/loyalty/my-rewards?usable_for=gift', headers=customer_auth_headers).status_code == 400

from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import (GoiDichVuPurchase, KhachHang, TheLieuTrinh,
                        LoyaltyRedemptionReservation, LoyaltyRewardRedemption)
from app.services import loyalty_service as loyalty
from app.services.vietqr_service import process_sepay_transaction
from test_loyalty_service import fund, invariant
from test_phase4_packages_care import package_data, purchase  # noqa: F401


def cancel(client, headers, purchase_id):
    return client.post(f'/api/packages/purchases/{purchase_id}/cancel', headers=headers)


def test_pending_purchase_cancel_is_persistent_and_idempotent(app, client, customer_auth_headers, package_data):
    row = purchase(client, customer_auth_headers, package_data)
    for _ in range(2):
        response = cancel(client, customer_auth_headers, row['id'])
        assert response.status_code == 200, response.json
        assert response.json['purchase']['status'] == 'cancelled'
        assert 'payment' not in response.json['purchase']
    assert client.get(f"/api/packages/purchases/{row['id']}/status", headers=customer_auth_headers).json['purchase']['status'] == 'cancelled'
    with app.app_context():
        assert db.session.get(GoiDichVuPurchase, row['id']).status == 'cancelled'
        assert GoiDichVuPurchase.query.count() == 1  # Preserve the transaction record.
        assert TheLieuTrinh.query.count() == 0


@pytest.mark.parametrize('actor', ['foreign', 'staff', 'guest', 'missing'])
def test_cancel_requires_customer_ownership(app, client, customer_auth_headers, staff_auth_headers, package_data, actor):
    row = purchase(client, customer_auth_headers, package_data)
    purchase_id, headers, expected = row['id'], customer_auth_headers, 404
    if actor == 'foreign':
        with app.app_context():
            other = KhachHang(hoten='Other customer', sdt='0900000099', email='other-cancel@example.com', taikhoan='other_cancel', matkhau='unused', trangthai='active')
            db.session.add(other)
            db.session.flush()
            db.session.get(GoiDichVuPurchase, purchase_id).makh = other.makh
            db.session.commit()
    elif actor == 'staff':
        headers, expected = staff_auth_headers, 403
    elif actor == 'guest':
        headers, expected = {}, 401
    else:
        purchase_id += 10000
    assert cancel(client, headers, purchase_id).status_code == expected
    with app.app_context():
        assert db.session.get(GoiDichVuPurchase, row['id']).status == 'pending'


@pytest.mark.parametrize('expired', [False, True])
def test_cancel_releases_points_and_voucher_once(app, client, customer_auth_headers, package_data, expired):
    row = purchase(client, customer_auth_headers, package_data)
    with app.app_context():
        fund(app, 1000)
        reward = loyalty.save_reward(dict(name='Voucher mua gói', reward_type='voucher_amount', points_cost=50, reward_value=50000, validity_days=30))
        voucher = loyalty.redeem_reward(package_data['customer'], reward.id, 'cancel-voucher')
        target = loyalty.lock_target('package_purchase', row['id'])
        loyalty.apply_reward(target, voucher.id)
        loyalty.reserve_points(target, 100)
        if expired:
            voucher.expires_at = datetime.utcnow() - timedelta(seconds=1)
        voucher_id = voucher.id
        db.session.commit()
    for _ in range(2):
        assert cancel(client, customer_auth_headers, row['id']).status_code == 200
    with app.app_context():
        balance = loyalty.get_balance(package_data['customer'])
        assert balance['available_points'] == 950 and balance['reserved_points'] == 0
        assert LoyaltyRedemptionReservation.query.one().status == 'released'
        voucher = db.session.get(LoyaltyRewardRedemption, voucher_id)
        assert voucher.status == ('expired' if expired else 'available')
        assert voucher.target_id is None and voucher.target_type is None
        invariant(app)


def test_paid_purchase_cannot_be_cancelled(app, client, customer_auth_headers, admin_auth_headers, package_data):
    row = purchase(client, customer_auth_headers, package_data)
    paid = client.post(f"/api/admin/packages/purchases/{row['id']}/confirm-payment",
                       headers=admin_auth_headers, json={'amount': 1200000})
    assert paid.status_code == 200, paid.json
    treatment_id = paid.json['mathe']
    response = cancel(client, customer_auth_headers, row['id'])
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(GoiDichVuPurchase, row['id']).status == 'paid'
        assert db.session.get(TheLieuTrinh, treatment_id).status == 'active'


def test_cancelled_purchase_rejects_late_payment_without_activation(app, client, customer_auth_headers, package_data):
    row = purchase(client, customer_auth_headers, package_data, 'vietqr')
    assert cancel(client, customer_auth_headers, row['id']).status_code == 200
    with app.app_context():
        response = process_sepay_transaction(dict(id=987654, content=f"PKG{row['id']}", transferType='in', transferAmount=1200000))
        assert response['status'] == 'failed'
        assert db.session.get(GoiDichVuPurchase, row['id']).status == 'cancelled'
        assert TheLieuTrinh.query.count() == 0


def test_cancel_rolls_back_point_release_if_voucher_release_fails(app, client, customer_auth_headers, package_data, monkeypatch):
    row = purchase(client, customer_auth_headers, package_data)
    with app.app_context():
        fund(app, 1000)
        target = loyalty.lock_target('package_purchase', row['id'])
        reward = loyalty.save_reward(dict(name='Voucher rollback', reward_type='voucher_amount', points_cost=50, reward_value=50000))
        voucher = loyalty.redeem_reward(package_data['customer'], reward.id, 'rollback-cancel-voucher')
        loyalty.apply_reward(target, voucher.id)
        loyalty.reserve_points(target, 100)
        voucher_id = voucher.id
        db.session.commit()
    def fail_release(_target):
        raise loyalty.LoyaltyError('Fixture voucher release failed')
    monkeypatch.setattr(loyalty, 'release_reward', fail_release)
    assert cancel(client, customer_auth_headers, row['id']).status_code == 400
    with app.app_context():
        assert db.session.get(GoiDichVuPurchase, row['id']).status == 'pending'
        assert loyalty.get_balance(package_data['customer'])['reserved_points'] == 100
        assert LoyaltyRedemptionReservation.query.one().status == 'reserved'
        assert db.session.get(LoyaltyRewardRedemption, voucher_id).status == 'reserved'
        invariant(app)

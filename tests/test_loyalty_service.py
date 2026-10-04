from decimal import Decimal
import pytest
from sqlalchemy import func
from app.extensions import db
from app.models import (HoaDon, LoyaltyWallet, LoyaltyPointTransaction,
    LoyaltyRedemptionReservation, LoyaltyRewardRedemption)
from app.services import loyalty_service as loyalty


def fund(app, points=300):
    return loyalty.admin_adjust_points(app.config['TEST_CUSTOMER_ID'], points,
        'Điểm chăm sóc khách hàng', app.config['TEST_ADMIN_ID'], 'initial')


def invariant(app):
    wallet = LoyaltyWallet.query.filter_by(makh=app.config['TEST_CUSTOMER_ID']).one()
    total = db.session.query(func.coalesce(func.sum(LoyaltyPointTransaction.points_delta), 0)).filter_by(makh=wallet.makh).scalar()
    assert wallet.available_points + wallet.reserved_points == total
    assert wallet.available_points >= 0 and wallet.reserved_points >= 0


def test_preview_read_only_and_reserve_release_resume(app, create_invoice):
    invoice_id = create_invoice(500000)
    with app.app_context():
        invoice = db.session.get(HoaDon, invoice_id)
        assert loyalty.calculate_point_discount(invoice, 100)['points_allowed'] == 0
        assert not db.session.new and LoyaltyWallet.query.count() == 0
        fund(app)
        db.session.commit()
        invoice = loyalty.lock_target('service_invoice', invoice_id)
        preview = loyalty.calculate_point_discount(invoice, 100)
        assert Decimal(preview['payable_amount']) == 400000
        assert not db.session.new
        first = loyalty.reserve_points(invoice, 100)
        assert loyalty.reserve_points(invoice, 100).id == first.id
        db.session.commit()
        db.session.remove()
        invoice = loyalty.lock_target('service_invoice', invoice_id)
        assert loyalty.payment_summary(invoice)['points_used'] == 100
        assert loyalty.get_balance(invoice.makh)['available_points'] == 200
        invariant(app)
        loyalty.release_points(invoice)
        assert invoice.payable_amount == 500000
        assert loyalty.get_balance(invoice.makh)['available_points'] == 300
        assert LoyaltyRedemptionReservation.query.one().status == 'released'
        invariant(app)


def test_wallet_cannot_spend_reserved_on_other_invoice(app, create_invoice):
    first, second = create_invoice(1000000), create_invoice(1000000)
    with app.app_context():
        fund(app)
        loyalty.reserve_points(loyalty.lock_target('service_invoice', first), 250)
        with pytest.raises(loyalty.LoyaltyError):
            loyalty.reserve_points(loyalty.lock_target('service_invoice', second), 250)
        invariant(app)


def test_finalize_idempotent_reversal_and_rollback(app, create_invoice):
    invoice_id = create_invoice(500000)
    with app.app_context():
        fund(app)
        invoice = loyalty.lock_target('service_invoice', invoice_id)
        loyalty.reserve_points(invoice, 100)
        with pytest.raises(loyalty.LoyaltyError):
            loyalty.award_points(invoice)
        invoice.trangthai = 'Đã thanh toán'
        loyalty.finalize_payment(invoice)
        loyalty.finalize_payment(invoice)
        assert loyalty.get_balance(invoice.makh)['available_points'] == 240
        assert LoyaltyPointTransaction.query.filter_by(type='earn').one().points_delta == 40
        assert LoyaltyPointTransaction.query.filter_by(type='redeem').one().points_delta == -100
        invariant(app)
        db.session.commit()
        loyalty.reverse_loyalty_for_payment('service_invoice', invoice_id)
        loyalty.reverse_loyalty_for_payment('service_invoice', invoice_id)
        assert loyalty.get_balance(invoice.makh)['available_points'] == 300
        assert LoyaltyPointTransaction.query.filter_by(type='refund').count() == 2
        invariant(app)
        db.session.rollback()
        assert loyalty.get_balance(app.config['TEST_CUSTOMER_ID'])['available_points'] == 240


def test_config_rounding_limits_and_zero(app):
    with app.app_context():
        assert loyalty.calculate_earned_points(350000) == 30
        assert loyalty.calculate_earned_points(0) == 0
        for payload in ({'point_value': 0}, {'maximum_redeem_percent': 101}, {'earn_points': True}, {'points_expiry_months': 12}):
            with pytest.raises(loyalty.LoyaltyError):
                loyalty.update_config(payload)


def test_reward_snapshot_stock_idempotency_and_voucher_order(app, create_invoice):
    invoice_id = create_invoice(500000)
    with app.app_context():
        fund(app, 1000)
        reward = loyalty.save_reward(dict(name='Voucher 50k', reward_type='voucher_amount', points_cost=200,
            reward_value=50000, stock=1, validity_days=30))
        voucher = loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], reward.id, 'one-click')
        assert loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], reward.id, 'one-click').id == voucher.id
        assert reward.stock == 0
        with pytest.raises(loyalty.LoyaltyError):
            loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], reward.id, 'another')
        reward.reward_value = 999000
        invoice = loyalty.lock_target('service_invoice', invoice_id)
        loyalty.apply_reward(invoice, voucher.id)
        assert invoice.reward_discount == 50000
        preview = loyalty.calculate_point_discount(invoice, 100)
        assert preview['max_points_allowed'] == 225
        loyalty.reserve_points(invoice, 100)
        assert invoice.payable_amount == 350000
        invoice.trangthai = 'Đã thanh toán'
        loyalty.finalize_payment(invoice)
        assert voucher.status == 'used'
        assert LoyaltyPointTransaction.query.filter_by(type='earn').one().points_delta == 30
        with pytest.raises(loyalty.LoyaltyError):
            loyalty.release_reward(invoice)
        invariant(app)


def test_adjustments_require_reason_and_never_negative(app):
    with app.app_context():
        fund(app, 50)
        for delta, reason in ((-51, 'Too much'), (10, ''), (True, 'Invalid')):
            with pytest.raises(loyalty.LoyaltyError):
                loyalty.admin_adjust_points(app.config['TEST_CUSTOMER_ID'], delta, reason, app.config['TEST_ADMIN_ID'], 'invalid')
        loyalty.admin_adjust_points(app.config['TEST_CUSTOMER_ID'], -20, 'Chỉnh điểm', app.config['TEST_ADMIN_ID'], 'subtract')
        assert loyalty.get_balance(app.config['TEST_CUSTOMER_ID'])['available_points'] == 30
        invariant(app)


def test_expired_voucher_release_other_target_and_reservation_snapshot(app,create_invoice):
    from datetime import datetime,timedelta
    first,second=create_invoice(500000),create_invoice(500000)
    with app.app_context():
        fund(app,1000)
        reward=loyalty.save_reward(dict(name='Voucher',reward_type='voucher_amount',points_cost=200,reward_value=50000,validity_days=1))
        voucher=loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'],reward.id,'first')
        a=loyalty.lock_target('service_invoice',first);b=loyalty.lock_target('service_invoice',second)
        loyalty.apply_reward(a,voucher.id)
        with pytest.raises(loyalty.LoyaltyError):loyalty.apply_reward(b,voucher.id)
        loyalty.release_reward(a)
        assert a.reward_discount==0 and voucher.status=='available'
        voucher.expires_at=datetime.utcnow()-timedelta(seconds=1)
        with pytest.raises(loyalty.LoyaltyError):loyalty.apply_reward(a,voucher.id)
        loyalty.reserve_points(a,100)
        loyalty.update_config(dict(point_value=2000,redeem_on_service_invoice=False))
        a.trangthai='Đã thanh toán';loyalty.finalize_payment(a)
        assert a.loyalty_discount==100000 and a.payable_amount==400000
        invariant(app)


def test_voucher_application_rolls_back_when_point_cap_would_be_exceeded(app,create_invoice):
    invoice_id=create_invoice(500000)
    with app.app_context():
        fund(app,1000)
        reward=loyalty.save_reward(dict(name='Voucher',reward_type='voucher_amount',points_cost=100,reward_value=100000))
        voucher=loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'],reward.id,'voucher')
        invoice=loyalty.lock_target('service_invoice',invoice_id)
        loyalty.reserve_points(invoice,250)
        db.session.commit()
        with pytest.raises(loyalty.LoyaltyError):loyalty.apply_reward(invoice,voucher.id)
        db.session.rollback()
        assert invoice.reward_discount==0 and voucher.status=='available'
        assert invoice.payable_amount==250000
        invariant(app)

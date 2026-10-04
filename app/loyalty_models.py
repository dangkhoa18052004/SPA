"""Loyalty accounting tables. Imported by models for Alembic discovery."""
from datetime import datetime
from .extensions import db

# Migration 20261004_0013 creates the same constraints.
VOUCHER_TYPES = ('voucher_amount', 'voucher_percent')
REWARD_CHECK = ("reward_type IN ('voucher_amount','voucher_percent','physical_gift') AND points_cost > 0 AND reward_value >= 0 "
    "AND (reward_type <> 'voucher_amount' OR reward_value > 0) AND (stock IS NULL OR stock >= 0) AND (validity_days IS NULL OR validity_days > 0)")
VOUCHER_TERMS_CHECK = ("(minimum_spend IS NULL OR minimum_spend >= 0) AND (reward_type IN ('voucher_amount','voucher_percent') "
    "AND apply_to IS NOT NULL AND apply_to IN ('service_invoice','package_purchase','both') OR reward_type NOT IN ('voucher_amount','voucher_percent') "
    "AND apply_to IS NULL AND minimum_spend IS NULL)")
PERCENT_CHECK = ("reward_type = 'voucher_percent' AND percentage_value IS NOT NULL AND percentage_value > 0 AND percentage_value <= 100 "
    "AND (max_discount_amount IS NULL OR max_discount_amount > 0) "
    "OR reward_type <> 'voucher_percent' AND percentage_value IS NULL AND max_discount_amount IS NULL")


def voucher_default(context, value):
    return value if context.get_current_parameters().get('reward_type') in VOUCHER_TYPES else None


class LoyaltyWallet(db.Model):
    __tablename__ = 'loyalty_wallet'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, unique=True)
    available_points = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    reserved_points = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    lifetime_earned = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    lifetime_redeemed = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    version = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=db.func.now())
    __table_args__ = (db.CheckConstraint('available_points >= 0 AND reserved_points >= 0 AND lifetime_earned >= 0 AND lifetime_redeemed >= 0', name='ck_loyalty_wallet_nonnegative'),)


class LoyaltyConfig(db.Model):
    __tablename__ = 'loyalty_config'
    id = db.Column(db.Integer, primary_key=True, default=1)
    earn_amount_unit = db.Column(db.Numeric(12, 2), nullable=False, default=100000, server_default='100000')
    earn_points = db.Column(db.Integer, nullable=False, default=10, server_default='10')
    point_value = db.Column(db.Numeric(12, 2), nullable=False, default=1000, server_default='1000')
    minimum_redeem_points = db.Column(db.Integer, nullable=False, default=10, server_default='10')
    maximum_redeem_percent = db.Column(db.Numeric(5, 2), nullable=False, default=50, server_default='50')
    earn_on_service_invoice = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    earn_on_package_purchase = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    redeem_on_service_invoice = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    redeem_on_package_purchase = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    points_expiry_months = db.Column(db.Integer, nullable=True)
    __table_args__ = (db.CheckConstraint('id = 1 AND earn_amount_unit > 0 AND earn_points >= 0 AND point_value > 0 AND minimum_redeem_points > 0 AND maximum_redeem_percent >= 0 AND maximum_redeem_percent <= 100 AND points_expiry_months IS NULL', name='ck_loyalty_config'),)


class LoyaltyPointTransaction(db.Model):
    __tablename__ = 'loyalty_point_transaction'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('loyalty_wallet.id'), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    points_delta = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(30), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    reference_code = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    idempotency_key = db.Column(db.String(200), nullable=False, unique=True)
    created_by_staff = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now(), index=True)
    __table_args__ = (db.CheckConstraint("type IN ('earn','redeem','refund','adjustment_add','adjustment_subtract','reward_redeem') AND points_delta <> 0", name='ck_loyalty_ledger_type'), db.Index('ix_loyalty_ledger_source', 'source_type', 'source_id'))


class LoyaltyRedemptionReservation(db.Model):
    __tablename__ = 'loyalty_redemption_reservation'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    target_type = db.Column(db.String(30), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    points_reserved = db.Column(db.Integer, nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='reserved')
    idempotency_key = db.Column(db.String(200), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now())
    consumed_at = db.Column(db.DateTime)
    released_at = db.Column(db.DateTime)
    __table_args__ = (db.CheckConstraint("target_type IN ('service_invoice','package_purchase') AND status IN ('reserved','consumed','released') AND points_reserved > 0 AND discount_amount > 0", name='ck_loyalty_reservation'), db.Index('uq_loyalty_active_reservation', 'target_type', 'target_id', unique=True, postgresql_where=db.text("status = 'reserved'"), sqlite_where=db.text("status = 'reserved'")))


class LoyaltyReward(db.Model):
    __tablename__ = 'loyalty_reward'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    reward_type = db.Column(db.String(30), nullable=False)
    points_cost = db.Column(db.Integer, nullable=False)
    reward_value = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    stock = db.Column(db.Integer)
    validity_days = db.Column(db.Integer)
    active = db.Column(db.Boolean, nullable=False, default=True)
    # Voucher terms only; physical gifts keep both NULL. 0 means no minimum spend.
    minimum_spend = db.Column(db.Numeric(12, 2), default=lambda context: voucher_default(context, 0))
    apply_to = db.Column(db.String(30), default=lambda context: voucher_default(context, 'both'))
    # voucher_percent only: percent of the original amount, optionally capped in VND.
    percentage_value = db.Column(db.Numeric(5, 2))
    max_discount_amount = db.Column(db.Numeric(12, 2))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=db.func.now())
    __table_args__ = (db.CheckConstraint(REWARD_CHECK, name='ck_loyalty_reward'),
        db.CheckConstraint(VOUCHER_TERMS_CHECK, name='ck_loyalty_reward_voucher_terms'),
        db.CheckConstraint(PERCENT_CHECK, name='ck_loyalty_reward_percent'))


class LoyaltyRewardRedemption(db.Model):
    __tablename__ = 'loyalty_reward_redemption'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    reward_id = db.Column(db.Integer, db.ForeignKey('loyalty_reward.id'), nullable=False)
    points_spent = db.Column(db.Integer, nullable=False)
    reward_snapshot_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available')
    code = db.Column(db.String(80), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime)
    redeemed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now())
    used_at = db.Column(db.DateTime)
    fulfilled_at = db.Column(db.DateTime)
    fulfilled_by_staff = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'))
    idempotency_key = db.Column(db.String(200), nullable=False, unique=True)
    target_type = db.Column(db.String(30))
    target_id = db.Column(db.Integer)
    __table_args__ = (db.CheckConstraint("status IN ('available','reserved','used','fulfilled','expired','cancelled') AND points_spent > 0", name='ck_loyalty_reward_redemption'), db.Index('uq_loyalty_target_voucher', 'target_type', 'target_id', unique=True, postgresql_where=db.text("status = 'reserved'"), sqlite_where=db.text("status = 'reserved'")))

"""Loyalty accounting, reward catalog and persisted payment discounts."""
from alembic import op
import sqlalchemy as sa

revision = '20261003_0009'
down_revision = '20261003_0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('loyalty_wallet',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('makh', sa.Integer(), nullable=False),
    sa.Column('available_points', sa.Integer(), server_default='0', nullable=False),
    sa.Column('reserved_points', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lifetime_earned', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lifetime_redeemed', sa.Integer(), server_default='0', nullable=False),
    sa.Column('version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint('available_points >= 0 AND reserved_points >= 0 AND lifetime_earned >= 0 AND lifetime_redeemed >= 0', name='ck_loyalty_wallet_nonnegative'),
    sa.ForeignKeyConstraint(['makh'], ['khachhang.makh'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('makh')
    )
    op.create_table('loyalty_config',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('earn_amount_unit', sa.Numeric(precision=12, scale=2), server_default='100000', nullable=False),
    sa.Column('earn_points', sa.Integer(), server_default='10', nullable=False),
    sa.Column('point_value', sa.Numeric(precision=12, scale=2), server_default='1000', nullable=False),
    sa.Column('minimum_redeem_points', sa.Integer(), server_default='10', nullable=False),
    sa.Column('maximum_redeem_percent', sa.Numeric(precision=5, scale=2), server_default='50', nullable=False),
    sa.Column('earn_on_service_invoice', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('earn_on_package_purchase', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('redeem_on_service_invoice', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('redeem_on_package_purchase', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('points_expiry_months', sa.Integer(), nullable=True),
    sa.CheckConstraint('id = 1 AND earn_amount_unit > 0 AND earn_points >= 0 AND point_value > 0 AND minimum_redeem_points > 0 AND maximum_redeem_percent >= 0 AND maximum_redeem_percent <= 100 AND points_expiry_months IS NULL', name='ck_loyalty_config'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loyalty_point_transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('makh', sa.Integer(), nullable=False),
    sa.Column('wallet_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('points_delta', sa.Integer(), nullable=False),
    sa.Column('source_type', sa.String(length=30), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('reference_code', sa.String(length=80), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('created_by_staff', sa.Integer(), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("type IN ('earn','redeem','refund','adjustment_add','adjustment_subtract','reward_redeem') AND points_delta <> 0", name='ck_loyalty_ledger_type'),
    sa.ForeignKeyConstraint(['created_by_staff'], ['nhanvien.manv'], ),
    sa.ForeignKeyConstraint(['makh'], ['khachhang.makh'], ),
    sa.ForeignKeyConstraint(['wallet_id'], ['loyalty_wallet.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('ix_loyalty_ledger_source', 'loyalty_point_transaction', ['source_type', 'source_id'], unique=False)
    op.create_index(op.f('ix_loyalty_point_transaction_created_at'), 'loyalty_point_transaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_loyalty_point_transaction_makh'), 'loyalty_point_transaction', ['makh'], unique=False)
    op.create_table('loyalty_redemption_reservation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('makh', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=30), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('points_reserved', sa.Integer(), nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('consumed_at', sa.DateTime(), nullable=True),
    sa.Column('released_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("target_type IN ('service_invoice','package_purchase') AND status IN ('reserved','consumed','released') AND points_reserved > 0 AND discount_amount > 0", name='ck_loyalty_reservation'),
    sa.ForeignKeyConstraint(['makh'], ['khachhang.makh'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_loyalty_redemption_reservation_makh'), 'loyalty_redemption_reservation', ['makh'], unique=False)
    op.create_index('uq_loyalty_active_reservation', 'loyalty_redemption_reservation', ['target_type', 'target_id'], unique=True, postgresql_where=sa.text("status = 'reserved'"), sqlite_where=sa.text("status = 'reserved'"))
    op.create_table('loyalty_reward',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('reward_type', sa.String(length=30), nullable=False),
    sa.Column('points_cost', sa.Integer(), nullable=False),
    sa.Column('reward_value', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=True),
    sa.Column('validity_days', sa.Integer(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("reward_type IN ('voucher_amount','physical_gift') AND points_cost > 0 AND reward_value >= 0 AND (reward_type <> 'voucher_amount' OR reward_value > 0) AND (stock IS NULL OR stock >= 0) AND (validity_days IS NULL OR validity_days > 0)", name='ck_loyalty_reward'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('loyalty_reward_redemption',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('makh', sa.Integer(), nullable=False),
    sa.Column('reward_id', sa.Integer(), nullable=False),
    sa.Column('points_spent', sa.Integer(), nullable=False),
    sa.Column('reward_snapshot_json', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('redeemed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
    sa.Column('fulfilled_by_staff', sa.Integer(), nullable=True),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('target_type', sa.String(length=30), nullable=True),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("status IN ('available','reserved','used','fulfilled','expired','cancelled') AND points_spent > 0", name='ck_loyalty_reward_redemption'),
    sa.ForeignKeyConstraint(['fulfilled_by_staff'], ['nhanvien.manv'], ),
    sa.ForeignKeyConstraint(['makh'], ['khachhang.makh'], ),
    sa.ForeignKeyConstraint(['reward_id'], ['loyalty_reward.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_loyalty_reward_redemption_makh'), 'loyalty_reward_redemption', ['makh'], unique=False)
    op.create_index('uq_loyalty_target_voucher', 'loyalty_reward_redemption', ['target_type', 'target_id'], unique=True, postgresql_where=sa.text("status = 'reserved'"), sqlite_where=sa.text("status = 'reserved'"))

    op.execute(sa.text('INSERT INTO loyalty_config (id) VALUES (1)'))
    for table, original in [('hoadon', 'tongtien'), ('goidichvupurchase', 'amount')]:
        op.add_column(table, sa.Column('reward_discount', sa.Numeric(12, 2), nullable=False, server_default='0'))
        op.add_column(table, sa.Column('loyalty_discount', sa.Numeric(12, 2), nullable=False, server_default='0'))
        op.add_column(table, sa.Column('payable_amount', sa.Numeric(12, 2), nullable=True))
        op.execute(sa.text(f'UPDATE {table} SET payable_amount = {original}'))
        with op.batch_alter_table(table) as batch:
            batch.alter_column('payable_amount', existing_type=sa.Numeric(12, 2), nullable=False)


def downgrade():
    for table in ['hoadon', 'goidichvupurchase']:
        with op.batch_alter_table(table) as batch:
            for column in ['payable_amount', 'loyalty_discount', 'reward_discount']:
                batch.drop_column(column)
    for table in ['loyalty_reward_redemption', 'loyalty_reward', 'loyalty_redemption_reservation', 'loyalty_point_transaction', 'loyalty_config', 'loyalty_wallet']:
        op.drop_table(table)

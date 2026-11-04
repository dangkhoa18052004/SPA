"""Issue welcome/staff vouchers without point ledger entries; preserve old rewards."""
from alembic import op
import sqlalchemy as sa

revision = '20261023_0025'
down_revision = '20261021_0024'
branch_labels = None
depends_on = None

OLD_REWARD_CHECK = ("reward_type IN ('voucher_amount','voucher_percent','physical_gift') AND points_cost > 0 AND reward_value >= 0 "
    "AND (reward_type <> 'voucher_amount' OR reward_value > 0) AND (stock IS NULL OR stock >= 0) AND (validity_days IS NULL OR validity_days > 0)")
REWARD_CHECK = OLD_REWARD_CHECK.replace('points_cost > 0', "points_cost >= 0 AND (NOT allow_points_redemption OR points_cost > 0) "
    "AND (NOT allow_manual_gift OR reward_type IN ('voucher_amount','voucher_percent'))")
OLD_ISSUANCE_CHECK = "status IN ('available','reserved','used','fulfilled','expired','cancelled') AND points_spent > 0"
ISSUANCE_CHECK = ("status IN ('available','reserved','used','fulfilled','expired','cancelled') AND "
    "((issuance_source = 'points_redemption' AND points_spent > 0) OR "
    "(issuance_source IN ('welcome','staff_gift') AND points_spent = 0)) AND "
    "(issuance_source <> 'staff_gift' OR (issued_by_staff IS NOT NULL AND gift_reason IS NOT NULL AND length(trim(gift_reason)) > 0)) AND "
    "((issuance_source = 'welcome' AND welcome_once_key IS NOT NULL AND length(welcome_once_key) > 0) OR "
    "(issuance_source <> 'welcome' AND welcome_once_key IS NULL))")


def upgrade():
    with op.batch_alter_table('loyalty_reward') as b:
        b.add_column(sa.Column('allow_points_redemption', sa.Boolean(), nullable=False, server_default=sa.true()))
        b.add_column(sa.Column('allow_manual_gift', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.drop_constraint('ck_loyalty_reward', type_='check')
        b.create_check_constraint('ck_loyalty_reward', REWARD_CHECK)
    with op.batch_alter_table('loyalty_reward_redemption') as b:
        b.add_column(sa.Column('issuance_source', sa.String(30), nullable=False, server_default='points_redemption'))
        b.add_column(sa.Column('issued_by_staff', sa.Integer()))
        b.add_column(sa.Column('gift_reason', sa.Text()))
        b.add_column(sa.Column('customer_message', sa.String(1000)))
        b.add_column(sa.Column('welcome_once_key', sa.String(80)))
        b.add_column(sa.Column('issuance_payload_json', sa.JSON()))
        b.add_column(sa.Column('cancelled_by_staff', sa.Integer()))
        b.add_column(sa.Column('cancelled_at', sa.DateTime()))
        b.add_column(sa.Column('cancel_reason', sa.Text()))
        b.create_foreign_key('fk_issuance_staff', 'nhanvien', ['issued_by_staff'], ['manv'])
        b.create_foreign_key('fk_cancelled_staff', 'nhanvien', ['cancelled_by_staff'], ['manv'])
        b.create_unique_constraint('uq_loyalty_welcome_once', ['welcome_once_key'])
        b.drop_constraint('ck_loyalty_reward_redemption', type_='check')
        b.create_check_constraint('ck_loyalty_reward_redemption', ISSUANCE_CHECK)
        b.create_index('ix_loyalty_issuance_history', ['makh', 'issuance_source', 'redeemed_at'])
    op.create_table('customer_otp_registration',
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), primary_key=True),
        sa.Column('registered_at', sa.DateTime(), nullable=False))
    op.create_table('welcome_voucher_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reward_id', sa.Integer(), sa.ForeignKey('loyalty_reward.id')),
        sa.Column('starts_at', sa.DateTime()), sa.Column('ends_at', sa.DateTime()),
        sa.Column('updated_by_staff', sa.Integer(), sa.ForeignKey('nhanvien.manv')),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1 AND (NOT enabled OR (reward_id IS NOT NULL AND starts_at IS NOT NULL)) "
            "AND (ends_at IS NULL OR (starts_at IS NOT NULL AND ends_at > starts_at))", name='ck_welcome_voucher_config'))


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT COUNT(*) FROM loyalty_reward_redemption WHERE issuance_source <> 'points_redemption' OR points_spent <= 0")).scalar():
        raise RuntimeError('Cannot downgrade: issued gift vouchers require the new schema; no vouchers were deleted')
    if connection.execute(sa.text('SELECT COUNT(*) FROM loyalty_reward WHERE points_cost <= 0')).scalar():
        raise RuntimeError('Cannot downgrade: zero-point templates require the new schema')
    op.drop_table('welcome_voucher_config')
    op.drop_table('customer_otp_registration')
    with op.batch_alter_table('loyalty_reward_redemption') as b:
        b.drop_index('ix_loyalty_issuance_history')
        b.drop_constraint('ck_loyalty_reward_redemption', type_='check')
        b.create_check_constraint('ck_loyalty_reward_redemption', OLD_ISSUANCE_CHECK)
        b.drop_constraint('uq_loyalty_welcome_once', type_='unique')
        b.drop_constraint('fk_issuance_staff', type_='foreignkey')
        b.drop_constraint('fk_cancelled_staff', type_='foreignkey')
        for name in ('issuance_source', 'issued_by_staff', 'gift_reason', 'customer_message', 'welcome_once_key',
                     'issuance_payload_json', 'cancelled_by_staff', 'cancelled_at', 'cancel_reason'):
            b.drop_column(name)
    with op.batch_alter_table('loyalty_reward') as b:
        b.drop_constraint('ck_loyalty_reward', type_='check')
        b.create_check_constraint('ck_loyalty_reward', OLD_REWARD_CHECK)
        b.drop_column('allow_manual_gift')
        b.drop_column('allow_points_redemption')

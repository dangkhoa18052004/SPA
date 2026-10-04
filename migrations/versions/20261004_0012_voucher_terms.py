"""Voucher terms: minimum spend and payment scope, without changing issued redemptions."""
from alembic import op
import sqlalchemy as sa

revision = '20261004_0012'
down_revision = '20261004_0011'
branch_labels = None
depends_on = None

VOUCHER_TERMS_CHECK = ("(minimum_spend IS NULL OR minimum_spend >= 0) AND (reward_type = 'voucher_amount' "
    "AND apply_to IN ('service_invoice','package_purchase','both') OR reward_type <> 'voucher_amount' "
    "AND apply_to IS NULL AND minimum_spend IS NULL)")


def upgrade():
    # Nullable columns without defaults: metadata-only on PostgreSQL, no table rewrite.
    op.add_column('loyalty_reward', sa.Column('minimum_spend', sa.Numeric(12, 2), nullable=True))
    op.add_column('loyalty_reward', sa.Column('apply_to', sa.String(30), nullable=True))
    # Existing vouchers keep working everywhere with no minimum; gifts stay without payment terms.
    op.execute(sa.text("UPDATE loyalty_reward SET apply_to = 'both', minimum_spend = 0 WHERE reward_type = 'voucher_amount'"))
    if op.get_context().dialect.name == 'sqlite':
        with op.batch_alter_table('loyalty_reward') as batch:
            batch.create_check_constraint('ck_loyalty_reward_voucher_terms', VOUCHER_TERMS_CHECK)
    else:
        op.create_check_constraint('ck_loyalty_reward_voucher_terms', 'loyalty_reward', VOUCHER_TERMS_CHECK)


def downgrade():
    with op.batch_alter_table('loyalty_reward') as batch:
        batch.drop_constraint('ck_loyalty_reward_voucher_terms', type_='check')
        batch.drop_column('apply_to')
        batch.drop_column('minimum_spend')

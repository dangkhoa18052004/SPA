"""Percentage vouchers: new reward type plus percent and cap columns; existing rewards keep their meaning."""
from alembic import op
import sqlalchemy as sa

revision = '20261004_0013'
down_revision = '20261004_0012'
branch_labels = None
depends_on = None

OLD_REWARD_CHECK = ("reward_type IN ('voucher_amount','physical_gift') AND points_cost > 0 AND reward_value >= 0 "
    "AND (reward_type <> 'voucher_amount' OR reward_value > 0) AND (stock IS NULL OR stock >= 0) AND (validity_days IS NULL OR validity_days > 0)")
OLD_TERMS_CHECK = ("(minimum_spend IS NULL OR minimum_spend >= 0) AND (reward_type = 'voucher_amount' "
    "AND apply_to IN ('service_invoice','package_purchase','both') OR reward_type <> 'voucher_amount' "
    "AND apply_to IS NULL AND minimum_spend IS NULL)")
REWARD_CHECK = ("reward_type IN ('voucher_amount','voucher_percent','physical_gift') AND points_cost > 0 AND reward_value >= 0 "
    "AND (reward_type <> 'voucher_amount' OR reward_value > 0) AND (stock IS NULL OR stock >= 0) AND (validity_days IS NULL OR validity_days > 0)")
TERMS_CHECK = ("(minimum_spend IS NULL OR minimum_spend >= 0) AND (reward_type IN ('voucher_amount','voucher_percent') "
    "AND apply_to IS NOT NULL AND apply_to IN ('service_invoice','package_purchase','both') OR reward_type NOT IN ('voucher_amount','voucher_percent') "
    "AND apply_to IS NULL AND minimum_spend IS NULL)")
PERCENT_CHECK = ("reward_type = 'voucher_percent' AND percentage_value IS NOT NULL AND percentage_value > 0 AND percentage_value <= 100 "
    "AND (max_discount_amount IS NULL OR max_discount_amount > 0) "
    "OR reward_type <> 'voucher_percent' AND percentage_value IS NULL AND max_discount_amount IS NULL")


def replace_checks(checks, drop=()):
    # Existing rows satisfy every new check (new columns are NULL), so validation cannot fail.
    # IS NOT NULL is explicit: a CHECK whose result is NULL counts as passing.
    if op.get_context().dialect.name == 'sqlite':
        with op.batch_alter_table('loyalty_reward') as batch:
            for name in drop:
                batch.drop_constraint(name, type_='check')
            for name, sql in checks:
                batch.create_check_constraint(name, sql)
    else:
        for name in drop:
            op.drop_constraint(name, 'loyalty_reward', type_='check')
        for name, sql in checks:
            op.create_check_constraint(name, 'loyalty_reward', sql)


def upgrade():
    op.add_column('loyalty_reward', sa.Column('percentage_value', sa.Numeric(5, 2), nullable=True))
    op.add_column('loyalty_reward', sa.Column('max_discount_amount', sa.Numeric(12, 2), nullable=True))
    replace_checks([('ck_loyalty_reward', REWARD_CHECK), ('ck_loyalty_reward_voucher_terms', TERMS_CHECK),
                    ('ck_loyalty_reward_percent', PERCENT_CHECK)], drop=('ck_loyalty_reward', 'ck_loyalty_reward_voucher_terms'))


def downgrade():
    # Refuse instead of deleting or silently converting percentage vouchers.
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM loyalty_reward WHERE reward_type = 'voucher_percent'")).scalar():
        raise RuntimeError('Cannot downgrade: voucher_percent rewards exist')
    replace_checks([('ck_loyalty_reward', OLD_REWARD_CHECK), ('ck_loyalty_reward_voucher_terms', OLD_TERMS_CHECK)],
                   drop=('ck_loyalty_reward_percent', 'ck_loyalty_reward', 'ck_loyalty_reward_voucher_terms'))
    with op.batch_alter_table('loyalty_reward') as batch:
        batch.drop_column('max_discount_amount')
        batch.drop_column('percentage_value')

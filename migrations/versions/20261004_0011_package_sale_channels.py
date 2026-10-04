"""Separate website and counter package sales without changing existing entitlements."""
from alembic import op
import sqlalchemy as sa

revision = '20261004_0011'
down_revision = '20261004_0010'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('goidichvu', sa.Column('customer_sale_enabled', sa.Boolean(),
        nullable=False, server_default=sa.true()))
    op.add_column('goidichvu', sa.Column('staff_sale_enabled', sa.Boolean(),
        nullable=False, server_default=sa.true()))
    # Preserve the old sale state, including packages that were already archived.
    op.execute(sa.text('UPDATE goidichvu SET customer_sale_enabled = active, staff_sale_enabled = active'))


def downgrade():
    with op.batch_alter_table('goidichvu') as batch:
        batch.drop_column('staff_sale_enabled')
        batch.drop_column('customer_sale_enabled')

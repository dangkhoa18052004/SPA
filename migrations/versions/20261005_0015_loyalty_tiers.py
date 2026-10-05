"""Membership tier thresholds on loyalty config (additive; tier is derived from the ledger).

Revision ID: 20261005_0015
Revises: 20261005_0014
"""
from alembic import op
import sqlalchemy as sa

revision = '20261005_0015'
down_revision = '20261005_0014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('loyalty_config', sa.Column('tier_thresholds', sa.JSON(), nullable=True))
    op.add_column('loyalty_config', sa.Column('tier_count_adjustments', sa.Boolean(), nullable=False,
                                              server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('loyalty_config') as batch:
        batch.drop_column('tier_count_adjustments')
        batch.drop_column('tier_thresholds')

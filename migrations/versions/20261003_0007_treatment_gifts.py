"""Extend existing entitlement items with independently valid gifts."""
from alembic import op
import sqlalchemy as sa

revision = '20261003_0007'
down_revision = '20261003_0006'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('thelieutrinhitem') as batch:
        batch.add_column(sa.Column('source_type', sa.String(20), nullable=False, server_default='package'))
        batch.add_column(sa.Column('valid_from', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('gifted_by_staff', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('gift_note', sa.Text(), nullable=True))
        batch.add_column(sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
        batch.create_foreign_key('fk_treatment_item_gift_staff', 'nhanvien', ['gifted_by_staff'], ['manv'])
        batch.drop_constraint('uq_treatment_service', type_='unique')
        batch.create_check_constraint('ck_treatment_item_source', "source_type IN ('package','gift')")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM thelieutrinhitem WHERE source_type='gift'")).scalar():
        raise RuntimeError('Cannot downgrade while gifts exist; preserve gift audit and usage data.')
    with op.batch_alter_table('thelieutrinhitem') as batch:
        batch.drop_constraint('ck_treatment_item_source', type_='check')
        batch.drop_constraint('fk_treatment_item_gift_staff', type_='foreignkey')
        batch.create_unique_constraint('uq_treatment_service', ['mathe', 'madv'])
        for name in ('created_at', 'gift_note', 'gifted_by_staff', 'expires_at', 'valid_from', 'source_type'):
            batch.drop_column(name)

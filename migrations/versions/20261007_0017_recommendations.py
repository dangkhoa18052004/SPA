"""Normalized service categories and authenticated customer behavior (additive)."""
from alembic import op
import sqlalchemy as sa

revision = '20261007_0017'
down_revision = '20261005_0016'
branch_labels = None
depends_on = None


def upgrade():
    categories = op.create_table('danhmucdichvu',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(80), nullable=False, unique=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.bulk_insert(categories, [dict(name=name, slug=slug) for name, slug in [
        ('Massage', 'massage'), ('Chăm sóc da mụn', 'acne'), ('Chăm sóc da mặt', 'facial'),
        ('Chăm sóc cơ thể', 'body-care'), ('Thư giãn', 'relaxation'),
        ('Nail & Móng', 'nail'), ('Tóc & Đầu', 'hair')]])
    with op.batch_alter_table('dichvu') as batch:
        batch.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_dichvu_category', 'danhmucdichvu', ['category_id'], ['id'])
        batch.create_index('ix_dichvu_category_id', ['category_id'])
    op.create_table('customer_behavior',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), nullable=False),
        sa.Column('madv', sa.Integer(), sa.ForeignKey('dichvu.madv'), nullable=True),
        sa.Column('magoi', sa.Integer(), sa.ForeignKey('goidichvu.magoi'), nullable=True),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('dedupe_key', sa.String(160), nullable=False, unique=True),
        sa.CheckConstraint('(madv IS NOT NULL AND magoi IS NULL) OR (madv IS NULL AND magoi IS NOT NULL)', name='ck_behavior_target'),
        sa.CheckConstraint("action IN ('view_service','click_service','select_service','book_service','complete_service','view_package','purchase_package','favorite')", name='ck_behavior_action'))
    op.create_index('ix_behavior_customer_time', 'customer_behavior', ['makh', 'created_at'])
    op.create_index('ix_lichhen_customer_date', 'lichhen', ['makh', 'ngaygio'])
    op.create_index('ix_hoadon_customer_date', 'hoadon', ['makh', 'ngaylap'])


def downgrade():
    op.drop_index('ix_hoadon_customer_date', table_name='hoadon')
    op.drop_index('ix_lichhen_customer_date', table_name='lichhen')
    op.drop_table('customer_behavior')
    with op.batch_alter_table('dichvu') as batch:
        batch.drop_index('ix_dichvu_category_id')
        batch.drop_constraint('fk_dichvu_category', type_='foreignkey')
        batch.drop_column('category_id')
    op.drop_table('danhmucdichvu')

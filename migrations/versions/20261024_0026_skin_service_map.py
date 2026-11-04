"""Approved acne type / service assignments, independent of process-local AI proposals."""
from alembic import op
import sqlalchemy as sa

revision = '20261024_0026'
down_revision = '20261023_0025'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('skin_service_map',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type_code', sa.String(30), nullable=False),
        sa.Column('madv', sa.Integer(), sa.ForeignKey('dichvu.madv', ondelete='CASCADE'), nullable=False),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('nhanvien.manv', ondelete='SET NULL')),
        sa.Column('approved_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("type_code IN ('closed_comedo','open_comedo','papule','pustule','nodule')",
                           name='ck_skin_service_map_type'),
        sa.UniqueConstraint('type_code', 'madv', name='uq_skin_service_map_type_service'))
    op.create_index('ix_skin_service_map_madv', 'skin_service_map', ['madv'])


def downgrade():
    op.drop_index('ix_skin_service_map_madv', table_name='skin_service_map')
    op.drop_table('skin_service_map')

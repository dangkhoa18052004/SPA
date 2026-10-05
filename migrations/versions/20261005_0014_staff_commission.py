"""Staff commission policy per service, commission snapshots and payroll column (additive).

Revision ID: 20261005_0014
Revises: 20261004_0013
"""
from alembic import op
import sqlalchemy as sa

revision = '20261005_0014'
down_revision = '20261004_0013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dichvu', sa.Column('commission_percent', sa.Numeric(5, 2), nullable=True))
    op.add_column('dichvu', sa.Column('commission_fixed', sa.Numeric(12, 2), nullable=True))
    op.add_column('luong', sa.Column('hoahong', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.create_table(
        'commission_entry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('malh', sa.Integer(), sa.ForeignKey('lichhen.malh'), nullable=False),
        sa.Column('madv', sa.Integer(), sa.ForeignKey('dichvu.madv'), nullable=False),
        sa.Column('manv', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=False),
        sa.Column('service_name', sa.String(100), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('base_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('rate_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('fixed_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('earned_at', sa.DateTime(), nullable=False),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('malh', 'madv', name='uq_commission_appointment_service'),
        sa.CheckConstraint("status IN ('active','voided')", name='ck_commission_status'),
        sa.CheckConstraint("source_type IN ('regular','package','gift')", name='ck_commission_source'),
    )
    op.create_index('ix_commission_entry_malh', 'commission_entry', ['malh'])
    op.create_index('ix_commission_entry_manv', 'commission_entry', ['manv'])
    op.create_index('ix_commission_entry_earned_at', 'commission_entry', ['earned_at'])


def downgrade():
    op.drop_index('ix_commission_entry_earned_at', table_name='commission_entry')
    op.drop_index('ix_commission_entry_manv', table_name='commission_entry')
    op.drop_index('ix_commission_entry_malh', table_name='commission_entry')
    op.drop_table('commission_entry')
    with op.batch_alter_table('luong') as batch:
        batch.drop_column('hoahong')
    with op.batch_alter_table('dichvu') as batch:
        batch.drop_column('commission_fixed')
        batch.drop_column('commission_percent')

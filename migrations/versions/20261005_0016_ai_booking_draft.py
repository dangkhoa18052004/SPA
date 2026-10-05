"""AI booking drafts: proposals that become appointments only after explicit confirmation (additive).

Revision ID: 20261005_0016
Revises: 20261005_0015
"""
from alembic import op
import sqlalchemy as sa

revision = '20261005_0016'
down_revision = '20261005_0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_booking_draft',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), nullable=False),
        sa.Column('madv_list', sa.JSON(), nullable=False),
        sa.Column('ngaygio', sa.DateTime(), nullable=False),
        sa.Column('manv', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('malh', sa.Integer(), sa.ForeignKey('lichhen.malh'), nullable=True, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('draft','confirmed','expired')", name='ck_ai_draft_status'),
    )
    op.create_index('ix_ai_booking_draft_makh', 'ai_booking_draft', ['makh'])


def downgrade():
    op.drop_index('ix_ai_booking_draft_makh', table_name='ai_booking_draft')
    op.drop_table('ai_booking_draft')

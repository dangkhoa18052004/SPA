"""Customer opt-in preferences and measured recommendation baseline."""
from alembic import op
import sqlalchemy as sa

revision = '20261015_0020'
down_revision = '20261014_0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('customer_preference',
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), primary_key=True),
        sa.Column('reminders', sa.Boolean(), nullable=False),
        sa.Column('post_care', sa.Boolean(), nullable=False),
        sa.Column('review_requests', sa.Boolean(), nullable=False),
        sa.Column('personalization', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_table('customer_preference_audit',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('makh', 'version', name='uq_customer_preference_version'))
    op.create_index('ix_customer_preference_audit_makh', 'customer_preference_audit', ['makh'])
    op.create_table('recommendation_impression',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), nullable=False),
        sa.Column('placement', sa.String(20), nullable=False),
        sa.Column('madv', sa.Integer(), sa.ForeignKey('dichvu.madv')),
        sa.Column('magoi', sa.Integer(), sa.ForeignKey('goidichvu.magoi')),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('strategy', sa.String(20), nullable=False),
        sa.Column('dedupe_key', sa.String(150), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('clicked_at', sa.DateTime()),
        sa.CheckConstraint('(madv IS NOT NULL AND magoi IS NULL) OR (madv IS NULL AND magoi IS NOT NULL)', name='ck_impression_target'),
        sa.CheckConstraint('position BETWEEN 1 AND 6', name='ck_impression_position'))
    op.create_index('ix_impression_customer_time', 'recommendation_impression', ['makh', 'created_at'])
    op.create_index('ix_impression_time', 'recommendation_impression', ['created_at'])
    op.create_table('recommendation_timing',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('placement', sa.String(20), nullable=False),
        sa.Column('duration_ms', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_recommendation_timing_created_at', 'recommendation_timing', ['created_at'])


def downgrade():
    for table in ('recommendation_timing', 'recommendation_impression', 'customer_preference_audit', 'customer_preference'):
        op.drop_table(table)

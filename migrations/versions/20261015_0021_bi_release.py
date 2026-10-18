"""BI export audit, no-show outcomes, shared authentication limits and worker heartbeat."""
from alembic import op
import sqlalchemy as sa

revision = '20261015_0021'
down_revision = '20261015_0020'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_rate_bucket',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('bucket', sa.BigInteger(), primary_key=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False))
    op.create_index('ix_auth_rate_bucket_expires_at', 'auth_rate_bucket', ['expires_at'])
    op.create_table('report_export_audit',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=False),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('branch_ids', sa.JSON(), nullable=False),
        sa.Column('business_scope', sa.String(30), nullable=False),
        sa.Column('request_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_report_export_audit_created_at', 'report_export_audit', ['created_at'])
    op.create_table('worker_heartbeat',
        sa.Column('name', sa.String(40), primary_key=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False))
    op.create_table('appointment_outcome',
        sa.Column('malh', sa.Integer(), sa.ForeignKey('lichhen.malh'), primary_key=True),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False))


def downgrade():
    for table in ('appointment_outcome', 'worker_heartbeat', 'report_export_audit', 'auth_rate_bucket'):
        op.drop_table(table)

"""Durable short-lived AI responses across customer page navigation."""
from alembic import op
import sqlalchemy as sa

revision = '20261015_0022'
down_revision = '20261015_0021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_chat_job',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_key', sa.String(64), nullable=False),
        sa.Column('actor_kind', sa.String(12), nullable=False),
        sa.Column('actor_id', sa.Integer()),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('result_json', sa.JSON()),
        sa.Column('error_message', sa.String(500)),
        sa.Column('error_status', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','PROCESSING','SUCCEEDED','FAILED')", name='ck_ai_chat_job_status'))
    op.create_index('ix_ai_chat_job_queue', 'ai_chat_job', ['status', 'created_at'])
    op.create_index('ix_ai_chat_job_owner', 'ai_chat_job', ['owner_key', 'created_at'])
    op.create_index('ix_ai_chat_job_expires_at', 'ai_chat_job', ['expires_at'])


def downgrade():
    op.drop_table('ai_chat_job')

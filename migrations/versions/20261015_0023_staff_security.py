"""Staff TOTP step-up for sensitive operations; business tables unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '20261015_0023'
down_revision = '20261015_0022'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('staff_mfa',
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('nhanvien.manv'), primary_key=True),
        sa.Column('secret_ciphertext', sa.Text()), sa.Column('pending_ciphertext', sa.Text()),
        sa.Column('pending_expires_at', sa.DateTime()), sa.Column('enabled_at', sa.DateTime()),
        sa.Column('generation', sa.Integer(), nullable=False), sa.Column('last_counter', sa.BigInteger(), nullable=False))
    op.create_table('staff_recovery_code',
        sa.Column('code_hash', sa.String(64), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False), sa.Column('used_at', sa.DateTime()))
    op.create_index('ix_staff_recovery_code_staff_id', 'staff_recovery_code', ['staff_id'])
    op.create_table('staff_step_up',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False), sa.Column('auth_digest', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False))
    op.create_index('ix_staff_step_up_staff_id', 'staff_step_up', ['staff_id'])
    op.create_index('ix_staff_step_up_expires_at', 'staff_step_up', ['expires_at'])
    op.create_table('staff_security_audit',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=False),
        sa.Column('action', sa.String(40), nullable=False), sa.Column('request_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_staff_security_audit_created_at', 'staff_security_audit', ['created_at'])


def downgrade():
    for name in ('staff_security_audit', 'staff_step_up', 'staff_recovery_code', 'staff_mfa'):
        op.drop_table(name)

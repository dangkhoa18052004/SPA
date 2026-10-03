"""Phase 4: packages, treatment ledger and care outbox (additive)."""
from alembic import op
import sqlalchemy as sa

revision = "20261002_0004"
down_revision = "20261001_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dichvu", sa.Column("post_care_instructions", sa.Text(), nullable=True))
    op.create_table('goidichvu',
        sa.Column('magoi', sa.Integer(), nullable=False),
        sa.Column('tengoi', sa.String(length=200), nullable=False),
        sa.Column('mota', sa.Text(), nullable=True),
        sa.Column('giagoi', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('validity_months', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('giagoi > 0 AND validity_months > 0', name='ck_package_values'),
        sa.PrimaryKeyConstraint('magoi'),
    )
    op.create_table('goidichvuitem',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('magoi', sa.Integer(), nullable=False),
        sa.Column('madv', sa.Integer(), nullable=False),
        sa.Column('total_sessions', sa.Integer(), nullable=False),
        sa.Column('regular_unit_price_snapshot', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('package_unit_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint('total_sessions > 0', name='ck_package_sessions'),
        sa.ForeignKeyConstraint(['madv'], ['dichvu.madv']),
        sa.ForeignKeyConstraint(['magoi'], ['goidichvu.magoi']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('magoi', 'madv', name='uq_package_service'),
    )
    op.create_table('goidichvupurchase',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('makh', sa.Integer(), nullable=False),
        sa.Column('magoi', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('payment_method', sa.String(length=30), nullable=False),
        sa.Column('external_transaction_id', sa.String(length=150), nullable=True),
        sa.Column('snapshot_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending','paid','failed','cancelled')", name='ck_purchase_status'),
        sa.ForeignKeyConstraint(['magoi'], ['goidichvu.magoi']),
        sa.ForeignKeyConstraint(['makh'], ['khachhang.makh']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_transaction_id', name=None),
    )
    op.create_index('ix_goidichvupurchase_makh', 'goidichvupurchase', ['makh'], unique=False)
    op.create_index('ix_goidichvupurchase_status', 'goidichvupurchase', ['status'], unique=False)
    op.create_table('thelieutrinh',
        sa.Column('mathe', sa.Integer(), nullable=False),
        sa.Column('makh', sa.Integer(), nullable=False),
        sa.Column('magoi', sa.Integer(), nullable=False),
        sa.Column('purchase_id', sa.Integer(), nullable=False),
        sa.Column('purchased_at', sa.DateTime(), nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active','used_up','expired','cancelled')", name='ck_treatment_status'),
        sa.ForeignKeyConstraint(['purchase_id'], ['goidichvupurchase.id']),
        sa.ForeignKeyConstraint(['makh'], ['khachhang.makh']),
        sa.ForeignKeyConstraint(['magoi'], ['goidichvu.magoi']),
        sa.PrimaryKeyConstraint('mathe'),
        sa.UniqueConstraint('purchase_id', name=None),
    )
    op.create_index('ix_thelieutrinh_makh', 'thelieutrinh', ['makh'], unique=False)
    op.create_table('thelieutrinhitem',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mathe', sa.Integer(), nullable=False),
        sa.Column('madv', sa.Integer(), nullable=False),
        sa.Column('total_sessions', sa.Integer(), nullable=False),
        sa.Column('unit_value_snapshot', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('regular_price_snapshot', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint('total_sessions > 0', name='ck_treatment_sessions'),
        sa.ForeignKeyConstraint(['mathe'], ['thelieutrinh.mathe']),
        sa.ForeignKeyConstraint(['madv'], ['dichvu.madv']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mathe', 'madv', name='uq_treatment_service'),
    )
    op.create_table('lieutrinhusage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mathe', sa.Integer(), nullable=False),
        sa.Column('the_item_id', sa.Integer(), nullable=False),
        sa.Column('malh', sa.Integer(), nullable=False),
        sa.Column('madv', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('reserved_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("state IN ('reserved','consumed','released')", name='ck_usage_state'),
        sa.ForeignKeyConstraint(['the_item_id'], ['thelieutrinhitem.id']),
        sa.ForeignKeyConstraint(['mathe'], ['thelieutrinh.mathe']),
        sa.ForeignKeyConstraint(['madv'], ['dichvu.madv']),
        sa.ForeignKeyConstraint(['malh'], ['lichhen.malh']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('malh', 'madv', name='uq_usage_appointment_service'),
    )
    op.create_index('ix_lieutrinhusage_malh', 'lieutrinhusage', ['malh'], unique=False)
    op.create_index('ix_lieutrinhusage_mathe', 'lieutrinhusage', ['mathe'], unique=False)
    op.create_table('notificationjob',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=40), nullable=False),
        sa.Column('makh', sa.Integer(), nullable=False),
        sa.Column('malh', sa.Integer(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('unique_key', sa.String(length=200), nullable=False),
        sa.Column('processing_at', sa.DateTime(), nullable=True),
        sa.Column('first_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('pending','processing','sent','failed','cancelled')", name='ck_job_status'),
        sa.ForeignKeyConstraint(['malh'], ['lichhen.malh']),
        sa.ForeignKeyConstraint(['makh'], ['khachhang.makh']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unique_key', name=None),
    )
    op.create_index('ix_notificationjob_scheduled_at', 'notificationjob', ['scheduled_at'], unique=False)
    op.create_index('ix_notificationjob_status', 'notificationjob', ['status'], unique=False)


def downgrade():
    op.drop_table('notificationjob')
    op.drop_table('lieutrinhusage')
    op.drop_table('thelieutrinhitem')
    op.drop_table('thelieutrinh')
    op.drop_table('goidichvupurchase')
    op.drop_table('goidichvuitem')
    op.drop_table('goidichvu')
    op.drop_column("dichvu", "post_care_instructions")

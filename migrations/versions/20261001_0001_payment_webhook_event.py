"""add payment webhook idempotency audit table

Revision ID: 20261001_0001
Revises: None
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa


revision = "20261001_0001"
down_revision = "f3b12dbde06b"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "payment_webhook_event" not in tables:
        op.create_table(
            "payment_webhook_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=20), nullable=False),
            sa.Column("external_transaction_id", sa.String(length=100), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("mahd", sa.Integer(), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["mahd"], ["hoadon.mahd"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "provider",
                "external_transaction_id",
                name="uq_payment_webhook_provider_transaction",
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "payment_webhook_event" in tables:
        op.drop_table("payment_webhook_event")


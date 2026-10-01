"""add danhgia review model

Revision ID: 20261001_0003
Revises: 20261001_0002
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa


revision = "20261001_0003"
down_revision = "20261001_0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "danhgia" not in tables:
        op.create_table(
            "danhgia",
            sa.Column("madg", sa.Integer(), nullable=False),
            sa.Column("malh", sa.Integer(), nullable=False),
            sa.Column("makh", sa.Integer(), nullable=False),
            sa.Column("manv", sa.Integer(), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["malh"], ["lichhen.malh"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["makh"], ["khachhang.makh"]),
            sa.ForeignKeyConstraint(["manv"], ["nhanvien.manv"]),
            sa.PrimaryKeyConstraint("madg"),
            sa.UniqueConstraint("malh", name="uq_danhgia_malh"),
        )
        op.create_index("ix_danhgia_malh", "danhgia", ["malh"], unique=True)
        op.create_index("ix_danhgia_makh", "danhgia", ["makh"], unique=False)
        op.create_index("ix_danhgia_manv", "danhgia", ["manv"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "danhgia" in tables:
        op.drop_table("danhgia")

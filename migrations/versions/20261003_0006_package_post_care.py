"""Add post_care_instructions to goidichvu (additive, nullable)."""
from alembic import op
import sqlalchemy as sa

revision = "20261003_0006"
down_revision = "20261002_0005"
branch_labels = None
depends_on = None


def upgrade():
    # Only add GoiDichVu.post_care_instructions.
    # dichvu.post_care_instructions already exists from migration 0004.
    op.add_column(
        "goidichvu",
        sa.Column("post_care_instructions", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("goidichvu", "post_care_instructions")

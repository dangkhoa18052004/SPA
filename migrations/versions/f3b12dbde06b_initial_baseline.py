"""initial baseline schema

Revision ID: f3b12dbde06b
Revises: None
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa


revision = "f3b12dbde06b"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Baseline exists in production database; no DDL needed
    pass


def downgrade():
    pass

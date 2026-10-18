"""Support manager-reviewed check-in/out requests without inventing an end time."""
from alembic import op
import sqlalchemy as sa

revision = '20261014_0019'
down_revision = '20261014_0018'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attendance_adjustment') as batch:
        batch.add_column(sa.Column('request_kind', sa.String(20), nullable=False, server_default='correction'))
        batch.alter_column('proposed_end', existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade():
    # Preserve an open request's start timestamp when returning to the older schema.
    op.execute(sa.text('UPDATE attendance_adjustment SET proposed_end = proposed_start WHERE proposed_end IS NULL'))
    with op.batch_alter_table('attendance_adjustment') as batch:
        batch.alter_column('proposed_end', existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.drop_column('request_kind')

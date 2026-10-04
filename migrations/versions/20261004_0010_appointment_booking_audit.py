"""Record appointment booking source and the staff member who created it."""
from alembic import op
import sqlalchemy as sa

revision = '20261004_0010'
down_revision = '20261003_0009'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lichhen') as batch:
        batch.add_column(sa.Column('booking_source', sa.String(20), nullable=True, server_default='legacy'))
        batch.add_column(sa.Column('created_by_staff', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_lichhen_booking_creator', 'nhanvien', ['created_by_staff'], ['manv'])


def downgrade():
    with op.batch_alter_table('lichhen') as batch:
        batch.drop_constraint('fk_lichhen_booking_creator', type_='foreignkey')
        batch.drop_column('created_by_staff')
        batch.drop_column('booking_source')

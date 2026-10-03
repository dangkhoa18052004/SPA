"""Package images, unlimited validity and counter sale audit (additive)."""
from alembic import op
import sqlalchemy as sa

revision = '20261002_0005'
down_revision = '20261002_0004'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('goidichvu') as batch:
        batch.add_column(sa.Column('anhgoi', sa.LargeBinary(), nullable=True))
        batch.alter_column('validity_months', existing_type=sa.Integer(), nullable=True)
        batch.drop_constraint('ck_package_values', type_='check')
        batch.create_check_constraint('ck_package_values', 'giagoi > 0 AND (validity_months IS NULL OR validity_months > 0)')
    with op.batch_alter_table('thelieutrinh') as batch:
        batch.alter_column('expires_at', existing_type=sa.DateTime(), nullable=True)
    with op.batch_alter_table('goidichvupurchase') as batch:
        batch.add_column(sa.Column('created_by_staff', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('confirmed_by_staff', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('cash_received', sa.Numeric(12, 2), nullable=True))
        batch.create_foreign_key('fk_purchase_creator', 'nhanvien', ['created_by_staff'], ['manv'])
        batch.create_foreign_key('fk_purchase_confirmer', 'nhanvien', ['confirmed_by_staff'], ['manv'])


def downgrade():
    # Unlimited records cannot be silently converted to a fabricated expiry.
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT COUNT(*) FROM goidichvu WHERE validity_months IS NULL')).scalar() or connection.execute(sa.text('SELECT COUNT(*) FROM thelieutrinh WHERE expires_at IS NULL')).scalar():
        raise RuntimeError('Resolve unlimited package/treatment validity before downgrading')
    with op.batch_alter_table('goidichvupurchase') as batch:
        batch.drop_constraint('fk_purchase_creator', type_='foreignkey')
        batch.drop_constraint('fk_purchase_confirmer', type_='foreignkey')
        batch.drop_column('cash_received')
        batch.drop_column('confirmed_by_staff')
        batch.drop_column('created_by_staff')
    with op.batch_alter_table('thelieutrinh') as batch:
        batch.alter_column('expires_at', existing_type=sa.DateTime(), nullable=False)
    with op.batch_alter_table('goidichvu') as batch:
        batch.drop_column('anhgoi')
        batch.alter_column('validity_months', existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint('ck_package_values', type_='check')
        batch.create_check_constraint('ck_package_values', 'giagoi > 0 AND validity_months > 0')

"""Preserve legacy reviews and link them to their actual appointment services."""
from alembic import op
import sqlalchemy as sa

revision = '20261003_0008'
down_revision = '20261003_0007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('danhgia', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.create_table('danhgiadichvu',
        sa.Column('madg', sa.Integer(), sa.ForeignKey('danhgia.madg'), primary_key=True),
        sa.Column('madv', sa.Integer(), sa.ForeignKey('dichvu.madv'), primary_key=True))
    op.create_table('reviewreply',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('danhgia.madg'), nullable=False, unique=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('nhanvien.manv'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.execute(sa.text('INSERT INTO danhgiadichvu (madg,madv) '
        'SELECT DISTINCT d.madg,c.madv FROM danhgia d JOIN chitietlichhen c ON c.malh=d.malh'))


def downgrade():
    op.drop_table('reviewreply')
    op.drop_table('danhgiadichvu')
    op.drop_column('danhgia', 'updated_at')

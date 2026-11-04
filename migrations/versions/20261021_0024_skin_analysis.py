"""Customer skin analyses (acne AI); additive, business tables unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '20261021_0024'
down_revision = '20261015_0023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('skin_analysis',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('makh', sa.Integer(), sa.ForeignKey('khachhang.makh'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('lesion_count', sa.Integer(), nullable=False),
        sa.Column('confident_count', sa.Integer(), nullable=False),
        sa.Column('type_counts', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('image_file', sa.String(80)),
        sa.Column('image_width', sa.Integer()), sa.Column('image_height', sa.Integer()),
        sa.Column('consent_version', sa.String(20), nullable=False),
        sa.Column('consent_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_skin_analysis_makh', 'skin_analysis', ['makh'])


def downgrade():
    op.drop_index('ix_skin_analysis_makh', table_name='skin_analysis')
    op.drop_table('skin_analysis')

"""normalize appointment status and add ghichu column with indexes

Revision ID: 20261001_0002
Revises: 20261001_0001
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa


revision = "20261001_0002"
down_revision = "20261001_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # 1. Thêm cột ghichu vào lichhen nếu chưa có
    columns = [c["name"] for c in inspector.get_columns("lichhen")]
    if "ghichu" not in columns:
        op.add_column("lichhen", sa.Column("ghichu", sa.Text(), nullable=True))

    # 2. Tạo index cho hiệu năng kiểm tra lịch hẹn
    indexes = [ix["name"] for ix in inspector.get_indexes("lichhen")]
    if "ix_lichhen_manv_ngaygio" not in indexes:
        op.create_index(
            "ix_lichhen_manv_ngaygio",
            "lichhen",
            ["manv", "ngaygio"],
            unique=False
        )
    if "ix_lichhen_trangthai" not in indexes:
        op.create_index(
            "ix_lichhen_trangthai",
            "lichhen",
            ["trangthai"],
            unique=False
        )

    # 3. Chuẩn hóa dữ liệu trạng thái tiếng Việt sang mã chuẩn (data migration)
    # Mapping:
    # 'Chờ xác nhận' / 'cho xac nhan' -> 'pending'
    # 'Đã xác nhận' / 'da xac nhan'   -> 'confirmed'
    # 'Đang thực hiện' / 'dang thuc hien' -> 'in_progress'
    # 'Đã hoàn thành' / 'da hoan thanh' -> 'completed'
    # 'Đã hủy' / 'da huy'           -> 'cancelled'
    
    bind.execute(sa.text("""
        UPDATE lichhen 
        SET trangthai = 'pending' 
        WHERE LOWER(trangthai) IN ('chờ xác nhận', 'cho xac nhan');
    """))
    bind.execute(sa.text("""
        UPDATE lichhen 
        SET trangthai = 'confirmed' 
        WHERE LOWER(trangthai) IN ('đã xác nhận', 'da xac nhan');
    """))
    bind.execute(sa.text("""
        UPDATE lichhen 
        SET trangthai = 'in_progress' 
        WHERE LOWER(trangthai) IN ('đang thực hiện', 'dang thuc hien', 'in progress');
    """))
    bind.execute(sa.text("""
        UPDATE lichhen 
        SET trangthai = 'completed' 
        WHERE LOWER(trangthai) IN ('đã hoàn thành', 'da hoan thanh', 'hoàn thành');
    """))
    bind.execute(sa.text("""
        UPDATE lichhen 
        SET trangthai = 'cancelled' 
        WHERE LOWER(trangthai) IN ('đã hủy', 'da huy', 'hủy', 'huy', 'canceled');
    """))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [ix["name"] for ix in inspector.get_indexes("lichhen")]
    if "ix_lichhen_manv_ngaygio" in indexes:
        op.drop_index("ix_lichhen_manv_ngaygio", table_name="lichhen")
    if "ix_lichhen_trangthai" in indexes:
        op.drop_index("ix_lichhen_trangthai", table_name="lichhen")

    # Revert status text to Vietnamese default
    bind.execute(sa.text("""
        UPDATE lichhen SET trangthai = 'Chờ xác nhận' WHERE trangthai = 'pending';
    """))
    bind.execute(sa.text("""
        UPDATE lichhen SET trangthai = 'Đã xác nhận' WHERE trangthai = 'confirmed';
    """))
    bind.execute(sa.text("""
        UPDATE lichhen SET trangthai = 'Đang thực hiện' WHERE trangthai = 'in_progress';
    """))
    bind.execute(sa.text("""
        UPDATE lichhen SET trangthai = 'Đã hoàn thành' WHERE trangthai = 'completed';
    """))
    bind.execute(sa.text("""
        UPDATE lichhen SET trangthai = 'Đã hủy' WHERE trangthai = 'cancelled';
    """))

    columns = [c["name"] for c in inspector.get_columns("lichhen")]
    if "ghichu" in columns:
        op.drop_column("lichhen", "ghichu")

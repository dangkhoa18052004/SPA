"""initial baseline schema

Revision ID: f3b12dbde06b
Revises: None
Create Date: 2026-10-01

Schema gốc trước 20261001_0001 (các bảng có sẵn ở database production cũ).

- Database rỗng: tạo đầy đủ các bảng gốc để chuỗi migration chạy được tới head.
- Database cũ đã có bảng gốc (chưa có alembic_version): không chạy DDL nào; xem
  docs/DATABASE_MIGRATIONS.md để nhận diện và `flask db stamp` đúng revision.
- Các cột được thêm bởi migration sau (lichhen.ghichu, hoadon.payable_amount,
  dichvu.post_care_instructions, ...) KHÔNG được tạo ở đây.
"""
from alembic import op
import sqlalchemy as sa


revision = "f3b12dbde06b"
down_revision = None
branch_labels = None
depends_on = None

LEGACY_TABLES = (
    "chucvu", "khachhang", "nhanvien", "dichvu", "calam", "nhanvien_calam",
    "lichhen", "chitietlichhen", "hoadon", "chitiethoadon", "thanhtoan",
    "hoithoai", "tinnhan", "luong", "bangluongchitiet", "dangkyschicht",
)


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if existing.intersection(LEGACY_TABLES):
        # Database cũ: schema gốc đã tồn tại, không thay đổi dữ liệu.
        return

    op.create_table(
        "chucvu",
        sa.Column("macv", sa.Integer(), primary_key=True),
        sa.Column("tencv", sa.String(100), nullable=False),
        sa.Column("dongiagio", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "khachhang",
        sa.Column("makh", sa.Integer(), primary_key=True),
        sa.Column("hoten", sa.String(100), nullable=False),
        sa.Column("sdt", sa.String(20), unique=True),
        sa.Column("diachi", sa.String(255)),
        sa.Column("email", sa.String(100), unique=True),
        sa.Column("taikhoan", sa.String(50), nullable=False, unique=True),
        sa.Column("matkhau", sa.String(255), nullable=False),
        sa.Column("anhdaidien", sa.String(255)),
        sa.Column("ngaytao", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("trangthai", sa.String(20), server_default="active"),
        sa.Column("resettoken", sa.String(255)),
        sa.Column("resettokenexpire", sa.DateTime()),
        sa.Column("otp_code", sa.String(10)),
        sa.Column("otp_expire", sa.DateTime()),
    )
    op.create_table(
        "nhanvien",
        sa.Column("manv", sa.Integer(), primary_key=True),
        sa.Column("hoten", sa.String(100), nullable=False),
        sa.Column("sdt", sa.String(20), unique=True),
        sa.Column("diachi", sa.String(255)),
        sa.Column("email", sa.String(100), unique=True),
        sa.Column("taikhoan", sa.String(50), nullable=False, unique=True),
        sa.Column("matkhau", sa.String(255), nullable=False),
        sa.Column("anhnhanvien", sa.String(255)),
        sa.Column("macv", sa.Integer(), sa.ForeignKey("chucvu.macv"), nullable=False),
        sa.Column("ngaytao", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("trangthai", sa.Boolean(), server_default=sa.true()),
        sa.Column("role", sa.String(50), nullable=False, server_default="staff"),
    )
    op.create_table(
        "dichvu",
        sa.Column("madv", sa.Integer(), primary_key=True),
        sa.Column("tendv", sa.String(100), nullable=False),
        sa.Column("gia", sa.Numeric(12, 2), nullable=False),
        sa.Column("thoiluong", sa.Integer()),
        sa.Column("donvitinh", sa.String(50)),
        sa.Column("anhdichvu", sa.LargeBinary()),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("mota", sa.Text()),
    )
    op.create_table(
        "calam",
        sa.Column("maca", sa.Integer(), primary_key=True),
        sa.Column("ngay", sa.Date(), nullable=False),
        sa.Column("giobatdau", sa.Time(), nullable=False),
        sa.Column("gioketthuc", sa.Time(), nullable=False),
        sa.Column("hesoluong", sa.Integer(), server_default="1"),
        # Ứng dụng tự tính và ghi sogio khi tạo/sửa ca.
        sa.Column("sogio", sa.Numeric(10, 2)),
    )
    op.create_table(
        "nhanvien_calam",
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), primary_key=True),
        sa.Column("maca", sa.Integer(), sa.ForeignKey("calam.maca"), primary_key=True),
    )
    op.create_table(
        "lichhen",
        sa.Column("malh", sa.Integer(), primary_key=True),
        sa.Column("ngaygio", sa.DateTime(), nullable=False),
        sa.Column("trangthai", sa.String(50), server_default="pending"),
        sa.Column("makh", sa.Integer(), sa.ForeignKey("khachhang.makh"), nullable=False),
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=True),
    )
    op.create_index("ix_lichhen_ngaygio", "lichhen", ["ngaygio"])
    op.create_index("ix_lichhen_manv", "lichhen", ["manv"])
    op.create_table(
        "chitietlichhen",
        sa.Column("malh", sa.Integer(), sa.ForeignKey("lichhen.malh"), primary_key=True),
        sa.Column("madv", sa.Integer(), sa.ForeignKey("dichvu.madv"), primary_key=True),
    )
    op.create_table(
        "hoadon",
        sa.Column("mahd", sa.Integer(), primary_key=True),
        sa.Column("ngaylap", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("tongtien", sa.Numeric(12, 2), nullable=False),
        sa.Column("makh", sa.Integer(), sa.ForeignKey("khachhang.makh"), nullable=False),
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=False),
        sa.Column("trangthai", sa.String(50), server_default="Chưa thanh toán"),
        sa.Column("malh", sa.Integer(), sa.ForeignKey("lichhen.malh"), nullable=True, unique=True),
    )
    op.create_table(
        "chitiethoadon",
        sa.Column("macthd", sa.Integer(), primary_key=True),
        sa.Column("mahd", sa.Integer(), sa.ForeignKey("hoadon.mahd"), nullable=False),
        sa.Column("madv", sa.Integer(), sa.ForeignKey("dichvu.madv"), nullable=False),
        sa.Column("soluong", sa.Integer(), server_default="1"),
        sa.Column("dongia", sa.Numeric(12, 2), nullable=False),
        sa.Column("thanhtien", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "thanhtoan",
        sa.Column("matt", sa.Integer(), primary_key=True),
        sa.Column("mahd", sa.Integer(), sa.ForeignKey("hoadon.mahd"), nullable=False),
        sa.Column("sotien", sa.Numeric(12, 2), nullable=False),
        sa.Column("phuongthuc", sa.String(50), server_default="Tiền mặt"),
        sa.Column("ngaythanhtoan", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("ghichu", sa.Text()),
    )
    op.create_table(
        "hoithoai",
        sa.Column("maht", sa.Integer(), primary_key=True),
        sa.Column("ngaybatdau", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("makh", sa.Integer(), sa.ForeignKey("khachhang.makh"), nullable=True),
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=True),
        sa.Column("tin_nhan_cuoi_noi_dung", sa.Text()),
        sa.Column("tin_nhan_cuoi_thoi_gian", sa.DateTime()),
        sa.Column("tin_nhan_cuoi_la_khach_gui", sa.Boolean()),
    )
    op.create_table(
        "tinnhan",
        sa.Column("matn", sa.Integer(), primary_key=True),
        sa.Column("noidung", sa.Text(), nullable=False),
        sa.Column("thoigiangui", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("maht", sa.Integer(), sa.ForeignKey("hoithoai.maht"), nullable=False),
        sa.Column("nguoigui_makh", sa.Integer(), sa.ForeignKey("khachhang.makh"), nullable=True),
        sa.Column("nguoigui_manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=True),
        sa.Column("da_doc", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "luong",
        sa.Column("maluong", sa.Integer(), primary_key=True),
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=False),
        sa.Column("thang", sa.Integer(), nullable=False),
        sa.Column("nam", sa.Integer(), nullable=False),
        sa.Column("luongcoban", sa.Numeric(12, 2)),
        sa.Column("thuong", sa.Numeric(12, 2), server_default="0"),
        sa.Column("khautru", sa.Numeric(12, 2), server_default="0"),
        sa.Column("tongluong", sa.Numeric(12, 2)),
    )
    op.create_table(
        "bangluongchitiet",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=False),
        sa.Column("maca", sa.Integer(), sa.ForeignKey("calam.maca"), nullable=False),
        sa.Column("maluong_thang", sa.Integer(), sa.ForeignKey("luong.maluong"), nullable=True),
        sa.Column("ngay_lam", sa.Date(), nullable=False),
        sa.Column("sogio_lam", sa.Numeric(5, 2), nullable=False),
        sa.Column("dongia_gio", sa.Numeric(10, 2), nullable=False),
        sa.Column("luong_ca", sa.Numeric(10, 2), nullable=False),
        sa.Column("thuong_ca", sa.Numeric(10, 2), server_default="0"),
        sa.Column("khautru_ca", sa.Numeric(10, 2), server_default="0"),
        sa.UniqueConstraint("manv", "maca", name="_manv_maca_uc"),
    )
    op.create_index("ix_bangluongchitiet_manv", "bangluongchitiet", ["manv"])
    op.create_index("ix_bangluongchitiet_maca", "bangluongchitiet", ["maca"])
    op.create_index("ix_bangluongchitiet_maluong_thang", "bangluongchitiet", ["maluong_thang"])
    op.create_table(
        "dangkyschicht",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manv", sa.Integer(), sa.ForeignKey("nhanvien.manv"), nullable=False),
        sa.Column("maca", sa.Integer(), sa.ForeignKey("calam.maca"), nullable=False),
        sa.Column("ngaydangky", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("trangthai", sa.String(50), server_default="pending"),
    )


def downgrade():
    # Không xóa bảng gốc: downgrade về base không được làm mất dữ liệu vận hành.
    # Muốn dựng lại database thử nghiệm, hãy xóa database đó rồi chạy lại upgrade.
    pass

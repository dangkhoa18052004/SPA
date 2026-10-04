from .extensions import db
from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy.schema import FetchedValue
from .loyalty_models import (LoyaltyWallet, LoyaltyConfig, LoyaltyPointTransaction,
    LoyaltyRedemptionReservation, LoyaltyReward, LoyaltyRewardRedemption)
nhanvien_calam = db.Table('nhanvien_calam',
    db.Column('manv', db.Integer, db.ForeignKey('nhanvien.manv'), primary_key=True),
    db.Column('maca', db.Integer, db.ForeignKey('calam.maca'), primary_key=True)
)

# bảng khách hàng
class KhachHang(db.Model):
    __tablename__ = 'khachhang'
    makh = db.Column(db.Integer, primary_key=True)      
    hoten = db.Column(db.String(100), nullable=False)
    sdt = db.Column(db.String(20), unique=True, nullable=True)
    diachi = db.Column(db.String(255))
    email = db.Column(db.String(100), unique=True, nullable=True)
    taikhoan = db.Column(db.String(50), unique=True, nullable=False)
    matkhau = db.Column(db.String(255), nullable=False)    # lưu hash
    anhdaidien = db.Column(db.String(255))
    ngaytao = db.Column(db.DateTime, default=datetime.utcnow)
    trangthai = db.Column(db.String(20), default='pending')
    resettoken = db.Column(db.String(255), nullable=True)
    resettokenexpire = db.Column(db.DateTime, nullable=True)
    otp_code = db.Column(db.String(10), comment='Lưu mã OTP gửi đến email')
    otp_expire = db.Column(db.DateTime, comment='Lưu thời điểm hết hạn của mã OTP')

# bảng nhân viên
class NhanVien(db.Model):
    __tablename__ = 'nhanvien'
    manv = db.Column(db.Integer, primary_key=True)  
    hoten = db.Column(db.String(100), nullable=False)
    sdt = db.Column(db.String(20), unique=True, nullable=True)  
    diachi = db.Column(db.String(255))
    email = db.Column(db.String(100), unique=True, nullable=True)   
    taikhoan = db.Column(db.String(50), unique=True, nullable=False)
    matkhau = db.Column(db.String(255), nullable=False)    # lưu hash   
    anhnhanvien = db.Column(db.String(255))
    macv = db.Column(db.Integer, db.ForeignKey('chucvu.macv'), nullable=False)
    ngaytao = db.Column(db.DateTime, default=datetime.utcnow)       
    role = db.Column(db.String(50), nullable=False, default='staff')
    trangthai = db.Column(db.Boolean, default=True) 
        # Quan hệ ngược với ChucVu
    chucvu = db.relationship('ChucVu', back_populates='nhanviens')
    calam = db.relationship('CaLam', secondary=nhanvien_calam,
                            back_populates='nhanvien', lazy='dynamic')
# bảng chức vụ
class ChucVu(db.Model):
    __tablename__ = 'chucvu'
    macv = db.Column(db.Integer, primary_key=True)  
    tencv = db.Column(db.String(100), nullable=False)
    dongiagio = db.Column(db.Numeric(12, 2), nullable=False)
    nhanviens = db.relationship('NhanVien', back_populates='chucvu', lazy=True)

# bảng dịch vụ
class DichVu(db.Model):
    __tablename__ = 'dichvu'
    madv = db.Column(db.Integer, primary_key=True)
    tendv = db.Column(db.String(100), nullable=False)
    gia = db.Column(db.Numeric(12, 2), nullable=False)
    thoiluong = db.Column(db.Integer) # Thời lượng tính bằng phút
    donvitinh = db.Column(db.String(50))
    anhdichvu = db.Column(db.LargeBinary) # Sử dụng LargeBinary cho kiểu bytea
    active = db.Column(db.Boolean, default=True)
    mota = db.Column(db.Text)
    post_care_instructions = db.Column(db.Text, nullable=True)

class AppointmentStatus:
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    ALL = {PENDING, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED}
    ACTIVE_STATUSES = {PENDING, CONFIRMED, IN_PROGRESS}
    FINAL_STATUSES = {COMPLETED, CANCELLED}

    VI_MAP = {
        PENDING: 'Chờ xác nhận',
        CONFIRMED: 'Đã xác nhận',
        IN_PROGRESS: 'Đang thực hiện',
        COMPLETED: 'Đã hoàn thành',
        CANCELLED: 'Đã hủy',
    }

    @classmethod
    def to_vietnamese(cls, status_code):
        return cls.VI_MAP.get(status_code, status_code)

    @classmethod
    def normalize(cls, raw_status):
        if not raw_status:
            return cls.PENDING
        cleaned = str(raw_status).strip().lower()
        mapping = {
            'pending': cls.PENDING,
            'chờ xác nhận': cls.PENDING,
            'cho xac nhan': cls.PENDING,
            'confirmed': cls.CONFIRMED,
            'đã xác nhận': cls.CONFIRMED,
            'da xac nhan': cls.CONFIRMED,
            'in_progress': cls.IN_PROGRESS,
            'dang thuc hien': cls.IN_PROGRESS,
            'đang thực hiện': cls.IN_PROGRESS,
            'in progress': cls.IN_PROGRESS,
            'completed': cls.COMPLETED,
            'hoàn thành': cls.COMPLETED,
            'hoan thanh': cls.COMPLETED,
            'đã hoàn thành': cls.COMPLETED,
            'da hoan thanh': cls.COMPLETED,
            'cancelled': cls.CANCELLED,
            'canceled': cls.CANCELLED,
            'đã hủy': cls.CANCELLED,
            'da huy': cls.CANCELLED,
            'hủy': cls.CANCELLED,
            'huy': cls.CANCELLED,
        }
        return mapping.get(cleaned, cleaned)


# bảng lịch hẹn
class LichHen(db.Model):
    __tablename__ = 'lichhen'
    malh = db.Column(db.Integer, primary_key=True)
    ngaygio = db.Column(db.DateTime, nullable=False, index=True)
    trangthai = db.Column(db.String(50), default=AppointmentStatus.PENDING, index=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True, index=True)
    ghichu = db.Column(db.Text, nullable=True)
    booking_source = db.Column(db.String(20), nullable=True, default='legacy', server_default='legacy')
    created_by_staff = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    khachhang = db.relationship('KhachHang', backref='lichhen', lazy=True)
    chitiet = db.relationship('ChiTietLichHen', backref='lichhen', lazy=True, cascade="all, delete-orphan")
    nhanvien = db.relationship('NhanVien', foreign_keys=[manv], lazy=True)
    booking_creator = db.relationship('NhanVien', foreign_keys=[created_by_staff], lazy=True)

    @property
    def trangthai_vi(self):
        return AppointmentStatus.to_vietnamese(self.trangthai)

# bảng chi tiết lịch hẹn
class ChiTietLichHen(db.Model):
    __tablename__ = 'chitietlichhen'
    malh = db.Column(db.Integer, db.ForeignKey('lichhen.malh'), primary_key=True)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'), primary_key=True)

    dichvu = db.relationship('DichVu', lazy=True)

# bảng hóa đơn
class HoaDon(db.Model):
    __tablename__ = 'hoadon'
    mahd = db.Column(db.Integer, primary_key=True)
    ngaylap = db.Column(db.DateTime, default=datetime.utcnow)
    tongtien = db.Column(db.Numeric(12, 2), nullable=False)
    reward_discount = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default='0')
    loyalty_discount = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default='0')
    payable_amount = db.Column(db.Numeric(12, 2), nullable=False,
        default=lambda context: context.get_current_parameters()['tongtien'])
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    trangthai = db.Column(db.String(50), default='Chưa thanh toán')
    malh = db.Column(db.Integer, db.ForeignKey('lichhen.malh'), nullable=True, unique=True)
    khachhang = db.relationship('KhachHang', backref='hoadon', lazy=True)
    nhanvien = db.relationship('NhanVien', backref='hoadon', lazy=True)

# bảng chi tiết hóa đơn
class ChiTietHoaDon(db.Model):
    __tablename__ = 'chitiethoadon'
    macthd = db.Column(db.Integer, primary_key=True)
    mahd = db.Column(db.Integer, db.ForeignKey('hoadon.mahd'), nullable=False)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'), nullable=False)
    soluong = db.Column(db.Integer, default=1)
    dongia = db.Column(db.Numeric(12, 2), nullable=False)
    thanhtien = db.Column(db.Numeric(12, 2), nullable=False)

    hoadon = db.relationship('HoaDon', backref='chitiet', lazy=True)
    dichvu = db.relationship('DichVu', backref='chitiet_hoadon', lazy=True)

# bảng hội thoại
class Hoithoai(db.Model):
    __tablename__ = 'hoithoai'
    maht = db.Column(db.Integer, primary_key=True)
    ngaybatdau = db.Column(db.DateTime, default=datetime.utcnow)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=True)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    khachhang = db.relationship('KhachHang', backref='hoithoai', lazy=True)
    tinnhan = db.relationship('TinNhan', backref='hoithoai', lazy=True, cascade="all, delete-orphan")

    # Nội dung của tin nhắn cuối cùng trong hội thoại
    tin_nhan_cuoi_noi_dung = db.Column(db.Text, nullable=True) 
    # Thời gian của tin nhắn cuối
    tin_nhan_cuoi_thoi_gian = db.Column(db.DateTime, nullable=True) 
    # True nếu khách gửi, False nếu NV gửi
    tin_nhan_cuoi_la_khach_gui = db.Column(db.Boolean, nullable=True)

# bảng tin nhắn
class TinNhan(db.Model):
    __tablename__ = 'tinnhan'
    matn = db.Column(db.Integer, primary_key=True) 
    noidung = db.Column(db.Text, nullable=False)
    thoigiangui = db.Column(db.DateTime, default=datetime.utcnow)
    maht = db.Column(db.Integer, db.ForeignKey('hoithoai.maht'), nullable=False)
    nguoigui_makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=True)
    nguoigui_manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    da_doc = db.Column(db.Boolean, default=False, nullable=False)
    khachhang_gui = db.relationship('KhachHang', foreign_keys=[nguoigui_makh])
    nhanvien_gui = db.relationship('NhanVien', foreign_keys=[nguoigui_manv])

# bảng ca làm việc
class CaLam(db.Model):
    """Model cho bảng Ca làm việc."""
    __tablename__ = 'calam'
    maca = db.Column(db.Integer, primary_key=True)
    ngay = db.Column(db.Date, nullable=False)
    giobatdau = db.Column(db.Time, nullable=False)
    gioketthuc = db.Column(db.Time, nullable=False)
    hesoluong = db.Column(db.Integer, default=1)
    sogio = db.Column(db.Numeric(10, 2), server_default=FetchedValue())    
    # Mối quan hệ Nhiều-Nhiều với NhanVien
    nhanvien = db.relationship('NhanVien', secondary=nhanvien_calam,
                               back_populates='calam', lazy='dynamic')

# bảng thanh toán
class ThanhToan(db.Model):
    """Model cho bảng Thanh toán."""
    __tablename__ = 'thanhtoan'
    matt = db.Column(db.Integer, primary_key=True)
    mahd = db.Column(db.Integer, db.ForeignKey('hoadon.mahd'), nullable=False)
    sotien = db.Column(db.Numeric(12, 2), nullable=False)
    phuongthuc = db.Column(db.String(50), default='Tiền mặt')
    ngaythanhtoan = db.Column(db.DateTime, default=datetime.utcnow)
    ghichu = db.Column(db.Text)
    # Mối quan hệ với HoaDon
    hoadon = db.relationship('HoaDon', backref=db.backref('thanhtoan', lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class PaymentWebhookEvent(db.Model):
    """Audit/idempotency record for external payment callbacks."""
    __tablename__ = 'payment_webhook_event'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False)
    external_transaction_id = db.Column(db.String(100), nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='processing')
    mahd = db.Column(db.Integer, db.ForeignKey('hoadon.mahd'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    invoice = db.relationship('HoaDon')

    __table_args__ = (
        UniqueConstraint(
            'provider',
            'external_transaction_id',
            name='uq_payment_webhook_provider_transaction',
        ),
    )

# bảng lương nhân viên
class Luong(db.Model):
    """Model cho bảng Lương nhân viên."""
    __tablename__ = 'luong'
    maluong = db.Column(db.Integer, primary_key=True)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    thang = db.Column(db.Integer, nullable=False)
    nam = db.Column(db.Integer, nullable=False)
    luongcoban = db.Column(db.Numeric(12, 2))
    thuong = db.Column(db.Numeric(12, 2), default=0)
    khautru = db.Column(db.Numeric(12, 2), default=0)
    tongluong = db.Column(db.Numeric(12, 2))
    chi_tiet = db.relationship('BangLuongChiTiet', back_populates='luong_thang_tonghop', lazy='dynamic')
    nhanvien = db.relationship('NhanVien', backref=db.backref('luong', lazy=True))

class BangLuongChiTiet(db.Model):
    __tablename__ = 'bangluongchitiet'

    id = db.Column(db.Integer, primary_key=True)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False, index=True)
    maca = db.Column(db.Integer, db.ForeignKey('calam.maca'), nullable=False, index=True) 
    maluong_thang = db.Column(db.Integer, db.ForeignKey('luong.maluong'), nullable=True, index=True)
    ngay_lam = db.Column(db.Date, nullable=False)
    sogio_lam = db.Column(db.Numeric(5, 2), nullable=False)
    dongia_gio = db.Column(db.Numeric(10, 2), nullable=False)
    luong_ca = db.Column(db.Numeric(10, 2), nullable=False)
    thuong_ca = db.Column(db.Numeric(10, 2), default=0)
    khautru_ca = db.Column(db.Numeric(10, 2), default=0)

    nhanvien = db.relationship('NhanVien')
    calam = db.relationship('CaLam')
    luong_thang_tonghop = db.relationship('Luong', back_populates='chi_tiet')
    __table_args__ = (
        UniqueConstraint('manv', 'maca', name='_manv_maca_uc'),
    )

# bảng đăng ký ca làm
class DangKyCaLam(db.Model):
    __tablename__ = 'dangkyschicht'
    id = db.Column(db.Integer, primary_key=True)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    maca = db.Column(db.Integer, db.ForeignKey('calam.maca'), nullable=False)
    ngaydangky = db.Column(db.DateTime, default=datetime.utcnow)
    trangthai = db.Column(db.String(50), default='pending') # pending, approved, rejected

    nhanvien = db.relationship('NhanVien', backref='dangkyschicht')
    calam = db.relationship('CaLam', backref='dangkyschicht')

# bảng đánh giá dịch vụ sau khi hoàn thành lịch hẹn
class DanhGia(db.Model):
    __tablename__ = 'danhgia'
    madg = db.Column(db.Integer, primary_key=True)
    malh = db.Column(db.Integer, db.ForeignKey('lichhen.malh'), nullable=False, unique=True, index=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1 đến 5 sao
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lichhen = db.relationship('LichHen', backref=db.backref('danhgia', uselist=False, cascade='all, delete-orphan'))
    khachhang = db.relationship('KhachHang', backref='danhgia_list')
    nhanvien = db.relationship('NhanVien', backref='danhgia_list')
    updated_at = db.Column(db.DateTime, nullable=True)
    service_links = db.relationship('DanhGiaDichVu', cascade='all, delete-orphan', backref='review')
    reply = db.relationship('ReviewReply', cascade='all, delete-orphan', backref='review', uselist=False)


class DanhGiaDichVu(db.Model):
    __tablename__ = 'danhgiadichvu'
    madg = db.Column(db.Integer, db.ForeignKey('danhgia.madg'), primary_key=True)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'), primary_key=True)
    service = db.relationship('DichVu')


class ReviewReply(db.Model):
    __tablename__ = 'reviewreply'
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('danhgia.madg'), nullable=False, unique=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    staff = db.relationship('NhanVien')


class GoiDichVu(db.Model):
    __tablename__ = 'goidichvu'
    magoi = db.Column(db.Integer, primary_key=True)
    tengoi = db.Column(db.String(200), nullable=False)
    mota = db.Column(db.Text)
    giagoi = db.Column(db.Numeric(12, 2), nullable=False)
    validity_months = db.Column(db.Integer, nullable=True)
    anhgoi = db.Column(db.LargeBinary)
    active = db.Column(db.Boolean, nullable=False, default=True)
    # Dặn dò BỔ SUNG dành riêng cho khách đang dùng liệu trình/gói này.
    # Khác DichVu.post_care_instructions (dặn dò sau dịch vụ vừa thực hiện).
    post_care_instructions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = db.relationship('GoiDichVuItem', cascade='all, delete-orphan', backref='package')
    __table_args__ = (db.CheckConstraint('giagoi > 0 AND (validity_months IS NULL OR validity_months > 0)', name='ck_package_values'),)


class GoiDichVuItem(db.Model):
    __tablename__ = 'goidichvuitem'
    id = db.Column(db.Integer, primary_key=True)
    magoi = db.Column(db.Integer, db.ForeignKey('goidichvu.magoi'), nullable=False)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'), nullable=False)
    total_sessions = db.Column(db.Integer, nullable=False)
    regular_unit_price_snapshot = db.Column(db.Numeric(12, 2), nullable=False)
    package_unit_value = db.Column(db.Numeric(12, 2), nullable=False)
    service = db.relationship('DichVu')
    __table_args__ = (db.UniqueConstraint('magoi', 'madv', name='uq_package_service'),
                      db.CheckConstraint('total_sessions > 0', name='ck_package_sessions'))


class GoiDichVuPurchase(db.Model):
    __tablename__ = 'goidichvupurchase'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    magoi = db.Column(db.Integer, db.ForeignKey('goidichvu.magoi'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reward_discount = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default='0')
    loyalty_discount = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default='0')
    payable_amount = db.Column(db.Numeric(12, 2), nullable=False,
        default=lambda context: context.get_current_parameters()['amount'])
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    payment_method = db.Column(db.String(30), nullable=False)
    external_transaction_id = db.Column(db.String(150), nullable=True, unique=True)
    snapshot_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    created_by_staff = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'))
    confirmed_by_staff = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'))
    cash_received = db.Column(db.Numeric(12, 2))
    creator = db.relationship('NhanVien', foreign_keys=[created_by_staff])
    confirmer = db.relationship('NhanVien', foreign_keys=[confirmed_by_staff])
    package = db.relationship('GoiDichVu')
    customer = db.relationship('KhachHang')
    __table_args__ = (db.CheckConstraint("status IN ('pending','paid','failed','cancelled')", name='ck_purchase_status'),)


class TheLieuTrinh(db.Model):
    """Customer treatment entitlement record; never a customer-issued electronic card."""
    __tablename__ = 'thelieutrinh'
    mathe = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    magoi = db.Column(db.Integer, db.ForeignKey('goidichvu.magoi'), nullable=False)
    purchase_id = db.Column(db.Integer, db.ForeignKey('goidichvupurchase.id'), nullable=False, unique=True)
    purchased_at = db.Column(db.DateTime, nullable=False)
    activated_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')
    version = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    purchase = db.relationship('GoiDichVuPurchase')
    customer = db.relationship('KhachHang')
    items = db.relationship('TheLieuTrinhItem', backref='treatment', cascade='all, delete-orphan')
    __table_args__ = (db.CheckConstraint("status IN ('active','used_up','expired','cancelled')", name='ck_treatment_status'),)


class TheLieuTrinhItem(db.Model):
    __tablename__ = 'thelieutrinhitem'
    id = db.Column(db.Integer, primary_key=True)
    mathe = db.Column(db.Integer, db.ForeignKey('thelieutrinh.mathe'), nullable=False)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'), nullable=False)
    total_sessions = db.Column(db.Integer, nullable=False)
    unit_value_snapshot = db.Column(db.Numeric(12, 2), nullable=False)
    regular_price_snapshot = db.Column(db.Numeric(12, 2), nullable=False)
    source_type = db.Column(db.String(20), nullable=False, default='package', server_default='package')
    valid_from = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    gifted_by_staff = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    gift_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now())
    gift_staff = db.relationship('NhanVien')
    service = db.relationship('DichVu')
    __table_args__ = (db.CheckConstraint('total_sessions > 0', name='ck_treatment_sessions'),
                     db.CheckConstraint("source_type IN ('package','gift')", name='ck_treatment_item_source'))


class LieuTrinhUsage(db.Model):
    __tablename__ = 'lieutrinhusage'
    id = db.Column(db.Integer, primary_key=True)
    mathe = db.Column(db.Integer, db.ForeignKey('thelieutrinh.mathe'), nullable=False, index=True)
    the_item_id = db.Column(db.Integer, db.ForeignKey('thelieutrinhitem.id'), nullable=False)
    malh = db.Column(db.Integer, db.ForeignKey('lichhen.malh'), nullable=False, index=True)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'), nullable=False)
    state = db.Column(db.String(20), nullable=False)
    reserved_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime)
    released_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    item = db.relationship('TheLieuTrinhItem')
    __table_args__ = (db.UniqueConstraint('malh', 'madv', name='uq_usage_appointment_service'),
                      db.CheckConstraint("state IN ('reserved','consumed','released')", name='ck_usage_state'))


class NotificationJob(db.Model):
    __tablename__ = 'notificationjob'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(40), nullable=False)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False)
    malh = db.Column(db.Integer, db.ForeignKey('lichhen.malh'), nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    sent_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    payload_json = db.Column(db.JSON, nullable=False)
    unique_key = db.Column(db.String(200), nullable=False, unique=True)
    processing_at = db.Column(db.DateTime)
    first_attempt_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.CheckConstraint("status IN ('pending','processing','sent','failed','cancelled')", name='ck_job_status'),)

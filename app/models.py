from .extensions import db
from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy.schema import FetchedValue
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

# bảng lịch hẹn
class LichHen(db.Model):
    __tablename__ = 'lichhen'
    malh = db.Column(db.Integer, primary_key=True)
    ngaygio = db.Column(db.DateTime, nullable=False)
    trangthai = db.Column(db.String(50), default='Chờ xác nhận')
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False)
    manv = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    khachhang = db.relationship('KhachHang', backref='lichhen', lazy=True)
    chitiet = db.relationship('ChiTietLichHen', backref='lichhen', lazy=True, cascade="all, delete-orphan")
    nhanvien = db.relationship('NhanVien', lazy=True)

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
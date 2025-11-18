-- Script SQL cho PostgreSQL (pgAdmin4)
-- Dựa trên models.py và yêu cầu Tiếng Việt hóa

-- Bảng ChucVu (Phải tạo trước vì NhanVien tham chiếu đến)
CREATE TABLE "ChucVu" (
    "MaChucVu" SERIAL PRIMARY KEY,
    "TenChucVu" VARCHAR(100) NOT NULL,
    "DonGiaGio" NUMERIC(12, 2) NOT NULL
);

-- Bảng KhachHang
CREATE TABLE "KhachHang" (
    "MaKhachHang" SERIAL PRIMARY KEY,
    "HoTen" VARCHAR(100) NOT NULL,
    "SoDienThoai" VARCHAR(20) UNIQUE,
    "DiaChi" VARCHAR(255),
    "Email" VARCHAR(100) UNIQUE,
    "TaiKhoan" VARCHAR(50) NOT NULL UNIQUE,
    "MatKhau" VARCHAR(255) NOT NULL,
    "AnhDaiDien" VARCHAR(255),
    "NgayTao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "TrangThai" VARCHAR(20) DEFAULT 'pending',
    "ResetToken" VARCHAR(255),
    "ResetTokenExpire" TIMESTAMP,
    "OtpCode" VARCHAR(10),
    "OtpExpire" TIMESTAMP
);

-- Bảng NhanVien
CREATE TABLE "NhanVien" (
    "MaNhanVien" SERIAL PRIMARY KEY,
    "HoTen" VARCHAR(100) NOT NULL,
    "SoDienThoai" VARCHAR(20) UNIQUE,
    "DiaChi" VARCHAR(255),
    "Email" VARCHAR(100) UNIQUE,
    "TaiKhoan" VARCHAR(50) NOT NULL UNIQUE,
    "MatKhau" VARCHAR(255) NOT NULL,
    "AnhNhanVien" VARCHAR(255),
    "MaChucVu" INT NOT NULL REFERENCES "ChucVu"("MaChucVu"),
    "NgayTao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "Role" VARCHAR(50) NOT NULL DEFAULT 'staff',
    "TrangThai" BOOLEAN DEFAULT TRUE
);

-- Bảng DichVu
CREATE TABLE "DichVu" (
    "MaDichVu" SERIAL PRIMARY KEY,
    "TenDichVu" VARCHAR(100) NOT NULL,
    "Gia" NUMERIC(12, 2) NOT NULL,
    "ThoiLuong" INT, -- Số phút
    "DonViTinh" VARCHAR(50),
    "AnhDichVu" BYTEA, -- Kiểu LargeBinary trong model
    "Active" BOOLEAN DEFAULT TRUE,
    "MoTa" TEXT
);

-- Bảng LichHen
CREATE TABLE "LichHen" (
    "MaLichHen" SERIAL PRIMARY KEY,
    "NgayGio" TIMESTAMP NOT NULL,
    "TrangThai" VARCHAR(50) DEFAULT 'Chờ xác nhận',
    "MaKhachHang" INT NOT NULL REFERENCES "KhachHang"("MaKhachHang")
);

-- Bảng ChiTietLichHen (Bảng này có 3 khóa chính)
CREATE TABLE "ChiTietLichHen" (
    "MaLichHen" INT NOT NULL REFERENCES "LichHen"("MaLichHen"),
    "MaNhanVien" INT NOT NULL REFERENCES "NhanVien"("MaNhanVien"),
    "MaDichVu" INT NOT NULL REFERENCES "DichVu"("MaDichVu"),
    PRIMARY KEY ("MaLichHen", "MaNhanVien", "MaDichVu")
);

-- Bảng HoaDon
CREATE TABLE "HoaDon" (
    "MaHoaDon" SERIAL PRIMARY KEY,
    "NgayLap" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "TongTien" NUMERIC(12, 2) NOT NULL,
    "MaKhachHang" INT NOT NULL REFERENCES "KhachHang"("MaKhachHang"),
    "MaNhanVien" INT NOT NULL REFERENCES "NhanVien"("MaNhanVien"),
    "TrangThai" VARCHAR(50) DEFAULT 'Chưa thanh toán',
    "MaLichHen" INT UNIQUE REFERENCES "LichHen"("MaLichHen")
);

-- Bảng ChiTietHoaDon
CREATE TABLE "ChiTietHoaDon" (
    "MaChiTietHD" SERIAL PRIMARY KEY,
    "MaHoaDon" INT NOT NULL REFERENCES "HoaDon"("MaHoaDon"),
    "MaDichVu" INT NOT NULL REFERENCES "DichVu"("MaDichVu"),
    "SoLuong" INT DEFAULT 1,
    "DonGia" NUMERIC(12, 2) NOT NULL,
    "ThanhTien" NUMERIC(12, 2) NOT NULL
);

-- Bảng HoiThoai (ĐÃ TỐI ƯU)
CREATE TABLE "HoiThoai" (
    "MaHoiThoai" SERIAL PRIMARY KEY,
    "NgayBatDau" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "MaKhachHang" INT REFERENCES "KhachHang"("MaKhachHang"),
    "MaNhanVien" INT REFERENCES "NhanVien"("MaNhanVien"),
    
    -- Các trường tối ưu được thêm vào:
    "TinNhanCuoi_NoiDung" TEXT, -- Lưu preview tin nhắn cuối
    "TinNhanCuoi_ThoiGian" TIMESTAMP, -- Thời gian của tin nhắn cuối
    "TinNhanCuoi_LaKhachGui" BOOLEAN -- True nếu khách gửi, False nếu NV gửi
);

-- Bảng TinNhan
CREATE TABLE "TinNhan" (
    "MaTinNhan" SERIAL PRIMARY KEY,
    "NoiDung" TEXT NOT NULL,
    "ThoiGianGui" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "MaHoiThoai" INT NOT NULL REFERENCES "HoiThoai"("MaHoiThoai"),
    "NguoiGui_MaKhachHang" INT REFERENCES "KhachHang"("MaKhachHang"),
    "NguoiGui_MaNhanVien" INT REFERENCES "NhanVien"("MaNhanVien")
);

-- Bảng CaLam
CREATE TABLE "CaLam" (
    "MaCaLam" SERIAL PRIMARY KEY,
    "Ngay" DATE NOT NULL,
    "GioBatDau" TIME NOT NULL,
    "GioKetThuc" TIME NOT NULL,
    "HeSoLuong" INT DEFAULT 1,
    "SoGio" NUMERIC(10, 2) -- Cần trigger hoặc tính toán khi insert/update
);

-- Bảng trung gian NhanVien_CaLam
CREATE TABLE "NhanVien_CaLam" (
    "MaNhanVien" INT NOT NULL REFERENCES "NhanVien"("MaNhanVien"),
    "MaCaLam" INT NOT NULL REFERENCES "CaLam"("MaCaLam"),
    PRIMARY KEY ("MaNhanVien", "MaCaLam")
);

-- Bảng ThanhToan
CREATE TABLE "ThanhToan" (
    "MaThanhToan" SERIAL PRIMARY KEY,
    "MaHoaDon" INT NOT NULL REFERENCES "HoaDon"("MaHoaDon"),
    "SoTien" NUMERIC(12, 2) NOT NULL,
    "PhuongThuc" VARCHAR(50) DEFAULT 'Tiền mặt',
    "NgayThanhToan" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "GhiChu" TEXT
);

-- Bảng Luong
CREATE TABLE "Luong" (
    "MaLuong" SERIAL PRIMARY KEY,
    "MaNhanVien" INT NOT NULL REFERENCES "NhanVien"("MaNhanVien"),
    "Thang" INT NOT NULL,
    "Nam" INT NOT NULL,
    "LuongCoBan" NUMERIC(12, 2),
    "Thuong" NUMERIC(12, 2) DEFAULT 0,
    "KhauTru" NUMERIC(12, 2) DEFAULT 0,
    "TongLuong" NUMERIC(12, 2)
);

-- Bảng DangKyCaLam (Dựa trên model DangKyCaLam)
CREATE TABLE "DangKyCaLam" (
    "ID" SERIAL PRIMARY KEY,
    "MaNhanVien" INT NOT NULL REFERENCES "NhanVien"("MaNhanVien"),
    "MaCaLam" INT NOT NULL REFERENCES "CaLam"("MaCaLam"),
    "NgayDangKy" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "TrangThai" VARCHAR(50) DEFAULT 'pending' -- 'pending', 'approved', 'rejected'
);

-- Thêm một số ràng buộc và chỉ mục (Indexes) để tăng tốc độ truy vấn
CREATE INDEX idx_lichhen_ngaygio ON "LichHen" ("NgayGio");
CREATE INDEX idx_tinnhan_mahoithoai ON "TinNhan" ("MaHoiThoai");
CREATE INDEX idx_hoadon_makhachhang ON "HoaDon" ("MaKhachHang");
CREATE INDEX idx_luong_manv ON "Luong" ("MaNhanVien");
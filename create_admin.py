"""
Script tạo tài khoản admin đầu tiên
Chạy: python create_admin.py
"""
import getpass
import os
import sys

from app import create_app, db
from app.models import NhanVien, ChucVu
from werkzeug.security import generate_password_hash

def create_admin():
    app = create_app()
    with app.app_context():
        admin_username = os.getenv("ADMIN_INITIAL_USERNAME", "admin")

        # ========== BƯỚC 1: KIỂM TRA ADMIN ĐÃ TỒN TẠI CHƯA ==========
        existing_admin = NhanVien.query.filter_by(taikhoan=admin_username).first()
        if existing_admin:
            print("=" * 60)
            print("❌ ADMIN ĐÃ TỒN TẠI!")
            print("=" * 60)
            print(f"   Tài khoản: {existing_admin.taikhoan}")
            print(f"   Họ tên: {existing_admin.hoten}")
            print(f"   Email: {existing_admin.email}")
            print(f"   Role: {existing_admin.role}")
            print("=" * 60)
            return
        
        initial_password = os.getenv("ADMIN_INITIAL_PASSWORD")
        if not initial_password and sys.stdin.isatty():
            initial_password = getpass.getpass("Nhập mật khẩu admin ban đầu: ")
        if not initial_password:
            raise RuntimeError(
                "Thiếu ADMIN_INITIAL_PASSWORD. Hãy cấu hình biến môi trường "
                "khi chạy không tương tác."
            )
        if len(initial_password) < 12:
            raise ValueError("ADMIN_INITIAL_PASSWORD phải có ít nhất 12 ký tự")

        admin_email = os.getenv("ADMIN_INITIAL_EMAIL") or None
        admin_phone = os.getenv("ADMIN_INITIAL_PHONE") or None

        # ========== BƯỚC 2: TẠO HOẶC LẤY CHỨC VỤ "ADMIN" ==========
        chucvu_admin = ChucVu.query.filter_by(tencv='Admin').first()
        
        if not chucvu_admin:
            print("🔧 Đang tạo chức vụ Admin...")
            chucvu_admin = ChucVu(
                tencv='Admin',
                dongiagio=0  # Admin không tính theo giờ
            )
            db.session.add(chucvu_admin)
            db.session.flush()  # Lấy ID ngay lập tức
            print(f"✅ Đã tạo chức vụ Admin (ID: {chucvu_admin.macv})")
        else:
            print(f"ℹ️  Chức vụ Admin đã tồn tại (ID: {chucvu_admin.macv})")
        
        # ========== BƯỚC 3: TẠO TÀI KHOẢN ADMIN ==========
        print("🔧 Đang tạo tài khoản Admin...")
        admin = NhanVien(
            taikhoan=admin_username,
            matkhau=generate_password_hash(initial_password),
            hoten='System Administrator',
            email=admin_email,
            sdt=admin_phone,
            macv=chucvu_admin.macv,  # ← Gán chức vụ vừa tạo/lấy
            role='admin',
            trangthai=True
        )
        
        db.session.add(admin)
        db.session.commit()
        
        # ========== HIỂN THỊ THÔNG TIN ==========
        print("=" * 60)
        print("✅ TẠO ADMIN THÀNH CÔNG!")
        print("=" * 60)
        print(f"🔑 Tài khoản: {admin_username}")
        print(f"👤 Họ tên: System Administrator")
        print(f"📧 Email: {admin_email or 'Chưa cấu hình'}")
        print(f"📱 SĐT: {admin_phone or 'Chưa cấu hình'}")
        print(f"💼 Chức vụ: Admin (ID: {chucvu_admin.macv})")
        print(f"⚙️  Role: admin")
        print("=" * 60)
        print("⚠️  VUI LÒNG ĐỔI MẬT KHẨU SAU KHI ĐĂNG NHẬP LẦN ĐẦU!")
        print("=" * 60)

if __name__ == '__main__':
    try:
        create_admin()
    except Exception as e:
        print("=" * 60)
        print(f"❌ LỖI: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()

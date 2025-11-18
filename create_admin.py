"""
Script tạo tài khoản admin đầu tiên
Chạy: python create_admin.py
"""
from app import create_app, db
from app.models import NhanVien
from werkzeug.security import generate_password_hash

def create_admin():
    app = create_app()
    with app.app_context():
        # Kiểm tra admin đã tồn tại chưa
        existing = NhanVien.query.filter_by(taikhoan='admin').first()
        if existing:
            print("❌ Admin đã tồn tại!")
            print(f"   Tài khoản: {existing.taikhoan}")
            print(f"   Họ tên: {existing.hoten}")
            return
        
        # Tạo admin mới
        admin = NhanVien(
            taikhoan='admin',
            matkhau=generate_password_hash('Admin@123456'),
            hoten='System Administrator',
            email='admin@binspa.com',
            sdt='0987654321',
            role='admin',
            trangthai=True
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print("=" * 60)
        print("✅ TẠO ADMIN THÀNH CÔNG!")
        print("=" * 60)
        print(f"🔑 Tài khoản: admin")
        print(f"🔒 Mật khẩu: Admin@123456")
        print(f"📧 Email: admin@binspa.com")
        print(f"📱 SĐT: 0987654321")
        print("=" * 60)
        print("⚠️  VUI LÒNG ĐỔI MẬT KHẨU SAU KHI ĐĂNG NHẬP!")
        print("=" * 60)

if __name__ == '__main__':
    create_admin()
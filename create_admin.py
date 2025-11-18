"""
Script tạo tài khoản admin đầu tiên
Chạy: python create_admin.py
"""
from app import create_app, db
from app.models import NhanVien, ChucVu
from werkzeug.security import generate_password_hash

def create_admin():
    app = create_app()
    with app.app_context():
        # ========== BƯỚC 1: KIỂM TRA ADMIN ĐÃ TỒN TẠI CHƯA ==========
        existing_admin = NhanVien.query.filter_by(taikhoan='admin').first()
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
            taikhoan='admin',
            matkhau=generate_password_hash('Admin@123456'),
            hoten='System Administrator',
            email='admin@binspa.com',
            sdt='0987654321',
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
        print(f"🔑 Tài khoản: admin")
        print(f"🔒 Mật khẩu: Admin@123456")
        print(f"👤 Họ tên: System Administrator")
        print(f"📧 Email: admin@binspa.com")
        print(f"📱 SĐT: 0987654321")
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
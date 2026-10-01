import os
from datetime import date, time
import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    ChucVu,
    HoaDon,
    KhachHang,
    NhanVien,
    DichVu,
    CaLam,
    nhanvien_calam,
    AppointmentStatus,
)


@pytest.fixture()
def app():
    upload_folder = os.path.join(os.getcwd(), "tests", "runtime_uploads")
    os.makedirs(upload_folder, exist_ok=True)
    application = create_app({
        "TESTING": True,
        "APP_ENV": "testing",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": "test-session-secret-not-for-production",
        "JWT_SECRET_KEY": "test-jwt-secret-not-for-production",
        "SEPAY_API_KEY": "test-sepay-key",
        "MOMO_PARTNER_CODE_SANDBOX": "TESTPARTNER",
        "MOMO_ACCESS_KEY_SANDBOX": "test-momo-access",
        "MOMO_SECRET_KEY_SANDBOX": "test-momo-secret",
        "UPLOAD_FOLDER": upload_folder,
        "MAX_CONTENT_LENGTH": 1024 * 1024,
    })

    with application.app_context():
        db.create_all()
        role_staff = ChucVu(tencv="Kỹ thuật viên", dongiagio=100000)
        role_admin = ChucVu(tencv="Quản trị viên", dongiagio=150000)
        db.session.add_all([role_staff, role_admin])
        db.session.flush()

        staff = NhanVien(
            hoten="Nhân viên Test",
            sdt="0900000001",
            diachi="Địa chỉ nội bộ",
            email="staff@example.com",
            taikhoan="staff_test",
            matkhau=generate_password_hash("password"),
            macv=role_staff.macv,
            role="staff",
            trangthai=True,
        )
        staff2 = NhanVien(
            hoten="Nhân viên Test 2",
            sdt="0900000003",
            diachi="Địa chỉ nội bộ 2",
            email="staff2@example.com",
            taikhoan="staff2_test",
            matkhau=generate_password_hash("password"),
            macv=role_staff.macv,
            role="staff",
            trangthai=True,
        )
        admin = NhanVien(
            hoten="Admin Test",
            sdt="0900000004",
            diachi="Văn phòng admin",
            email="admin@example.com",
            taikhoan="admin_test",
            matkhau=generate_password_hash("password"),
            macv=role_admin.macv,
            role="admin",
            trangthai=True,
        )
        customer = KhachHang(
            hoten="Khách hàng Test",
            sdt="0900000002",
            email="customer@example.com",
            taikhoan="customer_test",
            matkhau=generate_password_hash("password"),
            trangthai="active",
        )
        db.session.add_all([staff, staff2, admin, customer])
        db.session.commit()

        application.config["TEST_STAFF_ID"] = staff.manv
        application.config["TEST_STAFF2_ID"] = staff2.manv
        application.config["TEST_ADMIN_ID"] = admin.manv
        application.config["TEST_CUSTOMER_ID"] = customer.makh

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()
    for entry in os.scandir(upload_folder):
        if entry.is_file() and entry.name != ".gitkeep":
            try:
                os.remove(entry.path)
            except OSError:
                pass


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def customer_auth_headers(app):
    with app.app_context():
        token = create_access_token(
            identity=f"customer:{app.config['TEST_CUSTOMER_ID']}"
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def staff_auth_headers(app):
    with app.app_context():
        token = create_access_token(
            identity=f"staff:{app.config['TEST_STAFF_ID']}"
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_auth_headers(app):
    with app.app_context():
        token = create_access_token(
            identity=f"staff:{app.config['TEST_ADMIN_ID']}"
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def create_invoice(app):
    def factory(amount=100000):
        with app.app_context():
            invoice = HoaDon(
                tongtien=amount,
                makh=app.config["TEST_CUSTOMER_ID"],
                manv=app.config["TEST_STAFF_ID"],
                trangthai="Chưa thanh toán",
            )
            db.session.add(invoice)
            db.session.commit()
            return invoice.mahd

    return factory

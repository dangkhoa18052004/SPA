"""Local customer UI preview using the existing disposable SQLite test fixture.

python tests/customer_ui_preview.py [--new-ui] [--port 5077]
No real email, payment provider or production database is used.
"""
import argparse
import sys
from datetime import datetime, timedelta, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from flask import request, session, redirect
from app.extensions import db
from app.models import DichVu, DanhMucDichVu, HoaDon, LichHen, ChiTietLichHen, CaLam, nhanvien_calam
from app.services import email_service, package_service, appointment_service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--new-ui', action='store_true')
    parser.add_argument('--port', type=int, default=5077)
    parser.add_argument('--preferences', action='store_true')
    args = parser.parse_args()
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    app.config.update(CUSTOMER_PUBLIC_UI_ENABLED=args.new_ui,
                      CUSTOMER_ACCOUNT_REACT_ENABLED=args.new_ui,
                      CUSTOMER_CONSENT_ENABLED=args.preferences,
                      CUSTOMER_BOOKING_REACT_ENABLED=True,
                      MAIL_SUPPRESS_SEND=True, SEPAY_API_KEY='',
                      VIETQR_BANK_BIN='', VIETQR_ACCOUNT_NO='',
                      GEMINI_API_KEY='', SESSION_COOKIE_SECURE=False)
    email_service.send_email = lambda *a, **kw: None
    appointment_service.send_appointment_confirmation_email_async = lambda *a, **kw: None
    upload = Path(__file__).resolve().parents[1] / '.test-tmp/customer-ui/uploads'
    upload.mkdir(parents=True, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = str(upload)
    with app.app_context():
        category = DanhMucDichVu(name='Chăm sóc cơ thể', slug='body-care')
        db.session.add(category)
        db.session.flush()
        names = ['Massage thư giãn', 'Chăm sóc da mặt', 'Gội đầu dưỡng sinh',
                 'Chăm sóc cơ thể với tên dịch vụ dài để kiểm tra xuống dòng']
        for index, name in enumerate(names):
            db.session.add(DichVu(tendv=name, gia=150000 + index * 50000,
                                 thoiluong=30 + index * 15, active=True,
                                 category_id=category.id,
                                 mota='Dữ liệu kiểm thử giao diện local.'))
        db.session.commit()
        first = DichVu.query.order_by(DichVu.madv).first()
        package_service.save_package(dict(tengoi='Gói kiểm thử giao diện', giagoi=600000,
            validity_months=3, active=True, customer_sale_enabled=True,
            items=[dict(madv=first.madv, total_sessions=5)]))
        today = appointment_service.vn_now().date()
        day = today + timedelta(days=3)
        shift = CaLam(ngay=day, giobatdau=time(8), gioketthuc=time(18), sogio=10)
        db.session.add(shift)
        db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'],maca=shift.maca))
        for status, when in [('confirmed',datetime.combine(day,time(9))),('completed',datetime.combine(today-timedelta(days=1),time(9)))]:
            appointment = LichHen(makh=app.config['TEST_CUSTOMER_ID'],manv=app.config['TEST_STAFF_ID'],ngaygio=when,trangthai=status)
            db.session.add(appointment)
            db.session.flush()
            db.session.add(ChiTietLichHen(malh=appointment.malh,madv=first.madv))
        for status in ('Chưa thanh toán', 'Đã thanh toán', 'Đã hủy'):
            db.session.add(HoaDon(tongtien=150000,makh=app.config['TEST_CUSTOMER_ID'],manv=app.config['TEST_STAFF_ID'],trangthai=status))
        db.session.commit()

    @app.route('/__preview/session')
    def preview_session():
        # Only present in this loopback-only preview, never registered by create_app.
        session.clear()
        if request.args.get('customer') == '1':
            session.update(user_id=app.config['TEST_CUSTOMER_ID'], user_type='customer')
        return redirect('/profile' if session else '/')

    try:
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
    finally:
        fixture.close()


if __name__ == '__main__':
    main()

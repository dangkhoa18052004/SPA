"""Loopback-only master-plan QA server. Disposable SQLite; no real providers."""
import argparse
import os
from datetime import datetime, timedelta, time
from pathlib import Path
import sys
from threading import RLock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from flask import g, jsonify, request, session, redirect
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import DanhMucDichVu, DichVu, Hoithoai, TinNhan, NhanVien, KhachHang, HoaDon, CaLam, nhanvien_calam, LichHen, ChiTietLichHen
from app.services import package_service, loyalty_service, email_service, appointment_service

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5088)
    parser.add_argument('--all-ui', action='store_true', help='Enable all UI modules in the disposable review fixture.')
    parser.add_argument('--payments',action='store_true',help='Only offline test account/SQLite transactions; browser intercepts QR image.')
    args = parser.parse_args()
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    app.config.update(CUSTOMER_PUBLIC_UI_ENABLED=True, CUSTOMER_ACCOUNT_REACT_ENABLED=True,
        CUSTOMER_BOOKING_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True, BUSINESS_PORTAL_ENABLED=True,
        ADMIN_CARE_REACT_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=True, ADMIN_PEOPLE_REACT_ENABLED=True,
        STAFF_SECURITY_ENABLED=False, MAIL_SUPPRESS_SEND=True, SESSION_COOKIE_SECURE=False,
        SEPAY_API_KEY='', VIETQR_BANK_BIN='', VIETQR_ACCOUNT_NO='', GEMINI_API_KEY='')
    app.jinja_env.auto_reload = True
    # sqlite:// shares one connection; serialize browser requests so parallel
    # reads/rollbacks cannot interfere with each other's transactions.
    request_lock = RLock()
    @app.before_request
    def lock_request():
        request_lock.acquire()
        g.qa_request_locked = True
    @app.teardown_request
    def unlock_request(error):
        # An earlier before_request hook may short-circuit before ours runs.
        if g.pop('qa_request_locked', False):
            db.session.remove()
            request_lock.release()
    if args.all_ui:
        app.config.update(ADMIN_BILLING_REACT_ENABLED=True, ADMIN_CATALOG_REACT_ENABLED=True,
            CRM_ENABLED=True, BI_REPORTS_ENABLED=True, ATTENDANCE_ENABLED=True,
            PAYROLL_V2_ENABLED=True, STAFF_SECURITY_ENABLED=True)
    if args.payments:
        app.config.update(VIETQR_BANK_ID='970407',VIETQR_ACCOUNT_NO='000000000000',VIETQR_ACCOUNT_NAME='QA NOT A REAL ACCOUNT')
    # app/config.py loads .env, so the real Resend key is in this process. Remove it (any missed path then
    # fails instead of mailing a real inbox) and capture mail from every module that imported send_email by name.
    os.environ.pop('RESEND_API_KEY', None)
    email_service.resend.api_key = None
    outbox = []
    def capture_email(to_email, subject, body, *a, **k):
        outbox.append(dict(to=to_email, subject=subject, body=body, at=datetime.utcnow().isoformat()))
        return True
    original_send = email_service.send_email
    for module in list(sys.modules.values()):
        if getattr(module, 'send_email', None) is original_send:
            module.send_email = capture_email
    appointment_service.send_appointment_confirmation_email_async = lambda *a, **k: None
    with app.app_context():
        categories = [DanhMucDichVu(name=name, slug=slug, active=active) for name,slug,active in
            [('Chăm sóc da mụn','acne',True),('Chăm sóc cơ thể','body-care',True),('Danh mục trống','empty',True),('Ẩn','hidden',False)]]
        db.session.add_all(categories); db.session.flush()
        for i in range(25):
            db.session.add(DichVu(tendv=f'Dịch vụ {i+1:02d} massage trong tên', gia=100000+i*10000,
                thoiluong=30+i, active=True, category_id=categories[i%2].id if i<24 else None,
                mota='Nội dung kiểm thử local, không phải danh mục sản xuất.'))
        db.session.commit()
        first = DichVu.query.order_by(DichVu.madv).first()
        for i in range(25):
            package_service.save_package(dict(tengoi=f'Gói kiểm thử {i+1:02d}', giagoi=200000+i*10000,
                mota='Mô tả kiểm thử có tên dài để xác minh bố cục.', validity_months=3,
                active=True, customer_sale_enabled=True, items=[dict(madv=first.madv,total_sessions=10)]))
        customer_id, staff_id = app.config['TEST_CUSTOMER_ID'], app.config['TEST_STAFF_ID']
        original_staff=db.session.get(NhanVien,staff_id)
        for role in ('manager','letan'):
            actor=NhanVien(hoten=f'Kiểm thử {role}',taikhoan=f'qa_{role}',matkhau=original_staff.matkhau,
                macv=original_staff.macv,role=role,trangthai=True)
            db.session.add(actor);db.session.flush();app.config[f'TEST_{role.upper()}_ID']=actor.manv
        purchase=package_service.create_purchase(1,customer_id,'cash')
        package_service.confirm_purchase(purchase.id,purchase.amount)
        day=appointment_service.vn_now().date()+timedelta(days=3)
        shift=CaLam(ngay=day,giobatdau=time(8),gioketthuc=time(18),sogio=10)
        db.session.add(shift);db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=staff_id,maca=shift.maca))
        db.session.add(HoaDon(makh=customer_id,manv=staff_id,tongtien=500000,trangthai='Chưa thanh toán'))
        # Two appointments today (two customers, two staff) for dashboard -> exact appointment deep links.
        today=appointment_service.vn_now().date()
        walk_in=KhachHang(hoten='Khách lịch hôm nay',taikhoan='qa-today',sdt='0900000099',matkhau='unused-test-hash',trangthai='active')
        db.session.add(walk_in);db.session.flush()
        for hour,makh,manv,madv in [(9,customer_id,staff_id,first.madv),(15,walk_in.makh,app.config['TEST_STAFF2_ID'],first.madv+1)]:
            visit=LichHen(ngaygio=datetime.combine(today,time(hour)),trangthai='confirmed',makh=makh,manv=manv,booking_source='admin')
            db.session.add(visit);db.session.flush();db.session.add(ChiTietLichHen(malh=visit.malh,madv=madv))
        conv = Hoithoai(makh=customer_id, manv=staff_id, tin_nhan_cuoi_noi_dung='Xin tư vấn dịch vụ', tin_nhan_cuoi_thoi_gian=datetime.utcnow())
        db.session.add(conv); db.session.flush()
        db.session.add(TinNhan(maht=conv.maht, nguoigui_makh=customer_id, noidung='Xin tư vấn dịch vụ', da_doc=False))
        for index in range(2,18):
            customer=KhachHang(hoten=f'Khách chat {index:02d}',taikhoan=f'qa-chat-{index}',matkhau='unused-test-hash',trangthai='active')
            db.session.add(customer);db.session.flush()
            thread=Hoithoai(makh=customer.makh,manv=staff_id if index<17 else app.config['TEST_STAFF2_ID'],tin_nhan_cuoi_noi_dung=f'Tin nhắn {index}',tin_nhan_cuoi_thoi_gian=datetime.utcnow()-timedelta(minutes=index))
            db.session.add(thread);db.session.flush()
            for n in range(100 if index==17 else 1):
                db.session.add(TinNhan(maht=thread.maht,nguoigui_makh=customer.makh,noidung=f'Tin nhắn {index}-{n}',da_doc=False))
        loyalty_service.admin_adjust_points(customer_id, 10000, 'QA isolated fixture', app.config['TEST_ADMIN_ID'], 'qa-fund')
        for kind in ['physical_gift','voucher_percent']:
            reward = loyalty_service.save_reward(dict(name='Khăn BinSpa' if kind=='physical_gift' else 'Voucher giảm 30% có điều kiện áp dụng', reward_type=kind, points_cost=50, percentage_value=30 if kind=='voucher_percent' else None, validity_days=30))
            loyalty_service.redeem_reward(customer_id, reward.id, 'qa-'+kind)
            if args.payments and kind=='voucher_percent':
                loyalty_service.redeem_reward(customer_id,reward.id,'qa-voucher-desktop')
        db.session.commit()

    @app.route('/__qa/login/<role>')
    def login(role):
        session.clear()
        if role == 'guest':
            return jsonify(success=True)
        kind = 'customer' if role == 'customer' else 'staff'
        key = 'TEST_CUSTOMER_ID' if kind=='customer' else f'TEST_{role.upper()}_ID'
        uid = app.config[key]
        session.update(user_id=uid,user_type=kind)
        if kind=='staff':
            with app.app_context():
                actor = db.session.get(NhanVien, uid)
                session['user_role'] = actor.role
                role_name=actor.role
        else:
            role_name='customer'
        return jsonify(access_token=create_access_token(identity=f'{kind}:{uid}'),role=role_name)

    @app.route('/__qa/expired-token/<role>')
    def expired_token(role):
        # Signed by the fixture key but already expired: exercises the real "session expired" path.
        kind = 'customer' if role == 'customer' else 'staff'
        uid = app.config['TEST_CUSTOMER_ID' if kind=='customer' else f'TEST_{role.upper()}_ID']
        return jsonify(access_token=create_access_token(identity=f'{kind}:{uid}', expires_delta=timedelta(seconds=-60)))

    @app.route('/__qa/outbox')
    def qa_outbox():
        # Fixture mailbox: OTP / reset codes are read here instead of a real inbox.
        to = request.args.get('to')
        return jsonify(messages=[m for m in outbox if not to or m['to'] == to])

    @app.route('/__qa/ping')
    def ping():
        return jsonify(success=True, environment='isolated-sqlite', services=25, packages=25)

    @app.route('/__qa/pages')
    def pages():
        return jsonify(pages=sorted(str(rule) for rule in app.url_map.iter_rules()
            if 'GET' in rule.methods and not str(rule).startswith(('/api/', '/static/', '/__qa/'))))

    @app.route('/__qa/state', methods=['POST'])
    def qa_state():
        # Fixture-only shortcuts for states the UI cannot reach (expired gift, cancelled treatment, bank confirmation).
        from app.models import TheLieuTrinh, TheLieuTrinhItem, GoiDichVuPurchase
        d = request.get_json(force=True)
        yesterday = datetime.combine(appointment_service.vn_now().date()-timedelta(days=1), time.max)
        if 'treatment' in d:
            record = db.session.get(TheLieuTrinh, d['treatment'])
            record.status = d.get('status', record.status)
            if d.get('expired'):
                record.expires_at = yesterday
        if 'item' in d:
            db.session.get(TheLieuTrinhItem, d['item']).expires_at = yesterday
        if 'service' in d:
            db.session.get(DichVu, d['service']).active = d['active']
        if 'customer' in d:
            db.session.get(KhachHang, d['customer']).trangthai = d['trangthai']
        if 'expire_codes' in d:
            # Expire a customer's pending OTP and password-reset codes (by email).
            for customer in KhachHang.query.filter_by(email=d['expire_codes']):
                customer.otp_expire = customer.resettokenexpire = datetime.utcnow() - timedelta(minutes=1)
        if 'vietqr_paid' in d:
            purchase = db.session.get(GoiDichVuPurchase, d['vietqr_paid'])
            package_service.confirm_purchase(purchase.id, loyalty_service.payable(purchase),
                external_id=f'QA-BANK-{purchase.id}', method='vietqr')
        db.session.commit()
        return jsonify(success=True)

    @app.route('/__qa/customer-token/<int:conversation_id>')
    def customer_token(conversation_id):
        conversation=db.session.get(Hoithoai,conversation_id)
        return jsonify(access_token=create_access_token(identity=f'customer:{conversation.makh}'))

    try:
        # Browser route.fetch and normal navigation can keep separate sockets
        # alive. A single-threaded development server can block accepting one.
        app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False,threaded=True)
    finally:
        fixture.close()

if __name__ == '__main__':
    main()

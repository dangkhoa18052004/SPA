"""Disposable loopback-only UI fixture. In-memory SQLite, captured email, no providers."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from flask import jsonify, session, request
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import KhachHang, NhanVien, HoaDon
from app.services import loyalty_service as loyalty


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=59147);args=parser.parse_args()
    fixture=conftest.app.__wrapped__();app=next(fixture)
    app.config.update(BUSINESS_PORTAL_ENABLED=True,ADMIN_CARE_REACT_ENABLED=True,ADMIN_BOOKING_REACT_ENABLED=True,
        CUSTOMER_PUBLIC_UI_ENABLED=True,CUSTOMER_ACCOUNT_REACT_ENABLED=True,SESSION_COOKIE_SECURE=False,
        MAIL_SUPPRESS_SEND=True,GEMINI_API_KEY='',SEPAY_API_KEY='')
    import app.routes.auth_bp as auth
    auth.send_email=lambda *args,**kwargs: True
    with app.app_context():
        actor=db.session.get(NhanVien,app.config['TEST_STAFF_ID'])
        for role in ('manager','letan'):
            staff=NhanVien(hoten='Kiểm thử '+role,taikhoan='voucher-'+role,matkhau=actor.matkhau,macv=actor.macv,role=role,trangthai=True)
            db.session.add(staff);db.session.flush();app.config['TEST_'+role.upper()+'_ID']=staff.manv
        for i in range(12):
            loyalty.save_reward(dict(name=f'Voucher thử {i+1:02d}',reward_type='voucher_amount' if i%2==0 else 'voucher_percent',
                points_cost=0,reward_value=50000 if i%2==0 else 0,percentage_value=20 if i%2 else None,
                max_discount_amount=70000 if i%2 else None,minimum_spend=300000,apply_to='service_invoice',
                allow_points_redemption=False,allow_manual_gift=True,stock=10,validity_days=30))
        db.session.add(HoaDon(makh=app.config['TEST_CUSTOMER_ID'],manv=app.config['TEST_ADMIN_ID'],tongtien=500000,trangthai='Chưa thanh toán'))
        db.session.commit()

    @app.route('/__qa/ping')
    def ping():return jsonify(success=True)

    @app.route('/__qa/mode/<mode>')
    def mode(mode):
        app.config.update(ADMIN_CARE_REACT_ENABLED=mode!='legacy',ADMIN_BOOKING_REACT_ENABLED=mode!='legacy')
        return jsonify(success=True)

    @app.route('/__qa/login/<role>')
    def login(role):
        session.clear();kind='customer' if role=='customer' else 'staff'
        uid=app.config['TEST_CUSTOMER_ID' if role=='customer' else 'TEST_'+role.upper()+'_ID']
        session.update(user_id=uid,user_type=kind)
        if kind=='staff':session['user_role']=role
        return jsonify(access_token=create_access_token(identity=f'{kind}:{uid}'),role=role)

    @app.route('/__qa/registration')
    def registration():
        user=KhachHang.query.filter_by(taikhoan=request.args.get('account', 'browser-voucher-new')).first()
        return jsonify(otp=user.otp_code if user else None)

    try:app.run(host='127.0.0.1',port=args.port,threaded=False,debug=False,use_reloader=False)
    finally:
        try:next(fixture)
        except StopIteration:pass


if __name__=='__main__':main()

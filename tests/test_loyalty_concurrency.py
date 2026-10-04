"""Real concurrent connections; optional PostgreSQL uses a fresh, isolated schema.

Set TEST_LOYALTY_POSTGRES_URL to an isolated test server to verify PostgreSQL locks.
The suite never connects to DATABASE_URL or the application's existing database.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, func
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import KhachHang, NhanVien, ChucVu, HoaDon, ThanhToan, LoyaltyWallet, LoyaltyPointTransaction, LoyaltyRewardRedemption
from app.services import loyalty_service as loyalty


@pytest.fixture(params=['sqlite', 'postgresql'])
def concurrent_app(request):
    test_dir=Path('tests')/('loyalty-concurrency-'+uuid4().hex+'.tmp')
    url=os.environ.get('TEST_LOYALTY_POSTGRES_URL') if request.param=='postgresql' else 'sqlite:///'+str((test_dir/'loyalty.db').resolve())
    if not url:
        pytest.skip('TEST_LOYALTY_POSTGRES_URL not configured')
    if request.param=='sqlite':
        test_dir.mkdir()
    schema='loyalty_test_'+uuid4().hex
    engine=None
    options={'connect_args':{'timeout':20}}
    if request.param=='postgresql':
        engine=create_engine(url)
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        options={'connect_args':{'options':f'-csearch_path={schema}'}}
    application=create_app(dict(TESTING=True,APP_ENV='testing',SQLALCHEMY_DATABASE_URI=url,
        SQLALCHEMY_ENGINE_OPTIONS=options,SECRET_KEY='concurrent-test',JWT_SECRET_KEY='concurrent-test-secret-at-least-32-chars',SEPAY_API_KEY='test-sepay-key'))
    with application.app_context():
        db.create_all()
        role=ChucVu(tencv='Test',dongiagio=1);db.session.add(role);db.session.flush()
        staff=NhanVien(hoten='Admin',taikhoan='admin',matkhau='hash',macv=role.macv,role='admin')
        customer=KhachHang(hoten='Customer',taikhoan='customer',matkhau='hash')
        other=KhachHang(hoten='Other',taikhoan='other',matkhau='hash')
        db.session.add_all([staff,customer,other]);db.session.flush()
        loyalty.admin_adjust_points(customer.makh,300,'Initial',staff.manv,'initial')
        loyalty.admin_adjust_points(other.makh,300,'Initial',staff.manv,'initial-other')
        invoices=[HoaDon(makh=customer.makh,manv=staff.manv,tongtien=1000000) for _ in range(2)]
        db.session.add_all(invoices);db.session.commit()
        application.config['RACE_IDS']=[i.mahd for i in invoices]
        application.config['RACE_CUSTOMERS']=[customer.makh,other.makh]
        application.config['RACE_HEADERS']={'Authorization':'Bearer '+create_access_token(identity=f'staff:{staff.manv}')}
    yield application
    with application.app_context():
        db.session.remove();db.engine.dispose()
    if engine:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
    else:
        (test_dir/'loyalty.db').unlink()
        test_dir.rmdir()


def race(function, arguments):
    barrier=Barrier(len(arguments))
    def run(argument):
        barrier.wait(timeout=10)
        return function(argument)
    with ThreadPoolExecutor(max_workers=len(arguments)) as executor:
        return list(executor.map(run,arguments))


def test_two_payments_cannot_reserve_same_points(concurrent_app):
    app=concurrent_app
    def reserve(invoice):
        with app.test_client() as client:
            return client.post(f'/api/admin/invoices/{invoice}/loyalty',headers=app.config['RACE_HEADERS'],json={'points':250}).status_code
    assert sorted(race(reserve,app.config['RACE_IDS']))==[200,400]
    with app.app_context():
        wallet=LoyaltyWallet.query.filter_by(makh=app.config['RACE_CUSTOMERS'][0]).one()
        assert (wallet.available_points,wallet.reserved_points)==(50,250)
        assert db.session.query(func.sum(LoyaltyPointTransaction.points_delta)).filter_by(makh=wallet.makh).scalar()==300


def test_concurrent_cash_clicks_settle_once(concurrent_app):
    app=concurrent_app;invoice=app.config['RACE_IDS'][0]
    with app.test_client() as client:
        assert client.post(f'/api/admin/invoices/{invoice}/loyalty',headers=app.config['RACE_HEADERS'],json={'points':100}).status_code==200
    def pay(_):
        with app.test_client() as client:
            return client.post(f'/api/admin/invoices/{invoice}/record-payment',headers=app.config['RACE_HEADERS'],json={'sotien':900000,'phuongthuc':'Tiền mặt'}).status_code
    assert sorted(race(pay,[1,2]))==[201,400]
    with app.app_context():
        assert ThanhToan.query.filter_by(mahd=invoice).count()==1
        assert LoyaltyPointTransaction.query.filter_by(type='earn').count()==1
        assert LoyaltyPointTransaction.query.filter_by(type='redeem').count()==1


def test_concurrent_duplicate_bank_callbacks_settle_once(concurrent_app):
    app=concurrent_app;invoice=app.config['RACE_IDS'][0]
    with app.test_client() as client:
        client.post(f'/api/admin/invoices/{invoice}/loyalty',headers=app.config['RACE_HEADERS'],json={'points':100})
    def pay(_):
        with app.test_client() as client:
            response=client.post('/api/payment/webhook/sepay',headers={'Authorization':'Apikey test-sepay-key'},json=dict(id='duplicate-bank',content=f'HD{invoice}',transferAmount=900000))
            assert response.status_code==200,response.json
            return response.json['status']
    assert sorted(race(pay,[1,2]))==['duplicate','success']
    with app.app_context():
        assert ThanhToan.query.count()==1
        assert LoyaltyPointTransaction.query.filter_by(type='earn').count()==1
        assert LoyaltyPointTransaction.query.filter_by(type='redeem').count()==1


def test_reward_stock_cannot_be_oversold(concurrent_app):
    app=concurrent_app
    with app.app_context():
        reward=loyalty.save_reward(dict(name='Last gift',reward_type='physical_gift',points_cost=200,reward_value=0,stock=1))
        db.session.commit();reward_id=reward.id
    def redeem(customer):
        with app.app_context():
            try:
                loyalty.redeem_reward(customer,reward_id,str(customer));db.session.commit();return 'ok'
            except loyalty.LoyaltyError:
                db.session.rollback();return 'rejected'
    assert sorted(race(redeem,app.config['RACE_CUSTOMERS']))==['ok','rejected']
    with app.app_context():
        assert LoyaltyRewardRedemption.query.count()==1
        assert sorted(w.available_points for w in LoyaltyWallet.query.all())==[100,300]


def test_redemption_filters_match_effective_status_on_each_backend(concurrent_app):
    # JSON snapshot lookups compile differently per dialect (JSON_EXTRACT vs ->>).
    from datetime import datetime, timedelta
    with concurrent_app.app_context():
        makh=concurrent_app.config['RACE_CUSTOMERS'][0]
        voucher=loyalty.save_reward(dict(name='Voucher 100%_off',reward_type='voucher_amount',points_cost=50,reward_value=50000))
        gift=loyalty.save_reward(dict(name='Quà tặng',reward_type='physical_gift',points_cost=50,reward_value=0))
        live=loyalty.redeem_reward(makh,voucher.id,'live');expired=loyalty.redeem_reward(makh,voucher.id,'expired')
        loyalty.redeem_reward(makh,gift.id,'gift')
        expired.expires_at=datetime.utcnow()-timedelta(minutes=1);db.session.commit()
        base=LoyaltyRewardRedemption.query.filter_by(makh=makh)
        ids=lambda **kw:sorted(r.id for r in loyalty.filter_redemptions(base,**kw).all())
        assert ids(group='usable')==[live.id]
        assert ids(group='closed')==[expired.id]
        assert len(ids(group='pickup'))==1 and len(ids(reward_type='physical_gift'))==1
        assert len(ids(search='100%_'))==2 and ids(search='quà')==ids(group='pickup')
        assert ids(search=live.code[-5:].lower())==[live.id]

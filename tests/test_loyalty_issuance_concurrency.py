from datetime import datetime, timedelta
from test_loyalty_concurrency import concurrent_app, race
from app.extensions import db
from app.models import KhachHang, LoyaltyReward, LoyaltyRewardRedemption, LoyaltyPointTransaction, CustomerOtpRegistration
from app.services import loyalty_service as loyalty, voucher_issuance_service as issuance


def setup_template(app, stock=10):
    with app.app_context():
        KhachHang.query.update({KhachHang.trangthai:'active'})
        reward=loyalty.save_reward(dict(name='Shared',reward_type='voucher_amount',points_cost=50,reward_value=50000,
            allow_manual_gift=True,stock=stock,validity_days=30))
        db.session.commit();return reward.id


def send(app, customer, template, key):
    with app.test_client() as client:
        return client.post(f'/api/admin/loyalty/customers/{customer}/voucher-gifts',
            headers={**app.config['RACE_HEADERS'],'Idempotency-Key':key},json={'reward_id':template,'reason':'Gift'}).status_code


def test_manual_simultaneous_replay_and_different_payload(concurrent_app):
    app=concurrent_app;template=setup_template(app);customer,other=app.config['RACE_CUSTOMERS']
    assert sorted(race(lambda _:send(app,customer,template,'same'),[1,2]))==[200,201]
    assert sorted(race(lambda c:send(app,c,template,'different'),[customer,other]))==[201,409]
    with app.app_context():
        assert LoyaltyRewardRedemption.query.count()==2
        assert db.session.get(LoyaltyReward,template).stock==8
        assert LoyaltyPointTransaction.query.count()==2  # Only fixture funding, no gift entries.


def test_manual_and_points_share_last_stock(concurrent_app):
    app=concurrent_app;template=setup_template(app,1);customer,other=app.config['RACE_CUSTOMERS']
    def action(kind):
        if kind=='gift':return 'ok' if send(app,customer,template,'last')==201 else 'rejected'
        with app.app_context():
            try:loyalty.redeem_reward(other,template,'last-points');db.session.commit();return 'ok'
            except loyalty.LoyaltyError:db.session.rollback();return 'rejected'
    assert sorted(race(action,['gift','points']))==['ok','rejected']
    with app.app_context():
        assert LoyaltyRewardRedemption.query.count()==1
        assert db.session.get(LoyaltyReward,template).stock==0


def test_welcome_otp_race_issues_once(concurrent_app):
    app=concurrent_app;template=setup_template(app,1)
    with app.app_context():
        from app.models import NhanVien
        issuance.update_welcome_config(dict(enabled=True,reward_id=template,starts_at=(datetime.utcnow()-timedelta(minutes=1)).isoformat()+'Z'),NhanVien.query.one().manv)
        user=KhachHang(hoten='OTP race',taikhoan='otp-race',matkhau='hash',trangthai='pending',otp_code='987654',otp_expire=datetime.utcnow()+timedelta(minutes=10))
        db.session.add(user);db.session.flush();db.session.add(CustomerOtpRegistration(makh=user.makh,registered_at=user.ngaytao));db.session.commit();uid=user.makh
    def activate(_):
        with app.test_client() as client:return client.post('/api/auth/verify-otp',json={'otp_code':'987654'}).status_code
    codes=sorted(race(activate,[1,2]))
    assert codes[0]==200 and codes[1] in (400,404)
    with app.app_context():
        assert db.session.get(KhachHang,uid).trangthai=='active'
        assert LoyaltyRewardRedemption.query.filter_by(makh=uid).count()==1
        assert db.session.get(LoyaltyReward,template).stock==0


def test_cancel_and_apply_only_one_wins(concurrent_app):
    app=concurrent_app;template=setup_template(app);customer=app.config['RACE_CUSTOMERS'][0]
    assert send(app,customer,template,'cancel-race')==201
    with app.app_context():rid=LoyaltyRewardRedemption.query.one().id
    invoice=app.config['RACE_IDS'][0]
    def action(kind):
        with app.test_client() as client:
            if kind=='cancel':return client.post(f'/api/admin/loyalty/voucher-gifts/{rid}/cancel',headers=app.config['RACE_HEADERS'],json={'reason':'Mistake'}).status_code
            return client.post(f'/api/admin/invoices/{invoice}/reward',headers=app.config['RACE_HEADERS'],json={'redemption_id':rid}).status_code
    codes=race(action,['cancel','apply'])
    assert codes in ([200,400],[409,200])
    with app.app_context():
        from app.models import HoaDon
        row=db.session.get(LoyaltyRewardRedemption,rid);target=db.session.get(HoaDon,invoice)
        assert (row.status=='cancelled' and target.reward_discount==0) or (row.status=='reserved' and target.reward_discount==50000)

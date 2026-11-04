from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import (KhachHang, NhanVien, LoyaltyReward, LoyaltyRewardRedemption,
    LoyaltyWallet, LoyaltyPointTransaction, CustomerOtpRegistration, WelcomeVoucherConfig)
from app.services import loyalty_service as loyalty, voucher_issuance_service as issuance


@pytest.fixture
def gift_template(app):
    with app.app_context():
        reward = loyalty.save_reward(dict(name='Quà spa 50k', reward_type='voucher_amount', points_cost=0,
            reward_value=50000, allow_points_redemption=False, allow_manual_gift=True, stock=5,
            validity_days=30, minimum_spend=300000, apply_to='service_invoice'))
        db.session.commit()
        return reward.id


def gift(client, app, headers, reward, key='gift-1', **body):
    return client.post(f"/api/admin/loyalty/customers/{app.config['TEST_CUSTOMER_ID']}/voucher-gifts",
        headers={**headers, 'Idempotency-Key': key}, json={'reward_id':reward, 'reason':'Chăm sóc khách', 'customer_message':'Chúc bạn vui!', **body})


def test_manual_zero_points_replay_payload_stock_snapshot_and_privacy(app, client, admin_auth_headers, customer_auth_headers, gift_template):
    first = gift(client, app, admin_auth_headers, gift_template)
    assert first.status_code == 201, first.json
    row = first.json['redemption']
    assert row['points_spent'] == 0 and row['issuance_source'] == 'staff_gift'
    assert row['issued_by_staff'] == app.config['TEST_ADMIN_ID']
    replay = gift(client, app, admin_auth_headers, gift_template)
    assert replay.status_code == 200 and replay.json['redemption']['id'] == row['id']
    conflict = client.post(
        f"/api/admin/loyalty/customers/{app.config['TEST_CUSTOMER_ID']}/voucher-gifts",
        headers={**admin_auth_headers, 'Idempotency-Key': 'gift-1'}, json=dict(reward_id=gift_template, reason='Nội dung khác'))
    assert conflict.status_code == 409
    assert gift(client, app, admin_auth_headers, gift_template, key='gift-2').status_code == 201
    with app.app_context():
        assert LoyaltyRewardRedemption.query.count() == 2
        assert db.session.get(LoyaltyReward, gift_template).stock == 3
        assert LoyaltyPointTransaction.query.count() == LoyaltyWallet.query.count() == 0
        loyalty.save_reward(dict(reward_value=99999, validity_days=1), db.session.get(LoyaltyReward, gift_template))
        db.session.commit()
    offers = client.get('/api/loyalty/my-rewards', headers=customer_auth_headers).json['items']
    assert len(offers) == 2
    for offer in offers:
        assert offer['customer_message'] == 'Chúc bạn vui!'
        assert offer['reward']['reward_value'] == '50000.00'
        assert not {'gift_reason','issued_by_staff','issued_by_name','issuance_payload_json','cancel_reason'} & offer.keys()
    catalog = client.get('/api/loyalty/rewards', headers=customer_auth_headers).json
    assert catalog['total'] == 0
    redeem = client.post(f'/api/loyalty/rewards/{gift_template}/redeem', headers=customer_auth_headers, json={'idempotency_key':'try'})
    assert redeem.status_code == 400


@pytest.mark.parametrize('role', ['manager', 'letan'])
def test_authorized_roles_can_gift_but_only_managers_configure_cancel(app, client, gift_template, role):
    with app.app_context():
        actor = db.session.get(NhanVien, app.config['TEST_STAFF_ID']); actor.role = role
        db.session.commit(); headers = {'Authorization':'Bearer '+create_access_token(identity=f'staff:{actor.manv}')}
    result = gift(client, app, headers, gift_template)
    assert result.status_code == 201
    rid = result.json['redemption']['id']
    expected = 200 if role == 'manager' else 403
    assert client.get('/api/admin/loyalty/welcome-config', headers=headers).status_code == expected
    assert client.post(f'/api/admin/loyalty/voucher-gifts/{rid}/cancel', headers=headers, json={'reason':'Tặng nhầm'}).status_code == expected


def test_permissions_validation_recipients_and_actor_spoofing(app, client, staff_auth_headers, customer_auth_headers, admin_auth_headers, gift_template):
    path = f"/api/admin/loyalty/customers/{app.config['TEST_CUSTOMER_ID']}/voucher-gifts"
    assert client.post(path, json={}).status_code == 401
    assert gift(client, app, staff_auth_headers, gift_template).status_code == 403
    assert gift(client, app, customer_auth_headers, gift_template).status_code == 403
    assert client.post(path, headers=admin_auth_headers, json={'reward_id':gift_template,'reason':'a'}).status_code == 400
    for extra in ({'issued_by_staff':999}, {'reward_value':1}, {'expires_at':'2099-01-01'}, {'makh':999}):
        assert gift(client, app, admin_auth_headers, gift_template, **extra).status_code == 400
    for state in ('pending', 'blocked'):
        with app.app_context():
            db.session.get(KhachHang, app.config['TEST_CUSTOMER_ID']).trangthai = state; db.session.commit()
        assert gift(client, app, admin_auth_headers, gift_template).status_code == 400
    assert client.post('/api/admin/loyalty/customers/999/voucher-gifts', headers={**admin_auth_headers,'Idempotency-Key':'missing'}, json={'reward_id':gift_template,'reason':'a'}).status_code == 404
    with app.app_context():
        db.session.get(NhanVien, app.config['TEST_ADMIN_ID']).trangthai=False;db.session.commit()
    assert gift(client, app, admin_auth_headers, gift_template).status_code == 403


def test_gift_payment_release_finalize_and_cancel(app, client, admin_auth_headers, customer_auth_headers, gift_template, create_invoice):
    row = gift(client, app, admin_auth_headers, gift_template).json['redemption']; rid=row['id']
    invoice = create_invoice(amount=500000)
    path=f'/api/admin/invoices/{invoice}/reward'
    # Existing endpoint uses redemption_id; all gift terms use the same validation.
    response = client.post(path, headers=admin_auth_headers, json={'redemption_id':rid})
    assert response.status_code == 200, response.json
    assert client.post(f'/api/admin/loyalty/voucher-gifts/{rid}/cancel', headers=admin_auth_headers, json={'reason':'Nhầm'}).status_code == 409
    assert client.delete(path, headers=admin_auth_headers).status_code == 200
    assert client.post(f'/api/admin/loyalty/voucher-gifts/{rid}/cancel', headers=admin_auth_headers, json={'reason':'Tặng nhầm'}).status_code == 200
    assert client.post(path, headers=admin_auth_headers, json={'redemption_id':rid}).status_code == 400
    second = gift(client, app, admin_auth_headers, gift_template, key='next').json['redemption']['id']
    assert client.post(path, headers=admin_auth_headers, json={'redemption_id':second}).status_code == 200
    with app.app_context():
        from app.models import HoaDon
        target=loyalty.lock_target('service_invoice', invoice)
        assert target.payable_amount == Decimal('450000')
        target.trangthai = 'Đã thanh toán'
        loyalty.finalize_payment(target)
        db.session.commit()
        assert db.session.get(LoyaltyRewardRedemption, second).status == 'used'
        assert db.session.get(LoyaltyReward, gift_template).stock == 3
    assert client.post(f'/api/admin/loyalty/voucher-gifts/{second}/cancel', headers=admin_auth_headers, json={'reason':'Nhầm'}).status_code == 409


def configure(app, template, **overrides):
    data = dict(enabled=True, reward_id=template, starts_at=(datetime.utcnow()-timedelta(minutes=1)).isoformat()+'Z', ends_at=None)
    data.update(overrides)
    with app.app_context():
        issuance.update_welcome_config(data, app.config['TEST_ADMIN_ID']);db.session.commit()


def new_pending(app, name='new', marked=True, before=False):
    with app.app_context():
        created=datetime.utcnow()-timedelta(days=1) if before else datetime.utcnow()
        user=KhachHang(hoten='Khách mới', taikhoan=name, matkhau='hash', trangthai='pending', ngaytao=created,
            otp_code='123456', otp_expire=datetime.utcnow()+timedelta(minutes=10))
        db.session.add(user);db.session.flush()
        if marked:db.session.add(CustomerOtpRegistration(makh=user.makh, registered_at=created))
        db.session.commit();return user.makh


def test_real_registration_marker_and_otp_welcome_once(app, client, admin_auth_headers, gift_template, monkeypatch):
    configure(app, gift_template)
    monkeypatch.setattr('app.routes.auth_bp.send_email', lambda *args, **kwargs: True)
    response=client.post('/api/auth/register', json=dict(taikhoan='new_register', matkhau='password123', hoten='Mới', email='new@example.test', sdt='0901111222'))
    assert response.status_code == 201, response.json
    with app.app_context():
        user=KhachHang.query.filter_by(taikhoan='new_register').one();uid=user.makh;otp=user.otp_code
        assert db.session.get(CustomerOtpRegistration,uid)
    assert client.post('/api/auth/verify-otp',json={'otp_code':'wrong'}).status_code == 404
    activated=client.post('/api/auth/verify-otp',json={'otp_code':otp})
    assert activated.status_code == 200 and activated.json['welcome_voucher']['issued']
    assert client.post('/api/auth/verify-otp',json={'otp_code':otp}).status_code == 404
    with app.app_context():
        row=LoyaltyRewardRedemption.query.filter_by(makh=uid).one()
        assert row.points_spent == 0 and row.welcome_once_key == f'welcome:{uid}'
        assert LoyaltyPointTransaction.query.count() == LoyaltyWallet.query.count() == 0
        # Even changing the program cannot bypass the lifetime key.
        other=loyalty.save_reward(dict(name='Other',reward_type='voucher_percent',points_cost=0,reward_value=0,percentage_value=10,allow_points_redemption=False,validity_days=10))
        config=db.session.get(WelcomeVoucherConfig,1);config.reward_id=other.id;db.session.flush()
        assert issuance.issue_welcome(db.session.get(KhachHang,uid)) == {'issued':False,'reason':'already_received'}
        db.session.commit()


@pytest.mark.parametrize('case,reason', [('disabled','disabled'),('future','outside_program'),('ended','outside_program'),('stock','out_of_stock'),('old','not_new_registration'),('internal','not_new_registration')])
def test_welcome_business_skips_do_not_block_activation(app, client, gift_template, case, reason):
    configure(app,gift_template)
    uid=new_pending(app, marked=case!='internal', before=case=='old')
    with app.app_context():
        config=db.session.get(WelcomeVoucherConfig,1);reward=db.session.get(LoyaltyReward,gift_template)
        if case=='disabled':config.enabled=False
        if case=='future':config.starts_at=datetime.utcnow()+timedelta(days=1)
        if case=='ended':config.ends_at=datetime.utcnow()-timedelta(seconds=1)
        if case=='stock':reward.stock=0
        db.session.commit()
    result=client.post('/api/auth/verify-otp',json={'otp_code':'123456'})
    assert result.status_code==200, result.json
    assert result.json['welcome_voucher']==dict(issued=False,reason=reason)
    with app.app_context():
        assert db.session.get(KhachHang,uid).trangthai=='active'
        assert LoyaltyRewardRedemption.query.count()==0


def test_welcome_db_error_rolls_back_activation_and_stock(app, client, gift_template, monkeypatch):
    configure(app,gift_template);uid=new_pending(app)
    original=loyalty.issue_reward
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise IntegrityError('simulated failure', {}, Exception('DB failure'))
    monkeypatch.setattr(loyalty,'issue_reward',fail)
    assert client.post('/api/auth/verify-otp',json={'otp_code':'123456'}).status_code==500
    with app.app_context():
        user=db.session.get(KhachHang,uid)
        assert user.trangthai=='pending' and user.otp_code=='123456'
        assert db.session.get(LoyaltyReward,gift_template).stock==5
        assert LoyaltyRewardRedemption.query.count()==0
    monkeypatch.setattr(loyalty,'issue_reward',original)
    assert client.post('/api/auth/verify-otp',json={'otp_code':'123456'}).json['welcome_voucher']['issued']


def test_config_validation_and_source_constraints(app, client, admin_auth_headers, gift_template):
    endpoint='/api/admin/loyalty/welcome-config'
    assert client.get(endpoint,headers=admin_auth_headers).json['config']['enabled'] is False
    for data in ({'enabled':True},{'enabled':'yes'},{'enabled':True,'reward_id':gift_template,'starts_at':'2026-10-23T10:00'},
                 {'enabled':False,'starts_at':'2026-10-23T10:00:00Z','ends_at':'2026-10-22T10:00:00Z'}):
        assert client.put(endpoint,headers=admin_auth_headers,json=data).status_code==400
    with app.app_context():
        row=LoyaltyRewardRedemption(makh=app.config['TEST_CUSTOMER_ID'],reward_id=gift_template,points_spent=0,
            reward_snapshot_json={},code='BAD',idempotency_key='bad',issuance_source='points_redemption')
        db.session.add(row)
        with pytest.raises(IntegrityError):db.session.flush()
        db.session.rollback()


def test_program_can_be_disabled_after_its_template_is_stopped(app, client, admin_auth_headers, gift_template):
    configure(app,gift_template)
    with app.app_context():
        db.session.get(LoyaltyReward,gift_template).active=False;db.session.commit()
    data=client.get('/api/admin/loyalty/welcome-config',headers=admin_auth_headers).json['config']
    data={k:data[k] for k in ('enabled','reward_id','starts_at','ends_at')};data['enabled']=False
    result=client.put('/api/admin/loyalty/welcome-config',headers=admin_auth_headers,json=data)
    assert result.status_code==200 and result.json['config']['enabled'] is False
    data['enabled']=True
    assert client.put('/api/admin/loyalty/welcome-config',headers=admin_auth_headers,json=data).status_code==200
    with app.app_context():
        assert db.session.get(LoyaltyReward,gift_template).active is False


def test_inactive_welcome_is_giftable_and_usable_but_not_redeemable(app, client, admin_auth_headers, customer_auth_headers, gift_template, create_invoice):
    with app.app_context():
        template=db.session.get(LoyaltyReward,gift_template)
        template.active=False;template.allow_points_redemption=True;template.points_cost=1
        template.allow_manual_gift=False;db.session.commit()
    configure(app,gift_template)
    with app.app_context():
        template=db.session.get(LoyaltyReward,gift_template)
        assert template.active is False and template.allow_points_redemption is True
        assert template.points_cost==1
    assert client.get('/api/loyalty/rewards',headers=customer_auth_headers).json['total']==0
    assert client.get('/api/admin/loyalty/gift-templates',headers=admin_auth_headers).json['total']==1
    assert client.post(f'/api/loyalty/rewards/{gift_template}/redeem',headers=customer_auth_headers,json={'idempotency_key':'hidden'}).status_code==400
    issued=gift(client,app,admin_auth_headers,gift_template)
    assert issued.status_code==201, issued.json
    invoice=create_invoice(amount=500000)
    rid=issued.json['redemption']['id']
    assert client.post(f'/api/admin/invoices/{invoice}/reward',headers=admin_auth_headers,json={'redemption_id':rid}).status_code==200
    with app.app_context():
        target=loyalty.lock_target('service_invoice',invoice)
        target.trangthai='Đã thanh toán';loyalty.finalize_payment(target);db.session.commit()
        assert db.session.get(LoyaltyRewardRedemption,rid).status=='used'
        assert db.session.get(LoyaltyReward,gift_template).active is False
    uid=new_pending(app,name='inactive-welcome-new')
    activated=client.post('/api/auth/verify-otp',json={'otp_code':'123456'})
    assert activated.status_code==200 and activated.json['welcome_voucher']['issued']
    with app.app_context():
        assert LoyaltyRewardRedemption.query.filter_by(makh=uid,issuance_source='welcome').count()==1


def test_editor_saves_new_customer_selection_atomically(app, client, admin_auth_headers, gift_template):
    path=f'/api/admin/loyalty/rewards/{gift_template}'
    result=client.put(path,headers=admin_auth_headers,json={'for_new_customers':True,'active':False})
    assert result.status_code==200, result.json
    with app.app_context():
        config=db.session.get(WelcomeVoucherConfig,1)
        assert config.enabled and config.reward_id==gift_template
        started=config.starts_at
        assert db.session.get(LoyaltyReward,gift_template).active is False
    # Editing benefits must not move the registration cutoff.
    assert client.put(path,headers=admin_auth_headers,json={'for_new_customers':True,'reward_value':60000}).status_code==200
    with app.app_context():
        assert db.session.get(WelcomeVoucherConfig,1).starts_at==started
    assert client.put(path,headers=admin_auth_headers,json={'for_new_customers':False}).status_code==200
    with app.app_context():
        config=db.session.get(WelcomeVoucherConfig,1)
        assert not config.enabled and config.reward_id is None
    bad=client.post('/api/admin/loyalty/rewards',headers=admin_auth_headers,json={
        'name':'Invalid welcome','reward_type':'voucher_amount','reward_value':50000,
        'points_cost':10,'active':False,'for_new_customers':True})
    assert bad.status_code==400
    with app.app_context():
        assert LoyaltyReward.query.filter_by(name='Invalid welcome').count()==0
        assert not db.session.get(WelcomeVoucherConfig,1).enabled
    good=client.post('/api/admin/loyalty/rewards',headers=admin_auth_headers,json={
        'name':'New welcome','reward_type':'voucher_percent','reward_value':0,'percentage_value':15,
        'points_cost':10,'validity_days':20,'active':False,'for_new_customers':True})
    assert good.status_code==201, good.json
    with app.app_context():
        assert db.session.get(WelcomeVoucherConfig,1).reward_id==good.json['reward']['id']
        assert not db.session.get(LoyaltyReward,good.json['reward']['id']).active



def test_missing_expiry_has_clear_validation_instead_of_silently_enabling(app, client, admin_auth_headers, gift_template):
    with app.app_context():
        db.session.get(LoyaltyReward,gift_template).validity_days=None;db.session.commit()
    result=client.put('/api/admin/loyalty/welcome-config',headers=admin_auth_headers,json={'enabled':True,'reward_id':gift_template})
    assert result.status_code==400 and 'Sửa mẫu' in result.json['message']
    assert client.get('/api/admin/loyalty/welcome-config',headers=admin_auth_headers).json['config']['enabled'] is False


def test_percentage_gift_terms_ownership_expiry_and_no_points(app, client, admin_auth_headers, customer_auth_headers, create_invoice):
    with app.app_context():
        template=loyalty.save_reward(dict(name='Giảm 20%',reward_type='voucher_percent',points_cost=0,reward_value=0,
            percentage_value=20,max_discount_amount=70000,minimum_spend=300000,apply_to='service_invoice',
            allow_points_redemption=False,allow_manual_gift=True,validity_days=10))
        other=KhachHang(hoten='Khác',taikhoan='other-gift',matkhau='hash',trangthai='active')
        db.session.add(other);db.session.commit();template_id,other_id=template.id,other.makh
        other_headers={'Authorization':'Bearer '+create_access_token(identity=f'customer:{other_id}')}
    result=gift(client,app,admin_auth_headers,template_id)
    assert result.status_code==201
    rid=result.json['redemption']['id']
    invoice=create_invoice(amount=500000)
    small=create_invoice(amount=200000)
    assert client.post(f'/api/admin/invoices/{small}/reward',headers=admin_auth_headers,json={'redemption_id':rid}).status_code==400
    assert client.get('/api/loyalty/my-rewards?makh='+str(app.config['TEST_CUSTOMER_ID']),headers=other_headers).json['total']==0
    with app.app_context():
        from app.models import HoaDon
        target=loyalty.lock_target('service_invoice',invoice)
        voucher=db.session.get(LoyaltyRewardRedemption,rid)
        loyalty.apply_reward(target,rid)
        assert target.reward_discount==Decimal('70000') and target.payable_amount==Decimal('430000')
        loyalty.release_reward(target)
        voucher.expires_at=datetime.utcnow()-timedelta(seconds=1);db.session.commit()
    assert client.post(f'/api/admin/invoices/{invoice}/reward',headers=admin_auth_headers,json={'redemption_id':rid}).status_code==400
    assert client.post(f'/api/admin/loyalty/voucher-gifts/{rid}/cancel',headers=admin_auth_headers,json={'reason':'expired'}).status_code==409


def test_welcome_invalid_expired_otp_and_no_marker_for_internal_customer(app, client, gift_template):
    configure(app,gift_template);uid=new_pending(app)
    with app.app_context():
        user=db.session.get(KhachHang,uid);user.otp_expire=datetime.utcnow()-timedelta(seconds=1);db.session.commit()
    assert client.post('/api/auth/verify-otp',json={'otp_code':'123456'}).status_code==400
    with app.app_context():
        assert db.session.get(KhachHang,uid).trangthai=='pending'
        assert LoyaltyRewardRedemption.query.count()==0

from decimal import Decimal
import pytest
from app.extensions import db
from app.models import (HoaDon, ThanhToan, LoyaltyPointTransaction, LoyaltyRedemptionReservation,
    LoyaltyRewardRedemption, TheLieuTrinh, GoiDichVuPurchase, DichVu, KhachHang)
from app.services import loyalty_service as loyalty, package_service
from test_loyalty_service import fund, invariant
from test_phase4_packages_care import package_data, activate


@pytest.fixture
def funded(app):
    with app.app_context():
        fund(app, 1000)
        db.session.commit()


def apply(client, headers, invoice, points=100):
    result = client.post(f'/api/admin/invoices/{invoice}/loyalty', headers=headers, json={'points':points})
    assert result.status_code == 200, result.json
    return result.json


def test_cash_payable_double_click_and_resume(app, client, admin_auth_headers, create_invoice, funded):
    invoice = create_invoice(500000)
    preview = client.post(f'/api/admin/invoices/{invoice}/loyalty/preview', headers=admin_auth_headers, json={'points':100})
    assert Decimal(preview.json['payable_amount']) == 400000
    state = apply(client, admin_auth_headers, invoice)
    assert Decimal(state['original_total']) == 500000
    assert Decimal(state['loyalty_discount']) == 100000
    assert state['points_earned'] == 0
    for _ in range(2):
        state = client.get(f'/api/admin/invoices/{invoice}/loyalty', headers=admin_auth_headers).json
        assert state['points_used'] == 100
        assert Decimal(state['payable_amount']) == 400000
    response = client.post(f'/api/admin/invoices/{invoice}/record-payment', headers=admin_auth_headers, json={'sotien':500000,'phuongthuc':'Tiền mặt'})
    assert response.status_code == 201, response.json
    assert client.post(f'/api/admin/invoices/{invoice}/record-payment', headers=admin_auth_headers, json={'sotien':400000,'phuongthuc':'Tiền mặt'}).status_code in (400,409)
    row = client.get(f'/api/admin/billing/transactions/service/{invoice}', headers=admin_auth_headers).json['transaction']
    assert Decimal(row['total_amount']) == 500000
    assert Decimal(row['payable_amount']) == 400000
    assert Decimal(row['change']) == 100000
    assert row['points_used'] == 100 and row['points_earned'] == 40
    assert Decimal(client.get('/api/admin/billing/transactions', headers=admin_auth_headers).json['stats']['revenue']) == 400000
    with app.app_context():
        assert ThanhToan.query.one().sotien == 400000
        assert LoyaltyRedemptionReservation.query.one().status == 'consumed'
        invariant(app)
    assert client.delete(f'/api/admin/invoices/{invoice}/loyalty', headers=admin_auth_headers).status_code == 400


def test_qr_no_earn_sepay_exactly_once_and_outbound(app,client,admin_auth_headers,create_invoice,funded):
    app.config.update(VIETQR_BANK_ID='970407', VIETQR_ACCOUNT_NO='1234',VIETQR_ACCOUNT_NAME='BIN SPA')
    invoice=create_invoice(500000)
    apply(client,admin_auth_headers,invoice)
    qr=client.post(f'/api/admin/invoices/{invoice}/generate-qr',headers=admin_auth_headers,json={})
    assert qr.status_code==200 and qr.json['amount']==400000
    assert 'amount=400000' in qr.json['qrCodeUrl']
    with app.app_context():
        assert LoyaltyPointTransaction.query.filter_by(type='earn').count()==0
    url='/api/payment/webhook/sepay';headers={'Authorization':'Apikey test-sepay-key'}
    bad=client.post(url,headers=headers,json=dict(id='outbound',content=f'HD{invoice}',transferAmount=400000,transferType='out'))
    assert bad.json['status']=='failed'
    payload=dict(id='bank-1',content=f'HD{invoice}',transferAmount=450000)
    assert client.post(url,headers=headers,json=payload).json['status']=='success'
    assert client.post(url,headers=headers,json=payload).json['status']=='duplicate'
    assert client.post(url,headers=headers,json=dict(payload,id='bank-2')).json['status']=='duplicate'
    with app.app_context():
        assert ThanhToan.query.one().sotien==400000
        assert LoyaltyPointTransaction.query.filter_by(idempotency_key=f'loyalty:earn:invoice:{invoice}').count()==1
        assert LoyaltyPointTransaction.query.filter_by(idempotency_key=f'loyalty:redeem:invoice:{invoice}').count()==1
        invariant(app)


def test_remove_and_full_points(app,client,admin_auth_headers,create_invoice,funded):
    invoice=create_invoice(500000)
    apply(client,admin_auth_headers,invoice)
    state=client.delete(f'/api/admin/invoices/{invoice}/loyalty',headers=admin_auth_headers).json
    assert state['wallet']['available_points']==1000 and Decimal(state['payable_amount'])==500000
    assert client.put('/api/admin/loyalty/config',headers=admin_auth_headers,json={'maximum_redeem_percent':100}).status_code==200
    apply(client,admin_auth_headers,invoice,500)
    assert client.post(f'/api/admin/invoices/{invoice}/generate-qr',headers=admin_auth_headers,json={}).status_code==400
    for _ in range(2):
        result=client.post(f'/api/admin/invoices/{invoice}/pay-points',headers=admin_auth_headers,json={})
        assert result.status_code==200,result.json
    with app.app_context():
        payment=ThanhToan.query.one()
        assert payment.sotien==0 and payment.phuongthuc=='Điểm thưởng'
        assert LoyaltyPointTransaction.query.filter_by(type='earn').count()==0
        invariant(app)


@pytest.fixture
def package_id(app):
    with app.app_context():
        s=DichVu(tendv='Loyalty package',gia=200000,active=True)
        db.session.add(s);db.session.flush()
        package=package_service.save_package(dict(tengoi='Gói 10 buổi',giagoi=1200000,validity_months=12,items=[dict(madv=s.madv,total_sessions=10)]))
        db.session.commit()
        return package.magoi


@pytest.mark.parametrize('method',['cash','vietqr'])
def test_package_payment_discount_activation_and_earn(app,client,customer_auth_headers,admin_auth_headers,funded,package_id,method):
    app.config.update(VIETQR_BANK_ID='970407',VIETQR_ACCOUNT_NO='1234',VIETQR_ACCOUNT_NAME='BIN SPA')
    result=client.post(f'/api/packages/{package_id}/purchase',headers=customer_auth_headers,json={'payment_method':method,'points':200})
    assert result.status_code==201,result.json
    p=result.json['purchase'];pid=p['id']
    assert Decimal(p['amount'])==1200000 and Decimal(p['payable_amount'])==1000000
    assert p['points_earned']==0
    with app.app_context():
        assert TheLieuTrinh.query.count()==0
    if method=='cash':
        for _ in range(2):
            r=client.post(f'/api/admin/packages/purchases/{pid}/confirm-payment',headers=admin_auth_headers,json={'cash_received':1100000})
            assert r.status_code==200,r.json
        assert Decimal(r.json['purchase']['change'])==100000
    else:
        assert p['payment']['amount']==1000000
        payload=dict(id='pkg-bank',content=f'PKG{pid}',transferAmount=1000000)
        headers={'Authorization':'Apikey test-sepay-key'}
        assert client.post('/api/payment/webhook/sepay',headers=headers,json=payload).json['status']=='success'
        assert client.post('/api/payment/webhook/sepay',headers=headers,json=payload).json['status']=='duplicate'
    with app.app_context():
        assert TheLieuTrinh.query.count()==1
        assert TheLieuTrinh.query.one().items[0].total_sessions==10
        assert LoyaltyPointTransaction.query.filter_by(type='earn').one().points_delta==100
        assert LoyaltyPointTransaction.query.filter_by(type='redeem').one().points_delta==-200
        assert package_service.paid_package_revenue()==1000000
        invariant(app)


def test_payment_failure_rolls_back_all_accounting(app,client,admin_auth_headers,create_invoice,funded,monkeypatch):
    invoice=create_invoice(500000)
    apply(client,admin_auth_headers,invoice)
    original=loyalty.award_points
    def fail(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('Injected settlement failure')
    monkeypatch.setattr(loyalty,'award_points',fail)
    response=client.post(f'/api/admin/invoices/{invoice}/record-payment',headers=admin_auth_headers,json={'sotien':400000,'phuongthuc':'Tiền mặt'})
    assert response.status_code==500
    with app.app_context():
        assert db.session.get(HoaDon,invoice).trangthai=='Chưa thanh toán'
        assert ThanhToan.query.count()==0
        assert LoyaltyRedemptionReservation.query.one().status=='reserved'
        assert LoyaltyPointTransaction.query.filter(LoyaltyPointTransaction.type.in_(['earn','redeem'])).count()==0
        invariant(app)


def test_customer_identity_and_admin_permissions(app,client,staff_auth_headers,customer_auth_headers,admin_auth_headers,create_invoice,funded):
    invoice=create_invoice(500000)
    for path in ('/api/admin/loyalty/config','/api/admin/loyalty/customers','/api/admin/loyalty/rewards','/api/admin/loyalty/redemptions'):
        assert client.get(path,headers=staff_auth_headers).status_code==403
        assert client.get(path,headers=customer_auth_headers).status_code==403
    assert client.post('/api/admin/loyalty/customers/1/adjust',headers=staff_auth_headers,json={'points_delta':50,'reason':'No','idempotency_key':'no'}).status_code==403
    assert client.get(f'/api/admin/invoices/{invoice}/loyalty',headers=customer_auth_headers).status_code==403
    assert client.get(f'/api/payment/invoices/{invoice}/loyalty',headers=customer_auth_headers).status_code==200
    with app.app_context():
        other=KhachHang(hoten='Other',taikhoan='other-loyalty',matkhau='hash')
        db.session.add(other);db.session.flush()
        foreign=HoaDon(makh=other.makh,manv=app.config['TEST_ADMIN_ID'],tongtien=500000)
        db.session.add(foreign);db.session.commit();foreign_id=foreign.mahd
    assert client.post(f'/api/payment/invoices/{foreign_id}/loyalty',headers=customer_auth_headers,json={'points':100}).status_code==400
    assert client.post(f'/api/payment/invoices/{invoice}/pay-online',headers=customer_auth_headers,json={'sotien':500000}).status_code==410
    assert client.get('/api/loyalty/me?makh=999',headers=customer_auth_headers).json['wallet']['available_points']==1000
    assert client.get('/api/loyalty/me/transactions?per_page=1',headers=customer_auth_headers).json['total']==1


def test_reward_api_double_submit_voucher_and_physical_fulfillment(app,client,admin_auth_headers,customer_auth_headers,funded,create_invoice):
    r=client.post('/api/admin/loyalty/rewards',headers=admin_auth_headers,json=dict(name='Voucher',reward_type='voucher_amount',points_cost=200,reward_value=50000,stock=1))
    assert r.status_code==201,r.json
    rid=r.json['reward']['id']
    for _ in range(2):
        result=client.post(f'/api/loyalty/rewards/{rid}/redeem',headers=customer_auth_headers,json={'idempotency_key':'click'})
        assert result.status_code==201,result.json
    voucher=result.json['redemption']['id'];invoice=create_invoice(500000)
    r=client.post(f'/api/admin/invoices/{invoice}/reward',headers=admin_auth_headers,json={'redemption_id':voucher})
    assert r.status_code==200,r.json
    apply(client,admin_auth_headers,invoice)
    assert client.post(f'/api/admin/invoices/{invoice}/record-payment',headers=admin_auth_headers,json={'sotien':350000,'phuongthuc':'Tiền mặt'}).status_code==201
    with app.app_context():
        assert LoyaltyRewardRedemption.query.one().status=='used'
        assert LoyaltyPointTransaction.query.filter_by(type='earn').one().points_delta==30
        invariant(app)
    gift=client.post('/api/admin/loyalty/rewards',headers=admin_auth_headers,json=dict(name='Quà',reward_type='physical_gift',points_cost=100,reward_value=0)).json['reward']['id']
    redemption=client.post(f'/api/loyalty/rewards/{gift}/redeem',headers=customer_auth_headers,json={'idempotency_key':'gift'}).json['redemption']['id']
    for _ in range(2):
        assert client.post(f'/api/admin/loyalty/redemptions/{redemption}/fulfill',headers=admin_auth_headers,json={}).json['redemption']['status']=='fulfilled'


def test_admin_and_customer_pages(client):
    admin=client.get('/admin/loyalty')
    assert admin.status_code==200 and 'loyalty.js' in admin.text
    assert 'data-tab="redemptions"' in admin.text
    profile=client.get('/profile')
    assert 'loyalty-section' in profile.text and 'js/customers/loyalty.js' in profile.text


def test_package_full_points_and_rule_toggles(app,client,admin_auth_headers,customer_auth_headers,funded,package_id):
    app.config.update(VIETQR_BANK_ID='970407',VIETQR_ACCOUNT_NO='1234',VIETQR_ACCOUNT_NAME='BIN SPA')
    assert client.put('/api/admin/loyalty/config',headers=admin_auth_headers,json=dict(redeem_on_package_purchase=False)).status_code==200
    denied=client.post(f'/api/packages/{package_id}/purchase',headers=customer_auth_headers,json={'payment_method':'cash','points':100})
    assert denied.status_code==400
    with app.app_context():
        assert GoiDichVuPurchase.query.count()==0
        loyalty.admin_adjust_points(app.config['TEST_CUSTOMER_ID'],500,'Top up',app.config['TEST_ADMIN_ID'],'top-up')
        db.session.commit()
    client.put('/api/admin/loyalty/config',headers=admin_auth_headers,json=dict(redeem_on_package_purchase=True,maximum_redeem_percent=100))
    result=client.post(f'/api/packages/{package_id}/purchase',headers=customer_auth_headers,json={'payment_method':'vietqr','points':1200})
    assert result.status_code==201,result.json
    p=result.json['purchase'];assert Decimal(p['payable_amount'])==0 and 'payment' not in p
    for _ in range(2):
        assert client.post(f"/api/packages/purchases/{p['id']}/pay-points",headers=customer_auth_headers,json={}).status_code==200
    with app.app_context():
        assert TheLieuTrinh.query.count()==1 and GoiDichVuPurchase.query.one().payment_method=='points'
        assert LoyaltyPointTransaction.query.filter_by(type='earn').count()==0
        invariant(app)


def test_adjust_idempotency_reason_validation_and_recorded_staff(app,client,admin_auth_headers,funded):
    url=f"/api/admin/loyalty/customers/{app.config['TEST_CUSTOMER_ID']}/adjust"
    body=dict(points_delta=50,reason='A'*2000,idempotency_key='repeat-adjust')
    first=client.post(url,headers=admin_auth_headers,json=body)
    assert first.status_code==200,first.json
    assert client.post(url,headers=admin_auth_headers,json=body).json['transaction']['id']==first.json['transaction']['id']
    assert first.json['transaction']['created_by_staff']==app.config['TEST_ADMIN_ID']
    assert client.post(url,headers=admin_auth_headers,json=dict(body,points_delta=-2000,idempotency_key='too-much')).status_code==400
    assert client.post(url,headers=admin_auth_headers,json=dict(body,reason='',idempotency_key='no-reason')).status_code==400


@pytest.mark.parametrize('coverage',['package','gift','gift_and_paid_service'])
def test_sessions_and_gifts_earn_only_on_new_money(app,client,customer_auth_headers,admin_auth_headers,package_data,coverage):
    treatment=activate(client,customer_auth_headers,admin_auth_headers,package_data)
    with app.app_context():
        before=loyalty.get_balance(package_data['customer'])
        assert before['lifetime_earned']==120
        item=TheLieuTrinh.query.one().items[0].id
    if coverage!='package':
        gift=client.post(f'/api/admin/packages/treatments/{treatment}/gifts',headers=admin_auth_headers,
            json=dict(madv=package_data['service'],quantity=1,gift_note='Loyalty regression'))
        assert gift.status_code==201,gift.json
        item=gift.json['item_id']
    services=[package_data['service']]
    if coverage=='gift_and_paid_service':
        services.append(package_data['other_service'])
    booking=client.post('/api/appointments/create',headers=customer_auth_headers,json=dict(
        madv_list=services,ngaygio=package_data['slot'].isoformat(),
        package_usages=[dict(mathe=treatment,madv=package_data['service'],the_item_id=item,quantity=1)]))
    assert booking.status_code==201,booking.json
    appointment=booking.json['appointment']['malh']
    completed=client.post(f'/api/admin/appointments/{appointment}/complete',headers=admin_auth_headers,json={})
    assert completed.status_code==200,completed.json
    with app.app_context():
        assert loyalty.get_balance(package_data['customer'])==before
        assert LoyaltyPointTransaction.query.filter_by(type='earn').count()==1
    if coverage=='gift_and_paid_service':
        created=client.post(f'/api/admin/appointments/{appointment}/create-invoice',headers=admin_auth_headers)
        assert created.status_code==201,created.json
        with app.app_context():
            invoice=HoaDon.query.filter_by(malh=appointment).one()
            assert invoice.tongtien==invoice.payable_amount==300000
            invoice_id=invoice.mahd
            assert loyalty.get_balance(package_data['customer'])==before
        paid=client.post(f'/api/admin/invoices/{invoice_id}/record-payment',headers=admin_auth_headers,
            json=dict(sotien=300000,phuongthuc='Tiền mặt'))
        assert paid.status_code==201,paid.json
        with app.app_context():
            assert loyalty.get_balance(package_data['customer'])['lifetime_earned']==150
            invariant(app)
    else:
        with app.app_context():
            assert all(invoice.tongtien==invoice.payable_amount==0 for invoice in HoaDon.query.all())

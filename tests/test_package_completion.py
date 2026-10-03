from io import BytesIO
from datetime import datetime, timedelta, time
from decimal import Decimal
import json
from urllib.parse import urlsplit, parse_qs

import pytest
from PIL import Image
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import (DichVu, NhanVien, GoiDichVu, GoiDichVuPurchase, TheLieuTrinh,
                        TheLieuTrinhItem, CaLam, nhanvien_calam, LieuTrinhUsage)
from app.services import package_service as ps, appointment_service as appointments


def image_file(color='green'):
    data=BytesIO();Image.new('RGB',(24,24),color).save(data,format='PNG');data.seek(0)
    return data


@pytest.fixture
def catalog(app,monkeypatch):
    monkeypatch.setattr(appointments,'send_appointment_confirmation_email_async',lambda *args:None)
    with app.app_context():
        app.config.update(VIETQR_BANK_ID='TESTBANK',VIETQR_ACCOUNT_NO='123456',VIETQR_ACCOUNT_NAME='TEST & SPA')
        service=DichVu(tendv='Test massage',gia=300000,thoiluong=45,active=True)
        db.session.add(service);db.session.flush()
        package=ps.save_package(dict(tengoi='Test package',giagoi=1200000,validity_months=8,items=[dict(madv=service.madv,total_sessions=5)]))
        staff=db.session.get(NhanVien,app.config['TEST_STAFF_ID'])
        receptionist=NhanVien(hoten='Reception test',taikhoan='package_reception',matkhau='test',macv=staff.macv,role='letan',trangthai=True)
        db.session.add(receptionist);db.session.flush()
        day=ps.local_now().date()+timedelta(days=3)
        shift=CaLam(ngay=day,giobatdau=time(8),gioketthuc=time(18));db.session.add(shift);db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=staff.manv,maca=shift.maca))
        db.session.commit()
        return dict(package=package.magoi,service=service.madv,customer=app.config['TEST_CUSTOMER_ID'],
                    receptionist=receptionist.manv,headers={'Authorization':'Bearer '+create_access_token(identity=f'staff:{receptionist.manv}')},
                    slot=datetime.combine(day,time(9)))


def sale(client,data,method='cash'):
    r=client.post('/api/admin/package-sales',headers=data['headers'],json={'makh':data['customer'],'magoi':data['package'],'payment_method':method,'amount':1,'status':'paid'})
    assert r.status_code==201,r.json
    assert r.json['purchase']['status']=='pending'
    assert Decimal(r.json['purchase']['amount'])==1200000
    return r.json['purchase']


def test_package_image_fallback_and_replace(app,client,catalog,admin_auth_headers):
    url=f"/api/admin/packages/{catalog['package']}/image"
    with app.app_context():
        p=db.session.get(GoiDichVu,catalog['package'])
        assert ps.serialize_package(p)['image_url']=='/static/images/default-package.svg'
        db.session.get(DichVu,catalog['service']).anhdichvu=b'service-image';db.session.commit()
        assert ps.serialize_package(p)['image_url'].startswith('data:image/jpeg;base64,')
    for color in ['green','blue']:
        r=client.put(url,headers=admin_auth_headers,data={'anhgoi':(image_file(color),'photo.png','image/png')})
        assert r.status_code==200,r.json
        with app.app_context():
            blob=db.session.get(GoiDichVu,catalog['package']).anhgoi
            assert Image.open(BytesIO(blob)).format=='JPEG'
    old=r.json['package']['image_url']
    body=dict(tengoi='Edited',giagoi=1200000,validity_months=8,items=[dict(madv=catalog['service'],total_sessions=5)])
    assert client.put(f"/api/admin/packages/{catalog['package']}",headers=admin_auth_headers,json=body).json['package']['image_url']==old
    assert client.get('/static/images/default-package.svg').status_code==200


def test_package_create_image_is_atomic(app,client,catalog,admin_auth_headers):
    body=dict(tengoi='Atomic image package',giagoi=100000,validity_months=None,items=[dict(madv=catalog['service'],total_sessions=1)])
    for data,expected in [(b'invalid',400),(image_file().getvalue(),201)]:
        response=client.post('/api/admin/packages',headers=admin_auth_headers,data={'data':json.dumps(body),'anhgoi':(BytesIO(data),'photo.png','image/png')})
        assert response.status_code==expected,response.json
        with app.app_context():
            assert GoiDichVu.query.filter_by(tengoi=body['tengoi']).count()==(1 if expected==201 else 0)
    with app.app_context():assert GoiDichVu.query.filter_by(tengoi=body['tengoi']).one().anhgoi


@pytest.mark.parametrize('payload,name,mime',[(b'<script>bad</script>','evil.png','image/png'),(b'bad','evil.svg','image/svg+xml'),(b'x'*(5*1024*1024+1),'big.png','image/png')], ids=['spoofed-content','invalid-mime','oversized'])
def test_invalid_package_upload_rejected(client,catalog,admin_auth_headers,payload,name,mime):
    r=client.put(f"/api/admin/packages/{catalog['package']}/image",headers=admin_auth_headers,data={'anhgoi':(BytesIO(payload),name,mime)})
    assert r.status_code in (400,413)


def test_service_image_create_edit_and_preserve(app,client,admin_auth_headers):
    r=client.post('/api/admin/services',headers=admin_auth_headers,data={'tendv':'Image service','gia':'100000','thoiluong':'30','anhdichvu':(image_file(),'photo.png','image/png')})
    assert r.status_code==201
    service_id=r.json['madv']
    with app.app_context():old=db.session.get(DichVu,service_id).anhdichvu
    assert client.put(f'/api/admin/services/{service_id}',headers=admin_auth_headers,data={'tendv':'Renamed'}).status_code==200
    with app.app_context():assert db.session.get(DichVu,service_id).anhdichvu==old
    assert client.put(f'/api/admin/services/{service_id}',headers=admin_auth_headers,data={'anhdichvu':(image_file('blue'),'new.png','image/png')}).status_code==200
    with app.app_context():assert db.session.get(DichVu,service_id).anhdichvu!=old


@pytest.mark.parametrize('months',[8,None])
def test_validity_snapshot_and_booking(app,client,catalog,customer_auth_headers,months):
    with app.app_context():
        package=db.session.get(GoiDichVu,catalog['package']);package.validity_months=months
        purchase=ps.create_purchase(package.magoi,catalog['customer'],'cash')
        _,record,_=ps.confirm_purchase(purchase.id,1200000,method='cash');db.session.commit()
        record_id=record.mathe
        assert record.expires_at==(ps.add_months(record.activated_at,8) if months else None)
        assert ps.serialize_treatment(record)['expires_at']==(record.expires_at.isoformat() if months else None)
    r=client.post('/api/appointments/create',headers=customer_auth_headers,json={'madv_list':[catalog['service']],'ngaygio':catalog['slot'].isoformat(),'package_usages':[{'mathe':record_id,'madv':catalog['service'],'quantity':1}]})
    assert r.status_code==201,r.json
    with app.app_context():assert LieuTrinhUsage.query.filter_by(mathe=record_id,state='reserved').count()==1


def test_zero_validity_rejected_and_negative_savings(app,catalog):
    with app.app_context():
        from app.services.appointment_service import AppointmentValidationError
        body=dict(tengoi='Premium',giagoi=2000000,validity_months=0,items=[dict(madv=catalog['service'],total_sessions=5)])
        with pytest.raises(AppointmentValidationError):ps.save_package(body)
        body['validity_months']=None
        p=ps.save_package(body);assert Decimal(ps.serialize_package(p)['savings'])==-500000


def test_counter_cash_short_change_audit_and_replay(app,client,catalog):
    p=sale(client,catalog)
    url=f"/api/admin/packages/purchases/{p['id']}/confirm-payment"
    assert client.post(url,headers=catalog['headers'],json={'cash_received':1000}).status_code==400
    for _ in range(2):
        r=client.post(url,headers=catalog['headers'],json={'cash_received':1500000,'amount':1})
        assert r.status_code==200,r.json
        assert Decimal(r.json['purchase']['change'])==300000
    with app.app_context():
        row=db.session.get(GoiDichVuPurchase,p['id']);assert row.created_by_staff==row.confirmed_by_staff==catalog['receptionist']
        assert TheLieuTrinh.query.filter_by(purchase_id=p['id']).count()==1
        assert ps.paid_package_revenue()==1200000
    assert client.get('/api/admin/package-sales',headers=catalog['headers']).json['purchases'][0]['receipt_code'].startswith('PG')
    assert client.get(f"/api/admin/package-sales/{p['id']}",headers=catalog['headers']).json['purchase']['items']


@pytest.mark.parametrize('actor',['customer','staff','inactive'])
def test_counter_authorization(app,client,catalog,customer_auth_headers,staff_auth_headers,actor):
    headers={'customer':customer_auth_headers,'staff':staff_auth_headers}.get(actor)
    if actor=='inactive':
        with app.app_context():db.session.get(NhanVien,catalog['receptionist']).trangthai=False;db.session.commit()
        headers=catalog['headers']
    assert client.post('/api/admin/package-sales',headers=headers,json={'makh':catalog['customer'],'magoi':catalog['package'],'payment_method':'cash'}).status_code==403
    assert client.post('/api/admin/packages/purchases/1/confirm-payment',headers=headers,json={'cash_received':1200000}).status_code==403


def test_counter_vietqr_status_webhook_idempotency(app,client,catalog,customer_auth_headers):
    p=sale(client,catalog,'vietqr');payment=p['payment']
    assert payment['amount']==1200000 and payment['description']==f"PKG{p['id']}"
    query=parse_qs(urlsplit(payment['qrCodeUrl']).query);assert query['accountName']==['TEST & SPA']
    assert client.post(f"/api/admin/packages/purchases/{p['id']}/confirm-payment",headers=catalog['headers'],json={'cash_received':1200000}).status_code==400
    body={'id':'package-counter-test','content':payment['description'],'transferAmount':1200000,'transferType':'in'}
    for _ in range(3):assert client.post('/api/payment/webhook/sepay',json=body,headers={'Authorization':'Apikey test-sepay-key'}).status_code==200
    for url,headers in [(f"/api/admin/package-sales/{p['id']}/status",catalog['headers']),(f"/api/packages/purchases/{p['id']}/status",customer_auth_headers)]:
        r=client.get(url,headers=headers);assert r.status_code==200 and r.json['purchase']['status']=='paid'
    with app.app_context():
        record=TheLieuTrinh.query.filter_by(purchase_id=p['id']).one();assert TheLieuTrinhItem.query.filter_by(mathe=record.mathe).count()==1


def test_payment_capability_disables_missing_config(app,client,catalog,customer_auth_headers):
    app.config['VIETQR_ACCOUNT_NO']=None
    assert client.get('/api/packages/payment-options').json['vietqr_available'] is False
    r=client.post(f"/api/packages/{catalog['package']}/purchase",headers=customer_auth_headers,json={'payment_method':'vietqr'})
    assert r.status_code==503
    with app.app_context():assert GoiDichVuPurchase.query.count()==0

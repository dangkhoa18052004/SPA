"""Feature and authorization checks with isolated SQLite; no customer mail."""
from datetime import timedelta
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, text, inspect

from app.extensions import db
from app.models import (TheLieuTrinh, TheLieuTrinhItem, LieuTrinhUsage,
    NhanVien, KhachHang, LichHen, ChiTietLichHen, DanhGia, ReviewReply,
    DanhGiaDichVu, HoaDon, DichVu, CaLam, nhanvien_calam)
from app.services import package_service as ps
from test_phase4_packages_care import package_data, activate


@pytest.fixture
def treatment(client, customer_auth_headers, admin_auth_headers, package_data):
    return activate(client, customer_auth_headers, admin_auth_headers, package_data)


def gift(client, headers, treatment, service, **extra):
    return client.post(f'/api/admin/packages/treatments/{treatment}/gifts',
        headers=headers, json=dict(madv=service, quantity=2, gift_note='Chăm sóc bổ sung', **extra))


def book(client, headers, data, treatment, item, slot=None, mixed=False):
    return client.post('/api/appointments/create', headers=headers, json=dict(
        madv_list=[data['service'], data['other_service']] if mixed else [data['service']],
        ngaygio=(slot or data['slot']).isoformat(),
        package_usages=[dict(mathe=treatment, madv=data['service'], the_item_id=item, quantity=1)]))


@pytest.mark.parametrize('mode', ['unlimited', 'days', 'date'])
def test_gift_data_audit_independent_expiry(app, client, staff_auth_headers, customer_auth_headers,
                                          package_data, treatment, mode):
    extra = {'validity_days': 30} if mode == 'days' else {'expires_at': (ps.local_now().date()+timedelta(days=30)).isoformat()} if mode == 'date' else {}
    r = gift(client, staff_auth_headers, treatment, package_data['service'], **extra)
    assert r.status_code == 201, r.json
    details = client.get(f'/api/packages/my-treatments/{treatment}', headers=customer_auth_headers).json['treatment']
    assert len(details['items']) == 2
    item = next(i for i in details['items'] if i['id'] == r.json['item_id'])
    assert item['source_type'] == 'gift' and item['available_sessions'] == 2
    assert item['gifted_by_staff'] == app.config['TEST_STAFF_ID']
    assert item['gift_note'] == 'Chăm sóc bổ sung' and item['created_at']
    assert item['usable'] and float(item['unit_value_snapshot']) == 0
    assert (item['effective_expires_at'] is None) == (mode == 'unlimited')
    booked=book(client,customer_auth_headers,package_data,treatment,item['id'])
    assert booked.status_code==201,booked.json


@pytest.mark.parametrize('extra', [dict(quantity=0), dict(quantity=1.5), dict(quantity=True),
    dict(validity_days=0), dict(expires_at='invalid'), dict(expires_at='2000-01-01'), dict(expires_at=0), dict(expires_at=''),
    dict(makh=999), dict(gift_note='x'*2001)])
def test_invalid_gift_rolls_back(app, client, staff_auth_headers, package_data, treatment, extra):
    body=dict(madv=package_data['service'],quantity=2);body.update(extra)
    r=client.post(f'/api/admin/packages/treatments/{treatment}/gifts',headers=staff_auth_headers,json=body)
    assert r.status_code == 400, r.json
    with app.app_context(): assert TheLieuTrinhItem.query.count()==1


def test_gift_role_service_and_customer_checks(app, client, staff_auth_headers, customer_auth_headers,
                                            package_data, treatment):
    assert gift(client,customer_auth_headers,treatment,package_data['service']).status_code==403
    with app.app_context():
        staff=db.session.get(NhanVien,app.config['TEST_STAFF_ID']);staff.role='letan';db.session.commit()
    assert gift(client,staff_auth_headers,treatment,package_data['service']).status_code==403
    with app.app_context():
        staff=db.session.get(NhanVien,app.config['TEST_STAFF_ID']);staff.role='staff'
        db.session.get(DichVu,package_data['service']).active=False;db.session.commit()
    assert gift(client,staff_auth_headers,treatment,package_data['service']).status_code==400
    with app.app_context():
        db.session.get(DichVu,package_data['service']).active=True
        db.session.get(NhanVien,app.config['TEST_STAFF_ID']).trangthai=False;db.session.commit()
    assert gift(client,staff_auth_headers,treatment,package_data['service']).status_code==403


@pytest.mark.parametrize('action', ['cancel', 'complete'])
def test_exact_gift_ledger_and_free_invoice(app, client, customer_auth_headers, admin_auth_headers,
                                         package_data, treatment, action):
    item=gift(client,admin_auth_headers,treatment,package_data['service']).json['item_id']
    active=client.get('/api/admin/packages/treatments?status=active',headers=admin_auth_headers).json['treatments']
    assert any(t['mathe']==treatment for t in active)
    assert client.get('/api/admin/packages/treatments?status=expired',headers=admin_auth_headers).json['treatments']==[]
    r=book(client,customer_auth_headers,package_data,treatment,item)
    assert r.status_code==201,r.json
    malh=r.json['appointment']['malh']
    with app.app_context():
        usage=LieuTrinhUsage.query.one();assert usage.the_item_id==item and usage.state=='reserved'
        assert ps.item_counts(db.session.get(TheLieuTrinhItem,item))['reserved']==1
    r=client.post(f'/api/admin/appointments/{malh}/{action}',headers=admin_auth_headers,json={})
    assert r.status_code==200,r.json
    with app.app_context():
        usage=LieuTrinhUsage.query.one();assert usage.state==('released' if action=='cancel' else 'consumed')
        assert ps.item_counts(usage.item)['available_sessions']==(2 if action=='cancel' else 1)
        original=TheLieuTrinhItem.query.filter_by(source_type='package').one()
        assert ps.item_counts(original)['available_sessions']==5
        assert all(h.tongtien==0 for h in HoaDon.query.all())
    if action=='complete':
        assert client.post(f'/api/admin/appointments/{malh}/create-invoice',headers=admin_auth_headers).status_code==400
        r=client.post('/api/reviews',headers=customer_auth_headers,json=dict(malh=malh,rating=5,service_ids=[package_data['service']]))
        assert r.status_code==201,r.json


def test_gift_after_parent_expiry_mixed_billing_and_exhaustion(app, client, customer_auth_headers,
    admin_auth_headers, package_data, treatment):
    with app.app_context():
        record=db.session.get(TheLieuTrinh,treatment);record.expires_at=ps.local_now()-timedelta(days=1)
        record.status='expired';db.session.commit()
    item=gift(client,admin_auth_headers,treatment,package_data['service']).json['item_id']
    active=client.get('/api/admin/packages/treatments?status=active',headers=admin_auth_headers).json['treatments']
    assert any(t['mathe']==treatment for t in active)
    assert client.get('/api/admin/packages/treatments?status=expired',headers=admin_auth_headers).json['treatments']==[]
    for n in range(2):
        r=book(client,customer_auth_headers,package_data,treatment,item,package_data['slot']+timedelta(hours=n*3),mixed=True)
        assert r.status_code==201,r.json
        malh=r.json['appointment']['malh']
        r=client.post(f'/api/admin/appointments/{malh}/complete',headers=admin_auth_headers,json={})
        assert r.status_code==200,r.json
        invoice=client.post(f'/api/admin/appointments/{malh}/create-invoice',headers=admin_auth_headers)
        assert invoice.status_code==201,invoice.json
    with app.app_context():
        assert ps.item_counts(db.session.get(TheLieuTrinhItem,item))==dict(consumed=2,reserved=0,available_sessions=0)
        assert HoaDon.query.count()==2 and all(h.tongtien==300000 for h in HoaDon.query.all())
        assert ps.paid_package_revenue()==1200000
    assert book(client,customer_auth_headers,package_data,treatment,item,package_data['slot']+timedelta(hours=6)).status_code==400


def test_gift_expiry_boundary_and_reschedule(app, client, customer_auth_headers, admin_auth_headers,
                                            package_data, treatment):
    item=gift(client,admin_auth_headers,treatment,package_data['service'],expires_at=package_data['slot'].date().isoformat()).json['item_id']
    r=book(client,customer_auth_headers,package_data,treatment,item);assert r.status_code==201,r.json
    with app.app_context():
        record=db.session.get(TheLieuTrinh,treatment);it=db.session.get(TheLieuTrinhItem,item)
        assert ps.is_treatment_item_usable(it,record,package_data['slot'].replace(hour=23,minute=59))
        assert not ps.is_treatment_item_usable(it,record,package_data['slot']+timedelta(days=1))
        from app.services.appointment_service import AppointmentValidationError
        with pytest.raises(AppointmentValidationError):ps.validate_reschedule(db.session.get(LichHen,r.json['appointment']['malh']),package_data['slot']+timedelta(days=1))
        from datetime import time
        shift=CaLam(ngay=package_data['slot'].date()+timedelta(days=1),giobatdau=time(8),gioketthuc=time(20))
        db.session.add(shift);db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'],maca=shift.maca));db.session.commit()
    assert book(client,customer_auth_headers,package_data,treatment,item,package_data['slot']+timedelta(days=1)).status_code==400


def test_exact_item_mismatch_and_legacy_package_preference(app, client, customer_auth_headers,
    admin_auth_headers, package_data, treatment):
    other=gift(client,admin_auth_headers,treatment,package_data['other_service']).json['item_id']
    assert book(client,customer_auth_headers,package_data,treatment,other).status_code==400
    gifted=gift(client,admin_auth_headers,treatment,package_data['service']).json['item_id']
    r=client.post('/api/appointments/create',headers=customer_auth_headers,json=dict(madv_list=[package_data['service']],ngaygio=package_data['slot'].isoformat(),
        package_usages=[dict(mathe=treatment,madv=package_data['service'],quantity=1)]))
    assert r.status_code==201,r.json
    with app.app_context(): assert LieuTrinhUsage.query.one().the_item_id!=gifted


@pytest.fixture
def review_data(app, package_data):
    with app.app_context():
        other=KhachHang(hoten='Khách khác',taikhoan='other_review',matkhau='test',trangthai='active')
        db.session.add(other);db.session.flush()
        rows=[]
        for staff,status in [(app.config['TEST_STAFF_ID'],'completed'),(app.config['TEST_STAFF2_ID'],'completed'),(app.config['TEST_STAFF_ID'],'confirmed')]:
            apt=LichHen(makh=app.config['TEST_CUSTOMER_ID'],manv=staff,ngaygio=ps.local_now()-timedelta(days=2),trangthai=status)
            db.session.add(apt);db.session.flush()
            apt.chitiet=[ChiTietLichHen(madv=package_data['service']),ChiTietLichHen(madv=package_data['other_service'])]
            rows.append(apt.malh)
        db.session.commit()
        return dict(appointments=rows, other_headers={'Authorization':'Bearer '+create_access_token(identity=f'customer:{other.makh}')})


def review(client, headers, data, services, index=0, rating=5):
    return client.post('/api/reviews',headers=headers,json=dict(malh=data['appointments'][index],rating=rating,comment='Trải nghiệm <script>safe</script>',service_ids=services))


def test_review_verification_service_association_and_duplicate(app, client, customer_auth_headers, package_data, review_data):
    assert review(client,customer_auth_headers,review_data,[package_data['service']],index=2).status_code==400
    assert review(client,review_data['other_headers'],review_data,[package_data['service']]).status_code==403
    assert review(client,customer_auth_headers,review_data,[9999]).status_code==403
    assert review(client,customer_auth_headers,review_data,[]).status_code==400
    r=review(client,customer_auth_headers,review_data,[package_data['service']]);assert r.status_code==201,r.json
    assert r.json['review']['verified']
    assert review(client,customer_auth_headers,review_data,[package_data['service']]).status_code==409
    public=client.get(f"/api/services/{package_data['service']}/reviews");assert public.status_code==200,public.json
    assert public.json['total']==1 and public.json['reviews'][0]['verified']
    assert client.get(f"/api/services/{package_data['other_service']}/reviews").json['total']==0
    serialized=str(public.json)
    assert 'customer@example.com' not in serialized and '0900000002' not in serialized
    assert all(k not in public.json['reviews'][0] for k in ('makh','malh','manv','email','phone'))


@pytest.mark.parametrize('rating', [0,6,True,1.5,'NaN'])
def test_review_rating_validation(client, customer_auth_headers, package_data, review_data, rating):
    assert review(client,customer_auth_headers,review_data,[package_data['service']],rating=rating).status_code==400


def test_review_crud_stats_privacy_reply_and_context(app, client, customer_auth_headers,
    admin_auth_headers, staff_auth_headers, package_data, review_data):
    service=package_data['service']
    first=review(client,customer_auth_headers,review_data,[service]).json['review'];rid=first['madg']
    second=review(client,customer_auth_headers,review_data,[service],index=1,rating=3)
    assert second.status_code==201
    public_url=f'/api/services/{service}/reviews'
    assert client.get(public_url).json['stats']['average_rating']==4
    assert client.put(f'/api/reviews/{rid}',headers=review_data['other_headers'],json=dict(rating=1)).status_code==403
    assert client.delete(f'/api/reviews/{rid}',headers=review_data['other_headers']).status_code==403
    for field in ('malh','makh','manv','service_ids'):
        assert client.put(f'/api/reviews/{rid}',headers=customer_auth_headers,json={field:99}).status_code==400
    changed=client.put(f'/api/reviews/{rid}',headers=customer_auth_headers,json=dict(rating=1,comment='Đã cập nhật'))
    assert changed.status_code==200 and changed.json['review']['updated_at']
    assert client.get(public_url).json['stats']['average_rating']==2
    assert client.get('/api/reviews/manage',headers=admin_auth_headers).json['total']==2
    assert client.get('/api/reviews/manage',headers=staff_auth_headers).json['total']==1
    assert client.get('/api/reviews/manage?staff=2',headers=staff_auth_headers).json['total']==0
    reply_url=f'/api/reviews/{rid}/reply'
    assert client.post(reply_url,headers=customer_auth_headers,json=dict(content='fake')).status_code==403
    assert client.post(reply_url,headers=staff_auth_headers,json=dict(content=' ')).status_code==400
    assert client.post(reply_url,headers=staff_auth_headers,json=dict(content='Cảm ơn quý khách')).status_code==200
    assert client.put(reply_url,headers=admin_auth_headers,json=dict(content='Spa đã tiếp nhận')).status_code==200
    context=client.get(f"/api/reviews/appointments/{first['malh']}/context",headers=customer_auth_headers).json
    assert context['review']['madg']==rid
    assert any(r['reply'] and r['reply']['content']=='Spa đã tiếp nhận' for r in client.get(public_url).json['reviews'])
    assert client.get('/api/reviews/manage?replied=yes',headers=admin_auth_headers).json['total']==1
    assert client.get('/api/reviews/manage?rating=1&search=Test',headers=admin_auth_headers).json['total']==1
    other_reply=f"/api/reviews/{second.json['review']['madg']}/reply"
    assert client.post(other_reply,headers=staff_auth_headers,json=dict(content='Wrong staff')).status_code==403
    assert client.delete(other_reply,headers=staff_auth_headers).status_code==403
    assert client.delete(f'/api/reviews/{rid}',headers=customer_auth_headers).status_code==200
    public=client.get(public_url).json
    assert public['total']==1 and public['stats']['average_rating']==3
    assert all(r['madg']!=rid for r in public['reviews'])
    with app.app_context():
        assert ReviewReply.query.count()==0
        assert DanhGiaDichVu.query.filter_by(madg=rid).count()==0


def test_public_pagination_and_active_customer(app, client, customer_auth_headers, package_data, review_data):
    for n in range(2): assert review(client,customer_auth_headers,review_data,[package_data['service']],index=n).status_code==201
    r=client.get(f"/api/services/{package_data['service']}/reviews?per_page=1&page=2")
    assert r.status_code==200 and len(r.json['reviews'])==1 and r.json['total']==2
    assert 'no-store' in r.headers['Cache-Control']
    with app.app_context():
        db.session.get(KhachHang,app.config['TEST_CUSTOMER_ID']).trangthai='inactive';db.session.commit()
    assert client.get('/api/reviews/my',headers=customer_auth_headers).status_code==403


def test_additive_migrations_preserve_legacy_ids_reviews_and_usage():
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        ddl=["CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)","CREATE TABLE dichvu (madv INTEGER PRIMARY KEY)",
            "CREATE TABLE thelieutrinhitem (id INTEGER PRIMARY KEY, mathe INTEGER NOT NULL, madv INTEGER NOT NULL, total_sessions INTEGER NOT NULL, unit_value_snapshot NUMERIC, CONSTRAINT uq_treatment_service UNIQUE(mathe,madv))",
            "CREATE TABLE lieutrinhusage (id INTEGER PRIMARY KEY, the_item_id INTEGER REFERENCES thelieutrinhitem(id), state TEXT)",
            "CREATE TABLE danhgia (madg INTEGER PRIMARY KEY, malh INTEGER NOT NULL UNIQUE, comment TEXT)",
            "CREATE TABLE chitietlichhen (malh INTEGER, madv INTEGER)",
            "INSERT INTO nhanvien VALUES(1)","INSERT INTO dichvu VALUES(8)",
            "INSERT INTO thelieutrinhitem VALUES(42,12,8,5,240000)","INSERT INTO lieutrinhusage VALUES(9,42,'consumed')",
            "INSERT INTO danhgia VALUES(21,64,'Legacy review')","INSERT INTO chitietlichhen VALUES(64,8)"]
        for sql in ddl: connection.execute(text(sql))
        context=MigrationContext.configure(connection)
        for revision in ('0007_treatment_gifts','0008_review_services_reply'):
            path=Path('migrations/versions')/f'20261003_{revision}.py'
            spec=importlib.util.spec_from_file_location(revision,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with Operations.context(context): module.upgrade()
        row=connection.execute(text('SELECT id,total_sessions,unit_value_snapshot,source_type FROM thelieutrinhitem')).one()
        assert tuple(row)==(42,5,240000,'package')
        assert connection.execute(text('SELECT the_item_id,state FROM lieutrinhusage')).one()==(42,'consumed')
        assert connection.execute(text('SELECT madg,comment FROM danhgia')).one()==(21,'Legacy review')
        assert connection.execute(text('SELECT madg,madv FROM danhgiadichvu')).one()==(21,8)
        connection.execute(text("INSERT INTO thelieutrinhitem(id,mathe,madv,total_sessions,unit_value_snapshot,source_type) VALUES(43,12,8,2,0,'gift')"))
        assert connection.execute(text('SELECT count(*) FROM thelieutrinhitem')).scalar()==2
        assert not any(u['name']=='uq_treatment_service' for u in inspect(connection).get_unique_constraints('thelieutrinhitem'))


def test_booking_login_context_and_safe_redirect(client):
    url='/appointments/create?treatment=12&service=8&item=42'
    html=client.get(url).get_data(as_text=True)
    assert 'redirect=' in html and 'treatment%3D12' in html and 'item%3D42' in html
    for path in ('/services/8','/profile','/admin/reviews'):
        assert client.get(path).status_code in (200,302,404)

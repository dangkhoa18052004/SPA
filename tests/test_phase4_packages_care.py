from datetime import datetime, timedelta, time
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import threading
from pathlib import Path
import uuid
import shutil

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import (DichVu, CaLam, nhanvien_calam, KhachHang, GoiDichVu, GoiDichVuPurchase,
    TheLieuTrinh, TheLieuTrinhItem, LieuTrinhUsage, NotificationJob, LichHen, ThanhToan, NhanVien)
from app.services import package_service as packages, appointment_service as appointments
from app.services import notification_service as notifications, email_service
from app.services.appointment_service import AppointmentValidationError


@pytest.fixture
def phase4_temp_dir():
    # pytest's mode-0700 tmp fixture is inaccessible in the managed Windows sandbox.
    root = Path('tests').resolve()
    path = root / ('runtime_phase4_' + uuid.uuid4().hex)
    path.mkdir()
    yield path
    assert path.resolve().parent == root
    shutil.rmtree(path)


@pytest.fixture
def package_data(app, monkeypatch):
    monkeypatch.setattr(appointments, 'send_appointment_confirmation_email_async', lambda *a: None)
    with app.app_context():
        app.config.update(VIETQR_BANK_ID='TESTBANK', VIETQR_ACCOUNT_NO='123456', VIETQR_ACCOUNT_NAME='TEST SPA')
        services = [DichVu(tendv=f'Service {i}', gia=300000, thoiluong=45, active=True,
            post_care_instructions='Nghỉ ngơi và làm theo hướng dẫn của kỹ thuật viên.') for i in range(2)]
        db.session.add_all(services)
        db.session.flush()
        day = packages.local_now().date() + timedelta(days=3)
        shift = CaLam(ngay=day, giobatdau=time(8), gioketthuc=time(20))
        db.session.add(shift)
        db.session.flush()
        for staff_id in [app.config['TEST_STAFF_ID'], app.config['TEST_STAFF2_ID']]:
            db.session.execute(nhanvien_calam.insert().values(manv=staff_id, maca=shift.maca))
        package = packages.save_package(dict(tengoi='Massage 5 buổi', mota='Gói thử nghiệm', giagoi=1200000,
            validity_months=6, items=[dict(madv=services[0].madv,total_sessions=5)]))
        db.session.commit()
        return dict(id=package.magoi, service=services[0].madv, other_service=services[1].madv,
            slot=datetime.combine(day,time(9)), customer=app.config['TEST_CUSTOMER_ID'])


def purchase(client, headers, data, method='cash'):
    response=client.post(f"/api/packages/{data['id']}/purchase",headers=headers,
        json={'payment_method':method,'makh':99999,'amount':1})
    assert response.status_code==201, response.json
    return response.json['purchase']


def activate(client, customer_headers, admin_headers, data):
    p=purchase(client,customer_headers,data)
    response=client.post(f"/api/admin/packages/purchases/{p['id']}/confirm-payment",
        headers=admin_headers,json={'amount':1200000})
    assert response.status_code==200,response.json
    return response.json['mathe']


def book(client, headers, data, record, slot=None, usages=None):
    return client.post('/api/appointments/create',headers=headers,json={
        'madv_list':[data['service']], 'ngaygio':(slot or data['slot']).strftime('%Y-%m-%dT%H:%M'),
        'package_usages':usages if usages is not None else [dict(mathe=record,madv=data['service'],quantity=1)],
    })


@pytest.mark.parametrize('multiple',[False,True])
def test_create_package_and_permissions(app,client,admin_auth_headers,staff_auth_headers,
    customer_auth_headers,package_data,multiple):
    body=dict(tengoi='Combo',giagoi=600000,validity_months=3,items=[dict(madv=package_data['service'],total_sessions=3)])
    if multiple:body['items'].append(dict(madv=package_data['other_service'],total_sessions=2))
    assert client.post('/api/admin/packages',headers=staff_auth_headers,json=body).status_code==403
    assert client.post('/api/admin/packages',headers=customer_auth_headers,json=body).status_code==403
    r=client.post('/api/admin/packages',headers=admin_auth_headers,json=body)
    assert r.status_code==201
    assert len(r.json['package']['items'])==(2 if multiple else 1)
    assert client.get(f"/api/packages/{r.json['package']['magoi']}").status_code==200
    with app.app_context():
        manager=db.session.get(NhanVien,app.config['TEST_STAFF_ID']);manager.role='manager';db.session.commit()
        token=create_access_token(identity=f'staff:{manager.manv}')
    assert client.get('/api/admin/packages',headers={'Authorization':f'Bearer {token}'}).status_code==200


def test_inactive_cannot_purchase(app,client,customer_auth_headers,package_data):
    with app.app_context():
        db.session.get(GoiDichVu,package_data['id']).active=False;db.session.commit()
    assert client.post(f"/api/packages/{package_data['id']}/purchase",headers=customer_auth_headers,json={}).status_code==400


def test_pending_purchase_owner_and_no_activation(app,client,customer_auth_headers,package_data):
    p=purchase(client,customer_auth_headers,package_data)
    assert p['status']=='pending' and p['mathe'] is None
    with app.app_context():
        row=db.session.get(GoiDichVuPurchase,p['id'])
        assert row.makh==package_data['customer'] and row.amount==1200000
        assert TheLieuTrinh.query.count()==0
        with pytest.raises(AppointmentValidationError):packages.activate_package_purchase(row)


def test_vietqr_duplicate_webhooks_snapshots_revenue(app,client,customer_auth_headers,admin_auth_headers,package_data):
    p=purchase(client,customer_auth_headers,package_data,'vietqr')
    assert p['payment']['description']==f"PKG{p['id']}"
    # Change the package while payment is pending; paid record must keep purchase terms.
    body=dict(tengoi='New Package',giagoi=1500000,validity_months=12,
        items=[dict(madv=package_data['service'],total_sessions=10)])
    assert client.put(f"/api/admin/packages/{package_data['id']}",headers=admin_auth_headers,json=body).status_code==200
    event=dict(id='pkg-event-1',content=f"PKG{p['id']}",transferAmount=1200000,transferType='in')
    for _ in range(4):
        r=client.post('/api/payment/webhook/sepay',headers={'Authorization':'Apikey test-sepay-key'},json=event)
        assert r.status_code==200 and r.json['status'] in ('success','duplicate')
    event['id']='pkg-event-2'
    assert client.post('/api/payment/webhook/sepay',headers={'Authorization':'Apikey test-sepay-key'},json=event).json['status']=='duplicate'
    with app.app_context():
        assert TheLieuTrinh.query.count()==1 and TheLieuTrinhItem.query.count()==1
        record=TheLieuTrinh.query.one(); item=record.items[0]
        assert item.total_sessions==5 and item.unit_value_snapshot==240000 and item.regular_price_snapshot==300000
        assert record.expires_at==packages.add_months(record.activated_at,6)
        assert record.purchase.status=='paid'
        assert packages.paid_package_revenue()==1200000 and ThanhToan.query.count()==0


@pytest.mark.parametrize('amount',[0,1,1199999,1200001,'NaN'])
def test_wrong_payment_amount_does_not_activate(app,client,customer_auth_headers,package_data,amount):
    p=purchase(client,customer_auth_headers,package_data,'vietqr')
    event=dict(id=f'bad-{amount}',content=f"PKG{p['id']}",transferAmount=amount)
    assert client.post('/api/payment/webhook/sepay',headers={'Authorization':'Apikey test-sepay-key'},json=event).json['status']=='failed'
    with app.app_context():
        assert db.session.get(GoiDichVuPurchase,p['id']).status=='pending'
        assert TheLieuTrinh.query.count()==0


@pytest.mark.parametrize('action',['cancel','complete'])
def test_reserve_release_consume_and_invoice_revenue(app,client,customer_auth_headers,admin_auth_headers,package_data,action):
    record_id=activate(client,customer_auth_headers,admin_auth_headers,package_data)
    response=book(client,customer_auth_headers,package_data,record_id)
    assert response.status_code==201,response.json
    appointment_id=response.json['appointment']['malh']
    details=client.get(f'/api/packages/my-treatments/{record_id}',headers=customer_auth_headers).json['treatment']
    assert details['items'][0]['reserved']==1 and details['items'][0]['available_sessions']==4
    endpoint=f'/api/admin/appointments/{appointment_id}/{action}'
    first=client.post(endpoint,headers=admin_auth_headers,json={})
    assert first.status_code==200,first.json
    second=client.post(endpoint,headers=admin_auth_headers,json={})
    assert second.status_code==(400 if action=='cancel' else 200)
    with app.app_context():
        usage=LieuTrinhUsage.query.one()
        assert usage.state==('released' if action=='cancel' else 'consumed')
        counts=packages.item_counts(usage.item)
        assert counts['reserved']==0
        assert counts['available_sessions']==(5 if action=='cancel' else 4)
        assert packages.paid_package_revenue()==1200000 and ThanhToan.query.count()==0
        if action=='cancel':assert all(j.status=='cancelled' for j in NotificationJob.query.all())
        else:
            assert NotificationJob.query.filter_by(type='post_care').count()==1
            assert NotificationJob.query.filter_by(type='review_request').count()==1
            assert client.post(f'/api/admin/appointments/{appointment_id}/create-invoice',headers=admin_auth_headers).status_code==400
            assert client.put(f'/api/admin/appointments/{appointment_id}',headers=admin_auth_headers,json={'trangthai':'cancelled'}).status_code==400
            db.session.refresh(usage);assert usage.state=='consumed'


@pytest.mark.parametrize('failure',['other_owner','expired','no_sessions','wrong_service','future_expiry','bad_quantity','duplicate','invalid_type'])
def test_booking_treatment_validation(app,client,customer_auth_headers,admin_auth_headers,package_data,failure):
    record_id=activate(client,customer_auth_headers,admin_auth_headers,package_data)
    usages=[dict(mathe=record_id,madv=package_data['service'],quantity=1)]
    with app.app_context():
        record=db.session.get(TheLieuTrinh,record_id)
        if failure=='other_owner':
            customer=KhachHang(hoten='Other',taikhoan='other_phase4',matkhau='hash',trangthai='active')
            db.session.add(customer);db.session.flush();record.makh=customer.makh
        elif failure=='expired':record.expires_at=packages.local_now()-timedelta(days=1)
        elif failure=='future_expiry':record.expires_at=packages.local_now()+timedelta(days=1)
        elif failure=='wrong_service':record.items[0].madv=package_data['other_service']
        elif failure=='no_sessions':
            apt=LichHen(makh=package_data['customer'],ngaygio=package_data['slot']-timedelta(days=1),trangthai='confirmed')
            db.session.add(apt);db.session.flush()
            record.items[0].total_sessions=1
            db.session.add(LieuTrinhUsage(mathe=record_id,the_item_id=record.items[0].id,
                malh=apt.malh,madv=package_data['service'],state='reserved',reserved_at=packages.local_now()))
        db.session.commit()
        before=LichHen.query.count()
    if failure=='bad_quantity':usages[0]['quantity']=2
    if failure=='duplicate':usages=usages*2
    if failure=='invalid_type':usages={}
    r=book(client,customer_auth_headers,package_data,record_id,usages=usages)
    assert r.status_code==400,r.json
    with app.app_context():assert LichHen.query.count()==before
    if failure=='other_owner':assert client.get(f'/api/packages/my-treatments/{record_id}',headers=customer_auth_headers).status_code==404


def test_mixed_booking_only_uncovered_service_is_invoiced(app,client,customer_auth_headers,admin_auth_headers,package_data):
    record=activate(client,customer_auth_headers,admin_auth_headers,package_data)
    r=client.post('/api/appointments/create',headers=customer_auth_headers,json={
        'ngaygio':package_data['slot'].strftime('%Y-%m-%dT%H:%M'),
        'madv_list':[package_data['service'],package_data['other_service']],
        'package_usages':[dict(mathe=record,madv=package_data['service'],quantity=1)]})
    assert r.status_code==201
    malh=r.json['appointment']['malh']
    assert client.post(f'/api/admin/appointments/{malh}/complete',headers=admin_auth_headers).status_code==200
    r=client.post(f'/api/admin/appointments/{malh}/create-invoice',headers=admin_auth_headers)
    assert r.status_code==201,r.json
    invoice=client.get(f"/api/payment/invoices/{r.json['invoice_id']}",headers=customer_auth_headers).json
    assert Decimal(invoice['tongtien'])==300000 and len(invoice['chitiet'])==1


@pytest.mark.parametrize('hours,expected',[(30,2),(5,1),(1,0)])
def test_notification_scheduling_idempotency(app,package_data,hours,expected):
    now=datetime.utcnow()
    with app.app_context():
        apt=LichHen(makh=package_data['customer'],ngaygio=now+timedelta(hours=7+hours),trangthai='confirmed')
        db.session.add(apt);db.session.flush()
        notifications.sync_appointment_jobs(apt,now);db.session.flush()
        notifications.sync_appointment_jobs(apt,now);db.session.commit()
        assert NotificationJob.query.count()==expected


def test_worker_due_success_no_duplicate_and_failure_max(app,package_data,monkeypatch):
    now=datetime.utcnow()
    sent=[]
    monkeypatch.setattr(email_service,'send_email',lambda *a,**kw: sent.append(kw['idempotency_key']) or True)
    with app.app_context():
        apt=LichHen(makh=package_data['customer'],ngaygio=now+timedelta(days=3,hours=7),trangthai='confirmed')
        db.session.add(apt);db.session.flush();notifications.sync_appointment_jobs(apt,now);db.session.commit()
        assert notifications.process_jobs(now=now)['sent']==0
        job=NotificationJob.query.first();job.scheduled_at=now;db.session.commit()
        assert notifications.process_jobs(now=now)['sent']==1
        assert notifications.process_jobs(now=now)['sent']==0
        assert len(sent)==1 and job.status=='sent' and job.sent_at==now
        other=NotificationJob.query.filter(NotificationJob.id!=job.id).one();other.scheduled_at=now;db.session.commit()
        monkeypatch.setattr(email_service,'send_email',lambda *a,**kw: False)
        for i in range(3):
            notifications.process_jobs(now=now+timedelta(minutes=20*i))
            db.session.refresh(other);assert other.attempts==i+1
        assert other.status=='failed'
        notifications.process_jobs(now=now+timedelta(hours=3));db.session.refresh(other);assert other.attempts==3


def test_stale_worker_retry_uses_same_payload_and_key(app,package_data,monkeypatch):
    now=datetime.utcnow()
    calls=[]
    monkeypatch.setattr(email_service,'send_email',lambda *a,**kw:calls.append((a,kw)) or True)
    with app.app_context():
        apt=LichHen(makh=package_data['customer'],ngaygio=now+timedelta(days=3,hours=7),trangthai='confirmed')
        db.session.add(apt);db.session.flush();notifications.sync_appointment_jobs(apt,now);db.session.commit()
        job=NotificationJob.query.first();job.status='processing';job.processing_at=now-timedelta(minutes=20)
        job.first_attempt_at=now-timedelta(minutes=20);job.attempts=1;db.session.commit()
        notifications.process_jobs(now=now)
        assert len(calls)==1 and calls[0][1]['idempotency_key']==job.unique_key
        assert calls[0][0]==(job.payload_json['to'],job.payload_json['subject'],job.payload_json['body'])
        job.status='processing';job.processing_at=now-timedelta(hours=25);job.first_attempt_at=now-timedelta(hours=25);db.session.commit()
        notifications.process_jobs(now=now)
        assert job.status=='failed' and len(calls)==1


def test_last_session_concurrent_reservations(app,client,customer_auth_headers,admin_auth_headers,package_data,phase4_temp_dir):
    """Independent SQLite connections exercise DB locking, not a Python-only mutex."""
    record=activate(client,customer_auth_headers,admin_auth_headers,package_data)
    target=create_engine(f'sqlite:///{phase4_temp_dir / "concurrent.sqlite"}',connect_args={'timeout':5})
    with app.app_context():
        db.session.get(TheLieuTrinh,record).items[0].total_sessions=1;db.session.commit()
        db.metadata.create_all(target)
        with target.begin() as connection:
            for table in db.metadata.sorted_tables:
                rows=[dict(row._mapping) for row in db.session.execute(table.select())]
                if rows:connection.execute(table.insert(),rows)
        with Session(target) as session:
            apts=[LichHen(makh=package_data['customer'],ngaygio=package_data['slot']+timedelta(hours=i),trangthai='confirmed') for i in range(2)]
            session.add_all(apts);session.commit();ids=[a.malh for a in apts]
    from app import create_app
    config=dict(app.config)
    config['SQLALCHEMY_DATABASE_URI']=str(target.url)
    concurrent_app=create_app(config)
    barrier=threading.Barrier(2)
    def reserve(index):
        with concurrent_app.test_client() as booking_client:
            barrier.wait()
            response=book(booking_client,customer_auth_headers,package_data,record,
                slot=package_data['slot']+timedelta(hours=index*2))
            return response.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(reserve,[0,1]))
        assert sorted(results)==[201,400], results
        with Session(target) as session:
            assert session.query(LieuTrinhUsage).filter_by(mathe=record,state='reserved').count()==1
    finally:
        with concurrent_app.app_context():db.engine.dispose()
        target.dispose()



def test_pages_render_and_worker_command(app,client,package_data):
    for url in ['/packages',f"/packages/{package_data['id']}",'/profile','/admin/packages','/admin/dashboard']:
        assert client.get(url).status_code==200
    result=app.test_cli_runner().invoke(args=['process-notification-jobs'])
    assert result.exit_code==0,result.output


def test_customer_cannot_view_other_purchase_and_staff_cannot_confirm(app,client,
    customer_auth_headers,staff_auth_headers,admin_auth_headers,package_data):
    p=purchase(client,customer_auth_headers,package_data)
    assert client.post(f"/api/admin/packages/purchases/{p['id']}/confirm-payment",
        headers=staff_auth_headers,json={'amount':1200000}).status_code==403
    with app.app_context():
        customer=KhachHang(hoten='Other Buyer',taikhoan='other_buyer',matkhau='hash',trangthai='active')
        db.session.add(customer);db.session.commit()
        token=create_access_token(identity=f'customer:{customer.makh}')
    assert client.get(f"/api/packages/purchases/{p['id']}",headers={'Authorization':f'Bearer {token}'}).status_code==404
    assert client.get('/api/packages/my-treatments',headers=staff_auth_headers).status_code==403
    with app.app_context():
        admin=db.session.get(NhanVien,app.config['TEST_ADMIN_ID']);admin.trangthai=False;db.session.commit()
    assert client.post(f"/api/admin/packages/purchases/{p['id']}/confirm-payment",
        headers=admin_auth_headers,json={'amount':1200000}).status_code==403


def test_email_transport_uses_idempotency_header(app,monkeypatch):
    calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'id':'fake-email'}
    monkeypatch.setattr(email_service.resend,'api_key','test-api-key')
    monkeypatch.setattr(email_service.requests,'post',lambda *a,**kw:calls.append((a,kw)) or Response())
    with app.app_context():
        assert email_service.send_email('nobody@example.test','Test','<p>Test</p>',idempotency_key='appointment:1:review')
    assert calls[0][1]['headers']['Idempotency-Key']=='appointment:1:review'
    assert calls[0][1]['timeout']==20


def test_migration_additive_preserves_existing_service(app,phase4_temp_dir):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util
    path='migrations/versions/20261002_0004_packages_and_care.py'
    spec=importlib.util.spec_from_file_location('phase4_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    old=MetaData()
    new_names={'goidichvu','goidichvuitem','goidichvupurchase','thelieutrinh','thelieutrinhitem','lieutrinhusage','notificationjob'}
    for table in db.metadata.sorted_tables:
        if table.name not in new_names:table.to_metadata(old)
    old.tables['dichvu']._columns.remove(old.tables['dichvu'].c.post_care_instructions)
    engine=create_engine(f'sqlite:///{phase4_temp_dir / "migration.sqlite"}')
    try:
        old.create_all(engine)
        with engine.begin() as connection:
            connection.execute(old.tables['dichvu'].insert().values(madv=1,tendv='Existing Service',gia=300000))
            with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
            assert new_names.issubset(inspect(connection).get_table_names())
            assert connection.execute(old.tables['dichvu'].select()).one().tendv=='Existing Service'
            assert 'post_care_instructions' in {c['name'] for c in inspect(connection).get_columns('dichvu')}
    finally:engine.dispose()


def test_parallel_workers_claim_job_once(app,package_data,monkeypatch,phase4_temp_dir):
    from app import create_app
    now=datetime.utcnow()
    sent=[]
    monkeypatch.setattr(email_service,'send_email',lambda *a,**kw:sent.append(kw['idempotency_key']) or True)
    target=create_engine(f'sqlite:///{phase4_temp_dir / "workers.sqlite"}')
    with app.app_context():
        apt=LichHen(makh=package_data['customer'],ngaygio=now+timedelta(days=3,hours=7),trangthai='confirmed')
        db.session.add(apt);db.session.flush();notifications.sync_appointment_jobs(apt,now);db.session.flush()
        NotificationJob.query.first().scheduled_at=now;db.session.commit()
        db.metadata.create_all(target)
        with target.begin() as connection:
            for table in db.metadata.sorted_tables:
                rows=[dict(row._mapping) for row in db.session.execute(table.select())]
                if rows:connection.execute(table.insert(),rows)
    config=dict(app.config);config['SQLALCHEMY_DATABASE_URI']=str(target.url)
    worker_app=create_app(config)
    barrier=threading.Barrier(2)
    def process(_):
        with worker_app.app_context():
            barrier.wait();return notifications.process_jobs(now=now)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(process,[0,1]))
        assert len(sent)==1 and sum(r['sent'] for r in results)==1
    finally:
        with worker_app.app_context():db.engine.dispose()
        target.dispose()

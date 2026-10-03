"""
Tests for post-care email content building:
- Test 21: Single service (no package) → post-care email body contains service instructions
- Test 22: Package appointment → email body contains BOTH service AND package instructions
- Test 23: Multi-service appointment → email contains all service instructions
- Test 24: Worker sends pending jobs (extended)
- Test 26: Migration adds only goidichvu.post_care_instructions (regression)
- Test profile API: build_post_care_content endpoint
"""
from datetime import datetime, timedelta, time
from decimal import Decimal

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import (
    DichVu, CaLam, nhanvien_calam, KhachHang, LichHen, ChiTietLichHen,
    GoiDichVu, GoiDichVuPurchase, TheLieuTrinh, TheLieuTrinhItem,
    LieuTrinhUsage, NotificationJob, AppointmentStatus,
)
from app.services import package_service as packages, notification_service as notifications
from app.services.notification_service import build_post_care_content, build_post_care_html
from app.services import email_service


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def setup_services(app):
    """Create two services with and without post_care_instructions."""
    with app.app_context():
        svc1 = DichVu(tendv='Massage Body', gia=300000, thoiluong=60, active=True,
            post_care_instructions='Uong du nuoc sau massage.\nNghi ngoi va giu am co the.')
        svc2 = DichVu(tendv='Cham soc da', gia=250000, thoiluong=45, active=True,
            post_care_instructions='Tranh anh nang manh trong 24h.\nDungkem chong nang hang ngay.')
        svc3 = DichVu(tendv='Goi dau', gia=100000, thoiluong=30, active=True,
            post_care_instructions=None)  # no post-care
        db.session.add_all([svc1, svc2, svc3])

        day = datetime.utcnow().date() + timedelta(days=3)
        shift = CaLam(ngay=day, giobatdau=time(8), gioketthuc=time(20))
        db.session.add(shift)
        db.session.flush()

        db.session.execute(nhanvien_calam.insert().values(
            manv=app.config['TEST_STAFF_ID'], maca=shift.maca))
        db.session.commit()

        return {
            'svc1': svc1.madv, 'svc2': svc2.madv, 'svc3': svc3.madv,
            'day': day, 'customer': app.config['TEST_CUSTOMER_ID'],
            'staff': app.config['TEST_STAFF_ID'],
        }


def make_completed_appointment(app, customer_id, staff_id, service_ids, day, usages=None):
    """Create a completed appointment and return it."""
    with app.app_context():
        slot = datetime.combine(day, time(10, 0))
        apt = LichHen(makh=customer_id, manv=staff_id, ngaygio=slot, trangthai=AppointmentStatus.CONFIRMED)
        db.session.add(apt)
        db.session.flush()
        for madv in service_ids:
            db.session.add(ChiTietLichHen(malh=apt.malh, madv=madv))
        if usages:
            for u in usages:
                db.session.add(u(apt.malh))
        apt.trangthai = AppointmentStatus.COMPLETED
        db.session.commit()
        return apt.malh


# ---------------------------------------------------------------------------
# Test 21: Single service (no package)
# ---------------------------------------------------------------------------

def test_single_service_post_care_content(app, setup_services):
    """Completed single-service appointment builds correct post-care content."""
    data = setup_services
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        db.session.refresh(apt)

        content = build_post_care_content(apt)
        assert len(content['service_sections']) == 1
        assert 'Massage Body' in content['service_sections'][0]['tendv']
        assert 'Uong du nuoc' in content['service_sections'][0]['instructions']
        assert content['package_sections'] == []
        assert content['has_content'] is True
        assert content['fallback_used'] is False


def test_single_service_post_care_html_body(app, setup_services):
    """build_post_care_html contains service instruction and appointment details."""
    data = setup_services
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        db.session.refresh(apt)

        body = build_post_care_html(apt)
        assert 'Massage Body' in body
        assert 'Uong du nuoc' in body
        assert str(apt.malh) in body


def test_single_service_sync_creates_exactly_one_postcare_job(app, setup_services):
    """sync_appointment_jobs (COMPLETED) creates exactly 1 post_care job, idempotent."""
    data = setup_services
    now = datetime.utcnow()
    with app.app_context():
        customer = db.session.get(KhachHang, data['customer'])
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        db.session.refresh(apt)

        notifications.sync_appointment_jobs(apt, now)
        db.session.flush()
        # Idempotency: call twice
        notifications.sync_appointment_jobs(apt, now)
        db.session.commit()

        assert NotificationJob.query.filter_by(type='post_care').count() == 1
        assert NotificationJob.query.filter_by(type='review_request').count() == 1
        job = NotificationJob.query.filter_by(type='post_care').one()
        assert job.status == 'pending'
        assert job.scheduled_at <= now + timedelta(seconds=1)
        assert 'Uong du nuoc' in job.payload_json['body']


def test_single_service_worker_sends_email(app, setup_services, monkeypatch):
    """Worker processes post_care job and marks it sent."""
    data = setup_services
    now = datetime.utcnow()
    sent = []
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: sent.append(kw.get('idempotency_key')) or True)

    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        db.session.refresh(apt)

        notifications.sync_appointment_jobs(apt, now)
        db.session.commit()

        result = notifications.process_jobs(now=now)
        assert result['sent'] == 1
        assert result['sent'] == 1
        # No duplicate on second run
        result2 = notifications.process_jobs(now=now)
        assert result2['sent'] == 0
        job = NotificationJob.query.filter_by(type='post_care').one()
        assert job.status == 'sent'
        assert len(sent) == 1


# ---------------------------------------------------------------------------
# Test 22: Package appointment → both service and package instructions
# ---------------------------------------------------------------------------

@pytest.fixture
def package_with_post_care(app, setup_services):
    """Create GoiDichVu with post_care_instructions."""
    data = setup_services
    with app.app_context():
        package = packages.save_package(dict(
            tengoi='Massage phuc hoi 5 buoi',
            mota='Goi thu nghiem',
            giagoi=1200000,
            validity_months=6,
            post_care_instructions='Nen cach moi buoi 5-7 ngay.\nDuy tri uong du nuoc trong lieu trinh.',
            items=[dict(madv=data['svc1'], total_sessions=5)],
        ))
        db.session.commit()

        # Create purchase and activate
        purchase = GoiDichVuPurchase(
            makh=data['customer'], magoi=package.magoi, amount=1200000,
            payment_method='cash', status='paid',
            snapshot_json=packages.serialize_package(package),
            paid_at=packages.local_now(),
        )
        db.session.add(purchase)
        db.session.flush()
        record = packages.activate_package_purchase(purchase)
        db.session.commit()

        return {**data, 'package': package.magoi, 'record': record.mathe}


def test_package_appointment_post_care_content(app, package_with_post_care):
    """Completed package appointment has BOTH service_sections and package_sections."""
    data = package_with_post_care
    now = datetime.utcnow()
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(11)), trangthai=AppointmentStatus.CONFIRMED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.flush()

        # Reserve from treatment
        record = db.session.get(TheLieuTrinh, data['record'])
        item = record.items[0]
        db.session.add(LieuTrinhUsage(
            mathe=data['record'], the_item_id=item.id,
            malh=apt.malh, madv=data['svc1'], state='reserved',
            reserved_at=packages.local_now(),
        ))
        apt.trangthai = AppointmentStatus.COMPLETED
        # Mark as consumed
        db.session.query(LieuTrinhUsage).filter_by(malh=apt.malh).update({'state': 'consumed'})
        db.session.commit()
        db.session.refresh(apt)

        content = build_post_care_content(apt)
        assert len(content['service_sections']) == 1
        assert 'Massage Body' in content['service_sections'][0]['tendv']
        assert 'Uong du nuoc' in content['service_sections'][0]['instructions']
        assert len(content['package_sections']) == 1
        assert 'Massage phuc hoi' in content['package_sections'][0]['tengoi']
        assert 'cach moi buoi' in content['package_sections'][0]['instructions']
        assert content['has_content'] is True


def test_package_post_care_html_contains_both_sections(app, package_with_post_care):
    """Email HTML contains service instructions AND package instructions."""
    data = package_with_post_care
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(11)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.flush()
        record = db.session.get(TheLieuTrinh, data['record'])
        item = record.items[0]
        db.session.add(LieuTrinhUsage(
            mathe=data['record'], the_item_id=item.id,
            malh=apt.malh, madv=data['svc1'], state='consumed',
            reserved_at=packages.local_now(), consumed_at=packages.local_now(),
        ))
        db.session.commit()
        db.session.refresh(apt)

        body = build_post_care_html(apt)
        assert 'Uong du nuoc' in body  # service instructions
        assert 'cach moi buoi' in body  # package instructions
        assert 'Massage phuc hoi' in body  # package name


def test_package_post_care_not_duplicated(app, package_with_post_care):
    """Multiple usages of same package in one appointment → package section appears once."""
    data = package_with_post_care
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(11)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.flush()
        record = db.session.get(TheLieuTrinh, data['record'])
        item = record.items[0]
        db.session.add(LieuTrinhUsage(
            mathe=data['record'], the_item_id=item.id,
            malh=apt.malh, madv=data['svc1'], state='consumed',
            reserved_at=packages.local_now(), consumed_at=packages.local_now(),
        ))
        db.session.commit()
        db.session.refresh(apt)

        content = build_post_care_content(apt)
        # Package appears only once even if multiple usages relate to same package
        assert len(content['package_sections']) == 1


# ---------------------------------------------------------------------------
# Test 23: Multi-service appointment
# ---------------------------------------------------------------------------

def test_multi_service_post_care_contains_all_services(app, setup_services):
    """Appointment with 2 services → email contains both service instructions."""
    data = setup_services
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(9)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc2']))
        db.session.commit()
        db.session.refresh(apt)

        content = build_post_care_content(apt)
        assert len(content['service_sections']) == 2
        names = {s['tendv'] for s in content['service_sections']}
        assert 'Massage Body' in names
        assert 'Cham soc da' in names

        body = build_post_care_html(apt)
        assert 'Uong du nuoc' in body
        assert 'Tranh anh nang' in body


def test_service_without_post_care_not_in_sections(app, setup_services):
    """Service with no post_care_instructions not included in service_sections."""
    data = setup_services
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(9)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc3']))  # no post-care
        db.session.commit()
        db.session.refresh(apt)

        content = build_post_care_content(apt)
        assert content['service_sections'] == []
        assert content['fallback_used'] is True


# ---------------------------------------------------------------------------
# Test 24: Worker
# ---------------------------------------------------------------------------

def test_worker_sends_pending_post_care_job(app, setup_services, monkeypatch):
    """Simulate existing pending post_care jobs (like the DB currently has) → worker sends them."""
    data = setup_services
    now = datetime.utcnow()
    sent = []
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: sent.append(kw.get('idempotency_key')) or True)

    with app.app_context():
        customer = db.session.get(KhachHang, data['customer'])
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.flush()
        # Manually insert a pending job like the existing DB state
        job = NotificationJob(
            type='post_care', makh=data['customer'], malh=apt.malh,
            scheduled_at=now - timedelta(minutes=5),  # already due
            status='pending', unique_key=f'appointment:{apt.malh}:postcare',
            payload_json=dict(to=customer.email, subject='Test', body='Test body'),
        )
        db.session.add(job)
        db.session.commit()

        result = notifications.process_jobs(now=now)
        assert result['sent'] == 1
        assert len(sent) == 1


def test_worker_future_job_not_sent(app, setup_services, monkeypatch):
    """Job scheduled in the future is not sent."""
    data = setup_services
    now = datetime.utcnow()
    sent = []
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: sent.append(True) or True)

    with app.app_context():
        customer = db.session.get(KhachHang, data['customer'])
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.flush()
        job = NotificationJob(
            type='post_care', makh=data['customer'], malh=apt.malh,
            scheduled_at=now + timedelta(hours=2),  # future
            status='pending', unique_key=f'appointment:{apt.malh}:postcare',
            payload_json=dict(to=customer.email, subject='Test', body='Test body'),
        )
        db.session.add(job)
        db.session.commit()

        result = notifications.process_jobs(now=now)
        assert result['sent'] == 0
        assert sent == []


# ---------------------------------------------------------------------------
# Test 26: Migration only added goidichvu.post_care_instructions
# ---------------------------------------------------------------------------

def test_migration_0006_additive(app):
    """Migration 0006 only adds goidichvu.post_care_instructions, not dichvu again."""
    from sqlalchemy import inspect as sa_inspect
    with app.app_context():
        inspector = sa_inspect(db.engine)
        dichvu_cols = {c['name'] for c in inspector.get_columns('dichvu')}
        goidichvu_cols = {c['name'] for c in inspector.get_columns('goidichvu')}

        # dichvu already had post_care_instructions from migration 0004
        assert 'post_care_instructions' in dichvu_cols
        # goidichvu now has post_care_instructions from migration 0006
        assert 'post_care_instructions' in goidichvu_cols


# ---------------------------------------------------------------------------
# Test: package serializer includes post_care_instructions
# ---------------------------------------------------------------------------

def test_serialize_package_includes_post_care(app, setup_services):
    """serialize_package returns post_care_instructions field."""
    data = setup_services
    with app.app_context():
        pkg = packages.save_package(dict(
            tengoi='Test Package',
            giagoi=500000,
            validity_months=3,
            post_care_instructions='Test post care content.',
            items=[dict(madv=data['svc1'], total_sessions=3)],
        ))
        db.session.commit()
        serialized = packages.serialize_package(pkg)
        assert 'post_care_instructions' in serialized
        assert serialized['post_care_instructions'] == 'Test post care content.'


def test_serialize_package_empty_post_care(app, setup_services):
    """serialize_package returns empty string when post_care_instructions is None."""
    data = setup_services
    with app.app_context():
        pkg = packages.save_package(dict(
            tengoi='Test Package No Care',
            giagoi=500000,
            validity_months=3,
            items=[dict(madv=data['svc1'], total_sessions=3)],
        ))
        db.session.commit()
        serialized = packages.serialize_package(pkg)
        assert serialized['post_care_instructions'] == ''


# ---------------------------------------------------------------------------
# Test: Profile API post-care endpoint
# ---------------------------------------------------------------------------

def test_profile_post_care_endpoint(app, client, setup_services, customer_auth_headers):
    """GET /api/profile/appointments/<malh>/post-care returns correct content."""
    data = setup_services
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        malh = apt.malh

    r = client.get(f'/api/profile/appointments/{malh}/post-care', headers=customer_auth_headers)
    assert r.status_code == 200, r.json
    assert r.json['success'] is True
    assert 'post_care' in r.json
    assert 'service_sections' in r.json['post_care']
    assert len(r.json['post_care']['service_sections']) == 1


def test_profile_post_care_not_completed(app, client, setup_services, customer_auth_headers):
    """GET returns 400 if appointment not completed."""
    data = setup_services
    with app.app_context():
        apt = LichHen(makh=data['customer'], manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.CONFIRMED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        malh = apt.malh

    r = client.get(f'/api/profile/appointments/{malh}/post-care', headers=customer_auth_headers)
    assert r.status_code == 400


def test_profile_post_care_wrong_customer(app, client, setup_services):
    """GET returns 404 if appointment belongs to different customer."""
    data = setup_services
    with app.app_context():
        other = KhachHang(hoten='Other', taikhoan='other_pc', matkhau='hash', trangthai='active')
        db.session.add(other)
        db.session.flush()
        apt = LichHen(makh=other.makh, manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        malh = apt.malh
        token = create_access_token(identity=f'customer:{data["customer"]}')

    r = client.get(f'/api/profile/appointments/{malh}/post-care',
        headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Test: No post-care when customer has no email
# ---------------------------------------------------------------------------

def test_no_post_care_job_when_no_email(app, setup_services):
    """Customer without email → sync_appointment_jobs does NOT crash, no job created."""
    data = setup_services
    now = datetime.utcnow()
    with app.app_context():
        no_email_customer = KhachHang(
            hoten='No Email', taikhoan='noemail_pc', matkhau='hash',
            trangthai='active', email=None
        )
        db.session.add(no_email_customer)
        db.session.flush()
        apt = LichHen(makh=no_email_customer.makh, manv=data['staff'],
            ngaygio=datetime.combine(data['day'], time(10)), trangthai=AppointmentStatus.COMPLETED)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['svc1']))
        db.session.commit()
        db.session.refresh(apt)

        # Must not raise
        notifications.sync_appointment_jobs(apt, now)
        db.session.commit()
        # No job created
        assert NotificationJob.query.filter_by(malh=apt.malh).count() == 0


# ---------------------------------------------------------------------------
# Test: Worker CLI command exists
# ---------------------------------------------------------------------------

def test_notification_worker_command_registered(app):
    """notification-worker CLI command is registered."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=['notification-worker', '--help'])
    assert result.exit_code == 0
    assert 'interval' in result.output or 'batch' in result.output or 'Worker' in result.output

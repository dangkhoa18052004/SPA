from datetime import datetime, timedelta

import pytest
from app.extensions import db
from app.models import (LichHen, ChiTietLichHen, DichVu, HoaDon, ThanhToan,
                        NotificationJob, LieuTrinhUsage, TheLieuTrinhItem)
from app.services import package_service as packages, notification_service as notifications, email_service


def appointment(app, state='confirmed', package=False, mixed=False, instructions=True, staff_id=None):
    with app.app_context():
        service = DichVu(tendv='Massage flow', gia=300000, thoiluong=60, active=True,
                        post_care_instructions='Uống đủ nước.\nNghỉ ngơi sau massage.' if instructions else None)
        other = DichVu(tendv='Skin flow', gia=250000, thoiluong=45, active=True,
                      post_care_instructions='Tránh ánh nắng mạnh.' if instructions else None)
        db.session.add_all([service, other])
        db.session.flush()
        apt = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=staff_id or app.config['TEST_STAFF_ID'],
                      ngaygio=packages.local_now(), trangthai=state)
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=service.madv))
        if mixed:
            db.session.add(ChiTietLichHen(malh=apt.malh, madv=other.madv))
        if package:
            pkg = packages.save_package(dict(tengoi='Massage 5 buổi flow', giagoi=1200000,
                validity_months=6, post_care_instructions='Duy trì khoảng cách 5–7 ngày giữa các buổi.',
                items=[dict(madv=service.madv, total_sessions=5)]))
            purchase = packages.create_purchase(pkg.magoi, apt.makh, 'cash')
            _, treatment, _ = packages.confirm_purchase(purchase.id, purchase.amount, method='cash', cash_received=1200000)
            packages.reserve_usages(apt, [dict(mathe=treatment.mathe, madv=service.madv, quantity=1)])
        db.session.commit()
        return apt.malh


def detail(client, headers, apt_id):
    response = client.get(f'/api/admin/appointments/{apt_id}', headers=headers)
    assert response.status_code == 200, response.json
    return response.json['appointment']


def complete(client, headers, apt_id):
    response = client.post(f'/api/admin/appointments/{apt_id}/complete', headers=headers)
    assert response.status_code == 200, response.json


@pytest.mark.parametrize('state', ['confirmed', 'in_progress'])
def test_staff_complete_invoice_and_care_are_independent(app, client, staff_auth_headers, admin_auth_headers, monkeypatch, state):
    apt_id = appointment(app, state=state)
    row = detail(client, staff_auth_headers, apt_id)
    assert row['permissions']['canComplete'] and row['payment_status'] is None
    assert not row['permissions']['canCreateInvoice']
    complete(client, staff_auth_headers, apt_id)
    complete(client, staff_auth_headers, apt_id)
    row = detail(client, admin_auth_headers, apt_id)
    assert row['trangthai'] == 'completed'
    assert row['payment_status'] == 'Chưa thanh toán'
    assert row['permissions']['canCreateInvoice'] and not row['permissions']['canComplete']
    with app.app_context():
        job = NotificationJob.query.filter_by(unique_key=f'appointment:{apt_id}:postcare').one()
        assert job.status == 'pending' and job.attempts == 0
        assert job.payload_json['subject'] == 'Bin Spa - Dặn dò sau buổi chăm sóc'
        assert 'Uống đủ nước.' in job.payload_json['body']
        assert HoaDon.query.count() == ThanhToan.query.count() == 0
        review = NotificationJob.query.filter_by(malh=apt_id, type='review_request').one()
        assert review.scheduled_at - job.scheduled_at == timedelta(hours=2)
    sent = []
    def send(*args, **kwargs):
        sent.append((args, kwargs))
        return True
    monkeypatch.setattr(email_service, 'send_email', send)
    with app.app_context():
        assert notifications.process_jobs()['sent'] == 1
        assert notifications.process_jobs()['sent'] == 0
    assert len(sent) == 1 and sent[0][1]['idempotency_key'] == f'appointment:{apt_id}:postcare'
    created = client.post(f'/api/admin/appointments/{apt_id}/create-invoice', headers=admin_auth_headers)
    assert created.status_code == 201
    invoice_id = created.json['invoice_id']
    for _ in range(2):
        row = detail(client, admin_auth_headers, apt_id)
        assert row['permissions']['canPayInvoice'] and not row['permissions']['canCreateInvoice']
        assert row['invoice']['mahd'] == invoice_id and row['trangthai'] == 'completed'
    assert client.post(f'/api/admin/invoices/{invoice_id}/record-payment', headers=admin_auth_headers,
                       json=dict(sotien=350000, phuongthuc='Tiền mặt')).status_code == 201
    row = detail(client, admin_auth_headers, apt_id)
    assert row['trangthai'] == 'completed' and row['payment_status'] == 'Đã thanh toán'
    assert row['permissions']['canViewInvoice'] and not row['permissions']['canPayInvoice']
    complete(client, admin_auth_headers, apt_id)
    with app.app_context():
        assert notifications.process_jobs()['sent'] == 0
        assert NotificationJob.query.filter_by(malh=apt_id, type='post_care').count() == 1


def test_staff_cannot_complete_someone_elses_appointment(app, client, staff_auth_headers):
    apt_id = appointment(app, staff_id=app.config['TEST_STAFF2_ID'])
    assert client.post(f'/api/admin/appointments/{apt_id}/complete', headers=staff_auth_headers).status_code == 403
    with app.app_context():
        assert db.session.get(LichHen, apt_id).trangthai == 'confirmed'
        assert NotificationJob.query.count() == 0


def test_staff_schedule_uses_appointment_route_and_exposes_completion(app, client, staff_auth_headers):
    own_id = appointment(app)
    appointment(app, staff_id=app.config['TEST_STAFF2_ID'])
    with app.app_context():
        day = db.session.get(LichHen, own_id).ngaygio.date().isoformat()
    response = client.get(f'/api/admin/appointments/my-schedule?start_date={day}&end_date={day}', headers=staff_auth_headers)
    assert response.status_code == 200, response.json
    rows = response.json['appointments']
    assert len(rows) == 1 and rows[0]['malh'] == own_id
    assert rows[0]['permissions']['canComplete']
    assert rows[0]['invoice'] is None and rows[0]['payment_status'] is None


@pytest.mark.parametrize('mixed', [False, True])
def test_package_consumed_once_care_combined_and_only_extra_services_billed(app, client, admin_auth_headers, monkeypatch, mixed):
    apt_id = appointment(app, package=True, mixed=mixed)
    complete(client, admin_auth_headers, apt_id)
    complete(client, admin_auth_headers, apt_id)
    row = detail(client, admin_auth_headers, apt_id)
    assert row['package_covered'] is (not mixed)
    assert row['permissions']['canCreateInvoice'] is mixed
    assert row['payment_status'] == ('Chưa thanh toán' if mixed else 'Đã thanh toán bằng gói')
    with app.app_context():
        usage = LieuTrinhUsage.query.filter_by(malh=apt_id).one()
        assert usage.state == 'consumed'
        assert packages.item_counts(db.session.get(TheLieuTrinhItem, usage.the_item_id))['consumed'] == 1
        job = NotificationJob.query.filter_by(malh=apt_id, type='post_care').one()
        assert 'DẶN DÒ SAU DỊCH VỤ' in job.payload_json['body']
        assert 'LƯU Ý DÀNH CHO LIỆU TRÌNH' in job.payload_json['body']
        assert '5–7 ngày' in job.payload_json['body']
        assert HoaDon.query.count() == 0
    sent = []
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: sent.append(a) or True)
    with app.app_context():
        assert notifications.process_jobs()['sent'] == 1
    assert len(sent) == 1
    result = client.post(f'/api/admin/appointments/{apt_id}/create-invoice', headers=admin_auth_headers)
    assert result.status_code == (201 if mixed else 400)
    with app.app_context():
        if mixed:
            assert HoaDon.query.filter_by(malh=apt_id).one().tongtien == 250000
        else:
            assert HoaDon.query.count() == 0


def test_provider_failure_keeps_completed_and_retries_same_job(app, client, admin_auth_headers, monkeypatch):
    apt_id = appointment(app, instructions=False)
    def fail(*args, **kwargs):
        raise RuntimeError('Provider test failure')
    monkeypatch.setattr(email_service, 'send_email', fail)
    complete(client, admin_auth_headers, apt_id)  # No provider call in the request.
    with app.app_context():
        job = NotificationJob.query.filter_by(malh=apt_id, type='post_care').one()
        assert 'Vui lòng nghỉ ngơi' in job.payload_json['body']
        now = datetime.utcnow()
        assert notifications.process_jobs(now=now)['failed'] == 1
        db.session.refresh(job)
        assert job.attempts == 1 and job.status == 'pending'
        assert job.last_error == 'Provider test failure'
        assert job.scheduled_at == now + timedelta(minutes=5)
        assert db.session.get(LichHen, apt_id).trangthai == 'completed'
        keys = []
        monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: keys.append(kw['idempotency_key']) or True)
        assert notifications.process_jobs(now=now + timedelta(minutes=5))['sent'] == 1
        assert keys == [f'appointment:{apt_id}:postcare']


def test_continuous_worker_processes_jobs_and_stops_on_ctrl_c(app, monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 'worker-test-key')
    calls, handlers = [], {}
    monkeypatch.setattr(notifications.signal, 'signal', lambda number, handler: handlers.update({number: handler}))
    monkeypatch.setattr(notifications, 'process_jobs', lambda batch_size: calls.append(batch_size) or dict(sent=1, failed=1, cancelled=1))
    monkeypatch.setattr(notifications._time, 'sleep', lambda seconds: handlers[notifications.signal.SIGINT](None, None))
    result = app.test_cli_runner().invoke(args=['notification-worker', '--interval', '15', '--batch-size', '50'])
    assert result.exit_code == 0, result.output
    assert calls == [50]
    assert 'sent=1 failed=1 cancelled=1' in result.output
    assert 'Da dung' in result.output

"""Worker environment, transport diagnostics and safe real-email test scoping."""
from datetime import datetime, timedelta
import logging

import pytest
import requests

from app.extensions import db
from app.models import HoaDon, KhachHang, LichHen, NotificationJob
from app.services import email_service, notification_service as notifications
from test_appointment_completion_flow import appointment, complete


class ProviderResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self.body = body or {'id': 'provider-test-id'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('Provider rejected request')

    def json(self):
        return self.body


@pytest.mark.parametrize('value', [None, '', '   '])
def test_worker_missing_key_fails_before_processing(app, monkeypatch, value):
    if value is None:
        monkeypatch.delenv('RESEND_API_KEY', raising=False)
    else:
        monkeypatch.setenv('RESEND_API_KEY', value)
    monkeypatch.setattr(email_service.resend, 'api_key', 'stale-import-key')
    calls = []
    monkeypatch.setattr(notifications, 'process_jobs', lambda **kw: calls.append(kw))
    result = app.test_cli_runner().invoke(args=['notification-worker', '--interval', '15'])
    assert result.exit_code == 1
    assert 'RESEND_API_KEY configured: no' in result.output
    assert 'RESEND_API_KEY is not configured for notification worker.' in result.output
    assert not calls and 'stale-import-key' not in result.output


def test_transport_reads_process_key_and_returns_provider_id(app, monkeypatch, caplog):
    monkeypatch.setenv('RESEND_API_KEY', 'worker-env-key')
    monkeypatch.setattr(email_service.resend, 'api_key', 'old-web-key')
    calls = []
    monkeypatch.setattr(email_service.requests, 'post', lambda *a, **kw: calls.append(kw) or ProviderResponse())
    with app.app_context(), caplog.at_level(logging.INFO):
        result = email_service.send_email('private@example.test', 'Care', '<p>Care</p>',
            idempotency_key='appointment:1:postcare', return_provider_response=True)
    assert result['id'] == 'provider-test-id'
    assert calls[0]['headers']['Authorization'] == 'Bearer worker-env-key'
    assert calls[0]['headers']['Idempotency-Key'] == 'appointment:1:postcare'
    assert 'p***@example.test' in caplog.text and 'provider-test-id' in caplog.text
    assert 'private@example.test' not in caplog.text and 'worker-env-key' not in caplog.text


def test_provider_403_is_persisted_then_retry_uses_same_key(app, client, admin_auth_headers, monkeypatch, caplog):
    apt_id = appointment(app)
    complete(client, admin_auth_headers, apt_id)
    monkeypatch.setenv('RESEND_API_KEY', 'secret-for-test')
    monkeypatch.setattr(email_service.requests, 'post', lambda *a, **kw: ProviderResponse(403,
        {'message': 'Domain not verified secret-for-test'}))
    now = datetime.utcnow()
    with app.app_context(), caplog.at_level(logging.INFO):
        assert notifications.process_jobs(now=now)['failed'] == 1
        job = NotificationJob.query.filter_by(malh=apt_id, type='post_care').one()
        assert job.status == 'pending' and job.attempts == 1
        assert job.last_error == 'Resend HTTP 403: Domain not verified [redacted]'
        assert job.scheduled_at == now + timedelta(minutes=5)
        assert db.session.get(LichHen, apt_id).trangthai == 'completed'
        assert HoaDon.query.count() == 0
        calls = []
        monkeypatch.setattr(email_service.requests, 'post', lambda *a, **kw: calls.append(kw) or ProviderResponse())
        assert notifications.process_jobs(now=job.scheduled_at)['sent'] == 1
        db.session.refresh(job)
        assert job.status == 'sent' and job.sent_at and job.attempts == 2
        assert calls[0]['headers']['Idempotency-Key'] == f'appointment:{apt_id}:postcare'
        assert notifications.process_jobs(now=job.sent_at)['sent'] == 0
    assert 'secret-for-test' not in caplog.text
    assert f'post_care appointment={apt_id}' in caplog.text and 'provider_id=provider-test-id' in caplog.text


@pytest.mark.parametrize('email', [None, '', '   '])
def test_complete_without_email_does_not_create_job(app, client, admin_auth_headers, caplog, email):
    apt_id = appointment(app)
    with app.app_context():
        db.session.get(KhachHang, app.config['TEST_CUSTOMER_ID']).email = email
        db.session.commit()
    with caplog.at_level(logging.INFO):
        complete(client, admin_auth_headers, apt_id)
    with app.app_context():
        assert db.session.get(LichHen, apt_id).trangthai == 'completed'
        assert NotificationJob.query.filter_by(malh=apt_id).count() == 0
    assert 'không tạo post-care vì khách không có email' in caplog.text


def test_scoped_worker_leaves_other_jobs_untouched(app, client, admin_auth_headers, monkeypatch):
    first = appointment(app)
    second = appointment(app)
    complete(client, admin_auth_headers, first)
    complete(client, admin_auth_headers, second)
    calls = []
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: calls.append(kw['idempotency_key']) or True)
    with app.app_context():
        assert notifications.process_jobs(appointment_id=second)['sent'] == 1
        assert calls == [f'appointment:{second}:postcare']
        assert NotificationJob.query.filter_by(malh=first, type='post_care').one().attempts == 0
        assert notifications.process_jobs(appointment_id=second)['sent'] == 0


def test_enqueue_failure_rolls_back_completion_and_package_consumption(app, client, admin_auth_headers, monkeypatch):
    from app.models import LieuTrinhUsage
    apt_id = appointment(app, package=True)
    original = notifications.enqueue
    def enqueue(*args, **kwargs):
        if args[1] == 'review_request':
            raise RuntimeError('Outbox storage failed')
        return original(*args, **kwargs)
    monkeypatch.setattr(notifications, 'enqueue', enqueue)
    response = client.post(f'/api/admin/appointments/{apt_id}/complete', headers=admin_auth_headers)
    assert response.status_code == 500
    with app.app_context():
        assert db.session.get(LichHen, apt_id).trangthai == 'confirmed'
        assert LieuTrinhUsage.query.filter_by(malh=apt_id).one().state == 'reserved'
        assert NotificationJob.query.filter_by(malh=apt_id).count() == 0


def test_unpaid_invoice_does_not_delay_care(app, client, admin_auth_headers, monkeypatch):
    apt_id = appointment(app)
    complete(client, admin_auth_headers, apt_id)
    assert client.post(f'/api/admin/appointments/{apt_id}/create-invoice', headers=admin_auth_headers).status_code == 201
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **kw: True)
    with app.app_context():
        assert HoaDon.query.filter_by(malh=apt_id).one().trangthai == 'Chưa thanh toán'
        assert notifications.process_jobs()['sent'] == 1
        assert NotificationJob.query.filter_by(malh=apt_id, type='post_care').one().sent_at

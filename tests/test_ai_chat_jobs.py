"""A question survives the page that submitted it, without duplicate AI calls or IDOR."""
from datetime import datetime, timedelta
from uuid import uuid4
import json
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import AIChatJob, KhachHang, NhanVien, LichHen
from app.services import ai_chat_jobs as jobs, ai_service


@pytest.fixture
def queued(app):
    app.config.update(AI_CHAT_JOBS_ENABLED=True, GEMINI_API_KEY='mock-chat-key')
    return app


def payload(**kwargs):
    return dict(request_id=str(uuid4()), message='Spa có dịch vụ nào?', history=[], **kwargs)


def test_navigation_recovers_answer_from_another_page_request(queued, client, customer_auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(ai_service, 'chat', lambda message, **kw: calls.append(message) or dict(reply='Massage 300.000đ', draft=None))
    body = payload()
    result = client.post('/api/ai/chat/jobs', json=body, headers=customer_auth_headers)
    assert result.status_code == 202 and result.json['status'] == 'PENDING' and calls == []
    # A new HTTP connection/page knows the same request id and customer.
    another_page = queued.test_client()
    assert another_page.get('/api/ai/chat/jobs/' + body['request_id'], headers=customer_auth_headers).json['status'] == 'PENDING'
    with queued.app_context(): assert jobs.process_next() == body['request_id']
    answer = another_page.get('/api/ai/chat/jobs/' + body['request_id'], headers=customer_auth_headers)
    assert answer.json['result']['reply'] == 'Massage 300.000đ' and answer.json['status'] == 'SUCCEEDED'
    for _ in range(3):
        assert client.post('/api/ai/chat/jobs', json=body, headers=customer_auth_headers).json['status'] == 'SUCCEEDED'
    with queued.app_context():
        assert jobs.process_next() is None and AIChatJob.query.count() == 1 and LichHen.query.count() == 0
    assert len(calls) == 1


def test_anonymous_session_cannot_read_another_visitors_job(queued, client, monkeypatch):
    client.get('/api/ai/status')  # Establish anonymous ownership before navigating.
    body = payload()
    assert client.post('/api/ai/chat/jobs', json=body).status_code == 202
    other = queued.test_client(); other.get('/api/ai/status')
    assert other.get('/api/ai/chat/jobs/' + body['request_id']).status_code == 404
    assert other.post('/api/ai/chat/jobs', json=body).status_code == 404
    monkeypatch.setattr(ai_service, 'chat', lambda *a, **kw: dict(reply='Xin chào', draft=None))
    with queued.app_context(): jobs.process_next()
    assert client.get('/api/ai/chat/jobs/' + body['request_id']).json['result']['reply'] == 'Xin chào'


def test_customer_switch_changes_conversation_scope_and_never_exposes_results(queued, client, customer_auth_headers):
    body = payload()
    first_scope = client.get('/api/ai/status', headers=customer_auth_headers).json['conversation_scope']
    client.post('/api/ai/chat/jobs', json=body, headers=customer_auth_headers)
    with queued.app_context():
        user = KhachHang(hoten='Khách B', taikhoan='other-chat-owner', matkhau='hash', trangthai='active')
        db.session.add(user); db.session.commit()
        headers = {'Authorization': 'Bearer ' + create_access_token(identity=f'customer:{user.makh}')}
    assert client.get('/api/ai/status', headers=headers).json['conversation_scope'] != first_scope
    assert client.get('/api/ai/chat/jobs/' + body['request_id'], headers=headers).status_code == 404


def test_job_payload_is_bounded_and_scrubbed(queued, client, customer_auth_headers):
    body = payload(); body['message'] = 'Khách hàng Test 0912345678 lan@example.com'
    body['history'] = [{'role': 'user', 'text': 'lan@example.com ' * 300}] * 12
    assert client.post('/api/ai/chat/jobs', json=body, headers=customer_auth_headers).status_code == 202
    with queued.app_context():
        row = AIChatJob.query.one()
        saved = json.dumps(row.payload_json, ensure_ascii=False)
        assert '0912345678' not in saved and 'lan@example.com' not in saved and 'Khách hàng Test' not in saved
        assert len(row.payload_json['history']) == 10 and len(row.owner_key) == 64


def test_same_id_with_different_question_is_a_conflict(queued, client):
    body = payload(); client.post('/api/ai/chat/jobs', json=body)
    assert client.post('/api/ai/chat/jobs', json={**body, 'message': 'Câu khác'}).status_code == 409
    with queued.app_context(): assert AIChatJob.query.count() == 1


def test_failed_provider_is_saved_without_retrying_the_same_job(queued, client, monkeypatch):
    calls = []
    def unavailable(*a, **kw): calls.append(1); raise ai_service.AIUpstreamError('AI đang bận', 504)
    monkeypatch.setattr(ai_service, 'chat', unavailable)
    body = payload(); client.post('/api/ai/chat/jobs', json=body)
    with queued.app_context(): jobs.process_next(); assert jobs.process_next() is None
    result = client.get('/api/ai/chat/jobs/' + body['request_id']).json
    assert result['status'] == 'FAILED' and result['message'] == 'AI đang bận' and calls == [1]


def test_permission_is_checked_again_when_worker_runs(queued, client, customer_auth_headers, monkeypatch):
    body = payload(); client.post('/api/ai/chat/jobs', json=body, headers=customer_auth_headers)
    monkeypatch.setattr(ai_service, 'chat', lambda *a, **k: pytest.fail('Inactive customer must not run AI tools'))
    with queued.app_context():
        db.session.get(KhachHang, queued.config['TEST_CUSTOMER_ID']).trangthai = 'blocked'; db.session.commit()
        jobs.process_next()
        assert AIChatJob.query.one().status == 'FAILED'


def test_expired_and_interrupted_jobs_do_not_stay_pending_forever(queued, client):
    body = payload(); client.post('/api/ai/chat/jobs', json=body)
    with queued.app_context():
        row = AIChatJob.query.one(); row.status = 'PROCESSING'; row.started_at = datetime.utcnow() - timedelta(minutes=6)
        db.session.commit(); jobs.expire_stale(); db.session.refresh(row)
        assert row.status == 'FAILED'
        row.expires_at = datetime.utcnow() - timedelta(seconds=1); db.session.commit()
    assert client.get('/api/ai/chat/jobs/' + body['request_id']).status_code == 410
    result = queued.test_cli_runner().invoke(args=['ai', 'prune-chat-jobs', '--dry-run'])
    assert result.exit_code == 0 and 'jobs=1' in result.output
    assert queued.test_cli_runner().invoke(args=['ai', 'prune-chat-jobs']).exit_code == 0
    with queued.app_context(): assert AIChatJob.query.count() == 0


def test_worker_once_runs_only_ai_and_never_notification_jobs(queued, client, monkeypatch):
    from app.services import notification_service
    monkeypatch.setattr(notification_service, 'process_jobs', lambda *a, **kw: pytest.fail('AI worker must not send email'))
    monkeypatch.setattr(ai_service, 'chat', lambda *a, **kw: dict(reply='Trả lời nền', draft=None))
    client.post('/api/ai/chat/jobs', json=payload())
    result = queued.test_cli_runner().invoke(args=['ai', 'chat-worker', '--once'])
    assert result.exit_code == 0 and 'processed:' in result.output


@pytest.mark.parametrize('data', [[], {}, {'request_id': str(uuid4()), 'message': ''}, {'request_id': 'invalid', 'message': 'test'}, {'request_id': str(uuid4()), 'message': 'x' * 1001}])
def test_invalid_jobs_are_rejected(queued, client, data):
    assert client.post('/api/ai/chat/jobs', json=data).status_code == 400

import json
from flask import g
from app.services import ai_service
from test_ai_booking_agent import ai_app, text, call, chat


def test_slow_models_leave_time_for_fallback_and_tool_followup(ai_app, app, client, customer_auth_headers, monkeypatch):
    app.config.update(GEMINI_MODEL='slow-primary', GEMINI_FALLBACK_MODELS='slow-alias,working-lite')
    clock, calls = [0.0], []
    monkeypatch.setattr(ai_service.time, 'monotonic', lambda: clock[0])
    class Response:
        status_code = 200
        def __init__(self, body): self.body = body
        def json(self): return self.body
    def post(url, **kwargs):
        model = url.split('/models/')[1].split(':')[0]
        budget = sum(kwargs['timeout'])
        calls.append((model, budget))
        if model.startswith('slow'):
            clock[0] += budget
            raise ai_service.requests.Timeout()
        clock[0] += 1
        return Response(call('get_available_services_tool') if len(calls) == 3 else text('Có dịch vụ chăm sóc da mụn.'))
    monkeypatch.setattr(ai_service.requests, 'post', post)
    response = chat(client, customer_auth_headers, 'Tìm dịch vụ chăm sóc da mụn')
    assert response.status_code == 200, response.json
    assert response.json['tools_used'] == ['get_available_services_tool']
    assert [model for model, _ in calls] == ['slow-primary', 'slow-alias', 'working-lite', 'working-lite']
    assert calls[0][1] < 8 and clock[0] < 22


def test_business_timeout_has_report_context_and_no_booking_advice(ai_app, client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(ai_service, 'call_gemini', lambda payload: (_ for _ in ()).throw(
        ai_service.AIUpstreamError('Provider timeout', 504)))
    response = client.post('/api/ai/business-summary', headers=admin_auth_headers, json={})
    assert response.status_code == 504
    assert 'tóm tắt kinh doanh' in response.json['msg']
    assert 'Đặt lịch' not in response.json['msg']


def test_business_fallback_returns_facts_and_summary(ai_app, app, client, admin_auth_headers, monkeypatch):
    app.config.update(GEMINI_MODEL='slow', GEMINI_FALLBACK_MODELS='working')
    class Response:
        status_code = 200
        def json(self): return text(json.dumps({'summary': 'Cần theo dõi tình hình vận hành.', 'suggestions': ['Theo dõi lịch hẹn.']}))
    def post(url, **kwargs):
        if '/slow:' in url: raise ai_service.requests.Timeout()
        return Response()
    monkeypatch.setattr(ai_service.requests, 'post', post)
    response = client.post('/api/ai/business-summary', headers=admin_auth_headers, json={})
    assert response.status_code == 200 and response.json['facts']
    assert response.json['summary'] == 'Cần theo dõi tình hình vận hành.'


def test_plain_provider_timeout_never_mentions_booking(ai_app, app, monkeypatch):
    monkeypatch.setattr(ai_service.requests, 'post', lambda *a, **k: (_ for _ in ()).throw(ai_service.requests.Timeout()))
    with app.app_context():
        import pytest
        with pytest.raises(ai_service.AIUpstreamError) as error:
            ai_service.call_gemini({})
        assert error.value.status_code == 504
        assert 'Đặt lịch' not in error.value.message

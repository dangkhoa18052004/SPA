from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import time
from app.extensions import db
from app.models import AIChatJob
from app.services import ai_chat_jobs, ai_service
from test_attendance_concurrency import concurrent_operations  # noqa: F401


def test_navigation_resubmits_and_parallel_workers_execute_once(concurrent_operations, monkeypatch):
    app = concurrent_operations
    app.config.update(AI_CHAT_JOBS_ENABLED=True, GEMINI_API_KEY='test-chat-key', AUTH_RATE_LIMIT_ENABLED=False)
    body = dict(request_id=str(uuid4()), message='Dịch vụ nào?', history=[])
    barrier = Barrier(2)
    def submit():
        barrier.wait(timeout=10)
        with app.test_client() as client:
            return client.post('/api/ai/chat/jobs', json=body, headers=app.config['RACE_HEADERS']).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(code == 202 for code in pool.map(lambda _: submit(), range(2)))
    calls = []
    def respond(*a, **kw): calls.append(1); time.sleep(.1); return dict(reply='Còn dịch vụ', draft=None)
    monkeypatch.setattr(ai_service, 'chat', respond)
    barrier = Barrier(2)
    def work():
        barrier.wait(timeout=10)
        with app.app_context(): return ai_chat_jobs.process_next()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: work(), range(2)))
    assert results.count(body['request_id']) == 1 and calls == [1]
    with app.app_context(): assert AIChatJob.query.one().status == 'SUCCEEDED'

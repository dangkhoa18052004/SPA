"""A shared database limit must apply across independent connections/process contexts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from app.services.runtime_service import consume_limit
from test_attendance_concurrency import concurrent_operations  # noqa: F401


def test_last_auth_attempt_is_granted_once(concurrent_operations):
    app = concurrent_operations
    barrier = Barrier(2)
    def attempt():
        barrier.wait(timeout=10)
        with app.app_context():
            return consume_limit('auth.staff_login', 'same-peer', 1, 900, datetime(2026, 10, 15, 9))[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [False, True]

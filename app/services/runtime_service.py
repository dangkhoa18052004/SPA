"""Bounded per-process HTTP measurements and database-shared authentication throttling."""
from collections import deque
from datetime import datetime, timedelta
import hashlib
import calendar
import hmac
import json
import logging
import math
import threading
import time
from flask import g, request, jsonify, current_app
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db
from ..models import AuthRateBucket, WorkerHeartbeat, NotificationJob, PaymentWebhookEvent, AttendanceEvent


class RequestMeasurements:
    def __init__(self, capacity=5000):
        self.rows = deque(maxlen=capacity)
        self.lock = threading.Lock()

    def record(self, route, method, status, duration):
        with self.lock:
            self.rows.append((time.monotonic(), route, method, status, duration))

    def snapshot(self):
        cutoff = time.monotonic() - 1800
        with self.lock:
            rows = [r for r in self.rows if r[0] >= cutoff]
        groups = {}
        for _, route, method, status, duration in rows:
            item = groups.setdefault((route, method), dict(route=route, method=method, requests=0, client_errors=0, server_errors=0, durations=[]))
            item['requests'] += 1
            item['client_errors'] += int(400 <= status < 500)
            item['server_errors'] += int(status >= 500)
            item['durations'].append(duration)
        for item in groups.values():
            durations = sorted(item.pop('durations'))
            item['p95_ms'] = round(durations[max(0, math.ceil(len(durations) * .95) - 1)], 1)
        return dict(scope='current_process', window_seconds=1800, sample_limit=self.rows.maxlen,
            requests=len(rows), client_errors=sum(400 <= r[3] < 500 for r in rows), server_errors=sum(r[3] >= 500 for r in rows),
            routes=sorted(groups.values(), key=lambda r: (-r['server_errors'], -r['requests'], r['route'])))


LIMITS = {
    'auth.customer_login': (30, 900), 'auth.staff_login': (30, 900),
    'auth.verify_otp': (10, 600), 'auth.reset_password': (10, 600),
    'auth.register': (3, 600), 'auth.forgot_password': (3, 600), 'auth.resend_otp': (3, 600),
    'ai.ai_chat': (20, 60),
    'ai.submit_chat_job': (20, 60),
}


def insert_for(table):
    if db.engine.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(table)


def consume_limit(endpoint, address, limit, seconds, now=None):
    now = now or datetime.utcnow()
    tick = calendar.timegm(now.utctimetuple())
    bucket = tick // seconds
    secret = str(current_app.config['SECRET_KEY']).encode()
    key = hmac.new(secret, f'{endpoint}|{address}'.encode(), hashlib.sha256).hexdigest()
    table = AuthRateBucket.__table__
    statement = insert_for(table).values(key=key, bucket=bucket, attempts=1,
        expires_at=datetime.utcfromtimestamp((bucket + 1) * seconds))
    statement = statement.on_conflict_do_update(index_elements=['key', 'bucket'], set_={'attempts': table.c.attempts + 1}).returning(table.c.attempts)
    # Independent transaction: limits must survive rejected logins and their rollbacks.
    with db.engine.begin() as conn:
        attempts = conn.execute(statement).scalar_one()
    return attempts <= limit, max(1, seconds - tick % seconds)


def register_runtime(app):
    app.extensions['request_measurements'] = RequestMeasurements()
    if app.config.get('OBSERVABILITY_ENABLED'):
        app.logger.setLevel(logging.INFO)

    @app.before_request
    def request_start():
        g.request_started = time.perf_counter()
        if request.method == 'POST' and request.endpoint in ('auth.restore_customer_session', 'auth.logout'):
            origin = request.headers.get('Origin')
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' or origin and origin.rstrip('/') != request.host_url.rstrip('/'):
                return jsonify(success=False, message='Nguồn yêu cầu không hợp lệ.'), 403
        if app.config.get('AUTH_RATE_LIMIT_ENABLED') and request.method == 'POST' and request.endpoint in LIMITS:
            try:
                allowed, retry = consume_limit(request.endpoint, request.remote_addr or 'unknown', *LIMITS[request.endpoint])
            except SQLAlchemyError:
                app.logger.error('Authentication rate-limit storage unavailable; request_id=%s', g.get('request_id'))
                return jsonify(success=False, message='Chưa thể kiểm tra đăng nhập. Vui lòng thử lại sau.'), 503
            if not allowed:
                response = jsonify(success=False, message='Bạn đã thử quá nhiều lần. Vui lòng chờ rồi thử lại.', code='rate_limited')
                response.status_code = 429
                response.headers['Retry-After'] = str(retry)
                return response

    @app.after_request
    def record_request(response):
        if app.config.get('OBSERVABILITY_ENABLED') and request.path.startswith('/api/') and request.endpoint != 'release.runtime_status':
            duration = max(0, (time.perf_counter() - g.get('request_started', time.perf_counter())) * 1000)
            route = request.url_rule.rule if request.url_rule else 'unmatched'
            app.extensions['request_measurements'].record(route, request.method, response.status_code, duration)
            # Intentionally exclude query strings, bodies, cookies, tokens, identities and IPs.
            app.logger.info(json.dumps(dict(event='http_request', request_id=g.get('request_id'),
                route=route, method=request.method, status=response.status_code, duration_ms=round(duration, 1)), separators=(',', ':')))
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(self)')
        if request.path.startswith('/api/'):
            response.headers.setdefault('Cache-Control', 'private, no-store')
        if app.config.get('APP_ENV') == 'production' and request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
        return response


def heartbeat(status='ok', name='notification'):
    if not current_app.config.get('OBSERVABILITY_ENABLED'): return
    try:
        table = WorkerHeartbeat.__table__
        values = dict(name=name, last_seen_at=datetime.utcnow(), status=status)
        statement = insert_for(table).values(**values).on_conflict_do_update(index_elements=['name'], set_=values)
        with db.engine.begin() as conn: conn.execute(statement)
    except SQLAlchemyError:
        current_app.logger.error('Unable to record worker heartbeat (%s)', name)


def runtime_snapshot(start, end, branch_ids):
    lo = datetime.combine(start, datetime.min.time()) - timedelta(hours=7)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time()) - timedelta(hours=7)
    now = datetime.utcnow()
    worker = db.session.get(WorkerHeartbeat, 'notification')
    worker_data = dict(state='unknown', last_seen_at=None)
    if worker:
        worker_data = dict(state=worker.status if now - worker.last_seen_at < timedelta(seconds=120) else 'stale', last_seen_at=worker.last_seen_at.isoformat() + 'Z')
    jobs = dict(db.session.query(NotificationJob.status, func.count()).group_by(NotificationJob.status).all())
    overdue = NotificationJob.query.filter(NotificationJob.status == 'pending', NotificationJob.scheduled_at < now - timedelta(minutes=5)).count()
    stuck = NotificationJob.query.filter(NotificationJob.status == 'processing', NotificationJob.processing_at < now - timedelta(minutes=10)).count()
    webhooks = dict(db.session.query(PaymentWebhookEvent.status, func.count()).filter(PaymentWebhookEvent.created_at >= lo, PaymentWebhookEvent.created_at < hi).group_by(PaymentWebhookEvent.status).all())
    gps = [dict(verdict=v, reason=r, count=n) for v, r, n in db.session.query(AttendanceEvent.verdict, AttendanceEvent.reason, func.count()).filter(
        AttendanceEvent.branch_id.in_(branch_ids), AttendanceEvent.server_at >= lo, AttendanceEvent.server_at < hi).group_by(AttendanceEvent.verdict, AttendanceEvent.reason)]
    return dict(http=current_app.extensions['request_measurements'].snapshot(), worker=worker_data,
        jobs=dict(states=jobs, overdue_pending=overdue, stuck_processing=stuck), webhooks=webhooks, gps=gps)

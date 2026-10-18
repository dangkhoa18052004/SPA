"""A database queue, independent of the browser connection and notification mail worker."""
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import time
from uuid import UUID
from flask import current_app, g
from sqlalchemy import select, update, or_, and_
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import AIChatJob, KhachHang, NhanVien
from . import ai_service

TTL = timedelta(hours=2)


def owner_key(actor, anonymous_id):
    kind = actor.get('kind', 'anonymous')
    identity = f'customer:{actor["makh"]}' if kind == 'customer' else f'staff:{actor["manv"]}' if kind == 'staff' else f'anonymous:{anonymous_id}'
    return hmac.new(str(current_app.config['SECRET_KEY']).encode(), identity.encode(), hashlib.sha256).hexdigest()


def valid_id(value):
    try:
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value: raise ValueError()
        return value
    except (ValueError, TypeError, AttributeError):
        raise ai_service.AIError('Mã yêu cầu không hợp lệ.')


def get_job(request_id, owner):
    job = db.session.get(AIChatJob, request_id)
    if not job or not hmac.compare_digest(job.owner_key, owner):
        raise ai_service.AIError('Không tìm thấy yêu cầu này.', 404)
    if job.expires_at <= datetime.utcnow():
        raise ai_service.AIError('Yêu cầu đã hết hạn. Vui lòng gửi lại câu hỏi.', 410)
    return job


def serialize(job):
    return dict(success=True, request_id=job.id, status=job.status,
        result=job.result_json if job.status == 'SUCCEEDED' else None,
        message=job.error_message if job.status == 'FAILED' else None,
        error_status=job.error_status, expires_at=job.expires_at.isoformat() + 'Z')


def submit(data, actor, owner):
    if not isinstance(data, dict): raise ai_service.AIError('Yêu cầu không hợp lệ.')
    request_id = valid_id(data.get('request_id'))
    message = data.get('message')
    if not isinstance(message, str) or not message.strip() or len(message) > ai_service.MAX_MESSAGE_CHARS:
        raise ai_service.AIError('Vui lòng nhập câu hỏi từ 1 đến 1000 ký tự.')
    history = data.get('history', [])
    if not isinstance(history, list): raise ai_service.AIError('Lịch sử hội thoại không hợp lệ.')
    history = [dict(role=h['role'], text=str(h.get('text') or '')[:1000]) for h in history[-10:]
        if isinstance(h, dict) and h.get('role') in ('user', 'model')]
    payload = dict(message=message.strip(), history=history)
    try: digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    except UnicodeError: raise ai_service.AIError('Câu hỏi chứa ký tự không hợp lệ.')
    def existing():
        job = get_job(request_id, owner)
        if not hmac.compare_digest(job.payload_hash, digest):
            raise ai_service.AIError('Mã yêu cầu này đã dùng cho câu hỏi khác.', 409)
        return job
    if db.session.get(AIChatJob, request_id): return existing()
    if not ai_service.is_configured(): raise ai_service.AINotConfigured('Trợ lý AI chưa được cấu hình.')
    if AIChatJob.query.filter(AIChatJob.owner_key == owner, AIChatJob.status.in_(['PENDING', 'PROCESSING']), AIChatJob.expires_at > datetime.utcnow()).count() >= 3:
        raise ai_service.AIError('Bạn đang có câu hỏi chờ trả lời. Vui lòng chờ một chút.', 429)
    # Keep only a bounded, scrubbed payload in the short-lived queue. Full history
    # remains in sessionStorage; never store access tokens or request headers.
    payload = ai_service._scrub_value(payload, [actor.get('name')] if actor.get('name') else [])
    job = AIChatJob(id=request_id, owner_key=owner, actor_kind=actor['kind'],
        actor_id=actor.get('makh') if actor['kind'] == 'customer' else actor.get('manv'),
        payload_hash=digest, payload_json=payload, expires_at=datetime.utcnow() + TTL)
    db.session.add(job)
    try: db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return existing()
    return job


def actor_for(job):
    if job.actor_kind == 'customer':
        user = db.session.get(KhachHang, job.actor_id)
        if not user or user.trangthai != 'active': raise ai_service.AIError('Tài khoản không còn hoạt động.', 403)
        return dict(kind='customer', makh=user.makh, name=user.hoten)
    if job.actor_kind == 'staff':
        user = db.session.get(NhanVien, job.actor_id)
        if not user or not user.trangthai: raise ai_service.AIError('Tài khoản không còn hoạt động.', 403)
        return dict(kind='staff', manv=user.manv, name=user.hoten, role=user.role)
    return dict(kind='anonymous')


def expire_stale():
    now = datetime.utcnow()
    AIChatJob.query.filter(AIChatJob.status.in_(['PENDING', 'PROCESSING']), or_(AIChatJob.expires_at <= now,
        and_(AIChatJob.status == 'PROCESSING', AIChatJob.started_at < now - timedelta(minutes=5)))).update(
            dict(status='FAILED', error_message='Yêu cầu bị gián đoạn. Vui lòng gửi lại câu hỏi.', error_status=503, completed_at=now), synchronize_session=False)
    db.session.commit()


def process_next():
    if not current_app.config.get('AI_CHAT_JOBS_ENABLED'): return None
    expire_stale()
    candidate = select(AIChatJob.id).where(AIChatJob.status == 'PENDING', AIChatJob.expires_at > datetime.utcnow()).order_by(
        AIChatJob.created_at, AIChatJob.id).limit(1).correlate(None)
    if db.engine.dialect.name == 'postgresql': candidate = candidate.with_for_update(skip_locked=True)
    statement = update(AIChatJob).where(AIChatJob.id == candidate.scalar_subquery(), AIChatJob.status == 'PENDING').values(
        status='PROCESSING', started_at=datetime.utcnow()).returning(AIChatJob.id)
    request_id = db.session.execute(statement, execution_options={'synchronize_session': False}).scalar_one_or_none()
    db.session.commit()
    if not request_id: return None
    job = db.session.get(AIChatJob, request_id)
    lease = job.started_at
    previous_deadline = g.get('ai_deadline')
    try:
        actor = actor_for(job)
        g.ai_deadline = time.monotonic() + 22
        result = ai_service.chat(job.payload_json['message'], history=job.payload_json['history'], actor=actor)
        db.session.execute(update(AIChatJob).where(AIChatJob.id == request_id, AIChatJob.status == 'PROCESSING', AIChatJob.started_at == lease).values(
            status='SUCCEEDED', result_json=result, completed_at=datetime.utcnow()), execution_options={'synchronize_session': False})
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        db.session.execute(update(AIChatJob).where(AIChatJob.id == request_id, AIChatJob.status == 'PROCESSING', AIChatJob.started_at == lease).values(status='FAILED',
            error_message=error.message if isinstance(error, ai_service.AIError) else 'Trợ lý chưa xử lý được câu hỏi. Vui lòng thử lại.',
            error_status=error.status_code if isinstance(error, ai_service.AIError) else 500, completed_at=datetime.utcnow()), execution_options={'synchronize_session': False})
        db.session.commit()
        current_app.logger.warning('[ai-chat-job] failed id=%s error_type=%s', request_id, type(error).__name__)
    finally:
        if previous_deadline is None: g.pop('ai_deadline', None)
        else: g.ai_deadline = previous_deadline
    return request_id

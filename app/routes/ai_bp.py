"""API trợ lý AI (giai đoạn 5). AI tùy chọn: thiếu GEMINI_API_KEY chỉ tắt các endpoint này."""
from flask import Blueprint, jsonify, request, current_app, g, session, abort
from flask_jwt_extended import verify_jwt_in_request

from ..decorators import get_current_user, customer_required, roles_required
from ..services import ai_service
import time
import secrets
import click
from ..extensions import db
from ..services import ai_chat_jobs

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


@ai_bp.before_request
def response_deadline():
    # Leave time for a JSON error before a typical 30-second web-worker timeout.
    if request.endpoint in ('ai.ai_chat', 'ai.ai_business_summary'):
        g.ai_deadline = time.monotonic() + 22


def _actor():
    """Người gọi hiện tại (khách / nhân viên / ẩn danh). Chỉ id và vai trò; tên chỉ dùng để ẩn khỏi prompt."""
    try:
        verify_jwt_in_request(optional=True)
        user, kind = get_current_user()
    except Exception:
        user, kind = None, None
    if user is None:
        return {'kind': 'anonymous'}
    if kind == 'customer':
        return {'kind': 'customer', 'makh': user.makh, 'name': user.hoten}
    return {'kind': 'staff', 'manv': user.manv, 'role': user.role, 'name': user.hoten}


@ai_bp.errorhandler(ai_service.AIError)
def ai_error(error):
    return jsonify(success=False, msg=error.message, configured=ai_service.is_configured()), error.status_code


@ai_bp.route('/status')
def ai_status():
    result = dict(success=True, **ai_service.status())
    if current_app.config.get('AI_CHAT_JOBS_ENABLED'):
        _, owner = _job_owner()
        result.update(chat_jobs=True, conversation_scope=owner[:24])
    return jsonify(result)


def _job_owner():
    from ..models import KhachHang, NhanVien
    actor = _actor()
    if actor['kind'] == 'anonymous' and session.get('user_type') == 'customer':
        user = db.session.get(KhachHang, session.get('user_id'))
        if user and user.trangthai == 'active':
            actor = dict(kind='customer', makh=user.makh, name=user.hoten)
    if actor['kind'] == 'customer':
        user = db.session.get(KhachHang, actor['makh'])
        if not user or user.trangthai != 'active': abort(403)
    elif actor['kind'] == 'staff':
        user = db.session.get(NhanVien, actor['manv'])
        if not user or not user.trangthai: abort(403)
    if not session.get('ai_chat_anonymous_id'):
        session['ai_chat_anonymous_id'] = secrets.token_urlsafe(32)
    return actor, ai_chat_jobs.owner_key(actor, session['ai_chat_anonymous_id'])


@ai_bp.route('/chat/jobs', methods=['POST'])
def submit_chat_job():
    if not current_app.config.get('AI_CHAT_JOBS_ENABLED'): abort(404)
    origin = request.headers.get('Origin')
    if request.headers.get('Sec-Fetch-Site') == 'cross-site' or origin and origin.rstrip('/') != request.host_url.rstrip('/'):
        return jsonify(success=False, msg='Nguồn yêu cầu không hợp lệ.'), 403
    actor, owner = _job_owner()
    job = ai_chat_jobs.submit(request.get_json(silent=True), actor, owner)
    return jsonify(ai_chat_jobs.serialize(job)), 202 if job.status in ('PENDING', 'PROCESSING') else 200


@ai_bp.route('/chat/jobs/<request_id>')
def get_chat_job(request_id):
    if not current_app.config.get('AI_CHAT_JOBS_ENABLED'): abort(404)
    _, owner = _job_owner()
    return jsonify(ai_chat_jobs.serialize(ai_chat_jobs.get_job(ai_chat_jobs.valid_id(request_id), owner)))


@ai_bp.cli.command('chat-worker')
@click.option('--interval', default=1, type=click.IntRange(1, 30))
@click.option('--once', is_flag=True, help='Process at most one queued question and exit.')
def chat_worker(interval, once):
    """Process AI questions independently of page requests; never sends mail."""
    from ..models import AIChatJob
    from ..services.runtime_service import heartbeat
    from datetime import datetime
    last_cleanup, last_heartbeat = 0, 0
    try:
        while True:
            try:
                worked = ai_chat_jobs.process_next()
                if once:
                    click.echo('processed: ' + (worked or 'none')); return
                now = time.monotonic()
                if now - last_heartbeat >= 15:
                    heartbeat(name='ai_chat'); last_heartbeat = now
                if current_app.config.get('AI_CHAT_JOBS_ENABLED') and now - last_cleanup >= 600:
                    AIChatJob.query.filter(AIChatJob.expires_at < datetime.utcnow()).delete(synchronize_session=False)
                    db.session.commit(); last_cleanup = now
                if not worked: time.sleep(interval)
            except Exception as error:
                db.session.rollback()
                current_app.logger.error('AI chat worker cycle failed: %s', type(error).__name__)
                if once: raise click.ClickException('Chưa xử lý được câu hỏi; kiểm tra database và migration.')
                time.sleep(max(interval, 3))
    except KeyboardInterrupt:
        click.echo('AI chat worker stopped.')


@ai_bp.cli.command('prune-chat-jobs')
@click.option('--dry-run', is_flag=True)
def prune_chat_jobs(dry_run):
    from datetime import datetime
    from ..models import AIChatJob
    query = AIChatJob.query.filter(AIChatJob.expires_at < datetime.utcnow())
    count = query.count()
    if not dry_run: query.delete(synchronize_session=False); db.session.commit()
    click.echo(f'{"Dry run" if dry_run else "Removed"}: chat jobs={count}')


@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    data = request.get_json(silent=True) or {}
    history = data.get('history') if isinstance(data.get('history'), list) else []
    result = ai_service.chat(data.get('message'), history=history, actor=_actor())
    return jsonify(success=True, **result)


@ai_bp.route('/booking/confirm', methods=['POST'])
@customer_required
def ai_booking_confirm():
    """Khách bấm "Xác nhận đặt lịch": tạo đúng một lịch hẹn từ bản nháp của chính mình."""
    draft_id = (request.get_json(silent=True) or {}).get('draft_id')
    if not draft_id:
        return jsonify(success=False, msg='Thiếu draft_id'), 400
    result = ai_service.confirm_booking_tool(draft_id, g.current_user.makh)
    msg = 'Đặt lịch thành công!' if result['created'] else 'Lịch hẹn này đã được xác nhận trước đó.'
    return jsonify(success=True, msg=msg, **result), 201 if result['created'] else 200


@ai_bp.route('/business-summary', methods=['POST'])
@roles_required('admin', 'manager')
def ai_business_summary():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(ai_service.business_summary(data.get('from'), data.get('to'))), 200
    except ValueError:
        return jsonify(success=False, msg='Ngày không hợp lệ (YYYY-MM-DD)'), 400

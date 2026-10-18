"""Self-service staff security. No administrator can read another person's factor."""
import click
from flask import Blueprint, abort, current_app, g, jsonify, render_template, request
from ..decorators import login_required
from ..extensions import db
from ..security_models import StaffMFA, StaffStepUp
from ..services import staff_security_service as security
from ..ui_assets import portal_assets

staff_security_bp = Blueprint('staff_security', __name__)


@staff_security_bp.errorhandler(security.SecurityError)
def invalid(error):
    db.session.rollback()
    response = jsonify(success=False, message=str(error), code=error.code)
    response.status_code = error.status
    if error.status == 429:
        response.headers['Retry-After'] = str(g.get('security_retry_after', 300))
    return response


@staff_security_bp.before_request
def feature():
    if not current_app.config.get('STAFF_SECURITY_ENABLED'):
        abort(404)
    if request.method != 'GET':
        origin = request.headers.get('Origin')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site' or origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            raise security.SecurityError('Nguồn yêu cầu không hợp lệ.', 403)


def actor():
    user = g.current_user
    if g.current_user_type != 'staff' or not user.trangthai or user.role not in {'admin', 'manager', 'staff', 'letan'}:
        raise security.SecurityError('Cần tài khoản nhân viên đang hoạt động.', 403)
    return user


@staff_security_bp.get('/admin/security')
def page():
    assets = portal_assets('src/main.tsx')
    if not assets:
        abort(503)
    return render_template('operations/portal.html', portal_title='Bảo mật tài khoản', **assets)


@staff_security_bp.get('/api/me/security')
@login_required
def status():
    return jsonify(security.status(actor()))


@staff_security_bp.post('/api/me/security/<action>')
@login_required
def change(action):
    functions = {'enroll': security.start_enrollment, 'confirm': security.confirm_enrollment,
        'verify': security.verify, 'disable': security.disable, 'recovery-codes': security.regenerate}
    user = actor()
    if action == 'lock':
        StaffStepUp.query.filter_by(token_hash=security.token_key(), staff_id=user.manv).delete()
        security.audit(user, 'step_up_locked')
        db.session.commit()
        return jsonify(success=True)
    if action not in functions:
        abort(404)
    security.throttle(user)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise security.SecurityError('Nội dung phải là JSON object.')
    result = functions[action](user, data)
    db.session.commit()
    return jsonify(result or dict(success=True))


def register_commands(app):
    @app.cli.group('staff-security')
    def group():
        """Local maintenance only; never reveal or reset someone else's MFA."""

    @group.command('prune')
    @click.option('--dry-run', is_flag=True)
    def prune(dry_run):
        """Remove expired elevations and expired, never-enabled pending secrets."""
        grants = StaffStepUp.query.filter(StaffStepUp.expires_at <= security.now())
        pending = StaffMFA.query.filter(StaffMFA.enabled_at.is_(None), StaffMFA.pending_expires_at <= security.now())
        click.echo(f'Expired elevations: {grants.count()}; expired setups: {pending.count()}')
        if not dry_run:
            grants.delete(synchronize_session=False)
            pending.update({StaffMFA.pending_ciphertext: None, StaffMFA.pending_expires_at: None}, synchronize_session=False)
            db.session.commit()

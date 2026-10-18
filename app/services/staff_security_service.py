"""RFC 6238 TOTP. Elevation is kept on the server and bound to one JWT JTI."""
import base64
import calendar
import hashlib
import hmac
import re
import secrets
import struct
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, g, jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash
from ..extensions import db
from ..security_models import StaffMFA, StaffRecoveryCode, StaffStepUp, StaffSecurityAudit
from .runtime_service import consume_limit, insert_for

ELEVATION_SECONDS = 600


class SecurityError(Exception):
    def __init__(self, message, status=400, code='invalid_security_request'):
        super().__init__(message)
        self.status, self.code = status, code


def now():
    return datetime.utcnow()


def cipher():
    try:
        return Fernet(current_app.config.get('STAFF_MFA_ENCRYPTION_KEY', '').encode())
    except (ValueError, TypeError, AttributeError):
        raise SecurityError('Chưa thể mở bảo mật tài khoản. Vui lòng liên hệ quản trị.', 503, 'security_unavailable')


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode('ascii')
    except (InvalidToken, ValueError, UnicodeError, AttributeError):
        raise SecurityError('Chưa thể đọc ứng dụng xác thực. Vui lòng liên hệ quản trị.', 503, 'security_unavailable')


def digest(value):
    return hmac.new(str(current_app.config['SECRET_KEY']).encode(), value.encode(), hashlib.sha256).hexdigest()


def token_key():
    return digest('step-up|' + get_jwt()['jti'])


def auth_digest(actor):
    # Changing the password, role or active status invalidates every old elevation.
    return digest(f'auth|{actor.manv}|{actor.matkhau}|{actor.role}|{actor.trangthai}')


def revoke_elevations(staff_id):
    if current_app.config.get('STAFF_SECURITY_ENABLED'):
        StaffStepUp.query.filter_by(staff_id=staff_id).delete(synchronize_session=False)


def audit(actor, action):
    db.session.add(StaffSecurityAudit(actor_id=actor.manv, action=action, request_id=g.get('request_id', '')))


def throttle(actor):
    # Always active with MFA, independent of the general login-rate-limit feature flag.
    try:
        for key, limit in ((f'staff:{actor.manv}', 10), (request.remote_addr or 'unknown', 30)):
            allowed, retry = consume_limit('staff_security.proof', key, limit, 300)
            if not allowed:
                g.security_retry_after = retry
                raise SecurityError('Bạn đã thử quá nhiều lần. Vui lòng chờ rồi thử lại.', 429, 'rate_limited')
    except SQLAlchemyError:
        raise SecurityError('Chưa thể kiểm tra xác thực. Vui lòng thử lại sau.', 503, 'security_unavailable')


def password(actor, data):
    value = data.get('password')
    if not isinstance(value, str) or not 1 <= len(value) <= 1024 or not check_password_hash(actor.matkhau, value):
        raise SecurityError('Mật khẩu hiện tại không chính xác.', 400, 'password_invalid')


def otp_at(secret, counter, digits=6):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    mac = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = mac[-1] & 15
    value = struct.unpack('>I', mac[offset:offset + 4])[0] & 0x7fffffff
    return str(value % (10 ** digits)).zfill(digits)


def matching_counter(secret, code):
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code.strip()):
        return None
    counter = calendar.timegm(now().utctimetuple()) // 30
    for tick in (counter, counter - 1, counter + 1):
        if hmac.compare_digest(otp_at(secret, tick), code.strip()):
            return tick
    return None


def state_for(actor):
    return db.session.get(StaffMFA, actor.manv)


def elevated(actor, state=None):
    state = state or state_for(actor)
    if not state or not state.enabled_at:
        return None
    grant = db.session.get(StaffStepUp, token_key())
    if (grant and grant.staff_id == actor.manv and grant.generation == state.generation
            and grant.expires_at > now() and hmac.compare_digest(grant.auth_digest, auth_digest(actor))):
        return grant.expires_at
    return None


def grant(actor, state):
    expires = min(now() + timedelta(seconds=ELEVATION_SECONDS), datetime.utcfromtimestamp(get_jwt()['exp']))
    values = dict(token_hash=token_key(), staff_id=actor.manv, generation=state.generation,
                  auth_digest=auth_digest(actor), expires_at=expires)
    db.session.execute(insert_for(StaffStepUp.__table__).values(**values).on_conflict_do_update(
        index_elements=['token_hash'], set_=values))
    return expires


def status(actor):
    state = state_for(actor)
    until = elevated(actor, state)
    remaining = StaffRecoveryCode.query.filter_by(staff_id=actor.manv, generation=state.generation, used_at=None).count() if state and state.enabled_at else 0
    return dict(enabled=bool(state and state.enabled_at), verified_until=until.isoformat() + 'Z' if until else None,
        recovery_codes_remaining=remaining, elevation_seconds=ELEVATION_SECONDS,
        sensitive_actions_required=actor.role in {'admin', 'manager'})


def start_enrollment(actor, data):
    password(actor, data)
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
    encrypted = cipher().encrypt(secret.encode()).decode()
    table = StaffMFA.__table__
    statement = insert_for(table).values(staff_id=actor.manv, pending_ciphertext=encrypted,
        pending_expires_at=now() + timedelta(minutes=10), generation=0, last_counter=-1)
    statement = statement.on_conflict_do_update(index_elements=['staff_id'],
        set_=dict(pending_ciphertext=encrypted, pending_expires_at=now() + timedelta(minutes=10)),
        where=table.c.enabled_at.is_(None)).returning(table.c.staff_id)
    if db.session.execute(statement).scalar_one_or_none() is None:
        raise SecurityError('Tài khoản đã bật xác thực hai bước.', 409)
    audit(actor, 'enrollment_started')
    uri = 'otpauth://totp/' + quote('Bin Spa:' + actor.taikhoan, safe='') + '?' + urlencode(
        dict(secret=secret, issuer='Bin Spa', algorithm='SHA1', digits=6, period=30))
    return dict(secret=secret, provisioning_uri=uri, expires_in=600)


def new_recovery_codes(actor, state):
    StaffRecoveryCode.query.filter_by(staff_id=actor.manv).delete(synchronize_session=False)
    codes = []
    for _ in range(10):
        raw = secrets.token_hex(8).upper()
        codes.append('-'.join(raw[i:i + 4] for i in range(0, 16, 4)))
        db.session.add(StaffRecoveryCode(code_hash=digest(f'recovery|{actor.manv}|{raw}'),
            staff_id=actor.manv, generation=state.generation))
    return codes


def confirm_enrollment(actor, data):
    state = state_for(actor)
    if not state or state.enabled_at or not state.pending_expires_at or state.pending_expires_at <= now():
        raise SecurityError('Thiết lập đã hết hạn hoặc đã hoàn tất. Vui lòng bắt đầu lại.', 409)
    tick = matching_counter(decrypt(state.pending_ciphertext), data.get('code'))
    if tick is None:
        raise SecurityError('Mã xác thực chưa đúng. Kiểm tra giờ tự động trên điện thoại.', 400, 'code_invalid')
    changed = db.session.execute(update(StaffMFA).where(StaffMFA.staff_id == actor.manv,
        StaffMFA.enabled_at.is_(None), StaffMFA.pending_ciphertext == state.pending_ciphertext,
        StaffMFA.pending_expires_at > now()).values(secret_ciphertext=state.pending_ciphertext,
        pending_ciphertext=None, pending_expires_at=None, enabled_at=now(), last_counter=tick,
        generation=StaffMFA.generation + 1).returning(StaffMFA.staff_id),
        execution_options={'synchronize_session': False}).scalar_one_or_none()
    if changed is None:
        raise SecurityError('Thiết lập vừa thay đổi. Vui lòng tải lại trang.', 409)
    db.session.refresh(state)
    codes = new_recovery_codes(actor, state)
    grant(actor, state)
    audit(actor, 'mfa_enabled')
    return dict(success=True, recovery_codes=codes)


def prove(actor, code):
    state = state_for(actor)
    if not state or not state.enabled_at:
        raise SecurityError('Hãy thiết lập ứng dụng xác thực tại Bảo mật tài khoản.', 403, 'mfa_enrollment_required')
    tick = matching_counter(decrypt(state.secret_ciphertext), code)
    if tick is not None:
        changed = db.session.execute(update(StaffMFA).where(StaffMFA.staff_id == actor.manv,
            StaffMFA.generation == state.generation, StaffMFA.enabled_at.isnot(None),
            StaffMFA.last_counter < tick).values(last_counter=tick).returning(StaffMFA.staff_id),
            execution_options={'synchronize_session': False}).scalar_one_or_none()
        if changed is not None:
            return state
    elif isinstance(code, str) and len(code) <= 32:
        raw = code.strip().replace('-', '').upper()
        if re.fullmatch('[0-9A-F]{16}', raw):
            changed = db.session.execute(update(StaffRecoveryCode).where(
                StaffRecoveryCode.code_hash == digest(f'recovery|{actor.manv}|{raw}'),
                StaffRecoveryCode.staff_id == actor.manv, StaffRecoveryCode.generation == state.generation,
                StaffRecoveryCode.used_at.is_(None)).values(used_at=now()).returning(StaffRecoveryCode.code_hash)).scalar_one_or_none()
            if changed is not None:
                audit(actor, 'recovery_code_used')
                return state
    raise SecurityError('Mã chưa đúng hoặc đã dùng. Chờ mã mới hoặc dùng mã dự phòng còn lại.', 400, 'code_invalid')


def verify(actor, data):
    state = prove(actor, data.get('code'))
    until = grant(actor, state)
    audit(actor, 'step_up_verified')
    return dict(success=True, verified_until=until.isoformat() + 'Z')


def disable(actor, data):
    password(actor, data)
    state = prove(actor, data.get('code'))
    db.session.execute(update(StaffMFA).where(StaffMFA.staff_id == actor.manv,
        StaffMFA.generation == state.generation).values(secret_ciphertext=None, enabled_at=None,
        pending_ciphertext=None, pending_expires_at=None, generation=StaffMFA.generation + 1, last_counter=-1))
    StaffStepUp.query.filter_by(staff_id=actor.manv).delete(synchronize_session=False)
    StaffRecoveryCode.query.filter_by(staff_id=actor.manv).delete(synchronize_session=False)
    audit(actor, 'mfa_disabled')


def regenerate(actor, data):
    password(actor, data)
    state = prove(actor, data.get('code'))
    # Serialize replacement with disable/re-enrollment on the same state row.
    changed = db.session.execute(update(StaffMFA).where(StaffMFA.staff_id == actor.manv,
        StaffMFA.generation == state.generation, StaffMFA.enabled_at.isnot(None)).values(
        generation=StaffMFA.generation + 1).returning(StaffMFA.staff_id),
        execution_options={'synchronize_session': False}).scalar_one_or_none()
    if changed is None:
        raise SecurityError('Bảo mật vừa thay đổi. Vui lòng tải lại trang.', 409)
    db.session.refresh(state)
    codes = new_recovery_codes(actor, state)
    grant(actor, state)
    audit(actor, 'recovery_codes_replaced')
    return dict(success=True, recovery_codes=codes)


def step_up_required(fn):
    """Place inside the existing role guard, before any business mutation/file upload."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if current_app.config.get('STAFF_SECURITY_ENABLED'):
            from ..decorators import get_current_user
            verify_jwt_in_request()
            actor, kind = get_current_user()
            if kind != 'staff' or not actor or not actor.trangthai:
                return jsonify(success=False, message='Cần tài khoản nhân viên đang hoạt động.'), 403
            blocked = require_elevation(actor)
            if blocked is not None:
                return blocked
        return fn(*args, **kwargs)
    return wrapped


def require_elevation(actor):
    state = state_for(actor)
    if not state or not state.enabled_at:
        return jsonify(success=False, code='mfa_enrollment_required',
            message='Mở Bảo mật tài khoản (/admin/security) để thiết lập xác thực hai bước trước thao tác này.'), 403
    if not elevated(actor, state):
        return jsonify(success=False, code='mfa_required',
            message='Vui lòng xác minh tại Bảo mật tài khoản (/admin/security) rồi thực hiện lại.'), 403
    return None

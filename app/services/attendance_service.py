"""GPS validation, append-only events, reviewable sessions and branch-scoped decisions."""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from flask import current_app
from sqlalchemy import select, or_
from ..extensions import db
from ..models import CaLam, NhanVien, nhanvien_calam
from ..operations_models import (Branch, BranchMembership, BranchGeoPolicy, AttendanceEvent,
    AttendanceSession, AttendanceAdjustment, AttendancePeriod, OperationsAudit)

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=7))
DEFAULT_POLICY = dict(latitude=10.78686228650495, longitude=106.5794979291708, radius_m=500,
    max_accuracy_m=150, max_age_seconds=30, checkin_early_minutes=30,
    checkout_late_minutes=120, unpaid_break_minutes=0, retention_days=90,
    enabled=False, payroll_model='hourly-approved-v1')


class OperationsError(ValueError):
    def __init__(self, message, status=400, code='invalid_request'):
        super().__init__(message)
        self.status, self.code = status, code


def now_utc():
    return datetime.now(UTC)


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value):
    return aware(value).isoformat() if value else None


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(UTC)
    except (ValueError, TypeError):
        raise OperationsError('Thời gian phải là ISO 8601 có múi giờ')


def integer(value, label, minimum=0, maximum=100000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise OperationsError(f'{label} phải là số nguyên từ {minimum} đến {maximum}')
    return value


def number(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise OperationsError(f'{label} không hợp lệ')
    return float(value)


def reason_text(value):
    if not isinstance(value, str) or not 3 <= len(value.strip()) <= 2000:
        raise OperationsError('Cần lý do từ 3 đến 2000 ký tự')
    return value.strip()


def require_enabled():
    if not current_app.config.get('ATTENDANCE_ENABLED'):
        raise OperationsError('Chấm công đang chờ kích hoạt', 503, 'feature_disabled')


def lock_branch(branch_id):
    # An UPDATE also serializes writes in SQLite. All operations use branch -> shift order.
    count = Branch.query.filter_by(id=branch_id).update({Branch.id: Branch.id}, synchronize_session=False)
    if not count:
        raise OperationsError('Không tìm thấy cơ sở', 404)
    return db.session.get(Branch, branch_id)


def allowed_branches(actor, manage=False):
    if simple_mode():
        if actor.role not in {'staff', 'letan', 'manager', 'admin'} or (manage and actor.role not in {'manager', 'admin'}):
            return []
        return [fixed_branch_id()]
    if actor.role == 'admin':
        return [b.id for b in Branch.query.all()]
    if manage and actor.role != 'manager':
        return []
    query = BranchMembership.query.filter_by(staff_id=actor.manv)
    if manage:
        query = query.filter_by(can_manage=True)
    return [m.branch_id for m in query.all()]


def simple_mode():
    return bool(current_app.config.get('ATTENDANCE_SIMPLE_MODE'))


def fixed_branch_id():
    branch_id = current_app.config.get('ATTENDANCE_BRANCH_ID')
    if type(branch_id) is not int or branch_id < 1:
        raise OperationsError('Chưa khởi tạo địa điểm chấm công cố định', 503)
    return branch_id


def default_branch_id():
    """Branch for a shift saved without one: the fixed point in simple mode, otherwise the spa's
    only active branch. With several branches there is no safe default (None)."""
    if simple_mode():
        return fixed_branch_id()
    ids = [row[0] for row in db.session.query(Branch.id).filter(Branch.active.is_(True)).limit(2)]
    return ids[0] if len(ids) == 1 else None


def shift_branch_id(shift):
    return shift.branch_id or default_branch_id()


def shifts_in_branches(query, branch_ids):
    condition = CaLam.branch_id.in_(branch_ids)
    default = default_branch_id()
    if default and default in branch_ids:
        condition = or_(condition, CaLam.branch_id.is_(None))
    return query.filter(condition)


def require_branch(actor, branch_id, manage=False):
    if branch_id not in allowed_branches(actor, manage):
        raise OperationsError('Bạn không có quyền tại cơ sở này', 403, 'branch_forbidden')


def policy_for(branch_id):
    return BranchGeoPolicy.query.filter_by(branch_id=branch_id).order_by(BranchGeoPolicy.version.desc()).first()


def audit(actor, branch_id, action, entity, before, after, reason):
    db.session.add(OperationsAudit(branch_id=branch_id, actor_id=actor.manv,
        action=action, entity_type=entity.__tablename__, entity_id=entity.id,
        before=before, after=after, reason=reason))


def validate_policy(data):
    if not isinstance(data, dict) or set(data) - set(DEFAULT_POLICY):
        raise OperationsError('Trường chính sách không hợp lệ')
    result = dict(DEFAULT_POLICY, **data)
    for name, low, high in [('latitude', -90, 90), ('longitude', -180, 180),
            ('radius_m', 1, 2000), ('max_accuracy_m', 1, 1000)]:
        result[name] = number(result[name], name, low, high)
    for name, low, high in [('max_age_seconds', 1, 120), ('checkin_early_minutes', 0, 180),
            ('checkout_late_minutes', 0, 720), ('unpaid_break_minutes', 0, 480), ('retention_days', 1, 365)]:
        result[name] = integer(result[name], name, low, high)
    if type(result['enabled']) is not bool or result['payroll_model'] != 'hourly-approved-v1':
        raise OperationsError('Chính sách chưa được hỗ trợ')
    return result


def save_policy(actor, branch_id, data, reason):
    if actor.role != 'admin':
        raise OperationsError('Chỉ admin được thay đổi chính sách', 403)
    if simple_mode() and branch_id == fixed_branch_id():
        if not isinstance(data, dict):
            raise OperationsError('Chính sách không hợp lệ')
        if any(data.get(key, DEFAULT_POLICY[key]) != DEFAULT_POLICY[key]
                for key in ('latitude', 'longitude', 'radius_m', 'max_accuracy_m')):
            raise OperationsError('Địa điểm chấm công cố định theo cấu hình của cơ sở')
    lock_branch(branch_id)
    previous = policy_for(branch_id)
    policy = BranchGeoPolicy(branch_id=branch_id, version=(previous.version + 1 if previous else 1),
        settings=validate_policy(data), created_by=actor.manv)
    db.session.add(policy)
    db.session.flush()
    audit(actor, branch_id, 'policy_created', policy,
        previous.settings if previous else None, policy.settings, reason_text(reason))
    return policy


def shift_bounds(shift):
    start = datetime.combine(shift.ngay, shift.giobatdau, LOCAL)
    end = datetime.combine(shift.ngay, shift.gioketthuc, LOCAL)
    if end <= start:
        end += timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)


def assigned_shift(actor, shift_id):
    integer(shift_id, 'Mã ca', 1, 2147483647)
    shift = db.session.get(CaLam, shift_id)
    assigned = db.session.execute(select(nhanvien_calam.c.manv).where(
        nhanvien_calam.c.manv == actor.manv, nhanvien_calam.c.maca == shift_id)).first()
    if not shift or (not simple_mode() and not assigned):
        raise OperationsError('Ca làm không được phân cho bạn', 403, 'shift_forbidden')
    branch_id = shift_branch_id(shift)
    if not branch_id:
        raise OperationsError('Ca làm chưa được gắn cơ sở', 409, 'branch_missing')
    require_branch(actor, branch_id)
    return shift


def ensure_unlocked(branch_id, work_date):
    period = AttendancePeriod.query.filter(AttendancePeriod.branch_id == branch_id,
        AttendancePeriod.from_date <= work_date, AttendancePeriod.to_date >= work_date,
        AttendancePeriod.status == 'LOCKED').first()
    if period:
        raise OperationsError('Kỳ công đã khóa; gửi điều chỉnh ở kỳ sau', 409, 'period_locked')


def haversine(lat, lon, branch_lat, branch_lon):
    p1, p2 = math.radians(lat), math.radians(branch_lat)
    a = math.sin(math.radians(branch_lat - lat) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(branch_lon - lon) / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(min(1, a)), math.sqrt(max(0, 1 - a)))


def session_data(session):
    staff = db.session.get(NhanVien, session.staff_id)
    return dict(id=session.id, staff_id=session.staff_id, staff_name=staff.hoten if staff else '',
        shift_id=session.shift_id, branch_id=session.branch_id, work_date=session.work_date.isoformat(),
        planned_start=iso(session.planned_start), planned_end=iso(session.planned_end),
        actual_start=iso(session.actual_start), actual_end=iso(session.actual_end),
        worked_minutes=session.worked_minutes, paid_minutes=session.paid_minutes,
        break_minutes=session.break_minutes, overtime_minutes=session.overtime_minutes,
        late_minutes=session.late_minutes, early_leave_minutes=session.early_leave_minutes,
        hourly_rate=str(session.hourly_rate), shift_multiplier=str(session.shift_multiplier),
        compensation=session.compensation, approval_status=session.approval_status,
        version=session.version, policy_id=session.policy_id)


def recompute(session):
    if session.actual_end is None:
        return
    elapsed = int((aware(session.actual_end) - aware(session.actual_start)).total_seconds() // 60)
    session.worked_minutes = max(0, elapsed - session.break_minutes)
    session.late_minutes = max(0, int((aware(session.actual_start) - aware(session.planned_start)).total_seconds() // 60))
    session.early_leave_minutes = max(0, int((aware(session.planned_end) - aware(session.actual_end)).total_seconds() // 60))


GPS_ERRORS = dict(outside_geofence='Bạn đang ngoài khu vực chấm công',
    inaccurate_location='Vị trí chưa đủ chính xác, vui lòng thử lại',
    stale_location='Vị trí đã cũ, vui lòng lấy lại GPS',
    outside_window='Chưa đến hoặc đã qua thời gian chấm công',
    not_checked_in='Bạn chưa chấm vào ca này', already_checked_in='Ca này đã chấm vào',
    already_checked_out='Ca này đã chấm ra', policy_disabled='Cơ sở chưa bật chấm công GPS',
    open_session='Bạn đang chấm vào một ca khác; hãy chấm ra ca đó trước')


def punch(actor, data, kind):
    require_enabled()
    fields = {'shift_assignment_id', 'latitude', 'longitude', 'accuracy', 'location_timestamp', 'idempotency_key'}
    if not isinstance(data, dict) or set(data) != fields:
        raise OperationsError('Cần mã ca, vị trí, sai số, thời gian GPS và khóa yêu cầu')
    key = data['idempotency_key']
    if not isinstance(key, str) or not 8 <= len(key) <= 100:
        raise OperationsError('Khóa yêu cầu cần 8–100 ký tự')
    shift_id = integer(data['shift_assignment_id'], 'Mã ca', 1, 2147483647)
    latitude = number(data['latitude'], 'Vĩ độ', -90, 90)
    longitude = number(data['longitude'], 'Kinh độ', -180, 180)
    accuracy = number(data['accuracy'], 'Sai số', 0, 100000)
    location_at = parse_time(data['location_timestamp'])
    digest = hashlib.sha256(json.dumps(dict(data, event_type=kind), sort_keys=True, allow_nan=False).encode()).hexdigest()
    # Staff row serializes retries even if a request is sent to a different branch.
    NhanVien.query.filter_by(manv=actor.manv).update({NhanVien.manv: NhanVien.manv}, synchronize_session=False)
    old = AttendanceEvent.query.filter_by(staff_id=actor.manv, request_key=key).first()
    if old:
        if old.payload_hash != digest:
            raise OperationsError('Khóa yêu cầu đã dùng cho nội dung khác', 409, 'idempotency_conflict')
        return old.response, old.http_status
    shift = assigned_shift(actor, shift_id)
    branch_id = shift_branch_id(shift)
    branch = lock_branch(branch_id)
    db.session.refresh(shift)
    ensure_unlocked(branch_id, shift.ngay)
    policy = policy_for(branch_id)
    if not policy:
        raise OperationsError('Chưa có chính sách GPS', 409)
    now, settings = now_utc(), policy.settings
    active_policy_id, branch_gps_enabled = policy.id, settings['enabled']
    recent = AttendanceEvent.query.filter(AttendanceEvent.staff_id == actor.manv,
        AttendanceEvent.server_at >= now - timedelta(minutes=1)).count()
    if recent >= 12:
        raise OperationsError('Bạn thao tác quá nhanh, thử lại sau một phút', 429, 'rate_limited')
    start, end = shift_bounds(shift)
    session = AttendanceSession.query.filter_by(staff_id=actor.manv, shift_id=shift_id).first()
    if session:
        start, end = aware(session.planned_start), aware(session.planned_end)
        policy = db.session.get(BranchGeoPolicy, session.policy_id)
        settings = policy.settings
    distance = haversine(latitude, longitude, settings['latitude'], settings['longitude'])
    failure = None
    if not branch.active or not branch_gps_enabled or not settings['enabled']:
        failure = 'policy_disabled'
    elif not start - timedelta(minutes=settings['checkin_early_minutes']) <= now <= end + timedelta(minutes=settings['checkout_late_minutes']):
        failure = 'outside_window'
    elif kind == 'check-in' and now >= end:
        failure = 'outside_window'
    elif (now - location_at).total_seconds() > settings['max_age_seconds'] or (location_at - now).total_seconds() > 5:
        failure = 'stale_location'
    elif accuracy > settings['max_accuracy_m']:
        failure = 'inaccurate_location'
    elif distance > settings['radius_m']:
        failure = 'outside_geofence'
    elif kind == 'check-in' and session:
        failure = 'already_checked_in'
    elif kind == 'check-in' and simple_mode() and AttendanceSession.query.filter_by(
            staff_id=actor.manv, actual_end=None).first():
        failure = 'open_session'
    elif kind == 'check-out' and not session:
        failure = 'not_checked_in'
    elif kind == 'check-out' and session.actual_end:
        failure = 'already_checked_out'
    elif kind == 'check-out' and now < aware(session.actual_start):
        failure = 'outside_window'
    event = AttendanceEvent(staff_id=actor.manv, shift_id=shift_id, branch_id=branch_id,
        event_type=kind, server_at=now, latitude=latitude, longitude=longitude, accuracy=accuracy,
        distance=round(distance, 2), verdict='rejected' if failure else 'accepted',
        reason=failure or 'ok', request_key=key, payload_hash=digest, policy_id=policy.id,
        response={}, http_status=409 if failure else 200)
    db.session.add(event)
    db.session.flush()
    if not failure:
        if kind == 'check-in':
            session = AttendanceSession(staff_id=actor.manv, shift_id=shift_id, branch_id=branch_id,
                work_date=shift.ngay, planned_start=start, planned_end=end, actual_start=now,
                checkin_event_id=event.id, policy_id=policy.id,
                hourly_rate=Decimal(actor.chucvu.dongiagio), shift_multiplier=Decimal(shift.hesoluong or 1),
                break_minutes=settings['unpaid_break_minutes'], approval_status='OPEN')
            db.session.add(session)
        else:
            session.actual_end, session.checkout_event_id, session.approval_status = now, event.id, 'SUBMITTED'
            recompute(session)
        db.session.flush()
    message = GPS_ERRORS.get(failure, 'Đã chấm vào' if kind == 'check-in' else 'Đã chấm ra, chờ duyệt công')
    if failure == 'inaccurate_location':
        message = (f"Sai số định vị {accuracy:.0f} m, vượt giới hạn {settings['max_accuracy_m']:.0f} m. "
            'Hãy lấy lại vị trí hoặc gửi yêu cầu cho quản lý.')
    response = dict(success=not failure, code=failure or 'ok', message=message,
        server_at=iso(now), distance_m=round(distance, 2), event_id=event.id,
        policy_id=policy.id, active_policy_id=active_policy_id,
        session=session_data(session) if session else None)
    event.response = response
    return response, event.http_status


def approve_session(actor, session, data):
    require_branch(actor, session.branch_id, True)
    if actor.manv == session.staff_id:
        raise OperationsError('Không được tự duyệt công của mình', 403)
    lock_branch(session.branch_id)
    db.session.refresh(session)
    ensure_unlocked(session.branch_id, session.work_date)
    integer(data.get('version'), 'Phiên bản', 1)
    if data['version'] != session.version:
        raise OperationsError('Bản công đã thay đổi, vui lòng tải lại', 409, 'stale_version')
    if session.approval_status not in {'SUBMITTED', 'APPROVED', 'REJECTED'} or not session.actual_end:
        raise OperationsError('Phiên công chưa kết thúc hoặc đã khóa', 409)
    reason = reason_text(data.get('reason'))
    before = session_data(session)
    decision = data.get('decision', 'approve')
    if decision not in {'approve', 'reject'}:
        raise OperationsError('Quyết định không hợp lệ')
    if decision == 'approve':
        session.paid_minutes = integer(data.get('paid_minutes'), 'Phút công được trả', 0, 1440)
        session.overtime_minutes = integer(data.get('overtime_minutes', 0), 'Phút tăng ca', 0, 720)
        session.break_minutes = integer(data.get('break_minutes', session.break_minutes), 'Phút nghỉ không lương', 0, 480)
        night = integer(data.get('night_minutes', 0), 'Phút công đêm', 0, session.paid_minutes)
        night_ot = integer(data.get('night_overtime_minutes', 0), 'Phút tăng ca đêm', 0, session.overtime_minutes)
        day_kind = data.get('day_kind', 'weekday')
        if day_kind not in {'weekday', 'rest_day', 'holiday'}:
            raise OperationsError('Loại ngày không hợp lệ')
        if session.paid_minutes + session.overtime_minutes > 1440:
            raise OperationsError('Tổng công không vượt quá 24 giờ mỗi phiên')
        daytime_overtime = data.get('daytime_overtime', False)
        if type(daytime_overtime) is not bool:
            raise OperationsError('Trạng thái tăng ca ban ngày phải là boolean')
        session.compensation = dict(day_kind=day_kind, night_minutes=night,
            night_overtime_minutes=night_ot, daytime_overtime=daytime_overtime or session.overtime_minutes > night_ot)
        recompute(session)
        session.approval_status = 'APPROVED'
    else:
        session.approval_status = 'REJECTED'
        session.paid_minutes = session.overtime_minutes = 0
    session.approved_by, session.approved_at = actor.manv, now_utc()
    db.session.flush()
    audit(actor, session.branch_id, 'attendance_' + decision, session, before, session_data(session), reason)
    return session


def request_adjustment(actor, data):
    NhanVien.query.filter_by(manv=actor.manv).update({NhanVien.manv: NhanVien.manv}, synchronize_session=False)
    shift = assigned_shift(actor, data.get('shift_assignment_id'))
    branch_id = shift_branch_id(shift)
    lock_branch(branch_id)
    ensure_unlocked(branch_id, shift.ngay)
    kind = data.get('request_kind', 'correction')
    if kind not in {'correction', 'check-in', 'check-out'}:
        raise OperationsError('Loại yêu cầu không hợp lệ')
    session = AttendanceSession.query.filter_by(staff_id=actor.manv, shift_id=shift.maca).first()
    if kind == 'check-in':
        if session:
            raise OperationsError('Ca đã chấm vào; hãy gửi yêu cầu chỉnh công', 409)
        start, end = parse_time(data.get('proposed_start')), None
        if start > now_utc() + timedelta(seconds=5):
            raise OperationsError('Giờ vào đề nghị không được nằm trong tương lai')
    elif kind == 'check-out':
        if not session or session.actual_end:
            raise OperationsError('Cần ca đã chấm vào và chưa chấm ra', 409)
        start, end = aware(session.actual_start), parse_time(data.get('proposed_end'))
        if end > now_utc() + timedelta(seconds=5):
            raise OperationsError('Giờ ra đề nghị không được nằm trong tương lai')
    else:
        start, end = parse_time(data.get('proposed_start')), parse_time(data.get('proposed_end'))
    planned_start, planned_end = shift_bounds(shift)
    if (end is not None and not start < end <= start + timedelta(hours=24)) or start < planned_start - timedelta(hours=12) or (end or start) > planned_end + timedelta(hours=12):
        raise OperationsError('Khoảng thời gian đề nghị không phù hợp ca')
    if AttendanceAdjustment.query.filter_by(staff_id=actor.manv, shift_id=shift.maca, status='PENDING').first():
        raise OperationsError('Ca này đang có yêu cầu chỉnh công chờ duyệt', 409)
    request = AttendanceAdjustment(staff_id=actor.manv, shift_id=shift.maca, branch_id=branch_id,
        session_id=session.id if session else None, session_version=session.version if session else None,
        proposed_start=start, proposed_end=end, request_kind=kind, reason=reason_text(data.get('reason')))
    db.session.add(request)
    db.session.flush()
    audit(actor, branch_id, 'adjustment_requested', request, None, adjustment_data(request), request.reason)
    return request


def adjustment_data(item):
    staff = db.session.get(NhanVien, item.staff_id)
    return dict(id=item.id, session_id=item.session_id, staff_id=item.staff_id,
        staff_name=staff.hoten if staff else '', shift_id=item.shift_id, branch_id=item.branch_id,
        proposed_start=iso(item.proposed_start), proposed_end=iso(item.proposed_end),
        request_kind=item.request_kind,
        reason=item.reason, status=item.status, decision_reason=item.decision_reason,
        created_at=iso(item.created_at))


def decide_adjustment(actor, item, data):
    require_branch(actor, item.branch_id, True)
    if actor.manv == item.staff_id:
        raise OperationsError('Không được tự duyệt điều chỉnh công', 403)
    NhanVien.query.filter_by(manv=item.staff_id).update({NhanVien.manv: NhanVien.manv}, synchronize_session=False)
    lock_branch(item.branch_id)
    db.session.refresh(item)
    shift = db.session.get(CaLam, item.shift_id)
    ensure_unlocked(item.branch_id, shift.ngay)
    if item.status != 'PENDING':
        raise OperationsError('Yêu cầu đã được xử lý', 409)
    decision, reason = data.get('decision'), reason_text(data.get('reason'))
    if decision not in {'approve', 'reject'}:
        raise OperationsError('Quyết định không hợp lệ')
    session = AttendanceSession.query.filter_by(staff_id=item.staff_id, shift_id=item.shift_id).first()
    if decision == 'approve':
        if (session.version if session else None) != item.session_version:
            raise OperationsError('Phiên công đã thay đổi từ khi gửi yêu cầu; cần gửi lại', 409)
        if item.request_kind == 'check-in' and simple_mode() and AttendanceSession.query.filter_by(
                staff_id=item.staff_id, actual_end=None).first():
            raise OperationsError(GPS_ERRORS['open_session'], 409, 'open_session')
        if not session:
            staff = db.session.get(NhanVien, item.staff_id)
            start, end = shift_bounds(shift)
            policy = policy_for(item.branch_id)
            if not policy:
                raise OperationsError('Chưa có chính sách cơ sở', 409)
            session = AttendanceSession(staff_id=item.staff_id, shift_id=item.shift_id, branch_id=item.branch_id,
                work_date=shift.ngay, planned_start=start, planned_end=end, policy_id=policy.id,
                actual_start=item.proposed_start, hourly_rate=staff.chucvu.dongiagio,
                shift_multiplier=shift.hesoluong or 1, break_minutes=policy.settings['unpaid_break_minutes'])
            db.session.add(session)
        before = session_data(session) if session.id else None
        session.actual_start, session.actual_end = item.proposed_start, item.proposed_end
        session.approval_status, session.paid_minutes, session.overtime_minutes = ('OPEN' if item.request_kind == 'check-in' else 'SUBMITTED'), 0, 0
        session.approved_by, session.approved_at = None, None
        recompute(session)
        db.session.flush()
        item.session_id = session.id
        audit(actor, item.branch_id, 'attendance_corrected', session, before, session_data(session), reason)
    item.status = 'APPROVED' if decision == 'approve' else 'REJECTED'
    item.decision_by, item.decision_at, item.decision_reason = actor.manv, now_utc(), reason
    db.session.flush()
    audit(actor, item.branch_id, 'adjustment_' + decision, item, None, adjustment_data(item), reason)
    return item


def shift_data(actor, shift):
    start, end = shift_bounds(shift)
    branch_id = shift_branch_id(shift)
    branch = db.session.get(Branch, branch_id) if branch_id else None
    policy = policy_for(branch_id) if branch_id else None
    session = AttendanceSession.query.filter_by(staff_id=actor.manv, shift_id=shift.maca).first()
    settings = policy.settings if policy else {}
    return dict(shift_assignment_id=shift.maca, shift_id=shift.maca, branch_id=branch_id,
        branch_name=branch.name if branch else 'Chưa gắn cơ sở', start_at=iso(start), end_at=iso(end),
        attendance=session_data(session) if session else None,
        gps_enabled=bool(current_app.config.get('ATTENDANCE_ENABLED') and settings.get('enabled') and branch and branch.active),
        radius_m=settings.get('radius_m'), max_accuracy_m=settings.get('max_accuracy_m'),
        retention_days=settings.get('retention_days'),
        checkin_opens_at=iso(start - timedelta(minutes=settings.get('checkin_early_minutes', 30))),
        checkout_closes_at=iso(end + timedelta(minutes=settings.get('checkout_late_minutes', 120))))


def protect_shift(shift, actor):
    branch_id = shift_branch_id(shift)
    if branch_id:
        require_branch(actor, branch_id, True)
        lock_branch(branch_id)
        ensure_unlocked(branch_id, shift.ngay)
    elif actor.role != 'admin' and current_app.config.get('ATTENDANCE_ENABLED'):
        raise OperationsError('Ca chưa có cơ sở, cần admin xử lý', 403)
    if AttendanceSession.query.filter_by(shift_id=shift.maca).first() or AttendanceEvent.query.filter_by(shift_id=shift.maca).first() or AttendanceAdjustment.query.filter_by(shift_id=shift.maca).first():
        raise OperationsError('Ca đã có nhật ký công; dùng yêu cầu chỉnh công thay vì sửa/xóa ca', 409)


def record_exception(actor, data):
    """Resolve an absent punch explicitly; never invent a successful GPS event."""
    staff_id = integer(data.get('staff_id'), 'Mã nhân viên', 1)
    staff = db.session.get(NhanVien, staff_id)
    if not staff:
        raise OperationsError('Không tìm thấy nhân viên', 404)
    shift = assigned_shift(staff, data.get('shift_assignment_id'))
    branch_id = shift_branch_id(shift)
    require_branch(actor, branch_id, True)
    if actor.manv == staff_id:
        raise OperationsError('Không được tự xử lý ngoại lệ công của mình', 403)
    lock_branch(branch_id)
    ensure_unlocked(branch_id, shift.ngay)
    if AttendanceSession.query.filter_by(staff_id=staff_id, shift_id=shift.maca).first():
        raise OperationsError('Ca đã có phiên công; dùng yêu cầu chỉnh công', 409)
    reason = reason_text(data.get('reason'))
    start, end = shift_bounds(shift)
    policy = policy_for(branch_id)
    if not policy:
        raise OperationsError('Cơ sở chưa có chính sách', 409)
    decision = data.get('decision')
    if decision not in {'absence', 'manual'}:
        raise OperationsError('Chọn vắng mặt hoặc nhập giờ thực tế')
    if now_utc() < end:
        raise OperationsError('Chỉ xử lý ca thiếu công sau khi ca kết thúc', 409)
    if decision == 'manual':
        actual_start, actual_end = parse_time(data.get('actual_start')), parse_time(data.get('actual_end'))
        if not actual_start < actual_end <= actual_start + timedelta(hours=24) or actual_start < start - timedelta(hours=12) or actual_end > end + timedelta(hours=12):
            raise OperationsError('Giờ thực tế không phù hợp ca')
    else:
        actual_start = actual_end = start
    session = AttendanceSession(staff_id=staff_id, shift_id=shift.maca, branch_id=branch_id,
        work_date=shift.ngay, planned_start=start, planned_end=end, actual_start=actual_start,
        actual_end=actual_end, policy_id=policy.id, break_minutes=0 if decision == 'absence' else policy.settings['unpaid_break_minutes'],
        hourly_rate=staff.chucvu.dongiagio, shift_multiplier=shift.hesoluong or 1,
        approval_status='REJECTED' if decision == 'absence' else 'SUBMITTED',
        approved_by=actor.manv if decision == 'absence' else None,
        approved_at=now_utc() if decision == 'absence' else None)
    recompute(session)
    db.session.add(session)
    db.session.flush()
    audit(actor, branch_id, 'attendance_exception_' + decision, session, None, session_data(session), reason)
    return session

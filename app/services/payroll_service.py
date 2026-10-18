"""Reviewed minutes -> frozen payroll; commission reversals go to the next period."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from flask import current_app
from sqlalchemy import and_, or_, false

from ..extensions import db
from ..models import CaLam, NhanVien, CommissionEntry, nhanvien_calam, Luong
from ..operations_models import (AttendanceSession, AttendanceAdjustment, AttendancePeriod,
    PayrollPeriod, PayrollLine, PayrollAdjustment, PayrollCommissionClaim, PayrollCommissionDelta,
    BranchMembership, Branch)
from . import attendance_service as att, commission_service


def money(value):
    try:
        number = Decimal(str(value))
    except Exception:
        raise att.OperationsError('Số tiền không hợp lệ')
    if not number.is_finite() or abs(number) > 1000000000:
        raise att.OperationsError('Số tiền phải hữu hạn và không quá 1 tỷ đồng')
    return number.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise att.OperationsError('Ngày phải theo YYYY-MM-DD')


def period_data(period):
    return dict(id=period.id, branch_id=period.branch_id, from_date=period.from_date.isoformat(),
        to_date=period.to_date.isoformat(), status=period.status,
        locked_at=att.iso(period.locked_at), **({'version': period.version,
        'policy_snapshot': period.policy_snapshot} if isinstance(period, PayrollPeriod) else {}))


def line_data(line, include_snapshot=True):
    staff = db.session.get(NhanVien, line.staff_id)
    period = db.session.get(PayrollPeriod, line.period_id)
    result = dict(id=line.id, staff_id=line.staff_id, staff_name=staff.hoten if staff else '',
        period_id=line.period_id, from_date=period.from_date.isoformat(), to_date=period.to_date.isoformat(),
        status=period.status, paid_minutes=line.paid_minutes,
        **{key: str(getattr(line, key)) for key in ('base', 'overtime', 'commission', 'allowance', 'deduction', 'net')})
    if include_snapshot:
        result['source_snapshot'] = line.source_snapshot
    return result


def legacy_salary_query(actor):
    query = Luong.query.filter_by(manv=actor.manv)
    if current_app.config.get('PAYROLL_V2_ENABLED'):
        cutover = current_app.config.get('PAYROLL_V2_CUTOVER_DATE')
        if not cutover:
            return query.filter(false())
        date = parse_date(cutover)
        # Exclude the entire overlapping month; its aggregate cannot safely be split.
        query = query.filter(or_(Luong.nam < date.year,
            and_(Luong.nam == date.year, Luong.thang < date.month)))
    return query.order_by(Luong.nam.desc(), Luong.thang.desc())


def create_attendance_period(actor, data):
    branch_id = att.integer(data.get('branch_id'), 'Mã cơ sở', 1)
    att.require_branch(actor, branch_id, True)
    att.lock_branch(branch_id)
    start, end = parse_date(data.get('from_date')), parse_date(data.get('to_date'))
    if end < start or (end - start).days > 62:
        raise att.OperationsError('Kỳ công phải từ 1 đến 63 ngày')
    overlaps = AttendancePeriod.query.filter(AttendancePeriod.branch_id == branch_id,
        AttendancePeriod.from_date <= end, AttendancePeriod.to_date >= start).first()
    if overlaps:
        if overlaps.from_date == start and overlaps.to_date == end:
            return overlaps
        raise att.OperationsError('Kỳ công trùng với kỳ đã có', 409)
    period = AttendancePeriod(branch_id=branch_id, from_date=start, to_date=end)
    db.session.add(period)
    db.session.flush()
    att.audit(actor, branch_id, 'attendance_period_created', period, None, period_data(period), 'Tạo kỳ công')
    return period


def attendance_readiness(actor, period):
    att.require_branch(actor, period.branch_id, True)
    sessions = AttendanceSession.query.filter(AttendanceSession.branch_id == period.branch_id,
        AttendanceSession.work_date.between(period.from_date, period.to_date)).all()
    missing = 0
    if not att.simple_mode():
        shifts = att.shifts_in_branches(CaLam.query, [period.branch_id]).filter(
            CaLam.ngay.between(period.from_date, period.to_date)).all()
        expected = {(staff.manv, shift.maca) for shift in shifts for staff in shift.nhanvien}
        resolved = {(session.staff_id, session.shift_id) for session in sessions}
        missing = len(expected - resolved)
    pending = AttendanceAdjustment.query.join(CaLam, AttendanceAdjustment.shift_id == CaLam.maca).filter(
        AttendanceAdjustment.branch_id == period.branch_id, AttendanceAdjustment.status == 'PENDING',
        CaLam.ngay.between(period.from_date, period.to_date)).count()
    opened = sum(session.approval_status == 'OPEN' for session in sessions)
    submitted = sum(session.approval_status == 'SUBMITTED' for session in sessions)
    own = any(session.staff_id == actor.manv for session in sessions)
    ended = period.to_date < att.now_utc().astimezone(att.LOCAL).date()
    return dict(sessions=len(sessions), open=opened, submitted=submitted,
        approved=sum(session.approval_status in {'APPROVED', 'LOCKED'} for session in sessions),
        rejected=sum(session.approval_status == 'REJECTED' for session in sessions),
        missing=missing, pending_requests=pending, ended=ended, requires_other_manager=own,
        can_lock=ended and not (opened or submitted or missing or pending or own))


def lock_attendance_period(actor, period, reason):
    att.require_branch(actor, period.branch_id, True)
    att.lock_branch(period.branch_id)
    db.session.refresh(period)
    if period.status == 'LOCKED':
        return period
    readiness = attendance_readiness(actor, period)
    if not readiness['ended']:
        raise att.OperationsError('Chỉ khóa kỳ công sau ngày kết thúc', 409)
    sessions = AttendanceSession.query.filter(AttendanceSession.branch_id == period.branch_id,
        AttendanceSession.work_date.between(period.from_date, period.to_date)).all()
    if readiness['open'] or readiness['submitted'] or readiness['missing']:
        raise att.OperationsError(f"Còn {readiness['open']} phiên chưa chấm ra, {readiness['submitted']} phiên chờ duyệt công, "
            f"{readiness['missing']} ca thiếu công. Mở Bảng công để xử lý trước khi khóa", 409, 'unresolved_attendance')
    if readiness['pending_requests']:
        raise att.OperationsError(f"Còn {readiness['pending_requests']} yêu cầu chấm công chưa xử lý", 409)
    if readiness['requires_other_manager']:
        raise att.OperationsError('Kỳ chứa công của bạn; cần quản lý khác khóa', 403)
    before = period_data(period)
    for session in sessions:
        if session.approval_status == 'APPROVED':
            session.approval_status = 'LOCKED'
    period.status, period.locked_by, period.locked_at = 'LOCKED', actor.manv, att.now_utc()
    db.session.flush()
    att.audit(actor, period.branch_id, 'attendance_period_locked', period, before, period_data(period), att.reason_text(reason))
    return period


def income_summary(actor, start, end):
    if end < start:
        raise att.OperationsError('Ngày kết thúc phải từ ngày bắt đầu trở đi')
    sessions = AttendanceSession.query.filter(AttendanceSession.staff_id == actor.manv,
        AttendanceSession.work_date.between(start, end)).all()
    completed = [session for session in sessions if session.actual_end is not None]
    pending = [session for session in completed if session.approval_status == 'SUBMITTED']
    approved = [session for session in completed if session.approval_status in {'APPROVED', 'LOCKED'}]
    pending_estimate = sum((Decimal(session.worked_minutes) / 60 * session.hourly_rate * session.shift_multiplier
        for session in pending), Decimal(0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    approved_earnings = sum((sum(amounts(session)) for session in approved), Decimal(0))
    return dict(from_date=start.isoformat(), to_date=end.isoformat(),
        worked_minutes=sum(session.worked_minutes for session in completed),
        pending_minutes=sum(session.worked_minutes for session in pending),
        approved_minutes=sum(session.paid_minutes for session in approved),
        approved_overtime_minutes=sum(session.overtime_minutes for session in approved),
        pending_sessions=len(pending), open_sessions=sum(session.actual_end is None for session in sessions),
        pending_estimate=str(pending_estimate), approved_earnings=str(approved_earnings))


def amounts(session):
    """Vietnam weekday/rest/holiday overtime and separately reviewed night minutes.

    These are wage components before tax/insurance, not an automated HR compliance decision.
    Regular hours on holidays are reviewed through shift_multiplier (no holiday calendar inferred).
    """
    rate = Decimal(session.hourly_rate) / 60
    compensation = session.compensation or {}
    multiplier = {'weekday': Decimal('1.5'), 'rest_day': Decimal('2'), 'holiday': Decimal('3')}[compensation.get('day_kind', 'weekday')]
    night = compensation.get('night_minutes', 0)
    night_ot = compensation.get('night_overtime_minutes', 0)
    daytime = multiplier if compensation.get('day_kind', 'weekday') != 'weekday' or compensation.get('daytime_overtime') else Decimal('1')
    night_ot_multiplier = multiplier + Decimal('.3') + Decimal('.2') * daytime
    base = rate * Decimal(session.paid_minutes) * session.shift_multiplier + rate * night * Decimal('.3')
    overtime = rate * (Decimal(session.overtime_minutes - night_ot) * multiplier + Decimal(night_ot) * night_ot_multiplier)
    return money(base), money(overtime)


def build_payroll(actor, attendance_period):
    att.require_branch(actor, attendance_period.branch_id, True)
    att.lock_branch(attendance_period.branch_id)
    db.session.refresh(attendance_period)
    if attendance_period.status != 'LOCKED':
        raise att.OperationsError('Phải khóa kỳ công trước khi tạo bảng lương', 409)
    cutover = current_app.config.get('PAYROLL_V2_CUTOVER_DATE')
    if not cutover or attendance_period.from_date < parse_date(cutover):
        raise att.OperationsError('Cần ngày chuyển bảng lương mới; kỳ phải bắt đầu sau phần đã trả bằng hệ thống cũ', 409, 'cutover_required')
    existing = PayrollPeriod.query.filter_by(attendance_period_id=attendance_period.id).first()
    if existing:
        return existing
    sessions = AttendanceSession.query.filter(AttendanceSession.branch_id == attendance_period.branch_id,
        AttendanceSession.work_date.between(attendance_period.from_date, attendance_period.to_date),
        AttendanceSession.approval_status == 'LOCKED').all()
    grouped = defaultdict(list)
    for session in sessions:
        grouped[session.staff_id].append(session)
    member_ids = [m.staff_id for m in BranchMembership.query.filter_by(branch_id=attendance_period.branch_id).all()]
    if att.simple_mode():
        member_ids = [staff.manv for staff in NhanVien.query.filter(
            NhanVien.role.in_(['staff', 'letan', 'manager', 'admin'])).all()]
    start = datetime.combine(attendance_period.from_date, datetime.min.time())
    end = datetime.combine(attendance_period.to_date + timedelta(days=1), datetime.min.time())
    # Legacy commission timestamps are local Saigon. Claims serialize on the original row.
    entries = CommissionEntry.query.filter(CommissionEntry.manv.in_(member_ids),
        CommissionEntry.earned_at >= start, CommissionEntry.earned_at < end,
        CommissionEntry.status == 'active').order_by(CommissionEntry.id).all()
    commission_rows = defaultdict(list)
    deltas = defaultdict(list)
    for entry in entries:
        CommissionEntry.query.filter_by(id=entry.id).update({CommissionEntry.id: CommissionEntry.id}, synchronize_session=False)
        if db.session.get(PayrollCommissionClaim, entry.id):
            continue
        memberships = BranchMembership.query.filter_by(staff_id=entry.manv).all()
        if not att.simple_mode() and len(memberships) != 1:
            raise att.OperationsError('Hoa hồng nhân viên nhiều cơ sở chưa có phân bổ; cần đối soát riêng', 409, 'commission_branch_ambiguous')
        commission_rows[entry.manv].append(entry)
    # Reconcile previously paid commissions even if the source earned in an earlier month.
    claims = PayrollCommissionClaim.query.filter_by(branch_id=attendance_period.branch_id).order_by(PayrollCommissionClaim.commission_id).all()
    for claim in claims:
        entry = db.session.get(CommissionEntry, claim.commission_id)
        CommissionEntry.query.filter_by(id=entry.id).update({CommissionEntry.id: CommissionEntry.id}, synchronize_session=False)
        db.session.refresh(entry)
        old_line = db.session.get(PayrollLine, claim.line_id)
        old_period = db.session.get(PayrollPeriod, old_line.period_id)
        value = money(entry.amount) if entry.status == 'active' else Decimal(0)
        delta = value - claim.settled_amount
        if delta:
            if old_period.status != 'LOCKED':
                raise att.OperationsError('Hoa hồng thay đổi trong bảng lương chưa khóa; cần đối soát bản nháp trước', 409)
            deltas[entry.manv].append((claim, entry, delta))
    period = PayrollPeriod(attendance_period_id=attendance_period.id, branch_id=attendance_period.branch_id,
        from_date=attendance_period.from_date, to_date=attendance_period.to_date, created_by=actor.manv,
        policy_snapshot=dict(model='hourly-approved-v1', currency='VND', amount_type='before_tax_insurance',
            overtime_rates=dict(weekday='1.5', rest_day='2', holiday='3'), night_premium='.3', night_overtime_extra='.2'))
    db.session.add(period)
    db.session.flush()
    for staff_id in sorted(set(grouped) | set(commission_rows) | set(deltas)):
        rows = grouped[staff_id]
        base = sum((amounts(s)[0] for s in rows), Decimal(0))
        overtime = sum((amounts(s)[1] for s in rows), Decimal(0))
        commissions = commission_rows[staff_id]
        adjustments = deltas[staff_id]
        total_commission = sum((e.amount for e in commissions), Decimal(0)) + sum((d for _, _, d in adjustments), Decimal(0))
        staff = db.session.get(NhanVien, staff_id)
        line = PayrollLine(period_id=period.id, staff_id=staff_id, paid_minutes=sum(s.paid_minutes for s in rows),
            base=base, overtime=overtime, commission=total_commission, allowance=0, deduction=0,
            net=base + overtime + total_commission,
            source_snapshot=dict(staff_name=staff.hoten, attendance=[att.session_data(s) for s in rows],
                commissions=[commission_service.serialize(e) for e in commissions],
                commission_deltas=[dict(commission_id=e.id, source_status=e.status, amount=str(d),
                    revision=c.revision + 1) for c, e, d in adjustments]))
        db.session.add(line)
        db.session.flush()
        for entry in commissions:
            db.session.add(PayrollCommissionClaim(commission_id=entry.id, line_id=line.id,
                branch_id=period.branch_id, settled_amount=entry.amount, revision=1))
        for claim, entry, delta in adjustments:
            claim.revision += 1
            claim.settled_amount += delta
            db.session.add(PayrollCommissionDelta(commission_id=entry.id, line_id=line.id,
                revision=claim.revision, amount=delta))
    db.session.flush()
    att.audit(actor, period.branch_id, 'payroll_created', period, None, period_data(period), 'Chụp bản công và hoa hồng')
    return period


def adjust_line(actor, line, data):
    period = db.session.get(PayrollPeriod, line.period_id)
    att.require_branch(actor, period.branch_id, True)
    att.lock_branch(period.branch_id)
    db.session.refresh(period)
    db.session.refresh(line)
    if period.status != 'DRAFT':
        raise att.OperationsError('Bảng lương đã duyệt/khóa; điều chỉnh ở kỳ sau', 409)
    if line.staff_id == actor.manv:
        raise att.OperationsError('Không được tự điều chỉnh lương của mình', 403)
    if data.get('version') != period.version:
        raise att.OperationsError('Bảng lương đã thay đổi, vui lòng tải lại', 409)
    allowance = money(data.get('allowance_delta', 0))
    deduction = money(data.get('deduction_delta', 0))
    reason = att.reason_text(data.get('reason'))
    if line.allowance + allowance < 0 or line.deduction + deduction < 0:
        raise att.OperationsError('Phụ cấp/khấu trừ không được âm')
    before = line_data(line, False)
    line.allowance += allowance
    line.deduction += deduction
    line.net = line.base + line.overtime + line.commission + line.allowance - line.deduction
    db.session.add(PayrollAdjustment(line_id=line.id, actor_id=actor.manv,
        allowance_delta=allowance, deduction_delta=deduction, reason=reason))
    period.version += 1
    db.session.flush()
    att.audit(actor, period.branch_id, 'payroll_adjusted', line, before, line_data(line, False), reason)
    return line


def transition(actor, period, data, action):
    att.require_branch(actor, period.branch_id, True)
    att.lock_branch(period.branch_id)
    db.session.refresh(period)
    if data.get('version') != period.version:
        raise att.OperationsError('Bảng lương đã thay đổi, vui lòng tải lại', 409)
    expected = 'DRAFT' if action == 'approve' else 'APPROVED'
    if period.status != expected:
        raise att.OperationsError('Trạng thái kỳ lương không phù hợp', 409)
    lines = PayrollLine.query.filter_by(period_id=period.id).all()
    if action == 'approve' and commission_warnings(period):
        raise att.OperationsError('Hoa hồng nguồn đã thay đổi; đối soát lại bản nháp trước khi duyệt', 409, 'commission_changed')
    if any(line.staff_id == actor.manv for line in lines):
        raise att.OperationsError('Kỳ chứa lương của bạn; cần người khác duyệt', 403)
    if action == 'approve' and period.created_by == actor.manv:
        raise att.OperationsError('Cần người khác kiểm tra và duyệt bảng lương đã tạo', 403)
    before = period_data(period)
    period.status = 'APPROVED' if action == 'approve' else 'LOCKED'
    if action == 'approve':
        period.approved_by = actor.manv
    else:
        period.locked_at = att.now_utc()
    db.session.flush()
    att.audit(actor, period.branch_id, 'payroll_' + action, period, before, period_data(period), att.reason_text(data.get('reason')))
    return period


def commission_warnings(period):
    line_ids = [line.id for line in PayrollLine.query.filter_by(period_id=period.id)]
    ids = {claim.commission_id for claim in PayrollCommissionClaim.query.filter(PayrollCommissionClaim.line_id.in_(line_ids))}
    ids.update(delta.commission_id for delta in PayrollCommissionDelta.query.filter(PayrollCommissionDelta.line_id.in_(line_ids)))
    result = []
    for source_id in sorted(ids):
        entry = db.session.get(CommissionEntry, source_id)
        claim = db.session.get(PayrollCommissionClaim, source_id)
        current = money(entry.amount) if entry.status == 'active' else Decimal(0)
        if current != claim.settled_amount:
            result.append(dict(commission_id=source_id, staff_id=entry.manv,
                snapshot_amount=str(claim.settled_amount), current_amount=str(current)))
    return result


def reconcile_draft(actor, period, data):
    att.require_branch(actor, period.branch_id, True)
    att.lock_branch(period.branch_id)
    db.session.refresh(period)
    if period.status != 'DRAFT' or data.get('version') != period.version:
        raise att.OperationsError('Chỉ đối soát bản nháp hiện tại; vui lòng tải lại', 409)
    reason = att.reason_text(data.get('reason'))
    changes = commission_warnings(period)
    for change in changes:
        entry = db.session.get(CommissionEntry, change['commission_id'])
        CommissionEntry.query.filter_by(id=entry.id).update({CommissionEntry.id: CommissionEntry.id}, synchronize_session=False)
        db.session.refresh(entry)
        claim = db.session.get(PayrollCommissionClaim, entry.id)
        current = money(entry.amount) if entry.status == 'active' else Decimal(0)
        delta = current - claim.settled_amount
        if not delta:
            continue
        line = PayrollLine.query.filter_by(period_id=period.id, staff_id=entry.manv).first()
        before = line_data(line, False)
        claim.revision += 1
        claim.settled_amount = current
        line.commission += delta
        line.net += delta
        line.source_snapshot = dict(line.source_snapshot, commission_deltas=[
            *line.source_snapshot['commission_deltas'], dict(commission_id=entry.id, source_status=entry.status,
                amount=str(delta), revision=claim.revision)])
        db.session.add(PayrollCommissionDelta(commission_id=entry.id, line_id=line.id, revision=claim.revision, amount=delta))
        att.audit(actor, period.branch_id, 'payroll_commission_reconciled', line, before, line_data(line, False), reason)
    if changes:
        period.version += 1
    db.session.flush()
    return period

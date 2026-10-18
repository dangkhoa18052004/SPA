"""Read-only BI with explicit time bases and conservative legacy branch attribution."""
from datetime import datetime, time, timedelta
from decimal import Decimal
import re
from sqlalchemy import func, select
from ..extensions import db
from ..models import (LichHen, AppointmentStatus, NhanVien, CommissionEntry,
    AttendanceSession, PayrollPeriod, PayrollLine, Branch, AppointmentOutcome)
from . import analytics_service as analytics, attendance_service as attendance
from .package_service import local_now


class ReportError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def date_range(args):
    today = local_now().date()
    values = [args.get('from', today.replace(day=1).isoformat()), args.get('to', today.isoformat())]
    try:
        if any(not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) for v in values): raise ValueError()
        start, end = [datetime.strptime(v, '%Y-%m-%d').date() for v in values]
        if end < start or (end - start).days > 365: raise ValueError()
        # Avoid datetime overflow in the half-open upper boundary.
        datetime.combine(end + timedelta(days=1), time.min)
        start - timedelta(days=(end - start).days + 1)
        return start, end
    except (ValueError, TypeError, OverflowError):
        raise ReportError('Chọn khoảng ngày hợp lệ, tối đa 366 ngày (YYYY-MM-DD).')


def scope_for(actor, raw_branch=None):
    allowed = attendance.allowed_branches(actor, manage=True)
    if raw_branch:
        if not re.fullmatch(r'[1-9]\d*', raw_branch): raise ReportError('Cơ sở không hợp lệ.')
        branch = int(raw_branch)
        if branch not in allowed: raise ReportError('Bạn không có quyền tại cơ sở này.', 403)
        allowed = [branch]
    # Old bookings/invoices/package sales do not have a reliable branch snapshot.
    # A fixed single-site installation is unambiguous. Multi-site managers see only
    # their branch attendance/payroll, never the spa-wide legacy financial records.
    single_site = attendance.simple_mode() and allowed == [attendance.fixed_branch_id()]
    business = 'single_site' if single_site else 'legacy_global' if actor.role == 'admin' and not raw_branch else 'unavailable'
    return allowed, business


def pct(numerator, denominator):
    return round(numerator / denominator * 100, 1) if denominator else None


def money(value):
    return str(Decimal(value or 0).quantize(Decimal('.01')))


def report(actor, args):
    start, end = date_range(args)
    branches, business_scope = scope_for(actor, args.get('branch_id'))
    lo, hi = datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)
    result = dict(from_date=start.isoformat(), to_date=end.isoformat(), timezone='Asia/Ho_Chi_Minh',
        branch_ids=branches, business_scope=business_scope, business=None,
        branches=[dict(id=b.id, name=b.name) for b in Branch.query.filter(Branch.id.in_(branches)).order_by(Branch.id)])
    if business_scope != 'unavailable':
        base = LichHen.query.filter(LichHen.ngaygio >= lo, LichHen.ngaygio < hi)
        counts = {key: 0 for key in AppointmentStatus.ALL}
        for state, count in db.session.query(LichHen.trangthai, func.count()).filter(
                LichHen.ngaygio >= lo, LichHen.ngaygio < hi).group_by(LichHen.trangthai):
            normalized = AppointmentStatus.normalize(state)
            counts[normalized] = counts.get(normalized, 0) + count
        no_show = base.join(AppointmentOutcome, AppointmentOutcome.malh == LichHen.malh).filter(
            AppointmentOutcome.outcome == 'no_show', LichHen.trangthai == AppointmentStatus.CANCELLED).count()
        completed = LichHen.trangthai == AppointmentStatus.COMPLETED
        current_customers = select(LichHen.makh).where(completed, LichHen.ngaygio >= lo, LichHen.ngaygio < hi).distinct()
        before = select(LichHen.makh).where(completed, LichHen.ngaygio < lo).distinct()
        previous_lo = lo - timedelta(days=(end - start).days + 1)
        cohort = select(LichHen.makh).where(completed, LichHen.ngaygio >= previous_lo, LichHen.ngaygio < lo).distinct()
        current_count = db.session.query(func.count()).select_from(current_customers.subquery()).scalar()
        returning = base.filter(completed, LichHen.makh.in_(before)).with_entities(LichHen.makh).distinct().count()
        cohort_count = db.session.query(func.count()).select_from(cohort.subquery()).scalar()
        retained = base.filter(completed, LichHen.makh.in_(cohort)).with_entities(LichHen.makh).distinct().count()
        commissions = db.session.query(func.sum(CommissionEntry.amount)).filter(
            CommissionEntry.earned_at >= lo, CommissionEntry.earned_at < hi, CommissionEntry.status == 'active').scalar()
        revenue = analytics.revenue_breakdown(lo, hi - timedelta(microseconds=1))
        result['business'] = dict(revenue={key: money(revenue[key]) for key in ('service', 'package', 'total')},
            appointments=dict(total=sum(counts.values()), counts=counts, no_show_recorded=no_show,
                cancelled_without_outcome=max(0, counts.get('cancelled', 0) - no_show)),
            customers=dict(completed=current_count, returning=returning, returning_rate=pct(returning, current_count),
                cohort=cohort_count, retained=retained, retention_rate=pct(retained, cohort_count),
                cohort_from=previous_lo.date().isoformat(), cohort_to=(start - timedelta(days=1)).isoformat()),
            earned_commission=money(commissions),
            revenue_series=analytics.revenue_timeseries(start.isoformat(), end.isoformat())['records'])

    # Attendance work_date is the Vietnam shift-start date; approved minutes only.
    sessions = AttendanceSession.query.filter(AttendanceSession.branch_id.in_(branches), AttendanceSession.work_date.between(start, end))
    states = dict(sessions.with_entities(AttendanceSession.approval_status, func.count()).group_by(AttendanceSession.approval_status).all())
    rows = sessions.join(NhanVien, NhanVien.manv == AttendanceSession.staff_id).with_entities(
        AttendanceSession.staff_id, NhanVien.hoten, AttendanceSession.approval_status,
        func.count(), func.sum(AttendanceSession.worked_minutes), func.sum(AttendanceSession.paid_minutes),
        func.sum(AttendanceSession.overtime_minutes), func.sum(AttendanceSession.late_minutes)).group_by(
            AttendanceSession.staff_id, NhanVien.hoten, AttendanceSession.approval_status).all()
    people = {}
    for sid, name, state, count, worked, paid, overtime, late in rows:
        person = people.setdefault(sid, dict(staff_id=sid, name=name, sessions=0, worked_minutes=0, approved_minutes=0, overtime_minutes=0, late_minutes=0))
        person['sessions'] += count
        person['worked_minutes'] += worked or 0
        person['late_minutes'] += late or 0
        if state in ('APPROVED', 'LOCKED'):
            person['approved_minutes'] += paid or 0
            person['overtime_minutes'] += overtime or 0
    # Never prorate frozen payroll snapshots across report dates.
    periods = PayrollPeriod.query.filter(PayrollPeriod.branch_id.in_(branches), PayrollPeriod.from_date >= start, PayrollPeriod.to_date <= end)
    locked_ids = periods.filter(PayrollPeriod.status == 'LOCKED').with_entities(PayrollPeriod.id)
    totals = db.session.query(func.sum(PayrollLine.net), func.sum(PayrollLine.commission)).filter(PayrollLine.period_id.in_(select(locked_ids.subquery().c.id))).one()
    overlapping = PayrollPeriod.query.filter(PayrollPeriod.branch_id.in_(branches), PayrollPeriod.status == 'LOCKED', PayrollPeriod.from_date <= end,
        PayrollPeriod.to_date >= start, ~((PayrollPeriod.from_date >= start) & (PayrollPeriod.to_date <= end))).count()
    result['workforce'] = dict(session_states=states, people=sorted(people.values(), key=lambda p: (p['name'], p['staff_id'])),
        approved_minutes=sum(p['approved_minutes'] for p in people.values()), overtime_minutes=sum(p['overtime_minutes'] for p in people.values()),
        locked_payroll=money(totals[0]), locked_commission=money(totals[1]), locked_periods=locked_ids.count(),
        excluded_partial_periods=overlapping)
    return result

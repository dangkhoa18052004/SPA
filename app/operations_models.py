"""Attendance and payroll records. Existing (manv, maca) assignments remain canonical."""
from datetime import datetime, timezone
from .extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Branch(db.Model):
    __tablename__ = 'branch'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False, default='')
    active = db.Column(db.Boolean, nullable=False, default=True)


class BranchMembership(db.Model):
    __tablename__ = 'branch_membership'
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), primary_key=True)
    can_manage = db.Column(db.Boolean, nullable=False, default=False)


class BranchGeoPolicy(db.Model):
    __tablename__ = 'branch_geo_policy'
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    settings = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (db.UniqueConstraint('branch_id', 'version', name='uq_branch_policy_version'),)


class AttendanceEvent(db.Model):
    __tablename__ = 'attendance_event'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('calam.maca'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)
    server_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    accuracy = db.Column(db.Float, nullable=True)
    distance = db.Column(db.Float, nullable=True)
    verdict = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    request_key = db.Column(db.String(100), nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey('branch_geo_policy.id'), nullable=False)
    response = db.Column(db.JSON, nullable=False)
    http_status = db.Column(db.Integer, nullable=False)
    __table_args__ = (
        db.UniqueConstraint('staff_id', 'request_key', name='uq_attendance_request'),
        db.Index('ix_attendance_staff_time', 'staff_id', 'server_at'),
        db.Index('ix_attendance_shift_type', 'shift_id', 'event_type'),
    )


class AttendanceSession(db.Model):
    __tablename__ = 'attendance_session'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('calam.maca'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    planned_start = db.Column(db.DateTime(timezone=True), nullable=False)
    planned_end = db.Column(db.DateTime(timezone=True), nullable=False)
    actual_start = db.Column(db.DateTime(timezone=True), nullable=False)
    actual_end = db.Column(db.DateTime(timezone=True), nullable=True)
    checkin_event_id = db.Column(db.Integer, db.ForeignKey('attendance_event.id'), nullable=True)
    checkout_event_id = db.Column(db.Integer, db.ForeignKey('attendance_event.id'), nullable=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('branch_geo_policy.id'), nullable=False)
    break_minutes = db.Column(db.Integer, nullable=False, default=0)
    worked_minutes = db.Column(db.Integer, nullable=False, default=0)
    paid_minutes = db.Column(db.Integer, nullable=False, default=0)
    overtime_minutes = db.Column(db.Integer, nullable=False, default=0)
    compensation = db.Column(db.JSON, nullable=False, default=dict)
    late_minutes = db.Column(db.Integer, nullable=False, default=0)
    early_leave_minutes = db.Column(db.Integer, nullable=False, default=0)
    hourly_rate = db.Column(db.Numeric(14, 2), nullable=False)
    shift_multiplier = db.Column(db.Numeric(6, 2), nullable=False)
    approval_status = db.Column(db.String(20), nullable=False, default='OPEN')
    approved_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}
    __table_args__ = (
        db.UniqueConstraint('staff_id', 'shift_id', name='uq_attendance_assignment'),
        db.Index('ix_attendance_branch_date', 'branch_id', 'work_date'),
        db.CheckConstraint("approval_status IN ('OPEN','SUBMITTED','APPROVED','REJECTED','LOCKED')", name='ck_attendance_status'),
        db.CheckConstraint('paid_minutes >= 0 AND overtime_minutes >= 0 AND break_minutes >= 0', name='ck_attendance_minutes'),
    )


class AttendanceAdjustment(db.Model):
    __tablename__ = 'attendance_adjustment'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_session.id'), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('calam.maca'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    proposed_start = db.Column(db.DateTime(timezone=True), nullable=False)
    proposed_end = db.Column(db.DateTime(timezone=True), nullable=True)
    request_kind = db.Column(db.String(20), nullable=False, default='correction', server_default='correction')
    reason = db.Column(db.Text, nullable=False)
    session_version = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='PENDING')
    decision_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    decision_at = db.Column(db.DateTime(timezone=True), nullable=True)
    decision_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class AttendancePeriod(db.Model):
    __tablename__ = 'attendance_period'
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='DRAFT')
    locked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    locked_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    __table_args__ = (
        db.UniqueConstraint('branch_id', 'from_date', 'to_date', name='uq_attendance_period'),
        db.CheckConstraint('to_date >= from_date', name='ck_attendance_period_dates'),
    )


class PayrollPeriod(db.Model):
    __tablename__ = 'payroll_period'
    id = db.Column(db.Integer, primary_key=True)
    attendance_period_id = db.Column(db.Integer, db.ForeignKey('attendance_period.id'), nullable=False, unique=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    policy_snapshot = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='DRAFT')
    created_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=True)
    locked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}


class PayrollLine(db.Model):
    __tablename__ = 'payroll_line'
    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('payroll_period.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    paid_minutes = db.Column(db.Integer, nullable=False)
    base = db.Column(db.Numeric(14, 2), nullable=False)
    overtime = db.Column(db.Numeric(14, 2), nullable=False)
    commission = db.Column(db.Numeric(14, 2), nullable=False)
    allowance = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    deduction = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    net = db.Column(db.Numeric(14, 2), nullable=False)
    source_snapshot = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint('period_id', 'staff_id', name='uq_payroll_period_staff'),)


class PayrollAdjustment(db.Model):
    __tablename__ = 'payroll_adjustment'
    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey('payroll_line.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    allowance_delta = db.Column(db.Numeric(14, 2), nullable=False)
    deduction_delta = db.Column(db.Numeric(14, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class PayrollCommissionClaim(db.Model):
    """Each legacy commission is paid once across branches/periods, using a frozen copy."""
    __tablename__ = 'payroll_commission_claim'
    commission_id = db.Column(db.Integer, db.ForeignKey('commission_entry.id'), primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey('payroll_line.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    settled_amount = db.Column(db.Numeric(14, 2), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=1)


class PayrollCommissionDelta(db.Model):
    __tablename__ = 'payroll_commission_delta'
    id = db.Column(db.Integer, primary_key=True)
    commission_id = db.Column(db.Integer, db.ForeignKey('commission_entry.id'), nullable=False)
    line_id = db.Column(db.Integer, db.ForeignKey('payroll_line.id'), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    __table_args__ = (db.UniqueConstraint('commission_id', 'revision', name='uq_commission_delta_revision'),)


class OperationsAudit(db.Model):
    __tablename__ = 'operations_audit'
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    before = db.Column(db.JSON, nullable=True)
    after = db.Column(db.JSON, nullable=True)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (db.Index('ix_operations_audit_branch_time', 'branch_id', 'created_at'),)

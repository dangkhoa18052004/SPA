"""Additive operations APIs; authorization always comes from the current staff record."""
import csv
import io
from datetime import datetime, time, timedelta
from functools import wraps

import click
from flask import Blueprint, current_app, g, jsonify, request, render_template, Response, abort
from sqlalchemy import case, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import StaleDataError
from ..decorators import login_required
from ..extensions import db
from ..models import NhanVien, CaLam, LichHen, ChiTietLichHen, KhachHang, AppointmentStatus
from ..operations_models import (Branch, BranchMembership, BranchGeoPolicy, AttendanceEvent,
    AttendanceSession, AttendanceAdjustment, AttendancePeriod, PayrollPeriod, PayrollLine, OperationsAudit)
from ..services import attendance_service as att, payroll_service as payroll
from ..services.staff_security_service import step_up_required

operations_bp = Blueprint('operations', __name__)


def staff_api(manage=False, admin=False):
    def decorate(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            actor = g.current_user
            if g.current_user_type != 'staff' or not actor.trangthai:
                raise att.OperationsError('Cần tài khoản nhân viên đang hoạt động', 403)
            if actor.role not in {'staff', 'letan', 'manager', 'admin'}:
                raise att.OperationsError('Vai trò không hợp lệ', 403)
            if (manage and actor.role not in {'admin', 'manager'}) or (admin and actor.role != 'admin'):
                raise att.OperationsError('Bạn không có quyền thực hiện thao tác này', 403)
            return fn(*args, **kwargs)
        return wrapped
    return decorate


@operations_bp.errorhandler(att.OperationsError)
def invalid(error):
    db.session.rollback()
    return jsonify(success=False, code=error.code, message=str(error)), error.status


@operations_bp.errorhandler(IntegrityError)
@operations_bp.errorhandler(StaleDataError)
def conflict(_error):
    db.session.rollback()
    return jsonify(success=False, code='concurrent_change', message='Dữ liệu vừa thay đổi, vui lòng tải lại hoặc gửi lại cùng khóa yêu cầu'), 409


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise att.OperationsError('Nội dung phải là JSON object')
    return data


def get_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise att.OperationsError('Không tìm thấy bản ghi', 404)
    return item


def page(query, serializer):
    try:
        index, size = int(request.args.get('page', 1)), int(request.args.get('per_page', 20))
        if index < 1 or not 1 <= size <= 100:
            raise ValueError()
    except ValueError:
        raise att.OperationsError('Phân trang không hợp lệ')
    total = query.count()
    return dict(items=[serializer(row) for row in query.offset((index - 1) * size).limit(size)],
        page=index, per_page=size, total=total)


def branch_data(branch, include_policy=False):
    result = dict(id=branch.id, name=branch.name, address=branch.address, active=branch.active)
    if include_policy:
        policy = att.policy_for(branch.id)
        result['policy'] = dict(id=policy.id, version=policy.version, **policy.settings) if policy else None
        result['members'] = [dict(staff_id=m.staff_id, can_manage=m.can_manage,
            name=db.session.get(NhanVien, m.staff_id).hoten) for m in BranchMembership.query.filter_by(branch_id=branch.id)]
    return result


@operations_bp.get('/api/me/operations')
@staff_api()
def me():
    actor = g.current_user
    return jsonify(user=dict(id=actor.manv, name=actor.hoten, role=actor.role),
        branches=[branch_data(b) for b in Branch.query.filter(Branch.id.in_(att.allowed_branches(actor)))],
        managed_branch_ids=att.allowed_branches(actor, True),
        features=dict(attendance=bool(current_app.config.get('ATTENDANCE_ENABLED')),
            staff_security=bool(current_app.config.get('STAFF_SECURITY_ENABLED')),
            bi=bool(current_app.config.get('BI_REPORTS_ENABLED')), observability=bool(current_app.config.get('OBSERVABILITY_ENABLED')),
            crm=bool(current_app.config.get('CRM_ENABLED')), recommendation_metrics=bool(current_app.config.get('RECOMMENDATION_METRICS_ENABLED')),
            employee_portal=bool(current_app.config.get('EMPLOYEE_PORTAL_ENABLED')),
            business_portal=bool(current_app.config.get('BUSINESS_PORTAL_ENABLED')),
            admin_booking=bool(current_app.config.get('BUSINESS_PORTAL_ENABLED') and current_app.config.get('ADMIN_BOOKING_REACT_ENABLED')),
            admin_billing=bool(current_app.config.get('BUSINESS_PORTAL_ENABLED') and current_app.config.get('ADMIN_BILLING_REACT_ENABLED')),
            admin_catalog=bool(current_app.config.get('BUSINESS_PORTAL_ENABLED') and current_app.config.get('ADMIN_CATALOG_REACT_ENABLED')),
            admin_people=bool(current_app.config.get('BUSINESS_PORTAL_ENABLED') and current_app.config.get('ADMIN_PEOPLE_REACT_ENABLED')),
            admin_care=bool(current_app.config.get('BUSINESS_PORTAL_ENABLED') and current_app.config.get('ADMIN_CARE_REACT_ENABLED')),
            payroll=bool(current_app.config.get('PAYROLL_V2_ENABLED')), simple_attendance=att.simple_mode()), timezone='Asia/Ho_Chi_Minh')


def employee_appointment_data(item):
    from ..services.appointment_service import split_notes
    services = [dict(id=detail.madv, name=detail.dichvu.tendv,
        duration_minutes=detail.dichvu.thoiluong or 60) for detail in item.chitiet if detail.dichvu]
    duration = sum(service['duration_minutes'] for service in services)
    status = AppointmentStatus.normalize(item.trangthai)
    # Existing appointment timestamps are local Vietnam time, not UTC.
    start = item.ngaygio.replace(tzinfo=att.LOCAL)
    return dict(id=item.malh, scheduled_at=start.isoformat(),
        ends_at=(start + timedelta(minutes=duration)).isoformat(), duration_minutes=duration,
        customer_name=item.khachhang.hoten if item.khachhang else 'Khách hàng',
        customer_phone=item.khachhang.sdt if item.khachhang else None,
        services=services, status=status, status_label=AppointmentStatus.to_vietnamese(status),
        note=split_notes(item.ghichu)[0] or '')


@operations_bp.get('/api/me/appointments')
@staff_api()
def employee_appointments():
    # Always scope by the authenticated staff record, including admin/manager.
    own = LichHen.query.filter(LichHen.manv == g.current_user.manv)
    now = att.now_utc().astimezone(att.LOCAL).replace(tzinfo=None)
    today_start = datetime.combine(now.date(), time.min)
    summary = dict(total=own.count(), today=own.filter(LichHen.ngaygio >= today_start,
        LichHen.ngaygio < today_start + timedelta(days=1)).count(),
        upcoming=own.filter(LichHen.ngaygio >= now,
            LichHen.trangthai.in_(AppointmentStatus.ACTIVE_STATUSES)).count())
    start = payroll.parse_date(request.args['from_date']) if request.args.get('from_date') else None
    end = payroll.parse_date(request.args['to_date']) if request.args.get('to_date') else None
    if start and end and end < start:
        raise att.OperationsError('Ngày kết thúc phải từ ngày bắt đầu trở đi')
    query = own
    if start:
        query = query.filter(LichHen.ngaygio >= datetime.combine(start, time.min))
    if end:
        query = query.filter(LichHen.ngaygio <= datetime.combine(end, time.max))
    if request.args.get('status'):
        status = AppointmentStatus.normalize(request.args['status'])
        if status not in AppointmentStatus.ALL:
            raise att.OperationsError('Trạng thái lịch hẹn không hợp lệ')
        query = query.filter(LichHen.trangthai == status)
    search = request.args.get('q', '').strip()
    if len(search) > 100:
        raise att.OperationsError('Từ khóa tìm kiếm tối đa 100 ký tự')
    if search:
        query = query.join(LichHen.khachhang).filter(or_(
            KhachHang.hoten.icontains(search, autoescape=True),
            KhachHang.sdt.icontains(search, autoescape=True)))
    query = query.options(joinedload(LichHen.khachhang),
        joinedload(LichHen.chitiet).joinedload(ChiTietLichHen.dichvu)).order_by(
            case((LichHen.ngaygio >= now, 0), else_=1),
            case((LichHen.ngaygio >= now, LichHen.ngaygio), else_=None).asc(),
            LichHen.ngaygio.desc(), LichHen.malh.desc())
    return jsonify(**page(query, employee_appointment_data), summary=summary, today=now.date().isoformat())


@operations_bp.get('/api/me/shifts/today')
@operations_bp.get('/api/me/shifts')
@staff_api()
def shifts():
    today = att.now_utc().astimezone(att.LOCAL).date()
    start, end = today - timedelta(days=1), today
    if request.path == '/api/me/shifts':
        start = payroll.parse_date(request.args.get('from_date', (today - timedelta(days=7)).isoformat()))
        end = payroll.parse_date(request.args.get('to_date', (today + timedelta(days=30)).isoformat()))
        if end < start or (end - start).days > 93:
            raise att.OperationsError('Khoảng lịch không quá 94 ngày')
    query = (att.shifts_in_branches(CaLam.query, att.allowed_branches(g.current_user))
             if att.simple_mode() else g.current_user.calam)
    query = query.filter(CaLam.ngay.between(start, end)).order_by(CaLam.ngay, CaLam.giobatdau)
    items = [att.shift_data(g.current_user, shift) for shift in query]
    if request.path.endswith('/today'):
        # Previous-day overnight shift remains visible through its checkout grace window.
        items = [item for item in items if att.parse_time(item['checkout_closes_at']) >= att.now_utc() or
            att.parse_time(item['start_at']).astimezone(att.LOCAL).date() == today]
    return jsonify(items=items, server_at=att.iso(att.now_utc()))


@operations_bp.post('/api/attendance/check-in')
@operations_bp.post('/api/attendance/check-out')
@staff_api()
def punch():
    result, status = att.punch(g.current_user, body(), request.path.rsplit('/', 1)[1])
    db.session.commit()
    return jsonify(result), status


@operations_bp.get('/api/me/attendance')
@staff_api()
def history():
    query = AttendanceSession.query.filter_by(staff_id=g.current_user.manv).order_by(AttendanceSession.work_date.desc(), AttendanceSession.id.desc())
    return jsonify(page(query, att.session_data))


@operations_bp.get('/api/me/attendance-events')
@staff_api()
def my_events():
    query = AttendanceEvent.query.filter_by(staff_id=g.current_user.manv).order_by(AttendanceEvent.id.desc())
    return jsonify(page(query, lambda event: dict(id=event.id, shift_id=event.shift_id,
        event_type=event.event_type, server_at=att.iso(event.server_at), verdict=event.verdict,
        reason=att.GPS_ERRORS.get(event.reason, 'Đã ghi nhận'), accuracy_m=event.accuracy,
        distance_m=event.distance)))


@operations_bp.route('/api/me/attendance-adjustments', methods=['GET', 'POST'])
@staff_api()
def adjustments():
    if request.method == 'POST':
        item = att.request_adjustment(g.current_user, body())
        db.session.commit()
        return jsonify(att.adjustment_data(item)), 201
    return jsonify(page(AttendanceAdjustment.query.filter_by(staff_id=g.current_user.manv).order_by(AttendanceAdjustment.id.desc()), att.adjustment_data))


@operations_bp.get('/api/me/payslips')
@staff_api()
def payslips():
    query = PayrollLine.query.join(PayrollPeriod).filter(PayrollLine.staff_id == g.current_user.manv,
        PayrollPeriod.status == 'LOCKED').order_by(PayrollPeriod.from_date.desc())
    return jsonify(page(query, payroll.line_data))


@operations_bp.get('/api/me/income-summary')
@staff_api()
def income_summary():
    today = att.now_utc().astimezone(att.LOCAL).date()
    start = payroll.parse_date(request.args.get('from_date', today.replace(day=1).isoformat()))
    end = payroll.parse_date(request.args.get('to_date', today.isoformat()))
    return jsonify(payroll.income_summary(g.current_user, start, end))


@operations_bp.get('/api/me/payslips/<int:line_id>')
@staff_api()
def payslip(line_id):
    line = get_item(PayrollLine, line_id)
    period = get_item(PayrollPeriod, line.period_id)
    if line.staff_id != g.current_user.manv or period.status != 'LOCKED':
        raise att.OperationsError('Không có quyền xem phiếu lương', 403)
    return jsonify(payroll.line_data(line))


@operations_bp.get('/api/me/commissions')
@staff_api()
def commissions():
    from ..models import CommissionEntry
    from ..services import commission_service
    query = CommissionEntry.query.filter_by(manv=g.current_user.manv).order_by(CommissionEntry.earned_at.desc(), CommissionEntry.id.desc())
    return jsonify(page(query, commission_service.serialize))


@operations_bp.route('/api/admin/branches', methods=['GET', 'POST'])
@staff_api(manage=True)
def branches():
    actor = g.current_user
    if request.method == 'GET':
        return jsonify(items=[branch_data(b, True) for b in Branch.query.filter(Branch.id.in_(att.allowed_branches(actor, True))).order_by(Branch.id)])
    if actor.role != 'admin':
        raise att.OperationsError('Chỉ admin được tạo cơ sở', 403)
    # Creating a location also creates its GPS/payroll policy.
    if current_app.config.get('STAFF_SECURITY_ENABLED'):
        from ..services.staff_security_service import require_elevation
        blocked = require_elevation(actor)
        if blocked is not None:
            return blocked
    if att.simple_mode():
        raise att.OperationsError('Chấm công đang dùng một địa điểm cố định; không cần thêm cơ sở', 409)
    data = body()
    name = att.reason_text(data.get('name'))
    if len(name) > 100 or not isinstance(data.get('address', ''), str) or len(data.get('address', '')) > 255:
        raise att.OperationsError('Tên/địa chỉ cơ sở quá dài')
    branch = Branch(name=name, address=data.get('address', ''), active=True)
    db.session.add(branch)
    db.session.flush()
    att.audit(actor, branch.id, 'branch_created', branch, None, branch_data(branch), 'Tạo cơ sở')
    att.save_policy(actor, branch.id, data.get('policy', {}), data.get('reason', 'Khởi tạo cơ sở'))
    db.session.commit()
    return jsonify(branch_data(branch, True)), 201


@operations_bp.post('/api/admin/branches/<int:branch_id>/policy')
@staff_api(admin=True)
@step_up_required
def policy(branch_id):
    data = body()
    item = att.save_policy(g.current_user, branch_id, data.get('settings'), data.get('reason'))
    db.session.commit()
    return jsonify(id=item.id, version=item.version, settings=item.settings), 201


@operations_bp.put('/api/admin/branches/<int:branch_id>/members/<int:staff_id>')
@staff_api(admin=True)
@step_up_required
def membership(branch_id, staff_id):
    if att.simple_mode():
        raise att.OperationsError('Nhân viên được dùng địa điểm cố định tự động; không cần phân cơ sở', 409)
    data = body()
    att.lock_branch(branch_id)
    staff = get_item(NhanVien, staff_id)
    can_manage = data.get('can_manage', False)
    if type(can_manage) is not bool or (can_manage and staff.role not in {'manager', 'admin'}):
        raise att.OperationsError('Chỉ manager/admin được quản lý cơ sở')
    item = db.session.get(BranchMembership, (branch_id, staff_id))
    before = dict(staff_id=staff_id, can_manage=item.can_manage) if item else None
    if not item:
        item = BranchMembership(branch_id=branch_id, staff_id=staff_id)
        db.session.add(item)
    item.can_manage = can_manage
    branch = get_item(Branch, branch_id)
    att.audit(g.current_user, branch_id, 'branch_member_set', branch, before,
        dict(staff_id=staff_id, can_manage=can_manage), att.reason_text(data.get('reason')))
    db.session.commit()
    return jsonify(success=True)


@operations_bp.put('/api/admin/shifts/<int:shift_id>/branch')
@staff_api(manage=True)
def shift_branch(shift_id):
    if att.simple_mode():
        raise att.OperationsError('Ca làm dùng địa điểm cố định tự động; không cần gắn cơ sở', 409)
    data, actor = body(), g.current_user
    branch_id = att.integer(data.get('branch_id'), 'Mã cơ sở', 1)
    att.require_branch(actor, branch_id, True)
    shift = get_item(CaLam, shift_id)
    att.protect_shift(shift, actor)
    att.lock_branch(branch_id)
    att.ensure_unlocked(branch_id, shift.ngay)
    if any(branch_id not in att.allowed_branches(staff) for staff in shift.nhanvien):
        raise att.OperationsError('Cần cấp cơ sở cho tất cả nhân viên đã phân ca', 409)
    old = shift.branch_id
    shift.branch_id = branch_id
    branch = get_item(Branch, branch_id)
    att.audit(actor, branch_id, 'shift_branch_set', branch, dict(shift_id=shift_id, branch_id=old),
        dict(shift_id=shift_id, branch_id=branch_id), att.reason_text(data.get('reason')))
    db.session.commit()
    return jsonify(success=True)


@operations_bp.get('/api/admin/attendance/pending')
@operations_bp.get('/api/admin/attendance')
@staff_api(manage=True)
def attendance():
    ids = att.allowed_branches(g.current_user, True)
    query = AttendanceSession.query.filter(AttendanceSession.branch_id.in_(ids)).order_by(AttendanceSession.work_date.desc(), AttendanceSession.id.desc())
    if request.path.endswith('/pending'):
        query = query.filter(AttendanceSession.approval_status.in_(['OPEN', 'SUBMITTED']))
    if request.args.get('branch_id'):
        query = query.filter_by(branch_id=request.args.get('branch_id', type=int))
    if request.args.get('from_date'):
        query = query.filter(AttendanceSession.work_date >= payroll.parse_date(request.args['from_date']))
    if request.args.get('to_date'):
        query = query.filter(AttendanceSession.work_date <= payroll.parse_date(request.args['to_date']))
    return jsonify(page(query, att.session_data))


@operations_bp.get('/api/admin/attendance/missing')
@staff_api(manage=True)
def missing_attendance():
    start = payroll.parse_date(request.args.get('from_date'))
    end = payroll.parse_date(request.args.get('to_date'))
    if end < start or (end - start).days > 62:
        raise att.OperationsError('Khoảng ngày không hợp lệ')
    shifts = att.shifts_in_branches(CaLam.query, att.allowed_branches(g.current_user, True)).filter(CaLam.ngay.between(start, end)).all()
    sessions = {(s.staff_id, s.shift_id) for s in AttendanceSession.query.filter(AttendanceSession.shift_id.in_([x.maca for x in shifts])).all()}
    return jsonify(items=[dict(staff_id=staff.manv, staff_name=staff.hoten, shift_id=shift.maca,
        branch_id=att.shift_branch_id(shift), work_date=shift.ngay.isoformat()) for shift in shifts for staff in shift.nhanvien if (staff.manv, shift.maca) not in sessions])


@operations_bp.post('/api/admin/attendance/<int:session_id>/approve')
@staff_api(manage=True)
@step_up_required
def approve_attendance(session_id):
    item = att.approve_session(g.current_user, get_item(AttendanceSession, session_id), body())
    db.session.commit()
    return jsonify(att.session_data(item))


@operations_bp.post('/api/admin/attendance/exceptions')
@staff_api(manage=True)
@step_up_required
def attendance_exception():
    item = att.record_exception(g.current_user, body())
    db.session.commit()
    return jsonify(att.session_data(item)), 201


@operations_bp.get('/api/admin/attendance-adjustments')
@staff_api(manage=True)
def pending_adjustments():
    query = AttendanceAdjustment.query.filter(AttendanceAdjustment.branch_id.in_(att.allowed_branches(g.current_user, True)),
        AttendanceAdjustment.status == 'PENDING').order_by(AttendanceAdjustment.id)
    return jsonify(page(query, att.adjustment_data))


@operations_bp.post('/api/admin/attendance-adjustments/<int:item_id>/decide')
@staff_api(manage=True)
@step_up_required
def decide_adjustment(item_id):
    item = att.decide_adjustment(g.current_user, get_item(AttendanceAdjustment, item_id), body())
    db.session.commit()
    return jsonify(att.adjustment_data(item))


@operations_bp.route('/api/admin/attendance-periods', methods=['GET', 'POST'])
@staff_api(manage=True)
def attendance_periods():
    if request.method == 'POST':
        period = payroll.create_attendance_period(g.current_user, body())
        db.session.commit()
        return jsonify(payroll.period_data(period)), 201
    query = AttendancePeriod.query.filter(AttendancePeriod.branch_id.in_(att.allowed_branches(g.current_user, True))).order_by(AttendancePeriod.from_date.desc())
    return jsonify(page(query, lambda period: dict(**payroll.period_data(period),
        readiness=payroll.attendance_readiness(g.current_user, period))))


@operations_bp.post('/api/admin/attendance-periods/<int:period_id>/lock')
@staff_api(manage=True)
@step_up_required
def lock_attendance(period_id):
    item = payroll.lock_attendance_period(g.current_user, get_item(AttendancePeriod, period_id), body().get('reason'))
    db.session.commit()
    return jsonify(payroll.period_data(item))


def require_payroll():
    if not current_app.config.get('PAYROLL_V2_ENABLED'):
        raise att.OperationsError('Bảng lương mới đang chờ kích hoạt', 503, 'feature_disabled')


@operations_bp.route('/api/admin/payroll-periods', methods=['GET', 'POST'])
@staff_api(manage=True)
def payroll_periods():
    if request.method == 'POST':
        # Elevation runs before the snapshot transaction.
        return create_payroll_period()
    return jsonify(page(PayrollPeriod.query.filter(PayrollPeriod.branch_id.in_(att.allowed_branches(g.current_user, True))).order_by(PayrollPeriod.from_date.desc()), payroll.period_data))


@step_up_required
def create_payroll_period():
    require_payroll()
    period = payroll.build_payroll(g.current_user, get_item(AttendancePeriod,
        att.integer(body().get('attendance_period_id'), 'Mã kỳ công', 1)))
    db.session.commit()
    return jsonify(payroll.period_data(period)), 201



@operations_bp.get('/api/admin/payroll-periods/<int:period_id>')
@staff_api(manage=True)
def payroll_detail(period_id):
    period = get_item(PayrollPeriod, period_id)
    att.require_branch(g.current_user, period.branch_id, True)
    return jsonify(**payroll.period_data(period), warnings=payroll.commission_warnings(period) if period.status == 'DRAFT' else [],
        lines=[payroll.line_data(line) for line in PayrollLine.query.filter_by(period_id=period.id).order_by(PayrollLine.staff_id)])


@operations_bp.post('/api/admin/payroll-periods/<int:period_id>/reconcile')
@staff_api(manage=True)
@step_up_required
def reconcile_payroll(period_id):
    require_payroll()
    item = payroll.reconcile_draft(g.current_user, get_item(PayrollPeriod, period_id), body())
    db.session.commit()
    return jsonify(payroll.period_data(item))


@operations_bp.post('/api/admin/payroll-lines/<int:line_id>/adjust')
@staff_api(manage=True)
@step_up_required
def payroll_adjust(line_id):
    require_payroll()
    item = payroll.adjust_line(g.current_user, get_item(PayrollLine, line_id), body())
    db.session.commit()
    return jsonify(payroll.line_data(item))


@operations_bp.post('/api/admin/payroll-periods/<int:period_id>/approve')
@operations_bp.post('/api/admin/payroll-periods/<int:period_id>/lock')
@staff_api(manage=True)
@step_up_required
def payroll_transition(period_id):
    require_payroll()
    item = payroll.transition(g.current_user, get_item(PayrollPeriod, period_id), body(), request.path.rsplit('/', 1)[1])
    db.session.commit()
    return jsonify(payroll.period_data(item))


@operations_bp.get('/api/admin/payroll-periods/<int:period_id>/export.csv')
@staff_api(manage=True)
@step_up_required
def payroll_export(period_id):
    period = get_item(PayrollPeriod, period_id)
    att.require_branch(g.current_user, period.branch_id, True)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Nhân viên', 'Phút công', 'Lương công', 'Tăng ca', 'Hoa hồng', 'Phụ cấp', 'Khấu trừ', 'Tổng trước thuế/bảo hiểm'])
    for line in PayrollLine.query.filter_by(period_id=period_id).order_by(PayrollLine.staff_id):
        name = line.source_snapshot['staff_name']
        if name.startswith(('=', '+', '-', '@', '\t', '\r')):
            name = "'" + name
        writer.writerow([name, line.paid_minutes, line.base, line.overtime, line.commission, line.allowance, line.deduction, line.net])
    response = Response('\ufeff' + output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename="payroll-{period_id}.csv"'
    response.headers['Cache-Control'] = 'no-store'
    return response


@operations_bp.get('/api/admin/operations/audit')
@staff_api(manage=True)
def audit_log():
    query = OperationsAudit.query.filter(OperationsAudit.branch_id.in_(att.allowed_branches(g.current_user, True))).order_by(OperationsAudit.id.desc())
    return jsonify(page(query, lambda row: dict(id=row.id, actor_id=row.actor_id, branch_id=row.branch_id,
        action=row.action, entity_type=row.entity_type, entity_id=row.entity_id,
        before=row.before, after=row.after, reason=row.reason, created_at=att.iso(row.created_at))))


@operations_bp.get('/api/admin/operations/summary')
@staff_api(manage=True)
def summary():
    ids = att.allowed_branches(g.current_user, True)
    return jsonify(pending=AttendanceSession.query.filter(AttendanceSession.branch_id.in_(ids), AttendanceSession.approval_status == 'SUBMITTED').count(),
        open=AttendanceSession.query.filter(AttendanceSession.branch_id.in_(ids), AttendanceSession.approval_status == 'OPEN').count(),
        adjustments=AttendanceAdjustment.query.filter(AttendanceAdjustment.branch_id.in_(ids), AttendanceAdjustment.status == 'PENDING').count(),
        draft_payroll=PayrollPeriod.query.filter(PayrollPeriod.branch_id.in_(ids), PayrollPeriod.status == 'DRAFT').count())


@operations_bp.get('/employee')
@operations_bp.get('/employee/<path:screen>')
@operations_bp.get('/admin/operations')
@operations_bp.get('/admin/operations/<path:screen>')
def portal(screen='attendance'):
    if not current_app.config.get('EMPLOYEE_PORTAL_ENABLED'):
        abort(404)
    from ..ui_assets import portal_assets
    assets = portal_assets('src/main.tsx')
    return render_template('operations/portal.html', **(assets or dict(portal_styles=[], portal_ready=False)))


def register_commands(app):
    @app.cli.command('attendance-purge-gps')
    @click.option('--dry-run', is_flag=True)
    def purge_gps(dry_run):
        """Remove raw coordinates after each event's policy retention; keep decisions/audit."""
        total = 0
        for policy in BranchGeoPolicy.query.all():
            cutoff = att.now_utc() - timedelta(days=policy.settings['retention_days'])
            query = AttendanceEvent.query.filter(AttendanceEvent.policy_id == policy.id,
                AttendanceEvent.server_at < cutoff, AttendanceEvent.latitude.isnot(None))
            total += query.count()
            if not dry_run:
                query.update({AttendanceEvent.latitude: None, AttendanceEvent.longitude: None}, synchronize_session=False)
        if not dry_run:
            db.session.commit()
        click.echo(f'{"Would purge" if dry_run else "Purged"} coordinates: {total}')

    @app.cli.command('operations-init-branch')
    @click.option('--admin-id', type=int, required=True)
    @click.option('--name', default='Bin Spa', show_default=True)
    @click.option('--simple', is_flag=True, help='Bật chấm công tại tọa độ cố định, không cần phân cơ sở/nhân viên.')
    def init_branch(admin_id, name, simple):
        """Create the supplied GPS policy disabled; existing assignments are untouched."""
        actor = db.session.get(NhanVien, admin_id)
        if not actor or actor.role != 'admin' or not actor.trangthai:
            raise click.ClickException('Cần admin đang hoạt động')
        branch = Branch.query.filter_by(name=name).first()
        if branch and not simple:
            raise click.ClickException('Cơ sở đã có; cập nhật chính sách qua giao diện')
        if not branch:
            branch = Branch(name=name, address='')
            db.session.add(branch)
            db.session.flush()
        if simple:
            current_app.config.update(ATTENDANCE_SIMPLE_MODE=True, ATTENDANCE_BRANCH_ID=branch.id)
        att.save_policy(actor, branch.id, dict(att.DEFAULT_POLICY, enabled=simple),
            'Chủ spa chọn chấm công tại tọa độ cố định, bán kính 500 m, sai số tối đa 150 m' if simple else
            'Tọa độ chủ spa cung cấp ngày 14/10/2026; chờ khảo sát GPS')
        db.session.commit()
        click.echo(f'Branch {branch.id}; GPS {"enabled, simple mode" if simple else "disabled until activated"}')

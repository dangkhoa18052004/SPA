"""Opt-in, staff CRM and aggregated recommendation baseline."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g, current_app, abort
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from ..decorators import customer_required, roles_required
from ..extensions import db
from ..models import KhachHang, LichHen, ChiTietLichHen, NotificationJob
from ..services import crm_service as crm, recommendation_metrics as metrics
import click

crm_bp = Blueprint('crm', __name__)


@crm_bp.cli.command('prune-metrics')
@click.option('--days', default=90, type=click.IntRange(30, 365), show_default=True)
@click.option('--dry-run', is_flag=True)
def prune_metrics(days, dry_run):
    """Remove aged recommendation telemetry, never appointment/payment records."""
    from ..models import RecommendationImpression, RecommendationTiming, CustomerBehavior
    cutoff = datetime.utcnow() - timedelta(days=days)
    queries = [RecommendationImpression.query.filter(RecommendationImpression.created_at < cutoff),
        RecommendationTiming.query.filter(RecommendationTiming.created_at < cutoff),
        CustomerBehavior.query.filter(CustomerBehavior.source == 'frontend', CustomerBehavior.created_at < cutoff)]
    counts = [query.count() for query in queries]
    if not dry_run:
        for query in queries:
            query.delete(synchronize_session=False)
        db.session.commit()
    click.echo(f'{"Dry run" if dry_run else "Removed"}: impressions={counts[0]}, timings={counts[1]}, interactions={counts[2]}')


@crm_bp.before_request
def enabled():
    if request.path == '/api/me/communication-preferences' and current_app.config.get('CUSTOMER_CONSENT_ENABLED'):
        return
    flag = 'RECOMMENDATION_METRICS_ENABLED' if '/recommendations/' in request.path else 'CRM_ENABLED'
    if not current_app.config.get(flag):
        abort(404)


@crm_bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization, Cookie'
    return response


@crm_bp.errorhandler(crm.CRMError)
def invalid(error):
    db.session.rollback()
    return jsonify(success=False, message=str(error)), error.status


@crm_bp.errorhandler(IntegrityError)
def concurrent(_error):
    db.session.rollback()
    return jsonify(success=False, message='Dữ liệu vừa thay đổi. Vui lòng tải lại.'), 409


def active_customer():
    if g.current_user.trangthai != 'active':
        raise crm.CRMError('Tài khoản khách hàng không hoạt động', 403)
    return g.current_user


def pagination():
    try:
        page, size = int(request.args.get('page', 1)), int(request.args.get('per_page', 20))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError()
        return page, size
    except ValueError:
        raise crm.CRMError('Phân trang không hợp lệ')


@crm_bp.get('/api/me/communication-preferences')
@customer_required
def get_preferences():
    return jsonify(crm.preferences(active_customer().makh))


@crm_bp.put('/api/me/communication-preferences')
@customer_required
def put_preferences():
    result = crm.save_preferences(active_customer(), request.get_json(silent=True))
    db.session.commit()
    return jsonify(result)


@crm_bp.get('/api/admin/crm/customers')
@roles_required('manager', 'letan')
def customers():
    page, size = pagination()
    return jsonify(crm.customer_rows(request.args.get('segment', ''), request.args.get('q', '').strip()[:100], page, size))


@crm_bp.get('/api/admin/crm/customers/<int:customer_id>')
@roles_required('manager', 'letan')
def customer_history(customer_id):
    customer = db.session.get(KhachHang, customer_id)
    if not customer:
        raise crm.CRMError('Không tìm thấy khách hàng', 404)
    page, size = pagination()
    query = LichHen.query.filter_by(makh=customer_id)
    appointments = query.options(joinedload(LichHen.chitiet).joinedload(ChiTietLichHen.dichvu), joinedload(LichHen.nhanvien))\
        .order_by(LichHen.ngaygio.desc(), LichHen.malh.desc()).offset((page - 1) * size).limit(size).all()
    from .operations_bp import employee_appointment_data
    jobs = NotificationJob.query.filter_by(makh=customer_id).order_by(NotificationJob.id.desc()).limit(20).all()
    return jsonify(customer=dict(id=customer.makh, name=customer.hoten, phone=customer.sdt, email=customer.email),
        preferences=crm.preferences(customer_id), items=[employee_appointment_data(a) for a in appointments],
        page=page, per_page=size, total=query.count(), notifications=[dict(id=j.id, type=j.type, status=j.status,
            scheduled_at=j.scheduled_at.isoformat() + 'Z', sent_at=j.sent_at.isoformat() + 'Z' if j.sent_at else None,
            attempts=j.attempts) for j in jobs])


@crm_bp.post('/api/recommendations/impressions')
@customer_required
def impressions():
    result = metrics.record_impressions(active_customer(), request.get_json(silent=True))
    db.session.commit()
    return jsonify(items=result)


@crm_bp.post('/api/recommendations/impressions/<impression_id>/click')
@customer_required
def click_impression_route(impression_id):
    result = metrics.click_impression(active_customer(), impression_id)
    db.session.commit()
    return jsonify(recorded=result)


@crm_bp.get('/api/admin/recommendations/baseline')
@roles_required('manager')
def baseline():
    from ..services.package_service import local_now
    try:
        today = local_now().date()
        start_day = datetime.strptime(request.args.get('from', (today - timedelta(days=29)).isoformat()), '%Y-%m-%d').date()
        end_day = datetime.strptime(request.args.get('to', today.isoformat()), '%Y-%m-%d').date()
        if end_day < start_day or (end_day - start_day).days > 90:
            raise ValueError()
    except ValueError:
        raise crm.CRMError('Chọn khoảng ngày hợp lệ, tối đa 90 ngày')
    start = datetime.combine(start_day, datetime.min.time()) - timedelta(hours=7)
    end = datetime.combine(end_day + timedelta(days=1), datetime.min.time()) - timedelta(hours=7)
    return jsonify(**metrics.baseline(start, end), from_date=start_day.isoformat(), to_date=end_day.isoformat())

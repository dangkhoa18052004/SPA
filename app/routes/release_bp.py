"""BI and operations visibility. Health probes never contact mail, AI or banking providers."""
import csv
import io
from pathlib import Path
import click
from flask import Blueprint, abort, current_app, request, jsonify, g, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db
from ..decorators import roles_required
from ..models import ReportExportAudit, AuthRateBucket
from ..services import bi_service as bi, runtime_service as runtime
from ..ui_assets import portal_assets

release_bp = Blueprint('release', __name__)


@release_bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@release_bp.errorhandler(bi.ReportError)
def report_error(error):
    db.session.rollback()
    return jsonify(success=False, message=str(error)), error.status


@release_bp.get('/health/live')
def live():
    return jsonify(status='ok')


@release_bp.get('/health/ready')
def ready():
    healthy = True
    try:
        db.session.execute(text('SELECT 1'))
        revision = db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(); cfg.set_main_option('script_location', str(Path(current_app.root_path).parent / 'migrations'))
        healthy = revision == ScriptDirectory.from_config(cfg).get_current_head()
        for flag, source in [('EMPLOYEE_PORTAL_ENABLED', 'src/main.tsx'), ('BUSINESS_PORTAL_ENABLED', 'src/main.tsx'),
                ('CRM_ENABLED', 'src/main.tsx'), ('STAFF_SECURITY_ENABLED', 'src/main.tsx'),
                ('BI_REPORTS_ENABLED', 'src/main.tsx'), ('CUSTOMER_BOOKING_REACT_ENABLED', 'src/booking-main.tsx')]:
            if current_app.config.get(flag):
                assets = portal_assets(source)
                healthy = healthy and bool(assets) and all((Path(current_app.static_folder) / 'portal' / css).is_file() for css in assets['portal_styles'])
    except (SQLAlchemyError, OSError, ValueError):
        db.session.rollback(); healthy = False
    return jsonify(status='ready' if healthy else 'unavailable'), 200 if healthy else 503


@release_bp.get('/api/admin/bi/report')
@roles_required('manager')
def report():
    if not current_app.config.get('BI_REPORTS_ENABLED'): abort(404)
    return jsonify(bi.report(g.current_user, request.args))


@release_bp.get('/api/admin/bi/export.csv')
@roles_required('manager')
def export_report():
    if not current_app.config.get('BI_REPORTS_ENABLED'): abort(404)
    data = bi.report(g.current_user, request.args)
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Từ ngày', 'Đến ngày', 'Phạm vi', 'Chỉ số', 'Giá trị'])
    def row(name, value, scope): writer.writerow([data['from_date'], data['to_date'], scope, name, '' if value is None else value])
    if data['business']:
        b = data['business']
        for key, label in [('total', 'Tổng thực thu'), ('service', 'Thực thu dịch vụ'), ('package', 'Thực thu bán gói')]: row(label, b['revenue'][key], data['business_scope'])
        for key, label in [('total', 'Số lịch hẹn'), ('no_show_recorded', 'Không đến đã ghi nhận')]: row(label, b['appointments'][key], data['business_scope'])
        row('Tỷ lệ khách quay lại (%)', b['customers']['returning_rate'], data['business_scope'])
        row('Retention kỳ trước (%)', b['customers']['retention_rate'], data['business_scope'])
        row('Hoa hồng phát sinh', b['earned_commission'], data['business_scope'])
    w = data['workforce']; scope = ','.join(map(str, data['branch_ids'])) or 'none'
    for key, label in [('approved_minutes', 'Phút công được duyệt'), ('overtime_minutes', 'Phút tăng ca được duyệt'),
            ('locked_payroll', 'Lương các kỳ đã khóa trọn khoảng'), ('locked_commission', 'Hoa hồng trong kỳ lương đã khóa')]: row(label, w[key], scope)
    db.session.add(ReportExportAudit(actor_id=g.current_user.manv, from_date=bi.date_range(request.args)[0], to_date=bi.date_range(request.args)[1],
        branch_ids=data['branch_ids'], business_scope=data['business_scope'], request_id=g.request_id))
    db.session.commit()
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="binspa-bi-{data["from_date"]}-{data["to_date"]}.csv"'})


@release_bp.get('/api/admin/runtime/status')
@roles_required('admin')
def runtime_status():
    # roles_required also permits admins; explicitly exclude managers here.
    if g.current_user.role != 'admin': abort(403)
    if not current_app.config.get('OBSERVABILITY_ENABLED'): abort(404)
    start, end = bi.date_range(request.args)
    branches, _ = bi.scope_for(g.current_user)
    return jsonify(runtime.runtime_snapshot(start, end, branches))


@release_bp.cli.command('prune-auth-limits')
@click.option('--dry-run', is_flag=True)
def prune_auth_limits(dry_run):
    from datetime import datetime, timedelta
    query = AuthRateBucket.query.filter(AuthRateBucket.expires_at < datetime.utcnow() - timedelta(days=1))
    count = query.count()
    if not dry_run:
        query.delete(synchronize_session=False); db.session.commit()
    click.echo(f'{"Dry run" if dry_run else "Removed"}: auth buckets={count}')


@release_bp.cli.command('check')
@click.option('--production', is_flag=True, help='Also check production security configuration, without contacting providers.')
def release_check(production):
    with current_app.test_client() as client:
        response = client.get('/health/ready')
    checks = dict(schema_and_assets=response.status_code == 200)
    if production:
        checks.update(production_environment=current_app.config.get('APP_ENV') == 'production',
            secure_cookies=bool(current_app.config.get('SESSION_COOKIE_SECURE')),
            authentication_limits=bool(current_app.config.get('AUTH_RATE_LIMIT_ENABLED')),
            staff_sensitive_action_mfa=bool(current_app.config.get('STAFF_SECURITY_ENABLED')),
            observability=bool(current_app.config.get('OBSERVABILITY_ENABLED')),
            debug_disabled=not current_app.debug)
    for name, passed in checks.items(): click.echo(f'{"PASS" if passed else "FAIL"} {name}')
    click.echo('Field GPS checks, payroll reconciliation, external-provider smoke checks and deployment signoff require operator evidence.')
    if not all(checks.values()): raise click.ClickException('Release checks have not all passed.')

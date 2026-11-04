from flask import Blueprint, jsonify, current_app
from ..models import DichVu
from ..services.recommendation_metrics import measure

service_bp = Blueprint("service", __name__)


@service_bp.route('/categories', methods=['GET'])
def public_categories():
    """Only persisted, active categories containing publicly available services."""
    from sqlalchemy import func
    from sqlalchemy.exc import SQLAlchemyError
    from ..extensions import db
    from ..models import DanhMucDichVu
    try:
        rows = db.session.query(DanhMucDichVu, func.count(DichVu.madv)).join(
            DichVu, DichVu.category_id == DanhMucDichVu.id).filter(
            DanhMucDichVu.active.is_(True), DichVu.active.is_(True)).group_by(
            DanhMucDichVu.id).order_by(DanhMucDichVu.name, DanhMucDichVu.id).all()
        response = jsonify(success=True, categories=[dict(id=c.id, name=c.name,
            slug=c.slug, service_count=count) for c, count in rows])
        response.headers['Cache-Control'] = 'no-store'
        return response
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Unable to load public categories')
        return jsonify(success=False, message='Không thể tải danh mục dịch vụ'), 503


@service_bp.route('/<int:service_id>/reviews')
def service_reviews(service_id):
    from flask import request
    from ..services.review_service import public_service_reviews, ReviewServiceError
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 10))))
        response = jsonify(public_service_reviews(service_id, page, per_page))
        response.headers['Cache-Control'] = 'no-store'
        return response
    except (ValueError, TypeError):
        return jsonify(success=False, message='Phân trang không hợp lệ'), 400
    except ReviewServiceError as error:
        return jsonify(success=False, message=error.message), error.status_code

@service_bp.route("", methods=["GET"])
@measure('catalog')
def get_services():
    from flask import request
    from flask_jwt_extended import verify_jwt_in_request
    from sqlalchemy.orm import joinedload, defer, undefer
    from sqlalchemy.exc import SQLAlchemyError
    from ..decorators import get_current_user
    from ..extensions import db
    from ..models import DanhMucDichVu
    from ..services.recommendation_service import rank_services_for_customer, serialize_service

    verify_jwt_in_request(optional=True)
    try:
        user, kind = get_current_user()
        if kind == 'customer' and user and user.trangthai != 'active':
            return jsonify(success=False, message='Tài khoản đã ngừng hoạt động'), 403
        customer_id = user.makh if user and kind == 'customer' else None
        # Services without a category remain visible in All. Hidden category
        # metadata must never leak through the public serializer or its filters.
        query = DichVu.query.options(joinedload(DichVu.category)).filter_by(active=True)
        category = request.args.get('category', 'all')
        if category != 'all':
            query = query.join(DanhMucDichVu).filter(
                DanhMucDichVu.active.is_(True), DanhMucDichVu.slug == category)
        from decimal import Decimal, InvalidOperation
        ranges = {}
        try:
            for name in ('min_price', 'max_price', 'min_duration', 'max_duration'):
                raw = request.args.get(name)
                if raw is not None and raw != '':
                    value = Decimal(raw)
                    if not value.is_finite() or value < 0 or value > Decimal('1000000000000'):
                        raise ValueError()
                    ranges[name] = value
            for suffix, column in [('price', DichVu.gia), ('duration', DichVu.thoiluong)]:
                low, high = ranges.get('min_' + suffix), ranges.get('max_' + suffix)
                if low is not None and high is not None and low > high:
                    raise ValueError()
                if low is not None:
                    query = query.filter(column >= low)
                if high is not None:
                    query = query.filter(column <= high)
            paginated = 'page' in request.args or 'per_page' in request.args
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 9))
            if page < 1 or per_page < 1:
                raise ValueError()
            per_page = min(per_page, 100)
        except (ValueError, InvalidOperation, OverflowError):
            return jsonify(success=False, message='Khoảng lọc hoặc phân trang không hợp lệ'), 400
        search = request.args.get('search', '').strip()
        if search:
            # Treat wildcard characters as literal search text.
            escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            query = query.filter(db.or_(DichVu.tendv.ilike('%' + escaped + '%', escape='\\'),
                DichVu.mota.ilike('%' + escaped + '%', escape='\\')))
        if paginated:
            query = query.options(defer(DichVu.anhdichvu))
        candidates = query.all()
        sort = request.args.get('sort', 'default')
        if sort in ('price-asc', 'price-desc'):
            candidates.sort(key=lambda s: (float(s.gia), s.madv), reverse=sort == 'price-desc')
        elif sort in ('name-asc', 'name-desc'):
            candidates.sort(key=lambda s: (s.tendv.casefold(), s.madv), reverse=sort == 'name-desc')
        else:
            candidates = rank_services_for_customer(customer_id, candidates)
        total = len(candidates)
        metadata = {}
        if paginated:
            metadata = dict(page=page, per_page=per_page, total_pages=(total + per_page - 1) // per_page)
            candidates = candidates[(page - 1) * per_page:page * per_page]
            if candidates:
                # Ranking needs metadata for every match, but only this page's
                # binary images. Bulk-fill deferred fields without N+1 reads.
                DichVu.query.options(undefer(DichVu.anhdichvu)).filter(
                    DichVu.madv.in_([service.madv for service in candidates])).all()
        response = jsonify(success=True, services=[serialize_service(s) for s in candidates], total=total, **metadata)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Vary'] = 'Authorization, Cookie'
        return response
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Unable to load service catalog')
        return jsonify(success=False, msg='Không thể lấy danh sách dịch vụ'), 503


@service_bp.route("/<int:service_id>", methods=["GET"])
def get_service_details(service_id):
    from ..services.recommendation_service import serialize_service
    service = DichVu.query.filter_by(madv=service_id, active=True).first()
    if not service:
        return jsonify(success=False, msg='Không tìm thấy dịch vụ'), 404
    return jsonify(success=True, service=dict(serialize_service(service), donvitinh=service.donvitinh, active=service.active))

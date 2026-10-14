from flask import Blueprint, jsonify, current_app
from ..models import DichVu

service_bp = Blueprint("service", __name__)


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
def get_services():
    from flask import request
    from flask_jwt_extended import verify_jwt_in_request
    from sqlalchemy.orm import joinedload
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
        query = DichVu.query.options(joinedload(DichVu.category)).filter_by(active=True)
        category = request.args.get('category', 'all')
        if category != 'all':
            slugs = {'facial': ['facial', 'acne'], 'body': ['body-care']}.get(category, [category])
            query = query.join(DanhMucDichVu).filter(DanhMucDichVu.slug.in_(slugs))
        search = request.args.get('search', '').strip()
        if search:
            # Treat wildcard characters as literal search text.
            escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            query = query.filter(db.or_(DichVu.tendv.ilike('%' + escaped + '%', escape='\\'),
                DichVu.mota.ilike('%' + escaped + '%', escape='\\')))
        candidates = query.all()
        sort = request.args.get('sort', 'default')
        if sort in ('price-asc', 'price-desc'):
            candidates.sort(key=lambda s: (float(s.gia), s.madv), reverse=sort == 'price-desc')
        elif sort in ('name-asc', 'name-desc'):
            candidates.sort(key=lambda s: (s.tendv.casefold(), s.madv), reverse=sort == 'name-desc')
        else:
            candidates = rank_services_for_customer(customer_id, candidates)
        response = jsonify(success=True, services=[serialize_service(s) for s in candidates], total=len(candidates))
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

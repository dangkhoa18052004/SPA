from flask import Blueprint, jsonify, request, g, current_app
from flask_jwt_extended import verify_jwt_in_request
from sqlalchemy.exc import SQLAlchemyError

from ..decorators import customer_required, get_current_user
from ..extensions import db
from ..services.recommendation_service import Ranking, record_client_event, RecommendationError, get_related_recommendations
from ..services.recommendation_metrics import measure

recommendation_bp = Blueprint('recommendations', __name__, url_prefix='/api/recommendations')


@recommendation_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization, Cookie'
    return response


@recommendation_bp.errorhandler(RecommendationError)
def invalid_event(error):
    db.session.rollback()
    response = jsonify(success=False, message=str(error))
    if error.status == 429:
        response.headers['Retry-After'] = '60'
    return response, error.status


@recommendation_bp.errorhandler(SQLAlchemyError)
def unavailable(error):
    db.session.rollback()
    current_app.logger.error('Recommendation database error', exc_info=True)
    return jsonify(success=False, message='Đề xuất tạm thời chưa khả dụng'), 503


@recommendation_bp.route('', methods=['GET'])
@measure('home')
def recommendations():
    verify_jwt_in_request(optional=True)
    user, kind = get_current_user()
    if kind == 'customer' and user and user.trangthai != 'active':
        return jsonify(success=False, message='Tài khoản đã ngừng hoạt động'), 403
    customer_id = user.makh if user and kind == 'customer' else None
    return jsonify(Ranking(customer_id).response())


@recommendation_bp.route('/events', methods=['POST'])
@customer_required
def events():
    if g.current_user.trangthai != 'active':
        return jsonify(success=False, message='Tài khoản đã ngừng hoạt động'), 403
    recorded = record_client_event(g.current_user.makh, request.get_json(silent=True))
    db.session.commit()
    return jsonify(success=True, recorded=recorded), 201 if recorded else 200


@recommendation_bp.route('/related/<int:service_id>', methods=['GET'])
@measure('related')
def related(service_id):
    verify_jwt_in_request(optional=True)
    user, kind = get_current_user()
    if kind == 'customer' and user and user.trangthai != 'active':
        return jsonify(success=False, message='Tài khoản đã ngừng hoạt động'), 403
    customer_id = user.makh if user and kind == 'customer' else None
    return jsonify(get_related_recommendations(customer_id, service_id))

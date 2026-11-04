"""Review and explicitly approve service assignments; proposals never write the database."""
from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import SQLAlchemyError

from ..decorators import roles_required
from ..services import ai_service, skin_service_map_service as service
from ..services.skin_analysis_service import SkinAnalysisError, TYPE_LABELS

skin_service_map_bp = Blueprint('skin_service_map', __name__)


@skin_service_map_bp.after_request
def json_envelope(response):
    if response.is_json:
        body = response.get_json()
        if isinstance(body, dict) and 'success' not in body:
            body['success'] = response.status_code < 400
            response.set_data(jsonify(body).get_data())
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@skin_service_map_bp.route('/skin-service-map', methods=['GET'])
@roles_required('admin', 'manager')
def get_map():
    return jsonify(success=True, **service.current(), types=TYPE_LABELS,
        services=[dict(madv=s.madv, tendv=s.tendv,
                       category_name=s.category.name if s.category and s.category.active else None)
                  for s in service.active_services()])


@skin_service_map_bp.route('/skin-service-map/proposal', methods=['POST'])
@roles_required('admin', 'manager')
def proposal():
    try:
        return jsonify(success=True, **service.propose())
    except ai_service.AINotConfigured:
        return jsonify(success=False, message='Gemini chưa được cấu hình để đề xuất dịch vụ.'), 503
    except ai_service.AIError:
        return jsonify(success=False, message='Chưa lấy được đề xuất từ Gemini. Vui lòng thử lại.'), 502
    except SkinAnalysisError as error:
        return jsonify(success=False, message=error.message), error.status_code


@skin_service_map_bp.route('/skin-service-map', methods=['PUT'])
@roles_required('admin', 'manager')
def save_map():
    body = request.get_json(silent=True)
    if not service.recommendations.mapping_schema_ready():
        return jsonify(success=False, code='schema_not_ready', message='Chưa lưu được cấu hình gợi ý dịch vụ. Cần cập nhật dữ liệu hệ thống trước khi lưu; cấu hình cũ vẫn được giữ nguyên.'), 503
    try:
        service.save(body.get('map') if isinstance(body, dict) else None, g.current_user.manv)
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 400
    except SQLAlchemyError:
        return jsonify(success=False, message='Chưa lưu được map. Map đã duyệt trước đó vẫn được giữ nguyên.'), 500
    result = service.current()
    message = ('Đã lưu và duyệt map dịch vụ.' if result['source'] == 'database' else
               'Đã lưu map rỗng; hệ thống quay về dùng SKIN_SERVICE_MAP trong .env.')
    return jsonify(success=True, **result, message=message)

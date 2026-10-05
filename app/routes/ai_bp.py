"""API trợ lý AI (giai đoạn 5). AI tùy chọn: thiếu GEMINI_API_KEY chỉ tắt các endpoint này."""
from flask import Blueprint, jsonify, request, current_app, g
from flask_jwt_extended import verify_jwt_in_request

from ..decorators import get_current_user, customer_required, roles_required
from ..services import ai_service

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


def _actor():
    """Người gọi hiện tại (khách / nhân viên / ẩn danh). Chỉ id và vai trò; tên chỉ dùng để ẩn khỏi prompt."""
    try:
        verify_jwt_in_request(optional=True)
        user, kind = get_current_user()
    except Exception:
        user, kind = None, None
    if user is None:
        return {'kind': 'anonymous'}
    if kind == 'customer':
        return {'kind': 'customer', 'makh': user.makh, 'name': user.hoten}
    return {'kind': 'staff', 'manv': user.manv, 'role': user.role, 'name': user.hoten}


@ai_bp.errorhandler(ai_service.AIError)
def ai_error(error):
    return jsonify(success=False, msg=error.message, configured=ai_service.is_configured()), error.status_code


@ai_bp.route('/status')
def ai_status():
    return jsonify(success=True, **ai_service.status())


@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    data = request.get_json(silent=True) or {}
    history = data.get('history') if isinstance(data.get('history'), list) else []
    result = ai_service.chat(data.get('message'), history=history, actor=_actor())
    return jsonify(success=True, **result)


@ai_bp.route('/booking/confirm', methods=['POST'])
@customer_required
def ai_booking_confirm():
    """Khách bấm "Xác nhận đặt lịch": tạo đúng một lịch hẹn từ bản nháp của chính mình."""
    draft_id = (request.get_json(silent=True) or {}).get('draft_id')
    if not draft_id:
        return jsonify(success=False, msg='Thiếu draft_id'), 400
    result = ai_service.confirm_booking_tool(draft_id, g.current_user.makh)
    msg = 'Đặt lịch thành công!' if result['created'] else 'Lịch hẹn này đã được xác nhận trước đó.'
    return jsonify(success=True, msg=msg, **result), 201 if result['created'] else 200


@ai_bp.route('/business-summary', methods=['POST'])
@roles_required('admin', 'manager')
def ai_business_summary():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(ai_service.business_summary(data.get('from'), data.get('to'))), 200
    except ValueError:
        return jsonify(success=False, msg='Ngày không hợp lệ (YYYY-MM-DD)'), 400

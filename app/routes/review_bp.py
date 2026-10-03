# app/routes/review_bp.py
"""
Review Blueprint - API đánh giá dịch vụ cho khách hàng và thống kê cho quản trị.
"""

from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..decorators import roles_required
from ..services import review_service
from ..extensions import db
from ..models import KhachHang, DanhGia
from ..services.review_service import (
    ReviewServiceError,
    ReviewNotFoundError,
    ReviewPermissionError,
    ReviewValidationError,
    ReviewConflictError,
)

review_bp = Blueprint("review_bp", __name__)


def _extract_customer_id(identity):
    """Trích xuất mã khách hàng từ JWT identity."""
    if not identity:
        return None
    identity_str = str(identity)
    if ":" in identity_str:
        parts = identity_str.split(":", 1)
        if parts[0] == "customer":
            try:
                return int(parts[1])
            except ValueError:
                return None
        return None
    try:
        return int(identity_str)
    except ValueError:
        return None


@review_bp.route("", methods=["POST"])
@jwt_required()
def create_review_api():
    """Khách hàng gửi đánh giá cho một lịch hẹn đã hoàn thành."""
    identity = get_jwt_identity()
    customer_id = _extract_customer_id(identity)

    if not customer_id:
        return jsonify({"success": False, "message": "Yêu cầu đăng nhập với tài khoản khách hàng"}), 401

    customer_id = active_customer()
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(success=False, message='Dữ liệu đánh giá không hợp lệ'), 400
    malh = data.get("malh")
    rating = data.get("rating")
    comment = data.get("comment")

    if not malh or rating is None:
        return jsonify({"success": False, "message": "Thiếu mã lịch hẹn (malh) hoặc điểm đánh giá (rating)"}), 400
    if isinstance(malh, bool) or not isinstance(malh, (str, int)) or not str(malh).isdigit() or int(malh) <= 0:
        raise ReviewValidationError('Mã lịch hẹn không hợp lệ.')

    try:
        res = review_service.create_review(
            customer_id=customer_id,
            appointment_id=int(malh),
            rating=rating,
            comment=comment,
            service_ids=data.get('service_ids', [data['madv']] if 'madv' in data else None),
        )
        return jsonify(res), 201

    except ReviewNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ReviewPermissionError as e:
        return jsonify({"success": False, "message": e.message}), 403
    except ReviewConflictError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ReviewValidationError as e:
        return jsonify({"success": False, "message": e.message}), 400
    except ReviewServiceError as e:
        return jsonify({"success": False, "message": e.message}), e.status_code
    except (ValueError, TypeError):
        return jsonify(success=False, message='Mã lịch hẹn không hợp lệ'), 400
    except Exception as e:
        current_app.logger.error(f"Lỗi gửi đánh giá: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống khi gửi đánh giá"}), 500


@review_bp.route("/my", methods=["GET"])
@jwt_required()
def get_my_reviews_api():
    """Khách hàng xem lại các đánh giá của bản thân."""
    identity = get_jwt_identity()
    customer_id = _extract_customer_id(identity)

    if not customer_id:
        return jsonify({"success": False, "message": "Yêu cầu đăng nhập tài khoản khách hàng"}), 401

    try:
        customer_id = active_customer()
        res = review_service.get_my_reviews(customer_id)
        return jsonify(res), 200
    except ReviewServiceError:
        raise
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy đánh giá cá nhân: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi lấy danh sách đánh giá"}), 500


@review_bp.route("/staff/<int:manv>", methods=["GET"])
def get_staff_reviews_api(manv):
    """Xem danh sách đánh giá & điểm trung bình của một nhân viên kỹ thuật."""
    try:
        res = review_service.get_staff_reviews(manv)
        return jsonify(res), 200
    except ReviewNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy đánh giá nhân viên {manv}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500


@review_bp.route("/admin/stats", methods=["GET"])
@roles_required("admin", "manager")
def get_admin_review_stats_api():
    """Admin xem thống kê tổng hợp đánh giá."""
    try:
        res = review_service.get_admin_review_stats()
        return jsonify(res), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê review admin: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500


@review_bp.errorhandler(ReviewServiceError)
def review_error(error):
    db.session.rollback()
    return jsonify(success=False, message=error.message), error.status_code


def active_customer():
    customer_id = _extract_customer_id(get_jwt_identity())
    customer = db.session.get(KhachHang, customer_id) if customer_id else None
    if not customer or customer.trangthai != 'active':
        raise ReviewPermissionError('Bạn không có quyền truy cập. Vui lòng đăng nhập bằng tài khoản khách hàng đang hoạt động.')
    return customer.makh


@review_bp.route('/<int:review_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def customer_review(review_id):
    customer_id = active_customer()
    if request.method == 'DELETE':
        review_service.delete_review(review_id, customer_id)
        return jsonify(success=True)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ReviewValidationError('Dữ liệu đánh giá không hợp lệ.')
    return jsonify(success=True, review=review_service.update_review(review_id, customer_id, data))


@review_bp.route('/appointments/<int:appointment_id>/context')
@jwt_required()
def review_context(appointment_id):
    customer_id = active_customer()
    apt = review_service.completed_appointment(customer_id, appointment_id)
    existing = DanhGia.query.filter_by(malh=appointment_id).first()
    return jsonify(success=True, malh=apt.malh,
        services=[dict(madv=d.madv, tendv=d.dichvu.tendv) for d in apt.chitiet if d.dichvu],
        review=review_service.serialize_review(existing) if existing else None)


@review_bp.route('/manage')
@roles_required('admin', 'manager', 'staff')
def manage_reviews_api():
    try:
        return jsonify(review_service.manage_reviews(g.current_user, request.args))
    except (ValueError, TypeError):
        raise ReviewValidationError('Bộ lọc đánh giá không hợp lệ.')


@review_bp.route('/<int:review_id>/reply', methods=['POST', 'PUT', 'DELETE'])
@roles_required('admin', 'manager', 'staff')
def official_reply(review_id):
    if request.method == 'DELETE':
        review = db.session.get(DanhGia, review_id)
        if not review:
            raise ReviewNotFoundError()
        review_service.staff_review_permission(review, g.current_user)
        if review.reply:
            db.session.delete(review.reply)
            db.session.commit()
        return jsonify(success=True)
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ReviewValidationError('Nội dung phản hồi không hợp lệ.')
    return jsonify(success=True, review=review_service.save_reply(review_id, g.current_user, data.get('content')))

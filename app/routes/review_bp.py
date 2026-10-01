# app/routes/review_bp.py
"""
Review Blueprint - API đánh giá dịch vụ cho khách hàng và thống kê cho quản trị.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..decorators import roles_required
from ..services import review_service
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

    data = request.get_json() or {}
    malh = data.get("malh")
    rating = data.get("rating")
    comment = data.get("comment")

    if not malh or rating is None:
        return jsonify({"success": False, "message": "Thiếu mã lịch hẹn (malh) hoặc điểm đánh giá (rating)"}), 400

    try:
        res = review_service.create_review(
            customer_id=customer_id,
            appointment_id=int(malh),
            rating=rating,
            comment=comment,
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
        res = review_service.get_my_reviews(customer_id)
        return jsonify(res), 200
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

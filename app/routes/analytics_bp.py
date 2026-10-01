# app/routes/analytics_bp.py
"""
Analytics Blueprint - Cung cấp API báo cáo, biểu đồ Chart.js và KPI cho Spa.
"""

from flask import Blueprint, request, jsonify, current_app
from ..decorators import roles_required
from ..services import analytics_service

analytics_bp = Blueprint("analytics_bp", __name__)


@analytics_bp.route("/revenue-timeseries", methods=["GET"])
@roles_required("admin", "manager")
def get_revenue_timeseries():
    """Lấy dữ liệu doanh thu theo ngày hoặc tháng cho biểu đồ đường."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    group_by = request.args.get("group_by", "day").lower()

    if group_by not in ("day", "month"):
        group_by = "day"

    try:
        data = analytics_service.revenue_timeseries(from_date, to_date, group_by=group_by)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy revenue timeseries: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi lấy dữ liệu doanh thu"}), 500


@analytics_bp.route("/appointment-stats", methods=["GET"])
@roles_required("admin", "manager", "letan")
def get_appointment_stats():
    """Lấy thống kê trạng thái lịch hẹn cho biểu đồ tròn (Doughnut)."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    try:
        data = analytics_service.appointment_stats(from_date, to_date)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy appointment stats: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi lấy thống kê lịch hẹn"}), 500


@analytics_bp.route("/average-invoice", methods=["GET"])
@roles_required("admin", "manager")
def get_average_invoice():
    """Lấy giá trị thanh toán trung bình (AOV)."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    try:
        data = analytics_service.average_invoice(from_date, to_date)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy average invoice: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi tính giá trị trung bình"}), 500


@analytics_bp.route("/top-services", methods=["GET"])
@roles_required("admin", "manager", "letan")
def get_top_services():
    """Lấy top các dịch vụ được đặt nhiều nhất."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    limit_str = request.args.get("limit", "5")

    try:
        limit = int(limit_str)
    except ValueError:
        limit = 5

    try:
        data = analytics_service.top_services(from_date, to_date, limit=limit)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy top services: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi lấy top dịch vụ"}), 500


@analytics_bp.route("/new-customers", methods=["GET"])
@roles_required("admin", "manager")
def get_new_customers():
    """Lấy số lượng khách hàng mới đăng ký."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    try:
        data = analytics_service.new_customers(from_date, to_date)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy new customers: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi lấy dữ liệu khách hàng mới"}), 500


@analytics_bp.route("/kpi-cards", methods=["GET"])
@roles_required("admin", "manager")
def get_kpi_cards():
    """Lấy tổng hợp KPI Cards cho Admin Dashboard."""
    target_date = request.args.get("date")

    try:
        data = analytics_service.get_kpi_cards(target_date)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy KPI cards: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Lỗi tính toán chỉ số KPI"}), 500

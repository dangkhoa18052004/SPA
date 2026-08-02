from flask import Blueprint, request, jsonify, current_app, g
from ..extensions import db
from ..models import HoaDon, ThanhToan
from ..decorators import customer_required
from ..services import momo_service, vietqr_service # Import service
from datetime import datetime
import requests

payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")

@payment_bp.route("/invoices", methods=["GET"])
@customer_required 
def get_my_invoices():
    """(Customer) Lấy lịch sử hóa đơn."""
    customer = g.current_user
    try:
        invoices = HoaDon.query.filter_by(makh=customer.makh).order_by(HoaDon.ngaylap.desc()).all()
        result = [{"mahd": inv.mahd, "ngaylap": inv.ngaylap.isoformat(), "tongtien": str(inv.tongtien), "trangthai": inv.trangthai} for inv in invoices]
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy hóa đơn: {e}")
        return jsonify({"msg": "Lỗi máy chủ nội bộ"}), 500

@payment_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@customer_required
def get_my_invoice_details(invoice_id):
    """(Customer) Lấy chi tiết một hóa đơn."""
    customer = g.current_user
    try:
        invoice = HoaDon.query.filter_by(mahd=invoice_id, makh=customer.makh).first()
        if not invoice: return jsonify({"msg": "Không tìm thấy hóa đơn hoặc bạn không có quyền xem"}), 404
        details = [{"tendv": item.dichvu.tendv, "soluong": item.soluong, "dongia": str(item.dongia), "thanhtien": str(item.thanhtien)} for item in invoice.chitiet]
        return jsonify({"mahd": invoice.mahd, "ngaylap": invoice.ngaylap.isoformat(), "tongtien": str(invoice.tongtien), "trangthai": invoice.trangthai, "chitiet": details}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy chi tiết hóa đơn: {e}")
        return jsonify({"msg": "Lỗi máy chủ nội bộ"}), 500

@payment_bp.route("/invoices/<int:invoice_id>/pay-online", methods=["POST"])
@customer_required
def pay_for_invoice_online(invoice_id):
    """(Customer) Tự thanh toán hóa đơn online (Giả lập)."""

    customer = g.current_user
    data = request.get_json()
    try: sotien_thanh_toan = float(data.get("sotien"))
    except (ValueError, TypeError): return jsonify({"msg": "Số tiền không hợp lệ"}), 400
    phuongthuc = data.get("phuongthuc", "Online")

    invoice = HoaDon.query.filter_by(mahd=invoice_id, makh=customer.makh).first()
    if not invoice: return jsonify({"msg": "Không tìm thấy hóa đơn hoặc bạn không có quyền"}), 404
    if invoice.trangthai == 'Đã thanh toán': return jsonify({"msg": "Hóa đơn này đã được thanh toán xong"}), 400
    if sotien_thanh_toan < float(invoice.tongtien): return jsonify({"msg": "Số tiền thanh toán không đủ"}), 400

    try:
        new_payment = ThanhToan(mahd=invoice_id, sotien=sotien_thanh_toan, phuongthuc=phuongthuc, ngaythanhtoan=datetime.utcnow())
        invoice.trangthai = 'Đã thanh toán'
        db.session.add(new_payment)
        db.session.commit()
        return jsonify({"msg": "Thanh toán thành công!"}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi thanh toán: {e}")
        return jsonify({"msg": "Thanh toán thất bại"}), 500

@payment_bp.route("/webhook/sepay", methods=["POST"])
def sepay_payment_webhook():
    """(Hệ thống) Nhận tín hiệu chuyển khoản tự động (Webhook) từ SePay."""
    data = request.get_json() or {}
    auth_header = request.headers.get("Authorization")
    current_app.logger.info(f"SePay Webhook Received: {data}")
    
    try:
        res = vietqr_service.process_sepay_webhook(data, auth_header)
        return jsonify(res), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"SePay Webhook Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@payment_bp.route("/webhook/momo", methods=["POST"])
def momo_payment_webhook():
    """(Hệ thống) Nhận tín hiệu (IPN) từ Momo Sandbox."""
    data = request.get_json()
    current_app.logger.info(f"Momo Webhook Received: {data}")
    if not data: return jsonify({"status": "error", "message": "No data received"}), 400
    
    try:
        # Xác thực chữ ký
        is_valid = momo_service.verify_momo_webhook(data)
        if not is_valid:
            current_app.logger.error("Momo Webhook: Invalid signature!")
            return jsonify({"resultCode": 99, "message": "Invalid signature"}), 400
        
        #ghi nhận thanh toán
        momo_service.process_momo_webhook(data)
        
        # 3. Phản hồi cho Momo
        return jsonify({
            "partnerCode": data.get('partnerCode'), 
            "requestId": data.get('requestId'), 
            "orderId": data.get('orderId'), 
            "resultCode": 0, "message":"Success"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Momo Webhook: Error processing webhook: {e}", exc_info=True)
        return jsonify({"resultCode": 99, "message": "Server error"}), 500
    
@payment_bp.route("/invoices/<int:invoice_id>/generate-qr", methods=["POST"])
@customer_required
def generate_customer_payment_qr(invoice_id):
    """(Customer) Tạo mã VietQR thanh toán hóa đơn qua ngân hàng."""
    customer = g.current_user
    
    invoice = HoaDon.query.filter_by(mahd=invoice_id, makh=customer.makh).first()
    if not invoice: return jsonify({"msg": "Không tìm thấy hóa đơn hoặc bạn không có quyền"}), 404
    if invoice.trangthai == 'Đã thanh toán': return jsonify({"msg": "Hóa đơn đã thanh toán"}), 400
    
    try:
        vietqr_data = vietqr_service.generate_vietqr_info(invoice)
        return jsonify({
            "msg": "Tạo mã VietQR thành công.", 
            "qrCodeUrl": vietqr_data["qrCodeUrl"],
            "bank": vietqr_data["bank_id"],
            "accountNo": vietqr_data["account_no"],
            "accountName": vietqr_data["account_name"],
            "description": vietqr_data["description"],
            "amount": vietqr_data["amount"]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi tạo mã VietQR: {str(e)}", exc_info=True)
        return jsonify({"msg": f"Không thể tạo mã VietQR: {str(e)}"}), 500
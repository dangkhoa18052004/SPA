import requests
from flask import Blueprint, request, jsonify, current_app, g
from ..extensions import db
from ..models import HoaDon, LichHen, ChiTietHoaDon, ThanhToan
from ..decorators import roles_required
from ..services import momo_service
from sqlalchemy import func
from datetime import datetime, date
from sqlalchemy.sql.expression import case

invoice_manage_bp = Blueprint("invoice_manage", __name__)

@invoice_manage_bp.route("/payment-webhook", methods=["POST"])
def momo_webhook():
    """Nhận webhook từ Momo"""
    try:
        data = request.get_json()
        current_app.logger.info(f"Received Momo webhook: {data}")
        
        # Xác thực chữ ký
        if not momo_service.verify_momo_webhook(data):
            return jsonify({"msg": "Invalid signature"}), 403
        
        # Xử lý webhook
        momo_service.process_momo_webhook(data)
        
        return jsonify({"msg": "Success"}), 200
    except Exception as e:
        current_app.logger.error(f"Webhook error: {e}")
        return jsonify({"msg": "Error"}), 500

@invoice_manage_bp.route("/appointments/<int:appointment_id>/create-invoice", methods=["POST"])
@roles_required('letan', 'manager', 'admin')
def create_invoice_from_appointment(appointment_id):

    staff = g.current_user
    appointment = LichHen.query.get(appointment_id)
    if not appointment: return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
    if appointment.trangthai != 'Đã hoàn thành' and appointment.trangthai != 'completed': 
        return jsonify({"msg": "Chỉ có thể tạo hóa đơn từ lịch hẹn đã hoàn thành"}), 400
        
    if HoaDon.query.filter_by(malh=appointment_id).first(): 
        return jsonify({"msg": "Hóa đơn cho lịch hẹn này đã tồn tại"}), 400
    try:
        total_price = sum(detail.dichvu.gia for detail in appointment.chitiet if detail.dichvu)
        new_invoice = HoaDon(makh=appointment.makh, manv=staff.manv, tongtien=total_price, trangthai='Chưa thanh toán', malh=appointment_id)
        db.session.add(new_invoice)
        db.session.flush() 
        for detail in appointment.chitiet:
            if detail.dichvu:
                new_invoice_detail = ChiTietHoaDon(mahd=new_invoice.mahd, madv=detail.madv, soluong=1, dongia=detail.dichvu.gia, thanhtien=detail.dichvu.gia)
                db.session.add(new_invoice_detail)
        db.session.commit()
        return jsonify({"msg": "Tạo hóa đơn thành công!", "invoice_id": new_invoice.mahd}), 201
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi tạo hóa đơn: {e}"); return jsonify({"msg": "Tạo hóa đơn thất bại"}), 500

@invoice_manage_bp.route("/invoices/<int:invoice_id>/record-payment", methods=["POST"])
@roles_required('letan','staff', 'manager', 'admin')
def record_payment(invoice_id):

    invoice = HoaDon.query.get(invoice_id);
    if not invoice: return jsonify({"msg": "Không tìm thấy hóa đơn"}), 404
    if invoice.trangthai == 'Đã thanh toán': return jsonify({"msg": "Hóa đơn này đã được thanh toán rồi"}), 400
    data = request.get_json()
    try: sotien_nhan_duoc = float(data.get("sotien"))
    except (ValueError, TypeError): return jsonify({"msg": "Số tiền không hợp lệ"}), 400
    phuongthuc = data.get("phuongthuc")
    if phuongthuc != "Tiền mặt": return jsonify({"msg": "Chỉ chấp nhận phương thức 'Tiền mặt'."}), 400
    if sotien_nhan_duoc < float(invoice.tongtien): return jsonify({"msg": "Số tiền nhận được không đủ"}), 400
    try:
        new_payment = ThanhToan(mahd=invoice_id, sotien=invoice.tongtien, phuongthuc="Tiền mặt")
        invoice.trangthai = 'Đã thanh toán'; db.session.add(new_payment); db.session.commit()
        return jsonify({"msg": f"Đã ghi nhận thanh toán thành công cho hóa đơn #{invoice_id}"}), 201
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi ghi nhận thanh toán: {e}"); return jsonify({"msg": "Ghi nhận thất bại"}), 500

@invoice_manage_bp.route("/invoices/<int:invoice_id>/generate-qr", methods=["POST"])
@roles_required('letan', 'manager', 'admin')
def generate_payment_qr(invoice_id):

    invoice = HoaDon.query.get(invoice_id)
    if not invoice: return jsonify({"msg": "Không tìm thấy hóa đơn"}), 404
    if invoice.trangthai == 'Đã thanh toán': return jsonify({"msg": "Hóa đơn đã thanh toán"}), 400
    
    try:
        momo_response = momo_service.create_momo_payment_link(invoice)
        return jsonify({
            "msg": "Tạo link thanh toán Momo thành công.", 
            "payUrl": momo_response.get("payUrl"),
            "qrCodeUrl": momo_response.get("qrCodeUrl")
        }), 200
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Lỗi gọi API Momo: {str(e)}")
        return jsonify({"msg": f"Lỗi kết nối đến Momo: {str(e)}"}), 503
    except Exception as e:
        current_app.logger.error(f"Lỗi khi tạo mã QR Momo: {str(e)}", exc_info=True)
        return jsonify({"msg": f"Không thể tạo mã QR Momo: {str(e)}"}), 500
    
@invoice_manage_bp.route("/invoices", methods=["GET"])
@roles_required('letan', 'manager', 'admin')
def get_all_invoices():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        status_filter = request.args.get('status')
        search_term = request.args.get('search', '').lower()

        date_column = None
        for attr in ['ngaylap', 'ngaytao', 'created_at', 'date_created']:
            if hasattr(HoaDon, attr):
                date_column = getattr(HoaDon, attr)
                break
        
        base_query = HoaDon.query
        
        if date_column:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                base_query = base_query.filter(func.date(date_column) >= start_date)
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                base_query = base_query.filter(func.date(date_column) <= end_date)
        stats_query = base_query.with_entities(
            func.count().label('total_count'),
            func.sum(case((HoaDon.trangthai == 'Đã thanh toán', 1), else_=0)).label('paid_count'),
            func.sum(case((HoaDon.trangthai == 'Chưa thanh toán', 1), else_=0)).label('unpaid_count'),
            func.sum(case((HoaDon.trangthai == 'Đã thanh toán', HoaDon.tongtien), else_=0)).label('total_revenue')
        ).one_or_none()
        
        stats = {
            "total": stats_query.total_count if stats_query and stats_query.total_count is not None else 0,
            "paid": stats_query.paid_count if stats_query and stats_query.paid_count is not None else 0,
            "unpaid": stats_query.unpaid_count if stats_query and stats_query.unpaid_count is not None else 0,
            "revenue": str(stats_query.total_revenue) if stats_query and stats_query.total_revenue is not None else "0"
        }

        invoices_list_query = base_query.order_by(HoaDon.mahd.desc())
        if status_filter and status_filter != 'all':
            invoices_list_query = invoices_list_query.filter(HoaDon.trangthai == status_filter)
        invoices = invoices_list_query.all()
        
        result = []
        for inv in invoices:
            customer_name = inv.khachhang.hoten if inv.khachhang else "N/A"
            date_field = getattr(inv, date_column.key) if date_column else None
            if search_term and not (search_term in customer_name.lower() or search_term in str(inv.mahd).lower() or search_term in str(inv.malh or '').lower()):
                continue

            result.append({
                "mahd": inv.mahd,
                "malh": inv.malh,
                "khachhang_hoten": customer_name,
                "tongtien": str(inv.tongtien),
                "trangthai": inv.trangthai,
                "ngaytao": date_field.isoformat() if date_field else None
            })
        
        return jsonify({"success": True, "invoices": result, "stats": stats}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi lấy danh sách hóa đơn: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống"}), 500
    
@invoice_manage_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@roles_required('letan', 'manager', 'admin')
def get_invoice_detail(invoice_id):
    """Lấy chi tiết một hóa đơn."""
    try:
        invoice = HoaDon.query.get(invoice_id)
        if not invoice:
            return jsonify({"msg": "Không tìm thấy hóa đơn"}), 404
        
        # Lấy chi tiết dịch vụ
        details = [{
            "tendv": item.dichvu.tendv if item.dichvu else "Dịch vụ không xác định", 
            "soluong": item.soluong, 
            "dongia": str(item.dongia), 
            "thanhtien": str(item.thanhtien)
        } for item in invoice.chitiet]
        
        # Lấy ngày tạo
        date_field = None
        for attr in ['ngaylap', 'ngaytao', 'created_at', 'date_created']:
            if hasattr(invoice, attr):
                date_field = getattr(invoice, attr)
                break

        response_data = {
            "mahd": invoice.mahd,
            "malh": invoice.malh,
            "khachhang_hoten": invoice.khachhang.hoten if invoice.khachhang else "N/A",
            "tongtien": str(invoice.tongtien),
            "trangthai": invoice.trangthai,
            "ngaytao": date_field.isoformat() if date_field else None,
            "chitiet": details # Dữ liệu chi tiết cần cho frontend
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy chi tiết hóa đơn: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống khi tải chi tiết hóa đơn"}), 500
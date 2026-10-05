from app.services import vietqr_service
from flask import Blueprint, request, jsonify, current_app, g
from ..extensions import db
from ..models import HoaDon, LichHen, ChiTietHoaDon, ThanhToan
from ..decorators import roles_required
from ..services import momo_service, sepay_sync_service
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, InvalidOperation
import json
from sqlalchemy import func
from datetime import datetime, date
from ..services import loyalty_service as loyalty
from sqlalchemy.sql.expression import case

invoice_manage_bp = Blueprint("invoice_manage", __name__)

@invoice_manage_bp.route("/payment-webhook", methods=["POST"])
def momo_webhook():
    """Nhận webhook từ Momo"""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"msg": "No data received"}), 400
        
        # Xác thực chữ ký
        if not momo_service.verify_momo_webhook(data):
            return jsonify({"msg": "Invalid signature"}), 403
        
        # Xử lý webhook
        result = momo_service.process_momo_webhook(data)
        
        return jsonify({"msg": "Success", "status": result.get("status")}), 200
    except (ValueError, TypeError) as e:
        db.session.rollback()
        return jsonify({"msg": str(e)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.error("MoMo admin webhook processing failed", exc_info=True)
        return jsonify({"msg": "Error"}), 500

@invoice_manage_bp.route("/appointments/<int:appointment_id>/create-invoice", methods=["POST"])
@roles_required('letan', 'manager', 'admin')
def create_invoice_from_appointment(appointment_id):

    staff = g.current_user
    appointment = LichHen.query.get(appointment_id)
    if not appointment: return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
    if appointment.trangthai != 'Đã hoàn thành' and appointment.trangthai != 'completed': 
        return jsonify({"msg": "Chỉ có thể tạo hóa đơn từ lịch hẹn đã hoàn thành"}), 400
        
    existing = HoaDon.query.filter_by(malh=appointment_id).first()
    if existing:
        return existing_invoice_response(existing)
    try:
        from ..models import LieuTrinhUsage
        covered = {u.madv for u in LieuTrinhUsage.query.filter_by(malh=appointment_id, state='consumed').all()}
        billable = [d for d in appointment.chitiet if d.dichvu and d.madv not in covered]
        if not billable:
            return jsonify({'msg':'Lịch hẹn đã được thanh toán bằng liệu trình; không cần hóa đơn mới'}), 400
        total_price = sum(detail.dichvu.gia for detail in billable)
        # pyrefly: ignore [unexpected-keyword]
        new_invoice = HoaDon(makh=appointment.makh, manv=staff.manv, tongtien=total_price, trangthai='Chưa thanh toán', malh=appointment_id)
        db.session.add(new_invoice)
        db.session.flush() 
        for detail in billable:
            if detail.dichvu:
                # pyrefly: ignore [unexpected-keyword]
                new_invoice_detail = ChiTietHoaDon(mahd=new_invoice.mahd, madv=detail.madv, soluong=1, dongia=detail.dichvu.gia, thanhtien=detail.dichvu.gia)
                db.session.add(new_invoice_detail)
        db.session.commit()
        return jsonify({"msg": "Tạo hóa đơn thành công!", "invoice_id": new_invoice.mahd}), 201
    except IntegrityError:
        db.session.rollback()
        existing = HoaDon.query.filter_by(malh=appointment_id).first()
        if existing:
            return existing_invoice_response(existing)
        raise
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi tạo hóa đơn: {e}"); return jsonify({"msg": "Tạo hóa đơn thất bại"}), 500

@invoice_manage_bp.route("/invoices/<int:invoice_id>/record-payment", methods=["POST"])
@roles_required('letan','staff', 'manager', 'admin')
def record_payment(invoice_id):
    data = request.get_json(silent=True) or {}
    try: sotien_nhan_duoc = Decimal(str(data.get("sotien")))
    except (InvalidOperation, ValueError, TypeError): return jsonify({"msg": "Số tiền không hợp lệ"}), 400
    phuongthuc = data.get("phuongthuc")
    if phuongthuc != "Tiền mặt": return jsonify({"msg": "Chỉ chấp nhận phương thức 'Tiền mặt'."}), 400
    try:
        invoice = loyalty.lock_target('service_invoice', invoice_id)
        if invoice.trangthai == 'Đã thanh toán':
            db.session.rollback()
            return jsonify({"msg": "Hóa đơn này đã được thanh toán rồi"}), 400
        loyalty.require_unpaid(invoice)
        if not sotien_nhan_duoc.is_finite() or sotien_nhan_duoc < loyalty.payable(invoice):
            db.session.rollback()
            return jsonify({"msg": "Số tiền nhận được không đủ"}), 400
        if loyalty.payable(invoice) == 0:
            raise loyalty.LoyaltyError('Vui lòng chọn Thanh toán bằng điểm')
        from ..services.payment_webhook_service import claim_invoice_payment
        if not claim_invoice_payment(invoice_id):
            db.session.rollback()
            return jsonify({"msg": "Hóa đơn đã được thanh toán."}), 409
        new_payment = ThanhToan(mahd=invoice_id, sotien=loyalty.payable(invoice), phuongthuc="Tiền mặt",
                               ghichu=json.dumps({"cash_received": str(sotien_nhan_duoc)}))
        invoice.trangthai = 'Đã thanh toán'
        db.session.add(new_payment)
        loyalty.finalize_payment(invoice)
        db.session.commit()
        return jsonify({"msg": f"Đã ghi nhận thanh toán thành công cho hóa đơn #{invoice_id}"}), 201
    except loyalty.LoyaltyError as error:
        db.session.rollback()
        return jsonify(msg=str(error)), 400
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi ghi nhận thanh toán: {e}"); return jsonify({"msg": "Ghi nhận thất bại"}), 500

@invoice_manage_bp.route("/invoices/<int:invoice_id>/generate-qr", methods=["POST"])
@roles_required('letan', 'manager', 'admin')
def generate_payment_qr(invoice_id):

    invoice = HoaDon.query.get(invoice_id)
    if not invoice: return jsonify({"msg": "Không tìm thấy hóa đơn"}), 404
    if invoice.trangthai == 'Đã thanh toán': return jsonify({"msg": "Hóa đơn đã thanh toán"}), 400
    if loyalty.payable(invoice) == 0: return jsonify(msg='Vui lòng chọn Thanh toán bằng điểm'), 400
    
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
            func.sum(case((HoaDon.trangthai == 'Đã thanh toán', HoaDon.payable_amount), else_=0)).label('total_revenue')
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
                **loyalty.payment_summary(inv),
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
        if (db.session.get(HoaDon, invoice_id) or HoaDon()).trangthai == 'Chưa thanh toán' and sepay_sync_service.maybe_sync():
            db.session.expire_all()
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
            "makh": invoice.makh,
            **loyalty.payment_summary(invoice),
            "malh": invoice.malh,
            "khachhang_hoten": invoice.khachhang.hoten if invoice.khachhang else "N/A",
            "tongtien": str(invoice.tongtien),
            "trangthai": invoice.trangthai,
            "ngaytao": date_field.isoformat() if date_field else None,
            "thanhtoan": [{"phuongthuc": payment.phuongthuc,
                           "ngaythanhtoan": payment.ngaythanhtoan.isoformat() if payment.ngaythanhtoan else None}
                          for payment in invoice.thanhtoan],
            "chitiet": details
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy chi tiết hóa đơn: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống khi tải chi tiết hóa đơn"}), 500


def existing_invoice_response(invoice):
    return jsonify({"success": False, "code": "INVOICE_ALREADY_EXISTS",
                    "invoice_id": invoice.mahd, "invoice_status": invoice.trangthai,
                    "invoice": {"mahd": invoice.mahd, "trangthai": invoice.trangthai, "tongtien": str(invoice.tongtien)},
                    "msg": "Hóa đơn đã tồn tại"}), 409


@invoice_manage_bp.route('/billing/transactions', methods=['GET'])
@roles_required('letan', 'manager', 'admin')
def billing_transactions():
    from ..services.billing_service import transactions
    try:
        rows, stats = transactions(request.args)
        return jsonify(success=True, transactions=rows, stats=stats)
    except ValueError as error:
        return jsonify(success=False, msg=str(error)), 400


@invoice_manage_bp.route('/billing/transactions/<kind>/<int:record_id>', methods=['GET'])
@roles_required('letan', 'manager', 'admin')
def billing_transaction_detail(kind, record_id):
    from ..services import billing_service as billing
    if sepay_sync_service.maybe_sync():
        db.session.expire_all()
    if kind == 'service':
        record = billing.service_query().filter_by(mahd=record_id).first()
        serializer = billing.serialize_service
    elif kind == 'package':
        record = billing.package_query().filter_by(id=record_id).first()
        serializer = billing.serialize_package
    else:
        return jsonify(success=False, msg='Loại hóa đơn không hợp lệ'), 404
    if not record:
        return jsonify(success=False, msg='Không tìm thấy phiếu'), 404
    return jsonify(success=True, transaction=serializer(record))

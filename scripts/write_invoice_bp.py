"""Script to rewrite invoice_manage_bp.py with fixed invoice flow."""
import pathlib

target = pathlib.Path(__file__).parent.parent / "app" / "admin" / "invoice_manage_bp.py"

content = '''\
from app.services import vietqr_service
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
    """Nhan webhook tu Momo"""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"msg": "No data received"}), 400
        if not momo_service.verify_momo_webhook(data):
            return jsonify({"msg": "Invalid signature"}), 403
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
    """Tao hoa don cho lich hen da hoan thanh.

    Neu hoa don da ton tai:
        - Tra HTTP 409 kem invoice_id va invoice_status
        - Frontend dung de mo lai modal thanh toan (khong phai dead-end error)

    Neu thanh cong: tra 201 kem invoice_id.
    """
    staff = g.current_user
    appointment = LichHen.query.get(appointment_id)
    if not appointment:
        return jsonify({"success": False, "msg": "Khong tim thay lich hen"}), 404

    completed_statuses = ('completed',)
    if appointment.trangthai not in completed_statuses:
        return jsonify({"success": False, "msg": "Chi co the tao hoa don tu lich hen da hoan thanh"}), 400

    # Kiem tra da ton tai -> tra 409 voi du lieu de frontend mo lai modal
    existing = HoaDon.query.filter_by(malh=appointment_id).first()
    if existing:
        return jsonify({
            "success": False,
            "code": "INVOICE_ALREADY_EXISTS",
            "invoice_id": existing.mahd,
            "invoice_status": existing.trangthai,
            "msg": "Hoa don da ton tai",
        }), 409

    try:
        from ..models import LieuTrinhUsage
        covered = {
            u.madv for u in LieuTrinhUsage.query.filter_by(
                malh=appointment_id, state='consumed'
            ).all()
        }
        billable = [d for d in appointment.chitiet if d.dichvu and d.madv not in covered]
        if not billable:
            return jsonify({
                'success': False,
                'msg': 'Lich hen da duoc thanh toan bang lieu trinh; khong can hoa don moi',
            }), 400

        total_price = sum(detail.dichvu.gia for detail in billable)
        new_invoice = HoaDon(
            makh=appointment.makh,
            manv=staff.manv,
            tongtien=total_price,
            trangthai='Chua thanh toan',
            malh=appointment_id,
        )
        db.session.add(new_invoice)
        db.session.flush()
        for detail in billable:
            if detail.dichvu:
                db.session.add(ChiTietHoaDon(
                    mahd=new_invoice.mahd, madv=detail.madv,
                    soluong=1, dongia=detail.dichvu.gia, thanhtien=detail.dichvu.gia,
                ))
        db.session.commit()
        return jsonify({
            "success": True,
            "msg": "Tao hoa don thanh cong!",
            "invoice_id": new_invoice.mahd,
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Loi khi tao hoa don: {e}")
        return jsonify({"success": False, "msg": "Tao hoa don that bai"}), 500


@invoice_manage_bp.route("/appointments/<int:appointment_id>/invoice", methods=["GET"])
@roles_required('letan', 'manager', 'admin', 'staff')
def get_invoice_by_appointment(appointment_id):
    """Lay thong tin hoa don cua mot lich hen (neu co).

    Response:
        { "success": true, "invoice": { mahd, malh, tongtien, trangthai } }
    hoac:
        { "success": true, "invoice": null }  (neu chua co)

    Dung de frontend kiem tra trang thai sau khi reload trang ma khong can N+1 request.
    """
    try:
        inv = HoaDon.query.filter_by(malh=appointment_id).first()
        if not inv:
            return jsonify({"success": True, "invoice": None}), 200
        return jsonify({"success": True, "invoice": {
            "mahd": inv.mahd,
            "malh": inv.malh,
            "tongtien": str(inv.tongtien),
            "trangthai": inv.trangthai,
        }}), 200
    except Exception as e:
        current_app.logger.error(f"Loi lay hoa don theo lich hen {appointment_id}: {e}", exc_info=True)
        return jsonify({"success": False, "msg": "Loi he thong"}), 500


@invoice_manage_bp.route("/invoices/<int:invoice_id>/record-payment", methods=["POST"])
@roles_required('letan', 'staff', 'manager', 'admin')
def record_payment(invoice_id):
    """Ghi nhan thanh toan tien mat.

    Idempotent:
        - Neu hoa don da thanh toan: tra 200 voi already_paid=True.
          Frontend xu ly nhu thanh cong (tranh dead-end neu double-click).
        - Khong tao ThanhToan thu hai cho cung hoa don.
    """
    invoice = HoaDon.query.get(invoice_id)
    if not invoice:
        return jsonify({"success": False, "msg": "Khong tim thay hoa don"}), 404

    # Idempotent: da thanh toan -> tra 200 de frontend xu ly nhat quan
    if invoice.trangthai == 'Da thanh toan':
        return jsonify({
            "success": True,
            "already_paid": True,
            "msg": "Hoa don nay da duoc thanh toan",
        }), 200

    data = request.get_json() or {}
    try:
        sotien_nhan_duoc = float(data.get("sotien", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "msg": "So tien khong hop le"}), 400

    phuongthuc = data.get("phuongthuc")
    if phuongthuc != "Tien mat":
        return jsonify({"success": False, "msg": "Chi chap nhan phuong thuc Tien mat"}), 400

    if sotien_nhan_duoc < float(invoice.tongtien):
        return jsonify({"success": False, "msg": "So tien nhan duoc khong du"}), 400

    try:
        # Guard chong duplicate ThanhToan (concurrent request)
        existing_payment = ThanhToan.query.filter_by(mahd=invoice_id).first()
        if not existing_payment:
            db.session.add(ThanhToan(
                mahd=invoice_id, sotien=invoice.tongtien, phuongthuc="Tien mat",
            ))
        invoice.trangthai = 'Da thanh toan'
        db.session.commit()
        return jsonify({
            "success": True,
            "msg": f"Da ghi nhan thanh toan thanh cong cho hoa don #{invoice_id}",
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Loi khi ghi nhan thanh toan: {e}")
        return jsonify({"success": False, "msg": "Ghi nhan that bai"}), 500


@invoice_manage_bp.route("/invoices/<int:invoice_id>/generate-qr", methods=["POST"])
@roles_required('letan', 'manager', 'admin')
def generate_payment_qr(invoice_id):
    """Tao ma VietQR cho hoa don.

    Co the goi lai nhieu lan (khong tao thanh toan moi, khong thay doi DB).
    Neu hoa don da thanh toan: tra 400.
    """
    invoice = HoaDon.query.get(invoice_id)
    if not invoice:
        return jsonify({"msg": "Khong tim thay hoa don"}), 404
    if invoice.trangthai == 'Da thanh toan':
        return jsonify({"success": False, "msg": "Hoa don da thanh toan"}), 400
    try:
        vietqr_data = vietqr_service.generate_vietqr_info(invoice)
        return jsonify({
            "success": True,
            "msg": "Tao ma VietQR thanh cong.",
            "qrCodeUrl": vietqr_data["qrCodeUrl"],
            "bank": vietqr_data["bank_id"],
            "accountNo": vietqr_data["account_no"],
            "accountName": vietqr_data["account_name"],
            "description": vietqr_data["description"],
            "amount": vietqr_data["amount"],
        }), 200
    except Exception as e:
        current_app.logger.error(f"Loi khi tao ma VietQR: {str(e)}", exc_info=True)
        return jsonify({"msg": f"Khong the tao ma VietQR: {str(e)}"}), 500


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
            func.sum(case((HoaDon.trangthai == 'Da thanh toan', 1), else_=0)).label('paid_count'),
            func.sum(case((HoaDon.trangthai == 'Chua thanh toan', 1), else_=0)).label('unpaid_count'),
            func.sum(case((HoaDon.trangthai == 'Da thanh toan', HoaDon.tongtien), else_=0)).label('total_revenue'),
        ).one_or_none()

        stats = {
            "total": stats_query.total_count if stats_query and stats_query.total_count is not None else 0,
            "paid": stats_query.paid_count if stats_query and stats_query.paid_count is not None else 0,
            "unpaid": stats_query.unpaid_count if stats_query and stats_query.unpaid_count is not None else 0,
            "revenue": str(stats_query.total_revenue) if stats_query and stats_query.total_revenue is not None else "0",
        }

        invoices_list_query = base_query.order_by(HoaDon.mahd.desc())
        if status_filter and status_filter != 'all':
            invoices_list_query = invoices_list_query.filter(HoaDon.trangthai == status_filter)
        invoices = invoices_list_query.all()

        result = []
        for inv in invoices:
            customer_name = inv.khachhang.hoten if inv.khachhang else "N/A"
            date_field = getattr(inv, date_column.key) if date_column else None
            if search_term and not (
                search_term in customer_name.lower()
                or search_term in str(inv.mahd).lower()
                or search_term in str(inv.malh or '').lower()
            ):
                continue
            result.append({
                "mahd": inv.mahd,
                "malh": inv.malh,
                "khachhang_hoten": customer_name,
                "tongtien": str(inv.tongtien),
                "trangthai": inv.trangthai,
                "ngaytao": date_field.isoformat() if date_field else None,
            })

        return jsonify({"success": True, "invoices": result, "stats": stats}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Loi lay danh sach hoa don: {e}", exc_info=True)
        return jsonify({"msg": "Loi he thong"}), 500


@invoice_manage_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@roles_required('letan', 'manager', 'admin')
def get_invoice_detail(invoice_id):
    """Lay chi tiet mot hoa don."""
    try:
        invoice = HoaDon.query.get(invoice_id)
        if not invoice:
            return jsonify({"msg": "Khong tim thay hoa don"}), 404

        details = [{
            "tendv": item.dichvu.tendv if item.dichvu else "Dich vu khong xac dinh",
            "soluong": item.soluong,
            "dongia": str(item.dongia),
            "thanhtien": str(item.thanhtien),
        } for item in invoice.chitiet]

        date_field = None
        for attr in ['ngaylap', 'ngaytao', 'created_at', 'date_created']:
            if hasattr(invoice, attr):
                date_field = getattr(invoice, attr)
                break

        # Lay thanh toan neu co
        payment_info = None
        payment = ThanhToan.query.filter_by(mahd=invoice_id).first()
        if payment:
            payment_info = {
                "phuongthuc": payment.phuongthuc,
                "sotien": str(payment.sotien),
            }

        return jsonify({
            "mahd": invoice.mahd,
            "malh": invoice.malh,
            "khachhang_hoten": invoice.khachhang.hoten if invoice.khachhang else "N/A",
            "tongtien": str(invoice.tongtien),
            "trangthai": invoice.trangthai,
            "ngaytao": date_field.isoformat() if date_field else None,
            "chitiet": details,
            "payment": payment_info,
        }), 200

    except Exception as e:
        current_app.logger.error(f"Loi khi lay chi tiet hoa don: {e}", exc_info=True)
        return jsonify({"msg": "Loi he thong khi tai chi tiet hoa don"}), 500
'''

target.write_text(content, encoding='utf-8')
print(f"Written {len(content)} bytes to {target}")

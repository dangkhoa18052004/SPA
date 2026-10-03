import hmac
import re
from decimal import Decimal, InvalidOperation
from flask import current_app
from ..extensions import db
from ..models import HoaDon, ThanhToan
from datetime import datetime
from urllib.parse import urlencode, quote
from .payment_webhook_service import begin_event, duplicate_response, finish_event

def generate_vietqr_info(invoice):
    return generate_vietqr_payment_info(invoice.tongtien, f'HD{invoice.mahd}')


def vietqr_available():
    return all(str(current_app.config.get(name) or '').strip() for name in
               ('VIETQR_BANK_ID', 'VIETQR_ACCOUNT_NO', 'VIETQR_ACCOUNT_NAME'))


def generate_vietqr_payment_info(amount, description):
    """
    Tạo thông tin VietQR cho hóa đơn.
    Trả về URL ảnh QR VietQR QuickLink (Napas247) và thông tin chuyển khoản.
    """
    bank_id = current_app.config.get("VIETQR_BANK_ID")
    account_no = current_app.config.get("VIETQR_ACCOUNT_NO")
    account_name = current_app.config.get("VIETQR_ACCOUNT_NAME")
    if not all([bank_id, account_no, account_name]):
        raise RuntimeError("Thiếu cấu hình tài khoản VietQR")
    
    amount = int(Decimal(str(amount)))
    
    # Mã hóa URL cho tên chủ tài khoản và nội dung
    query = urlencode({'amount': amount, 'addInfo': description, 'accountName': account_name})
    
    # URL ảnh VietQR QuickLink tiêu chuẩn Napas247
    qr_image_url = f"https://img.vietqr.io/image/{quote(str(bank_id), safe='')}-{quote(str(account_no), safe='')}-compact2.png?{query}"
    
    return {
        "bank_id": bank_id,
        "account_no": account_no,
        "account_name": account_name,
        "amount": amount,
        "description": description,
        "qrCodeUrl": qr_image_url
    }

def verify_sepay_authorization(authorization_header):
    expected_key = current_app.config.get("SEPAY_API_KEY")
    if not expected_key:
        raise RuntimeError("SEPAY_API_KEY chưa được cấu hình")

    supplied = str(authorization_header or "").strip()
    parts = supplied.split(None, 1)
    if len(parts) == 2 and parts[0].lower() in {"apikey", "bearer"}:
        supplied = parts[1].strip()
    return bool(supplied) and hmac.compare_digest(supplied, str(expected_key))


def _sepay_transaction_id(data):
    return (
        data.get("id")
        or data.get("transactionId")
        or data.get("transaction_id")
        or data.get("referenceCode")
        or data.get("reference_code")
    )


def process_sepay_webhook(data, authorization_header=None):
    """
    Xử lý Webhook từ SePay khi có tiền chuyển vào tài khoản.
    """
    if not verify_sepay_authorization(authorization_header):
        raise PermissionError("SePay Authorization không hợp lệ")

    event, is_duplicate = begin_event("sepay", _sepay_transaction_id(data), data)
    if is_duplicate:
        return duplicate_response(event)
    
    # 1. Lấy nội dung giao dịch và tìm mã hóa đơn HDxxx (Ví dụ: HD27 -> 27)
    content = str(data.get("content") or data.get("description") or data.get("code") or "")
    package_match = re.search(r'\bPKG\s*(\d+)\b', content, re.IGNORECASE)
    if package_match:
        from .package_service import confirm_purchase
        from .appointment_service import AppointmentValidationError
        if str(data.get('transferType', 'in')).lower() != 'in':
            finish_event(event, 'rejected')
            db.session.commit()
            return {'status':'failed', 'message':'Không phải giao dịch tiền vào'}
        try:
            _, record, created = confirm_purchase(int(package_match.group(1)),
                data.get('transferAmount') or data.get('amountIn') or data.get('amount') or 0,
                external_id=f'sepay:{event.external_transaction_id}', method='vietqr')
        except AppointmentValidationError as error:
            finish_event(event, 'rejected')
            db.session.commit()
            return {'status':'failed', 'message':error.message}
        finish_event(event, 'processed')
        db.session.commit()
        return {'status':'success' if created else 'duplicate', 'mathe':record.mathe}
    match = re.search(r'\bHD\s*(\d+)\b', content, re.IGNORECASE)
    if not match:
        finish_event(event, "ignored")
        db.session.commit()
        return {"status": "ignored", "message": "Không tìm thấy mã hóa đơn trong nội dung chuyển khoản"}
        
    invoice_id = int(match.group(1))
    
    # Thử tìm theo mã hóa đơn mahd, nếu không có thử tìm theo mã lịch hẹn malh
    invoice = HoaDon.query.get(invoice_id)
        
    if not invoice:
        finish_event(event, "ignored")
        db.session.commit()
        return {"status": "ignored", "message": f"Hóa đơn #{invoice_id} không tồn tại"}
        
    if invoice.trangthai == 'Đã thanh toán':
        finish_event(event, "ignored", invoice.mahd)
        db.session.commit()
        return {"status": "duplicate", "message": "Hóa đơn đã thanh toán trước đó"}
        
    # 2. Kiểm tra số tiền chuyển khoản
    try:
        transfer_amount = Decimal(str(
            data.get("transferAmount") or data.get("amountIn") or data.get("amount") or "0"
        ))
    except (InvalidOperation, TypeError):
        transfer_amount = Decimal("0")
    invoice_amount = Decimal(invoice.tongtien)

    if not transfer_amount.is_finite() or transfer_amount <= 0:
        finish_event(event, "rejected", invoice.mahd)
        db.session.commit()
        return {"status": "failed", "message": "Số tiền thanh toán phải lớn hơn 0"}

    if transfer_amount < invoice_amount:
        finish_event(event, "rejected", invoice.mahd)
        db.session.commit()
        return {"status": "failed", "message": "Số tiền thanh toán không đủ"}

    # 3. Ghi nhận thanh toán hóa đơn & cập nhật trạng thái
    from .payment_webhook_service import claim_invoice_payment
    if not claim_invoice_payment(invoice.mahd):
        finish_event(event, "ignored", invoice.mahd)
        db.session.commit()
        return {"status": "duplicate", "message": "Hóa đơn đã thanh toán trước đó"}
    new_payment = ThanhToan(
        mahd=invoice.mahd,
        sotien=transfer_amount,
        phuongthuc="VietQR (SePay)",
        ngaythanhtoan=datetime.utcnow()
    )
    invoice.trangthai = 'Đã thanh toán'
    db.session.add(new_payment)
    finish_event(event, "processed", invoice.mahd)
    db.session.commit()

    current_app.logger.info(
        "SePay webhook processed: transaction=%s invoice=%s",
        event.external_transaction_id,
        invoice.mahd,
    )
    return {"status": "success", "message": f"Tự động thanh toán thành công hóa đơn #{invoice.mahd}"}

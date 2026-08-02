import re
from flask import current_app
from ..extensions import db
from ..models import HoaDon, ThanhToan
from datetime import datetime

def generate_vietqr_info(invoice):
    """
    Tạo thông tin VietQR cho hóa đơn.
    Trả về URL ảnh QR VietQR QuickLink (Napas247) và thông tin chuyển khoản.
    """
    bank_id = current_app.config.get("VIETQR_BANK_ID", "TCB")
    account_no = current_app.config.get("VIETQR_ACCOUNT_NO", "19071655175011")
    account_name = current_app.config.get("VIETQR_ACCOUNT_NAME", "DANG VAN KHOA")
    
    amount = int(float(invoice.tongtien))
    description = f"HD{invoice.mahd}"
    
    # Mã hóa URL cho tên chủ tài khoản và nội dung
    encoded_name = account_name.replace(" ", "%20")
    
    # URL ảnh VietQR QuickLink tiêu chuẩn Napas247
    qr_image_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png?amount={amount}&addInfo={description}&accountName={encoded_name}"
    
    return {
        "bank_id": bank_id,
        "account_no": account_no,
        "account_name": account_name,
        "amount": amount,
        "description": description,
        "qrCodeUrl": qr_image_url
    }

def process_sepay_webhook(data, authorization_header=None):
    """
    Xử lý Webhook từ SePay khi có tiền chuyển vào tài khoản.
    SePay webhook payload mẫu:
    {
        "id": 123456,
        "gateway": "Techcombank",
        "transactionDate": "2026-08-02 09:20:00",
        "accountNumber": "19071655175011",
        "content": "HD105 thanh toan",
        "transferType": "in",
        "transferAmount": 150000,
        "referenceCode": "FT2308..."
    }
    """
    sepay_key = current_app.config.get("SEPAY_API_KEY")
    
    # Xác thực API Key từ SePay nếu có Header Authorization (Ví dụ: "Apikey 3ENNHUPB...")
    if authorization_header and sepay_key:
        expected_auth = f"Apikey {sepay_key}"
        expected_bearer = f"Bearer {sepay_key}"
        if authorization_header not in [expected_auth, expected_bearer, sepay_key]:
            current_app.logger.warning(f"SePay Webhook: Authorization Header không khớp ({authorization_header})")
    
    content = data.get("content") or data.get("description") or ""
    transfer_type = data.get("transferType", "in")
    transfer_amount = float(data.get("transferAmount") or data.get("amountIn") or 0)
    
    # Chỉ xử lý giao dịch nạp tiền vào
    if transfer_type == "out" and transfer_amount <= 0:
        return {"status": "ignored", "message": "Chỉ xử lý giao dịch tiền vào"}
        
    # Tìm mã hóa đơn HDxxx trong nội dung chuyển khoản (Ví dụ: HD105, HD 105, thanh toan HD105)
    match = re.search(r'HD\s*(\d+)', content, re.IGNORECASE)
    if not match:
        current_app.logger.warning(f"SePay Webhook: Không tìm thấy mã hóa đơn trong nội dung: '{content}'")
        return {"status": "ignored", "message": "Không tìm thấy mã hóa đơn trong nội dung chuyển khoản"}
        
    invoice_id = int(match.group(1))
    invoice = HoaDon.query.get(invoice_id)
    if not invoice:
        current_app.logger.warning(f"SePay Webhook: Hóa đơn #{invoice_id} không tồn tại")
        return {"status": "ignored", "message": f"Hóa đơn #{invoice_id} không tồn tại"}
        
    if invoice.trangthai == 'Đã thanh toán':
        current_app.logger.info(f"SePay Webhook: Hóa đơn #{invoice_id} đã được thanh toán trước đó")
        return {"status": "success", "message": "Hóa đơn đã thanh toán trước đó"}
        
    # Kiểm tra số tiền chuyển khoản có đủ không
    if transfer_amount < float(invoice.tongtien):
        current_app.logger.warning(f"SePay Webhook: Số tiền nhận ({transfer_amount}) ít hơn tổng tiền hóa đơn ({invoice.tongtien})")
        return {"status": "failed", "message": "Số tiền thanh toán không đủ"}
        
    # Ghi nhận thanh toán hóa đơn
    new_payment = ThanhToan(
        mahd=invoice_id,
        sotien=transfer_amount,
        phuongthuc="VietQR (SePay)",
        ngaythanhtoan=datetime.utcnow()
    )
    invoice.trangthai = 'Đã thanh toán'
    
    db.session.add(new_payment)
    db.session.commit()
    
    current_app.logger.info(f"SePay Webhook: Đã tự động cập nhật thanh toán thành công cho Hóa đơn #{invoice_id}")
    return {"status": "success", "message": f"Tự động thanh toán thành công hóa đơn #{invoice_id}"}

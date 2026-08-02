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
    bank_id = current_app.config.get("VIETQR_BANK_ID", "MB")
    account_no = current_app.config.get("VIETQR_ACCOUNT_NO", "0387829152")
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
    """
    sepay_key = current_app.config.get("SEPAY_API_KEY")
    current_app.logger.info(f"SePay Webhook Data Received: {data}")
    
    # 1. Lấy nội dung giao dịch và tìm mã hóa đơn HDxxx (Ví dụ: HD27 -> 27)
    content = str(data.get("content") or data.get("description") or data.get("code") or "")
    full_payload_str = str(data)
    
    match = re.search(r'HD\s*(\d+)', content, re.IGNORECASE) or re.search(r'HD\s*(\d+)', full_payload_str, re.IGNORECASE)
    if not match:
        match = re.search(r'(\d+)', content)
        if not match:
            current_app.logger.warning(f"SePay Webhook: Không tìm thấy mã hóa đơn trong: '{content}'")
            return {"status": "ignored", "message": "Không tìm thấy mã hóa đơn trong nội dung chuyển khoản"}
        
    invoice_id = int(match.group(1))
    
    # Thử tìm theo mã hóa đơn mahd, nếu không có thử tìm theo mã lịch hẹn malh
    invoice = HoaDon.query.get(invoice_id)
    if not invoice:
        invoice = HoaDon.query.filter_by(malh=invoice_id).first()
        
    if not invoice:
        current_app.logger.warning(f"SePay Webhook: Hóa đơn/Lịch hẹn #{invoice_id} không tồn tại trong CSDL")
        return {"status": "ignored", "message": f"Hóa đơn #{invoice_id} không tồn tại"}
        
    if invoice.trangthai == 'Đã thanh toán':
        current_app.logger.info(f"SePay Webhook: Hóa đơn #{invoice.mahd} đã được thanh toán trước đó")
        return {"status": "success", "message": "Hóa đơn đã thanh toán trước đó"}
        
    # 2. Kiểm tra số tiền chuyển khoản
    transfer_amount = float(data.get("transferAmount") or data.get("amountIn") or data.get("amount") or 0)
    invoice_amount = float(invoice.tongtien)
    
    # Nếu có truyền số tiền thực tế và nhỏ hơn tổng hóa đơn
    if transfer_amount > 0 and transfer_amount < (invoice_amount - 1):
        current_app.logger.warning(f"SePay Webhook: Số tiền nhận ({transfer_amount}) ít hơn tổng tiền hóa đơn ({invoice_amount})")
        return {"status": "failed", "message": "Số tiền thanh toán không đủ"}

    final_amount = transfer_amount if transfer_amount > 0 else invoice_amount

    # 3. Ghi nhận thanh toán hóa đơn & cập nhật trạng thái
    new_payment = ThanhToan(
        mahd=invoice.mahd,
        sotien=final_amount,
        phuongthuc="VietQR (SePay)",
        ngaythanhtoan=datetime.utcnow()
    )
    invoice.trangthai = 'Đã thanh toán'
    
    db.session.add(new_payment)
    db.session.commit()
    
    current_app.logger.info(f"SePay Webhook: Đã tự động cập nhật THANH TOÁN THÀNH CÔNG cho Hóa đơn #{invoice.mahd}")
    return {"status": "success", "message": f"Tự động thanh toán thành công hóa đơn #{invoice.mahd}"}

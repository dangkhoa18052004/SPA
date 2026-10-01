import json
import time
import requests
import hmac
import hashlib
import re
from decimal import Decimal, InvalidOperation
from flask import current_app
from ..models import HoaDon, ThanhToan
from ..extensions import db
from .payment_webhook_service import begin_event, duplicate_response, finish_event

def create_momo_payment_link(invoice):
    """
    Tạo link thanh toán Momo cho một hóa đơn.
    invoice: Đối tượng HoaDon
    """
    MOMO_PARTNER_CODE = current_app.config.get("MOMO_PARTNER_CODE_SANDBOX")
    MOMO_ACCESS_KEY = current_app.config.get("MOMO_ACCESS_KEY_SANDBOX")
    MOMO_SECRET_KEY = current_app.config.get("MOMO_SECRET_KEY_SANDBOX")
    MOMO_API_ENDPOINT = current_app.config.get("MOMO_API_ENDPOINT_SANDBOX")
    YOUR_REDIRECT_URL = current_app.config.get("YOUR_REDIRECT_URL")
    YOUR_IPN_URL = current_app.config.get("YOUR_IPN_URL")

    if not all([MOMO_PARTNER_CODE, MOMO_ACCESS_KEY, MOMO_SECRET_KEY, MOMO_API_ENDPOINT]):
        current_app.logger.error("Cấu hình Momo bị thiếu!")
        raise ValueError("Cấu hình Momo chưa đầy đủ")

    # ✅ SỬA: Tạo orderId và requestId ngắn hơn (max 50 chars)
    timestamp = int(time.time())
    orderId = f"HD{invoice.mahd}_{timestamp}"  # VD: HD1_1731580123
    requestId = f"{orderId}_REQ"
    
    orderInfo = f"Thanh toan HD{invoice.mahd}"
    amount = str(int(invoice.tongtien))
    requestType = "captureWallet"
    extraData = ""

    # ✅ QUAN TRỌNG: Thứ tự các trường PHẢI theo alphabet
    rawSignature = (
        f"accessKey={MOMO_ACCESS_KEY}"
        f"&amount={amount}"
        f"&extraData={extraData}"
        f"&ipnUrl={YOUR_IPN_URL}"
        f"&orderId={orderId}"
        f"&orderInfo={orderInfo}"
        f"&partnerCode={MOMO_PARTNER_CODE}"
        f"&redirectUrl={YOUR_REDIRECT_URL}"
        f"&requestId={requestId}"
        f"&requestType={requestType}"
    )
    
    signature = hmac.new(
        bytes(MOMO_SECRET_KEY, 'ascii'), 
        bytes(rawSignature, 'ascii'), 
        hashlib.sha256
    ).hexdigest()

    # ✅ Payload đầy đủ
    payload = {
        'partnerCode': MOMO_PARTNER_CODE,
        'partnerName': 'Bin Spa',  # ✅ Thêm
        'storeId': 'BinSpaStore',  # ✅ Thêm
        'requestId': requestId,
        'amount': amount,
        'orderId': orderId,
        'orderInfo': orderInfo,
        'redirectUrl': YOUR_REDIRECT_URL,
        'ipnUrl': YOUR_IPN_URL,
        'requestType': requestType,
        'extraData': extraData,
        'lang': 'vi',
        'autoCapture': True,  # ✅ Thêm
        'signature': signature
    }
    
    current_app.logger.info(
        "Creating MoMo payment request: invoice=%s order=%s",
        invoice.mahd,
        orderId,
    )
    
    data_json = json.dumps(payload)
    
    response = requests.post(
        MOMO_API_ENDPOINT, 
        data=data_json, 
        headers={
            'Content-Type': 'application/json',
            'Content-Length': str(len(data_json))
        },
        timeout=10
    )
    
    # ✅ Log response
    current_app.logger.info(f"📥 Momo Response Status: {response.status_code}")
    response.raise_for_status()
    momo_response = response.json()

    if momo_response.get("resultCode") == 0:
        return momo_response 
    else:
        current_app.logger.error(f"❌ Momo Error: {momo_response}")
        raise ValueError(f"Momo Error: {momo_response.get('message')}")

def verify_momo_webhook(data):
    """
    Xác thực chữ ký từ Momo IPN Webhook.
    data: Dữ liệu JSON từ request của Momo
    """
    MOMO_SECRET_KEY = current_app.config.get("MOMO_SECRET_KEY_SANDBOX")
    MOMO_ACCESS_KEY = current_app.config.get("MOMO_ACCESS_KEY_SANDBOX")
    
    if not MOMO_SECRET_KEY or not MOMO_ACCESS_KEY:
        raise ValueError("Thiếu cấu hình Momo (Secret/Access Key)")

    momo_signature = data.get('signature')
    if not momo_signature:
        return False
    
    # ✅ Thứ tự alphabet
    raw_verify_signature_parts = [
        f"accessKey={MOMO_ACCESS_KEY}",
        f"amount={data.get('amount')}",
        f"extraData={data.get('extraData', '')}",
        f"message={data.get('message', '')}",  # ✅ Thêm default
        f"orderId={data.get('orderId')}",
        f"orderInfo={data.get('orderInfo')}",
        f"orderType={data.get('orderType')}",
        f"partnerCode={data.get('partnerCode')}",
        f"payType={data.get('payType')}",
        f"requestId={data.get('requestId')}",
        f"responseTime={data.get('responseTime')}",
        f"resultCode={data.get('resultCode')}",
        f"transId={data.get('transId')}"
    ]
    raw_verify_signature = "&".join(raw_verify_signature_parts)
    
    verify_signature = hmac.new(
        MOMO_SECRET_KEY.encode('utf-8'), 
        raw_verify_signature.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(verify_signature, momo_signature)

def process_momo_webhook(data):
    """
    Xử lý logic nghiệp vụ sau khi webhook đã được xác thực.
    """
    external_id = data.get('transId') or data.get('requestId') or data.get('orderId')
    event, is_duplicate = begin_event("momo", external_id, data)
    if is_duplicate:
        return duplicate_response(event)

    try:
        result_code = int(data.get('resultCode'))
    except (TypeError, ValueError):
        result_code = -1
    if result_code != 0:
        finish_event(event, "rejected")
        db.session.commit()
        return {"status": "failed", "message": "MoMo báo giao dịch không thành công"}
        
    order_info = data.get('orderInfo')
    try:
        match = re.fullmatch(r"Thanh toan HD(\d+)", str(order_info or "").strip())
        mahd = int(match.group(1)) if match else None
        invoice = HoaDon.query.get(mahd)
    except Exception:
        invoice = None

    if not invoice:
        finish_event(event, "ignored")
        db.session.commit()
        return {"status": "ignored", "message": "Không tìm thấy hóa đơn"}
        
    if invoice.trangthai == 'Đã thanh toán':
        finish_event(event, "ignored", invoice.mahd)
        db.session.commit()
        return {"status": "duplicate", "message": "Hóa đơn đã thanh toán trước đó"}

    try:
        paid_amount = Decimal(str(data.get('amount') or "0"))
    except (InvalidOperation, TypeError):
        paid_amount = Decimal("0")
    if paid_amount <= 0 or paid_amount < Decimal(invoice.tongtien):
        finish_event(event, "rejected", invoice.mahd)
        db.session.commit()
        return {"status": "failed", "message": "Số tiền thanh toán không hợp lệ hoặc không đủ"}

    new_payment = ThanhToan(
        mahd=invoice.mahd,
        sotien=paid_amount,
        phuongthuc='Momo QR',
        ghichu=f"Momo TransId: {data.get('transId')}"
    )
    invoice.trangthai = 'Đã thanh toán'
    db.session.add(new_payment)
    finish_event(event, "processed", invoice.mahd)
    db.session.commit()
    current_app.logger.info(
        "MoMo webhook processed: transaction=%s invoice=%s",
        event.external_transaction_id,
        invoice.mahd,
    )
    return {"status": "success", "message": "Thanh toán thành công"}

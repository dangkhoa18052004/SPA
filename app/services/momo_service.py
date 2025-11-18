import json
import time
import requests
import hmac
import hashlib
from flask import current_app, jsonify
from ..models import HoaDon, ThanhToan
from ..extensions import db
from datetime import datetime

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
    
    # ✅ Log để debug
    current_app.logger.info(f"📤 Momo Request Payload:\n{json.dumps(payload, indent=2)}")
    current_app.logger.info(f"📤 Raw Signature: {rawSignature}")
    
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
    current_app.logger.info(f"📥 Momo Response Body: {response.text}")
    
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
    result_code = data.get('resultCode')
    if result_code != 0:
        current_app.logger.warning(f"Momo Webhook: Payment failed {data.get('orderId')} code {result_code}: {data.get('message')}")
        return
        
    order_info = data.get('orderInfo')
    try:
        mahd = int(order_info.replace("Thanh toan HD", ""))
        invoice = HoaDon.query.get(mahd)
    except Exception:
        invoice = None
        current_app.logger.error(f"Momo Webhook: Could not parse mahd from orderInfo: {order_info}")
        return

    if not invoice:
        current_app.logger.warning(f"Momo Webhook: Invoice not found: {order_info}")
        return
        
    if invoice.trangthai == 'Đã thanh toán':
        current_app.logger.warning(f"Momo Webhook: Invoice {invoice.mahd} already paid.")
        return

    try:
        new_payment = ThanhToan(
            mahd=invoice.mahd, 
            sotien=data.get('amount'), 
            phuongthuc='Momo QR', 
            ghichu=f"Momo TransId: {data.get('transId')}"
        )
        invoice.trangthai = 'Đã thanh toán'
        db.session.add(new_payment)
        db.session.commit()
        current_app.logger.info(f"✅ Momo Webhook: Updated invoice {invoice.mahd} to paid.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Momo Webhook: Error updating DB for invoice {invoice.mahd}: {e}")
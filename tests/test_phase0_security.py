import hashlib
import hmac
import io
import os

import pytest
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import HoaDon, PaymentWebhookEvent, ThanhToan


def _sepay_payload(invoice_id, transaction_id, amount):
    return {
        "id": transaction_id,
        "transferAmount": amount,
        "content": f"Thanh toan HD{invoice_id}",
    }


def _momo_payload(invoice_id, transaction_id="900001"):
    payload = {
        "amount": "100000",
        "extraData": "",
        "message": "Successful.",
        "orderId": f"HD{invoice_id}_request",
        "orderInfo": f"Thanh toan HD{invoice_id}",
        "orderType": "momo_wallet",
        "partnerCode": "TESTPARTNER",
        "payType": "qr",
        "requestId": f"HD{invoice_id}_request_REQ",
        "responseTime": 1790870400000,
        "resultCode": 0,
        "transId": transaction_id,
    }
    raw = "&".join([
        "accessKey=test-momo-access",
        f"amount={payload['amount']}",
        "extraData=",
        f"message={payload['message']}",
        f"orderId={payload['orderId']}",
        f"orderInfo={payload['orderInfo']}",
        f"orderType={payload['orderType']}",
        f"partnerCode={payload['partnerCode']}",
        f"payType={payload['payType']}",
        f"requestId={payload['requestId']}",
        f"responseTime={payload['responseTime']}",
        f"resultCode={payload['resultCode']}",
        f"transId={payload['transId']}",
    ])
    payload["signature"] = hmac.new(
        b"test-momo-secret",
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return payload


def test_sepay_rejects_invalid_authorization(client, app, create_invoice):
    invoice_id = create_invoice()
    response = client.post(
        "/api/payment/webhook/sepay",
        json=_sepay_payload(invoice_id, "sepay-invalid-auth", 100000),
        headers={"Authorization": "Apikey wrong-key"},
    )

    assert response.status_code in {401, 403}
    with app.app_context():
        assert ThanhToan.query.count() == 0
        assert PaymentWebhookEvent.query.count() == 0
        assert db.session.get(HoaDon, invoice_id).trangthai == "Chưa thanh toán"


def test_sepay_valid_payment_is_idempotent(client, app, create_invoice):
    invoice_id = create_invoice()
    payload = _sepay_payload(invoice_id, "sepay-transaction-1", 100000)
    headers = {"Authorization": "Apikey test-sepay-key"}

    first = client.post("/api/payment/webhook/sepay", json=payload, headers=headers)
    second = client.post("/api/payment/webhook/sepay", json=payload, headers=headers)

    assert first.status_code == 200
    assert first.get_json()["status"] == "success"
    assert second.status_code == 200
    assert second.get_json()["status"] == "duplicate"
    with app.app_context():
        assert ThanhToan.query.filter_by(mahd=invoice_id).count() == 1
        assert PaymentWebhookEvent.query.filter_by(provider="sepay").count() == 1
        assert db.session.get(HoaDon, invoice_id).trangthai == "Đã thanh toán"


@pytest.mark.parametrize("amount", [0, 99999])
def test_sepay_zero_or_insufficient_amount_does_not_pay(
    client, app, create_invoice, amount
):
    invoice_id = create_invoice()
    response = client.post(
        "/api/payment/webhook/sepay",
        json=_sepay_payload(invoice_id, f"sepay-low-{amount}", amount),
        headers={"Authorization": "Bearer test-sepay-key"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "failed"
    with app.app_context():
        assert ThanhToan.query.filter_by(mahd=invoice_id).count() == 0
        assert db.session.get(HoaDon, invoice_id).trangthai == "Chưa thanh toán"
        event = PaymentWebhookEvent.query.filter_by(
            external_transaction_id=f"sepay-low-{amount}"
        ).one()
        assert event.status == "rejected"


def test_momo_rejects_invalid_signature(client, app, create_invoice):
    invoice_id = create_invoice()
    payload = _momo_payload(invoice_id)
    payload["signature"] = "invalid"

    response = client.post("/api/payment/webhook/momo", json=payload)

    assert response.status_code == 400
    with app.app_context():
        assert ThanhToan.query.count() == 0
        assert PaymentWebhookEvent.query.count() == 0


def test_momo_valid_payment_is_idempotent(client, app, create_invoice):
    invoice_id = create_invoice()
    payload = _momo_payload(invoice_id, "momo-transaction-1")

    first = client.post("/api/payment/webhook/momo", json=payload)
    second = client.post("/api/payment/webhook/momo", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["status"] == "duplicate"
    with app.app_context():
        assert ThanhToan.query.filter_by(mahd=invoice_id).count() == 1
        assert PaymentWebhookEvent.query.filter_by(provider="momo").count() == 1


def test_avatar_rejects_executable(client, customer_auth_headers):
    response = client.post(
        "/api/profile/upload-avatar",
        data={"file": (io.BytesIO(b"MZ-not-an-image"), "malware.exe")},
        headers=customer_auth_headers,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_avatar_accepts_real_image(client, app, customer_auth_headers):
    image_bytes = io.BytesIO()
    Image.new("RGB", (16, 16), color="green").save(image_bytes, format="PNG")
    image_bytes.seek(0)

    response = client.post(
        "/api/profile/upload-avatar",
        data={"file": (image_bytes, "avatar.png", "image/png")},
        headers=customer_auth_headers,
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    filename = response.get_json()["filename"]
    assert filename.startswith("customer_customer_test_")
    assert filename.endswith(".png")
    assert os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], filename))


def test_public_staff_api_does_not_expose_pii(client):
    list_response = client.get("/api/staff")
    detail_response = client.get("/api/staff/1")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    for staff in [list_response.get_json()["staff"][0], detail_response.get_json()["staff"]]:
        assert "email" not in staff
        assert "sdt" not in staff
        assert "diachi" not in staff


def test_production_missing_secrets_fails_fast():
    with pytest.raises(RuntimeError, match="DATABASE_URL.*JWT_SECRET_KEY.*SECRET_KEY.*SEPAY_API_KEY"):
        create_app({
            "APP_ENV": "production",
            "RENDER": False,
            "SQLALCHEMY_DATABASE_URI": None,
            "SECRET_KEY": None,
            "JWT_SECRET_KEY": None,
            "SEPAY_API_KEY": None,
        })

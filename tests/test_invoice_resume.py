from datetime import datetime

from app.extensions import db
from app.models import LichHen, DichVu, ChiTietLichHen, HoaDon, ThanhToan


def completed_appointment(app):
    with app.app_context():
        service = DichVu(tendv="Invoice resume service", gia=500000, thoiluong=60)
        db.session.add(service)
        db.session.flush()
        appointment = LichHen(makh=app.config["TEST_CUSTOMER_ID"],
                              manv=app.config["TEST_STAFF_ID"],
                              ngaygio=datetime(2026, 10, 3, 10), trangthai="completed")
        db.session.add(appointment)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=appointment.malh, madv=service.madv))
        db.session.commit()
        return appointment.malh


def test_resume_invoice_from_fresh_list_and_detail(app, client, admin_auth_headers):
    appointment_id = completed_appointment(app)
    url = f"/api/admin/appointments/{appointment_id}"
    assert client.get(url, headers=admin_auth_headers).json["appointment"]["invoice"] is None
    created = client.post(url + "/create-invoice", headers=admin_auth_headers)
    assert created.status_code == 201
    invoice_id = created.json["invoice_id"]
    duplicate = client.post(url + "/create-invoice", headers=admin_auth_headers)
    assert duplicate.status_code == 409
    assert duplicate.json["code"] == "INVOICE_ALREADY_EXISTS"
    assert duplicate.json["invoice_id"] == invoice_id
    for _ in range(2):
        listing = client.get("/api/admin/appointments", headers=admin_auth_headers).json
        invoice = next(a for a in listing if a["malh"] == appointment_id)["invoice"]
        assert invoice["mahd"] == invoice_id
        assert invoice["trangthai"] == "Chưa thanh toán"
        assert client.get(url, headers=admin_auth_headers).json["appointment"]["invoice"] == invoice
    payment_url = f"/api/admin/invoices/{invoice_id}/record-payment"
    paid = client.post(payment_url, json={"sotien": 600000, "phuongthuc": "Tiền mặt"}, headers=admin_auth_headers)
    assert paid.status_code == 201
    assert client.post(payment_url, json={"sotien": 600000, "phuongthuc": "Tiền mặt"}, headers=admin_auth_headers).status_code in (400, 409)
    detail = client.get(f"/api/admin/invoices/{invoice_id}", headers=admin_auth_headers).json
    assert detail["trangthai"] == "Đã thanh toán"
    assert detail["thanhtoan"][0]["phuongthuc"] == "Tiền mặt"
    assert detail["thanhtoan"][0]["ngaythanhtoan"]
    assert client.get(url, headers=admin_auth_headers).json["appointment"]["invoice"]["trangthai"] == "Đã thanh toán"
    with app.app_context():
        assert HoaDon.query.filter_by(malh=appointment_id).count() == 1
        assert ThanhToan.query.filter_by(mahd=invoice_id).count() == 1


def test_regenerate_qr_then_sepay_and_cash_duplicate(app, client, create_invoice, admin_auth_headers):
    app.config.update(VIETQR_BANK_ID="970407", VIETQR_ACCOUNT_NO="123456", VIETQR_ACCOUNT_NAME="TEST")
    invoice_id = create_invoice()
    url = f"/api/admin/invoices/{invoice_id}"
    first = client.post(url + "/generate-qr", headers=admin_auth_headers)
    second = client.post(url + "/generate-qr", headers=admin_auth_headers)
    assert first.status_code == second.status_code == 200
    assert first.json == second.json
    assert first.json["description"] == f"HD{invoice_id}"
    with app.app_context():
        assert ThanhToan.query.count() == 0
        assert db.session.get(HoaDon, invoice_id).trangthai == "Chưa thanh toán"
    for transaction in ("resume-1", "resume-1", "resume-2"):
        response = client.post("/api/payment/webhook/sepay", json={"id": transaction,
            "content": f"HD{invoice_id}", "transferAmount": 100000},
            headers={"Authorization": "Apikey test-sepay-key"})
        assert response.status_code == 200
    assert client.post(url + "/record-payment", json={"sotien": 100000, "phuongthuc": "Tiền mặt"}, headers=admin_auth_headers).status_code in (400, 409)
    assert client.post(url + "/generate-qr", headers=admin_auth_headers).status_code == 400
    with app.app_context():
        assert ThanhToan.query.filter_by(mahd=invoice_id).count() == 1

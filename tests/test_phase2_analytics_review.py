from datetime import datetime, date, time, timedelta
from decimal import Decimal
import pytest

from app.extensions import db
from app.models import (
    KhachHang,
    NhanVien,
    DichVu,
    HoaDon,
    ThanhToan,
    LichHen,
    ChiTietLichHen,
    DanhGia,
    AppointmentStatus,
)
from app.services import analytics_service, review_service


@pytest.fixture
def analytics_seed(app):
    """Tạo fixture dữ liệu cho Analytics và Review test."""
    with app.app_context():
        customer_id = app.config["TEST_CUSTOMER_ID"]
        staff_id = app.config["TEST_STAFF_ID"]

        # 1. Services
        sv1 = DichVu(tendv="Chăm sóc da nâng cao", gia=500000, thoiluong=60, active=True)
        sv2 = DichVu(tendv="Massage bấm huyệt", gia=300000, thoiluong=45, active=True)
        db.session.add_all([sv1, sv2])
        db.session.flush()

        # 2. Invoices & Payments (Revenue)
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # Hóa đơn 1: Đã thanh toán hôm qua (200.000đ)
        inv1 = HoaDon(tongtien=200000, makh=customer_id, manv=staff_id, trangthai="Đã thanh toán")
        db.session.add(inv1)
        db.session.flush()
        pay1 = ThanhToan(
            mahd=inv1.mahd,
            sotien=200000,
            phuongthuc="Chuyển khoản",
            ngaythanhtoan=datetime.combine(yesterday, time(10, 0)),
        )

        # Hóa đơn 2: Đã thanh toán hôm nay (300.000đ)
        inv2 = HoaDon(tongtien=300000, makh=customer_id, manv=staff_id, trangthai="Đã thanh toán")
        db.session.add(inv2)
        db.session.flush()
        pay2 = ThanhToan(
            mahd=inv2.mahd,
            sotien=300000,
            phuongthuc="Tiền mặt",
            ngaythanhtoan=datetime.combine(today, time(14, 0)),
        )

        # Hóa đơn 3: CHƯA THANH TOÁN (1.000.000đ) - KHÔNG ĐƯỢC TÍNH VÀO DOANH THU
        inv3_unpaid = HoaDon(tongtien=1000000, makh=customer_id, manv=staff_id, trangthai="Chưa thanh toán")
        db.session.add(inv3_unpaid)

        db.session.add_all([pay1, pay2])

        # 3. Appointments & Details for Top Services & Review
        # Lịch 1: Completed, của customer_id
        apt1_completed = LichHen(
            makh=customer_id,
            manv=staff_id,
            ngaygio=datetime.combine(yesterday, time(9, 0)),
            trangthai=AppointmentStatus.COMPLETED,
        )
        # Lịch 2: Confirmed (chưa completed)
        apt2_confirmed = LichHen(
            makh=customer_id,
            manv=staff_id,
            ngaygio=datetime.combine(today, time(15, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        db.session.add_all([apt1_completed, apt2_confirmed])
        db.session.flush()

        # Dịch vụ cho apt1: sv1 x 1
        db.session.add(ChiTietLichHen(malh=apt1_completed.malh, madv=sv1.madv))
        # Dịch vụ cho apt2: sv1 x 1, sv2 x 1
        db.session.add(ChiTietLichHen(malh=apt2_confirmed.malh, madv=sv1.madv))
        db.session.add(ChiTietLichHen(malh=apt2_confirmed.malh, madv=sv2.madv))

        # 4. Khách hàng thứ 2 đăng ký hôm nay
        cust2 = KhachHang(
            hoten="Khách Hàng Mới Hôm Nay",
            taikhoan="cust_new_today",
            matkhau="hashpass",
            ngaytao=datetime.combine(today, time(8, 0)),
        )
        db.session.add(cust2)

        db.session.commit()

        return {
            "customer_id": customer_id,
            "cust2_id": cust2.makh,
            "staff_id": staff_id,
            "sv1_id": sv1.madv,
            "sv2_id": sv2.madv,
            "apt1_malh": apt1_completed.malh,
            "apt2_malh": apt2_confirmed.malh,
            "today": today,
            "yesterday": yesterday,
        }


# =========================================================================
# 1. Revenue theo ngày đúng fixture
# =========================================================================
def test_revenue_timeseries_matches_payments(app, client, admin_auth_headers, analytics_seed):
    """Test 1: Revenue theo ngày đúng với bảng ThanhToan (200k hôm qua, 300k hôm nay)."""
    with app.app_context():
        res = analytics_service.revenue_timeseries(
            from_date=analytics_seed["yesterday"],
            to_date=analytics_seed["today"],
            group_by="day",
        )
        assert res["success"] is True
        assert res["total_revenue"] == 500000.0
        assert res["total_transactions"] == 2

        yesterday_str = analytics_seed["yesterday"].strftime("%Y-%m-%d")
        today_str = analytics_seed["today"].strftime("%Y-%m-%d")

        rec_y = next((r for r in res["records"] if r["date"] == yesterday_str), None)
        rec_t = next((r for r in res["records"] if r["date"] == today_str), None)

        assert rec_y is not None and rec_y["revenue"] == 200000.0
        assert rec_t is not None and rec_t["revenue"] == 300000.0


# =========================================================================
# 2. Unpaid invoice không tính vào revenue
# =========================================================================
def test_unpaid_invoice_not_included_in_revenue(app, client, admin_auth_headers, analytics_seed):
    """Test 2: Hóa đơn 1.000.000đ ở trạng thái 'Chưa thanh toán' tuyệt đối không được tính vào doanh thu."""
    with app.app_context():
        # Tổng doanh thu chỉ là 500.000đ (từ pay1 và pay2)
        total_rev = analytics_service.revenue_timeseries(
            from_date=analytics_seed["yesterday"],
            to_date=analytics_seed["today"],
        )["total_revenue"]
        assert total_rev == 500000.0

    res = client.get(
        f"/api/analytics/revenue-timeseries?from={analytics_seed['yesterday']}&to={analytics_seed['today']}",
        headers=admin_auth_headers,
    )
    assert res.status_code == 200
    assert res.get_json()["total_revenue"] == 500000.0


# =========================================================================
# 3. Top service đúng
# =========================================================================
def test_top_services_correct_ranking(app, client, admin_auth_headers, analytics_seed):
    """Test 3: Top service đúng thứ tự (sv1 có 2 lượt đặt, sv2 có 1 lượt đặt)."""
    with app.app_context():
        res = analytics_service.top_services(
            from_date=analytics_seed["yesterday"],
            to_date=analytics_seed["today"],
            limit=5,
        )
        assert res["success"] is True
        services = res["top_services"]
        assert len(services) >= 2
        assert services[0]["madv"] == analytics_seed["sv1_id"]
        assert services[0]["booking_count"] == 2
        assert services[1]["madv"] == analytics_seed["sv2_id"]
        assert services[1]["booking_count"] == 1


# =========================================================================
# 4. New customer đúng date
# =========================================================================
def test_new_customers_filtered_by_created_at(app, client, admin_auth_headers, analytics_seed):
    """Test 4: Thống kê khách hàng mới lọc đúng theo ngày tạo (KhachHang.ngaytao)."""
    with app.app_context():
        res = analytics_service.new_customers(
            from_date=analytics_seed["today"],
            to_date=analytics_seed["today"],
        )
        assert res["success"] is True
        # Ít nhất có cust2 tạo hôm nay
        assert res["total_new_customers"] >= 1


# =========================================================================
# 5. Review chưa completed -> reject (400)
# =========================================================================
def test_review_not_completed_appointment_rejected(app, client, customer_auth_headers, analytics_seed):
    """Test 5: Đánh giá lịch hẹn chưa hoàn thành (confirmed) -> Bị từ chối (400 Bad Request)."""
    payload = {
        "malh": analytics_seed["apt2_malh"], # apt2 đang ở trạng thái confirmed
        "rating": 5,
        "comment": "Rất hài lòng",
    }
    res = client.post("/api/reviews", json=payload, headers=customer_auth_headers)
    assert res.status_code == 400
    assert "hoàn thành" in res.get_json()["message"]


# =========================================================================
# 6. Review người khác -> 403
# =========================================================================
def test_review_another_customer_appointment_forbidden(app, client, analytics_seed):
    """Test 6: Đánh giá lịch hẹn thuộc khách hàng khác -> 403 Forbidden."""
    # Tạo token cho customer 2
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token2 = create_access_token(identity=f"customer:{analytics_seed['cust2_id']}")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # customer 2 cố gắng đánh giá apt1 (thuộc customer 1)
    payload = {
        "malh": analytics_seed["apt1_malh"],
        "rating": 5,
        "comment": "Spam review",
    }
    res = client.post("/api/reviews", json=payload, headers=headers2)
    assert res.status_code == 403
    assert "không có quyền" in res.get_json()["message"]


# =========================================================================
# 7. Review lần 2 -> 409
# =========================================================================
def test_duplicate_review_rejected_with_409(app, client, customer_auth_headers, analytics_seed):
    """Test 7: Mỗi lịch hẹn chỉ được đánh giá 1 lần. Đánh giá lần 2 -> 409 Conflict."""
    payload = {
        "malh": analytics_seed["apt1_malh"],
        "rating": 5,
        "comment": "Dịch vụ tuyệt vời!",
    }
    # Lần 1: Thành công
    res1 = client.post("/api/reviews", json=payload, headers=customer_auth_headers)
    assert res1.status_code == 201

    # Lần 2: 409 Conflict
    res2 = client.post("/api/reviews", json=payload, headers=customer_auth_headers)
    assert res2.status_code == 409
    assert "đã có đánh giá" in res2.get_json()["message"]


# =========================================================================
# 8. Rating ngoài 1..5 -> 400
# =========================================================================
def test_rating_out_of_range_rejected(app, client, customer_auth_headers, analytics_seed):
    """Test 8: Điểm đánh giá < 1 hoặc > 5 -> 400 Bad Request."""
    with app.app_context():
        # Tạo thêm 1 lịch completed chưa đánh giá
        apt_new = LichHen(
            makh=analytics_seed["customer_id"],
            manv=analytics_seed["staff_id"],
            ngaygio=datetime.now() - timedelta(days=3),
            trangthai=AppointmentStatus.COMPLETED,
        )
        db.session.add(apt_new)
        db.session.commit()
        malh_new = apt_new.malh

    # Thử rating = 6
    res1 = client.post("/api/reviews", json={"malh": malh_new, "rating": 6}, headers=customer_auth_headers)
    assert res1.status_code == 400

    # Thử rating = 0
    res2 = client.post("/api/reviews", json={"malh": malh_new, "rating": 0}, headers=customer_auth_headers)
    assert res2.status_code == 400


# =========================================================================
# 9. Average rating đúng
# =========================================================================
def test_staff_average_rating_calculation(app, client, analytics_seed):
    """Test 9: Tính đúng average rating cho nhân viên (ví dụ rating 4 và 5 -> trung bình 4.5)."""
    with app.app_context():
        staff_id = analytics_seed["staff_id"]
        customer_id = analytics_seed["customer_id"]

        # Tạo lịch 10 và 11
        apt10 = LichHen(makh=customer_id, manv=staff_id, ngaygio=datetime.now(), trangthai=AppointmentStatus.COMPLETED)
        apt11 = LichHen(makh=customer_id, manv=staff_id, ngaygio=datetime.now(), trangthai=AppointmentStatus.COMPLETED)
        db.session.add_all([apt10, apt11])
        db.session.flush()

        # Đánh giá 4 sao và 5 sao
        dg1 = DanhGia(malh=apt10.malh, makh=customer_id, manv=staff_id, rating=4)
        dg2 = DanhGia(malh=apt11.malh, makh=customer_id, manv=staff_id, rating=5)
        db.session.add_all([dg1, dg2])
        db.session.commit()

        staff_reviews = review_service.get_staff_reviews(staff_id)
        assert staff_reviews["stats"]["total_reviews"] >= 2
        # Điểm trung bình giữa 4 và 5 là 4.5
        assert staff_reviews["stats"]["average_rating"] == 4.5


# =========================================================================
# 10. API chart schema đúng
# =========================================================================
def test_analytics_api_chart_schema(app, client, admin_auth_headers, analytics_seed):
    """Test 10: API trả về đúng schema dành cho Chart.js (labels, datasets, backgroundColor, data)."""
    # 1. Revenue timeseries
    res_rev = client.get("/api/analytics/revenue-timeseries?group_by=day", headers=admin_auth_headers)
    assert res_rev.status_code == 200
    chart_rev = res_rev.get_json()["chart_data"]
    assert "labels" in chart_rev
    assert "datasets" in chart_rev
    assert isinstance(chart_rev["datasets"][0]["data"], list)

    # 2. Appointment stats
    res_apt = client.get("/api/analytics/appointment-stats", headers=admin_auth_headers)
    assert res_apt.status_code == 200
    chart_apt = res_apt.get_json()["chart_data"]
    assert "labels" in chart_apt
    assert "datasets" in chart_apt
    assert isinstance(chart_apt["datasets"][0]["backgroundColor"], list)

    # 3. KPI Cards
    res_kpi = client.get("/api/analytics/kpi-cards", headers=admin_auth_headers)
    assert res_kpi.status_code == 200
    kpi_data = res_kpi.get_json()
    assert "today" in kpi_data
    assert "month" in kpi_data
    assert "general" in kpi_data
    assert "revenue" in kpi_data["today"]

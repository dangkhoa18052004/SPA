from datetime import datetime, date, time, timedelta
import pytest
from app.extensions import db
from app.models import (
    NhanVien,
    KhachHang,
    DichVu,
    CaLam,
    LichHen,
    ChiTietLichHen,
    nhanvien_calam,
    AppointmentStatus,
)
from app.services import appointment_service
from app.services.appointment_service import (
    AppointmentConflictError,
    NoStaffAvailableError,
    AppointmentValidationError,
)


@pytest.fixture
def seed_data(app):
    """Seed services, shifts and link staff to shifts for testing."""
    with app.app_context():
        # Services
        sv1 = DichVu(tendv="Chăm sóc da mặt cơ bản", gia=200000, thoiluong=45, active=True)
        sv2 = DichVu(tendv="Massage trị liệu", gia=350000, thoiluong=60, active=True)
        sv3 = DichVu(tendv="Gội đầu dưỡng sinh", gia=150000, thoiluong=30, active=True)
        sv_inactive = DichVu(tendv="Dịch vụ cũ ngừng bán", gia=50000, thoiluong=30, active=False)
        db.session.add_all([sv1, sv2, sv3, sv_inactive])
        db.session.flush()

        # Ca làm việc ngày mai (08:00 - 18:00)
        tomorrow = date.today() + timedelta(days=1)
        shift = CaLam(
            ngay=tomorrow,
            giobatdau=time(8, 0),
            gioketthuc=time(18, 0),
            hesoluong=1
        )
        db.session.add(shift)
        db.session.flush()

        # Gán ca cho staff 1 và staff 2
        staff1_id = app.config["TEST_STAFF_ID"]
        staff2_id = app.config["TEST_STAFF2_ID"]
        db.session.execute(nhanvien_calam.insert().values([
            {"manv": staff1_id, "maca": shift.maca},
            {"manv": staff2_id, "maca": shift.maca},
        ]))
        db.session.commit()

        return {
            "sv1_id": sv1.madv,
            "sv2_id": sv2.madv,
            "sv3_id": sv3.madv,
            "sv_inactive_id": sv_inactive.madv,
            "shift_id": shift.maca,
            "tomorrow": tomorrow,
            "staff1_id": staff1_id,
            "staff2_id": staff2_id,
        }


# =========================================================================
# 1. Booking 1 service
# =========================================================================
def test_booking_single_service_success(app, client, customer_auth_headers, seed_data):
    """Test 1: Booking 1 service thành công."""
    booking_dt = datetime.combine(seed_data["tomorrow"], time(9, 0))
    payload = {
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": booking_dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
        "ghichu": "Ghi chú đặt lịch test 1 dịch vụ",
    }

    res = client.post("/api/appointments/create", json=payload, headers=customer_auth_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["appointment"]["trangthai"] == AppointmentStatus.CONFIRMED
    assert data["appointment"]["manv"] == seed_data["staff1_id"]
    assert data["appointment"]["total_duration"] == 45


# =========================================================================
# 2. Nhiều service tính đúng duration
# =========================================================================
def test_booking_multiple_services_calculates_total_duration(app, client, customer_auth_headers, seed_data):
    """Test 2: Nhiều service tính đúng tổng duration (45 + 60 = 105 phút)."""
    with app.app_context():
        total_dur = appointment_service.calculate_total_duration([seed_data["sv1_id"], seed_data["sv2_id"]])
        assert total_dur == 105

    booking_dt = datetime.combine(seed_data["tomorrow"], time(10, 0))
    payload = {
        "madv_list": [seed_data["sv1_id"], seed_data["sv2_id"]],
        "ngaygio": booking_dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }
    res = client.post("/api/appointments/create", json=payload, headers=customer_auth_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["appointment"]["total_duration"] == 105
    assert data["appointment"]["end_time"] == "11:45"


# =========================================================================
# 3. Overlap reject
# =========================================================================
def test_overlapping_appointment_is_rejected(app, client, customer_auth_headers, seed_data):
    """Test 3: Reject lịch hẹn bị trùng giờ của cùng nhân viên (409 Conflict)."""
    # Lịch 1: 14:00 - 15:00 (60 phút) với staff1
    dt1 = datetime.combine(seed_data["tomorrow"], time(14, 0))
    payload1 = {
        "madv_list": [seed_data["sv2_id"]],
        "ngaygio": dt1.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }
    res1 = client.post("/api/appointments/create", json=payload1, headers=customer_auth_headers)
    assert res1.status_code == 201

    # Lịch 2: 14:30 - 15:15 (overlap với Lịch 1)
    dt2 = datetime.combine(seed_data["tomorrow"], time(14, 30))
    payload2 = {
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": dt2.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }
    res2 = client.post("/api/appointments/create", json=payload2, headers=customer_auth_headers)
    assert res2.status_code == 409
    data2 = res2.get_json()
    assert data2["success"] is False
    assert len(data2.get("conflicts", [])) > 0


# =========================================================================
# 4. Staff không có ca -> không khả dụng
# =========================================================================
def test_staff_without_covering_shift_is_unavailable(app, client, customer_auth_headers, seed_data):
    """Test 4: Nhân viên không có ca làm việc vào ngày đó -> không khả dụng."""
    # Ngày kia không có ca nào được setup
    day_after_tomorrow = date.today() + timedelta(days=2)
    dt = datetime.combine(day_after_tomorrow, time(9, 0))

    payload = {
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }
    res = client.post("/api/appointments/create", json=payload, headers=customer_auth_headers)
    assert res.status_code == 409
    assert "không có ca làm việc" in res.get_json()["message"]


# =========================================================================
# 5. Auto assign đúng (ít lịch nhất trong ngày, tie-break ổn định)
# =========================================================================
def test_auto_assign_picks_least_busy_staff_with_stable_tie_break(app, client, customer_auth_headers, seed_data):
    """Test 5: Tự động xếp lịch chọn nhân viên có ít lịch nhất trong ngày, tie-break manv ASC."""
    # Ban đầu cả staff1 và staff2 đều có 0 lịch hẹn trong ngày tomorrow.
    # Tie-break: staff1 có manv nhỏ hơn staff2 -> auto-assign chọn staff1.
    dt_morning = datetime.combine(seed_data["tomorrow"], time(8, 30))
    payload_auto_1 = {
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": dt_morning.strftime("%Y-%m-%dT%H:%M"),
    }
    res1 = client.post("/api/appointments/create", json=payload_auto_1, headers=customer_auth_headers)
    assert res1.status_code == 201
    assert res1.get_json()["appointment"]["manv"] == seed_data["staff1_id"]

    # Bây giờ staff1 đã có 1 lịch, staff2 có 0 lịch -> auto-assign tiếp theo phải chọn staff2.
    dt_later = datetime.combine(seed_data["tomorrow"], time(11, 0))
    payload_auto_2 = {
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": dt_later.strftime("%Y-%m-%dT%H:%M"),
    }
    res2 = client.post("/api/appointments/create", json=payload_auto_2, headers=customer_auth_headers)
    assert res2.status_code == 201
    assert res2.get_json()["appointment"]["manv"] == seed_data["staff2_id"]


# =========================================================================
# 6. Không staff rảnh -> 409
# =========================================================================
def test_no_available_staff_returns_409(app, client, customer_auth_headers, seed_data):
    """Test 6: Khi tất cả nhân viên có ca đều bận trong khung giờ -> trả về 409 Conflict."""
    slot_dt = datetime.combine(seed_data["tomorrow"], time(15, 0))
    # Gán lịch cho staff 1
    client.post("/api/appointments/create", json={
        "madv_list": [seed_data["sv2_id"]], # 60 phút: 15:00 - 16:00
        "ngaygio": slot_dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }, headers=customer_auth_headers)

    # Gán lịch cho staff 2
    client.post("/api/appointments/create", json={
        "madv_list": [seed_data["sv2_id"]], # 60 phút: 15:00 - 16:00
        "ngaygio": slot_dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff2_id"],
    }, headers=customer_auth_headers)

    # Khách thứ 3 yêu cầu auto-assign vào cùng khung giờ 15:15
    res = client.post("/api/appointments/create", json={
        "madv_list": [seed_data["sv3_id"]],
        "ngaygio": datetime.combine(seed_data["tomorrow"], time(15, 15)).strftime("%Y-%m-%dT%H:%M"),
    }, headers=customer_auth_headers)

    assert res.status_code == 409
    assert "Không có nhân viên rảnh" in res.get_json()["message"]


# =========================================================================
# 7. Cancel >4h success
# =========================================================================
def test_cancel_appointment_more_than_4_hours_succeeds(app, client, customer_auth_headers, seed_data):
    """Test 7: Khách hàng hủy lịch hẹn trước > 4 giờ thành công."""
    future_dt = datetime.now() + timedelta(hours=10)
    # Tạo ca làm việc cho ngày tương ứng nếu cần
    with app.app_context():
        c = CaLam(ngay=future_dt.date(), giobatdau=time(0, 0), gioketthuc=time(23, 59))
        db.session.add(c)
        db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=seed_data["staff1_id"], maca=c.maca))
        db.session.commit()

    create_res = client.post("/api/appointments/create", json={
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": future_dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }, headers=customer_auth_headers)
    assert create_res.status_code == 201
    malh = create_res.get_json()["appointment"]["malh"]

    # Hủy lịch
    cancel_res = client.put(f"/api/appointments/{malh}/cancel", json={"reason": "Bận việc đột xuất"}, headers=customer_auth_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["success"] is True

    # Kiểm tra DB
    with app.app_context():
        apt = LichHen.query.get(malh)
        assert apt.trangthai == AppointmentStatus.CANCELLED
        assert "Bận việc đột xuất" in apt.ghichu


# =========================================================================
# 8. Cancel <4h reject
# =========================================================================
def test_cancel_appointment_less_than_4_hours_rejected(app, client, customer_auth_headers, seed_data):
    """Test 8: Khách hàng hủy lịch hẹn trong vòng < 4 giờ bị từ chối (400 Bad Request)."""
    close_dt = datetime.now() + timedelta(hours=2)
    with app.app_context():
        c = CaLam(ngay=close_dt.date(), giobatdau=time(0, 0), gioketthuc=time(23, 59))
        db.session.add(c)
        db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=seed_data["staff1_id"], maca=c.maca))
        
        apt = LichHen(
            makh=app.config["TEST_CUSTOMER_ID"],
            manv=seed_data["staff1_id"],
            ngaygio=close_dt,
            trangthai=AppointmentStatus.CONFIRMED
        )
        db.session.add(apt)
        db.session.commit()
        malh = apt.malh

    res = client.put(f"/api/appointments/{malh}/cancel", headers=customer_auth_headers)
    assert res.status_code == 400
    assert "trong vòng 4 giờ" in res.get_json()["message"]


# =========================================================================
# 9. completed/cancelled không cancel lại
# =========================================================================
def test_completed_or_cancelled_cannot_be_cancelled_again(app, client, customer_auth_headers, seed_data):
    """Test 9: Lịch hẹn đã completed hoặc cancelled không thể hủy tiếp."""
    with app.app_context():
        apt = LichHen(
            makh=app.config["TEST_CUSTOMER_ID"],
            manv=seed_data["staff1_id"],
            ngaygio=datetime.now() + timedelta(days=5),
            trangthai=AppointmentStatus.COMPLETED
        )
        db.session.add(apt)
        db.session.commit()
        malh = apt.malh

    res = client.put(f"/api/appointments/{malh}/cancel", headers=customer_auth_headers)
    assert res.status_code == 400
    assert "Không thể hủy" in res.get_json()["message"]


# =========================================================================
# 10. Customer/Admin cùng service
# =========================================================================
def test_customer_and_admin_routes_use_same_appointment_service(app, client, customer_auth_headers, admin_auth_headers, seed_data):
    """Test 10: Cả Customer và Admin route đều dùng appointment_service, tuân thủ cùng quy tắc."""
    dt = datetime.combine(seed_data["tomorrow"], time(16, 0))

    # Admin tạo lịch hẹn bằng admin endpoint
    admin_payload = {
        "makh": app.config["TEST_CUSTOMER_ID"],
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
        "ghichu": "Admin đặt lịch",
    }
    admin_res = client.post("/api/admin/appointments", json=admin_payload, headers=admin_auth_headers)
    assert admin_res.status_code == 201
    malh = admin_res.get_json()["malh"]

    # Customer thử đặt lịch đè lên cùng slot và staff đó qua customer endpoint -> phải bị reject 409
    cust_res = client.post("/api/appointments/create", json={
        "madv_list": [seed_data["sv1_id"]],
        "ngaygio": dt.strftime("%Y-%m-%dT%H:%M"),
        "manv": seed_data["staff1_id"],
    }, headers=customer_auth_headers)
    assert cust_res.status_code == 409


# =========================================================================
# 11. available-slots đúng
# =========================================================================
def test_available_slots_reflects_actual_availability(app, client, seed_data):
    """Test 11: GET /api/appointments/available-slots phản ánh đúng tình trạng ca làm và trùng lịch."""
    tomorrow_str = seed_data["tomorrow"].strftime("%Y-%m-%d")
    res = client.get(f"/api/appointments/available-slots?date={tomorrow_str}&manv={seed_data['staff1_id']}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    slots = data["slots"]

    # Khung giờ 09:00 ban đầu còn trống (vì staff 1 có ca 08:00 - 18:00)
    slot_09 = next((s for s in slots if s["time"] == "09:00"), None)
    assert slot_09 is not None
    assert slot_09["available"] is True


# =========================================================================
# 12. Migration status đúng
# =========================================================================
def test_status_normalization_and_migration_integrity(app):
    """Test 12: Đảm bảo AppointmentStatus chuẩn hóa code và mapping tiếng Việt chuẩn."""
    assert AppointmentStatus.normalize("Chờ xác nhận") == AppointmentStatus.PENDING
    assert AppointmentStatus.normalize("Đã xác nhận") == AppointmentStatus.CONFIRMED
    assert AppointmentStatus.normalize("Đang thực hiện") == AppointmentStatus.IN_PROGRESS
    assert AppointmentStatus.normalize("Đã hoàn thành") == AppointmentStatus.COMPLETED
    assert AppointmentStatus.normalize("Đã hủy") == AppointmentStatus.CANCELLED

    assert AppointmentStatus.to_vietnamese(AppointmentStatus.PENDING) == "Chờ xác nhận"
    assert AppointmentStatus.to_vietnamese(AppointmentStatus.CONFIRMED) == "Đã xác nhận"
    assert AppointmentStatus.to_vietnamese(AppointmentStatus.IN_PROGRESS) == "Đang thực hiện"
    assert AppointmentStatus.to_vietnamese(AppointmentStatus.COMPLETED) == "Đã hoàn thành"
    assert AppointmentStatus.to_vietnamese(AppointmentStatus.CANCELLED) == "Đã hủy"


# =========================================================================
# 13. Service soft delete
# =========================================================================
def test_service_soft_delete(app, client, admin_auth_headers, seed_data):
    """Test bổ sung: DELETE /api/admin/services/<madv> soft delete bằng active=False."""
    sv_id = seed_data["sv3_id"]
    res = client.delete(f"/api/admin/services/{sv_id}", headers=admin_auth_headers)
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    with app.app_context():
        sv = DichVu.query.get(sv_id)
        assert sv.active is False

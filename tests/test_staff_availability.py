from datetime import datetime, date, time, timedelta
import pytest
from app.extensions import db
from app.models import (
    NhanVien,
    ChucVu,
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
    AVAILABILITY_REASON_AVAILABLE,
    AVAILABILITY_REASON_CONFLICT,
    AVAILABILITY_REASON_NOT_WORKING,
    AVAILABILITY_REASON_INACTIVE,
    AVAILABILITY_REASON_INVALID,
    AVAILABILITY_REASON_API_ERROR,
    NoStaffAvailableError,
)


@pytest.fixture
def availability_data(app):
    """Thiết lập dữ liệu dịch vụ, nhân viên các vai trò, và ca làm việc."""
    with app.app_context():
        # Chức vụ
        cv_tech = ChucVu.query.filter_by(tencv="Kỹ thuật viên").first()
        if not cv_tech:
            cv_tech = ChucVu(tencv="Kỹ thuật viên", dongiagio=100000)
            db.session.add(cv_tech)
            db.session.flush()

        cv_letan = ChucVu(tencv="Lễ tân", dongiagio=90000)
        db.session.add(cv_letan)
        db.session.flush()

        # Dịch vụ: 45 phút, 60 phút
        sv_45 = DichVu(tendv="Chăm sóc da 45p", gia=200000, thoiluong=45, active=True)
        sv_60 = DichVu(tendv="Massage toàn thân 60p", gia=350000, thoiluong=60, active=True)
        db.session.add_all([sv_45, sv_60])
        db.session.flush()

        # Kỹ thuật viên 1 & 2 (role='staff', active=True)
        tech1 = NhanVien(
            hoten="Kỹ thuật viên 1",
            taikhoan="tech1_user",
            matkhau="hash1",
            macv=cv_tech.macv,
            role="staff",
            trangthai=True,
        )
        tech2 = NhanVien(
            hoten="Kỹ thuật viên 2",
            taikhoan="tech2_user",
            matkhau="hash2",
            macv=cv_tech.macv,
            role="staff",
            trangthai=True,
        )
        # Lễ tân (role='letan')
        receptionist = NhanVien(
            hoten="Lễ tân Hoa",
            taikhoan="letan_user",
            matkhau="hash3",
            macv=cv_letan.macv,
            role="letan",
            trangthai=True,
        )
        # Nhân viên inactive
        inactive_tech = NhanVien(
            hoten="KTV Đã nghỉ việc",
            taikhoan="tech_inactive_user",
            matkhau="hash4",
            macv=cv_tech.macv,
            role="staff",
            trangthai=False,
        )
        db.session.add_all([tech1, tech2, receptionist, inactive_tech])
        db.session.flush()

        # Ngày test: 3 ngày sau
        test_date = date.today() + timedelta(days=3)

        # Ca làm việc (08:00 - 18:00) cho test_date
        shift = CaLam(
            ngay=test_date,
            giobatdau=time(8, 0),
            gioketthuc=time(18, 0),
            hesoluong=1,
        )
        db.session.add(shift)
        db.session.flush()

        # Chỉ gán ca cho tech1 (tech2 không có ca ban đầu)
        db.session.execute(nhanvien_calam.insert().values(manv=tech1.manv, maca=shift.maca))
        db.session.commit()

        return {
            "test_date": test_date,
            "sv_45_id": sv_45.madv,
            "sv_60_id": sv_60.madv,
            "tech1_id": tech1.manv,
            "tech2_id": tech2.manv,
            "receptionist_id": receptionist.manv,
            "inactive_tech_id": inactive_tech.manv,
            "shift_id": shift.maca,
        }


# =========================================================================
# 1. Ngày không có lịch + KTV có ca => available
# =========================================================================
def test_1_no_appointment_with_covering_shift_is_available(app, client, availability_data):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]
    sv_45_id = availability_data["sv_45_id"]

    slot_str = datetime.combine(test_date, time(9, 0)).strftime("%Y-%m-%dT%H:%M")

    with app.app_context():
        is_avail, conflicts, reason = appointment_service.check_staff_availability(
            manv=tech1_id,
            start_dt=slot_str,
            duration_minutes=45,
        )
        assert is_avail is True
        assert reason == AVAILABILITY_REASON_AVAILABLE
        assert conflicts == []

    # Kiểm tra API POST /api/appointments/available-staff
    res = client.post("/api/appointments/available-staff", json={
        "ngaygio": slot_str,
        "madv_list": [sv_45_id]
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    tech1_item = next((s for s in data["staff"] if s["manv"] == tech1_id), None)
    assert tech1_item is not None
    assert tech1_item["available"] is True
    assert tech1_item["reason"] == "available"


# =========================================================================
# 2. KTV có appointment overlap => appointment_conflict
# =========================================================================
def test_2_ktv_with_appointment_overlap_returns_conflict(app, client, availability_data):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]
    sv_60_id = availability_data["sv_60_id"]
    customer_id = app.config["TEST_CUSTOMER_ID"]

    # Tạo lịch hẹn 10:00 - 11:00 cho tech1
    with app.app_context():
        apt = LichHen(
            makh=customer_id,
            manv=tech1_id,
            ngaygio=datetime.combine(test_date, time(10, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=sv_60_id))
        db.session.commit()

    # Kiểm tra khung giờ trùng lặp: 10:30 (bị giao nhau với 10:00 - 11:00)
    overlap_slot = datetime.combine(test_date, time(10, 30)).strftime("%Y-%m-%dT%H:%M")
    with app.app_context():
        is_avail, conflicts, reason = appointment_service.check_staff_availability(
            manv=tech1_id,
            start_dt=overlap_slot,
            duration_minutes=45,
        )
        assert is_avail is False
        assert reason == AVAILABILITY_REASON_CONFLICT
        assert len(conflicts) > 0

    res = client.post("/api/appointments/available-staff", json={
        "ngaygio": overlap_slot,
        "madv_list": [sv_60_id]
    })
    assert res.status_code == 200
    data = res.get_json()
    tech1_item = next(s for s in data["staff"] if s["manv"] == tech1_id)
    assert tech1_item["available"] is False
    assert tech1_item["reason"] == "appointment_conflict"


# =========================================================================
# 3. KTV không có ca bị loại khỏi danh sách booking
# =========================================================================
def test_3_ktv_without_shift_is_excluded_from_booking(app, client, availability_data):
    test_date = availability_data["test_date"]
    tech2_id = availability_data["tech2_id"]  # tech2 chưa được gán ca nào
    sv_45_id = availability_data["sv_45_id"]

    slot_str = datetime.combine(test_date, time(9, 0)).strftime("%Y-%m-%dT%H:%M")

    with app.app_context():
        is_avail, conflicts, reason = appointment_service.check_staff_availability(
            manv=tech2_id,
            start_dt=slot_str,
            duration_minutes=45,
        )
        assert is_avail is False
        assert reason == AVAILABILITY_REASON_NOT_WORKING

    res = client.post("/api/appointments/available-staff", json={
        "ngaygio": slot_str,
        "madv_list": [sv_45_id]
    })
    assert res.status_code == 200
    data = res.get_json()
    assert tech2_id not in {s["manv"] for s in data["staff"]}


# =========================================================================
# 4. Lễ tân không xuất hiện trong danh sách booking
# =========================================================================
def test_4_receptionist_excluded_from_booking_staff(app, client, availability_data):
    receptionist_id = availability_data["receptionist_id"]
    test_date = availability_data["test_date"]
    sv_45_id = availability_data["sv_45_id"]
    slot_str = datetime.combine(test_date, time(9, 0)).strftime("%Y-%m-%dT%H:%M")

    # 1. API /api/staff không có lễ tân
    res_staff = client.get("/api/staff")
    assert res_staff.status_code == 200
    staff_ids = [s["manv"] for s in res_staff.get_json()["staff"]]
    assert receptionist_id not in staff_ids

    # 2. API /api/appointments/available-staff không có lễ tân
    res_avail = client.post("/api/appointments/available-staff", json={
        "ngaygio": slot_str,
        "madv_list": [sv_45_id]
    })
    assert res_avail.status_code == 200
    avail_staff_ids = [s["manv"] for s in res_avail.get_json()["staff"]]
    assert receptionist_id not in avail_staff_ids

    # 3. check_staff_availability trực tiếp từ chối với invalid_staff
    with app.app_context():
        is_avail, _, reason = appointment_service.check_staff_availability(
            manv=receptionist_id,
            start_dt=slot_str,
            duration_minutes=45,
        )
        assert is_avail is False
        assert reason == AVAILABILITY_REASON_INVALID


# =========================================================================
# 5. Nhân viên inactive không xuất hiện
# =========================================================================
def test_5_inactive_staff_excluded_from_booking_staff(app, client, availability_data):
    inactive_id = availability_data["inactive_tech_id"]
    test_date = availability_data["test_date"]
    sv_45_id = availability_data["sv_45_id"]
    slot_str = datetime.combine(test_date, time(9, 0)).strftime("%Y-%m-%dT%H:%M")

    # 1. API /api/staff không có inactive
    res_staff = client.get("/api/staff")
    assert res_staff.status_code == 200
    staff_ids = [s["manv"] for s in res_staff.get_json()["staff"]]
    assert inactive_id not in staff_ids

    # 2. API /api/appointments/available-staff không có inactive
    res_avail = client.post("/api/appointments/available-staff", json={
        "ngaygio": slot_str,
        "madv_list": [sv_45_id]
    })
    assert res_avail.status_code == 200
    avail_staff_ids = [s["manv"] for s in res_avail.get_json()["staff"]]
    assert inactive_id not in avail_staff_ids

    # 3. check_staff_availability trực tiếp trả về inactive
    with app.app_context():
        is_avail, _, reason = appointment_service.check_staff_availability(
            manv=inactive_id,
            start_dt=slot_str,
            duration_minutes=45,
        )
        assert is_avail is False
        assert reason == AVAILABILITY_REASON_INACTIVE


# =========================================================================
# 6. API lỗi => frontend không hiển thị "Đã bận"
# =========================================================================
def test_6_api_error_returns_error_and_does_not_show_busy(client):
    # Gửi request thiếu tham số vào /api/appointments/available-staff
    res = client.post("/api/appointments/available-staff", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False

    # Gửi request thiếu tham số vào /check-availability
    res_check = client.post("/api/appointments/check-availability", json={})
    assert res_check.status_code == 400
    data_check = res_check.get_json()
    assert data_check["available"] is False
    assert data_check["reason"] == AVAILABILITY_REASON_INVALID


# =========================================================================
# 7. Hai dịch vụ cộng thời lượng đúng
# =========================================================================
def test_7_multiple_services_duration_sum(app, availability_data):
    sv_45 = availability_data["sv_45_id"]
    sv_60 = availability_data["sv_60_id"]

    with app.app_context():
        total = appointment_service.calculate_total_duration([sv_45, sv_60])
        assert total == 105  # 45 + 60 = 105 phút


# =========================================================================
# 8. Một lịch 60 phút và lịch mới bắt đầu giữa khoảng đó => conflict
# =========================================================================
def test_8_appointment_starting_in_middle_of_60min_conflicts(app, availability_data):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]
    sv_60_id = availability_data["sv_60_id"]
    customer_id = app.config["TEST_CUSTOMER_ID"]

    with app.app_context():
        # Lịch hiện tại: 13:00 - 14:00 (60 phút)
        apt = LichHen(
            makh=customer_id,
            manv=tech1_id,
            ngaygio=datetime.combine(test_date, time(13, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=sv_60_id))
        db.session.commit()

        # Lịch mới bắt đầu lúc 13:30 (giữa khoảng 13:00 - 14:00)
        start_middle = datetime.combine(test_date, time(13, 30))
        is_avail, conflicts, reason = appointment_service.check_staff_availability(
            manv=tech1_id,
            start_dt=start_middle,
            duration_minutes=30,
        )
        assert is_avail is False
        assert reason == AVAILABILITY_REASON_CONFLICT
        assert len(conflicts) == 1
        assert conflicts[0]["ngaygio"] == "13:00"


# =========================================================================
# 9. Auto assign không chọn người không có ca
# =========================================================================
def test_9_auto_assign_excludes_staff_without_shift(app, availability_data):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]  # có ca
    tech2_id = availability_data["tech2_id"]  # không có ca
    sv_45_id = availability_data["sv_45_id"]

    slot_dt = datetime.combine(test_date, time(9, 30))
    with app.app_context():
        best_staff, candidates = appointment_service.find_available_staff(slot_dt, [sv_45_id])
        assert best_staff is not None
        assert best_staff.manv == tech1_id
        candidate_ids = [c["manv"] for c in candidates]
        assert tech2_id not in candidate_ids


# =========================================================================
# 10. Auto assign không chọn người đang bận
# =========================================================================
def test_10_auto_assign_excludes_busy_staff(app, availability_data):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]
    tech2_id = availability_data["tech2_id"]
    sv_60_id = availability_data["sv_60_id"]
    customer_id = app.config["TEST_CUSTOMER_ID"]

    with app.app_context():
        # Gán ca làm việc cho tech2 để cả hai đều có ca
        shift = CaLam.query.get(availability_data["shift_id"])
        db.session.execute(nhanvien_calam.insert().values(manv=tech2_id, maca=shift.maca))

        # Đặt lịch cho tech1 lúc 14:00 - 15:00
        apt = LichHen(
            makh=customer_id,
            manv=tech1_id,
            ngaygio=datetime.combine(test_date, time(14, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=sv_60_id))
        db.session.commit()

        # Khách cần đặt lúc 14:15 -> auto-assign phải chọn tech2 vì tech1 đang bận
        slot_dt = datetime.combine(test_date, time(14, 15))
        best_staff, candidates = appointment_service.find_available_staff(slot_dt, [sv_60_id])
        assert best_staff is not None
        assert best_staff.manv == tech2_id
        candidate_ids = [c["manv"] for c in candidates]
        assert tech1_id not in candidate_ids


# =========================================================================
# 11. Nếu có nhiều người rảnh => ưu tiên người ít lịch hơn
# =========================================================================
def test_11_auto_assign_prioritizes_staff_with_fewer_appointments(app, availability_data):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]
    tech2_id = availability_data["tech2_id"]
    sv_45_id = availability_data["sv_45_id"]
    customer_id = app.config["TEST_CUSTOMER_ID"]

    with app.app_context():
        # Cả 2 đều có ca
        shift = CaLam.query.get(availability_data["shift_id"])
        db.session.execute(nhanvien_calam.insert().values(manv=tech2_id, maca=shift.maca))

        # tech1 đã có 2 lịch hẹn trong ngày (buổi sáng: 08:30 và 09:30)
        apt1 = LichHen(
            makh=customer_id,
            manv=tech1_id,
            ngaygio=datetime.combine(test_date, time(8, 30)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        apt2 = LichHen(
            makh=customer_id,
            manv=tech1_id,
            ngaygio=datetime.combine(test_date, time(9, 30)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        # tech2 chỉ có 0 lịch hẹn
        db.session.add_all([apt1, apt2])
        db.session.commit()

        # Lúc 15:00 cả hai đều rảnh -> auto assign ưu tiên tech2 (0 lịch < 2 lịch)
        slot_dt = datetime.combine(test_date, time(15, 0))
        best_staff, candidates = appointment_service.find_available_staff(slot_dt, [sv_45_id])
        assert best_staff is not None
        assert best_staff.manv == tech2_id


# =========================================================================
# 12. Không có ai rảnh => trả thông báo rõ, không tạo lịch
# =========================================================================
def test_12_no_staff_available_returns_clear_error_and_no_appointment_created(
    app, client, customer_auth_headers, availability_data
):
    test_date = availability_data["test_date"]
    tech1_id = availability_data["tech1_id"]
    sv_60_id = availability_data["sv_60_id"]
    customer_id = app.config["TEST_CUSTOMER_ID"]

    # tech1 là người duy nhất có ca ở test_date. Đặt lịch cho tech1 lúc 16:00 - 17:00
    with app.app_context():
        apt = LichHen(
            makh=customer_id,
            manv=tech1_id,
            ngaygio=datetime.combine(test_date, time(16, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        db.session.add(apt)
        db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=sv_60_id))
        db.session.commit()
        initial_count = LichHen.query.count()

    # Khách đặt lịch tự động lúc 16:30 (không còn ai rảnh)
    payload = {
        "madv_list": [sv_60_id],
        "ngaygio": datetime.combine(test_date, time(16, 30)).strftime("%Y-%m-%dT%H:%M"),
    }
    res = client.post("/api/appointments/create", json=payload, headers=customer_auth_headers)
    assert res.status_code == 409
    data = res.get_json()
    assert data["success"] is False
    assert "Không có nhân viên rảnh" in data["message"]

    # Đảm bảo không tạo thêm lịch hẹn mới
    with app.app_context():
        assert LichHen.query.count() == initial_count


@pytest.mark.parametrize("role,active,position,eligible", [
    # Quy tắc: nhận khách khi vai trò 'staff' HOẶC chức vụ "Kỹ thuật viên" (như hiện ở ca làm), và đang hoạt động.
    ("letan", True, "Lễ tân", False), ("manager", True, "Quản lý", False), ("admin", True, "Quản lý", False),
    ("staff", False, "Kỹ thuật viên", False),
    ("manager", True, "Kỹ thuật viên", True),
])
def test_shift_eligibility_follows_role_or_technician_position(
    app, client, availability_data, role, active, position, eligible
):
    """Có ca chưa đủ: phải là kỹ thuật viên (vai trò staff hoặc chức vụ KTV) và đang hoạt động."""
    with app.app_context():
        cv = ChucVu.query.filter_by(tencv=position).first()
        if cv is None:
            cv = ChucVu(tencv=position, dongiagio=100000)
            db.session.add(cv); db.session.flush()
        tech = db.session.get(NhanVien, availability_data["tech2_id"])
        tech.role = role
        tech.trangthai = active
        tech.macv = cv.macv
        db.session.execute(nhanvien_calam.insert().values(
            manv=tech.manv, maca=availability_data["shift_id"]
        ))
        db.session.commit()

    expected = [availability_data["tech1_id"]] + ([availability_data["tech2_id"]] if eligible else [])
    slot = datetime.combine(availability_data["test_date"], time(9, 0))
    res = client.post("/api/appointments/available-staff", json={
        "ngaygio": slot.isoformat(), "madv_list": [availability_data["sv_45_id"]],
    })
    assert res.status_code == 200
    assert sorted(s["manv"] for s in res.get_json()["staff"]) == sorted(expected)
    public_staff = client.get("/api/staff").get_json()["staff"]
    assert (availability_data["tech2_id"] in {s["manv"] for s in public_staff}) is eligible
    with app.app_context():
        best, candidates = appointment_service.find_available_staff(slot, [availability_data["sv_45_id"]])
        assert sorted(s["manv"] for s in candidates) == sorted(expected)


@pytest.mark.parametrize("day_offset,hour,minute,service_keys,expected", [
    (0, 8, 0, ["sv_45_id"], True),       # Shift starts exactly at booking time.
    (0, 17, 15, ["sv_45_id"], True),    # Service finishes exactly at shift end.
    (0, 7, 59, ["sv_45_id"], False),
    (0, 17, 16, ["sv_45_id"], False),
    (0, 16, 30, ["sv_45_id", "sv_60_id"], False),
    (1, 9, 0, ["sv_45_id"], False),     # Shift on a different date.
    (0, 23, 30, ["sv_60_id"], False),   # Must not wrap end time past midnight.
])
def test_booking_requires_shift_covering_entire_service_range(
    app, client, availability_data, day_offset, hour, minute, service_keys, expected
):
    slot = datetime.combine(
        availability_data["test_date"] + timedelta(days=day_offset), time(hour, minute)
    )
    service_ids = [availability_data[key] for key in service_keys]
    res = client.post("/api/appointments/available-staff", json={
        "ngaygio": slot.isoformat(), "madv_list": service_ids,
    })
    assert res.status_code == 200
    staff = res.get_json()["staff"]
    assert [s["manv"] for s in staff] == ([availability_data["tech1_id"]] if expected else [])
    assert all(s["available"] and s["reason"] == "available" for s in staff)
    with app.app_context():
        working = appointment_service.get_staff_working_at(
            slot, appointment_service.calculate_total_duration(service_ids)
        )
        assert bool(working) == expected
        best, candidates = appointment_service.find_available_staff(slot, service_ids)
        assert bool(best) == expected
        assert bool(candidates) == expected

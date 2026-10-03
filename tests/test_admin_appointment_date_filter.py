import re
from datetime import datetime, date, time, timedelta
import pytest
from app.extensions import db
from app.models import (
    NhanVien,
    KhachHang,
    DichVu,
    LichHen,
    ChiTietLichHen,
    AppointmentStatus,
)


@pytest.fixture
def seed_admin_appointments(app):
    """Seed test appointments on multiple dates and statuses for filter testing."""
    with app.app_context():
        customer = KhachHang.query.filter_by(makh=app.config["TEST_CUSTOMER_ID"]).first()
        staff = NhanVien.query.filter_by(manv=app.config["TEST_STAFF_ID"]).first()

        sv = DichVu(tendv="Dịch vụ Test Filter", gia=150000, thoiluong=45, active=True)
        db.session.add(sv)
        db.session.flush()

        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        two_weeks_ago = today - timedelta(days=14)

        # 1. Hôm nay: 1 confirmed, 1 completed
        apt_today_1 = LichHen(
            makh=customer.makh,
            manv=staff.manv,
            ngaygio=datetime.combine(today, time(9, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )
        apt_today_2 = LichHen(
            makh=customer.makh,
            manv=staff.manv,
            ngaygio=datetime.combine(today, time(14, 0)),
            trangthai=AppointmentStatus.COMPLETED,
        )

        # 2. Hôm qua: 1 confirmed
        apt_yesterday = LichHen(
            makh=customer.makh,
            manv=staff.manv,
            ngaygio=datetime.combine(yesterday, time(10, 0)),
            trangthai=AppointmentStatus.CONFIRMED,
        )

        # 3. Ngày mai: 1 pending
        apt_tomorrow = LichHen(
            makh=customer.makh,
            manv=staff.manv,
            ngaygio=datetime.combine(tomorrow, time(11, 0)),
            trangthai=AppointmentStatus.PENDING,
        )

        # 4. 2 tuần trước: 1 cancelled
        apt_old = LichHen(
            makh=customer.makh,
            manv=staff.manv,
            ngaygio=datetime.combine(two_weeks_ago, time(15, 0)),
            trangthai=AppointmentStatus.CANCELLED,
        )

        # 5. Lịch lúc 23:30 cuối ngày 2026-10-05 (kiểm tra ranh giới cuối ngày)
        test_custom_date = date(2026, 10, 5)
        apt_late_night = LichHen(
            makh=customer.makh,
            manv=staff.manv,
            ngaygio=datetime.combine(test_custom_date, time(23, 30)),
            trangthai=AppointmentStatus.CONFIRMED,
        )

        db.session.add_all([
            apt_today_1, apt_today_2, apt_yesterday, apt_tomorrow,
            apt_old, apt_late_night
        ])
        db.session.flush()

        for a in [apt_today_1, apt_today_2, apt_yesterday, apt_tomorrow, apt_old, apt_late_night]:
            db.session.add(ChiTietLichHen(malh=a.malh, madv=sv.madv))

        db.session.commit()

        return {
            "today": today.isoformat(),
            "yesterday": yesterday.isoformat(),
            "tomorrow": tomorrow.isoformat(),
            "apt_today_1_id": apt_today_1.malh,
            "apt_today_2_id": apt_today_2.malh,
            "apt_yesterday_id": apt_yesterday.malh,
            "apt_late_night_id": apt_late_night.malh,
            "apt_old_id": apt_old.malh,
        }


# =========================================================================
# 1. Tổng toàn bộ => không gửi start_date/end_date
# =========================================================================
def test_1_filter_total_no_date_params(client, admin_auth_headers, seed_admin_appointments):
    # API danh sách
    res = client.get("/api/admin/appointments", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()
    assert len(apts) >= 6

    # API thống kê
    res_stats = client.get("/api/admin/appointments/statistics", headers=admin_auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total"] == len(apts)


# =========================================================================
# 2. Hôm nay => chỉ lịch hôm nay
# =========================================================================
def test_2_filter_today(client, admin_auth_headers, seed_admin_appointments):
    today_str = seed_admin_appointments["today"]

    # Table
    res = client.get(f"/api/admin/appointments?start_date={today_str}&end_date={today_str}", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()
    assert len(apts) == 2
    for a in apts:
        assert a["ngaygio"].startswith(today_str)

    # Statistics
    res_stats = client.get(f"/api/admin/appointments/statistics?start_date={today_str}&end_date={today_str}", headers=admin_auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total"] == 2
    assert stats["confirmed"] == 1
    assert stats["completed"] == 1


# =========================================================================
# 3. Tuần này => đúng range từ Thứ Hai đến hôm nay
# =========================================================================
def test_3_filter_this_week(client, admin_auth_headers, seed_admin_appointments):
    today = date.today()
    day_of_week = today.weekday()  # Monday = 0
    start_of_week = today - timedelta(days=day_of_week)

    start_str = start_of_week.isoformat()
    end_str = today.isoformat()

    res = client.get(f"/api/admin/appointments?start_date={start_str}&end_date={end_str}", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()

    res_stats = client.get(f"/api/admin/appointments/statistics?start_date={start_str}&end_date={end_str}", headers=admin_auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total"] == len(apts)


# =========================================================================
# 4. Tháng này => từ ngày 1 đến hôm nay
# =========================================================================
def test_4_filter_this_month(client, admin_auth_headers, seed_admin_appointments):
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    start_str = start_of_month.isoformat()
    end_str = today.isoformat()

    res = client.get(f"/api/admin/appointments?start_date={start_str}&end_date={end_str}", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()

    res_stats = client.get(f"/api/admin/appointments/statistics?start_date={start_str}&end_date={end_str}", headers=admin_auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total"] == len(apts)


# =========================================================================
# 5. Custom một ngày (start=2026-10-02, end=2026-10-02)
# =========================================================================
def test_5_custom_single_day(client, admin_auth_headers, seed_admin_appointments):
    target = date.today().isoformat()

    res = client.get(f"/api/admin/appointments?start_date={target}&end_date={target}", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()
    assert len(apts) == 2
    for a in apts:
        assert a["ngaygio"].startswith(target)

    res_stats = client.get(f"/api/admin/appointments/statistics?start_date={target}&end_date={target}", headers=admin_auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total"] == 2


# =========================================================================
# 6. Custom khoảng: 2026-10-01 -> 2026-10-05
# =========================================================================
def test_6_custom_date_range(client, admin_auth_headers, seed_admin_appointments):
    start = "2026-10-01"
    end = "2026-10-05"

    res = client.get(f"/api/admin/appointments?start_date={start}&end_date={end}", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()
    apt_ids = [a["malh"] for a in apts]

    assert seed_admin_appointments["apt_yesterday_id"] in apt_ids   # 2026-10-01
    assert seed_admin_appointments["apt_today_1_id"] in apt_ids     # 2026-10-02
    assert seed_admin_appointments["apt_today_2_id"] in apt_ids     # 2026-10-02
    assert seed_admin_appointments["apt_late_night_id"] in apt_ids   # 2026-10-05 23:30
    assert seed_admin_appointments["apt_old_id"] not in apt_ids


# =========================================================================
# 7. Lịch lúc 23:30 ngày 2026-10-05 xuất hiện khi end_date=2026-10-05
# =========================================================================
def test_7_appointment_at_end_of_day_included(client, admin_auth_headers, seed_admin_appointments):
    target_date = "2026-10-05"

    res = client.get(f"/api/admin/appointments?start_date={target_date}&end_date={target_date}", headers=admin_auth_headers)
    assert res.status_code == 200
    apts = res.get_json()
    assert len(apts) == 1
    assert apts[0]["malh"] == seed_admin_appointments["apt_late_night_id"]
    assert "23:30" in apts[0]["ngaygio"]

    # Statistics cũng phải tính cả lịch này
    res_stats = client.get(f"/api/admin/appointments/statistics?start_date={target_date}&end_date={target_date}", headers=admin_auth_headers)
    assert res_stats.status_code == 200
    stats = res_stats.get_json()["statistics"]
    assert stats["total"] == 1
    assert stats["confirmed"] == 1


# =========================================================================
# 8 & 9. Frontend JS validation tests (kiểm tra logic quy tắc custom)
# =========================================================================
def test_8_and_9_frontend_custom_date_validation_contract():
    with open("app/static/js/admin/appointments.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    # Rule 8: end_date < start_date báo lỗi không được nhỏ hơn và trả về null (không gọi API)
    assert "Ngày kết thúc không được nhỏ hơn ngày bắt đầu" in js_code
    assert "return null" in js_code

    # Rule 9: thiếu start_date báo lỗi vui lòng chọn ngày bắt đầu
    assert "Vui lòng chọn ngày bắt đầu" in js_code

    # Rule 1: chỉ chọn start_date thì end_date tự bằng start_date
    assert "endVal = startVal" in js_code


# =========================================================================
# 10. Đổi từ custom sang option định sẵn tự ẩn custom date area
# =========================================================================
def test_10_handle_date_select_change_hides_custom_area():
    with open("app/static/js/admin/appointments.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "handleDateSelectChange" in js_code
    assert "customContainer.classList.add('d-none')" in js_code


# =========================================================================
# 11. Reset clear toàn bộ filter và ẩn custom date area
# =========================================================================
def test_11_reset_filters_contract():
    with open("app/static/js/admin/appointments.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "function resetFilters" in js_code
    assert "filterDateSelect.value = ''" in js_code
    assert "filterStatusSelect.value = ''" in js_code
    assert "startInput.value = ''" in js_code
    assert "endInput.value = ''" in js_code
    assert "customContainer.classList.add('d-none')" in js_code


# =========================================================================
# 12. Bảng lịch và statistics dùng cùng dateRange
# =========================================================================
def test_12_table_and_statistics_use_same_date_range_contract():
    with open("app/static/js/admin/appointments.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    # Cả hai hàm đều nhận cùng dateRange từ getActiveDateRange
    assert "function getActiveDateRange()" in js_code
    assert "loadAppointments(filters, dateRange)" in js_code
    assert "loadStatistics(dateRange)" in js_code


# =========================================================================
# 13. Filter trạng thái hoạt động chung với filter ngày
# =========================================================================
def test_13_status_filter_works_with_date_filter(client, admin_auth_headers, seed_admin_appointments):
    today_str = seed_admin_appointments["today"]

    # Lọc hôm nay + trạng thái confirmed (chỉ có apt_today_1)
    res_conf = client.get(f"/api/admin/appointments?start_date={today_str}&end_date={today_str}&status=confirmed", headers=admin_auth_headers)
    assert res_conf.status_code == 200
    apts_conf = res_conf.get_json()
    assert len(apts_conf) == 1
    assert apts_conf[0]["malh"] == seed_admin_appointments["apt_today_1_id"]

    # Lọc hôm nay + trạng thái completed (chỉ có apt_today_2)
    res_comp = client.get(f"/api/admin/appointments?start_date={today_str}&end_date={today_str}&status=completed", headers=admin_auth_headers)
    assert res_comp.status_code == 200
    apts_comp = res_comp.get_json()
    assert len(apts_comp) == 1
    assert apts_comp[0]["malh"] == seed_admin_appointments["apt_today_2_id"]


# =========================================================================
# 14. Search vẫn hoạt động sau khi filter ngày
# =========================================================================
def test_14_search_works_with_filter():
    with open("app/static/js/admin/appointments.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "function searchAppointments" in js_code
    assert "function clearSearch" in js_code


# =========================================================================
# 15. UI HTML chứa đúng IDs và cấu trúc theo Bước 2
# =========================================================================
def test_15_html_custom_date_ui_elements():
    with open("app/templates/admin/appointments.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="filter-date-select"' in html
    assert 'id="custom-date-filter"' in html
    assert 'id="filter-start-date"' in html
    assert 'id="filter-end-date"' in html
    assert 'onchange="handleDateSelectChange()"' in html
    assert 'onclick="applyCustomDateFilter()"' in html

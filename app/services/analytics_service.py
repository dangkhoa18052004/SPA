# app/services/analytics_service.py
"""
Analytics Service - Doanh thu, Thống kê Lịch hẹn, Khách hàng & KPI Spa.
Doanh thu chuẩn xác dựa trên ThanhToan (sotien + ngaythanhtoan).
"""

from datetime import datetime, date, time, timedelta
from calendar import monthrange
from sqlalchemy import func, and_, or_, extract

from ..extensions import db
from ..models import (
    ThanhToan,
    HoaDon,
    LichHen,
    ChiTietLichHen,
    KhachHang,
    NhanVien,
    DichVu,
    CaLam,
    nhanvien_calam,
    AppointmentStatus,
)


def _parse_date_range(from_date, to_date, default_days=30):
    """Helper chuyển đổi tham số from/to thành datetime boundaries."""
    now = datetime.now()
    if not to_date:
        to_d = now.date()
    elif isinstance(to_date, str):
        to_d = datetime.strptime(to_date.strip()[:10], "%Y-%m-%d").date()
    elif isinstance(to_date, datetime):
        to_d = to_date.date()
    else:
        to_d = to_date

    if not from_date:
        from_d = to_d - timedelta(days=default_days - 1)
    elif isinstance(from_date, str):
        from_d = datetime.strptime(from_date.strip()[:10], "%Y-%m-%d").date()
    elif isinstance(from_date, datetime):
        from_d = from_date.date()
    else:
        from_d = from_date

    if from_d > to_d:
        from_d, to_d = to_d, from_d

    start_dt = datetime.combine(from_d, time.min)
    end_dt = datetime.combine(to_d, time.max)
    return from_d, to_d, start_dt, end_dt


def revenue_timeseries(from_date=None, to_date=None, group_by="day"):
    """
    Tính chuỗi thời gian doanh thu thực thu từ bảng ThanhToan.
    - group_by: 'day' hoặc 'month'.
    - Điền 0 vào các ngày/tháng không có phát sinh giao dịch để Chart.js vẽ liên tục.
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)

    payments = (
        db.session.query(
            ThanhToan.ngaythanhtoan,
            ThanhToan.sotien,
        )
        .filter(
            ThanhToan.ngaythanhtoan >= start_dt,
            ThanhToan.ngaythanhtoan <= end_dt,
            ThanhToan.sotien > 0,
        )
        .order_by(ThanhToan.ngaythanhtoan.asc())
        .all()
    )

    data_map = {}
    trans_map = {}

    if group_by == "month":
        # Tạo chuỗi các tháng liên tục từ from_d đến to_d
        cur_year, cur_month = from_d.year, from_d.month
        end_year, end_month = to_d.year, to_d.month
        while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
            key = f"{cur_year:04d}-{cur_month:02d}"
            data_map[key] = 0.0
            trans_map[key] = 0
            if cur_month == 12:
                cur_year += 1
                cur_month = 1
            else:
                cur_month += 1

        for p in payments:
            if p.ngaythanhtoan:
                key = p.ngaythanhtoan.strftime("%Y-%m")
                if key in data_map:
                    data_map[key] += float(p.sotien)
                    trans_map[key] += 1
    else:
        # group_by == 'day'
        cur_d = from_d
        while cur_d <= to_d:
            key = cur_d.strftime("%Y-%m-%d")
            data_map[key] = 0.0
            trans_map[key] = 0
            cur_d += timedelta(days=1)

        for p in payments:
            if p.ngaythanhtoan:
                key = p.ngaythanhtoan.strftime("%Y-%m-%d")
                if key in data_map:
                    data_map[key] += float(p.sotien)
                    trans_map[key] += 1

    labels = list(data_map.keys())
    revenue_data = [round(data_map[k], 2) for k in labels]
    records = [
        {"date": k, "revenue": round(data_map[k], 2), "transactions_count": trans_map[k]}
        for k in labels
    ]

    total_revenue = sum(revenue_data)
    total_transactions = sum(trans_map.values())

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "group_by": group_by,
        "total_revenue": round(total_revenue, 2),
        "total_transactions": total_transactions,
        "chart_data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Doanh thu (VNĐ)",
                    "data": revenue_data,
                    "borderColor": "#C9A961",
                    "backgroundColor": "rgba(201, 169, 97, 0.15)",
                    "fill": True,
                    "tension": 0.3,
                }
            ],
        },
        "records": records,
    }


def appointment_stats(from_date=None, to_date=None):
    """
    Thống kê số lượng lịch hẹn theo trạng thái chuẩn trong khoảng thời gian.
    Trả về dữ liệu phù hợp với Chart.js Doughnut/Pie chart.
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)

    apts = (
        db.session.query(
            LichHen.trangthai,
            func.count(LichHen.malh).label("cnt"),
        )
        .filter(
            LichHen.ngaygio >= start_dt,
            LichHen.ngaygio <= end_dt,
        )
        .group_by(LichHen.trangthai)
        .all()
    )

    counts = {
        AppointmentStatus.PENDING: 0,
        AppointmentStatus.CONFIRMED: 0,
        AppointmentStatus.IN_PROGRESS: 0,
        AppointmentStatus.COMPLETED: 0,
        AppointmentStatus.CANCELLED: 0,
    }

    for row in apts:
        norm = AppointmentStatus.normalize(row.trangthai)
        if norm in counts:
            counts[norm] += row.cnt

    total = sum(counts.values())

    status_keys = [
        AppointmentStatus.PENDING,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
    ]
    labels = [AppointmentStatus.to_vietnamese(s) for s in status_keys]
    values = [counts[s] for s in status_keys]
    colors = [
        "#ffc107",  # pending: vàng
        "#17a2b8",  # confirmed: xanh cyan
        "#6f42c1",  # in_progress: tím
        "#28a745",  # completed: xanh lá
        "#dc3545",  # cancelled: đỏ
    ]

    percentages = {
        s: round((counts[s] / total * 100), 1) if total > 0 else 0.0
        for s in status_keys
    }

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "total_appointments": total,
        "counts": counts,
        "percentages": percentages,
        "chart_data": {
            "labels": labels,
            "datasets": [
                {
                    "data": values,
                    "backgroundColor": colors,
                    "borderWidth": 1,
                }
            ],
        },
    }


def average_invoice(from_date=None, to_date=None):
    """
    Tính giá trị trung bình mỗi hóa đơn / thanh toán (AOV).
    Dựa trên thực thu từ bảng ThanhToan.
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)

    res = (
        db.session.query(
            func.coalesce(func.sum(ThanhToan.sotien), 0).label("total_rev"),
            func.count(ThanhToan.matt).label("total_tx"),
            func.coalesce(func.avg(ThanhToan.sotien), 0).label("avg_tx"),
        )
        .filter(
            ThanhToan.ngaythanhtoan >= start_dt,
            ThanhToan.ngaythanhtoan <= end_dt,
            ThanhToan.sotien > 0,
        )
        .first()
    )

    total_revenue = float(res.total_rev) if res else 0.0
    total_transactions = int(res.total_tx) if res else 0
    average_value = float(res.avg_tx) if res else 0.0

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "total_revenue": round(total_revenue, 2),
        "total_transactions": total_transactions,
        "average_invoice": round(average_value, 2),
    }


def top_services(from_date=None, to_date=None, limit=5):
    """
    Top các dịch vụ được khách hàng lựa chọn nhiều nhất trong khoảng thời gian.
    Chỉ tính các lịch hẹn hợp lệ (không bị hủy).
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)

    query = (
        db.session.query(
            DichVu.madv,
            DichVu.tendv,
            DichVu.gia,
            func.count(ChiTietLichHen.malh).label("booking_count"),
            func.sum(DichVu.gia).label("estimated_revenue"),
        )
        .join(ChiTietLichHen, DichVu.madv == ChiTietLichHen.madv)
        .join(LichHen, ChiTietLichHen.malh == LichHen.malh)
        .filter(
            LichHen.ngaygio >= start_dt,
            LichHen.ngaygio <= end_dt,
            LichHen.trangthai.in_([
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.IN_PROGRESS,
                AppointmentStatus.COMPLETED,
            ]),
        )
        .group_by(DichVu.madv, DichVu.tendv, DichVu.gia)
        .order_by(func.count(ChiTietLichHen.malh).desc())
        .limit(limit)
    )

    items = query.all()
    results = [
        {
            "madv": item.madv,
            "tendv": item.tendv,
            "gia": float(item.gia),
            "booking_count": item.booking_count,
            "estimated_revenue": float(item.estimated_revenue or 0),
        }
        for item in items
    ]

    labels = [r["tendv"] for r in results]
    counts = [r["booking_count"] for r in results]

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "top_services": results,
        "chart_data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Số lượt đặt",
                    "data": counts,
                    "backgroundColor": [
                        "#C9A961",
                        "#4a7c59",
                        "#2c5282",
                        "#9b2c2c",
                        "#dd6b20",
                    ][: len(labels)],
                }
            ],
        },
    }


def new_customers(from_date=None, to_date=None):
    """
    Thống kê số lượng khách hàng mới đăng ký tài khoản (KhachHang.ngaytao).
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)

    customers = (
        db.session.query(KhachHang.ngaytao)
        .filter(
            KhachHang.ngaytao >= start_dt,
            KhachHang.ngaytao <= end_dt,
        )
        .all()
    )

    day_map = {}
    cur_d = from_d
    while cur_d <= to_d:
        day_map[cur_d.strftime("%Y-%m-%d")] = 0
        cur_d += timedelta(days=1)

    for c in customers:
        if c.ngaytao:
            k = c.ngaytao.strftime("%Y-%m-%d")
            if k in day_map:
                day_map[k] += 1

    labels = list(day_map.keys())
    data = [day_map[k] for k in labels]

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "total_new_customers": len(customers),
        "chart_data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Khách hàng mới",
                    "data": data,
                    "borderColor": "#4a7c59",
                    "backgroundColor": "rgba(74, 124, 89, 0.2)",
                    "tension": 0.2,
                }
            ],
        },
    }


def get_kpi_cards(target_date=None):
    """
    Tính toán các chỉ số KPI Cards cho Dashboard Quản trị.
    FIX BUG:
    1. Doanh thu hôm nay: CHỈ tính từ các khoản ThanhToan có ngaythanhtoan trong ngày hôm nay.
    2. Khách hàng mới tháng này: Lọc theo KhachHang.ngaytao >= đầu tháng.
    3. Doanh thu tháng: Tổng ThanhToan trong tháng hiện tại.
    """
    if not target_date:
        today = date.today()
    elif isinstance(target_date, str):
        today = datetime.strptime(target_date.strip()[:10], "%Y-%m-%d").date()
    elif isinstance(target_date, datetime):
        today = target_date.date()
    else:
        today = target_date

    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    month_start = today.replace(day=1)
    _, last_day = monthrange(today.year, today.month)
    month_end = datetime.combine(today.replace(day=last_day), time.max)
    month_start_dt = datetime.combine(month_start, time.min)

    # 1. Doanh thu hôm nay (chính xác từ ThanhToan)
    today_revenue = (
        db.session.query(func.coalesce(func.sum(ThanhToan.sotien), 0))
        .filter(
            ThanhToan.ngaythanhtoan >= today_start,
            ThanhToan.ngaythanhtoan <= today_end,
            ThanhToan.sotien > 0,
        )
        .scalar()
        or 0
    )

    # 2. Doanh thu tháng này (chính xác từ ThanhToan)
    month_revenue = (
        db.session.query(func.coalesce(func.sum(ThanhToan.sotien), 0))
        .filter(
            ThanhToan.ngaythanhtoan >= month_start_dt,
            ThanhToan.ngaythanhtoan <= month_end,
            ThanhToan.sotien > 0,
        )
        .scalar()
        or 0
    )

    # 3. Lịch hẹn hôm nay
    today_appointments = (
        db.session.query(LichHen)
        .filter(
            LichHen.ngaygio >= today_start,
            LichHen.ngaygio <= today_end,
        )
        .all()
    )

    status_counts = {
        "pending": 0,
        "confirmed": 0,
        "in_progress": 0,
        "completed": 0,
        "cancelled": 0,
    }
    for a in today_appointments:
        norm = AppointmentStatus.normalize(a.trangthai)
        if norm in status_counts:
            status_counts[norm] += 1

    # 4. Nhân viên có ca trực hôm nay
    working_staff_today = (
        db.session.query(func.count(func.distinct(nhanvien_calam.c.manv)))
        .join(CaLam, nhanvien_calam.c.maca == CaLam.maca)
        .filter(CaLam.ngay == today)
        .scalar()
        or 0
    )

    # 5. Khách hàng mới tháng này (FIX BUG: lọc theo ngaytao)
    new_customers_month = (
        db.session.query(func.count(KhachHang.makh))
        .filter(
            KhachHang.ngaytao >= month_start_dt,
            KhachHang.ngaytao <= month_end,
        )
        .scalar()
        or 0
    )

    total_customers = db.session.query(func.count(KhachHang.makh)).scalar() or 0
    active_staff = (
        db.session.query(func.count(NhanVien.manv))
        .filter(NhanVien.trangthai == True)
        .scalar()
        or 0
    )

    # 6. Giá trị thanh toán trung bình (AOV) tháng này
    month_aov_res = (
        db.session.query(func.coalesce(func.avg(ThanhToan.sotien), 0))
        .filter(
            ThanhToan.ngaythanhtoan >= month_start_dt,
            ThanhToan.ngaythanhtoan <= month_end,
            ThanhToan.sotien > 0,
        )
        .scalar()
        or 0
    )

    return {
        "success": True,
        "date": today.isoformat(),
        "today": {
            "revenue": float(today_revenue),
            "total_appointments": len(today_appointments),
            "appointments_by_status": status_counts,
            "working_staff": working_staff_today,
        },
        "month": {
            "revenue": float(month_revenue),
            "new_customers": new_customers_month,
            "average_invoice": float(month_aov_res),
        },
        "general": {
            "total_customers": total_customers,
            "active_staff": active_staff,
        },
    }

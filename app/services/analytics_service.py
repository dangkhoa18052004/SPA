# app/services/analytics_service.py
"""
Analytics Service - Doanh thu, Thống kê Lịch hẹn, Khách hàng & KPI Spa.
Doanh thu thực thu = dịch vụ (ThanhToan.sotien theo ngaythanhtoan)
                     + bán gói (GoiDichVuPurchase.payable_amount theo paid_at, status='paid').
Lượt dùng buổi gói không tạo ThanhToan nên không bị tính doanh thu lần hai.
"""

from datetime import datetime, date, time, timedelta
from calendar import monthrange
from decimal import Decimal
from sqlalchemy import func, and_, or_, extract

from ..extensions import db
from ..models import (
    ThanhToan,
    HoaDon,
    GoiDichVuPurchase,
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


def _service_payments(start_dt, end_dt):
    return (
        db.session.query(ThanhToan.ngaythanhtoan, ThanhToan.sotien)
        .filter(
            ThanhToan.ngaythanhtoan >= start_dt,
            ThanhToan.ngaythanhtoan <= end_dt,
            ThanhToan.sotien > 0,
        )
        .all()
    )


def _package_payments(start_dt, end_dt):
    """Gói đã thanh toán: số thực thu sau ưu đãi/điểm; gói trả bằng điểm (0đ) bị loại."""
    return (
        db.session.query(GoiDichVuPurchase.paid_at, GoiDichVuPurchase.payable_amount)
        .filter(
            GoiDichVuPurchase.status == 'paid',
            GoiDichVuPurchase.paid_at >= start_dt,
            GoiDichVuPurchase.paid_at <= end_dt,
            GoiDichVuPurchase.payable_amount > 0,
        )
        .all()
    )


def revenue_breakdown(start_dt, end_dt):
    """Tổng thực thu trong khoảng: tách dịch vụ, gói và tổng (Decimal)."""
    service_rows = _service_payments(start_dt, end_dt)
    package_rows = _package_payments(start_dt, end_dt)
    service = sum((Decimal(r[1]) for r in service_rows), Decimal('0'))
    package = sum((Decimal(r[1]) for r in package_rows), Decimal('0'))
    return {
        "service": service,
        "package": package,
        "total": service + package,
        "service_transactions": len(service_rows),
        "package_transactions": len(package_rows),
    }


def _money(value):
    return float(round(value, 2))


def revenue_timeseries(from_date=None, to_date=None, group_by="day"):
    """
    Chuỗi thời gian doanh thu thực thu (dịch vụ + bán gói).
    - group_by: 'day' hoặc 'month'.
    - Điền 0 vào các ngày/tháng không có phát sinh giao dịch để Chart.js vẽ liên tục.
    - total_revenue là tổng; service_revenue/package_revenue là phần tách riêng.
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)

    keys = []
    if group_by == "month":
        fmt = "%Y-%m"
        cur_year, cur_month = from_d.year, from_d.month
        while (cur_year, cur_month) <= (to_d.year, to_d.month):
            keys.append(f"{cur_year:04d}-{cur_month:02d}")
            cur_year, cur_month = (cur_year + 1, 1) if cur_month == 12 else (cur_year, cur_month + 1)
    else:
        fmt = "%Y-%m-%d"
        cur_d = from_d
        while cur_d <= to_d:
            keys.append(cur_d.strftime(fmt))
            cur_d += timedelta(days=1)

    service_map = {k: Decimal('0') for k in keys}
    package_map = {k: Decimal('0') for k in keys}
    trans_map = {k: 0 for k in keys}

    for target, rows in ((service_map, _service_payments(start_dt, end_dt)),
                         (package_map, _package_payments(start_dt, end_dt))):
        for paid_at, amount in rows:
            if not paid_at:
                continue
            key = paid_at.strftime(fmt)
            if key in target:
                target[key] += Decimal(amount)
                trans_map[key] += 1

    total_map = {k: service_map[k] + package_map[k] for k in keys}
    records = [
        {
            "date": k,
            "revenue": _money(total_map[k]),
            "service_revenue": _money(service_map[k]),
            "package_revenue": _money(package_map[k]),
            "transactions_count": trans_map[k],
        }
        for k in keys
    ]

    service_total = sum(service_map.values(), Decimal('0'))
    package_total = sum(package_map.values(), Decimal('0'))

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "group_by": group_by,
        "total_revenue": _money(service_total + package_total),
        "service_revenue": _money(service_total),
        "package_revenue": _money(package_total),
        "total_transactions": sum(trans_map.values()),
        "chart_data": {
            "labels": keys,
            "datasets": [
                {
                    "label": "Tổng thực thu (VNĐ)",
                    "data": [_money(total_map[k]) for k in keys],
                    "borderColor": "#C9A961",
                    "backgroundColor": "rgba(201, 169, 97, 0.15)",
                    "fill": True,
                    "tension": 0.3,
                },
                {
                    "label": "Dịch vụ",
                    "data": [_money(service_map[k]) for k in keys],
                    "borderColor": "#4a7c59",
                    "backgroundColor": "rgba(74, 124, 89, 0.1)",
                    "fill": False,
                    "tension": 0.3,
                },
                {
                    "label": "Bán gói",
                    "data": [_money(package_map[k]) for k in keys],
                    "borderColor": "#2c5282",
                    "backgroundColor": "rgba(44, 82, 130, 0.1)",
                    "fill": False,
                    "tension": 0.3,
                },
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
    Giá trị trung bình mỗi giao dịch thực thu (AOV), gồm thanh toán dịch vụ và bán gói.
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)
    rev = revenue_breakdown(start_dt, end_dt)
    total_transactions = rev["service_transactions"] + rev["package_transactions"]
    average_value = rev["total"] / total_transactions if total_transactions else Decimal('0')

    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "total_revenue": _money(rev["total"]),
        "service_revenue": _money(rev["service"]),
        "package_revenue": _money(rev["package"]),
        "total_transactions": total_transactions,
        "average_invoice": _money(average_value),
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
    1. Doanh thu hôm nay/tháng: thực thu dịch vụ + bán gói, kèm số tách riêng.
    2. Khách hàng mới tháng này: Lọc theo KhachHang.ngaytao trong tháng.
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

    # 1-2. Doanh thu thực thu hôm nay / tháng này (dịch vụ + bán gói)
    today_rev = revenue_breakdown(today_start, today_end)
    month_rev = revenue_breakdown(month_start_dt, month_end)

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

    # 6. Giá trị giao dịch trung bình (AOV) tháng này
    month_tx = month_rev["service_transactions"] + month_rev["package_transactions"]
    month_aov = month_rev["total"] / month_tx if month_tx else Decimal('0')

    return {
        "success": True,
        "date": today.isoformat(),
        "today": {
            "revenue": _money(today_rev["total"]),
            "service_revenue": _money(today_rev["service"]),
            "package_revenue": _money(today_rev["package"]),
            "total_appointments": len(today_appointments),
            "appointments_by_status": status_counts,
            "working_staff": working_staff_today,
        },
        "month": {
            "revenue": _money(month_rev["total"]),
            "service_revenue": _money(month_rev["service"]),
            "package_revenue": _money(month_rev["package"]),
            "new_customers": new_customers_month,
            "average_invoice": _money(month_aov),
        },
        "general": {
            "total_customers": total_customers,
            "active_staff": active_staff,
        },
    }


def dashboard_summary(from_date=None, to_date=None):
    """
    KPI dashboard dùng chung một khoảng ngày: thực thu (dịch vụ/gói/tổng), AOV,
    số lịch, số/tỷ lệ hủy, khách mới. Chart lấy từ các API cùng tham số from/to.
    """
    from_d, to_d, start_dt, end_dt = _parse_date_range(from_date, to_date)
    rev = revenue_breakdown(start_dt, end_dt)
    transactions = rev["service_transactions"] + rev["package_transactions"]
    stats = appointment_stats(from_d, to_d)
    total_appointments = stats["total_appointments"]
    cancelled = stats["counts"][AppointmentStatus.CANCELLED]
    new_count = (
        db.session.query(func.count(KhachHang.makh))
        .filter(KhachHang.ngaytao >= start_dt, KhachHang.ngaytao <= end_dt)
        .scalar()
        or 0
    )
    return {
        "success": True,
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "revenue": {
            "total": _money(rev["total"]),
            "service": _money(rev["service"]),
            "package": _money(rev["package"]),
            "transactions": transactions,
            "average_transaction": _money(rev["total"] / transactions) if transactions else 0.0,
        },
        "appointments": {
            "total": total_appointments,
            "completed": stats["counts"][AppointmentStatus.COMPLETED],
            "cancelled": cancelled,
            "cancel_rate": round(cancelled / total_appointments * 100, 1) if total_appointments else 0.0,
        },
        "new_customers": new_count,
    }

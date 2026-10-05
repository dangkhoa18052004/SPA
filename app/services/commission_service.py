"""Hoa hồng kỹ thuật viên. Caller giữ transaction (được gọi trong update_appointment_status).

Quy tắc base amount (giá trị tính hoa hồng) cho mỗi dịch vụ của lịch đã hoàn thành:
- regular (trả tiền lẻ, kể cả có voucher/điểm): giá niêm yết dịch vụ lúc hoàn thành.
  Ưu đãi do spa chịu, không làm giảm hoa hồng KTV.
- package (buổi trong gói): giá trị phân bổ của buổi (unit_value_snapshot của thẻ).
- gift (buổi quà tặng): giá niêm yết đã chụp khi tặng (regular_price_snapshot).

Mức hoa hồng: DichVu.commission_fixed (VNĐ/lượt) nếu có, ngược lại commission_percent × base.
Bản ghi được chụp lại khi ghi: đổi mức hoa hồng/giá về sau không sửa lịch sử.
Mỗi (lịch hẹn, dịch vụ) chỉ có một bản ghi; hoàn thành lặp không tạo thêm.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from sqlalchemy import func

from ..extensions import db
from ..models import CommissionEntry, DichVu, LieuTrinhUsage


def local_now():
    return datetime.utcnow() + timedelta(hours=7)


def _vnd(value):
    return Decimal(value or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def compute_amount(base, percent, fixed):
    if fixed is not None:
        return _vnd(fixed)
    if percent is not None:
        return _vnd(Decimal(base) * Decimal(percent) / Decimal(100))
    return Decimal('0')


def _source_for(usage, service):
    if usage is None:
        return 'regular', Decimal(service.gia or 0)
    item = usage.item
    if item is not None and item.source_type == 'gift':
        return 'gift', Decimal(item.regular_price_snapshot or 0)
    return 'package', Decimal(item.unit_value_snapshot if item is not None else service.gia or 0)


def record_for_appointment(appointment):
    """Ghi hoa hồng cho lịch vừa hoàn thành. Trả về danh sách bản ghi đang hiệu lực của lịch."""
    if appointment.manv is None:
        return []
    usages = {u.madv: u for u in LieuTrinhUsage.query.filter(
        LieuTrinhUsage.malh == appointment.malh, LieuTrinhUsage.state != 'released').all()}
    existing = {e.madv: e for e in CommissionEntry.query.filter_by(malh=appointment.malh).all()}
    now = local_now()
    entries = []
    for detail in appointment.chitiet:
        service = detail.dichvu or db.session.get(DichVu, detail.madv)
        if service is None:
            continue
        entry = existing.get(service.madv)
        if entry is not None:
            if entry.status == 'voided':
                # Mở lại rồi hoàn thành lại: khôi phục snapshot cũ, không tính lại theo mức mới.
                entry.status, entry.voided_at = 'active', None
            entries.append(entry)
            continue
        source, base = _source_for(usages.get(service.madv), service)
        percent = service.commission_percent
        fixed = service.commission_fixed
        entry = CommissionEntry(
            malh=appointment.malh, madv=service.madv, manv=appointment.manv,
            service_name=service.tendv[:100], source_type=source,
            base_amount=_vnd(base), rate_percent=percent, fixed_amount=fixed,
            amount=compute_amount(base, percent, fixed), status='active', earned_at=now)
        db.session.add(entry)
        entries.append(entry)
    db.session.flush()
    return entries


def void_for_appointment(malh):
    """Lịch rời trạng thái hoàn thành: hủy hiệu lực hoa hồng (giữ bản ghi để đối soát)."""
    now = local_now()
    CommissionEntry.query.filter_by(malh=malh, status='active').update(
        {CommissionEntry.status: 'voided', CommissionEntry.voided_at: now}, synchronize_session=False)


def _month_bounds(thang, nam):
    start = datetime(int(nam), int(thang), 1)
    end = datetime(int(nam) + (int(thang) == 12), int(thang) % 12 + 1, 1)
    return start, end


def monthly_total(manv, thang, nam):
    start, end = _month_bounds(thang, nam)
    total = db.session.query(func.coalesce(func.sum(CommissionEntry.amount), 0)).filter(
        CommissionEntry.manv == manv, CommissionEntry.status == 'active',
        CommissionEntry.earned_at >= start, CommissionEntry.earned_at < end).scalar()
    return _vnd(total)


def daily_totals(day):
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    rows = db.session.query(CommissionEntry.manv, func.sum(CommissionEntry.amount)).filter(
        CommissionEntry.status == 'active', CommissionEntry.earned_at >= start,
        CommissionEntry.earned_at < end).group_by(CommissionEntry.manv).all()
    return {manv: _vnd(total) for manv, total in rows}


def entries_for_month(manv, thang, nam):
    start, end = _month_bounds(thang, nam)
    return CommissionEntry.query.filter(
        CommissionEntry.manv == manv, CommissionEntry.status == 'active',
        CommissionEntry.earned_at >= start, CommissionEntry.earned_at < end,
    ).order_by(CommissionEntry.earned_at.asc(), CommissionEntry.id.asc()).all()


SOURCE_LABELS = {'regular': 'Trả lẻ', 'package': 'Buổi gói', 'gift': 'Buổi quà tặng'}


def serialize(entry):
    return dict(id=entry.id, malh=entry.malh, madv=entry.madv, manv=entry.manv,
                service_name=entry.service_name, source_type=entry.source_type,
                source_label=SOURCE_LABELS.get(entry.source_type, entry.source_type),
                base_amount=str(entry.base_amount),
                rate_percent=str(entry.rate_percent) if entry.rate_percent is not None else None,
                fixed_amount=str(entry.fixed_amount) if entry.fixed_amount is not None else None,
                amount=str(entry.amount), status=entry.status,
                earned_at=entry.earned_at.isoformat())


def parse_policy(percent_raw, fixed_raw):
    """Chuẩn hóa chính sách từ form dịch vụ. Chuỗi rỗng = không áp dụng."""
    def parse(raw, limit, label):
        if raw is None or str(raw).strip() == '':
            return None
        try:
            value = Decimal(str(raw).strip())
        except Exception:
            raise ValueError(f'{label} không hợp lệ')
        if not value.is_finite() or value < 0 or value > limit:
            raise ValueError(f'{label} phải từ 0 đến {limit:,}'.replace(',', '.'))
        return value
    percent = parse(percent_raw, Decimal('100'), 'Phần trăm hoa hồng')
    fixed = parse(fixed_raw, Decimal('100000000'), 'Hoa hồng cố định')
    if fixed is not None:
        fixed = _vnd(fixed)
    return percent, fixed

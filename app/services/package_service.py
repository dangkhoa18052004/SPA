"""Package purchases and treatment entitlement ledger. Caller owns the transaction."""
import calendar
from datetime import datetime, timedelta, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import base64

from sqlalchemy import func

from ..extensions import db
from ..models import (GoiDichVu, GoiDichVuItem, GoiDichVuPurchase, TheLieuTrinh,
                      TheLieuTrinhItem, LieuTrinhUsage, DichVu)
from .appointment_service import AppointmentValidationError
from . import loyalty_service as loyalty


def local_now():
    # Existing appointment datetimes are naive Asia/Saigon wall time.
    return datetime.utcnow() + timedelta(hours=7)


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999'):
            raise ValueError()
        if amount != amount.quantize(Decimal('1')):
            raise ValueError()
        return amount.quantize(Decimal('.01'))
    except (ValueError, TypeError, InvalidOperation):
        raise AppointmentValidationError('Giá phải là số tiền VND nguyên dương hợp lệ')


def positive_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 10000:
        raise AppointmentValidationError('Số buổi/thời hạn phải là số nguyên dương')
    return value


def save_package(data, package=None):
    name = str(data.get('tengoi', '')).strip()
    if not name or len(name) > 200:
        raise AppointmentValidationError('Vui lòng nhập tên gói (tối đa 200 ký tự)')
    amount = money(data.get('giagoi'))
    months = data.get('validity_months')
    if months is not None:
        months = positive_int(months)
    if months is not None and months > 120:
        raise AppointmentValidationError('Thời hạn tối đa 120 tháng')
    rows = data.get('items')
    if not isinstance(rows, list) or not rows:
        raise AppointmentValidationError('Gói phải có ít nhất một dịch vụ')
    items, seen, retail = [], set(), Decimal(0)
    for row in rows:
        if not isinstance(row, dict):
            raise AppointmentValidationError('Dịch vụ trong gói không hợp lệ')
        service_id = positive_int(row.get('madv'))
        sessions = positive_int(row.get('total_sessions'))
        service = db.session.get(DichVu, service_id)
        if not service or not service.active or service_id in seen:
            raise AppointmentValidationError('Dịch vụ không tồn tại, ngừng bán hoặc bị lặp')
        price = Decimal(service.gia)
        if price <= 0:
            raise AppointmentValidationError('Giá lẻ dịch vụ phải lớn hơn 0')
        seen.add(service_id)
        retail += price * sessions
        items.append((service, sessions, price))
    active = data.get('active', True)
    if not isinstance(active, bool):
        raise AppointmentValidationError('Active phải là boolean')
    # Dan do BỔ SUNG danh rieng cho lieu trinh/goi (optional, max 10000 ky tu)
    post_care = data.get('post_care_instructions')
    if post_care is not None:
        post_care = str(post_care).strip()
        if len(post_care) > 10000:
            raise AppointmentValidationError('Dan do lieu trinh toi da 10.000 ky tu')
        post_care = post_care or None
    package = package or GoiDichVu()
    package.tengoi, package.mota = name, str(data.get('mota') or '')
    package.giagoi, package.validity_months, package.active = amount, months, active
    if post_care is not None:
        package.post_care_instructions = post_care
    # Purchase snapshots make editing a sold package safe; records never depend on these rows.
    if package.magoi:
        package.items.clear()
        db.session.flush()
    for service, sessions, price in items:
        unit = (amount * price / retail).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        package.items.append(GoiDichVuItem(madv=service.madv, total_sessions=sessions,
            regular_unit_price_snapshot=price, package_unit_value=unit))
    db.session.add(package)
    db.session.flush()
    return package


def package_image(package):
    image = package.anhgoi or next((i.service.anhdichvu for i in sorted(package.items, key=lambda i: i.id or 0)[:1]), None)
    return 'data:image/jpeg;base64,' + base64.b64encode(image).decode('ascii') if image else '/static/images/default-package.svg'


def serialize_package(package):
    retail = sum(i.regular_unit_price_snapshot * i.total_sessions for i in package.items)
    return dict(magoi=package.magoi, tengoi=package.tengoi, mota=package.mota,
        giagoi=str(package.giagoi), validity_months=package.validity_months, active=package.active,
        # post_care_instructions: lay tu GoiDichVu hien tai (khong phai snapshot) de dam bao
        # huong dan cham soc luon la ban moi nhat, an toan nhat.
        post_care_instructions=package.post_care_instructions or '',
        regular_total=str(retail), savings=str(retail-package.giagoi), image_url=package_image(package),
        items=[dict(madv=i.madv, tendv=i.service.tendv, total_sessions=i.total_sessions,
            regular_unit_price_snapshot=str(i.regular_unit_price_snapshot),
            package_unit_value=str(i.package_unit_value)) for i in package.items])


def create_purchase(package_id, customer_id, method):
    package = GoiDichVu.query.filter_by(magoi=package_id, active=True).with_for_update().first()
    if not package:
        raise AppointmentValidationError('Gói không tồn tại hoặc đã ngừng bán')
    if method not in ('vietqr', 'cash'):
        raise AppointmentValidationError('Chỉ hỗ trợ VietQR hoặc thanh toán tại quầy')
    snapshot = serialize_package(package)
    if not snapshot['items'] or any(not i.service.active for i in package.items):
        raise AppointmentValidationError('Gói chứa dịch vụ đã ngừng cung cấp')
    purchase = GoiDichVuPurchase(makh=customer_id, magoi=package_id, amount=package.giagoi,
        payment_method=method, status='pending', snapshot_json=snapshot, created_at=local_now())
    db.session.add(purchase)
    db.session.flush()
    return purchase


def add_months(dt, months):
    year, month = divmod(dt.year * 12 + dt.month - 1 + months, 12)
    return dt.replace(year=year, month=month + 1, day=min(dt.day, calendar.monthrange(year, month + 1)[1]))


def activate_package_purchase(purchase):
    if purchase.status != 'paid':
        raise AppointmentValidationError('Chỉ kích hoạt liệu trình sau khi xác nhận thanh toán')
    existing = TheLieuTrinh.query.filter_by(purchase_id=purchase.id).first()
    if existing:
        return existing
    now = purchase.paid_at or local_now()
    record = TheLieuTrinh(makh=purchase.makh, magoi=purchase.magoi, purchase_id=purchase.id,
        purchased_at=purchase.created_at, activated_at=now,
        expires_at=add_months(now, purchase.snapshot_json['validity_months']) if purchase.snapshot_json['validity_months'] is not None else None, status='active')
    for item in purchase.snapshot_json['items']:
        record.items.append(TheLieuTrinhItem(madv=item['madv'], total_sessions=item['total_sessions'],
            unit_value_snapshot=Decimal(item['package_unit_value']),
            regular_price_snapshot=Decimal(item['regular_unit_price_snapshot'])))
    db.session.add(record)
    db.session.flush()
    return record


def confirm_purchase(purchase_id, amount, external_id=None, method=None, staff_id=None, cash_received=None):
    # The UPDATE obtains a write/row lock before reading status, also on SQLite.
    updated = GoiDichVuPurchase.query.filter_by(id=purchase_id).update(
        {GoiDichVuPurchase.id: GoiDichVuPurchase.id}, synchronize_session=False)
    if not updated:
        raise AppointmentValidationError('Không tìm thấy giao dịch mua gói')
    purchase = GoiDichVuPurchase.query.filter_by(id=purchase_id).populate_existing().one()
    if purchase.status == 'paid':
        return purchase, activate_package_purchase(purchase), False
    if purchase.status != 'pending':
        raise AppointmentValidationError('Giao dịch đã bị hủy hoặc thất bại')
    if loyalty.money(amount) != loyalty.payable(purchase):
        raise AppointmentValidationError('Số tiền thanh toán không khớp giá gói')
    if method and method != 'points' and purchase.payment_method != method:
        raise AppointmentValidationError('Phương thức thanh toán không khớp giao dịch')
    if method == 'points' and (loyalty.payable(purchase) != 0 or not (purchase.loyalty_discount or purchase.reward_discount)):
        raise AppointmentValidationError('Thanh toán bằng điểm yêu cầu số tiền còn lại bằng 0')
    if method == 'points':
        purchase.payment_method = 'points'
    elif loyalty.payable(purchase) == 0:
        raise AppointmentValidationError('Vui lòng chọn Thanh toán bằng điểm')
    if cash_received is not None:
        received = money(cash_received)
        if received < loyalty.payable(purchase):
            raise AppointmentValidationError('Số tiền khách đưa chưa đủ')
        purchase.cash_received = received
    purchase.confirmed_by_staff = staff_id
    purchase.status, purchase.paid_at = 'paid', local_now()
    purchase.external_transaction_id = external_id
    loyalty.finalize_payment(purchase)
    return purchase, activate_package_purchase(purchase), True


def lock_treatment(record_id):
    count = TheLieuTrinh.query.filter_by(mathe=record_id).update(
        {TheLieuTrinh.version: TheLieuTrinh.version + 1}, synchronize_session=False)
    if not count:
        raise AppointmentValidationError('Không tìm thấy liệu trình')
    return TheLieuTrinh.query.filter_by(mathe=record_id).populate_existing().one()


def item_counts(item):
    rows = db.session.query(LieuTrinhUsage.state, func.count(LieuTrinhUsage.id)).filter_by(
        the_item_id=item.id).group_by(LieuTrinhUsage.state).all()
    counts = dict(rows)
    consumed, reserved = counts.get('consumed', 0), counts.get('reserved', 0)
    return dict(consumed=consumed, reserved=reserved,
                available_sessions=item.total_sessions-consumed-reserved)


def effective_item_expiry(item, treatment):
    return item.expires_at if item.source_type == 'gift' or item.expires_at else treatment.expires_at


def is_treatment_item_usable(item, treatment, appointment_date=None):
    """Shared calendar-day validity for listing, reserve and reschedule."""
    day = appointment_date or local_now().date()
    if isinstance(day, datetime):
        day = day.date()
    if (item.source_type not in ('package', 'gift') or item.mathe != treatment.mathe
            or treatment.status == 'cancelled' or not item.service.active):
        return False
    if item.valid_from and day < item.valid_from.date():
        return False
    expiry = effective_item_expiry(item, treatment)
    if expiry and day > expiry.date():
        return False
    if item.source_type != 'gift' and treatment.status == 'expired' and expiry is None:
        return False
    return True


def gift_service(record_id, data, staff):
    if staff.role not in ('admin', 'manager', 'staff') or not staff.trangthai:
        raise AppointmentValidationError('Bạn không có quyền tặng dịch vụ')
    record = lock_treatment(record_id)
    if record.status == 'cancelled':
        raise AppointmentValidationError('Liệu trình đã bị hủy')
    if data.get('makh', record.makh) != record.makh:
        raise AppointmentValidationError('Khách hàng không khớp liệu trình')
    service = db.session.get(DichVu, positive_int(data.get('madv')))
    if not service or not service.active:
        raise AppointmentValidationError('Dịch vụ không tồn tại hoặc đã ngừng hoạt động')
    quantity = positive_int(data.get('total_sessions', data.get('quantity')))
    now, expiry = local_now(), None
    if data.get('expires_at') is not None and (not isinstance(data['expires_at'], str) or not data['expires_at'].strip()):
        raise AppointmentValidationError('Ngày hết hạn không hợp lệ')
    if data.get('expires_at') and data.get('validity_days') is not None:
        raise AppointmentValidationError('Chỉ chọn số ngày hoặc ngày hết hạn')
    if data.get('validity_days') is not None:
        expiry = now + timedelta(days=positive_int(data['validity_days']))
    elif data.get('expires_at'):
        try:
            raw = str(data['expires_at'])
            expiry = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if expiry.tzinfo:
                expiry = expiry.astimezone(timezone(timedelta(hours=7))).replace(tzinfo=None)
            if len(raw) == 10:
                expiry = datetime.combine(expiry.date(), time.max)
        except (ValueError, TypeError):
            raise AppointmentValidationError('Ngày hết hạn không hợp lệ')
    if expiry and expiry.date() < now.date():
        raise AppointmentValidationError('Ngày hết hạn phải từ hôm nay trở đi')
    note = data.get('gift_note') or ''
    if not isinstance(note, str) or len(note) > 2000:
        raise AppointmentValidationError('Ghi chú tối đa 2000 ký tự')
    item = TheLieuTrinhItem(mathe=record.mathe, madv=service.madv, total_sessions=quantity,
        source_type='gift', valid_from=now, expires_at=expiry, gifted_by_staff=staff.manv,
        gift_note=note.strip(), created_at=now, unit_value_snapshot=0, regular_price_snapshot=service.gia)
    db.session.add(item)
    db.session.flush()
    return record, item


def reserve_usages(appointment, usages, require_item_id=False):
    if not isinstance(usages, list):
        raise AppointmentValidationError('package_usages phải là danh sách')
    seen = set()
    for row in sorted(usages, key=lambda r: str(r.get('mathe', '')) if isinstance(r, dict) else ''):
        if not isinstance(row, dict) or row.get('quantity') != 1 or isinstance(row.get('quantity'), bool):
            raise AppointmentValidationError('Mỗi dịch vụ trong một lịch hẹn dùng đúng 1 buổi')
        if require_item_id and row.get('the_item_id') is None:
            raise AppointmentValidationError('Vui lòng chọn chính xác lượt dịch vụ bằng the_item_id')
        record_id, service_id = positive_int(row.get('mathe')), positive_int(row.get('madv'))
        if service_id in seen or service_id not in {d.madv for d in appointment.chitiet}:
            raise AppointmentValidationError('Dịch vụ liệu trình không thuộc lịch hẹn hoặc bị lặp')
        seen.add(service_id)
        record = lock_treatment(record_id)
        if record.makh != appointment.makh:
            raise AppointmentValidationError('Không được dùng liệu trình của khách hàng khác')
        item_query = TheLieuTrinhItem.query.filter_by(mathe=record_id, madv=service_id)
        if row.get('the_item_id') is not None:
            item = item_query.filter_by(id=positive_int(row['the_item_id'])).first()
        else:
            # Legacy payload: prefer a usable original package entitlement.
            candidates = item_query.order_by(TheLieuTrinhItem.id).all()
            item = next((i for i in candidates if i.source_type == 'package'
                and is_treatment_item_usable(i, record) and is_treatment_item_usable(i, record, appointment.ngaygio)
                and item_counts(i)['available_sessions'] > 0), None)
            if item is None:
                candidates = [i for i in candidates if is_treatment_item_usable(i, record)
                    and is_treatment_item_usable(i, record, appointment.ngaygio) and item_counts(i)['available_sessions'] > 0]
                if len(candidates) > 1:
                    raise AppointmentValidationError('Vui lòng chọn chính xác lượt dịch vụ bằng the_item_id')
                item = candidates[0] if candidates else None
        if not item or item_counts(item)['available_sessions'] < 1:
            raise AppointmentValidationError('Dịch vụ không thuộc liệu trình hoặc đã hết buổi khả dụng')
        if not is_treatment_item_usable(item, record) or not is_treatment_item_usable(item, record, appointment.ngaygio):
            raise AppointmentValidationError('Dịch vụ liệu trình không hoạt động hoặc ngày hẹn ngoài hạn sử dụng')
        db.session.add(LieuTrinhUsage(mathe=record_id, the_item_id=item.id,
            malh=appointment.malh, madv=service_id, state='reserved', reserved_at=local_now()))
        db.session.flush()


def transition_usages(appointment_id, state):
    usages = LieuTrinhUsage.query.filter_by(malh=appointment_id).all()
    for record_id in sorted({u.mathe for u in usages}):
        record = lock_treatment(record_id)
        for usage in usages:
            if usage.mathe == record_id and usage.state == 'reserved':
                usage.state = state
                if state == 'consumed':
                    usage.consumed_at = local_now()
                elif state == 'released':
                    usage.released_at = local_now()
        db.session.flush()
        if record.status not in ('cancelled', 'expired'):
            record.status = 'used_up' if all(item_counts(i)['consumed'] == i.total_sessions for i in record.items) else 'active'


def validate_reschedule(appointment, new_dt):
    for usage in LieuTrinhUsage.query.filter_by(malh=appointment.malh, state='reserved').all():
        record = db.session.get(TheLieuTrinh, usage.mathe)
        if not is_treatment_item_usable(usage.item, record, new_dt):
            raise AppointmentValidationError('Ngày hẹn ngoài hạn sử dụng dịch vụ liệu trình')


def serialize_treatment(record, history=False):
    result = dict(mathe=record.mathe, makh=record.makh, magoi=record.magoi,
        tengoi=record.purchase.snapshot_json['tengoi'], status=record.status,
        image_url=record.purchase.snapshot_json.get('image_url') or package_image(record.purchase.package),
        purchased_at=record.purchased_at.isoformat(), activated_at=record.activated_at.isoformat(),
        expires_at=record.expires_at.isoformat() if record.expires_at is not None else None, items=[dict(id=i.id, madv=i.madv,
        tendv=i.service.tendv, total_sessions=i.total_sessions,
        unit_value_snapshot=str(i.unit_value_snapshot), regular_price_snapshot=str(i.regular_price_snapshot),
        source_type=i.source_type, valid_from=i.valid_from.isoformat() if i.valid_from else None,
        expires_at=i.expires_at.isoformat() if i.expires_at else None,
        effective_expires_at=effective_item_expiry(i, record).isoformat() if effective_item_expiry(i, record) else None,
        usable=is_treatment_item_usable(i, record), gifted_by_staff=i.gifted_by_staff,
        gifted_by_name=i.gift_staff.hoten if i.gift_staff else None, gift_note=i.gift_note or '',
        created_at=i.created_at.isoformat() if i.created_at else None,
        **item_counts(i)) for i in record.items])
    if record.status != 'cancelled':
        valid_items = [i for i in result['items'] if i['usable']]
        result['status'] = ('active' if any(i['consumed'] < i['total_sessions'] for i in valid_items)
                            else 'used_up' if valid_items else 'expired')
    if history:
        result['history'] = [dict(id=u.id, malh=u.malh, madv=u.madv, the_item_id=u.the_item_id,
            source_type=u.item.source_type, tendv=u.item.service.tendv, state=u.state,
            reserved_at=u.reserved_at.isoformat(), consumed_at=u.consumed_at.isoformat() if u.consumed_at else None,
            released_at=u.released_at.isoformat() if u.released_at else None)
            for u in LieuTrinhUsage.query.filter_by(mathe=record.mathe).order_by(LieuTrinhUsage.id.desc()).all()]
    return result


def paid_package_revenue(start=None, end=None):
    query = db.session.query(func.coalesce(func.sum(GoiDichVuPurchase.payable_amount), 0)).filter(
        GoiDichVuPurchase.status == 'paid')
    if start:
        query = query.filter(GoiDichVuPurchase.paid_at >= start)
    if end:
        query = query.filter(GoiDichVuPurchase.paid_at < end)
    return query.scalar()

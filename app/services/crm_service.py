"""Explicit customer preferences and operational customer groups from canonical bookings."""
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import case, func, or_
from ..extensions import db
from ..models import KhachHang, LichHen, NotificationJob, CustomerPreference, CustomerPreferenceAudit
from .package_service import local_now

FIELDS = ('reminders', 'post_care', 'review_requests', 'personalization')
DEFAULTS = dict(reminders=False, post_care=False, review_requests=False, personalization=True)
OPTIONAL_JOBS = {'appointment_reminder_24h': 'reminders', 'appointment_reminder_2h': 'reminders',
                 'post_care': 'post_care', 'review_request': 'review_requests'}
SEGMENTS = {'new': 'Khách mới', 'returning': 'Đang quay lại', 'due': '31–60 ngày chưa quay lại',
            'inactive': 'Trên 60 ngày chưa quay lại', 'never': 'Chưa sử dụng dịch vụ'}


class CRMError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def preferences(customer_id):
    row = db.session.get(CustomerPreference, customer_id, populate_existing=True)
    return dict(**({k: getattr(row, k) for k in FIELDS} if row else DEFAULTS),
                version=row.version if row else 0, updated_at=row.updated_at.isoformat() + 'Z' if row else None)


def personalization_allowed(customer_id):
    if not current_app.config.get('PERSONALIZATION_ENABLED', True):
        return False
    return tracking_allowed(customer_id)


def tracking_allowed(customer_id):
    return not customer_id or not (current_app.config.get('CRM_ENABLED') or current_app.config.get('CUSTOMER_CONSENT_ENABLED')) or preferences(customer_id)['personalization']


def notification_allowed(customer_id, kind):
    if not (current_app.config.get('CRM_ENABLED') or current_app.config.get('CUSTOMER_CONSENT_ENABLED')) or kind not in OPTIONAL_JOBS:
        return True
    customer = db.session.get(KhachHang, customer_id, populate_existing=True)
    row = db.session.get(CustomerPreference, customer_id, populate_existing=True)
    return bool(customer and customer.trangthai == 'active' and row and getattr(row, OPTIONAL_JOBS[kind]))


def save_preferences(customer, data):
    if not isinstance(data, dict) or set(data) != set(FIELDS) | {'version'} or any(type(data[k]) is not bool for k in FIELDS) or type(data['version']) is not int or data['version'] < 0:
        raise CRMError('Cần đủ lựa chọn thông báo/cá nhân hóa và phiên bản hợp lệ')
    # Serialize the first write too, when no preference record exists yet.
    KhachHang.query.filter_by(makh=customer.makh).update({KhachHang.makh: KhachHang.makh}, synchronize_session=False)
    row = db.session.get(CustomerPreference, customer.makh, populate_existing=True)
    if data['version'] != (row.version if row else 0):
        raise CRMError('Lựa chọn vừa được thay đổi ở nơi khác. Tải lại trước khi lưu.', 409)
    before = preferences(customer.makh)
    if all(before[k] == data[k] for k in FIELDS) and row:
        return before
    now = datetime.utcnow()
    if not row:
        row = CustomerPreference(makh=customer.makh, version=0)
        db.session.add(row)
    row.version += 1
    row.updated_at = now
    for key in FIELDS:
        setattr(row, key, data[key])
    if before['personalization'] and not data['personalization']:
        from ..models import CustomerBehavior, RecommendationImpression
        CustomerBehavior.query.filter_by(makh=customer.makh, source='frontend').delete(synchronize_session=False)
        RecommendationImpression.query.filter_by(makh=customer.makh).delete(synchronize_session=False)
    db.session.add(CustomerPreferenceAudit(makh=customer.makh, version=row.version,
        settings={k: data[k] for k in FIELDS}, created_at=now))
    for kind, field in OPTIONAL_JOBS.items():
        if not data[field]:
            NotificationJob.query.filter(NotificationJob.makh == customer.makh, NotificationJob.type == kind,
                NotificationJob.status.in_(('pending', 'processing'))).update(
                    dict(status='cancelled', last_error='Khách không đăng ký loại thông báo này'), synchronize_session=False)
    db.session.flush()
    if data['reminders'] and not before['reminders']:
        from .notification_service import sync_appointment_jobs
        for apt in LichHen.query.filter(LichHen.makh == customer.makh, LichHen.trangthai == 'confirmed',
                                       LichHen.ngaygio > local_now()).all():
            sync_appointment_jobs(apt, now=now)
    return preferences(customer.makh)


def customer_rows(segment='', search='', page=1, per_page=20):
    if segment and segment not in SEGMENTS:
        raise CRMError('Nhóm khách không hợp lệ')
    now = local_now()
    utc = datetime.utcnow()
    visits = db.session.query(LichHen.makh.label('makh'),
        func.max(case((LichHen.trangthai == 'completed', LichHen.ngaygio))).label('last_visit'),
        func.sum(case((LichHen.trangthai == 'completed', 1), else_=0)).label('visits'),
        func.min(case(((LichHen.trangthai.in_(('pending', 'confirmed')) & (LichHen.ngaygio >= now)), LichHen.ngaygio))).label('next_visit'))\
        .group_by(LichHen.makh).subquery()
    group = case(
        (visits.c.last_visit >= now - timedelta(days=30), 'returning'),
        (visits.c.last_visit >= now - timedelta(days=60), 'due'),
        (visits.c.last_visit.isnot(None), 'inactive'),
        (KhachHang.ngaytao >= utc - timedelta(days=30), 'new'), else_='never')
    query = db.session.query(KhachHang, visits.c.last_visit, visits.c.visits, visits.c.next_visit, group.label('segment'))\
        .outerjoin(visits, visits.c.makh == KhachHang.makh).filter(KhachHang.trangthai == 'active')
    if search:
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(or_(*[column.ilike('%' + escaped + '%', escape='\\') for column in (KhachHang.hoten, KhachHang.sdt, KhachHang.email)]))
    counts = {key: 0 for key in SEGMENTS}
    for key, count in query.with_entities(group, func.count()).group_by(group).all():
        counts[key] = count
    if segment:
        query = query.filter(group == segment)
    total = query.count()
    items = []
    for customer, last, count, upcoming, key in query.order_by(KhachHang.makh.desc()).offset((page - 1) * per_page).limit(per_page):
        items.append(dict(id=customer.makh, name=customer.hoten, phone=customer.sdt, email=customer.email,
            last_visit=last.isoformat() + '+07:00' if last else None, visits=count or 0,
            next_visit=upcoming.isoformat() + '+07:00' if upcoming else None,
            segment=key, segment_label=SEGMENTS[key]))
    return dict(items=items, total=total, page=page, per_page=per_page, segments=counts, segment_labels=SEGMENTS)

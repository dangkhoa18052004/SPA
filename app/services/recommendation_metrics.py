"""Observed top-six card impressions and bounded, descriptive booking attribution."""
from datetime import datetime, timedelta
from functools import wraps
import math
from threading import Lock
from time import perf_counter
from uuid import uuid4
from flask import current_app, make_response
from sqlalchemy import and_, or_, exists, func
from ..extensions import db
from ..models import (KhachHang, DichVu, GoiDichVu, CustomerBehavior,
                      RecommendationImpression as Impression, RecommendationTiming)
from .crm_service import CRMError, personalization_allowed, tracking_allowed

PLACEMENTS = {'home', 'catalog', 'related', 'booking'}


def measure(placement):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            started = perf_counter()
            result = fn(*args, **kwargs)
            if not current_app.config.get('RECOMMENDATION_METRICS_ENABLED'):
                return result
            response = make_response(result)
            elapsed = round((perf_counter() - started) * 1000, 3)
            response.headers['Server-Timing'] = f'recommendation;dur={elapsed}'
            if response.status_code == 200:
                state = current_app.extensions.setdefault('recommendation_timing_sample', {'lock': Lock(), 'last': {}})
                with state['lock']:
                    last = state['last'].get(placement)
                    if last is not None and started - last < 10:
                        return response
                    state['last'][placement] = started
                # Telemetry must never make a successfully rendered catalog unavailable.
                try:
                    db.session.add(RecommendationTiming(placement=placement, duration_ms=elapsed))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    current_app.logger.warning('Recommendation timing unavailable')
            return response
        return wrapped
    return decorate


def record_impressions(customer, data, now=None):
    now = now or datetime.utcnow()
    if not isinstance(data, dict) or set(data) != {'placement', 'items'} or not isinstance(data['placement'], str) or data['placement'] not in PLACEMENTS:
        raise CRMError('Vị trí hiển thị không hợp lệ')
    items = data['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 6:
        raise CRMError('Mỗi lượt chỉ ghi tối đa 6 thẻ đã hiển thị')
    seen, positions = set(), set()
    validated = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'type', 'id', 'position'} or item['type'] not in ('service', 'package')\
                or type(item['id']) is not int or not 0 < item['id'] <= 2147483647 or type(item['position']) is not int or not 1 <= item['position'] <= 6:
            raise CRMError('Thẻ hiển thị không hợp lệ')
        key = item['type'], item['id']
        if key in seen or item['position'] in positions:
            raise CRMError('Thẻ hoặc thứ tự hiển thị bị trùng')
        seen.add(key); positions.add(item['position'])
        target = db.session.get(DichVu if item['type'] == 'service' else GoiDichVu, item['id'])
        if not target or not target.active or (item['type'] == 'package' and not target.customer_sale_enabled):
            raise CRMError('Dịch vụ/gói đã ngừng hoạt động', 404)
        validated.append(item)
    KhachHang.query.filter_by(makh=customer.makh).update({KhachHang.makh: KhachHang.makh}, synchronize_session=False)
    if not tracking_allowed(customer.makh):
        return []
    if Impression.query.filter(Impression.makh == customer.makh, Impression.created_at >= now - timedelta(minutes=1)).count() >= 120:
        raise CRMError('Quá nhiều lượt hiển thị, vui lòng thử lại sau', 429)
    bucket = int((now - datetime(1970, 1, 1)).total_seconds()) // 600
    response = []
    for item in validated:
        key = f'{customer.makh}:{data["placement"]}:{item["type"]}:{item["id"]}:{bucket}'
        row = Impression.query.filter_by(dedupe_key=key).first()
        if not row:
            row = Impression(id=str(uuid4()), makh=customer.makh, placement=data['placement'],
                **{'madv' if item['type'] == 'service' else 'magoi': item['id']},
                position=item['position'], strategy='enabled' if personalization_allowed(customer.makh) else 'popular', dedupe_key=key, created_at=now)
            db.session.add(row)
        response.append(dict(id=row.id, type=item['type'], target_id=item['id']))
    return response


def click_impression(customer, impression_id, now=None):
    KhachHang.query.filter_by(makh=customer.makh).update({KhachHang.makh: KhachHang.makh}, synchronize_session=False)
    row = Impression.query.filter_by(id=impression_id, makh=customer.makh).first()
    if not row:
        raise CRMError('Không tìm thấy lượt hiển thị', 404)
    if tracking_allowed(customer.makh):
        row.clicked_at = row.clicked_at or now or datetime.utcnow()
    return row.clicked_at is not None


def baseline(start, end, now=None):
    now = now or datetime.utcnow()
    query = Impression.query.filter(Impression.created_at >= start, Impression.created_at < end)
    count = query.count()
    clicked = query.filter(Impression.clicked_at.isnot(None)).count()
    deadline = func.datetime(Impression.clicked_at, '+7 days') if db.engine.dialect.name == 'sqlite' else Impression.clicked_at + timedelta(days=7)
    conversion = exists().where(and_(CustomerBehavior.makh == Impression.makh,
        CustomerBehavior.source == 'backend', CustomerBehavior.created_at >= Impression.clicked_at,
        CustomerBehavior.created_at <= deadline, CustomerBehavior.created_at <= now,
        or_(and_(CustomerBehavior.action == 'book_service', CustomerBehavior.madv == Impression.madv),
            and_(CustomerBehavior.action == 'purchase_package', CustomerBehavior.magoi == Impression.magoi))))
    converted = query.filter(Impression.clicked_at.isnot(None), conversion).count()
    active_count = DichVu.query.filter_by(active=True).count()
    covered = query.join(DichVu, DichVu.madv == Impression.madv).filter(DichVu.active.is_(True)).with_entities(Impression.madv).distinct().count()
    timings = RecommendationTiming.query.filter(RecommendationTiming.created_at >= start, RecommendationTiming.created_at < end)
    samples = sorted(row[0] for row in timings.with_entities(RecommendationTiming.duration_ms).order_by(RecommendationTiming.id.desc()).limit(5000))
    return dict(impressions=count, clicks=clicked, ctr=round(clicked / count * 100, 2) if count else None,
        conversions=converted, conversion_rate=round(converted / clicked * 100, 2) if clicked else None,
        covered_services=covered, active_services=active_count, coverage=round(covered / active_count * 100, 2) if active_count else None,
        latency_samples=len(samples), latency_total=timings.count(), p95_ms=round(samples[math.ceil(.95 * len(samples)) - 1], 2) if samples else None,
        attribution_days=7, top_k=6, population='authenticated_customers',
        by_placement={key: dict(impressions=query.filter(Impression.placement == key).count(),
            clicks=query.filter(Impression.placement == key, Impression.clicked_at.isnot(None)).count()) for key in sorted(PLACEMENTS)})

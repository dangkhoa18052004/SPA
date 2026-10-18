"""Deterministic hybrid ranking. Business tables are canonical; audit events never add twice."""
import base64
from collections import defaultdict
from datetime import datetime, timedelta
from flask import current_app

from sqlalchemy import func, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload, defer

from ..extensions import db
from ..models import (CustomerBehavior, DichVu, KhachHang, LichHen, ChiTietLichHen,
    HoaDon, ChiTietHoaDon, DanhGia, DanhGiaDichVu, GoiDichVu, GoiDichVuItem,
    GoiDichVuPurchase, TheLieuTrinh)

ACTION_WEIGHTS = dict(view_service=1, click_service=2, select_service=3, book_service=5,
    complete_service=8, view_package=1, purchase_package=10, favorite=4)
RATING_WEIGHTS = {5: 5, 4: 3, 3: 0, 2: -3, 1: -5}
SCORE_WEIGHTS = dict(category=.40, booking=.30, behavior=.15, rating=.15)
CLIENT_ACTIONS = {'view_service', 'click_service', 'select_service', 'view_package', 'favorite'}
HALF_LIFE_DAYS = 30
HISTORY_DAYS = 730
DEDUPE_SECONDS = 600
DAILY_EVENT_CAP = 3
EVENTS_PER_MINUTE = 60


class RecommendationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def decay(value, now, local=False):
    """UTC for behaviors/reviews; naive Saigon time for appointments/package ledger."""
    if value is None:
        return 0.0
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value))
    if local:
        value -= timedelta(hours=7)
    age = max(0, (now - value).total_seconds() / 86400)
    return 2 ** (-age / HALF_LIFE_DAYS)


def normalize(value):
    # Fixed signed saturation preserves recency even when only one category is present.
    return value / (abs(value) + 5)


def record_business_event(customer_id, action, reference, *, madv=None, magoi=None):
    """Caller owns commit/rollback. Reference is a server-issued appointment/purchase ID."""
    key = f'business:{customer_id}:{action}:{reference}:{madv or magoi}'
    if not CustomerBehavior.query.filter_by(dedupe_key=key).first():
        db.session.add(CustomerBehavior(makh=customer_id, madv=madv, magoi=magoi,
            action=action, source='backend', dedupe_key=key))


def record_client_event(customer_id, data, now=None):
    now = now or datetime.utcnow()
    if not isinstance(data, dict) or set(data) - {'action', 'madv', 'magoi'}:
        raise RecommendationError('Chỉ chấp nhận action và mã dịch vụ/gói')
    action = data.get('action')
    if not isinstance(action, str) or action not in CLIENT_ACTIONS:
        raise RecommendationError('Hành vi không hợp lệ hoặc chỉ được ghi từ backend')
    target = 'magoi' if action == 'view_package' else 'madv'
    target_id = data.get(target)
    if type(target_id) is not int or not 0 < target_id <= 2147483647 or data.get('madv' if target == 'magoi' else 'magoi') is not None:
        raise RecommendationError('Mã dịch vụ/gói không hợp lệ')
    model = GoiDichVu if target == 'magoi' else DichVu
    item = db.session.get(model, target_id)
    if not item or not item.active or (target == 'magoi' and not item.customer_sale_enabled):
        raise RecommendationError('Dịch vụ/gói không tồn tại hoặc đã ngừng bán', 404)
    # Serialize customer writes across workers; SQLite also obtains a write lock.
    KhachHang.query.filter_by(makh=customer_id).update({KhachHang.makh: KhachHang.makh}, synchronize_session=False)
    from .crm_service import personalization_allowed
    if not personalization_allowed(customer_id):
        return False
    bucket = int((now - datetime(1970, 1, 1)).total_seconds()) // DEDUPE_SECONDS
    key = f'client:{customer_id}:{action}:{target_id}:{bucket}'
    if CustomerBehavior.query.filter_by(dedupe_key=key).first():
        return False
    recent = CustomerBehavior.query.filter(CustomerBehavior.makh == customer_id,
        CustomerBehavior.source == 'frontend', CustomerBehavior.created_at >= now - timedelta(minutes=1)).count()
    if recent >= EVENTS_PER_MINUTE:
        raise RecommendationError('Bạn thao tác quá nhanh, vui lòng thử lại sau', 429)
    try:
        with db.session.begin_nested():
            db.session.add(CustomerBehavior(makh=customer_id, action=action,
                **{target: target_id}, created_at=now, source='frontend', dedupe_key=key))
            db.session.flush()
    except IntegrityError:
        return False
    return True


def _review_rows(customer_id=None):
    """Use explicit review links, or appointment services for pre-link legacy reviews."""
    columns = [DanhGia.rating.label('rating'), DanhGia.created_at.label('created_at')]
    linked = db.session.query(DanhGiaDichVu.madv.label('madv'), *columns).join(DanhGia, DanhGia.madg == DanhGiaDichVu.madg)
    legacy = db.session.query(ChiTietLichHen.madv.label('madv'), *columns).join(DanhGia, DanhGia.malh == ChiTietLichHen.malh).filter(
        ~exists().where(DanhGiaDichVu.madg == DanhGia.madg))
    # Legacy rows already join ChiTietLichHen; explicit correlation avoids auto-correlation ambiguity.
    linked = linked.join(LichHen, LichHen.malh == DanhGia.malh).filter(
        LichHen.trangthai == 'completed', LichHen.makh == DanhGia.makh,
        exists().where((ChiTietLichHen.malh == DanhGia.malh) & (ChiTietLichHen.madv == DanhGiaDichVu.madv)))
    legacy = legacy.join(LichHen, LichHen.malh == DanhGia.malh).filter(
        LichHen.trangthai == 'completed', LichHen.makh == DanhGia.makh)
    if customer_id is not None:
        linked = linked.filter(DanhGia.makh == customer_id)
        legacy = legacy.filter(DanhGia.makh == customer_id)
    return linked.union_all(legacy).subquery()


class Ranking:
    """One request computes catalog/profile/popularity once, then ranks both entity types."""
    def __init__(self, customer_id=None, now=None):
        self.now = now or datetime.utcnow()
        from .crm_service import personalization_allowed
        self.customer_id = customer_id if personalization_allowed(customer_id) else None
        self.services = {s.madv: s for s in DichVu.query.options(joinedload(DichVu.category), defer(DichVu.anhdichvu)).all()}
        self.category = defaultdict(float)
        self.booking = defaultdict(float)
        self.behavior = defaultdict(float)
        self.rating = defaultdict(float)
        self.has_signal = False
        self.owned_packages = set()
        self.package_views = defaultdict(float)
        self._popularity()
        if self.customer_id is not None:
            self._profile()
        self.strategy = 'personalized' if self.has_signal else 'popular'
        self.scores = {s.madv: self._score(s) for s in self.services.values() if s.active}

    def _add(self, service_id, value, component):
        service = self.services.get(service_id)
        if not service or abs(value) < .001:
            return
        self.has_signal = True
        component[service_id] += value
        if service.category and service.category.active:
            self.category[service.category.slug] += value

    def _popularity(self):
        local_cutoff = self.now + timedelta(hours=7) - timedelta(days=90)
        rows = db.session.query(ChiTietLichHen.madv, func.count(),
            func.sum(db.case((LichHen.trangthai == 'completed', 1), else_=0)),
            func.sum(db.case(((LichHen.trangthai == 'completed') & (LichHen.ngaygio >= local_cutoff), 1), else_=0)))\
            .join(LichHen).filter(LichHen.trangthai.in_(('pending', 'confirmed', 'in_progress', 'completed')))\
            .group_by(ChiTietLichHen.madv).all()
        counts = {sid: bookings + completed + 2 * recent for sid, bookings, completed, recent in rows}
        reviews = _review_rows()
        ratings = {sid: (float(avg), n) for sid, avg, n in db.session.query(
            reviews.c.madv, func.avg(reviews.c.rating), func.count()).group_by(reviews.c.madv).all()}
        self.popularity = {}
        for sid in self.services:
            avg, n = ratings.get(sid, (3.5, 0))
            bayesian = (avg * n + 3.5 * 5) / (n + 5) / 5
            self.popularity[sid] = .7 * normalize(counts.get(sid, 0)) + .3 * bayesian

    def _profile(self):
        cutoff = self.now - timedelta(days=HISTORY_DAYS)
        local_cutoff = cutoff + timedelta(hours=7)
        # SQL aggregates history by service/status/day rather than loading all appointments.
        rows = db.session.query(ChiTietLichHen.madv, LichHen.trangthai,
            func.date(LichHen.ngaygio), func.count()).join(LichHen).filter(
            LichHen.makh == self.customer_id, LichHen.ngaygio >= local_cutoff,
            LichHen.trangthai.in_(('pending', 'confirmed', 'in_progress', 'completed')))\
            .group_by(ChiTietLichHen.madv, LichHen.trangthai, func.date(LichHen.ngaygio)).all()
        for sid, status, day, n in rows:
            action = 'complete_service' if status == 'completed' else 'book_service'
            self._add(sid, ACTION_WEIGHTS[action] * n * decay(day, self.now, local=True), self.booking)
        # Linked invoices are excluded entirely, including prepayment and cancelled appointments.
        for sid, day, n in db.session.query(ChiTietHoaDon.madv, func.date(HoaDon.ngaylap), func.count(func.distinct(HoaDon.mahd)))\
                .join(HoaDon).filter(HoaDon.makh == self.customer_id, HoaDon.malh.is_(None),
                    HoaDon.trangthai == 'Đã thanh toán', HoaDon.ngaylap >= cutoff)\
                .group_by(ChiTietHoaDon.madv, func.date(HoaDon.ngaylap)).all():
            self._add(sid, ACTION_WEIGHTS['complete_service'] * n * decay(day, self.now), self.booking)
        rows = db.session.query(CustomerBehavior.madv, CustomerBehavior.magoi, CustomerBehavior.action,
            func.date(CustomerBehavior.created_at), func.count()).filter(
            CustomerBehavior.makh == self.customer_id, CustomerBehavior.source == 'frontend',
            CustomerBehavior.action.in_(CLIENT_ACTIONS), CustomerBehavior.created_at >= cutoff)\
            .group_by(CustomerBehavior.madv, CustomerBehavior.magoi, CustomerBehavior.action, func.date(CustomerBehavior.created_at)).all()
        viewed_ids = {pid for _, pid, _, _, _ in rows if pid}
        package_items = defaultdict(list)
        if viewed_ids:
            for pid, sid in db.session.query(GoiDichVuItem.magoi, GoiDichVuItem.madv).filter(GoiDichVuItem.magoi.in_(viewed_ids)).all():
                package_items[pid].append(sid)
        for sid, pid, action, day, n in rows:
            value = ACTION_WEIGHTS[action] * min(n, DAILY_EVENT_CAP) * decay(day, self.now)
            if sid:
                self._add(sid, value, self.behavior)
            else:
                self.package_views[pid] += value
                ids = package_items[pid]
                for service_id in ids:
                    self._add(service_id, value / len(ids), self.behavior)
        reviews = _review_rows(self.customer_id)
        for sid, rating, day, n in db.session.query(reviews.c.madv, reviews.c.rating,
                func.date(reviews.c.created_at), func.count()).filter(reviews.c.created_at >= cutoff)\
                .group_by(reviews.c.madv, reviews.c.rating, func.date(reviews.c.created_at)).all():
            self._add(sid, RATING_WEIGHTS.get(rating, 0) * n * decay(day, self.now), self.rating)
        # Paid snapshots, never the edited catalog, express what the customer actually bought.
        purchases = GoiDichVuPurchase.query.filter(
            GoiDichVuPurchase.makh == self.customer_id, GoiDichVuPurchase.status == 'paid',
            GoiDichVuPurchase.paid_at >= local_cutoff).all()
        for purchase in purchases:
            ids = {item.get('madv') for item in (purchase.snapshot_json or {}).get('items', []) if isinstance(item, dict)}
            ids.discard(None)
            for sid in ids:
                self._add(sid, ACTION_WEIGHTS['purchase_package'] * decay(purchase.paid_at, self.now, local=True) / len(ids), self.booking)
            if purchase.paid_at >= self.now + timedelta(hours=7) - timedelta(days=30):
                self.owned_packages.add(purchase.magoi)
        # Ledger handles legacy paid purchases without snapshots and avoids adding purchases twice.
        records = TheLieuTrinh.query.options(selectinload(TheLieuTrinh.items)).join(
            GoiDichVuPurchase, GoiDichVuPurchase.id == TheLieuTrinh.purchase_id).filter(TheLieuTrinh.makh == self.customer_id,
            GoiDichVuPurchase.status == 'paid', TheLieuTrinh.status != 'cancelled').all()
        snapshotted = {p.id for p in purchases if (p.snapshot_json or {}).get('items')}
        for record in records:
            if record.status == 'active' and (record.expires_at is None or record.expires_at >= self.now + timedelta(hours=7)):
                self.owned_packages.add(record.magoi)
            if record.purchase_id not in snapshotted and record.activated_at >= local_cutoff:
                ids = {item.madv for item in record.items if item.source_type == 'package'}
                for sid in ids:
                    self._add(sid, ACTION_WEIGHTS['purchase_package'] * decay(record.activated_at, self.now, local=True) / len(ids), self.booking)

    def _score(self, service):
        if not self.has_signal:
            return self.popularity[service.madv]
        category = service.category.slug if service.category and service.category.active else None
        components = dict(category=normalize(self.category.get(category, 0)),
            booking=normalize(self.booking[service.madv]), behavior=normalize(self.behavior[service.madv]),
            rating=normalize(self.rating[service.madv]))
        return sum(SCORE_WEIGHTS[key] * value for key, value in components.items())

    def service_reason(self, service):
        if self.strategy == 'popular':
            return 'Được khách hàng lựa chọn và đánh giá tốt'
        if service.category and self.category.get(service.category.slug, 0) > 0:
            return f'Phù hợp với nhóm {service.category.name} bạn quan tâm'
        return 'Dựa trên dịch vụ bạn đã quan tâm hoặc sử dụng'

    def recommend_services(self, limit=6):
        return [dict(madv=sid, tendv=self.services[sid].tendv, score=round(score, 6),
            reason=self.service_reason(self.services[sid])) for sid, score in
            sorted(self.scores.items(), key=lambda item: (-item[1], -self.popularity[item[0]], item[0]))[:limit]]

    def rank_services(self, candidate_services):
        """Rank every unique active candidate; popularity only breaks personal-score ties."""
        candidates = {s.madv: s for s in candidate_services if s.active}
        return sorted(candidates.values(), key=lambda s:
            (-self.scores.get(s.madv, 0), -self.popularity.get(s.madv, 0), s.madv))

    def eligible_packages(self):
        from .vietqr_service import vietqr_available
        if not current_app.config.get('PACKAGE_CUSTOMER_CASH_ENABLED') and not vietqr_available():
            return []
        packages = GoiDichVu.query.options(selectinload(GoiDichVu.items).joinedload(GoiDichVuItem.service).load_only(DichVu.madv, DichVu.active), defer(GoiDichVu.anhgoi)).filter_by(
            active=True, customer_sale_enabled=True).all()
        return [p for p in packages if p.items and all(
            item.service and item.service.active and item.total_sessions > 0 for item in p.items)]

    def package_rows(self, packages):
        rows = []
        for package in packages:
            sessions = sum(item.total_sessions for item in package.items)
            score = sum(self.scores.get(item.madv, 0) * item.total_sessions for item in package.items) / sessions
            score += .05 * normalize(self.package_views[package.magoi])
            if package.magoi in self.owned_packages:
                score -= .5  # Penalty also works for negative ratings; multiplying would increase a negative score.
            rows.append(dict(magoi=package.magoi, tengoi=package.tengoi, score=round(score, 6),
                reason='Gói gồm các dịch vụ phù hợp với sở thích của bạn' if self.has_signal else 'Gói gồm các dịch vụ được nhiều khách lựa chọn'))
        return sorted(rows, key=lambda row: (-row['score'], row['magoi']))

    def recommend_packages(self, limit=4):
        return self.package_rows(self.eligible_packages())[:limit]

    def response(self, service_limit=6, package_limit=4):
        return self.serialize_rows(self.recommend_services(service_limit), self.recommend_packages(package_limit))

    def serialize_rows(self, services, packages):
        from .package_service import serialize_package
        # Fetch images only for the selected cards, in one query.
        selected = {s.madv: s for s in DichVu.query.filter(DichVu.madv.in_([row['madv'] for row in services])).all()}
        for row in services:
            service = selected[row['madv']]
            row.update(gia=str(service.gia), thoiluong=service.thoiluong, mota=service.mota or '',
                anhdichvu=base64.b64encode(service.anhdichvu).decode('ascii') if service.anhdichvu else None)
        selected_packages = {p.magoi: p for p in GoiDichVu.query.options(
            selectinload(GoiDichVu.items).joinedload(GoiDichVuItem.service)).filter(
            GoiDichVu.magoi.in_([row['magoi'] for row in packages])).all()}
        for row in packages:
            row.update(serialize_package(selected_packages[row['magoi']]))
            # The public API carries explanations; numeric scores remain backend-only.
            row.pop('score')
            row.pop('post_care_instructions', None)
        for row in services:
            row.pop('score')
        return dict(success=True, strategy=self.strategy,
            reason='Dựa trên những dịch vụ bạn quan tâm và sử dụng gần đây' if self.has_signal else 'Các dịch vụ được nhiều khách lựa chọn',
            services=services, packages=packages)

    def related(self, current_service_id, service_limit=3, package_limit=2):
        current = self.services.get(current_service_id)
        if not current or not current.active:
            raise RecommendationError('Dịch vụ không tồn tại hoặc đã ngừng hoạt động', 404)
        category_id = current.category_id if current.category and current.category.active else None

        def same_category(service):
            return bool(category_id and service.category_id == category_id)

        def similarity(service):
            # Bounded numeric similarity; a category match always takes precedence.
            def closeness(a, b):
                return 1 - abs(float(a or 0) - float(b or 0)) / max(float(a or 0), float(b or 0), 1)
            return (closeness(current.gia, service.gia) + closeness(current.thoiluong, service.thoiluong)) / 2

        service_candidates = [s for s in self.services.values() if s.active and s.madv != current_service_id]
        service_candidates.sort(key=lambda s: (-int(same_category(s)), -similarity(s),
            -self.scores.get(s.madv, 0) if self.has_signal else 0, -self.popularity[s.madv], s.madv))
        services = [dict(madv=s.madv, tendv=s.tendv, score=self.scores[s.madv],
            reason='Cùng nhóm dịch vụ bạn đang xem' if same_category(s) else 'Dịch vụ có giá và thời lượng tương tự')
            for s in service_candidates[:service_limit]]
        packages = self.eligible_packages()
        package_scores = {r['magoi']: r for r in self.package_rows(packages)}

        def package_context(package):
            contains = any(i.madv == current_service_id for i in package.items)
            overlap = sum(i.total_sessions for i in package.items if same_category(self.services[i.madv])) / sum(i.total_sessions for i in package.items)
            popularity = sum(self.popularity[i.madv] for i in package.items) / len(package.items)
            return int(contains), overlap, package_scores[package.magoi]['score'] if self.has_signal else 0, popularity

        packages.sort(key=lambda p: (*(-v for v in package_context(p)), p.magoi))
        package_rows = [dict(package_scores[p.magoi], reason='Gói có dịch vụ bạn đang xem' if package_context(p)[0]
            else 'Gói có dịch vụ cùng nhóm bạn đang xem' if package_context(p)[1] else 'Gói dịch vụ được khách hàng quan tâm')
            for p in packages[:package_limit]]
        payload = self.serialize_rows(services, package_rows)
        # One mixed list; context remains primary across both card types.
        mixed = [(2 if same_category(self.services[r['madv']]) else 0, index, dict(r, type='service'))
            for index, r in enumerate(payload['services'])]
        for index, row in enumerate(payload['packages']):
            context = package_context(packages[index])
            mixed.append((3 if context[0] else 2 if context[1] else 0, index, dict(row, type='package')))
        mixed.sort(key=lambda row: (-row[0], row[1], row[2]['type']))
        return dict(success=True, items=[row[2] for row in mixed])


def recommend_services(customer_id, limit=6):
    return Ranking(customer_id).recommend_services(limit)


def recommend_packages(customer_id, limit=4):
    return Ranking(customer_id).recommend_packages(limit)


def customer_interest_profile(customer_id):
    return dict(Ranking(customer_id).category)


def rank_services_for_customer(customer_id, candidate_services):
    return Ranking(customer_id).rank_services(candidate_services)


def get_related_recommendations(customer_id, current_service_id, service_limit=3, package_limit=2):
    return Ranking(customer_id).related(current_service_id, service_limit, package_limit)


def serialize_service(service):
    image = service.anhdichvu
    return dict(madv=service.madv, tendv=service.tendv, gia=str(service.gia),
        thoiluong=service.thoiluong, mota=service.mota or '',
        category_id=service.category_id,
        category_slug=service.category.slug if service.category else None,
        category_name=service.category.name if service.category else None,
        anhdichvu=base64.b64encode(image).decode('ascii') if isinstance(image, bytes) else image)

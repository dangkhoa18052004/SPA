"""Loyalty accounting. Never commit here: payment and ledger share one transaction.

Lock order: payment target -> customer/wallet -> reward redemption/catalog.
available + reserved equals SUM(ledger.points_delta); reserving never writes ledger.
Money is Decimal, points are integers, earning rounds down by complete amount units.
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from sqlalchemy import func
from ..extensions import db
from ..models import (KhachHang, HoaDon, GoiDichVuPurchase, LoyaltyWallet,
    LoyaltyConfig, LoyaltyPointTransaction, LoyaltyRedemptionReservation,
    LoyaltyReward, LoyaltyRewardRedemption)


class LoyaltyError(ValueError):
    pass


DEFAULTS = dict(earn_amount_unit=Decimal('100000'), earn_points=10,
    point_value=Decimal('1000'), minimum_redeem_points=10,
    maximum_redeem_percent=Decimal('50'), earn_on_service_invoice=True,
    earn_on_package_purchase=True, redeem_on_service_invoice=True,
    redeem_on_package_purchase=True, points_expiry_months=None)


def integer(value, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 2147483647:
        raise LoyaltyError('Số điểm phải là số nguyên hợp lệ')
    return value


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal('9999999999.99'):
            raise ValueError()
        if result != result.quantize(Decimal('0.01')):
            raise ValueError()
        return result.quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        raise LoyaltyError('Số tiền không hợp lệ')


def get_config():
    # Reading/previewing on a fresh test DB must not INSERT defaults.
    return db.session.get(LoyaltyConfig, 1) or LoyaltyConfig(id=1, **DEFAULTS)


def serialize_config(config=None):
    config = config or get_config()
    return {key: str(getattr(config, key)) if isinstance(getattr(config, key), Decimal)
            else getattr(config, key) for key in DEFAULTS}


def update_config(data):
    if not isinstance(data, dict) or set(data) - set(DEFAULTS):
        raise LoyaltyError('Cấu hình không hợp lệ')
    values = dict(serialize_config(), **data)
    for key in ('earn_amount_unit', 'point_value', 'maximum_redeem_percent'):
        values[key] = money(values[key])
    for key in ('earn_points', 'minimum_redeem_points'):
        values[key] = integer(values[key], 0 if key == 'earn_points' else 1)
    for key in ('earn_on_service_invoice', 'earn_on_package_purchase', 'redeem_on_service_invoice', 'redeem_on_package_purchase'):
        if not isinstance(values[key], bool):
            raise LoyaltyError('Quy tắc bật/tắt phải là boolean')
    if values['earn_amount_unit'] <= 0 or values['point_value'] <= 0 or values['point_value'] % 1 or values['maximum_redeem_percent'] > 100 or values['points_expiry_months'] is not None:
        raise LoyaltyError('Quy tắc quy đổi không hợp lệ; điểm GĐ3A không hết hạn')
    config = get_config()
    for key, value in values.items():
        setattr(config, key, value)
    db.session.add(config)
    db.session.flush()
    return config


def get_wallet(makh, lock=False):
    # Parent row exists even before a wallet. This serializes lazy creation as
    # well as balance changes on PostgreSQL and SQLite without INSERT races.
    if not KhachHang.query.filter_by(makh=makh).update(
            {KhachHang.makh: KhachHang.makh}, synchronize_session=False):
        raise LoyaltyError('Không tìm thấy khách hàng')
    wallet = LoyaltyWallet.query.filter_by(makh=makh).populate_existing().with_for_update().first()
    if wallet is None:
        wallet = LoyaltyWallet(makh=makh)
        db.session.add(wallet)
        db.session.flush()
    return wallet


def get_balance(makh):
    wallet = LoyaltyWallet.query.filter_by(makh=makh).first()
    return {key: getattr(wallet, key) if wallet else 0 for key in
            ('available_points', 'reserved_points', 'lifetime_earned', 'lifetime_redeemed')}


def lock_target(kind, record_id, makh=None):
    if kind == 'service_invoice':
        model, column = HoaDon, HoaDon.mahd
    elif kind == 'package_purchase':
        model, column = GoiDichVuPurchase, GoiDichVuPurchase.id
    else:
        raise LoyaltyError('Loại thanh toán không hợp lệ')
    query = model.query.filter(column == record_id)
    if makh is not None:
        query = query.filter(model.makh == makh)
    if not query.update({column: column}, synchronize_session=False):
        raise LoyaltyError('Không tìm thấy thanh toán của khách hàng')
    return query.populate_existing().one()


def target_kind(target):
    return 'service_invoice' if isinstance(target, HoaDon) else 'package_purchase'


def target_id(target):
    return target.mahd if isinstance(target, HoaDon) else target.id


def original_total(target):
    return money(target.tongtien if isinstance(target, HoaDon) else target.amount)


def payable(target):
    return money(target.payable_amount if target.payable_amount is not None else original_total(target))


def is_paid(target):
    return target.trangthai == 'Đã thanh toán' if isinstance(target, HoaDon) else target.status == 'paid'


def require_unpaid(target):
    valid = target.trangthai == 'Chưa thanh toán' if isinstance(target, HoaDon) else target.status == 'pending'
    if not valid:
        raise LoyaltyError('Chỉ thay đổi ưu đãi khi chưa thanh toán')


def active_reservation(target):
    return LoyaltyRedemptionReservation.query.filter_by(target_type=target_kind(target),
        target_id=target_id(target), status='reserved').first()


def calculate_earned_points(amount, config=None):
    config = config or get_config()
    return int(money(amount) // config.earn_amount_unit) * config.earn_points


def calculate_point_discount(target, points, config=None):
    points = integer(points)
    config = config or get_config()
    reservation = active_reservation(target)
    balance = get_balance(target.makh)
    available = balance['available_points'] + (reservation.points_reserved if reservation else 0)
    base = original_total(target) - money(target.reward_discount or 0)
    enabled = getattr(config, 'redeem_on_' + target_kind(target))
    # Floor to whole VND before points, never exceed the configured percentage.
    cap = int(base * config.maximum_redeem_percent / Decimal(100) // config.point_value) if enabled else 0
    maximum = min(available, cap)
    if maximum < config.minimum_redeem_points:
        maximum = 0
    allowed = min(points, maximum)
    if allowed < config.minimum_redeem_points:
        allowed = 0
    discount = money(allowed * config.point_value)
    return dict(available_points=balance['available_points'], points_requested=points,
        points_allowed=allowed, discount_amount=str(discount), original_total=str(original_total(target)),
        reward_discount=str(money(target.reward_discount or 0)), payable_amount=str(base-discount),
        max_points_allowed=maximum, redeem_enabled=enabled)


def recalculate(target):
    target.payable_amount = original_total(target) - money(target.reward_discount or 0) - money(target.loyalty_discount or 0)
    if target.payable_amount < 0:
        raise LoyaltyError('Ưu đãi vượt giá trị thanh toán')


def touch(wallet):
    wallet.version += 1
    wallet.updated_at = datetime.utcnow()


def reserve_points(target, points, idempotency_key=None):
    require_unpaid(target)
    points = integer(points, 1)
    wallet = get_wallet(target.makh, lock=True)
    preview = calculate_point_discount(target, points)
    if preview['points_allowed'] != points:
        raise LoyaltyError('Số điểm vượt số dư/quy tắc áp dụng')
    existing = active_reservation(target)
    if existing and existing.points_reserved == points and existing.discount_amount == money(preview['discount_amount']):
        return existing
    release_points(target, wallet=wallet)
    wallet.available_points -= points
    wallet.reserved_points += points
    touch(wallet)
    reservation = LoyaltyRedemptionReservation(makh=target.makh, target_type=target_kind(target),
        target_id=target_id(target), points_reserved=points, discount_amount=money(preview['discount_amount']),
        status='reserved', idempotency_key=f'loyalty:reserve:{target_kind(target)}:{target_id(target)}:{idempotency_key or uuid4().hex}')
    db.session.add(reservation)
    target.loyalty_discount = reservation.discount_amount
    recalculate(target)
    db.session.flush()
    return reservation


def release_points(target, wallet=None):
    require_unpaid(target)
    wallet = wallet or get_wallet(target.makh, lock=True)
    reservation = active_reservation(target)
    if reservation:
        wallet.reserved_points -= reservation.points_reserved
        wallet.available_points += reservation.points_reserved
        touch(wallet)
        reservation.status, reservation.released_at = 'released', datetime.utcnow()
    target.loyalty_discount = Decimal(0)
    recalculate(target)
    db.session.flush()


def reference(target):
    return f'HD{target_id(target):06d}' if isinstance(target, HoaDon) else f'PG{target_id(target):06d}'


def ledger_key(action, target):
    name = 'invoice' if isinstance(target, HoaDon) else 'package'
    return f'loyalty:{action}:{name}:{target_id(target)}'


def post(wallet, delta, kind, source_type, source_id, key, description, staff_id=None, metadata=None, reserved=False):
    existing = LoyaltyPointTransaction.query.filter_by(idempotency_key=key).first()
    if existing:
        if existing.makh != wallet.makh or existing.points_delta != delta:
            raise LoyaltyError('Khóa chống trùng không khớp giao dịch')
        return existing
    if not delta:
        return None
    if not reserved and wallet.available_points + delta < 0:
        raise LoyaltyError('Không đủ điểm khả dụng')
    if reserved:
        if delta >= 0 or wallet.reserved_points < -delta:
            raise LoyaltyError('Reservation không khớp ví')
        wallet.reserved_points += delta
    else:
        wallet.available_points += delta
    if kind == 'earn':
        wallet.lifetime_earned += delta
    if kind in ('redeem', 'reward_redeem'):
        wallet.lifetime_redeemed -= delta
    touch(wallet)
    txn = LoyaltyPointTransaction(makh=wallet.makh, wallet_id=wallet.id, type=kind,
        points_delta=delta, source_type=source_type, source_id=source_id, reference_code=description.split(' · ')[0][:80],
        description=description, idempotency_key=key, created_by_staff=staff_id, metadata_json=metadata)
    db.session.add(txn)
    db.session.flush()
    return txn


def consume_reserved_points(target, wallet=None):
    if not is_paid(target):
        raise LoyaltyError('Chỉ ghi điểm sau khi thanh toán được xác nhận')
    wallet = wallet or get_wallet(target.makh, lock=True)
    reservation = active_reservation(target)
    if reservation:
        if reservation.makh != target.makh or reservation.discount_amount != money(target.loyalty_discount):
            raise LoyaltyError('Reservation không khớp thanh toán')
        post(wallet, -reservation.points_reserved, 'redeem', target_kind(target), target_id(target),
             ledger_key('redeem', target), reference(target)+' · Sử dụng điểm', reserved=True)
        reservation.status, reservation.consumed_at = 'consumed', datetime.utcnow()
    elif money(target.loyalty_discount or 0) and not LoyaltyPointTransaction.query.filter_by(idempotency_key=ledger_key('redeem', target)).first():
        raise LoyaltyError('Thiếu reservation cho thanh toán')


def award_points(target, wallet=None):
    if not is_paid(target):
        raise LoyaltyError('Chưa xác nhận thanh toán')
    wallet = wallet or get_wallet(target.makh, lock=True)
    config = get_config()
    if not getattr(config, 'earn_on_' + target_kind(target)):
        return None
    existing = LoyaltyPointTransaction.query.filter_by(idempotency_key=ledger_key('earn', target)).first()
    if existing:
        return existing
    return post(wallet, calculate_earned_points(payable(target), config), 'earn', target_kind(target),
        target_id(target), ledger_key('earn', target), reference(target)+' · Thanh toán',
        metadata={'actual_paid': str(payable(target)), 'earn_amount_unit': str(config.earn_amount_unit), 'earn_points': config.earn_points})


def finalize_payment(target):
    wallet = get_wallet(target.makh, lock=True)
    consume_reserved_points(target, wallet)
    voucher = LoyaltyRewardRedemption.query.filter_by(target_type=target_kind(target), target_id=target_id(target), status='reserved').with_for_update().first()
    if voucher:
        # A voucher already reserved for this payment remains valid on resume.
        voucher.status, voucher.used_at = 'used', datetime.utcnow()
    elif money(target.reward_discount or 0) and not LoyaltyRewardRedemption.query.filter_by(target_type=target_kind(target), target_id=target_id(target), status='used').first():
        raise LoyaltyError('Thiếu voucher cho thanh toán')
    award_points(target, wallet)
    db.session.flush()


def admin_adjust_points(makh, points_delta, reason, staff_id, idempotency_key):
    if not isinstance(points_delta, int) or isinstance(points_delta, bool) or not points_delta or abs(points_delta) > 2147483647:
        raise LoyaltyError('Số điểm điều chỉnh không hợp lệ')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise LoyaltyError('Bắt buộc nhập lý do (tối đa 2000 ký tự)')
    wallet = get_wallet(makh, lock=True)
    return post(wallet, points_delta, 'adjustment_add' if points_delta > 0 else 'adjustment_subtract',
        'admin_adjustment', makh, f'loyalty:adjust:{makh}:{idempotency_key}', reason.strip(), staff_id)


def reverse_points(transaction, wallet):
    return post(wallet, -transaction.points_delta, 'refund', transaction.source_type, transaction.source_id,
        f'loyalty:reverse:{transaction.id}', transaction.reference_code+' · Hoàn tác điểm',
        metadata={'reverses_transaction_id': transaction.id})


def reverse_loyalty_for_payment(kind, record_id):
    target = lock_target(kind, record_id)
    if not is_paid(target):
        raise LoyaltyError('Chỉ hoàn tác điểm cho thanh toán đã xác nhận')
    wallet = get_wallet(target.makh, lock=True)
    # Restore redeemed points before clawing back earnings; never permit debt.
    rows = LoyaltyPointTransaction.query.filter_by(source_type=kind, source_id=record_id).filter(
        LoyaltyPointTransaction.type.in_(['redeem', 'earn'])).order_by(LoyaltyPointTransaction.points_delta).all()
    for row in rows:
        reverse_points(row, wallet)
    db.session.flush()


def serialize_reward(reward):
    return dict(id=reward.id, name=reward.name, description=reward.description,
        reward_type=reward.reward_type, points_cost=reward.points_cost,
        reward_value=str(reward.reward_value), stock=reward.stock, validity_days=reward.validity_days, active=reward.active)


def save_reward(data, reward=None):
    if not isinstance(data, dict):
        raise LoyaltyError('Quà không hợp lệ')
    values = dict(serialize_reward(reward) if reward else {}, **data)
    name = values.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 200 or values.get('reward_type') not in ('voucher_amount', 'physical_gift'):
        raise LoyaltyError('Tên hoặc loại quà không hợp lệ')
    values['points_cost'] = integer(values.get('points_cost'), 1)
    values['reward_value'] = money(values.get('reward_value', 0))
    if values['reward_type'] == 'voucher_amount' and not values['reward_value']:
        raise LoyaltyError('Voucher cần giá trị lớn hơn 0')
    for key in ('stock', 'validity_days'):
        if values.get(key) is not None:
            values[key] = integer(values[key], 0 if key == 'stock' else 1)
    if values.get('validity_days') is not None and values['validity_days'] > 36500:
        raise LoyaltyError('Hiệu lực quà tối đa 36.500 ngày')
    if not isinstance(values.get('active', True), bool) or not isinstance(values.get('description', ''), str):
        raise LoyaltyError('Quà không hợp lệ')
    reward = reward or LoyaltyReward()
    for key in ('description', 'reward_type', 'points_cost', 'reward_value', 'stock', 'validity_days', 'active'):
        setattr(reward, key, values.get(key, '' if key == 'description' else True if key == 'active' else None))
    reward.name = name.strip()
    db.session.add(reward)
    db.session.flush()
    return reward


def redeem_reward(makh, reward_id, idempotency_key):
    wallet = get_wallet(makh, lock=True)
    key = f'loyalty:reward:{makh}:{idempotency_key}'
    existing = LoyaltyRewardRedemption.query.filter_by(idempotency_key=key).first()
    if existing:
        if existing.reward_id != reward_id:
            raise LoyaltyError('Khóa chống trùng không khớp quà')
        return existing
    if not LoyaltyReward.query.filter_by(id=reward_id).update({LoyaltyReward.id: LoyaltyReward.id}, synchronize_session=False):
        raise LoyaltyError('Không tìm thấy quà')
    reward = LoyaltyReward.query.filter_by(id=reward_id).populate_existing().one()
    if not reward.active or reward.stock == 0:
        raise LoyaltyError('Quà đã hết hoặc ngừng đổi')
    if wallet.available_points < reward.points_cost:
        raise LoyaltyError('Không đủ điểm đổi quà')
    redemption = LoyaltyRewardRedemption(makh=makh, reward_id=reward_id, points_spent=reward.points_cost,
        reward_snapshot_json=serialize_reward(reward), status='available', code='BIN-'+uuid4().hex[:16].upper(),
        expires_at=datetime.utcnow()+timedelta(days=reward.validity_days) if reward.validity_days else None, idempotency_key=key)
    db.session.add(redemption)
    db.session.flush()
    post(wallet, -reward.points_cost, 'reward_redeem', 'reward', redemption.id, key,
        redemption.code+' · Đổi '+reward.name)
    if reward.stock is not None:
        reward.stock -= 1
    return redemption


def apply_reward(target, redemption_id):
    require_unpaid(target)
    get_wallet(target.makh, lock=True)
    if not LoyaltyRewardRedemption.query.filter_by(id=redemption_id, makh=target.makh).update(
            {LoyaltyRewardRedemption.id: LoyaltyRewardRedemption.id}, synchronize_session=False):
        raise LoyaltyError('Không tìm thấy ưu đãi của khách hàng')
    voucher = LoyaltyRewardRedemption.query.filter_by(id=redemption_id).populate_existing().one()
    if voucher.status == 'reserved' and voucher.target_type == target_kind(target) and voucher.target_id == target_id(target):
        return voucher
    if voucher.status != 'available' or voucher.reward_snapshot_json['reward_type'] != 'voucher_amount' or (voucher.expires_at and voucher.expires_at < datetime.utcnow()):
        raise LoyaltyError('Voucher không còn khả dụng')
    if LoyaltyRewardRedemption.query.filter_by(target_type=target_kind(target), target_id=target_id(target), status='reserved').first():
        raise LoyaltyError('Hãy bỏ voucher hiện tại trước khi áp dụng voucher khác')
    voucher.status, voucher.target_type, voucher.target_id = 'reserved', target_kind(target), target_id(target)
    target.reward_discount = min(original_total(target), money(voucher.reward_snapshot_json['reward_value']))
    reservation = active_reservation(target)
    if reservation and calculate_point_discount(target, reservation.points_reserved)['points_allowed'] != reservation.points_reserved:
        raise LoyaltyError('Hãy giảm/bỏ điểm trước khi áp dụng voucher')
    recalculate(target)
    db.session.flush()
    return voucher


def release_reward(target):
    require_unpaid(target)
    get_wallet(target.makh, lock=True)
    voucher = LoyaltyRewardRedemption.query.filter_by(target_type=target_kind(target), target_id=target_id(target), status='reserved').with_for_update().first()
    if voucher:
        voucher.status = 'expired' if voucher.expires_at and voucher.expires_at < datetime.utcnow() else 'available'
        voucher.target_type, voucher.target_id = None, None
    target.reward_discount = Decimal(0)
    recalculate(target)
    db.session.flush()


def fulfill_reward(redemption_id, staff_id):
    if not LoyaltyRewardRedemption.query.filter_by(id=redemption_id).update(
            {LoyaltyRewardRedemption.id: LoyaltyRewardRedemption.id}, synchronize_session=False):
        raise LoyaltyError('Không tìm thấy quà đã đổi')
    redemption = LoyaltyRewardRedemption.query.filter_by(id=redemption_id).populate_existing().one()
    if redemption.status == 'fulfilled':
        return redemption
    if redemption.reward_snapshot_json['reward_type'] != 'physical_gift' or redemption.status != 'available' or (redemption.expires_at and redemption.expires_at < datetime.utcnow()):
        raise LoyaltyError('Quà không thể bàn giao')
    redemption.status, redemption.fulfilled_at, redemption.fulfilled_by_staff = 'fulfilled', datetime.utcnow(), staff_id
    return redemption


def payment_summary(target):
    kind, record_id = target_kind(target), target_id(target)
    rows = LoyaltyPointTransaction.query.filter_by(source_type=kind, source_id=record_id).all()
    reservation = active_reservation(target)
    voucher = LoyaltyRewardRedemption.query.filter_by(target_type=kind, target_id=record_id).filter(
        LoyaltyRewardRedemption.status.in_(['reserved', 'used'])).first()
    return dict(original_total=str(original_total(target)), reward_discount=str(money(target.reward_discount or 0)),
        loyalty_discount=str(money(target.loyalty_discount or 0)), payable_amount=str(payable(target)),
        points_used=reservation.points_reserved if reservation else -sum(r.points_delta for r in rows if r.type == 'redeem'),
        points_earned=sum(r.points_delta for r in rows if r.type == 'earn'),
        reward_redemption_id=voucher.id if voucher else None)


def serialize_transaction(row):
    return {key: getattr(row, key) for key in ('id', 'makh', 'type', 'points_delta', 'source_type', 'source_id', 'reference_code', 'description', 'created_by_staff')} | {'created_at': row.created_at.isoformat()+'Z'}


REDEMPTION_GROUPS = ('all', 'usable', 'pickup', 'applied', 'done', 'closed')
REWARD_TYPES = ('voucher_amount', 'physical_gift')


def redemption_status(row, now=None):
    # Expiry is derived, never written on read: filters below use the same rule.
    now = now or datetime.utcnow()
    return 'expired' if row.status == 'available' and row.expires_at and row.expires_at < now else row.status


def like_pattern(text):
    # Paired with escape='!' so user text never acts as a wildcard.
    return '%' + text.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def filter_redemptions(query, group='all', reward_type=None, search=None, now=None):
    model = LoyaltyRewardRedemption
    now = now or datetime.utcnow()
    kind = model.reward_snapshot_json['reward_type'].as_string()
    live = db.and_(model.status == 'available', db.or_(model.expires_at.is_(None), model.expires_at >= now))
    conditions = dict(all=[], usable=[live, kind == 'voucher_amount'], pickup=[live, kind == 'physical_gift'],
        applied=[model.status == 'reserved'], done=[model.status.in_(['used', 'fulfilled'])],
        closed=[db.or_(model.status.in_(['expired', 'cancelled']), db.and_(model.status == 'available', model.expires_at < now))])
    if group not in conditions:
        raise LoyaltyError('Nhóm trạng thái không hợp lệ')
    query = query.filter(*conditions[group])
    if reward_type:
        query = query.filter(kind == reward_type)
    if search:
        pattern = like_pattern(search)
        query = query.filter(db.or_(model.code.ilike(pattern, escape='!'),
            model.reward_snapshot_json['name'].as_string().ilike(pattern, escape='!')))
    return query


def serialize_redemption(row, now=None):
    status = redemption_status(row, now)
    return dict(id=row.id, makh=row.makh, reward_id=row.reward_id, points_spent=row.points_spent,
        reward=row.reward_snapshot_json, status=status, code=row.code,
        expires_at=row.expires_at.isoformat()+'Z' if row.expires_at else None,
        redeemed_at=row.redeemed_at.isoformat()+'Z', used_at=row.used_at.isoformat()+'Z' if row.used_at else None,
        fulfilled_at=row.fulfilled_at.isoformat()+'Z' if row.fulfilled_at else None,
        fulfilled_by_staff=row.fulfilled_by_staff, target_type=row.target_type, target_id=row.target_id)

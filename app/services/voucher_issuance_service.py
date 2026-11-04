"""Gift issuance shares loyalty stock, immutable snapshots and the payment lifecycle.

No commits. Manual locks actor -> customer -> catalog; welcome already holds customer.
The actor lock serializes a key even when requests specify different recipients.
"""
from datetime import datetime, timezone
from ..extensions import db
from ..models import (KhachHang, NhanVien, LoyaltyReward, LoyaltyRewardRedemption,
                      WelcomeVoucherConfig, CustomerOtpRegistration)
from . import loyalty_service as loyalty
from . import voucher_observability as events


class IssuanceError(loyalty.LoyaltyError):
    def __init__(self, message, status=400, reason='validation_error'):
        super().__init__(message)
        self.status = status
        self.reason = reason


def clean_text(value, label, maximum, required=False):
    if value is None and not required:
        return ''
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise IssuanceError(f'{label} không hợp lệ (tối đa {maximum} ký tự)')
    return value.strip()


def manual_gift(makh, data, staff_id, key):
    if set(data) - {'reward_id', 'reason', 'customer_message'}:
        raise IssuanceError('Chỉ được chọn mẫu, lý do và lời nhắn')
    body = dict(makh=makh, reward_id=loyalty.integer(data.get('reward_id'), 1),
        reason=clean_text(data.get('reason'), 'Lý do nội bộ', 2000, True),
        customer_message=clean_text(data.get('customer_message'), 'Lời nhắn', 1000))
    # Touch a non-key column: PostgreSQL's NO KEY UPDATE lock permits FK KEY SHARE
    # checks by cancellation/payment while still serializing the actor's gifts.
    if not NhanVien.query.filter_by(manv=staff_id, trangthai=True).filter(
            NhanVien.role.in_(('admin', 'manager', 'letan'))).update({NhanVien.trangthai: NhanVien.trangthai}, synchronize_session=False):
        raise IssuanceError('Không có quyền tặng voucher', 403)
    operation_key = f'loyalty:gift:{staff_id}:{key}'
    previous = LoyaltyRewardRedemption.query.filter_by(idempotency_key=operation_key).first()
    if previous:
        if previous.issuance_payload_json != body:
            raise IssuanceError('Khóa chống trùng đã dùng với nội dung khác', 409, 'idempotency_conflict')
        events.after_commit('replayed', source='staff_gift', operation='issue', redemption_id=previous.id, reward_id=previous.reward_id)
        return previous, False
    # No wallet is created or changed when issuing a gift.
    if not KhachHang.query.filter_by(makh=makh).update({KhachHang.makh: KhachHang.makh}, synchronize_session=False):
        raise IssuanceError('Không tìm thấy khách hàng', 404)
    customer = KhachHang.query.filter_by(makh=makh).populate_existing().one()
    if customer.trangthai != 'active':
        raise IssuanceError('Chỉ tặng voucher cho khách đang hoạt động')
    if not db.session.get(LoyaltyReward, body['reward_id']):
        raise IssuanceError('Không tìm thấy mẫu voucher', 404)
    reward = loyalty.lock_reward(body['reward_id'])
    if reward.reward_type not in loyalty.VOUCHER_TYPES:
        raise IssuanceError('Chỉ tặng voucher giảm tiền hoặc phần trăm')
    if reward.stock == 0:
        raise IssuanceError('Mẫu voucher đã hết tồn', 409, 'out_of_stock')
    row = loyalty.issue_reward(makh, reward, operation_key, points_spent=0,
        issuance_source='staff_gift', issued_by_staff=staff_id, gift_reason=body['reason'],
        customer_message=body['customer_message'], issuance_payload_json=body)
    return row, True


def serialize_gift(row):
    staff = db.session.get(NhanVien, row.issued_by_staff) if row.issued_by_staff else None
    canceller = db.session.get(NhanVien, row.cancelled_by_staff) if row.cancelled_by_staff else None
    return dict(loyalty.serialize_redemption(row), issued_by_staff=row.issued_by_staff,
        issued_by_name=staff.hoten if staff else None, gift_reason=row.gift_reason,
        cancelled_by_staff=row.cancelled_by_staff, cancelled_by_name=canceller.hoten if canceller else None,
        cancelled_at=iso(row.cancelled_at), cancel_reason=row.cancel_reason)


def cancel_gift(redemption_id, reason, staff_id):
    reason = clean_text(reason, 'Lý do thu hồi', 2000, True)
    # Same write lock as apply_reward: cancellation and reservation cannot both win.
    if not LoyaltyRewardRedemption.query.filter_by(id=redemption_id).update(
            {LoyaltyRewardRedemption.id: LoyaltyRewardRedemption.id}, synchronize_session=False):
        raise IssuanceError('Không tìm thấy voucher', 404)
    row = LoyaltyRewardRedemption.query.filter_by(id=redemption_id).populate_existing().one()
    if row.issuance_source not in ('welcome', 'staff_gift'):
        raise IssuanceError('Chỉ thu hồi voucher được tặng')
    if loyalty.redemption_status(row) != 'available':
        raise IssuanceError('Chỉ thu hồi voucher còn hạn, chưa giữ hoặc sử dụng', 409)
    row.status, row.cancelled_at, row.cancelled_by_staff, row.cancel_reason = 'cancelled', datetime.utcnow(), staff_id, reason
    db.session.flush()
    events.after_commit('cancelled', source=row.issuance_source, operation='cancel', redemption_id=row.id, reward_id=row.reward_id)
    return row


def iso(value):
    return value.isoformat()+'Z' if value else None


def get_welcome_config():
    return db.session.get(WelcomeVoucherConfig, 1)


def serialize_welcome_config():
    row = get_welcome_config()
    return dict(enabled=bool(row and row.enabled), reward_id=row.reward_id if row else None,
        starts_at=iso(row.starts_at) if row else None, ends_at=iso(row.ends_at) if row else None,
        updated_at=iso(row.updated_at) if row else None, updated_by_staff=row.updated_by_staff if row else None)


def parse_date(value):
    if value in (None, ''):
        return None
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError()
        return date.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, AttributeError):
        raise IssuanceError('Thời gian phải là ISO 8601 kèm múi giờ')


def update_welcome_config(data, staff_id):
    if set(data) - {'enabled', 'reward_id', 'starts_at', 'ends_at'}:
        raise IssuanceError('Cấu hình không hợp lệ')
    enabled = data.get('enabled')
    if not isinstance(enabled, bool):
        raise IssuanceError('Trạng thái chương trình phải là boolean')
    start, end = parse_date(data.get('starts_at')), parse_date(data.get('ends_at'))
    if enabled and not start:
        start = datetime.utcnow()
    if end and (not start or end <= start):
        raise IssuanceError('Ngày kết thúc phải sau ngày bắt đầu')
    reward_id = data.get('reward_id')
    if reward_id is not None:
        loyalty.integer(reward_id, 1)
        reward = db.session.get(LoyaltyReward, reward_id)
        if not reward or (enabled and (reward.reward_type not in loyalty.VOUCHER_TYPES or not reward.validity_days)):
            raise IssuanceError('Cần mẫu voucher có hạn dùng; hãy nhập số ngày hiệu lực trong Sửa mẫu')
    if enabled and (not start or reward_id is None):
        raise IssuanceError('Chọn mẫu voucher chào mừng trước khi bật chương trình')
    # Stable singleton write lock also protects first-time configuration.
    NhanVien.query.filter_by(manv=staff_id).update({NhanVien.trangthai: NhanVien.trangthai}, synchronize_session=False)
    row = WelcomeVoucherConfig.query.filter_by(id=1).populate_existing().with_for_update().first()
    if not row:
        # Concurrent first writes by different managers may conflict on id=1;
        # the route's IntegrityError handler rolls back and allows a clean retry.
        row = WelcomeVoucherConfig(id=1)
        db.session.add(row)
    if enabled:
        reward = loyalty.lock_reward(reward_id)
        if reward.reward_type not in loyalty.VOUCHER_TYPES or not reward.validity_days:
            raise IssuanceError('Mẫu chào mừng phải là voucher có số ngày hiệu lực')
    row.enabled, row.reward_id, row.starts_at, row.ends_at = enabled, reward_id, start, end
    row.updated_by_staff, row.updated_at = staff_id, datetime.utcnow()
    db.session.flush()
    return row


def save_template(data, staff_id, reward=None):
    """Save the normal editor and its new-customer selection atomically."""
    data = dict(data)
    welcome = data.pop('for_new_customers', None)
    if welcome is not None and not isinstance(welcome, bool):
        raise IssuanceError('Dành cho khách hàng mới phải là boolean')
    NhanVien.query.filter_by(manv=staff_id).update({NhanVien.trangthai: NhanVien.trangthai}, synchronize_session=False)
    config = WelcomeVoucherConfig.query.filter_by(id=1).with_for_update().first()
    if reward:
        reward = loyalty.lock_reward(reward.id)
    if welcome is False and reward and config and config.reward_id == reward.id:
        update_welcome_config(dict(enabled=False, reward_id=None, starts_at=None, ends_at=None), staff_id)
    if welcome:
        data.update(allow_points_redemption=False, points_cost=0)
    reward = loyalty.save_reward(data, reward)
    if welcome:
        same_program = config and config.enabled and config.reward_id == reward.id
        update_welcome_config(dict(enabled=True, reward_id=reward.id,
            starts_at=iso(config.starts_at) if same_program else None,
            ends_at=iso(config.ends_at) if same_program else None), staff_id)
    return reward


def _welcome_skip(reason):
    events.after_commit('skipped', source='welcome', operation='issue', reason=reason)
    return dict(issued=False, reason=reason)


def issue_welcome(customer, now=None):
    """Called only by successful pending -> active OTP CAS, with the customer lock held."""
    now = now or datetime.utcnow()
    once = f'welcome:{customer.makh}'
    previous = LoyaltyRewardRedemption.query.filter_by(welcome_once_key=once).first()
    if previous:
        return _welcome_skip('already_received')
    config = get_welcome_config()
    if not config or not config.enabled:
        return _welcome_skip('disabled')
    if not config.starts_at or now < config.starts_at or (config.ends_at and now >= config.ends_at):
        return _welcome_skip('outside_program')
    registration = db.session.get(CustomerOtpRegistration, customer.makh)
    if (not registration or not customer.ngaytao or customer.ngaytao < config.starts_at
            or registration.registered_at < config.starts_at):
        return _welcome_skip('not_new_registration')
    if customer.trangthai != 'active':
        return _welcome_skip('inactive_customer')
    if not config.reward_id or not db.session.get(LoyaltyReward, config.reward_id):
        return _welcome_skip('invalid_template')
    reward = loyalty.lock_reward(config.reward_id)
    if reward.reward_type not in loyalty.VOUCHER_TYPES or not reward.validity_days:
        return _welcome_skip('invalid_template')
    if reward.stock == 0:
        return _welcome_skip('out_of_stock')
    row = loyalty.issue_reward(customer.makh, reward, 'loyalty:'+once, points_spent=0,
        issuance_source='welcome', welcome_once_key=once)
    return dict(issued=True, reason='issued', redemption=loyalty.serialize_redemption(row))

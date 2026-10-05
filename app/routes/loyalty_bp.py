from datetime import datetime
from flask import Blueprint, request, jsonify, g
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..decorators import customer_required, login_required
from ..models import HoaDon, GoiDichVuPurchase, ThanhToan, LoyaltyPointTransaction, LoyaltyReward, LoyaltyRewardRedemption
from ..services import loyalty_service as service
from ..services import loyalty_tier_service as tiers

loyalty_bp = Blueprint('loyalty', __name__)


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise service.LoyaltyError('Dữ liệu không hợp lệ')
    return data


def request_key(data):
    key = request.headers.get('Idempotency-Key') or data.get('idempotency_key')
    if not isinstance(key, str) or not key.strip() or len(key) > 80:
        raise service.LoyaltyError('Cần mã chống trùng (Idempotency-Key, tối đa 80 ký tự)')
    return key.strip()


def paginate(query, serializer):
    page = request.args.get('page', 1, type=int)
    size = request.args.get('per_page', 20, type=int)
    if page is None or size is None or page < 1 or not 1 <= size <= 100:
        raise service.LoyaltyError('Phân trang không hợp lệ')
    result = query.paginate(page=page, per_page=size, error_out=False)
    return dict(items=[serializer(row) for row in result.items], page=page,
        per_page=size, total=result.total, pages=result.pages)


def text_arg(name, limit=100):
    value = request.args.get(name, '').strip()
    if len(value) > limit:
        raise service.LoyaltyError('Từ khóa tìm kiếm quá dài')
    return value


def choice_arg(name, choices):
    value = request.args.get(name, '').strip()
    if value and value not in choices:
        raise service.LoyaltyError('Bộ lọc không hợp lệ')
    return value


@loyalty_bp.errorhandler(service.LoyaltyError)
def validation(error):
    db.session.rollback()
    return jsonify(success=False, msg=str(error), message=str(error)), 400


@loyalty_bp.errorhandler(IntegrityError)
def conflict(error):
    db.session.rollback()
    return jsonify(success=False, msg='Giao dịch trùng hoặc đã thay đổi. Vui lòng tải lại.'), 409


@loyalty_bp.route('/api/loyalty/me')
@customer_required
def me():
    service.get_wallet(g.current_user.makh)
    balance = service.get_balance(g.current_user.makh)
    db.session.commit()
    return jsonify(success=True, wallet=balance, config=service.serialize_config(),
                   tier=tiers.tier_status(g.current_user.makh))


@loyalty_bp.route('/api/loyalty/me/transactions')
@customer_required
def transactions():
    return jsonify(success=True, **paginate(LoyaltyPointTransaction.query.filter_by(makh=g.current_user.makh).order_by(LoyaltyPointTransaction.id.desc()), service.serialize_transaction))


@loyalty_bp.route('/api/loyalty/rewards')
@customer_required
def rewards():
    query = LoyaltyReward.query.filter_by(active=True)
    search = text_arg('search')
    if search:
        query = query.filter(LoyaltyReward.name.ilike(service.like_pattern(search), escape='!'))
    reward_type = choice_arg('reward_type', service.REWARD_FILTERS)
    if reward_type:
        query = query.filter(LoyaltyReward.reward_type.in_(service.VOUCHER_TYPES) if reward_type == 'voucher' else LoyaltyReward.reward_type == reward_type)
    if choice_arg('affordable_only', ('0', '1')) == '1':
        query = query.filter(LoyaltyReward.points_cost <= service.get_balance(g.current_user.makh)['available_points'])
    return jsonify(success=True, **paginate(query.order_by(LoyaltyReward.id), service.serialize_reward))


@loyalty_bp.route('/api/loyalty/my-rewards')
@customer_required
def my_rewards():
    # Ownership comes only from the token; one `now` keeps filter, total and labels consistent.
    now = datetime.utcnow()
    query = service.filter_redemptions(LoyaltyRewardRedemption.query.filter_by(makh=g.current_user.makh),
        choice_arg('status', service.REDEMPTION_GROUPS) or 'all', choice_arg('reward_type', service.REWARD_FILTERS),
        text_arg('search'), now, choice_arg('usable_for', service.TARGET_KINDS))
    return jsonify(success=True, **paginate(query.order_by(LoyaltyRewardRedemption.id.desc()),
        lambda row: service.serialize_redemption(row, now)))


@loyalty_bp.route('/api/loyalty/rewards/<int:reward_id>/redeem', methods=['POST'])
@customer_required
def redeem(reward_id):
    data = payload()
    reward = service.redeem_reward(g.current_user.makh, reward_id, request_key(data))
    db.session.commit()
    return jsonify(success=True, redemption=service.serialize_redemption(reward)), 201


def authorized_target(kind, record_id, mutate=False):
    if g.current_user_type == 'customer':
        if request.path.startswith('/api/admin/'):
            return None
        makh = g.current_user.makh
    else:
        if not g.current_user.trangthai or g.current_user.role not in ('admin', 'manager', 'letan', 'staff'):
            return None
        if kind == 'package_purchase' and g.current_user.role == 'staff':
            return None
        makh = None
    if mutate:
        return service.lock_target(kind, record_id, makh)
    model = HoaDon if kind == 'service_invoice' else GoiDichVuPurchase
    column = model.mahd if kind == 'service_invoice' else model.id
    query = model.query.filter(column == record_id)
    if makh is not None:
        query = query.filter_by(makh=makh)
    return query.first()


def target_state(target):
    return (service.calculate_point_discount(target, 0) | service.payment_summary(target) |
            dict(wallet=service.get_balance(target.makh), config=service.serialize_config()))


@loyalty_bp.route('/api/admin/invoices/<int:record_id>/loyalty', methods=['GET', 'POST', 'DELETE'])
@loyalty_bp.route('/api/payment/invoices/<int:record_id>/loyalty', methods=['GET', 'POST', 'DELETE'])
@loyalty_bp.route('/api/admin/packages/purchases/<int:record_id>/loyalty', methods=['GET', 'POST', 'DELETE'])
@loyalty_bp.route('/api/packages/purchases/<int:record_id>/loyalty', methods=['GET', 'POST', 'DELETE'])
@login_required
def target_loyalty(record_id):
    kind = 'package_purchase' if '/packages/' in request.path else 'service_invoice'
    target = authorized_target(kind, record_id, request.method != 'GET')
    if target is None:
        return jsonify(success=False, msg='Không có quyền hoặc không tìm thấy thanh toán'), 403
    if request.method == 'POST':
        service.reserve_points(target, payload().get('points'))
    elif request.method == 'DELETE':
        service.release_points(target)
    state = target_state(target)
    if request.method != 'GET':
        db.session.commit()
    return jsonify(success=True, **state)


@loyalty_bp.route('/api/admin/invoices/<int:record_id>/loyalty/preview', methods=['POST'])
@loyalty_bp.route('/api/payment/invoices/<int:record_id>/loyalty/preview', methods=['POST'])
@loyalty_bp.route('/api/admin/packages/purchases/<int:record_id>/loyalty/preview', methods=['POST'])
@loyalty_bp.route('/api/packages/purchases/<int:record_id>/loyalty/preview', methods=['POST'])
@login_required
def preview(record_id):
    kind = 'package_purchase' if '/packages/' in request.path else 'service_invoice'
    target = authorized_target(kind, record_id)
    if target is None:
        return jsonify(success=False, msg='Không có quyền hoặc không tìm thấy thanh toán'), 403
    service.require_unpaid(target)
    return jsonify(success=True, **service.calculate_point_discount(target, payload().get('points')))


@loyalty_bp.route('/api/admin/invoices/<int:record_id>/reward', methods=['POST', 'DELETE'])
@loyalty_bp.route('/api/payment/invoices/<int:record_id>/reward', methods=['POST', 'DELETE'])
@loyalty_bp.route('/api/admin/packages/purchases/<int:record_id>/reward', methods=['POST', 'DELETE'])
@loyalty_bp.route('/api/packages/purchases/<int:record_id>/reward', methods=['POST', 'DELETE'])
@login_required
def target_reward(record_id):
    kind = 'package_purchase' if '/packages/' in request.path else 'service_invoice'
    target = authorized_target(kind, record_id, True)
    if target is None:
        return jsonify(success=False, msg='Không có quyền hoặc không tìm thấy thanh toán'), 403
    if request.method == 'POST':
        service.apply_reward(target, service.integer(payload().get('redemption_id'), 1))
    else:
        service.release_reward(target)
    state = target_state(target)
    db.session.commit()
    return jsonify(success=True, **state)


@loyalty_bp.route('/api/admin/invoices/<int:record_id>/pay-points', methods=['POST'])
@loyalty_bp.route('/api/payment/invoices/<int:record_id>/pay-points', methods=['POST'])
@loyalty_bp.route('/api/admin/packages/purchases/<int:record_id>/pay-points', methods=['POST'])
@loyalty_bp.route('/api/packages/purchases/<int:record_id>/pay-points', methods=['POST'])
@login_required
def pay_points(record_id):
    kind = 'package_purchase' if '/packages/' in request.path else 'service_invoice'
    target = authorized_target(kind, record_id, True)
    if target is None:
        return jsonify(success=False, msg='Không có quyền hoặc không tìm thấy thanh toán'), 403
    if service.is_paid(target):
        return jsonify(success=True, **service.payment_summary(target))
    service.require_unpaid(target)
    if service.payable(target) != 0 or not (target.loyalty_discount or target.reward_discount):
        raise service.LoyaltyError('Thanh toán bằng điểm yêu cầu số tiền còn lại bằng 0')
    if kind == 'service_invoice':
        from ..services.payment_webhook_service import claim_invoice_payment
        if not claim_invoice_payment(record_id):
            raise service.LoyaltyError('Hóa đơn đã thay đổi')
        target.trangthai = 'Đã thanh toán'
        db.session.add(ThanhToan(mahd=record_id, sotien=0, phuongthuc='Điểm thưởng'))
        service.finalize_payment(target)
    else:
        from ..services.package_service import confirm_purchase
        confirm_purchase(record_id, 0, method='points', staff_id=g.current_user.manv if g.current_user_type == 'staff' else None)
    db.session.commit()
    return jsonify(success=True, **service.payment_summary(target))

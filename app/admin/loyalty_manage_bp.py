from datetime import datetime
from flask import Blueprint, jsonify, request, g, render_template
from sqlalchemy import func, or_
from ..extensions import db
from ..decorators import roles_required
from ..models import KhachHang, NhanVien, LoyaltyWallet, LoyaltyPointTransaction, LoyaltyReward, LoyaltyRewardRedemption
from ..services import loyalty_service as service
from ..services import loyalty_tier_service as tiers
from ..routes.loyalty_bp import paginate, payload, request_key, validation, conflict, choice_arg, text_arg
from sqlalchemy.exc import IntegrityError

admin_loyalty_bp = Blueprint('admin_loyalty', __name__)
admin_loyalty_bp.register_error_handler(service.LoyaltyError, validation)
admin_loyalty_bp.register_error_handler(IntegrityError, conflict)


def manager():
    if not g.current_user.trangthai:
        raise service.LoyaltyError('Tài khoản đã ngừng hoạt động')


@admin_loyalty_bp.route('/admin/loyalty')
def page():
    return render_template('admin/loyalty.html')


@admin_loyalty_bp.route('/api/admin/loyalty/config', methods=['GET', 'PUT'])
@roles_required('admin', 'manager')
def config():
    manager()
    if request.method == 'PUT':
        service.update_config(payload())
        db.session.commit()
    return jsonify(success=True, config=service.serialize_config())


@admin_loyalty_bp.route('/api/admin/loyalty/tiers', methods=['GET', 'PUT'])
@roles_required('admin', 'manager')
def tier_policy():
    manager()
    if request.method == 'PUT':
        tiers.update_policy(payload())
        db.session.commit()
    return jsonify(success=True, policy=tiers.serialize_policy())


@admin_loyalty_bp.route('/api/admin/loyalty/overview')
@roles_required('admin', 'manager')
def overview():
    manager()
    totals = db.session.query(func.count(LoyaltyWallet.id), func.sum(LoyaltyWallet.available_points),
        func.sum(LoyaltyWallet.reserved_points), func.sum(LoyaltyWallet.lifetime_earned), func.sum(LoyaltyWallet.lifetime_redeemed)).one()
    return jsonify(success=True, overview=dict(zip(('wallets', 'available_points', 'reserved_points', 'lifetime_earned', 'lifetime_redeemed'), [v or 0 for v in totals])))


@admin_loyalty_bp.route('/api/admin/loyalty/customers')
@roles_required('admin', 'manager')
def customers():
    manager()
    query = KhachHang.query
    term = request.args.get('search', '').strip()
    if term:
        query = query.filter(or_(KhachHang.hoten.ilike(f'%{term}%'), KhachHang.sdt.ilike(f'%{term}%'), KhachHang.email.ilike(f'%{term}%')))
    return jsonify(success=True, **paginate(query.order_by(KhachHang.makh),
        lambda customer: dict(makh=customer.makh, hoten=customer.hoten, sdt=customer.sdt, email=customer.email, **service.get_balance(customer.makh))))


@admin_loyalty_bp.route('/api/admin/loyalty/customers/<int:makh>')
@roles_required('admin', 'manager')
def customer_detail(makh):
    manager()
    customer = db.session.get(KhachHang, makh)
    if not customer:
        return jsonify(success=False, msg='Không tìm thấy khách hàng'), 404
    return jsonify(success=True, customer=dict(makh=makh, hoten=customer.hoten, sdt=customer.sdt, email=customer.email),
        wallet=service.get_balance(makh), tier=tiers.tier_status(makh), **paginate(LoyaltyPointTransaction.query.filter_by(makh=makh).order_by(LoyaltyPointTransaction.id.desc()), service.serialize_transaction))


@admin_loyalty_bp.route('/api/admin/loyalty/customers/<int:makh>/adjust', methods=['POST'])
@roles_required('admin', 'manager')
def adjust(makh):
    manager()
    data = payload()
    transaction = service.admin_adjust_points(makh, data.get('points_delta'), data.get('reason'), g.current_user.manv, request_key(data))
    db.session.commit()
    return jsonify(success=True, transaction=service.serialize_transaction(transaction), wallet=service.get_balance(makh))


@admin_loyalty_bp.route('/api/admin/loyalty/transactions')
@roles_required('admin', 'manager')
def transactions():
    manager()
    query = LoyaltyPointTransaction.query
    if request.args.get('makh'):
        query = query.filter_by(makh=request.args.get('makh', type=int))
    return jsonify(success=True, **paginate(query.order_by(LoyaltyPointTransaction.id.desc()), service.serialize_transaction))


@admin_loyalty_bp.route('/api/admin/loyalty/rewards', methods=['GET', 'POST'])
@roles_required('admin', 'manager')
def rewards():
    manager()
    if request.method == 'POST':
        reward = service.save_reward(payload())
        db.session.commit()
        return jsonify(success=True, reward=service.serialize_reward(reward)), 201
    return jsonify(success=True, **paginate(LoyaltyReward.query.order_by(LoyaltyReward.id.desc()), service.serialize_reward))


@admin_loyalty_bp.route('/api/admin/loyalty/rewards/<int:reward_id>', methods=['GET', 'PUT', 'DELETE'])
@roles_required('admin', 'manager')
def reward_detail(reward_id):
    manager()
    reward = LoyaltyReward.query.filter_by(id=reward_id).with_for_update().first()
    if not reward:
        return jsonify(success=False, msg='Không tìm thấy quà'), 404
    if request.method == 'PUT':
        service.save_reward(payload(), reward)
    elif request.method == 'DELETE':
        reward.active = False  # Preserve historical redemptions and audit.
    if request.method != 'GET':
        db.session.commit()
    return jsonify(success=True, reward=service.serialize_reward(reward))


# Front desk (letan) may look up and hand over gifts; catalog, rules and points stay admin/manager only.
GIFT_DESK_ROLES = ('admin', 'manager', 'letan')


def desk_query():
    return db.session.query(LoyaltyRewardRedemption, KhachHang, NhanVien.hoten).join(
        KhachHang, KhachHang.makh == LoyaltyRewardRedemption.makh).outerjoin(
        NhanVien, NhanVien.manv == LoyaltyRewardRedemption.fulfilled_by_staff)


def desk_redemption(row, now=None):
    redemption, customer, staff_name = row
    return dict(service.serialize_redemption(redemption, now), customer=dict(makh=customer.makh, hoten=customer.hoten,
        sdt=customer.sdt, email=customer.email), fulfilled_by_name=staff_name)


@admin_loyalty_bp.route('/api/admin/loyalty/redemptions')
@roles_required(*GIFT_DESK_ROLES)
def redemptions():
    manager()
    now = datetime.utcnow()
    query = service.filter_redemptions(desk_query(), choice_arg('status', service.REDEMPTION_GROUPS) or 'all',
        choice_arg('reward_type', service.REWARD_FILTERS), now=now)
    if request.args.get('makh'):
        query = query.filter(LoyaltyRewardRedemption.makh == request.args.get('makh', type=int))
    search = text_arg('search')
    if search:
        pattern = service.like_pattern(search)
        query = query.filter(or_(*(column.ilike(pattern, escape='!') for column in (
            LoyaltyRewardRedemption.code, LoyaltyRewardRedemption.reward_snapshot_json['name'].as_string(),
            KhachHang.hoten, KhachHang.sdt, KhachHang.email))))
    return jsonify(success=True, **paginate(query.order_by(LoyaltyRewardRedemption.id.desc()), lambda row: desk_redemption(row, now)))


@admin_loyalty_bp.route('/api/admin/loyalty/redemptions/<int:redemption_id>/fulfill', methods=['POST'])
@roles_required(*GIFT_DESK_ROLES)
def fulfill(redemption_id):
    manager()
    redemption, changed = service.fulfill_reward(redemption_id, g.current_user.manv)
    db.session.commit()
    row = desk_query().filter(LoyaltyRewardRedemption.id == redemption.id).one()
    return jsonify(success=True, already_fulfilled=not changed, redemption=desk_redemption(row))


@admin_loyalty_bp.route('/api/admin/loyalty/customers/<int:makh>/vouchers')
@roles_required('admin', 'manager', 'letan', 'staff')
def payment_vouchers(makh):
    manager()
    now = datetime.utcnow()
    usable_for = choice_arg('usable_for', service.TARGET_KINDS)
    query = service.filter_redemptions(LoyaltyRewardRedemption.query.filter_by(makh=makh), 'usable', now=now, usable_for=usable_for)
    return jsonify(success=True, **paginate(query.order_by(LoyaltyRewardRedemption.id), lambda row: service.serialize_redemption(row, now)))

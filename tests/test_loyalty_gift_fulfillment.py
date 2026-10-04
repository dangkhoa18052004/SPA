"""Physical gift handover: front-desk permissions, lookup, expiry and idempotent fulfillment."""
from datetime import datetime, timedelta

import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import ChucVu, KhachHang, LoyaltyRewardRedemption, NhanVien
from app.services import loyalty_service as loyalty
from test_loyalty_service import fund


@pytest.fixture
def staff_headers(app):
    """Bearer headers for an active employee of the given role (and an inactive letan)."""
    created = {}

    def factory(role, active=True):
        key = (role, active)
        if key not in created:
            with app.app_context():
                position = ChucVu.query.first()
                employee = NhanVien(hoten=f'NV {role}', sdt=f'09111{len(created):05d}', diachi='Bin Spa', email=f'{role}{len(created)}@example.com',
                                    taikhoan=f'{role}_{len(created)}', matkhau=generate_password_hash('password'), macv=position.macv,
                                    role=role, trangthai=active)
                db.session.add(employee)
                db.session.commit()
                created[key] = (employee.manv, {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{employee.manv}')})
        return created[key]
    return factory


@pytest.fixture
def gifts(app):
    """Redeem gifts/vouchers for the test customer and return their redemption ids."""
    with app.app_context():
        fund(app, 1000)
        gift = loyalty.save_reward(dict(name='Khăn tắm Bin Spa', reward_type='physical_gift', points_cost=50, validity_days=30))
        voucher = loyalty.save_reward(dict(name='Voucher 50k', reward_type='voucher_amount', points_cost=50, reward_value=50000))
        makh = app.config['TEST_CUSTOMER_ID']
        ids = {name: loyalty.redeem_reward(makh, gift.id, name).id for name in ('admin', 'manager', 'letan', 'spare', 'expired')}
        ids['voucher'] = loyalty.redeem_reward(makh, voucher.id, 'voucher').id
        db.session.get(LoyaltyRewardRedemption, ids['expired']).expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    return ids


def fulfill(client, headers, rid):
    return client.post(f'/api/admin/loyalty/redemptions/{rid}/fulfill', headers=headers, json={})


def row(app, rid):
    with app.app_context():
        return db.session.get(LoyaltyRewardRedemption, rid)


@pytest.mark.parametrize('role', ['admin', 'manager', 'letan'])
def test_admin_manager_and_letan_can_fulfill(app, client, staff_headers, gifts, role):
    manv, headers = staff_headers(role)
    result = fulfill(client, headers, gifts[role])
    assert result.status_code == 200, result.json
    body = result.json['redemption']
    assert result.json['already_fulfilled'] is False and body['status'] == 'fulfilled'
    assert body['fulfilled_by_staff'] == manv and body['fulfilled_by_name'] == f'NV {role}' and body['fulfilled_at']
    assert body['customer']['hoten'] == 'Khách hàng Test'
    saved = row(app, gifts[role])
    assert (saved.status, saved.fulfilled_by_staff) == ('fulfilled', manv) and saved.fulfilled_at is not None


def test_customer_staff_and_inactive_letan_are_rejected(app, client, staff_headers, customer_auth_headers, staff_auth_headers, gifts):
    _, inactive = staff_headers('letan', active=False)
    for headers in (customer_auth_headers, staff_auth_headers):
        assert fulfill(client, headers, gifts['spare']).status_code == 403
        assert client.get('/api/admin/loyalty/redemptions', headers=headers).status_code == 403
    assert fulfill(client, inactive, gifts['spare']).status_code in (400, 401, 403)
    assert row(app, gifts['spare']).status == 'available' and row(app, gifts['spare']).fulfilled_at is None


def test_letan_gets_only_the_gift_desk(client, staff_headers, gifts):
    _, headers = staff_headers('letan')
    assert client.get('/api/admin/loyalty/redemptions', headers=headers).status_code == 200
    for method, path in (('get', '/api/admin/loyalty/config'), ('put', '/api/admin/loyalty/config'), ('get', '/api/admin/loyalty/overview'),
                         ('get', '/api/admin/loyalty/customers'), ('get', '/api/admin/loyalty/transactions'),
                         ('get', '/api/admin/loyalty/rewards'), ('post', '/api/admin/loyalty/rewards'),
                         ('put', '/api/admin/loyalty/rewards/1'), ('delete', '/api/admin/loyalty/rewards/1'),
                         ('post', '/api/admin/loyalty/customers/1/adjust')):
        assert getattr(client, method)(path, headers=headers, json={}).status_code == 403, path


def test_expired_and_voucher_cannot_be_fulfilled(app, client, staff_headers, gifts):
    _, headers = staff_headers('letan')
    expired = fulfill(client, headers, gifts['expired'])
    assert expired.status_code == 400 and expired.json['msg'] == 'Quà đã hết hạn, không thể bàn giao'
    assert row(app, gifts['expired']).status == 'available' and row(app, gifts['expired']).fulfilled_at is None
    voucher = fulfill(client, headers, gifts['voucher'])
    assert voucher.status_code == 400 and voucher.json['msg'] == 'Đây là voucher thanh toán, không bàn giao tại quầy'
    assert fulfill(client, headers, 999999).status_code == 400


def test_double_fulfill_has_no_second_side_effect(app, client, staff_headers, gifts):
    first_id, first = staff_headers('letan')
    _, second = staff_headers('manager')
    assert fulfill(client, first, gifts['spare']).status_code == 200
    before = row(app, gifts['spare'])
    for headers in (first, second):
        again = fulfill(client, headers, gifts['spare'])
        assert again.status_code == 200 and again.json['already_fulfilled'] is True
        assert again.json['redemption']['fulfilled_by_staff'] == first_id
    after = row(app, gifts['spare'])
    assert (after.status, after.fulfilled_at, after.fulfilled_by_staff) == ('fulfilled', before.fulfilled_at, first_id)


def test_desk_search_and_filters(app, client, staff_headers, gifts):
    _, headers = staff_headers('letan')
    with app.app_context():
        other = KhachHang(hoten='Trần Thị Mai', sdt='0988777666', email='mai@example.com', taikhoan='mai', matkhau='x', trangthai='active')
        db.session.add(other)
        db.session.commit()
        loyalty.admin_adjust_points(other.makh, 100, 'Quà', app.config['TEST_ADMIN_ID'], 'mai')
        reward = loyalty.save_reward(dict(name='Nến thơm', reward_type='physical_gift', points_cost=50))
        mai = loyalty.redeem_reward(other.makh, reward.id, 'mai-gift')
        db.session.commit()
        mai_id, mai_code = mai.id, mai.code
    fulfill(client, headers, gifts['admin'])
    get = lambda query: client.get('/api/admin/loyalty/redemptions?per_page=100&' + query, headers=headers).json
    ids = lambda data: {r['id'] for r in data['items']}
    assert ids(get(f'search={mai_code}')) == {mai_id}
    assert ids(get(f'search={mai_code.lower()}')) == {mai_id}
    for term in ('Trần Thị', '0988777', 'mai@example', 'Nến'):
        assert ids(get('search=' + term)) == {mai_id}, term
    assert ids(get('search=customer@example.com')) == {gifts[k] for k in ('admin', 'manager', 'letan', 'spare', 'expired', 'voucher')}
    assert ids(get('status=pickup')) == {gifts[k] for k in ('manager', 'letan', 'spare')} | {mai_id}
    assert ids(get('status=done')) == {gifts['admin']} and ids(get('status=closed')) == {gifts['expired']}
    assert ids(get('reward_type=voucher_amount')) == {gifts['voucher']}
    item = get(f'search={mai_code}')['items'][0]
    assert item['customer'] == dict(makh=item['makh'], hoten='Trần Thị Mai', sdt='0988777666', email='mai@example.com')
    assert (item['status'], item['points_spent'], item['fulfilled_by_name']) == ('available', 50, None) and item['redeemed_at']
    assert get('search=100%25_')['total'] == 0
    assert client.get('/api/admin/loyalty/redemptions?status=bogus', headers=headers).status_code == 400


def test_physical_gift_never_reaches_payment(app, client, customer_auth_headers, create_invoice, gifts):
    invoice = create_invoice(500000)
    result = client.post(f'/api/payment/invoices/{invoice}/reward', headers=customer_auth_headers, json={'redemption_id': gifts['spare']})
    assert result.status_code == 400 and result.json['msg'] == 'Ưu đãi này không phải voucher giảm tiền'
    usable = client.get('/api/loyalty/my-rewards?status=usable&usable_for=service_invoice', headers=customer_auth_headers).json
    assert {r['id'] for r in usable['items']} == {gifts['voucher']}

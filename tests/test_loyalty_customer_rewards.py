"""Customer Đổi thưởng / Ưu đãi của tôi: catalog filters, effective status groups, ownership."""
from datetime import datetime, timedelta
import pytest
from app.extensions import db
from app.models import KhachHang, LoyaltyReward, LoyaltyRewardRedemption, LoyaltyWallet
from app.services import loyalty_service as loyalty
from test_loyalty_service import fund, invariant


def reward(client, headers, **data):
    data = dict(dict(name='Voucher', reward_type='voucher_amount', points_cost=100, reward_value=50000), **data)
    result = client.post('/api/admin/loyalty/rewards', headers=headers, json=data)
    assert result.status_code == 201, result.json
    return result.json['reward']['id']


def redeem(client, headers, rid, key):
    return client.post(f'/api/loyalty/rewards/{rid}/redeem', headers=headers, json={'idempotency_key': key})


@pytest.fixture
def funded(app):
    with app.app_context():
        fund(app, 300)
        db.session.commit()


def test_catalog_filters_apply_before_pagination(client, admin_auth_headers, customer_auth_headers, funded):
    for i in range(25):
        reward(client, admin_auth_headers, name=f'Voucher {i}', points_cost=100 + i * 20)
    gift = reward(client, admin_auth_headers, name='Khăn 100%_đặc biệt', reward_type='physical_gift', points_cost=50, reward_value=0)
    reward(client, admin_auth_headers, name='Ngừng đổi', active=False)
    get = lambda query: client.get('/api/loyalty/rewards?' + query, headers=customer_auth_headers).json
    assert get('per_page=10')['total'] == 26
    page = get('reward_type=physical_gift&per_page=1&page=1')
    assert page['total'] == 1 and page['items'][0]['id'] == gift
    affordable = get('affordable_only=1&per_page=5&page=2')
    assert affordable['total'] == 12 and affordable['pages'] == 3
    assert all(r['points_cost'] <= 300 for r in get('affordable_only=1&per_page=100')['items'])
    assert get('search=100%25_&per_page=100')['total'] == 1
    assert get('search=voucher 2&per_page=100')['total'] == 6  # 2, 20..24
    for bad in ('reward_type=coupon', 'affordable_only=yes', 'search=' + 'x' * 101, 'page=0'):
        assert client.get('/api/loyalty/rewards?' + bad, headers=customer_auth_headers).status_code == 400


def test_my_rewards_groups_use_effective_status(app, client, admin_auth_headers, customer_auth_headers, funded, create_invoice):
    voucher = reward(client, admin_auth_headers, name='Voucher 50K', points_cost=50)
    gift = reward(client, admin_auth_headers, name='Quà tặng', reward_type='physical_gift', points_cost=50, reward_value=0)
    ids = {key: redeem(client, customer_auth_headers, rid, key).json['redemption']['id'] for key, rid in
           (('usable', voucher), ('expired', voucher), ('applied', voucher), ('pickup', gift), ('received', gift))}
    with app.app_context():
        # DB row stays 'available'; only the derived status says expired.
        db.session.get(LoyaltyRewardRedemption, ids['expired']).expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    invoice = create_invoice(500000)
    assert client.post(f'/api/payment/invoices/{invoice}/reward', headers=customer_auth_headers, json={'redemption_id': ids['applied']}).status_code == 200
    assert client.post(f"/api/admin/loyalty/redemptions/{ids['received']}/fulfill", headers=admin_auth_headers, json={}).status_code == 200
    get = lambda query: client.get('/api/loyalty/my-rewards?' + query, headers=customer_auth_headers).json
    expected = dict(usable=[ids['usable']], pickup=[ids['pickup']], applied=[ids['applied']],
                    done=[ids['received']], closed=[ids['expired']])
    for group, rows in expected.items():
        data = get(f'status={group}&per_page=1')
        assert data['total'] == len(rows) and [r['id'] for r in data['items']] == rows, group
    closed = get('status=closed')['items'][0]
    assert closed['status'] == 'expired'
    with app.app_context():
        assert db.session.get(LoyaltyRewardRedemption, ids['expired']).status == 'available'
    assert get('per_page=2')['total'] == 5 and get('per_page=2')['pages'] == 3
    assert get('reward_type=physical_gift')['total'] == 2
    code = get('status=pickup')['items'][0]['code']
    assert [r['id'] for r in get('search=' + code[-6:].lower())['items']] == [ids['pickup']]
    assert get('search=quà')['total'] == 2
    # Expired vouchers are never applicable, even though the row is still 'available'.
    other = create_invoice(500000)
    assert client.post(f'/api/payment/invoices/{other}/reward', headers=customer_auth_headers, json={'redemption_id': ids['expired']}).status_code == 400
    for bad in ('status=reserved', 'reward_type=x', 'search=' + 'y' * 101):
        assert client.get('/api/loyalty/my-rewards?' + bad, headers=customer_auth_headers).status_code == 400


def test_snapshot_survives_catalog_edits_and_retry_is_idempotent(app, client, admin_auth_headers, customer_auth_headers, funded):
    rid = reward(client, admin_auth_headers, name='Voucher gốc', points_cost=100, reward_value=50000, stock=2, validity_days=30)
    first = [redeem(client, customer_auth_headers, rid, 'retry-same') for _ in range(3)]
    assert {r.status_code for r in first} == {201} and len({r.json['redemption']['id'] for r in first}) == 1
    assert client.put(f'/api/admin/loyalty/rewards/{rid}', headers=admin_auth_headers,
                      json=dict(name='Voucher mới', reward_value=10000, validity_days=1, active=False)).status_code == 200
    # Same key after deactivation still returns the original result; a new key is refused.
    assert redeem(client, customer_auth_headers, rid, 'retry-same').status_code == 201
    assert redeem(client, customer_auth_headers, rid, 'new-click').status_code == 400
    item = client.get('/api/loyalty/my-rewards', headers=customer_auth_headers).json['items'][0]
    assert item['reward']['name'] == 'Voucher gốc' and item['reward']['reward_value'] == '50000.00'
    assert item['status'] == 'available' and item['points_spent'] == 100
    with app.app_context():
        wallet = LoyaltyWallet.query.one()
        assert wallet.available_points == 200 and db.session.get(LoyaltyReward, rid).stock == 1
        invariant(app)


def test_redeem_rejections_leave_balance_and_stock(app, client, admin_auth_headers, customer_auth_headers, funded):
    expensive = reward(client, admin_auth_headers, points_cost=301)
    empty = reward(client, admin_auth_headers, stock=0)
    for rid in (expensive, empty, 9999):
        result = redeem(client, customer_auth_headers, rid, f'no-{rid}')
        assert result.status_code == 400 and result.json['msg']
    assert client.get('/api/loyalty/me', headers=customer_auth_headers).json['wallet']['available_points'] == 300
    with app.app_context():
        assert LoyaltyRewardRedemption.query.count() == 0 and db.session.get(LoyaltyReward, empty).stock == 0


def test_customer_cannot_read_or_use_another_customers_rewards(app, client, admin_auth_headers, customer_auth_headers, funded, create_invoice):
    rid = reward(client, admin_auth_headers, points_cost=50)
    with app.app_context():
        other = KhachHang(hoten='Other', taikhoan='other-rewards', matkhau='hash')
        db.session.add(other)
        db.session.flush()
        loyalty.admin_adjust_points(other.makh, 100, 'Other', app.config['TEST_ADMIN_ID'], 'other')
        foreign = loyalty.redeem_reward(other.makh, rid, 'other-key')
        db.session.commit()
        foreign_id, other_id, foreign_code = foreign.id, other.makh, foreign.code
    data = client.get(f'/api/loyalty/my-rewards?makh={other_id}&search={foreign_code}', headers=customer_auth_headers).json
    assert data['total'] == 0
    invoice = create_invoice(500000)
    assert client.post(f'/api/payment/invoices/{invoice}/reward', headers=customer_auth_headers, json={'redemption_id': foreign_id}).status_code == 400
    with app.app_context():
        assert db.session.get(LoyaltyRewardRedemption, foreign_id).status == 'available'

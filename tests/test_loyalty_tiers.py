"""F04: hạng thành viên/tiến độ tính từ ledger; đổi điểm không làm tụt hạng."""
import pytest

from app.extensions import db
from app.models import LoyaltyPointTransaction, LoyaltyWallet
from app.services import loyalty_service as loyalty, loyalty_tier_service as tiers


def _post(app, makh, delta, kind, key):
    with app.app_context():
        wallet = loyalty.get_wallet(makh, lock=True)
        loyalty.post(wallet, delta, kind, 'service_invoice', 1, key, 'HD1 · test')
        db.session.commit()


def _status(app, makh):
    with app.app_context():
        return tiers.tier_status(makh)


@pytest.mark.parametrize('points,expected,next_code,to_next', [
    (0, 'member', 'silver', 200), (199, 'member', 'silver', 1), (200, 'silver', 'gold', 300),
    (500, 'gold', 'diamond', 500), (1000, 'diamond', None, 0), (5000, 'diamond', None, 0)])
def test_default_thresholds(app, points, expected, next_code, to_next):
    makh = app.config['TEST_CUSTOMER_ID']
    if points:
        _post(app, makh, points, 'earn', f'earn-{points}')
    status = _status(app, makh)
    assert status['tier']['code'] == expected
    assert (status['next_tier'] or {}).get('code') == next_code
    assert status['points_to_next'] == to_next


def test_progress_percent_between_tiers(app):
    makh = app.config['TEST_CUSTOMER_ID']
    _post(app, makh, 350, 'earn', 'e1')
    status = _status(app, makh)
    assert status['tier']['code'] == 'silver' and status['progress_percent'] == 50.0


def test_redeem_does_not_reduce_tier_but_refund_of_earn_does(app):
    makh = app.config['TEST_CUSTOMER_ID']
    _post(app, makh, 600, 'earn', 'earn-a')
    _post(app, makh, -400, 'redeem', 'redeem-a')
    _post(app, makh, -100, 'reward_redeem', 'reward-a')
    status = _status(app, makh)
    assert status['qualifying_points'] == 600 and status['tier']['code'] == 'gold'
    # Hoàn lại điểm đã đổi (refund dương) không cộng thêm tiến độ.
    _post(app, makh, 400, 'refund', 'refund-redeem')
    assert _status(app, makh)['qualifying_points'] == 600
    # Hoàn tiền thu hồi điểm tích (refund âm) làm giảm tiến độ.
    _post(app, makh, -150, 'refund', 'refund-earn')
    status = _status(app, makh)
    assert status['qualifying_points'] == 450 and status['tier']['code'] == 'silver'
    # Ledger/available vẫn khớp: hạng không đụng tới số dư.
    with app.app_context():
        wallet = LoyaltyWallet.query.filter_by(makh=makh).one()
        ledger = db.session.query(db.func.sum(LoyaltyPointTransaction.points_delta)).filter_by(makh=makh).scalar()
        assert wallet.available_points + wallet.reserved_points == ledger


def test_manual_adjustments_follow_policy(app, client, admin_auth_headers):
    makh = app.config['TEST_CUSTOMER_ID']
    _post(app, makh, 150, 'earn', 'earn-b')
    _post(app, makh, 100, 'adjustment_add', 'adj-b')
    assert _status(app, makh)['qualifying_points'] == 150
    r = client.put('/api/admin/loyalty/tiers', headers=admin_auth_headers, json={'count_adjustments': True})
    assert r.status_code == 200, r.json
    status = _status(app, makh)
    assert status['qualifying_points'] == 250 and status['tier']['code'] == 'silver'


def test_custom_thresholds_validation(app, client, admin_auth_headers):
    bad = [
        [],
        [dict(code='a', name='A', min_points=10)],
        [dict(code='a', name='A', min_points=0), dict(code='b', name='B', min_points=0)],
        [dict(code='a', name='A', min_points=0), dict(code='a', name='B', min_points=5)],
        [dict(code='a', name='', min_points=0)],
        [dict(code='a', name='A', min_points=0), dict(code='b', name='B', min_points=-1)],
    ]
    for tiers_payload in bad:
        r = client.put('/api/admin/loyalty/tiers', headers=admin_auth_headers, json={'tiers': tiers_payload})
        assert r.status_code == 400, tiers_payload
    good = [dict(code='basic', name='Cơ bản', min_points=0), dict(code='vip', name='VIP', min_points=100)]
    r = client.put('/api/admin/loyalty/tiers', headers=admin_auth_headers, json={'tiers': good})
    assert r.status_code == 200 and r.json['policy']['tiers'] == good
    _post(app, app.config['TEST_CUSTOMER_ID'], 120, 'earn', 'earn-c')
    assert _status(app, app.config['TEST_CUSTOMER_ID'])['tier']['code'] == 'vip'


def test_customer_and_admin_endpoints_expose_tier(app, client, customer_auth_headers, admin_auth_headers, staff_auth_headers):
    makh = app.config['TEST_CUSTOMER_ID']
    _post(app, makh, 210, 'earn', 'earn-d')
    me = client.get('/api/loyalty/me', headers=customer_auth_headers).json
    assert me['tier']['tier']['name'] == 'Bạc' and me['tier']['next_tier']['name'] == 'Vàng'
    detail = client.get(f'/api/admin/loyalty/customers/{makh}', headers=admin_auth_headers).json
    assert detail['tier']['qualifying_points'] == 210
    assert client.put('/api/admin/loyalty/tiers', headers=staff_auth_headers, json={}).status_code == 403

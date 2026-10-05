"""Percentage vouchers: migration, validation, Decimal calculation, terms, payment flow and finalization."""
import json
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import HoaDon, LoyaltyPointTransaction, LoyaltyRewardRedemption, ThanhToan
from app.services import loyalty_service as loyalty
from test_loyalty_migration import migration_engine  # noqa: F401  (fixture)
from test_loyalty_payments import package_id  # noqa: F401  (fixture)
from test_loyalty_service import fund, invariant
from test_loyalty_voucher_terms import LEGACY_SNAPSHOT, load, seed_0011

SEPAY = {'Authorization': 'Apikey test-sepay-key'}


def test_migration_adds_percent_type_without_touching_existing_rewards(migration_engine):
    migration = load('20261004_0013_voucher_percent.py')
    assert migration.down_revision == '20261004_0012'
    with migration_engine.begin() as connection:
        seed_0011(connection)
        with Operations.context(MigrationContext.configure(connection)):
            load('20261004_0012_voucher_terms.py').upgrade()
            migration.upgrade()
        rows = connection.execute(text('SELECT id, reward_type, reward_value, apply_to, percentage_value, max_discount_amount '
                                       'FROM loyalty_reward ORDER BY id')).all()
        assert [(r[0], r[1], float(r[2]), r[3], r[4], r[5]) for r in rows] == [
            (1, 'voucher_amount', 50000.0, 'both', None, None), (2, 'physical_gift', 0.0, None, None, None)]
        snapshot = connection.execute(text('SELECT reward_snapshot_json FROM loyalty_reward_redemption')).scalar()
        assert (snapshot if isinstance(snapshot, dict) else json.loads(snapshot)) == LEGACY_SNAPSHOT
        # Explicit ids: the seed inserted ids 1-2 directly, so PostgreSQL's sequence was never advanced.
        ids = iter(range(100, 200))
        insert = lambda kind, value, rest: ('INSERT INTO loyalty_reward (id, name, description, reward_type, points_cost, reward_value, active, '
            f"apply_to, minimum_spend, percentage_value, max_discount_amount) VALUES ({next(ids)}, 'x', '', {kind}, 10, {value}, TRUE, {rest})")
        connection.execute(text(insert("'voucher_percent'", 0, "'both', 0, 10, 30000")))
        connection.execute(text(insert("'voucher_percent'", 0, "'service_invoice', 0, 100, NULL")))
        connection.execute(text(insert("'voucher_amount'", 50000, "'both', 0, NULL, NULL")))
        # Each row breaks exactly one rule; NULLs must fail too (a NULL CHECK result would otherwise pass).
        for kind, value, rest in (("'voucher_percent'", 0, "'both', 0, 0, NULL"), ("'voucher_percent'", 0, "'both', 0, 101, NULL"),
                                  ("'voucher_percent'", 0, "'both', 0, 10, 0"), ("'voucher_percent'", 0, "'both', 0, NULL, NULL"),
                                  ("'voucher_percent'", 0, "NULL, 0, 10, NULL"), ("'physical_gift'", 0, "NULL, NULL, 10, NULL"),
                                  ("'voucher_amount'", 50000, "'both', 0, 10, NULL"), ("'voucher_amount'", 50000, "NULL, 0, NULL, NULL"),
                                  ("'voucher_amount'", 0, "'both', 0, NULL, NULL"), ("'coupon'", 0, "'both', 0, NULL, NULL")):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text(insert(kind, value, rest)))
        with Operations.context(MigrationContext.configure(connection)), pytest.raises(RuntimeError, match='voucher_percent'):
            migration.downgrade()


def test_postgresql_sql_only_swaps_checks_and_single_head():
    output = StringIO()
    context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})
    with Operations.context(context):
        load('20261004_0013_voucher_percent.py').upgrade()
    sql = output.getvalue()
    assert 'ADD COLUMN percentage_value NUMERIC(5, 2)' in sql and 'ADD COLUMN max_discount_amount NUMERIC(12, 2)' in sql
    assert sql.count('DROP CONSTRAINT') == 2 and 'ck_loyalty_reward_percent' in sql and "'voucher_percent'" in sql
    assert 'DROP TABLE' not in sql and 'DROP COLUMN' not in sql and 'DELETE' not in sql and 'UPDATE' not in sql
    config = Config('migrations/alembic.ini')
    config.set_main_option('script_location', 'migrations')
    assert ScriptDirectory.from_config(config).get_heads() == ['20261005_0016']


@pytest.mark.parametrize('amount, snapshot, expected', [
    ('500000', dict(percentage_value='10.00'), '50000'),
    ('500000', dict(percentage_value='10.00', max_discount_amount='30000.00'), '30000'),
    ('500000', dict(percentage_value='10.00', max_discount_amount='80000.00'), '50000'),
    ('333333', dict(percentage_value='15.00'), '49999'),  # 49 999.95 rounds down to whole VND
    ('199999', dict(percentage_value='12.50'), '24999'),
    ('500000', dict(percentage_value='100.00'), '500000'),
])
def test_percent_discount_uses_decimal_and_caps(amount, snapshot, expected):
    result = loyalty.voucher_discount(dict(reward_type='voucher_percent', **snapshot), Decimal(amount))
    assert isinstance(result, Decimal) and result == Decimal(expected)
    assert loyalty.voucher_discount(dict(reward_type='voucher_amount', reward_value='600000.00'), Decimal(amount)) == Decimal(amount)


def create(client, headers, **data):
    body = dict(name='Giảm 10%', reward_type='voucher_percent', points_cost=300, percentage_value=10, max_discount_amount=100000,
                minimum_spend=300000, apply_to='both')
    body.update(data)
    return client.post('/api/admin/loyalty/rewards', headers=headers, json=body)


def test_admin_creates_and_validates_percent_voucher(client, admin_auth_headers):
    reward = create(client, admin_auth_headers, validity_days=30, stock=10).json['reward']
    assert (reward['reward_type'], reward['percentage_value'], reward['max_discount_amount'], reward['reward_value']) == (
        'voucher_percent', '10.00', '100000.00', '0.00')
    assert (reward['minimum_spend'], reward['apply_to'], reward['validity_days'], reward['stock']) == ('300000.00', 'both', 30, 10)
    assert create(client, admin_auth_headers, max_discount_amount=None).json['reward']['max_discount_amount'] is None
    assert create(client, admin_auth_headers, max_discount_amount='', percentage_value='12.5').json['reward']['percentage_value'] == '12.50'
    for data, message in ((dict(percentage_value=0), 'Phần trăm giảm'), (dict(percentage_value=101), 'Phần trăm giảm'),
                          (dict(percentage_value='abc'), 'Phần trăm giảm'), (dict(percentage_value=None), 'Phần trăm giảm'),
                          (dict(percentage_value=10.123), 'Phần trăm giảm'), (dict(max_discount_amount=0), 'Giảm tối đa'),
                          (dict(max_discount_amount=-5), 'Giảm tối đa'), (dict(minimum_spend=-1), 'Đơn tối thiểu'),
                          (dict(apply_to='all'), 'Phạm vi áp dụng')):
        response = create(client, admin_auth_headers, **data)
        assert response.status_code == 400 and message in response.json['msg'], (data, response.json)
    # Switching type clears the other type's fields.
    fixed = client.put(f"/api/admin/loyalty/rewards/{reward['id']}", headers=admin_auth_headers,
                       json=dict(reward_type='voucher_amount', reward_value=50000)).json['reward']
    assert (fixed['percentage_value'], fixed['max_discount_amount'], fixed['reward_value']) == (None, None, '50000.00')
    back = client.put(f"/api/admin/loyalty/rewards/{reward['id']}", headers=admin_auth_headers,
                      json=dict(reward_type='voucher_percent', percentage_value=20)).json['reward']
    assert (back['percentage_value'], back['reward_value']) == ('20.00', '0.00')


@pytest.fixture
def percent_voucher(app):
    with app.app_context():
        fund(app, 1000)
        db.session.commit()
    app.config.update(VIETQR_BANK_ID='970407', VIETQR_ACCOUNT_NO='1234', VIETQR_ACCOUNT_NAME='BIN SPA')
    keys = iter(range(100))

    def factory(**terms):
        with app.app_context():
            data = dict(name='Giảm 10%', reward_type='voucher_percent', points_cost=50, percentage_value=10)
            data.update(terms)
            reward = loyalty.save_reward(data)
            redemption = loyalty.redeem_reward(app.config['TEST_CUSTOMER_ID'], reward.id, f'p{next(keys)}')
            db.session.commit()
            return redemption.id
    return factory


def apply(client, headers, invoice, rid):
    return client.post(f'/api/payment/invoices/{invoice}/reward', headers=headers, json={'redemption_id': rid})


def test_snapshot_keeps_percent_terms(app, client, admin_auth_headers, customer_auth_headers, percent_voucher):
    rid = percent_voucher(max_discount_amount=30000, minimum_spend=300000, apply_to='service_invoice')
    with app.app_context():
        reward_id = db.session.get(LoyaltyRewardRedemption, rid).reward_id
    client.put(f'/api/admin/loyalty/rewards/{reward_id}', headers=admin_auth_headers, json=dict(percentage_value=50, max_discount_amount=None))
    offer = client.get('/api/loyalty/my-rewards', headers=customer_auth_headers).json['items'][0]['reward']
    assert {k: offer[k] for k in ('reward_type', 'percentage_value', 'max_discount_amount', 'minimum_spend', 'apply_to')} == dict(
        reward_type='voucher_percent', percentage_value='10.00', max_discount_amount='30000.00', minimum_spend='300000.00', apply_to='service_invoice')


def test_apply_percent_without_and_with_cap(app, client, customer_auth_headers, create_invoice, percent_voucher):
    plain, capped = percent_voucher(), percent_voucher(max_discount_amount=30000)
    first, second = create_invoice(500000), create_invoice(500000)
    result = apply(client, customer_auth_headers, first, plain)
    assert result.status_code == 200 and Decimal(result.json['reward_discount']) == 50000 and Decimal(result.json['payable_amount']) == 450000
    result = apply(client, customer_auth_headers, second, capped)
    assert Decimal(result.json['reward_discount']) == 30000 and Decimal(result.json['payable_amount']) == 470000
    with app.app_context():
        assert db.session.get(LoyaltyRewardRedemption, capped).status == 'reserved'


def test_percent_reuses_minimum_spend_apply_to_and_expiry(app, client, customer_auth_headers, create_invoice, percent_voucher, package_id):
    short = apply(client, customer_auth_headers, create_invoice(250000), percent_voucher(minimum_spend=300000))
    assert short.status_code == 400 and short.json['msg'] == 'Hóa đơn chưa đạt giá trị tối thiểu 300.000đ để sử dụng ưu đãi này.'
    package_only = apply(client, customer_auth_headers, create_invoice(500000), percent_voucher(apply_to='package_purchase'))
    assert package_only.status_code == 400 and package_only.json['msg'] == 'Voucher này chỉ dùng cho giao dịch mua gói'
    expired = percent_voucher(validity_days=1)
    with app.app_context():
        db.session.get(LoyaltyRewardRedemption, expired).expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    result = apply(client, customer_auth_headers, create_invoice(500000), expired)
    assert result.status_code == 400 and result.json['msg'] == 'Voucher đã hết hạn'
    pid = client.post(f'/api/packages/{package_id}/purchase', headers=customer_auth_headers, json={'payment_method': 'cash'}).json['purchase']['id']
    ok = client.post(f'/api/packages/purchases/{pid}/reward', headers=customer_auth_headers,
                     json={'redemption_id': percent_voucher(apply_to='package_purchase', max_discount_amount=100000)})
    assert ok.status_code == 200 and Decimal(ok.json['reward_discount']) == 100000 and Decimal(ok.json['payable_amount']) == 1100000


def test_percent_voucher_listing_and_type_filter(client, customer_auth_headers, percent_voucher):
    percent_id = percent_voucher(apply_to='service_invoice')
    usable = client.get('/api/loyalty/my-rewards?status=usable&usable_for=service_invoice', headers=customer_auth_headers).json
    assert [r['id'] for r in usable['items']] == [percent_id]
    assert client.get('/api/loyalty/my-rewards?usable_for=package_purchase&status=usable', headers=customer_auth_headers).json['total'] == 0
    for value in ('voucher', 'voucher_percent'):
        assert client.get(f'/api/loyalty/my-rewards?reward_type={value}', headers=customer_auth_headers).json['total'] == 1
        assert client.get(f'/api/loyalty/rewards?reward_type={value}', headers=customer_auth_headers).json['total'] == 1
    assert client.get('/api/loyalty/rewards?reward_type=voucher_amount', headers=customer_auth_headers).json['total'] == 0


def test_points_cap_after_percent_then_cash_finalize(app, client, admin_auth_headers, customer_auth_headers, create_invoice, percent_voucher):
    invoice, rid = create_invoice(500000), percent_voucher(max_discount_amount=30000)
    base = f'/api/payment/invoices/{invoice}'
    assert apply(client, customer_auth_headers, invoice, rid).json['max_points_allowed'] == 235  # 50% of 470 000
    assert client.post(base + '/loyalty', headers=customer_auth_headers, json={'points': 250}).status_code == 400
    state = client.post(base + '/loyalty', headers=customer_auth_headers, json={'points': 100}).json
    assert Decimal(state['payable_amount']) == 370000
    paid = client.post(f'/api/admin/invoices/{invoice}/record-payment', headers=admin_auth_headers, json={'sotien': 400000, 'phuongthuc': 'Tiền mặt'})
    assert paid.status_code == 201
    with app.app_context():
        assert ThanhToan.query.one().sotien == 370000
        assert db.session.get(LoyaltyRewardRedemption, rid).status == 'used'
        rows = LoyaltyPointTransaction.query.filter_by(source_type='service_invoice', source_id=invoice).order_by(LoyaltyPointTransaction.id).all()
        assert [(r.type, r.points_delta) for r in rows] == [('redeem', -100), ('earn', 30)]
        invariant(app)
    row = client.get(f'/api/admin/billing/transactions/service/{invoice}', headers=admin_auth_headers).json['transaction']
    assert (Decimal(row['reward_discount']), Decimal(row['loyalty_discount']), Decimal(row['change'])) == (30000, 100000, 30000)


def test_percent_voucher_vietqr_finalizes_once(app, client, customer_auth_headers, create_invoice, percent_voucher):
    invoice, rid = create_invoice(500000), percent_voucher()
    apply(client, customer_auth_headers, invoice, rid)
    assert client.post(f'/api/payment/invoices/{invoice}/generate-qr', headers=customer_auth_headers, json={}).json['amount'] == 450000
    with app.app_context():
        assert db.session.get(HoaDon, invoice).trangthai == 'Chưa thanh toán'
        assert db.session.get(LoyaltyRewardRedemption, rid).status == 'reserved'
    payload = dict(id='pct-1', content=f'HD{invoice}', transferAmount=450000)
    assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=payload).json['status'] == 'success'
    assert client.post('/api/payment/webhook/sepay', headers=SEPAY, json=payload).json['status'] == 'duplicate'
    with app.app_context():
        assert db.session.get(LoyaltyRewardRedemption, rid).status == 'used'
        assert [(p.sotien) for p in ThanhToan.query.all()] == [450000]
        assert LoyaltyPointTransaction.query.filter_by(type='earn').one().points_delta == 40

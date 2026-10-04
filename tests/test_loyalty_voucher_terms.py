"""Voucher terms (minimum_spend, apply_to): migration backfill, validation, snapshot, admin form."""
import importlib.util
import json
from io import StringIO
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import LoyaltyReward, LoyaltyRewardRedemption
from app.services import loyalty_service as loyalty
from test_loyalty_migration import migration_engine
from test_loyalty_service import fund

LEGACY_SNAPSHOT = {'id': 1, 'name': 'Voucher cũ', 'description': '', 'reward_type': 'voucher_amount', 'points_cost': 100,
                   'reward_value': '50000.00', 'stock': None, 'validity_days': None, 'active': True}


def load(name):
    path = Path('migrations/versions') / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_0011(connection):
    for sql in ('CREATE TABLE khachhang (makh INTEGER PRIMARY KEY)', 'CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)',
                'CREATE TABLE hoadon (mahd INTEGER PRIMARY KEY, tongtien NUMERIC NOT NULL)',
                'CREATE TABLE goidichvupurchase (id INTEGER PRIMARY KEY, amount NUMERIC NOT NULL)',
                'INSERT INTO khachhang VALUES (5)'):
        connection.execute(text(sql))
    with Operations.context(MigrationContext.configure(connection)):
        load('20261003_0009_loyalty_rewards.py').upgrade()
    connection.execute(text("INSERT INTO loyalty_reward (id, name, description, reward_type, points_cost, reward_value, active) VALUES "
                            "(1, 'Voucher cũ', '', 'voucher_amount', 100, 50000, TRUE), (2, 'Khăn', '', 'physical_gift', 50, 0, TRUE)"))
    connection.execute(text("INSERT INTO loyalty_reward_redemption (id, makh, reward_id, points_spent, reward_snapshot_json, status, code, idempotency_key) "
                            "VALUES (9, 5, 1, 100, :snapshot, 'available', 'BIN-LEGACY', 'legacy-key')"), dict(snapshot=json.dumps(LEGACY_SNAPSHOT)))


def test_migration_backfills_vouchers_and_keeps_gifts_and_redemptions(migration_engine):
    migration = load('20261004_0012_voucher_terms.py')
    assert migration.down_revision == '20261004_0011'
    with migration_engine.begin() as connection:
        seed_0011(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        rows = connection.execute(text('SELECT id, apply_to, minimum_spend FROM loyalty_reward ORDER BY id')).all()
        assert [(r[0], r[1], r[2] if r[2] is None else float(r[2])) for r in rows] == [(1, 'both', 0.0), (2, None, None)]
        redemption = connection.execute(text('SELECT status, code, points_spent, reward_snapshot_json FROM loyalty_reward_redemption')).one()
        snapshot = redemption[3] if isinstance(redemption[3], dict) else json.loads(redemption[3])
        assert redemption[:3] == ('available', 'BIN-LEGACY', 100) and snapshot == LEGACY_SNAPSHOT
        for values in ("'voucher_amount', 10000, 'all', 0", "'voucher_amount', 10000, 'both', -1",
                       "'physical_gift', 0, 'both', NULL", "'physical_gift', 0, NULL, 0"):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text('INSERT INTO loyalty_reward (name, description, reward_type, reward_value, apply_to, minimum_spend, points_cost, active) '
                                        f"VALUES ('x', '', {values}, 10, TRUE)"))


def test_postgresql_migration_sql_is_additive_and_single_head():
    output = StringIO()
    context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})
    with Operations.context(context):
        load('20261004_0012_voucher_terms.py').upgrade()
    sql = output.getvalue()
    assert 'ADD COLUMN minimum_spend NUMERIC(12, 2)' in sql and 'ADD COLUMN apply_to VARCHAR(30)' in sql
    assert "SET apply_to = 'both', minimum_spend = 0 WHERE reward_type = 'voucher_amount'" in sql
    assert 'ck_loyalty_reward_voucher_terms' in sql
    assert 'DROP' not in sql and 'DELETE' not in sql and 'NOT NULL' not in sql
    config = Config('migrations/alembic.ini')
    config.set_main_option('script_location', 'migrations')
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1


def create(client, headers, **data):
    return client.post('/api/admin/loyalty/rewards', headers=headers,
                       json=dict(dict(name='Voucher 50k', reward_type='voucher_amount', points_cost=100, reward_value=50000), **data))


def test_create_voucher_with_terms_and_default_scope(client, admin_auth_headers):
    reward = create(client, admin_auth_headers, apply_to='service_invoice', minimum_spend=300000, stock=5, validity_days=30).json['reward']
    assert reward['apply_to'] == 'service_invoice' and reward['minimum_spend'] == '300000.00'
    assert reward['stock'] == 5 and reward['validity_days'] == 30 and reward['active'] is True
    plain = create(client, admin_auth_headers).json['reward']
    assert plain['apply_to'] == 'both' and plain['minimum_spend'] == '0.00'
    assert create(client, admin_auth_headers, minimum_spend=None).json['reward']['minimum_spend'] == '0.00'
    edited = client.put(f"/api/admin/loyalty/rewards/{reward['id']}", headers=admin_auth_headers,
                        json=dict(apply_to='package_purchase')).json['reward']
    assert edited['apply_to'] == 'package_purchase' and edited['minimum_spend'] == '300000.00'


@pytest.mark.parametrize('data, message', [
    (dict(reward_value=0), 'Voucher cần giá trị lớn hơn 0'),
    (dict(minimum_spend=-1), 'Đơn tối thiểu'),
    (dict(minimum_spend='abc'), 'Đơn tối thiểu'),
    (dict(apply_to='all'), 'Phạm vi áp dụng'),
    (dict(apply_to=['both']), 'Phạm vi áp dụng'),
    (dict(points_cost=0), 'Số điểm'),
    (dict(stock=-1), 'Số điểm'),
    (dict(validity_days=0), 'Số điểm'),
])
def test_invalid_voucher_terms_are_rejected(app, client, admin_auth_headers, data, message):
    response = create(client, admin_auth_headers, **data)
    assert response.status_code == 400 and message in response.json['msg']
    with app.app_context():
        assert LoyaltyReward.query.count() == 0


def test_physical_gift_needs_no_payment_terms(client, admin_auth_headers):
    gift = client.post('/api/admin/loyalty/rewards', headers=admin_auth_headers,
                       json=dict(name='Khăn Bin Spa', reward_type='physical_gift', points_cost=50, stock=2)).json['reward']
    assert gift['reward_value'] == '0.00' and gift['apply_to'] is None and gift['minimum_spend'] is None
    # Voucher-only fields sent for a gift are dropped, also when a voucher becomes a gift.
    voucher = create(client, admin_auth_headers, apply_to='service_invoice', minimum_spend=100000).json['reward']
    changed = client.put(f"/api/admin/loyalty/rewards/{voucher['id']}", headers=admin_auth_headers,
                         json=dict(reward_type='physical_gift', apply_to='both', minimum_spend=5)).json['reward']
    assert changed['reward_type'] == 'physical_gift' and changed['apply_to'] is None and changed['minimum_spend'] is None


def test_snapshot_keeps_terms_after_catalog_edit(app, client, admin_auth_headers, customer_auth_headers):
    with app.app_context():
        fund(app, 300)
        db.session.commit()
    rid = create(client, admin_auth_headers, apply_to='service_invoice', minimum_spend=300000, validity_days=30).json['reward']['id']
    redeemed = client.post(f'/api/loyalty/rewards/{rid}/redeem', headers=customer_auth_headers, json={'idempotency_key': 'terms'})
    assert redeemed.status_code == 201
    snapshot = redeemed.json['redemption']['reward']
    expected = dict(name='Voucher 50k', description='', reward_type='voucher_amount', points_cost=100, reward_value='50000.00',
                    minimum_spend='300000.00', apply_to='service_invoice', validity_days=30)
    assert {key: snapshot[key] for key in expected} == expected
    assert client.put(f'/api/admin/loyalty/rewards/{rid}', headers=admin_auth_headers, json=dict(
        name='Voucher sửa', reward_value=10000, minimum_spend=0, apply_to='both', validity_days=1)).status_code == 200
    item = client.get('/api/loyalty/my-rewards', headers=customer_auth_headers).json['items'][0]
    assert {key: item['reward'][key] for key in expected} == expected
    with app.app_context():
        assert db.session.get(LoyaltyRewardRedemption, item['id']).reward_snapshot_json['apply_to'] == 'service_invoice'


def test_admin_form_has_voucher_and_gift_fields(client):
    page = client.get('/admin/loyalty').text
    for expected in ('data-voucher-fields', 'name="apply_to"', 'name="minimum_spend"', 'Giá trị giảm',
                     '>Hóa đơn dịch vụ<', '>Mua gói<', '>Cả hai<', 'data-name-label', 'Đang cho đổi'):
        assert expected in page, expected
    script = Path('app/static/js/admin/loyalty.js').read_text(encoding='utf-8')
    assert 'fields.hidden=!on;fields.disabled=!on' in script and "body.reward_type==='voucher_amount'?Number(f.elements.reward_value.value):0" in script

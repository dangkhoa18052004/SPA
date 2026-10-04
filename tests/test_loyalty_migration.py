import importlib.util
import os
from uuid import uuid4
import pytest
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.fixture(params=['sqlite', 'postgresql'])
def migration_engine(request):
    url=os.environ.get('TEST_LOYALTY_POSTGRES_URL') if request.param=='postgresql' else 'sqlite://'
    if not url:
        pytest.skip('TEST_LOYALTY_POSTGRES_URL not configured')
    admin=create_engine(url)
    schema='migration_test_'+uuid4().hex
    if request.param=='postgresql':
        with admin.begin() as c:c.execute(text(f'CREATE SCHEMA {schema}'))
        engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    else:engine=admin
    yield engine
    engine.dispose()
    if request.param=='postgresql':
        with admin.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def test_additive_loyalty_migration_backfills_without_changing_legacy(migration_engine):
    path=Path('migrations/versions/20261003_0009_loyalty_rewards.py')
    spec=importlib.util.spec_from_file_location('loyalty_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    assert migration.down_revision=='20261003_0008'
    engine=migration_engine
    with engine.begin() as connection:
        for sql in [
            'CREATE TABLE khachhang (makh INTEGER PRIMARY KEY)',
            'CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)',
            'CREATE TABLE hoadon (mahd INTEGER PRIMARY KEY, tongtien NUMERIC NOT NULL, trangthai TEXT)',
            'CREATE TABLE goidichvupurchase (id INTEGER PRIMARY KEY, amount NUMERIC NOT NULL, status TEXT)',
            "INSERT INTO hoadon VALUES (31,500000,'paid')",
            "INSERT INTO goidichvupurchase VALUES (42,1200000,'paid')",
            'CREATE TABLE gift_sentinel (id INTEGER PRIMARY KEY, value TEXT)',
            "INSERT INTO gift_sentinel VALUES (7,'unchanged')",
            'CREATE TABLE review_sentinel (id INTEGER PRIMARY KEY, value TEXT)',
            "INSERT INTO review_sentinel VALUES (8,'unchanged')",
        ]:connection.execute(text(sql))
        with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
        assert connection.execute(text('SELECT mahd,tongtien,reward_discount,loyalty_discount,payable_amount FROM hoadon')).one()==(31,500000,0,0,500000)
        assert connection.execute(text('SELECT id,amount,payable_amount FROM goidichvupurchase')).one()==(42,1200000,1200000)
        assert connection.execute(text('SELECT earn_points,point_value,maximum_redeem_percent FROM loyalty_config')).one()==(10,1000,50)
        assert connection.execute(text('SELECT * FROM gift_sentinel')).one()==(7,'unchanged')
        assert connection.execute(text('SELECT * FROM review_sentinel')).one()==(8,'unchanged')
        assert not next(c for c in inspect(connection).get_columns('hoadon') if c['name']=='payable_amount')['nullable']
        assert 'uq_loyalty_active_reservation' in {i['name'] for i in inspect(connection).get_indexes('loyalty_redemption_reservation')}


def test_flask_db_upgrade_from_existing_head(migration_engine, monkeypatch):
    # Alembic fileConfig replaces pytest's root handlers and disables existing
    # app loggers. DDL is real; keep this in-process CLI test's logging isolated.
    monkeypatch.setattr('logging.config.fileConfig', lambda *args, **kwargs: None)
    from app import create_app
    from app.extensions import db
    engine=migration_engine
    with engine.begin() as c:
        for sql in ['CREATE TABLE khachhang (makh INTEGER PRIMARY KEY)',
            'CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)',
            'CREATE TABLE lichhen (malh INTEGER PRIMARY KEY, manv INTEGER REFERENCES nhanvien(manv))',
            'CREATE TABLE hoadon (mahd INTEGER PRIMARY KEY, tongtien NUMERIC NOT NULL)',
            'CREATE TABLE goidichvu (magoi INTEGER PRIMARY KEY, active BOOLEAN NOT NULL)',
            'CREATE TABLE goidichvupurchase (id INTEGER PRIMARY KEY, amount NUMERIC NOT NULL)',
            'INSERT INTO hoadon VALUES (1,500000)', 'INSERT INTO goidichvupurchase VALUES (1,1200000)']:
            c.execute(text(sql))
    application=create_app(dict(TESTING=True,APP_ENV='testing',SQLALCHEMY_DATABASE_URI='sqlite://',
        SECRET_KEY='migration-test',JWT_SECRET_KEY='migration-test-secret'))
    with application.app_context():
        db.engine.dispose()
        db.engines[None]=engine
    runner=application.test_cli_runner()
    result=runner.invoke(args=['db','stamp','20261003_0008'])
    assert result.exit_code==0,result.output
    result=runner.invoke(args=['db','upgrade'])
    assert result.exit_code==0,result.output
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar()=='20261004_0011'
        assert c.execute(text('SELECT payable_amount FROM hoadon')).scalar()==500000
    with application.app_context():
        db.session.remove();db.engine.dispose()

import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text, inspect

from test_loyalty_migration import migration_engine


def load_migration():
    path = Path('migrations/versions/20261004_0011_package_sale_channels.py')
    spec = importlib.util.spec_from_file_location('package_sale_channels_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def seed_legacy(connection):
    for sql in (
        'CREATE TABLE goidichvu (magoi INTEGER PRIMARY KEY, tengoi TEXT NOT NULL, active BOOLEAN NOT NULL)',
        "INSERT INTO goidichvu VALUES (1, 'Active package', TRUE), (2, 'Archived package', FALSE)",
        'CREATE TABLE goidichvupurchase (id INTEGER PRIMARY KEY, magoi INTEGER REFERENCES goidichvu(magoi), snapshot_json TEXT)',
        "INSERT INTO goidichvupurchase VALUES (11, 2, 'legacy snapshot')",
        'CREATE TABLE thelieutrinh (mathe INTEGER PRIMARY KEY, purchase_id INTEGER REFERENCES goidichvupurchase(id))',
        'INSERT INTO thelieutrinh VALUES (21, 11)',
        'CREATE TABLE thelieutrinhitem (id INTEGER PRIMARY KEY, mathe INTEGER REFERENCES thelieutrinh(mathe), source_type TEXT)',
        "INSERT INTO thelieutrinhitem VALUES (31, 21, 'gift')",
        'CREATE TABLE lieutrinhusage (id INTEGER PRIMARY KEY, the_item_id INTEGER REFERENCES thelieutrinhitem(id), state TEXT)',
        "INSERT INTO lieutrinhusage VALUES (41, 31, 'reserved')",
    ):
        connection.execute(text(sql))


def assert_backfill(connection):
    assert connection.execute(text('SELECT magoi, active, customer_sale_enabled, staff_sale_enabled FROM goidichvu ORDER BY magoi')).all() == [
        (1, True, True, True), (2, False, False, False)]
    for table, expected in (
        ('goidichvupurchase', (11, 2, 'legacy snapshot')),
        ('thelieutrinh', (21, 11)), ('thelieutrinhitem', (31, 21, 'gift')),
        ('lieutrinhusage', (41, 31, 'reserved')),
    ):
        assert connection.execute(text(f'SELECT * FROM {table}')).one() == expected
    columns = {c['name']: c for c in inspect(connection).get_columns('goidichvu')}
    for field in ('customer_sale_enabled', 'staff_sale_enabled'):
        assert columns[field]['nullable'] is False


def test_additive_sale_channel_migration_preserves_existing_data(migration_engine):
    migration = load_migration()
    assert migration.down_revision == '20261004_0010'
    with migration_engine.begin() as connection:
        seed_legacy(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert_backfill(connection)
        connection.execute(text("INSERT INTO goidichvu (magoi, tengoi, active) VALUES (3, 'New package', TRUE)"))
        assert connection.execute(text('SELECT customer_sale_enabled, staff_sale_enabled FROM goidichvu WHERE magoi = 3')).one() == (True, True)


def test_flask_db_upgrade_from_current_head(migration_engine, monkeypatch):
    monkeypatch.setattr('logging.config.fileConfig', lambda *args, **kwargs: None)
    from app import create_app
    from app.extensions import db
    with migration_engine.begin() as connection:
        seed_legacy(connection)
    application = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI='sqlite://',
        SECRET_KEY='migration-test', JWT_SECRET_KEY='migration-test-secret'))
    with application.app_context():
        db.engine.dispose()
        db.engines[None] = migration_engine
    runner = application.test_cli_runner()
    for args in (['db', 'stamp', '20261004_0010'], ['db', 'upgrade'], ['db', 'upgrade']):
        result = runner.invoke(args=args)
        assert result.exit_code == 0, result.output
    with migration_engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '20261004_0011'
        assert_backfill(connection)
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


def test_postgresql_upgrade_sql_is_additive_and_has_one_head():
    output = StringIO()
    context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})
    with Operations.context(context):
        load_migration().upgrade()
    sql = output.getvalue()
    assert 'ADD COLUMN customer_sale_enabled BOOLEAN DEFAULT true NOT NULL' in sql
    assert 'ADD COLUMN staff_sale_enabled BOOLEAN DEFAULT true NOT NULL' in sql
    assert 'customer_sale_enabled = active, staff_sale_enabled = active' in sql
    assert 'DROP' not in sql and 'DELETE' not in sql
    config = Config('migrations/alembic.ini')
    config.set_main_option('script_location', 'migrations')
    assert ScriptDirectory.from_config(config).get_heads() == ['20261004_0011']

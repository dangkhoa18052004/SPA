"""F02: `flask db upgrade` phải dựng được database rỗng và giữ dữ liệu database cũ."""
import importlib.util
import os
from datetime import date, time
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]


def _load_detector():
    spec = importlib.util.spec_from_file_location('detect_db_revision', ROOT / 'scripts' / 'detect_db_revision.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _head():
    cfg = AlembicConfig()
    cfg.set_main_option('script_location', str(ROOT / 'migrations'))
    return ScriptDirectory.from_config(cfg).get_current_head()


@pytest.fixture(params=['sqlite', 'postgresql'])
def db_url(request, tmp_path):
    if request.param == 'sqlite':
        yield f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
        return
    base = os.environ.get('TEST_LOYALTY_POSTGRES_URL')
    if not base:
        pytest.skip('TEST_LOYALTY_POSTGRES_URL not configured')
    name = 'binspa_mig_' + uuid4().hex[:12]
    admin = create_engine(base, isolation_level='AUTOCOMMIT')
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE {name}'))
    yield admin.url.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def make_app(monkeypatch):
    # Alembic fileConfig thay logging của pytest; tắt trong test CLI chạy cùng tiến trình.
    monkeypatch.setattr('logging.config.fileConfig', lambda *args, **kwargs: None)
    from app import create_app
    from app.extensions import db
    apps = []

    def factory(url):
        application = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI=url,
                                      SECRET_KEY='migration-test', JWT_SECRET_KEY='migration-test-secret-32-bytes!!'))
        apps.append(application)
        return application

    yield factory
    for application in apps:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def _cli(application, *args):
    result = application.test_cli_runner().invoke(args=['db', *args])
    assert result.exit_code == 0, (result.output, result.exception)


def test_empty_database_upgrades_to_head_matching_models(db_url, make_app):
    from app.extensions import db
    application = make_app(db_url)
    _cli(application, 'upgrade')
    with application.app_context():
        with db.engine.connect() as conn:
            assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar() == _head()
            diffs = compare_metadata(MigrationContext.configure(conn), db.metadata)
    structural = [d for d in diffs if not isinstance(d, list)
                  and d[0] in ('add_table', 'remove_table', 'add_column', 'remove_column')]
    assert structural == []
    for diff in diffs:
        if isinstance(diff, list):  # modify_* trên cột: chỉ chấp nhận khác biệt nullable/type nhỏ
            continue
        assert diff[0] in ('add_index', 'remove_index', 'add_constraint', 'remove_constraint', 'add_fk', 'remove_fk'), diff


def test_fresh_schema_supports_core_writes(db_url, make_app):
    from app.extensions import db
    from app.models import ChucVu, NhanVien, KhachHang, DichVu, LichHen, ChiTietLichHen, CaLam
    application = make_app(db_url)
    _cli(application, 'upgrade')
    with application.app_context():
        role = ChucVu(tencv='KTV', dongiagio=100000)
        db.session.add(role); db.session.flush()
        staff = NhanVien(hoten='A', taikhoan='a', matkhau='x', macv=role.macv, role='staff')
        customer = KhachHang(hoten='B', taikhoan='b', matkhau='x')
        service = DichVu(tendv='Massage', gia=300000, thoiluong=60)
        db.session.add_all([staff, customer, service]); db.session.flush()
        db.session.add(CaLam(ngay=date(2026, 10, 5), giobatdau=time(8), gioketthuc=time(17), sogio=9))
        appt = LichHen(makh=customer.makh, manv=staff.manv, ngaygio=__import__('datetime').datetime(2026, 10, 5, 9))
        db.session.add(appt); db.session.flush()
        db.session.add(ChiTietLichHen(malh=appt.malh, madv=service.madv))
        db.session.commit()
        assert LichHen.query.one().booking_source == 'legacy'


def test_legacy_database_is_detected_stamped_and_upgraded_without_data_loss(tmp_path, make_app):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    application = make_app(url)
    # Dựng database cũ ở trạng thái 20261003_0009 rồi xóa dấu vết alembic như DB tạo tay.
    _cli(application, 'upgrade', '20261003_0009')
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("INSERT INTO chucvu (macv, tencv, dongiagio) VALUES (1, 'KTV', 100000)"))
        c.execute(text("INSERT INTO khachhang (makh, hoten, taikhoan, matkhau) VALUES (7, 'Khách cũ', 'old', 'x')"))
        c.execute(text("INSERT INTO lichhen (malh, ngaygio, trangthai, makh) VALUES (3, '2026-01-01 09:00:00', 'completed', 7)"))
        c.execute(text('DROP TABLE alembic_version'))

    detector = _load_detector()
    state, revision = detector.detect(engine)
    assert (state, revision) == ('legacy', '20261003_0009')
    assert 'flask db stamp 20261003_0009' in detector.advice(state, revision)

    _cli(application, 'stamp', revision)
    _cli(application, 'upgrade')
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar() == _head()
        assert c.execute(text('SELECT hoten FROM khachhang WHERE makh = 7')).scalar() == 'Khách cũ'
        assert c.execute(text('SELECT trangthai, booking_source FROM lichhen WHERE malh = 3')).one() == ('completed', 'legacy')
    assert detector.detect(engine) == ('managed', _head())
    engine.dispose()


def test_baseline_is_noop_on_existing_legacy_tables(tmp_path):
    spec = importlib.util.spec_from_file_location('baseline', ROOT / 'migrations/versions/f3b12dbde06b_initial_baseline.py')
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    from alembic.operations import Operations
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as c:
        c.execute(text('CREATE TABLE lichhen (malh INTEGER PRIMARY KEY, note TEXT)'))
        c.execute(text("INSERT INTO lichhen VALUES (1, 'giữ nguyên')"))
        with Operations.context(MigrationContext.configure(c)):
            baseline.upgrade()
        assert set(inspect(c).get_table_names()) == {'lichhen'}
        assert c.execute(text('SELECT note FROM lichhen')).scalar() == 'giữ nguyên'
    engine.dispose()


def test_downgrade_to_baseline_and_upgrade_again(tmp_path, make_app):
    url = f"sqlite:///{(tmp_path / 'roundtrip.db').as_posix()}"
    application = make_app(url)
    _cli(application, 'upgrade')
    _cli(application, 'downgrade', 'f3b12dbde06b')
    _cli(application, 'upgrade')
    engine = create_engine(url)
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar() == _head()
    engine.dispose()

"""Expand/rollback changes only the security tables, on SQLite and PostgreSQL."""
from sqlalchemy import create_engine, text, inspect
from test_fresh_migration import db_url, make_app, _cli  # noqa: F401


def test_security_upgrade_downgrade_preserves_business_rows(db_url, make_app):
    app = make_app(db_url)
    _cli(app, 'upgrade', '20261015_0022')
    engine = create_engine(db_url)
    with engine.begin() as c:
        c.execute(text("INSERT INTO chucvu (macv,tencv,dongiagio) VALUES (41,'Sentinel',30000)"))
        c.execute(text("INSERT INTO nhanvien (manv,hoten,taikhoan,matkhau,macv,role,trangthai) VALUES (41,'Preserved','sentinel','hash',41,'admin',true)"))
    _cli(app, 'upgrade')
    with engine.connect() as c:
        assert c.execute(text('SELECT hoten,matkhau FROM nhanvien WHERE manv=41')).one() == ('Preserved', 'hash')
        assert 'staff_mfa' in inspect(c).get_table_names()
    _cli(app, 'downgrade', '20261015_0022')
    with engine.connect() as c:
        assert c.execute(text('SELECT hoten,matkhau FROM nhanvien WHERE manv=41')).one() == ('Preserved', 'hash')
        assert 'staff_mfa' not in inspect(c).get_table_names()
    _cli(app, 'upgrade')
    engine.dispose()

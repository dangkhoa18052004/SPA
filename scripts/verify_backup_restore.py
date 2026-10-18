"""Restore a PostgreSQL archive into a disposable loopback cluster and test migration.

Never reads DATABASE_URL or connects to the running business database.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TABLES = ('khachhang', 'lichhen', 'hoadon', 'thanhtoan', 'goidichvupurchase', 'commission_entry', 'attendance_session', 'payroll_period', 'payroll_line')


def snapshot(engine):
    with engine.connect() as conn:
        counts = {name: conn.execute(text(f'SELECT COUNT(*) FROM {name}')).scalar() for name in TABLES}
        counts['service_receipts'] = str(conn.execute(text('SELECT COALESCE(SUM(sotien),0) FROM thanhtoan')).scalar())
        counts['locked_payroll'] = str(conn.execute(text("SELECT COALESCE(SUM(l.net),0) FROM payroll_line l JOIN payroll_period p ON p.id=l.period_id WHERE p.status='LOCKED'")).scalar())
        return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--postgres-bin', type=Path, default=Path(r'C:\Program Files\PostgreSQL\17\bin'))
    args = parser.parse_args()
    archive = args.archive.resolve(strict=True)
    directory = ROOT / '.test-tmp' / ('restore-drill-' + uuid4().hex[:10]); directory.mkdir(parents=True)
    suffix = '.exe' if os.name == 'nt' else ''
    binary = lambda name: args.postgres_bin / (name + suffix)
    if not binary('initdb').is_file(): parser.error('PostgreSQL initdb not found; specify --postgres-bin')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    data = directory / 'data'
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    def run(values):
        with (directory / 'commands.log').open('a', encoding='utf-8') as log:
            result = subprocess.run([str(v) for v in values], stdout=log, stderr=log, timeout=180, **options)
        if result.returncode: raise RuntimeError('Restore drill command failed; see ' + str(directory / 'commands.log'))
    started = False
    engine = app = None
    try:
        run([binary('initdb'), '-D', data, '-A', 'trust', '-U', 'binspa_restore', '--no-locale', '--encoding=UTF8'])
        run([binary('pg_ctl'), '-D', data, '-l', directory / 'server.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start']); started = True
        url = f'postgresql://binspa_restore@127.0.0.1:{port}/postgres'
        run([binary('pg_restore'), '--no-owner', '--no-privileges', '--exit-on-error', '-d', url, archive])
        engine = create_engine(url)
        before = snapshot(engine)
        from app import create_app
        app = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI=url,
            SECRET_KEY='restore-drill', JWT_SECRET_KEY='restore-drill-only-at-least-32-characters',
            GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False, BI_REPORTS_ENABLED=False,
            OBSERVABILITY_ENABLED=False, AUTH_RATE_LIMIT_ENABLED=False))
        result = app.test_cli_runner().invoke(args=['db', 'upgrade'])
        (directory / 'migration.log').write_text(result.output, encoding='utf-8')
        if result.exit_code: raise RuntimeError('Restored database did not migrate; see migration.log')
        after = snapshot(engine)
        if before != after: raise AssertionError('Business data changed during migration on restored copy')
        with engine.connect() as conn: revision = conn.execute(text('SELECT version_num FROM alembic_version')).scalar()
        result = dict(archive=archive.name, restored=True, migration_revision=revision, business_data_preserved=True, counts=after)
        (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(dict(restored=True, migration_revision=revision, business_data_preserved=True, artifacts=str(directory))))
    finally:
        if engine: engine.dispose()
        if app:
            from app.extensions import db
            with app.app_context(): db.session.remove(); db.engine.dispose()
        if started: run([binary('pg_ctl'), '-D', data, '-m', 'fast', '-w', 'stop'])


if __name__ == '__main__': main()

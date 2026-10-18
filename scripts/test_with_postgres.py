"""Run tests against a disposable, loopback-only PostgreSQL cluster, never DATABASE_URL."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres-bin', default=r'C:\Program Files\PostgreSQL\17\bin')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    directory = ROOT / '.test-tmp' / ('postgres-' + uuid4().hex)
    directory.mkdir(parents=True)
    bin_dir = Path(args.postgres_bin)
    suffix = '.exe' if os.name == 'nt' else ''
    initdb = bin_dir / ('initdb' + suffix)
    ctl = bin_dir / ('pg_ctl' + suffix)
    if not initdb.exists():
        parser.error('Không tìm thấy initdb, truyền --postgres-bin')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    data = directory / 'data'
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    def command(values):
        # Windows postmaster children inherit pipes; file handles avoid waiting for EOF.
        log = directory / 'commands.log'
        with log.open('a', encoding='utf-8') as output:
            result = subprocess.run([str(v) for v in values], stdout=output, stderr=output,
                text=True, timeout=120, **options)
        if result.returncode:
            raise RuntimeError(log.read_text(encoding='utf-8'))
    started = False
    try:
        command([initdb, '-D', data, '-A', 'trust', '-U', 'binspa_test', '--no-locale', '--encoding=UTF8'])
        command([ctl, '-D', data, '-l', directory / 'server.log', '-o', f'-h 127.0.0.1 -p {port} -c fsync=off', '-w', 'start'])
        started = True
        environment = dict(os.environ, TEST_LOYALTY_POSTGRES_URL=f'postgresql://binspa_test@127.0.0.1:{port}/postgres', PYTHONDONTWRITEBYTECODE='1')
        test_args = args.pytest_args
        if test_args and test_args[0] == '--':
            test_args = test_args[1:]
        output_path = directory / 'pytest.log'
        with output_path.open('w', encoding='utf-8') as output:
            result = subprocess.run([sys.executable, '-m', 'pytest', *test_args], cwd=ROOT,
                env=environment, stdout=output, stderr=subprocess.STDOUT, **options)
        print(output_path.read_text(encoding='utf-8'))
        return result.returncode
    finally:
        if started:
            command([ctl, '-D', data, '-m', 'fast', '-w', 'stop'])
        print(f'Isolated PostgreSQL artifacts: {directory}')


if __name__ == '__main__':
    raise SystemExit(main())

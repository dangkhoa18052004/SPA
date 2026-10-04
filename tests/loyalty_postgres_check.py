"""Run concurrency/regression on a disposable local PostgreSQL cluster.

No connection to the application's DATABASE_URL, no live payment or mail.
Usage: python tests/loyalty_postgres_check.py [--full]
Requires installed PostgreSQL binaries (or POSTGRES_BIN).
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET
from uuid import uuid4


def main():
    root=Path(__file__).resolve().parents[1]
    binaries=Path(os.environ.get('POSTGRES_BIN',r'C:\Program Files\PostgreSQL\17\bin'))
    artifacts=root/'tests'/('loyalty-postgres-'+uuid4().hex+'.tmp')
    artifacts.mkdir()
    data=artifacts/'data'
    log=artifacts/'postgres.log'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    def run(args):
        # Windows postgres children inherit handles: pipes can leave communicate()
        # waiting after pg_ctl exits. A file lets us wait only for the helper.
        helper_log=artifacts/('helper-'+uuid4().hex+'.log')
        with helper_log.open('w',encoding='utf-8') as output:
            result=subprocess.run(args,cwd=root,stdout=output,stderr=output,creationflags=flags)
        if result.returncode:
            print(helper_log.read_text(encoding='utf-8',errors='replace')[-3000:]);raise RuntimeError('Local PostgreSQL helper failed')
    run([str(binaries/'initdb.exe'),'--pgdata',str(data),'--username','loyalty_test','--auth-local','trust','--auth-host','trust','--encoding','UTF8','--locale','C'])
    started=False
    try:
        run([str(binaries/'pg_ctl.exe'),'-D',str(data),'-l',str(log),'-o',f'-h 127.0.0.1 -p {port}','-w','start'])
        started=True
        env=dict(os.environ,TEST_LOYALTY_POSTGRES_URL=f'postgresql+psycopg2://loyalty_test@127.0.0.1:{port}/postgres',PYTHONDONTWRITEBYTECODE='1')
        target=['tests'] if '--full' in sys.argv else ['tests/test_loyalty_concurrency.py','tests/test_loyalty_migration.py']
        report=artifacts/'results.xml'
        result=subprocess.run([sys.executable,'-m','pytest',*target,'-q','--disable-warnings','--basetemp',str(artifacts/'pytest'),'--junitxml',str(report)],cwd=root,env=env,creationflags=flags)
        if report.exists():
            print('Test results:',ET.parse(report).getroot().find('testsuite').attrib)
        print('Disposable PostgreSQL artifacts:',artifacts.relative_to(root))
        return result.returncode
    finally:
        if started:
            run([str(binaries/'pg_ctl.exe'),'-D',str(data),'-m','fast','-w','stop'])


if __name__=='__main__':
    raise SystemExit(main())

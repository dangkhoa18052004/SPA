"""Real Chrome security setup and interrupted GPS-policy writes on an isolated DB."""
import base64
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import websocket
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server, WSGIRequestHandler
from billing_browser_check import Browser, free_port
from app import create_app
from app.extensions import db
from app.models import NhanVien, ChucVu, Branch, BranchGeoPolicy, StaffMFA
from app.services import attendance_service as att, staff_security_service as security


class SecurityBrowser(Browser):
    def wait(self, expression): return super().wait('Boolean(' + expression + ')')


def main():
    artifacts = ROOT / '.test-tmp' / ('staff-security-browser-' + uuid4().hex[:8]); artifacts.mkdir(parents=True)
    app = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI='sqlite:///' + (artifacts / 'test.db').as_posix(),
        SECRET_KEY='security-browser-only', JWT_SECRET_KEY='security-browser-only-at-least-32-characters',
        STAFF_SECURITY_ENABLED=True, STAFF_MFA_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        ATTENDANCE_ENABLED=True, ATTENDANCE_SIMPLE_MODE=False, EMPLOYEE_PORTAL_ENABLED=True,
        PAYROLL_V2_ENABLED=False, BUSINESS_PORTAL_ENABLED=True, OBSERVABILITY_ENABLED=False,
        AUTH_RATE_LIMIT_ENABLED=False, GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False))
    clock = [datetime.utcnow()]
    security.now = lambda: clock[0]
    with app.app_context():
        db.create_all()
        role = ChucVu(tencv='Browser', dongiagio=30000); branch = Branch(name='Cơ sở thử bảo mật', address='Dữ liệu kiểm thử')
        db.session.add_all([role, branch]); db.session.flush()
        admin = NhanVien(hoten='Quản trị thử nghiệm', taikhoan='security-browser', matkhau=generate_password_hash('test-password'),
            macv=role.macv, role='admin', trangthai=True)
        db.session.add(admin); db.session.flush()
        policy = BranchGeoPolicy(branch_id=branch.id, version=1, settings=dict(att.DEFAULT_POLICY, enabled=True), created_by=admin.manv)
        db.session.add(policy); db.session.commit()
        admin_id = admin.manv
        token = create_access_token(identity=f'staff:{admin_id}')
    @app.after_request
    def bootstrap(response):
        if response.mimetype == 'text/html':
            script = 'localStorage.setItem("admin_token",' + json.dumps(token) + ');localStorage.setItem("admin_role","admin");window.__uiErrors=[];window.__requests=[];const nativeFetch=fetch;window.fetch=(u,...args)=>{__requests.push(String(u));return nativeFetch(u,...args)};addEventListener("error",e=>{if(e.message)__uiErrors.push(e.message)});addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
            response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + script + '</script>', 1))
        return response
    class Quiet(WSGIRequestHandler):
        def log(self, *a, **k): pass
    server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = free_port(); chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    process = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts / "profile"}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    ws = browser = None
    try:
        for _ in range(100):
            try: tabs = json.load(urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1)); break
            except Exception: time.sleep(.1)
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        browser = SecurityBrowser(ws); browser.call('Page.enable')
        def navigate(path):
            browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}' + path))
            browser.wait('location.pathname===' + json.dumps(path) + '&&document.readyState==="complete"')
        def click_text(value):
            point = browser.evaluate('(()=>{const e=[...document.querySelectorAll("button")].find(e=>e.textContent.trim()===' + json.dumps(value) + '&&e.getBoundingClientRect().width);e.scrollIntoView({block:"center"});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')
            browser.call('Input.dispatchMouseEvent', dict(type='mousePressed', button='left', clickCount=1, **point))
            browser.call('Input.dispatchMouseEvent', dict(type='mouseReleased', button='left', clickCount=1, **point))
        def fill(selector, value):
            browser.evaluate('(()=>{const e=document.querySelector(' + json.dumps(selector) + ');Object.getOwnPropertyDescriptor(e.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,"value").set.call(e,' + json.dumps(value) + ');e.dispatchEvent(new Event("input",{bubbles:true}))})()')
        def screenshot(name):
            time.sleep(.15)
            state = browser.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:__uiErrors})')
            assert state['scroll'] <= state['width'] + 1 and not state['errors'], (name, state)
            (artifacts / (name + '.png')).write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
        def submit_policy():
            browser.wait('document.body.textContent.includes("Chính sách GPS")')
            click_text('Chính sách GPS'); browser.wait('document.querySelector(".ant-drawer-body textarea")')
            fill('.ant-drawer-body textarea', 'Thử xác minh, giữ dữ liệu và tránh ghi lặp')
            browser.evaluate('document.querySelector(".ant-drawer-body form").requestSubmit()')
            browser.wait('document.querySelector(".ant-modal-content")')
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=360, height=900, deviceScaleFactor=1, mobile=True))
        navigate('/admin/operations/branches'); submit_policy()
        browser.wait('document.body.textContent.includes("Đã thiết lập, tiếp tục")'); screenshot('360-enrollment-required')
        with app.app_context(): assert BranchGeoPolicy.query.count() == 1
        click_text('Hủy thao tác')
        browser.wait('!document.querySelector(".ant-modal-content")')
        assert browser.evaluate('document.querySelector(".ant-drawer-body textarea").value').startswith('Thử xác minh')
        navigate('/admin/security'); browser.wait('document.querySelector("#security-password")')
        fill('#security-password', 'test-password'); browser.evaluate('document.querySelector(".security-form").requestSubmit()')
        browser.wait('document.querySelector(".security-secret")'); screenshot('360-setup-qr')
        secret = browser.evaluate('document.querySelector(".security-secret").textContent')
        import calendar
        def current_code(): return security.otp_at(secret, calendar.timegm(clock[0].utctimetuple()) // 30)
        fill('#security-code', current_code()); browser.evaluate('document.querySelector(".security-form").requestSubmit()')
        browser.wait('document.querySelectorAll(".security-codes code").length===10'); screenshot('360-recovery-codes')
        browser.evaluate('document.querySelector(".ant-checkbox-input").click()'); click_text('Đã lưu, đóng mã')
        for width in (360, 390, 768, 1440):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))
            navigate('/admin/security'); browser.wait('document.body.textContent.includes("Còn 10 mã dự phòng")'); screenshot(f'{width}-security')
            browser.evaluate('fetch("/api/me/security/lock",{method:"POST",headers:{Authorization:"Bearer "+localStorage.getItem("admin_token")}}).then(r=>r.json())')
            navigate('/admin/operations/branches'); submit_policy()
            browser.wait('document.querySelector("#step-up-code")'); screenshot(f'{width}-step-up')
            fill('#step-up-code', 'wrong'); click_text('Xác minh và tiếp tục')
            browser.wait('document.querySelector(".ant-modal-content [role=alert]")')
            with app.app_context(): before = BranchGeoPolicy.query.count()
            clock[0] += timedelta(seconds=31)
            fill('#step-up-code', current_code()); click_text('Xác minh và tiếp tục')
            browser.wait('!document.querySelector(".ant-modal-content") && !document.querySelector(".ant-drawer-open")')
            with app.app_context():
                assert BranchGeoPolicy.query.count() == before + 1
                assert BranchGeoPolicy.query.order_by(BranchGeoPolicy.id.desc()).first().settings['radius_m'] == att.DEFAULT_POLICY['radius_m']
            screenshot(f'{width}-policy-saved')
            print(f'PASS {width}px: setup/status, failed proof, preserved form, one policy write after proof', flush=True)
        with app.app_context(): assert db.session.get(StaffMFA, admin_id).enabled_at
        print('Screenshots: ' + str(artifacts), flush=True)
    except Exception:
        if browser:
            (artifacts / 'failure.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
            (artifacts / 'failure.txt').write_text(browser.evaluate('document.body.innerText'), encoding='utf-8')
        raise
    finally:
        if ws: ws.close()
        server.shutdown(); process.terminate(); process.wait(timeout=10)


if __name__ == '__main__': main()

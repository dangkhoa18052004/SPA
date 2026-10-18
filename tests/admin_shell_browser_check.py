"""Headless Chrome checks for the shared admin shell (UX-02, đợt 1).

Run after frontend build: python tests/admin_shell_browser_check.py
Uses an isolated in-memory database; no payments, SMTP or external services.
Covers: one shell for dashboard/CRM/reports/security/operations/profile per role, in-app navigation
without reload, Back, filters kept in the URL, expired session → login → same screen, responsive widths.
"""
import base64
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import websocket
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server, WSGIRequestHandler
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien

artifacts = ROOT / '.test-tmp' / ('admin-shell-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='admin-shell-browser-only-at-least-32-characters',
    ATTENDANCE_ENABLED=True, PAYROLL_V2_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True, BUSINESS_PORTAL_ENABLED=True,
    CRM_ENABLED=True, BI_REPORTS_ENABLED=True, GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False))
tokens = {}
with app.app_context():
    db.create_all()
    role = ChucVu(tencv='Test', dongiagio=30000)
    db.session.add(role); db.session.flush()
    for key, name in [('staff', 'Nguyễn Minh Anh'), ('manager', 'Trần Thanh Hà'), ('admin', 'Admin Bin Spa'), ('letan', 'Lê Thu Lễ Tân')]:
        staff = NhanVien(hoten=name, taikhoan=key, matkhau=generate_password_hash('matkhau-123'), macv=role.macv, role=key, trangthai=True)
        db.session.add(staff); db.session.flush()
        tokens[key] = create_access_token(identity=f'staff:{staff.manv}')
    tokens['expired'] = create_access_token(identity=f'staff:{staff.manv}', expires_delta=timedelta(seconds=-60))
    db.session.commit()
app.config['BROWSER_ROLE'] = 'admin'


@app.after_request
def test_bootstrap(response):
    if response.mimetype == 'text/html':
        token = tokens.get(app.config['BROWSER_ROLE'])  # role 'keep': leave what the page stored itself
        init = ('localStorage.setItem("admin_token",' + json.dumps(token) + ');') if token else ''
        init += 'window.__uiErrors=[];window.addEventListener("error",e=>{if(e.message)window.__uiErrors.push(e.message)});'
        init += 'window.addEventListener("unhandledrejection",e=>window.__uiErrors.push(String(e.reason)));'
        response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + init + '</script>', 1))
    return response


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=QuietHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
profile = artifacts / 'chrome-profile'
options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
process = subprocess.Popen([chrome, '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-allow-origins=*', '--remote-debugging-port=0', '--user-data-dir=' + str(profile), 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)


class Browser:
    def __init__(self):
        active = profile / 'DevToolsActivePort'
        for _ in range(100):
            if active.exists():
                break
            time.sleep(.1)
        port = int(active.read_text().splitlines()[0])
        targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
        target = next(t for t in targets if t['type'] == 'page')
        self.ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=20)
        self.index = 0
        self.call('Page.enable')

    def call(self, method, params=None):
        self.index += 1
        self.ws.send(json.dumps(dict(id=self.index, method=method, params=params or {})))
        while True:
            response = json.loads(self.ws.recv())
            if response.get('id') == self.index:
                if response.get('error'):
                    raise RuntimeError(response['error'])
                return response.get('result', {})

    def js(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
        if result.get('exceptionDetails'):
            raise AssertionError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression):
        for _ in range(20):  # the page may still be swapping documents right after a navigation
            try:
                return self._wait(expression)
            except RuntimeError as error:
                if 'navigated or closed' not in str(error):
                    raise
                time.sleep(.2)
        raise AssertionError('Page kept navigating: ' + expression)

    def _wait(self, expression):
        self.js("(async()=>{for(let n=0;n<200;n++){if(" + expression + ")return true;await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait: ' + " + json.dumps(expression) + ");})()")

    def navigate(self, path):
        self.call('Page.navigate', dict(url=base + path))
        self.wait("document.readyState==='complete' && document.querySelector('h1') && !document.querySelector('.ant-skeleton')")

    def viewport(self, width):
        self.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))

    def click(self, selector):
        self.js(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center",behavior:"instant"}})')
        time.sleep(.15)
        point = self.js(f'(()=>{{const e=document.querySelector({json.dumps(selector)}),r=e.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y);return {{x,y,covered:!(e===h||e.contains(h))}}}})()')
        assert not point['covered'], f'Element covered: {selector}'
        for kind in ['mousePressed', 'mouseReleased']:
            self.call('Input.dispatchMouseEvent', dict(type=kind, x=point['x'], y=point['y'], button='left', clickCount=1))

    def fill(self, selector, value):
        self.click(selector)
        self.call('Input.insertText', dict(text=value))

    def screenshot(self, label):
        self.wait("!document.querySelector('.ant-skeleton')")
        time.sleep(.4)
        state = self.js('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:window.__uiErrors})')
        assert state['scroll'] <= state['width'] + 1, (label, state)
        assert not state['errors'], (label, state)
        image = self.call('Page.captureScreenshot', dict(format='png'))['data']
        (artifacts / f'{label}.png').write_bytes(base64.b64decode(image))


browser = Browser()
try:
    shell = "document.querySelector('.admin-shell')"
    one_root = "document.querySelectorAll('#root').length===1 && document.querySelectorAll('.admin-shell').length===1"

    # Every existing React admin screen renders inside the same shell and menu.
    browser.viewport(1440)
    for path, heading in [('/admin/dashboard', 'Tổng quan công việc'), ('/admin/crm', 'Chăm sóc khách hàng'),
            ('/admin/reports', 'Kinh doanh và vận hành'), ('/admin/operations/payroll', None), ('/admin/profile', 'Trang cá nhân')]:
        browser.navigate(path)
        browser.wait(shell)
        assert browser.js(one_root), path
        if heading:
            assert heading in browser.js("document.querySelector('h1').textContent"), path
        if path != '/admin/profile':  # the profile lives in the account menu
            assert browser.js("document.querySelector('.admin-menu .ant-menu-item-selected') !== null"), path
        assert browser.js("document.querySelector('.admin-breadcrumb') !== null"), path
        browser.screenshot('admin' + path.replace('/', '-') + '-1440')

    # Menu moves between React screens without a page load, Back restores the previous one.
    browser.navigate('/admin/dashboard')
    browser.js('window.__sameDocument = true')
    # Only the active group starts open; open "Chăm sóc" first.
    browser.js("[...document.querySelectorAll('.admin-sidebar .ant-menu-submenu-title')].find(e=>e.textContent.includes('Chăm sóc')).click()")
    browser.wait("!!document.querySelector(\".admin-sidebar a[href='/admin/crm']\")")
    browser.js("document.querySelector(\".admin-menu a[href='/admin/crm']\").click()")
    browser.wait("location.pathname === '/admin/crm' && document.querySelector('h1')?.textContent.includes('Chăm sóc')")
    assert browser.js('window.__sameDocument === true'), 'menu caused a full reload'
    browser.wait("!document.querySelector('.ant-skeleton')")
    browser.js("document.querySelector('.crm-segments button').click()")
    browser.wait("location.search.includes('segment=')")
    segment_url = browser.js('location.pathname + location.search')
    browser.js('history.back()')
    browser.wait("location.pathname === '/admin/crm' && !location.search")
    browser.js('history.back()')
    browser.wait("location.pathname === '/admin/dashboard' && document.querySelector('h1')?.textContent.includes('Tổng quan')")
    assert browser.js('window.__sameDocument === true')
    browser.navigate(segment_url)  # reload keeps the filter
    browser.wait("document.querySelector('.crm-segments .ant-btn-primary')")

    # Collapsed sidebar is remembered.
    browser.click('.admin-topbar .desktop-only')
    browser.wait("document.querySelector('.admin-shell.is-collapsed')")
    browser.screenshot('admin-collapsed-1440')
    browser.navigate('/admin/dashboard')
    browser.wait("document.querySelector('.admin-shell.is-collapsed')")
    browser.click('.admin-topbar .desktop-only')

    # Each role sees its own menu and still the same shell.
    expected = {'admin': ['/admin/staff', '/admin/operations/payroll'], 'manager': ['/admin/operations/payroll'],
                'letan': ['/admin/appointments', '/admin/crm'], 'staff': ['/employee/appointments']}
    hidden = {'manager': ['/admin/staff'], 'letan': ['/admin/operations/payroll', '/admin/reports'], 'staff': ['/admin/appointments', '/admin/crm']}
    for role, links in expected.items():
        app.config['BROWSER_ROLE'] = role
        browser.navigate('/admin/profile')
        browser.wait(shell + " && document.querySelector('.profile-head')")
        # Collapsed groups do not render their links; open every group to compare.
        browser.js("document.querySelectorAll('.admin-sidebar .ant-menu-submenu:not(.ant-menu-submenu-open) > .ant-menu-submenu-title').forEach(e=>e.click())")
        time.sleep(.4)
        hrefs = browser.js("[...document.querySelectorAll('.admin-sidebar .admin-menu a')].map(a=>a.getAttribute('href'))")
        for link in links:
            assert link in hrefs, (role, link, hrefs)
        for link in hidden.get(role, []):
            assert link not in hrefs, (role, link)
        browser.screenshot(f'profile-{role}-1440')
    app.config['BROWSER_ROLE'] = 'staff'
    browser.call('Page.navigate', dict(url=base + '/admin/operations/payroll'))
    browser.wait("document.readyState==='complete' && document.body.textContent.includes('Không có quyền') && !!document.querySelector('.admin-shell')")

    # Profile: edit in a Drawer, validation, then change password with a wrong current password stays signed in.
    app.config['BROWSER_ROLE'] = 'manager'
    browser.navigate('/admin/profile')
    browser.js("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Sửa thông tin')).click()")
    browser.wait("document.querySelector('.ant-drawer-open input#hoten')")
    browser.js("document.querySelector('#hoten').select()")
    browser.call('Input.insertText', dict(text='Trần Thanh Hà Mới'))
    browser.js("document.querySelector('.ant-drawer-open button[type=submit]').click()")
    browser.wait("!document.querySelector('.ant-drawer-open') && document.body.textContent.includes('Trần Thanh Hà Mới')")
    browser.navigate('/admin/profile?tab=password')
    browser.wait("document.querySelector('#current')")
    browser.fill('#current', 'sai-mat-khau')
    browser.fill('#next', 'matkhau-moi-1')
    browser.fill('#confirm', 'matkhau-moi-1')
    browser.js("document.querySelector('.ant-tabs-tabpane-active button[type=submit]').click()")
    browser.wait("document.querySelector('[role=alert]') && document.querySelector('[role=alert]')?.textContent.includes('không chính xác')")
    assert browser.js("location.pathname === '/admin/profile' && !!localStorage.getItem('admin_token')")
    browser.screenshot('profile-password-error-1440')

    # Expired session → login with next → back to the same filtered screen.
    app.config['BROWSER_ROLE'] = 'expired'
    browser.call('Page.navigate', dict(url=base + '/admin/crm?segment=due'))
    browser.wait("location.pathname === '/admin/login' && document.querySelector('#taikhoan')")
    assert browser.js("new URLSearchParams(location.search).get('next')") == '/admin/crm?segment=due'
    assert 'hết hạn' in browser.js('document.body.textContent')
    browser.screenshot('login-expired-1440')
    app.config['BROWSER_ROLE'] = 'keep'
    browser.fill('#taikhoan', 'letan')
    browser.fill('#matkhau', 'matkhau-123')
    browser.js("document.querySelector('button[type=submit]').click()")
    browser.wait("location.pathname === '/admin/crm' && location.search === '?segment=due' && document.querySelector('.admin-shell')")

    # A plain login keeps landing on the personal page.
    browser.navigate('/admin/login')
    browser.fill('#taikhoan', 'letan')
    browser.fill('#matkhau', 'matkhau-123')
    browser.js("document.querySelector('button[type=submit]').click()")
    browser.wait("location.pathname === '/admin/profile' && document.querySelector('.profile-head')")

    # Responsive: no horizontal scroll, Drawer menu on small screens.
    app.config['BROWSER_ROLE'] = 'admin'
    for width in [360, 390, 768, 1024]:
        browser.viewport(width)
        for path in ['/admin/dashboard', '/admin/profile', '/admin/operations/attendance']:
            browser.navigate(path)
            browser.wait(shell)
            browser.screenshot(f'admin{path.replace("/", "-")}-{width}')
        if width < 992:
            browser.click('.admin-topbar .mobile-only')
            browser.wait("document.querySelector('.admin-drawer .admin-menu')")
            browser.screenshot(f'admin-drawer-{width}')

    # Logout clears the session.
    browser.viewport(1440)
    browser.navigate('/admin/dashboard')
    browser.click('.admin-account')
    browser.wait("[...document.querySelectorAll('.ant-dropdown-menu-item')].some(e=>e.textContent.includes('Đăng xuất'))")
    browser.js("[...document.querySelectorAll('.ant-dropdown-menu-item')].find(e=>e.textContent.includes('Đăng xuất')).click()")
    browser.wait("location.pathname === '/admin/login'")
    print('Admin shell browser check passed. Screenshots:', artifacts)
finally:
    process.terminate()
    server.shutdown()

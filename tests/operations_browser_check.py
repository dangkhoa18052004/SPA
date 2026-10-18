"""Headless Chrome exercises real Flask/React, GPS retry, review and payslip journeys.

Run after frontend build: python tests/operations_browser_check.py
Uses an isolated in-memory database, no payments, SMTP or external services.
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
from flask import request
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, CaLam, KhachHang, DichVu, LichHen, ChiTietLichHen
from app.operations_models import (Branch, BranchMembership, BranchGeoPolicy, AttendanceSession,
    AttendanceEvent, AttendancePeriod, PayrollPeriod)
from app.services import attendance_service as att, payroll_service as pay


artifacts = ROOT / '.test-tmp' / ('operations-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='operations-browser-only-at-least-32-characters',
    ATTENDANCE_ENABLED=True, PAYROLL_V2_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True,
    GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False))
tokens, staff_ids = {}, {}
with app.app_context():
    db.create_all()
    role = ChucVu(tencv='Test', dongiagio=30000)
    branch = Branch(name='Bin Spa · Tân Phú', address='Cơ sở kiểm thử')
    db.session.add_all([role, branch]); db.session.flush()
    for key, name in [('staff', 'Nguyễn Minh Anh'), ('manager', 'Trần Thanh Hà'), ('admin', 'Admin Bin Spa')]:
        staff = NhanVien(hoten=name, taikhoan=key, matkhau='hash', macv=role.macv, role=key, trangthai=True)
        db.session.add(staff); db.session.flush()
        tokens[key] = create_access_token(identity=f'staff:{staff.manv}')
        staff_ids[key] = staff.manv
        if not os.environ.get('BINSPA_BROWSER_SIMPLE'):
            db.session.add(BranchMembership(branch_id=branch.id, staff_id=staff.manv, can_manage=key != 'staff'))
    local = att.now_utc().astimezone(att.LOCAL)
    shift = CaLam(ngay=(local - timedelta(minutes=60)).date(), giobatdau=(local - timedelta(minutes=60)).time().replace(second=0, microsecond=0),
        gioketthuc=(local + timedelta(minutes=60)).time().replace(second=0, microsecond=0),
        sogio=2, hesoluong=1, branch_id=branch.id)
    db.session.add(shift); db.session.flush()
    if os.environ.get('BINSPA_BROWSER_SIMPLE'):
        shift.branch_id = None
        app.config.update(ATTENDANCE_SIMPLE_MODE=True, ATTENDANCE_BRANCH_ID=branch.id)
    else:
        app.config['ATTENDANCE_SIMPLE_MODE'] = False
        db.session.get(NhanVien, staff_ids['staff']).calam.append(shift)
    db.session.add(BranchGeoPolicy(branch_id=branch.id, version=1, settings=dict(att.DEFAULT_POLICY, enabled=True),
        created_by=staff_ids['admin']))
    db.session.commit()
    branch_id, shift_id, work_date = branch.id, shift.maca, shift.ngay
    customer = KhachHang(hoten='Khách hẹn của tôi', sdt='0900000010', taikhoan='ui_own_customer', matkhau='hash')
    foreign_customer = KhachHang(hoten='Khách hẹn nhân viên khác', sdt='0900000020', taikhoan='ui_foreign_customer', matkhau='hash')
    service = DichVu(tendv='Massage thư giãn', thoiluong=60, gia=300000, active=True)
    db.session.add_all([customer, foreign_customer, service]); db.session.flush()
    for when, status in [(local + timedelta(minutes=30), 'confirmed'), (local - timedelta(days=1), 'completed'),
            (local - timedelta(days=2), 'cancelled')]:
        booking = LichHen(makh=customer.makh, manv=staff_ids['staff'], ngaygio=when.replace(tzinfo=None),
            trangthai=status, ghichu='Khách yêu cầu phòng yên tĩnh; <script>không chạy mã</script>')
        db.session.add(booking); db.session.flush()
        db.session.add(ChiTietLichHen(malh=booking.malh, madv=service.madv))
    db.session.add(LichHen(makh=foreign_customer.makh, manv=staff_ids['manager'],
        ngaygio=(local + timedelta(minutes=45)).replace(tzinfo=None), trangthai='confirmed'))
    db.session.commit()
    app.config['PAYROLL_V2_CUTOVER_DATE'] = work_date.isoformat()

app.config['BROWSER_ROLE'] = 'staff'


@app.after_request
def test_bootstrap(response):
    if response.mimetype == 'text/html':
        init = 'localStorage.setItem("admin_token",' + json.dumps(tokens[app.config['BROWSER_ROLE']]) + ');'
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
        self.js("(async()=>{for(let n=0;n<200;n++){if(" + expression + ")return true;await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait: ' + " + json.dumps(expression) + ");})()")

    def navigate(self, path):
        self.call('Page.navigate', dict(url=base + path))
        self.wait("location.pathname === " + json.dumps(path) + " && document.querySelector('h1') && document.readyState==='complete'")

    def viewport(self, width):
        self.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))

    def click(self, selector):
        self.js(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center",behavior:"instant"}})')
        time.sleep(.15)
        point = self.js(f'(()=>{{const e=document.querySelector({json.dumps(selector)}),r=e.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y);return {{x,y,covered:!(e===h||e.contains(h)),hit:h?.outerHTML.slice(0,200),width:r.width,height:r.height}};}})()')
        assert not point['covered'], f'Element covered: {selector}: {point}'
        for kind in ['mousePressed', 'mouseReleased']:
            self.call('Input.dispatchMouseEvent', dict(type=kind, x=point['x'], y=point['y'], button='left', clickCount=1))

    def fill(self, selector, value):
        self.click(selector)
        self.call('Input.insertText', dict(text=value))

    def screenshot(self, label):
        self.wait("!document.querySelector('.ant-skeleton')")
        self.wait("document.getAnimations().every(a=>a.playState!=='running'||a.effect?.getComputedTiming().iterations===Infinity)")
        time.sleep(.2)
        state = self.js('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:window.__uiErrors})')
        assert state['scroll'] <= state['width'] + 1, (label, state)
        assert not state['errors'], (label, state)
        image = self.call('Page.captureScreenshot', dict(format='png'))['data']
        (artifacts / (label + '.png')).write_bytes(base64.b64decode(image))


browser = None
try:
    browser = Browser()
    browser.call('Browser.grantPermissions', dict(origin=base, permissions=['geolocation']))
    browser.call('Emulation.setGeolocationOverride', dict(latitude=att.DEFAULT_POLICY['latitude'], longitude=att.DEFAULT_POLICY['longitude'], accuracy=25))
    for width in [360, 390, 768, 1440]:
        browser.viewport(width); browser.navigate('/employee/appointments')
        browser.wait("document.body.textContent.includes('Khách hẹn của tôi')")
        assert not browser.js("document.body.textContent.includes('Khách hẹn nhân viên khác')")
        browser.screenshot(f'employee-appointments-{width}')
        selector = '.mobile-cards button' if width < 768 else '.desktop-table button'
        browser.click(selector)
        browser.wait("document.querySelector('.ant-drawer-content .appointment-note')")
        assert browser.js("document.querySelector('.appointment-note').textContent.includes('<script>')")
        assert not browser.js("document.querySelector('.appointment-note script') !== null")
        browser.screenshot(f'employee-appointment-detail-{width}')
    browser.viewport(390); browser.navigate('/employee/attendance')
    browser.wait("document.querySelector('.punch-button') && !document.querySelector('.punch-button').disabled")
    # The server accepts the first request; simulate losing just its response.
    browser.js("window.__gpsCalls=0;const gps=navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);navigator.geolocation.getCurrentPosition=(...args)=>{window.__gpsCalls++;gps(...args)};const fetchReal=window.fetch.bind(window);let drop=true;window.fetch=async (url,options)=>{const response=await fetchReal(url,options);if(drop&&String(url).endsWith('/api/attendance/check-in')){drop=false;throw new TypeError('Response lost in test')}return response};")
    browser.click('.punch-button')
    browser.wait("document.querySelector('.punch-button').textContent.includes('Gửi lại')")
    with app.app_context():
        assert AttendanceSession.query.count() == 1 and AttendanceEvent.query.count() == 1
    browser.click('.punch-button')
    browser.wait("document.querySelector('.recorded') && document.querySelector('.punch-button').textContent.includes('Chấm ra')")
    assert browser.js('window.__gpsCalls') == 1
    with app.app_context():
        assert AttendanceSession.query.count() == 1 and AttendanceEvent.query.count() == 1
    for width in [360, 390, 768, 1440]:
        browser.viewport(width); browser.screenshot(f'employee-today-{width}')
    browser.viewport(390); browser.click('.punch-button')
    browser.wait("document.body.textContent.includes('Chờ duyệt') && !document.querySelector('.punch-button')")
    if os.environ.get('BINSPA_BROWSER_SIMPLE'):
        with app.app_context():
            original_shift = db.session.get(CaLam, shift_id)
            another = CaLam(ngay=work_date, giobatdau=original_shift.giobatdau, gioketthuc=original_shift.gioketthuc, sogio=2, hesoluong=1)
            db.session.add(another); db.session.commit()
        browser.navigate('/employee/attendance')
        assert browser.js("document.querySelector('.profile-return').getAttribute('href')") == '/admin/profile'
        browser.wait("document.querySelector('.punch-request')")
        browser.click('.punch-request')
        browser.wait("document.querySelector('.ant-modal textarea')")
        browser.fill('.ant-modal textarea', 'Không lấy được vị trí, nhờ quản lý xác nhận giờ vào')
        browser.screenshot('employee-request-checkin-390')
        browser.click('.ant-modal button[type=submit]')
        browser.wait("!document.querySelector('.ant-modal textarea')")
        app.config['BROWSER_ROLE'] = 'manager'
        browser.navigate('/admin/operations/adjustments')
        browser.wait("document.querySelector('.list-grid button')")
        browser.click('.list-grid button')
        browser.wait("document.querySelector('.ant-drawer-content textarea')")
        browser.fill('.ant-drawer-content textarea', 'Đã thấy nhân viên có mặt tại cơ sở')
        browser.screenshot('manager-request-checkin-390')
        browser.click('.ant-drawer-content button[type=submit]')
        browser.wait("!document.querySelector('.ant-drawer-open')")
        app.config['BROWSER_ROLE'] = 'staff'
        browser.navigate('/employee/attendance')
        browser.wait("document.querySelector('.punch-button')?.textContent.includes('Chấm ra')")
        browser.click('.punch-button')
        browser.wait("!document.querySelector('.punch-button')")
    with app.app_context():
        completed = AttendanceSession.query.filter_by(staff_id=staff_ids['staff'], shift_id=shift_id).one()
        completed.actual_start = att.aware(completed.actual_end) - timedelta(hours=6)
        att.recompute(completed)
        db.session.commit()
    for screen in ['schedule', 'history', 'income', 'account']:
        browser.navigate('/employee/' + screen); browser.screenshot('employee-' + screen + '-390')
        if screen == 'income':
            assert browser.js("document.body.textContent.includes('Giờ thực tế đã chấm ra') && document.body.textContent.includes('Lương công tạm tính chờ duyệt')")
            assert browser.js("document.querySelector('.kpi-grid .ant-statistic-content').textContent.includes('6')")
    app.config['BROWSER_ROLE'] = 'manager'
    for width in [390, 768, 1440]:
        browser.viewport(width)
        for screen in ['dashboard', 'attendance', 'adjustments', 'payroll', 'branches', 'audit']:
            browser.navigate('/admin/operations/' + screen); browser.screenshot(f'manager-{screen}-{width}')
    browser.viewport(390); browser.navigate('/admin/operations/payroll')
    browser.click('.section-toolbar button')
    browser.js("window.__createModal=()=>[...document.querySelectorAll('.ant-modal-wrap')].find(e=>e.getBoundingClientRect().width>0&&e.querySelector('.ant-modal-title')?.textContent==='Tạo kỳ công')")
    browser.wait("window.__createModal()")
    browser.screenshot('manager-create-period-empty-390')
    for field in ['from_date', 'to_date']:
        browser.js("(()=>{const input=window.__createModal().querySelector('input[id=" + field + "]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input," + json.dumps(work_date.isoformat()) + ");input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));})()")
        browser.wait("window.__createModal().querySelector('input[id=" + field + "]').value === " + json.dumps(work_date.isoformat()))
    browser.screenshot('manager-create-period-390')
    browser.js("window.__createModal().setAttribute('data-test-create','1')")
    browser.click('[data-test-create="1"] button[type=submit]')
    browser.wait("!window.__createModal() && document.body.textContent.includes('Chờ duyệt:')")
    browser.screenshot('manager-period-readiness-390')
    browser.navigate('/admin/operations/attendance')
    browser.wait("document.querySelector('.mobile-review-button')")
    browser.click('.mobile-review-button')
    browser.wait("document.querySelector('.ant-drawer-content textarea')")
    browser.fill('.ant-drawer-content textarea', 'Đã đối chiếu nhân viên có mặt đủ ca')
    browser.screenshot('manager-review-drawer-390')
    browser.click('.ant-drawer-content button[type=submit]')
    browser.wait("!document.querySelector('.ant-drawer-open') && document.body.textContent.includes('Đã duyệt')")
    original_now = att.now_utc
    att.now_utc = lambda: original_now() + timedelta(days=2)
    with app.app_context():
        admin = db.session.get(NhanVien, staff_ids['admin'])
        manager = db.session.get(NhanVien, staff_ids['manager'])
        for submitted in AttendanceSession.query.filter_by(approval_status='SUBMITTED').all():
            att.approve_session(manager, submitted, dict(version=submitted.version,
                paid_minutes=120, overtime_minutes=0, reason='Đối chiếu phiên chấm công bổ sung trong kiểm thử'))
        db.session.commit()
        period = pay.create_attendance_period(admin, dict(branch_id=branch_id, from_date=work_date.isoformat(), to_date=work_date.isoformat()))
        pay.lock_attendance_period(admin, period, 'Đã đối chiếu kỳ công trong kiểm thử')
        payroll = pay.build_payroll(admin, period)
        db.session.commit()
        pay.transition(manager, payroll, dict(version=payroll.version, reason='Kiểm tra bảng lương bởi người khác'), 'approve')
        db.session.commit()
        pay.transition(admin, payroll, dict(version=payroll.version, reason='Chốt phiếu lương kiểm thử'), 'lock')
        db.session.commit()
    app.config['BROWSER_ROLE'] = 'staff'
    browser.navigate('/employee/income')
    browser.wait("document.body.textContent.includes('Xem phiếu lương')")
    browser.js("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Xem phiếu lương')).click()")
    browser.wait("document.querySelector('.payslip')")
    browser.screenshot('employee-payslip-390')
    print(json.dumps(dict(result='passed', screenshots=len(list(artifacts.glob('*.png'))), artifacts=str(artifacts)), ensure_ascii=False))
finally:
    if browser:
        browser.ws.close()
    process.terminate()
    process.wait(timeout=10)
    server.shutdown()

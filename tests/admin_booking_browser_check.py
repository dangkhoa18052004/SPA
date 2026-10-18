"""Headless Chrome: appointments and customers on the shared React admin shell (đợt 2).

Run after frontend build: python tests/admin_booking_browser_check.py
In-memory database, fake email, no payment provider: cash only; VietQR is not contacted.
Journey: desk books (walk-in + package session), lost response is reconciled without a duplicate,
confirm → check-in → complete → invoice → cash with change → receipt; change services; cancel;
role-based buttons; filters in the URL; 360–1440 px without horizontal scroll.
"""
import base64
from datetime import datetime, time as dtime, timedelta
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
from werkzeug.serving import make_server, WSGIRequestHandler
from app import create_app
from app.extensions import db
from app.models import (ChucVu, NhanVien, KhachHang, DichVu, CaLam, nhanvien_calam, LichHen, ChiTietLichHen, HoaDon,
                        ThanhToan, LieuTrinhUsage)
from app.services import appointment_service, email_service, package_service as ps

artifacts = ROOT / '.test-tmp' / ('admin-booking-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='admin-booking-browser-only-at-least-32-characters',
    BUSINESS_PORTAL_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=False, CRM_ENABLED=False,
    BI_REPORTS_ENABLED=False, AI_CHAT_JOBS_ENABLED=False, GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False))
appointment_service.send_appointment_confirmation_email_async = lambda *args: None
email_service.send_email = lambda *args, **kwargs: True

with app.app_context():
    db.create_all()
    position = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
    db.session.add(position); db.session.flush()
    customer = KhachHang(hoten='Nguyễn Thị Hoa', sdt='0901111222', taikhoan='hoa', matkhau='hash', email='hoa@example.test', trangthai='active')
    actors = {role: NhanVien(hoten=f'Kiểm thử {role}', taikhoan=role, matkhau='hash', macv=position.macv, role=role, trangthai=True)
              for role in ('staff', 'manager', 'admin', 'letan')}
    massage = DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=60, active=True)
    facial = DichVu(tendv='Chăm sóc da', gia=500000, thoiluong=90, active=True)
    hair = DichVu(tendv='Gội đầu dưỡng sinh', gia=250000, thoiluong=30, active=True)
    db.session.add_all([customer, *actors.values(), massage, facial, hair]); db.session.flush()
    now = ps.local_now()
    today, day = now.date(), now.date() + timedelta(days=3)
    for target in (today, day):
        shift = CaLam(ngay=target, giobatdau=dtime(7), gioketthuc=dtime(20), sogio=13)
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=actors['staff'].manv, maca=shift.maca))
    package = ps.save_package(dict(tengoi='Combo thư giãn 5 buổi', giagoi=1200000, validity_months=6,
                                  items=[dict(madv=massage.madv, total_sessions=5)]))
    purchase = ps.create_purchase(package.magoi, customer.makh, 'cash')
    _, treatment, _ = ps.confirm_purchase(purchase.id, 1200000, method='cash')
    journey = {}
    for key, hour, svc in (('pay', 7, facial), ('change', 9, hair), ('cancel', 11, hair)):
        apt = LichHen(makh=customer.makh, manv=actors['staff'].manv, ngaygio=datetime.combine(today, dtime(hour)), trangthai='pending')
        db.session.add(apt); db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=svc.madv))
        journey[key] = apt.malh
    db.session.commit()
    ids = dict(customer=customer.makh, massage=massage.madv, facial=facial.madv, hair=hair.madv, staff=actors['staff'].manv)
    tokens = {role: create_access_token(identity=f'staff:{person.manv}') for role, person in actors.items()}
day_iso = day.isoformat()
app.config['BROWSER_ROLE'] = 'letan'


@app.after_request
def bootstrap(response):
    if response.mimetype == 'text/html':
        init = 'localStorage.setItem("admin_token",' + json.dumps(tokens[app.config['BROWSER_ROLE']]) + ');'
        init += 'window.__uiErrors=[];window.addEventListener("error",e=>{if(e.message)window.__uiErrors.push(e.message)});'
        init += 'window.addEventListener("unhandledrejection",e=>window.__uiErrors.push(String(e.reason)));'
        response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + init + '</script>', 1))
    return response


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


# sqlite:// shares one connection between the server and this script: never query while a request runs.
db_lock = threading.Lock()


def serve_locked(environ, start_response):
    with db_lock:
        return list(app(environ, start_response))


def query(fn):
    with db_lock, app.app_context():
        return fn()


server = make_server('127.0.0.1', 0, serve_locked, threaded=False, request_handler=QuietHandler)
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
            try:
                port = int(active.read_text().splitlines()[0]); break
            except (OSError, IndexError, ValueError):
                time.sleep(.1)
        targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
        target = next(t for t in targets if t['type'] == 'page')
        self.ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=30)
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
            raise AssertionError(result['exceptionDetails'].get('exception', {}).get('description') or result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression, label=None):
        for _ in range(20):
            try:
                return self.js("(async()=>{for(let n=0;n<240;n++){try{if(" + expression + ")return true;}catch(e){}"
                               "await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait: ' + " + json.dumps(label or expression) + ");})()")
            except RuntimeError as error:
                if 'navigated or closed' not in str(error):
                    raise
                time.sleep(.2)

    def navigate(self, path):
        self.call('Page.navigate', dict(url=base + path))
        self.wait("document.readyState==='complete' && document.querySelector('.admin-shell h1') && !document.querySelector('.ant-skeleton')", 'page ' + path)

    def viewport(self, width):
        self.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))

    def click(self, selector):
        for attempt in range(20):  # drawers/modals animate in; wait until the target is on top
            self.js(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center",behavior:"instant"}})')
            time.sleep(.15)
            point = self.js(f'(()=>{{const e=document.querySelector({json.dumps(selector)}),r=e.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y);return {{x,y,covered:!(e===h||e.contains(h)||h?.contains(e))}}}})()')
            if not point['covered']:
                break
        assert not point['covered'], f'Element covered: {selector}'
        for kind in ['mousePressed', 'mouseReleased']:
            self.call('Input.dispatchMouseEvent', dict(type=kind, x=point['x'], y=point['y'], button='left', clickCount=1))

    def button(self, text, scope='document'):
        """Click the first visible button whose text contains `text`."""
        found = self.js(f"""(()=>{{const b=[...{scope}.querySelectorAll('button')].find(b=>b.offsetParent&&b.textContent.includes({json.dumps(text)})&&!b.disabled);
            if(!b)return false;b.setAttribute('data-click-target','1');return true}})()""")
        assert found, f'button not found: {text}'
        self.click('[data-click-target="1"]')
        self.js("document.querySelector('[data-click-target]')?.removeAttribute('data-click-target')")

    def type(self, selector, value):
        self.click(selector)
        self.js(f"document.querySelector({json.dumps(selector)}).select?.()")
        self.call('Input.insertText', dict(text=value))

    def key(self, name, code):
        for kind in ['keyDown', 'keyUp']:
            self.call('Input.dispatchKeyEvent', dict(type=kind, key=name, code=name, windowsVirtualKeyCode=code))

    def choose(self, aria, text):
        """Pick an antd Select option by typing into its search box."""
        selector = f'input[aria-label="{aria}"]'
        self.wait(f"document.querySelector({json.dumps(selector)})", aria)
        self.js(f"document.querySelector({json.dumps(selector)}).closest('.ant-select').querySelector('.ant-select-selector').dispatchEvent(new MouseEvent('mousedown',{{bubbles:true}}))")
        if not self.js(f"document.querySelector({json.dumps(selector)}).readOnly"):  # searchable select
            self.click(selector)
            self.call('Input.insertText', dict(text=text))
        self.wait(f"[...document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')].some(o=>o.textContent.includes({json.dumps(text)}))", 'option ' + text)
        self.js(f"""(()=>{{const o=[...document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')]
            .find(o=>o.textContent.includes({json.dumps(text)}));o.click()}})()""")
        self.js("document.activeElement?.blur?.()")
        time.sleep(.2)

    def date(self, aria, value):
        self.js(f"""(()=>{{const i=document.querySelector('input[aria-label="{aria}"]');
            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(i,{json.dumps(value)});
            i.dispatchEvent(new Event('input',{{bubbles:true}}));i.dispatchEvent(new Event('change',{{bubbles:true}}));}})()""")

    def confirm_modal(self, text):
        self.wait("document.querySelector('.ant-modal-confirm')", 'confirm dialog')
        self.button(text, "document.querySelector('.ant-modal-confirm')")
        self.wait("!document.querySelector('.ant-modal-confirm')", 'confirm closed')

    def screenshot(self, label):
        self.wait("!document.querySelector('.ant-skeleton')")
        time.sleep(.4)
        state = self.js('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:window.__uiErrors})')
        assert state['scroll'] <= state['width'] + 1, (label, state)
        assert not state['errors'], (label, state)
        image = self.call('Page.captureScreenshot', dict(format='png'))['data']
        (artifacts / f'{label}.png').write_bytes(base64.b64decode(image))


def appointment_count():
    return query(lambda: LichHen.query.count())


browser = Browser()
try:
    browser.viewport(1440)
    browser.navigate('/admin/appointments')
    assert browser.js("document.querySelectorAll('#root').length===1 && !!document.querySelector('.admin-menu .ant-menu-item-selected')")
    browser.wait("document.body.textContent.includes('Nguyễn Thị Hoa')", 'today list')
    browser.screenshot('appointments-letan-1440')

    # 1. Walk-in customer created from the booking drawer, regular service.
    before = appointment_count()
    browser.click('[data-testid="appointment-new"]')
    browser.wait("document.querySelector('.ant-drawer-open input[aria-label=\"Khách hàng\"]')", 'booking drawer')
    browser.button('Thêm khách vãng lai', "document.querySelector('.ant-drawer-open')")
    browser.wait("document.querySelector('.ant-modal input#hoten')", 'quick add')
    browser.type('.ant-modal input#hoten', 'Khách Vãng Lai Test')
    browser.type('.ant-modal input#sdt', '0909888777')
    browser.button('Lưu khách hàng', "document.querySelector('.ant-modal')")
    browser.wait("document.querySelector('.ant-drawer-open .ant-select-selection-item')?.textContent.includes('Khách Vãng Lai Test')", 'walk-in selected')
    browser.choose('Dịch vụ', 'Gội đầu')
    browser.date('Ngày hẹn', day_iso)
    browser.choose('Giờ hẹn', '10:00')
    browser.wait("document.querySelector('[data-testid=booking-quote]').textContent.includes('250.000')", 'quote 250k')
    browser.wait("!document.querySelector('.ant-drawer-open .ant-select-disabled input[aria-label=\"Nhân viên\"]')", 'staff loaded')
    browser.screenshot('booking-walkin-1440')
    browser.click('[data-testid="booking-save"]')
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Chi tiết lịch hẹn')", 'detail after create')
    assert appointment_count() == before + 1
    walkin = query(lambda: KhachHang.query.filter_by(sdt='0909888777').one().makh)
    browser.js("document.querySelector('.ant-drawer-open .ant-drawer-close').click()")
    browser.wait("!document.querySelector('.ant-drawer-open')")

    # 2. Package session + paid extra service: only the extra service is charged.
    browser.click('[data-testid="appointment-new"]')
    browser.choose('Khách hàng', '0901111222')
    browser.wait("[...document.querySelectorAll('.ant-segmented-item')].some(e=>e.textContent.includes('gói'))", 'method switch')
    browser.js("[...document.querySelectorAll('.ant-segmented-item')].find(e=>e.textContent.includes('gói')).click()")
    browser.wait("document.querySelector('.booking-treatment-item input:not([disabled])')", 'treatments')
    browser.date('Ngày hẹn', day_iso)
    browser.js("document.querySelector('.booking-treatment-item input:not([disabled])').click()")
    browser.choose('Dịch vụ', 'Chăm sóc da')
    browser.choose('Giờ hẹn', '13:00')
    browser.wait("document.querySelector('[data-testid=booking-quote]').textContent.includes('500.000') && document.querySelector('[data-testid=booking-quote]').textContent.includes('Giá gốc')", 'package quote')
    browser.screenshot('booking-package-1440')
    browser.click('[data-testid="booking-save"]')
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Đã giữ buổi')", 'package reserved in detail')
    assert query(lambda: LieuTrinhUsage.query.filter_by(state='reserved').count()) == 1
    browser.js("document.querySelector('.ant-drawer-open .ant-drawer-close').click()")

    # 3. Lost response: the request reaches the server, the reply is dropped; reconciliation finds it.
    before = appointment_count()
    browser.js("""(()=>{const real=window.fetch;window.fetch=async(url,opts)=>{const r=await real(url,opts);
        if(String(url)==='/api/admin/appointments'&&opts?.method==='POST'){window.fetch=real;throw new TypeError('Failed to fetch');}return r;};})()""")
    browser.click('[data-testid="appointment-new"]')
    browser.choose('Khách hàng', '0909888777')
    browser.choose('Dịch vụ', 'Massage')
    browser.date('Ngày hẹn', day_iso)
    browser.choose('Giờ hẹn', '16:00')
    browser.wait("!document.querySelector('.ant-drawer-open .ant-select-disabled input[aria-label=\"Nhân viên\"]')", 'staff loaded 2')
    browser.click('[data-testid="booking-save"]')
    browser.wait("document.body.textContent.includes('đã được tạo trước đó')", 'reconciled')
    assert appointment_count() == before + 1, 'lost response must not create a second appointment'
    browser.js("document.querySelector('.ant-drawer-open .ant-drawer-close')?.click()")

    # 4. Filters live in the URL; Back restores them.
    browser.navigate('/admin/appointments')
    browser.choose('Khoảng thời gian', 'Hôm nay')
    browser.wait("location.search.includes('range=today')")
    browser.js("document.querySelector('input[aria-label=\"Tìm lịch hẹn\"]').focus()")
    browser.call('Input.insertText', dict(text='gội'))
    browser.key('Enter', 13)
    browser.wait("location.search.includes('q=')")
    browser.wait("document.querySelectorAll('.desktop-table tbody tr.ant-table-row').length===2", 'two hair bookings today')
    browser.js('history.back()')
    browser.wait("!location.search.includes('q=') && location.search.includes('range=today')")
    browser.navigate(f"/admin/appointments?makh={walkin}")
    browser.wait("document.body.textContent.includes('Đang xem lịch của khách') && document.querySelectorAll('.desktop-table tbody tr.ant-table-row').length===2", 'customer filter')

    # 5. Desk journey on today's booking: confirm → check-in → complete → invoice → cash → receipt.
    pay = journey['pay']
    browser.navigate('/admin/appointments?range=today')
    row = f"tr[data-row-key='{pay}']"
    for label, ok in (('Xác nhận', 'Xác nhận'), ('Check-in', 'Check-in'), ('Hoàn thành', 'Hoàn thành')):
        browser.wait(f"[...document.querySelectorAll(\"{row} button\")].some(b=>b.textContent.includes('{label}'))", label)
        browser.button(label, f'document.querySelector("{row}")')
        browser.confirm_modal(ok)
    browser.wait(f"[...document.querySelectorAll(\"{row} button\")].some(b=>b.textContent.includes('Tạo hóa đơn'))", 'create invoice')
    browser.button('Tạo hóa đơn', f'document.querySelector("{row}")')
    browser.wait("document.querySelector('[data-testid=invoice-payable]')?.textContent.includes('500.000')", 'payment modal')
    browser.screenshot('invoice-payment-1440')
    browser.button('Tiền mặt', "document.querySelector('.ant-modal')")
    browser.type('#cash-received', '600000')
    browser.wait("document.querySelector('[data-testid=cash-change]').textContent.includes('100.000')", 'change shown')
    browser.button('Xác nhận đã thu tiền', "document.querySelector('.ant-modal')")
    browser.wait("!document.querySelector('.ant-modal-wrap:not([style*=\"display: none\"]) [data-testid=invoice-payable]')", 'payment closed')
    invoice = query(lambda: (lambda h: (h.trangthai, ThanhToan.query.filter_by(mahd=h.mahd).count()))(HoaDon.query.filter_by(malh=pay).one()))
    assert invoice == ('Đã thanh toán', 1), invoice
    browser.wait(f"[...document.querySelectorAll(\"{row} button\")].some(b=>b.textContent.includes('Xem hóa đơn'))", 'view invoice')
    browser.button('Xem hóa đơn', f'document.querySelector("{row}")')
    browser.wait("document.querySelector('.ant-modal .receipt')?.textContent.includes('Tiền thối')", 'receipt')
    browser.screenshot('receipt-1440')
    browser.button('Đóng', "document.querySelector('.ant-modal')")

    # 6. Change services keeps time/staff and saves once.
    change = journey['change']
    browser.button('Đổi dịch vụ', f"document.querySelector(\"tr[data-row-key='{change}']\")")
    browser.wait(f"document.querySelector('[data-toggle=\"{ids['massage']}\"]')", 'change dialog')
    browser.click(f"[data-toggle=\"{ids['massage']}\"]")
    browser.wait("document.querySelector('.cs-compare-react').textContent.includes('550.000')", 'after total')
    browser.screenshot('change-services-1440')
    browser.button('Lưu thay đổi', "document.querySelector('.ant-modal')")
    browser.wait("!document.querySelector('.cs-compare-react')")
    assert query(lambda: sorted(d.madv for d in db.session.get(LichHen, change).chitiet)) == sorted([ids['hair'], ids['massage']])

    # 7. Cancel with a reason.
    cancel = journey['cancel']
    browser.button('Hủy', f"document.querySelector(\"tr[data-row-key='{cancel}']\")")
    browser.wait("document.querySelector('.ant-modal-confirm textarea')")
    browser.type('.ant-modal-confirm textarea', 'Khách báo bận')
    browser.confirm_modal('Hủy lịch')
    assert query(lambda: db.session.get(LichHen, cancel).trangthai) == 'cancelled'

    # 8. Customers: front desk sees quick add only; manager may edit and lock.
    browser.navigate('/admin/customers')
    browser.wait("document.body.textContent.includes('Khách Vãng Lai Test')")
    assert not browser.js("[...document.querySelectorAll('.desktop-table button')].some(b=>/Sửa|Khóa/.test(b.textContent))"), 'letan must not see edit/lock'
    assert browser.js("[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Khách vãng lai'))")
    browser.button('Hồ sơ', f"document.querySelector(\"tr[data-row-key='{ids['customer']}']\")")
    browser.wait("location.search.includes('view=') && document.querySelector('.ant-drawer-open .profile-head')", 'profile')
    browser.js("[...document.querySelectorAll('.ant-drawer-open .ant-tabs-tab')].find(t=>t.textContent.includes('Liệu trình')).click()")
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Combo thư giãn')", 'treatments tab')
    browser.screenshot('customer-profile-1440')
    app.config['BROWSER_ROLE'] = 'manager'
    browser.navigate('/admin/customers?q=0909888777')
    browser.wait(f"document.querySelector(\"tr[data-row-key='{walkin}']\")")
    browser.button('Khóa', f"document.querySelector(\"tr[data-row-key='{walkin}']\")")
    browser.confirm_modal('Khóa')
    browser.wait(f"document.querySelector(\"tr[data-row-key='{walkin}']\").textContent.includes('Đã khóa')")
    assert query(lambda: db.session.get(KhachHang, walkin).trangthai) == 'blocked'
    browser.button('Sửa', f"document.querySelector(\"tr[data-row-key='{walkin}']\")")
    browser.wait("document.querySelector('.ant-drawer-open input#hoten')")
    browser.type('.ant-drawer-open input#hoten', 'Khách Đã Đổi Tên')
    browser.js("document.querySelector('.ant-drawer-open button[type=submit]').click()")
    browser.wait("!document.querySelector('.ant-drawer-open input#hoten')")
    assert query(lambda: db.session.get(KhachHang, walkin).hoten) == 'Khách Đã Đổi Tên'

    # 9. Staff see only their own schedule and no desk actions.
    app.config['BROWSER_ROLE'] = 'staff'
    browser.navigate('/admin/appointments')
    browser.wait("document.querySelector('h1').textContent.includes('Lịch hẹn của tôi')")
    assert not browser.js("!!document.querySelector('[data-testid=appointment-new]')")
    browser.call('Page.navigate', dict(url=base + '/admin/customers'))
    browser.wait("document.body.textContent.includes('Không có quyền')", 'staff blocked from customers')

    # 10. Responsive: no horizontal scroll, cards on small screens.
    app.config['BROWSER_ROLE'] = 'letan'
    for width in [360, 390, 768, 1024]:
        browser.viewport(width)
        browser.navigate('/admin/appointments?range=today')
        browser.wait("document.body.textContent.includes('Nguyễn Thị Hoa')")
        browser.screenshot(f'appointments-{width}')
        browser.click('[data-testid="appointment-new"]')
        browser.wait("document.querySelector('.ant-drawer-open input[aria-label=\"Khách hàng\"]')")
        browser.screenshot(f'booking-drawer-{width}')
        browser.navigate('/admin/customers')
        browser.screenshot(f'customers-{width}')
    print('Admin booking browser check passed. Screenshots:', artifacts)
finally:
    process.terminate()
    server.shutdown()

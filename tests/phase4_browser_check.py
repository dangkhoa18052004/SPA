"""Phase 4 real-browser journeys, isolated SQLite, mocked mail and synthetic payments.

Run after frontend build: python tests/phase4_browser_check.py
Chrome + websocket-client required. No SMTP, Gemini or bank service is called.
"""
import base64
from datetime import datetime, timedelta, time as day_time
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
from flask import session
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler
from app import create_app
from app.extensions import db
from app.models import (ChucVu, NhanVien, KhachHang, DichVu, CaLam, nhanvien_calam,
                        LichHen, ChiTietLichHen, HoaDon, ThanhToan, LieuTrinhUsage)
from app.services import package_service as ps, appointment_service, email_service

artifacts = ROOT / '.test-tmp' / ('phase4-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    AI_CHAT_JOBS_ENABLED=False,
    SECRET_KEY='phase4-only-session-secret', JWT_SECRET_KEY='phase4-only-jwt-secret-at-least-32-chars',
    BUSINESS_PORTAL_ENABLED=True, CUSTOMER_BOOKING_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True,
    ATTENDANCE_ENABLED=False, ATTENDANCE_SIMPLE_MODE=False, PAYROLL_V2_ENABLED=False,
    GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False, SEPAY_API_KEY='phase4-synthetic-webhook',
    VIETQR_BANK_ID='970416', VIETQR_ACCOUNT_NO='123456', VIETQR_ACCOUNT_NAME='TEST SPA'))
appointment_service.send_appointment_confirmation_email_async = lambda *args: None
email_service.send_email = lambda *args, **kwargs: True

with app.app_context():
    db.create_all()
    position = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
    db.session.add(position); db.session.flush()
    customer = KhachHang(hoten='Khách kiểm thử', taikhoan='customer', matkhau='hash', email='test@example.test', trangthai='active')
    other = KhachHang(hoten='Khách của nhân viên khác', taikhoan='other', matkhau='hash', trangthai='active')
    actors = {role: NhanVien(hoten='Kiểm thử ' + role, taikhoan=role, matkhau='hash', macv=position.macv, role=role, trangthai=True)
              for role in ('staff', 'manager', 'admin', 'letan')}
    second = NhanVien(hoten='Nhân viên khác', taikhoan='second', matkhau='hash', macv=position.macv, role='staff', trangthai=True)
    massage = DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=60, active=True)
    facial = DichVu(tendv='Chăm sóc da', gia=500000, thoiluong=90, active=True)
    hair = DichVu(tendv='Gội đầu dưỡng sinh', gia=250000, thoiluong=30, active=True)
    db.session.add_all([customer, other, *actors.values(), second, massage, facial, hair]); db.session.flush()
    now = ps.local_now()
    day = now.date() + timedelta(days=3)
    for target in (now.date(), day, day + timedelta(days=1)):
        shift = CaLam(ngay=target, giobatdau=day_time(8), gioketthuc=day_time(18), sogio=10)
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=actors['staff'].manv, maca=shift.maca))
    for hour, state, person, owner in ((9, 'pending', customer, actors['staff']), (11, 'in_progress', customer, actors['staff']),
                                       (13, 'completed', customer, actors['staff']), (15, 'confirmed', other, second)):
        apt = LichHen(makh=person.makh, manv=owner.manv, ngaygio=datetime.combine(now.date(), day_time(hour)), trangthai=state)
        db.session.add(apt); db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=massage.madv))
    package = ps.save_package(dict(tengoi='Combo thư giãn 5 buổi', giagoi=1200000, validity_months=6,
                                  items=[dict(madv=massage.madv, total_sessions=5)]))
    purchase = ps.create_purchase(package.magoi, customer.makh, 'cash')
    _, treatment, _ = ps.confirm_purchase(purchase.id, 1200000, method='cash')
    _, gift = ps.gift_service(treatment.mathe, dict(madv=facial.madv, quantity=1, validity_days=7), actors['staff'])
    invoice = HoaDon(makh=customer.makh, manv=actors['staff'].manv, tongtien=300000, trangthai='Đã thanh toán')
    db.session.add(invoice); db.session.flush()
    db.session.add(ThanhToan(mahd=invoice.mahd, sotien=300000, phuongthuc='Tiền mặt', ngaythanhtoan=now))
    db.session.commit()
    customer_id, massage_id, facial_id, hair_id = customer.makh, massage.madv, facial.madv, hair.madv
    treatment_id, package_item, gift_item = treatment.mathe, treatment.items[0].id, gift.id
    customer_token = create_access_token(identity=f'customer:{customer.makh}')
    tokens = {role: create_access_token(identity=f'staff:{person.manv}') for role, person in actors.items()}
app.config['BROWSER_ROLE'] = 'admin'
app.config['BROWSER_GUEST'] = False

@app.before_request
def bootstrap_session():
    if app.config['BROWSER_GUEST']:
        session.clear()
    else:
        session.update(user_id=customer_id, user_type='customer')

@app.after_request
def bootstrap_tokens(response):
    if response.mimetype == 'text/html':
        init = ('window.__uiErrors=[];window.__requests=[];window.addEventListener("error",e=>{if(e.message)__uiErrors.push(e.message)});'
                'window.addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
                'const nativeFetch=window.fetch.bind(window);window.fetch=(url,...rest)=>{window.__requests.push(String(url));return nativeFetch(url,...rest)};')
        init += 'localStorage.setItem("admin_token",' + json.dumps(tokens[app.config['BROWSER_ROLE']]) + ');'
        init += ('localStorage.removeItem("access_token");' if app.config['BROWSER_GUEST'] else 'localStorage.setItem("access_token",' + json.dumps(customer_token) + ');')
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
process = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run',
    '--no-default-browser-check', '--remote-allow-origins=*', '--remote-debugging-port=0',
    '--user-data-dir=' + str(profile), 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class Browser:
    def __init__(self):
        active = profile / 'DevToolsActivePort'
        port = None
        for _ in range(100):
            try:
                port = int(active.read_text().splitlines()[0])
                break
            except (OSError, ValueError, IndexError):
                pass
            time.sleep(.1)
        if port is None:
            raise RuntimeError('Chrome did not expose a readable DevTools port: ' + str(active))
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
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression):
        self.js('(async()=>{for(let i=0;i<200;i++){if(' + expression + ')return true;await new Promise(r=>setTimeout(r,50));}throw new Error(' + json.dumps(expression) + ')})()')

    def navigate(self, path):
        self.call('Page.navigate', dict(url=base + path))
        self.wait('location.pathname===' + json.dumps(path.split('?')[0]) + '&&document.readyState==="complete"')

    def viewport(self, width):
        self.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))

    def click(self, selector):
        self.js('document.querySelector(' + json.dumps(selector) + ').scrollIntoView({block:"center",behavior:"instant"})')
        time.sleep(.2)
        point = self.js('(()=>{const e=document.querySelector(' + json.dumps(selector) + '),r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,hit=document.elementFromPoint(x,y);return {x,y,covered:!(hit===e||e.contains(hit))}})()')
        assert not point['covered'], (selector, point)
        for kind in ('mousePressed', 'mouseReleased'):
            self.call('Input.dispatchMouseEvent', dict(type=kind, x=point['x'], y=point['y'], button='left', clickCount=1))

    def set_value(self, selector, value, kind='input'):
        self.js('(()=>{const e=document.querySelector(' + json.dumps(selector) + ');Object.getOwnPropertyDescriptor(' + ('HTMLSelectElement' if kind == 'select' else 'HTMLInputElement') + '.prototype,"value").set.call(e,' + json.dumps(value) + ');e.dispatchEvent(new Event(' + json.dumps('change' if kind == 'select' else 'input') + ',{bubbles:true}));})()')

    def screenshot(self, name):
        self.wait('!document.querySelector(".ant-skeleton")')
        time.sleep(.3)
        state = self.js('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:window.__uiErrors})')
        assert state['scroll'] <= state['width'] + 1 and not state['errors'], (name, state)
        data = self.call('Page.captureScreenshot', dict(format='png'))['data']
        (artifacts / (name + '.png')).write_bytes(base64.b64decode(data))

browser = None
try:
    browser = Browser()
    for width in (360, 390, 768, 1440):
        browser.viewport(width)
        for role in ('admin', 'manager', 'letan', 'staff'):
            app.config['BROWSER_ROLE'] = role
            browser.navigate('/admin/dashboard')
            browser.wait('document.body.textContent.includes("Lịch khách của tôi hôm nay")' if role == 'staff' else 'document.body.textContent.includes("Lịch hẹn hôm nay")')
            browser.wait('!document.querySelector(".ant-skeleton")')
            if role in ('admin', 'manager'):
                browser.wait('document.querySelector("[data-testid=business-finance]")?.textContent.includes("1.500.000")')
                assert browser.js('document.querySelector("[data-testid=business-finance]").textContent.includes("1.200.000")')
            else:
                assert not browser.js('window.__requests.some(url=>url.startsWith("/api/analytics/"))')
                assert not browser.js('document.querySelector("[data-testid=business-finance]")')
            if role == 'staff':
                assert not browser.js('document.body.textContent.includes("Khách của nhân viên khác")')
            browser.screenshot(f'{width}-dashboard-{role}')
            if role == 'admin':
                browser.set_value('[aria-label="Tìm lịch hẹn"]', 'no-such-customer')
                browser.wait('document.body.textContent.includes("Không có lịch khớp bộ lọc")')
                browser.click('.business-filters>button')
                browser.wait('!document.body.textContent.includes("Không có lịch khớp bộ lọc")')
                browser.js('document.querySelector("[data-testid=business-finance]").scrollIntoView({block:"start"});window.scrollBy(0,-100)')
                browser.screenshot(f'{width}-dashboard-finance')
        browser.navigate(f'/appointments/create?treatment={treatment_id}&service={facial_id}&item={gift_item}')
        browser.wait('document.querySelector("[data-service-id]")')
        assert browser.js(f'document.querySelector(`[data-treatment-service="{facial_id}"]`).value==="{gift_item}"')
        browser.click(f'[data-service-id="{massage_id}"]')
        browser.set_value(f'[data-treatment-service="{massage_id}"]', str(package_item), 'select')
        browser.wait('document.querySelector("[data-testid=booking-total]").textContent.startsWith("0")')
        browser.screenshot(f'{width}-booking-services')
        browser.click('[data-testid=booking-next]')
        browser.set_value('[data-testid=booking-date]', day.isoformat())
        browser.wait('document.querySelector(`[data-slot="09:00"]:not([disabled])`)')
        browser.click('[data-slot="09:00"]')
        browser.wait('document.body.textContent.includes("Kiểm thử staff")')
        browser.screenshot(f'{width}-booking-time')
        browser.click('[data-testid=booking-next]')
        browser.wait('document.querySelector("[data-testid=booking-recap]")')
        assert browser.js('document.querySelector("[data-testid=booking-recap]").textContent.includes("Dùng 1 buổi")')
        browser.screenshot(f'{width}-booking-review')
        print(f'PASS {width}px dashboard roles and booking wizard', flush=True)

    # Lost response after the server reserves both paid-package and gift items.
    browser.js('window.__createCount=0;const realFetch=window.fetch.bind(window);let drop=true;window.fetch=async(url,options)=>{const r=await realFetch(url,options);if(String(url).endsWith("/api/appointments/create")){window.__createCount++;if(drop){drop=false;throw new TypeError("response lost")}}return r};')
    browser.click('[data-testid=booking-submit]')
    browser.wait('document.body.textContent.includes("Kiểm tra kết quả đặt lịch")')
    with app.app_context():
        assert LichHen.query.count() == 5
        assert LieuTrinhUsage.query.count() == 2
        assert all(u.state == 'reserved' for u in LieuTrinhUsage.query.all())
        assert HoaDon.query.count() == 1, 'free entitlement booking must not create a retail invoice'
    browser.screenshot('lost-response')
    browser.navigate('/appointments/create')
    browser.wait('document.body.textContent.includes("Kiểm tra kết quả đặt lịch")')
    browser.click('#root button')
    browser.wait('document.querySelector("[data-testid=booking-success]")')
    with app.app_context():
        assert LichHen.query.count() == 5
    browser.screenshot('reconciled-booking')

    # Retail prepay: invoice remains unpaid until synthetic webhook acknowledges it.
    browser.navigate('/appointments/create')
    browser.wait('document.querySelector("[data-service-id]")')
    browser.click(f'[data-service-id="{hair_id}"]')
    browser.click('[data-testid=booking-next]')
    browser.set_value('[data-testid=booking-date]', day.isoformat())
    browser.wait('document.querySelector(`[data-slot="13:00"]:not([disabled])`)')
    browser.click('[data-slot="13:00"]')
    browser.click('[data-testid=booking-next]')
    browser.wait('document.querySelector("[data-testid=booking-prepay]")')
    browser.click('[data-testid=booking-prepay]')
    browser.click('[data-testid=booking-submit]')
    browser.wait('document.querySelector("#customerLoyaltyPayment")?.open')
    with app.app_context():
        prepaid = HoaDon.query.order_by(HoaDon.mahd.desc()).first()
        assert prepaid.trangthai == 'Chưa thanh toán' and prepaid.tongtien == 250000 and prepaid.malh
        invoice_id = prepaid.mahd
    for width in (360, 390, 768, 1440):
        browser.viewport(width)
        browser.screenshot(f'{width}-prepay-loyalty-dialog')
    browser.viewport(390)
    browser.click('#customerLoyaltyPayment [data-pay]')
    browser.wait('document.querySelector("#customerLoyaltyPayment [data-bank] img")')
    browser.screenshot('prepay-qr-dialog')
    response = app.test_client().post('/api/payment/webhook/sepay', headers={'Authorization': 'Apikey phase4-synthetic-webhook'},
                                    json={'id': 'PHASE4-ONLY', 'content': f'HD{invoice_id}', 'transferAmount': 250000, 'transferType': 'in'})
    assert response.status_code == 200, response.json
    browser.wait('!document.getElementById("customerLoyaltyPayment")')
    browser.screenshot('prepay-confirmed')
    with app.app_context():
        assert db.session.get(HoaDon, invoice_id).trangthai == 'Đã thanh toán'
        assert ThanhToan.query.count() == 2

    # Logout keeps the exact entitlement link as the return URL.
    app.config['BROWSER_GUEST'] = True
    browser.navigate(f'/appointments/create?treatment={treatment_id}&service={massage_id}&item={package_item}')
    browser.wait('document.body.textContent.includes("Đăng nhập để đặt lịch")')
    assert browser.js(f'document.querySelector("#root a").href.includes(encodeURIComponent("item={package_item}"))')
    browser.screenshot('guest-return-link')
    print('PASS package + gift, lost-response reconciliation, VietQR synthetic payment, guest deep link', flush=True)
    print('Screenshots: ' + str(artifacts), flush=True)
except Exception:
    if browser:
        (artifacts / 'failure.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
        (artifacts / 'failure.txt').write_text(browser.js('document.body.innerText'), encoding='utf-8')
        print('Failure artifacts: ' + str(artifacts), flush=True)
    raise
finally:
    if browser:
        browser.ws.close()
    server.shutdown()
    process.terminate()
    process.wait(timeout=10)

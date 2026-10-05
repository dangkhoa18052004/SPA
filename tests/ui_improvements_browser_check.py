"""Opt-in Chrome check for the 2026-10-05 improvement plan (F01, F05–F10) on an isolated in-memory DB.

Run: python tests/ui_improvements_browser_check.py
Requires local Chrome and websocket-client. No real payment or email is sent.
Checks real viewport widths (innerWidth must equal the emulated width, so content that
silently widens the layout viewport is caught), a real mouse click on "Xóa bộ lọc",
appointment cards without horizontal scrolling, and the booking order (source → time → confirm).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import base64
import json
import subprocess
import threading
import time as clock
import urllib.request
import uuid
from datetime import datetime, timedelta, time

import websocket
from flask import session
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler

from app import create_app
from app.extensions import db
from app.models import (ChucVu, NhanVien, KhachHang, DichVu, CaLam, nhanvien_calam, LichHen,
                        ChiTietLichHen, HoaDon, ThanhToan, AppointmentStatus)
from app.services import package_service, appointment_service, email_service

root = Path(__file__).resolve().parents[1]
artifacts = root / 'tests' / 'runtime_ui_improvements'
artifacts.mkdir(exist_ok=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='ui-test-only', JWT_SECRET_KEY='ui-test-secret-at-least-32-characters',
    VIETQR_BANK_ID='TESTBANK', VIETQR_ACCOUNT_NO='123456', VIETQR_ACCOUNT_NAME='TEST SPA'))
appointment_service.send_appointment_confirmation_email_async = lambda *args: None
# Gemini giả lập cho widget AI: lượt có tool → tạo bản nháp; sau functionResponse → trả lời; tóm tắt → JSON.
from app.services import ai_service
app.config['GEMINI_API_KEY'] = 'fake-key-for-ui-check'


def fake_gemini(payload):
    def reply(parts):
        return {'candidates': [{'content': {'role': 'model', 'parts': parts}}]}
    if 'tools' not in payload:
        return reply([{'text': json.dumps({'summary': 'Thực thu ổn định.', 'suggestions': ['Đẩy mạnh combo massage.']}, ensure_ascii=False)}])
    last = payload['contents'][-1]['parts'][0]
    if 'functionResponse' in last:
        return reply([{'text': 'Mình đã tạo **bản nháp**, bạn bấm Xác nhận đặt lịch nhé.'}])
    return reply([{'functionCall': {'name': 'create_booking_draft_tool',
                                    'args': {'madv_list': [facial_id], 'ngaygio': f'{booking_day.isoformat()}T16:30'}}}])


ai_service.call_gemini = fake_gemini
email_service.send_email = lambda *args, **kwargs: True

with app.app_context():
    db.create_all()
    role = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
    db.session.add(role); db.session.flush()
    customer = KhachHang(hoten='Khách thử nghiệm', email='nobody@example.test', sdt='0900000000',
                         taikhoan='ui_customer', matkhau='hash', trangthai='active')
    other = KhachHang(hoten='Nguyễn Văn Tên Rất Dài Để Kiểm Tra Xuống Dòng', sdt='0900000009',
                      taikhoan='ui_other', matkhau='hash', trangthai='active')
    staff = NhanVien(hoten='Kỹ thuật viên thử nghiệm', taikhoan='ui_staff', matkhau='hash', macv=role.macv, role='staff', trangthai=True)
    admin = NhanVien(hoten='Admin thử nghiệm', taikhoan='ui_admin', matkhau='hash', macv=role.macv, role='admin', trangthai=True)
    service = DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=60, active=True)
    facial = DichVu(tendv='Chăm sóc da', gia=500000, thoiluong=90, active=True)
    db.session.add_all([customer, other, staff, admin, service, facial]); db.session.flush()
    now = package_service.local_now()
    today, booking_day = now.date(), now.date() + timedelta(days=3)
    for day in (today, booking_day):
        shift = CaLam(ngay=day, giobatdau=time(8), gioketthuc=time(18), sogio=10)
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=staff.manv, maca=shift.maca))
    for hour, status, who in ((9, AppointmentStatus.PENDING, other), (11, AppointmentStatus.IN_PROGRESS, customer),
                              (13, AppointmentStatus.COMPLETED, customer), (15, AppointmentStatus.CONFIRMED, other)):
        apt = LichHen(makh=who.makh, manv=staff.manv, ngaygio=datetime.combine(today, time(hour)), trangthai=status)
        db.session.add(apt); db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=service.madv))
    # Doanh thu: 1 gói 1.200.000 + 1 hóa đơn dịch vụ 300.000 trong hôm nay.
    package = package_service.save_package(dict(tengoi='Combo Massage 5 buổi', giagoi=1200000, validity_months=6,
                                                items=[dict(madv=service.madv, total_sessions=5)]))
    purchase = package_service.create_purchase(package.magoi, customer.makh, 'cash')
    _, record, _ = package_service.confirm_purchase(purchase.id, 1200000, method='cash')
    invoice = HoaDon(makh=customer.makh, manv=staff.manv, tongtien=300000, trangthai='Đã thanh toán')
    db.session.add(invoice); db.session.flush()
    db.session.add(ThanhToan(mahd=invoice.mahd, sotien=300000, phuongthuc='Tiền mặt', ngaythanhtoan=now))
    db.session.commit()
    customer_id, service_id, facial_id = customer.makh, service.madv, facial.madv
    item_id = record.items[0].id
    customer_token = create_access_token(identity=f'customer:{customer.makh}')
    admin_token = create_access_token(identity=f'staff:{admin.manv}')
    admin_user = dict(role='admin', hoten='Admin thử nghiệm', manv=admin.manv)
    appointment_total = LichHen.query.count()


@app.before_request
def test_session():
    session.update(user_id=customer_id, user_type='customer', hoten='Khách thử nghiệm')


@app.after_request
def test_browser_tokens(response):
    if response.mimetype == 'text/html':
        init = ("window.__uiErrors=[];window.addEventListener('error',e=>{if(e.message)__uiErrors.push(e.message)});"
                "window.addEventListener('unhandledrejection',e=>__uiErrors.push(String(e.reason)));")
        init += (f"localStorage.setItem('access_token',{json.dumps(customer_token)});"
                 f"localStorage.setItem('admin_token',{json.dumps(admin_token)});localStorage.setItem('admin_role','admin');"
                 f"localStorage.setItem('admin_user',{json.dumps(json.dumps(admin_user))});")
        response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + init + '</script>', 1))
    return response


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=QuietHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
base = f'http://127.0.0.1:{server.server_port}'
chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
profile_path = artifacts / ('chrome-profile-' + uuid.uuid4().hex)
process = subprocess.Popen([chrome, '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-allow-origins=*', '--remote-debugging-port=0', '--user-data-dir=' + str(profile_path), 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Browser:
    def __init__(self):
        portfile = profile_path / 'DevToolsActivePort'
        for _ in range(100):
            if portfile.exists():
                break
            clock.sleep(.1)
        port = int(portfile.read_text().splitlines()[0])
        targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
        target = next(t for t in targets if t['type'] == 'page')
        self.ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=20)
        self.counter = 0
        self.call('Page.enable')

    def call(self, method, params=None):
        self.counter += 1; identifier = self.counter
        self.ws.send(json.dumps(dict(id=identifier, method=method, params=params or {})))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') == identifier:
                if message.get('error'):
                    raise RuntimeError(message['error'])
                return message.get('result', {})

    def evaluate(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression, label=''):
        try:
            return self.evaluate("(async()=>{for(let n=0;n<160;n++){if(" + expression + ")return true;"
                                 "await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait timeout');})()")
        except RuntimeError:
            raise AssertionError(f'Timeout waiting for {label or expression}')

    def navigate(self, url):
        self.call('Page.navigate', {'url': base + url})
        pathname = url.split('?')[0].split('#')[0]
        self.wait("location.pathname===" + json.dumps(pathname) + "&&document.readyState==='complete'", url)

    def viewport(self, width):
        self.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))

    def click(self, selector):
        """Real mouse click at the element centre (fails if another element covers it)."""
        box = self.evaluate(f"(()=>{{const e=document.querySelector({json.dumps(selector)});e.scrollIntoView({{block:'center'}});"
                            "const r=e.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2;"
                            "const hit=document.elementFromPoint(x,y);return {x,y,covered:!(hit===e||e.contains(hit))};})()")
        assert not box['covered'], f'{selector} is covered by another element'
        for kind in ('mousePressed', 'mouseReleased'):
            self.call('Input.dispatchMouseEvent', dict(type=kind, x=box['x'], y=box['y'], button='left', clickCount=1))

    def screenshot(self, name):
        data = self.call('Page.captureScreenshot', {'format': 'png'})['data']
        (artifacts / name).write_bytes(base64.b64decode(data))

    def layout_ok(self, width, label):
        state = self.evaluate("({w:innerWidth,sw:document.documentElement.scrollWidth,errors:window.__uiErrors,"
                              "wide:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1)"
                              ".slice(0,6).map(e=>e.tagName+'.'+e.className+'#'+e.id+' '+Math.round(e.getBoundingClientRect().right))})")
        assert state['w'] == width, (label, width, state)
        assert state['sw'] <= state['w'] + 1, (label, width, state)
        assert not state['errors'], (label, state['errors'])


results = []
browser = None
try:
    browser = Browser()
    for width in (1440, 768, 390):
        browser.viewport(width)

        # F01/F09: dashboard số thực thu gộp gói + dịch vụ, một cột trên mobile.
        browser.navigate('/admin/dashboard')
        browser.wait("document.querySelector('#kpi-revenue-total').textContent.includes('1.500.000')", 'dashboard KPI')
        columns = browser.evaluate("getComputedStyle(document.querySelector('.analytics-row')).gridTemplateColumns.split(' ').length")
        assert columns == (3 if width >= 1100 else 1), (width, columns)
        assert browser.evaluate("document.querySelector('#kpi-revenue-package').textContent.includes('1.200.000')")
        browser.layout_ok(width, 'dashboard')
        browser.screenshot(f'{width}-dashboard.png')

        # F05/F08: lọc rồi bấm "Xóa bộ lọc" bằng chuột thật; thao tác chính không cần kéo ngang.
        browser.navigate('/admin/appointments')
        browser.wait(f"document.querySelectorAll('#appointments-table tbody tr[data-appointment-id]').length==={appointment_total}", 'appointment rows')
        browser.evaluate("const d=document.querySelector('#filter-date-select');d.value='today';d.dispatchEvent(new Event('change'));")
        browser.evaluate("const s=document.querySelector('#filter-status-select');s.value='in_progress';s.dispatchEvent(new Event('change'));")
        browser.wait("document.querySelectorAll('#appointments-table tbody tr[data-appointment-id]').length===1", 'in_progress filter')
        browser.evaluate("const i=document.querySelector('#search-input');i.value='zzz';i.dispatchEvent(new Event('input'));")
        browser.wait("document.querySelector('#filter-summary').textContent.includes('Đang lọc')", 'filter summary')
        browser.click('#reset-filters-btn')
        browser.wait(f"document.querySelectorAll('#appointments-table tbody tr[data-appointment-id]').length==={appointment_total}", 'reset reload')
        state = browser.evaluate("({d:document.querySelector('#filter-date-select').value,s:document.querySelector('#filter-status-select').value,"
                                 "q:document.querySelector('#search-input').value,summary:document.querySelector('#filter-summary').textContent})")
        assert state['d'] == '' and state['s'] == '' and state['q'] == '' and 'Không áp dụng' in state['summary'], state
        browser.evaluate("window.scrollTo(0,0)")
        offscreen = browser.evaluate("[...document.querySelectorAll('#appointments-table .action-buttons .btn')].filter(b=>b.getClientRects().length)"
                                     ".filter(b=>{const r=b.getBoundingClientRect();return r.right>innerWidth+1||r.left<0}).length")
        if offscreen:
            print(browser.evaluate("JSON.stringify({table:document.querySelector('#appointments-table').getBoundingClientRect(),container:document.querySelector('.data-table-container').getBoundingClientRect(),cells:[...document.querySelectorAll('#appointments-table tbody tr:first-child td')].map(td=>[td.className,Math.round(td.getBoundingClientRect().width),td.textContent.trim().slice(0,40)])})"))
            browser.screenshot(f'{width}-appointments-fail.png')
        assert offscreen == 0, (width, offscreen)
        if width < 1100:
            assert browser.evaluate("getComputedStyle(document.querySelector('#appointments-table thead')).display") == 'none'
        browser.layout_ok(width, 'appointments')
        browser.screenshot(f'{width}-appointments.png')

        # F06/F07: liệu trình chọn ở bước 1; giờ lấy từ API; tóm tắt + CTA trước khi gửi.
        browser.navigate('/appointments/create')
        browser.wait("document.querySelector('[data-service-id]')", 'services')
        browser.evaluate(f"toggleServiceSelection({service_id})")
        browser.wait("document.querySelector('[data-treatment-service]')", 'treatment select in step 1')
        order = browser.evaluate("(()=>{const sel=document.querySelector('#bookingTreatments');const step1=document.querySelector('#step1');"
                                 "return {inStep1:step1.contains(sel),visible:sel.getClientRects().length>0};})()")
        assert order == {'inStep1': True, 'visible': True}, order
        browser.evaluate(f"const s=document.querySelector('[data-treatment-service]');s.value='{item_id}';s.dispatchEvent(new Event('change'));")
        browser.wait("PackageCare.getUsages().length===1", 'usage chosen')
        browser.evaluate("goToStep(2)")
        browser.evaluate(f"document.querySelector('#appointmentDate').value='{booking_day.isoformat()}';loadTimeSlots();")
        browser.wait("document.querySelector('#appointmentTime option[value=\"09:00\"]:not([disabled])')", 'slots')
        options = browser.evaluate("[...document.querySelectorAll('#appointmentTime option')].map(o=>o.value).filter(Boolean)")
        assert len(options) == len(set(options)), options
        browser.evaluate("const t=document.querySelector('#appointmentTime');t.value='09:00';t.dispatchEvent(new Event('change'));")
        browser.evaluate("goToStep(3)")
        browser.wait("document.querySelector('#confirmRecap').textContent.includes('Còn phải trả')", 'confirm recap')
        recap = browser.evaluate("document.querySelector('#confirmRecap').textContent")
        assert 'dùng 1 buổi' in recap and '0' in recap, recap
        cta = browser.evaluate("(()=>{const b=document.querySelector('#step3 button[type=submit]');b.scrollIntoView({block:'nearest'});"
                               "const r=b.getBoundingClientRect();const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);"
                               "const recap=document.querySelector('#confirmRecap').getBoundingClientRect();"
                               "return {covered:!(hit===b||b.contains(hit)),h:r.height,recapAbove:recap.top<r.top||getComputedStyle(b.parentElement).position==='sticky'};})()")
        assert not cta['covered'] and cta['h'] >= 44 and cta['recapAbove'], (width, cta)
        browser.layout_ok(width, 'booking')
        browser.screenshot(f'{width}-booking-step3.png')
        results.append(dict(width=width, dashboard_columns=columns, booking_cta=cta))
        print(f'PASS {width}px: dashboard, reset filters, appointment cards, booking order', flush=True)

    # Gửi đặt lịch thật một lần với buổi gói đã chọn.
    browser.viewport(390)
    with app.app_context():
        before = LichHen.query.count()
    browser.click('#step3 button[type="submit"]')
    for _ in range(60):
        with app.app_context():
            if LichHen.query.count() == before + 1:
                break
        clock.sleep(.1)
    with app.app_context():
        assert LichHen.query.count() == before + 1, 'booking submit did not create appointment'

    # Đặt lịch chọn "Thanh toán ngay bằng VietQR" → hộp QR hóa đơn mở ngay sau khi đặt.
    browser.navigate('/appointments/create')
    browser.wait("document.querySelector('[data-service-id]')", 'services (prepay)')
    browser.evaluate(f"toggleServiceSelection({facial_id});goToStep(2);document.querySelector('#appointmentDate').value='{booking_day.isoformat()}';loadTimeSlots();")
    browser.wait("document.querySelector('#appointmentTime option[value=\"15:00\"]:not([disabled])')", 'prepay slots')
    browser.evaluate("const t=document.querySelector('#appointmentTime');t.value='15:00';t.dispatchEvent(new Event('change'));goToStep(3);")
    browser.wait("!document.querySelector('#prepayOption input').disabled", 'prepay enabled')
    browser.click('#prepayOption input')
    browser.wait("document.querySelector('#confirmRecap').textContent.includes('VietQR')", 'recap shows VietQR')
    browser.click('#step3 button[type="submit"]')
    browser.wait("document.getElementById('customerLoyaltyPayment')?.open", 'prepay QR dialog')
    with app.app_context():
        prepaid = HoaDon.query.order_by(HoaDon.mahd.desc()).first()
        assert prepaid.malh and prepaid.trangthai == 'Chưa thanh toán' and prepaid.tongtien == 500000
    browser.screenshot('390-prepay-dialog.png')
    browser.evaluate("document.getElementById('customerLoyaltyPayment').close()")
    for attempt in range(3):  # hộp QR tải voucher/điểm xong mới chuyển trang
        try:
            browser.wait("location.pathname==='/profile'", 'redirect after prepay dialog')
            break
        except AssertionError:
            if attempt == 2:
                raise
    print('PASS prepay booking opens VietQR invoice dialog', flush=True)

    # Khách đổi dịch vụ trước giờ hẹn từ hồ sơ (lịch vừa đặt ở trên).
    with app.app_context():
        booked = LichHen.query.filter(~LichHen.malh.in_(db.session.query(HoaDon.malh).filter(HoaDon.malh.isnot(None))))             .order_by(LichHen.malh.desc()).first().malh
    browser.navigate('/profile#appointments')
    browser.wait(f"document.querySelector('[onclick=\"openChangeServices({booked})\"]')", 'customer change button')
    browser.click(f'[onclick="openChangeServices({booked})"]')
    browser.wait(f"document.querySelector('#csDialog [data-toggle=\"{facial_id}\"]')", 'customer change dialog')
    # Tìm kiếm không dấu lọc ngay khi gõ; chọn dịch vụ mới → chênh lệch giá hiện +500.000.
    browser.evaluate("const q=document.querySelector('#csDialog [data-search]');q.value='cham soc da';q.dispatchEvent(new Event('input'));")
    browser.wait("document.querySelectorAll('#csDialog [data-toggle]').length===1", 'smart search filters')
    browser.click(f'#csDialog [data-toggle="{facial_id}"]')
    browser.wait("document.querySelector('#csDialog .cs-diff').textContent.includes('500.000')", 'price diff')
    assert browser.evaluate("[...document.querySelectorAll('#csDialog .cs-card img')].every(i=>i.getAttribute('src'))")
    browser.screenshot('390-change-services.png')
    browser.click('#csDialog [data-save]')
    browser.wait("!document.querySelector('#csDialog')", 'customer change saved')
    with app.app_context():
        assert {d.madv for d in db.session.get(LichHen, booked).chitiet} == {service_id, facial_id}

    # Lễ tân/admin đổi dịch vụ theo yêu cầu khách từ danh sách lịch hẹn.
    browser.navigate('/admin/appointments')
    browser.wait(f"document.querySelector('[onclick=\"openChangeServicesModal({booked})\"]')", 'admin change button')
    browser.click(f'[onclick="openChangeServicesModal({booked})"]')
    browser.wait(f"document.querySelector('#csDialog [data-toggle=\"{facial_id}\"]')", 'admin change modal')
    browser.click(f'#csDialog [data-toggle="{facial_id}"]')
    browser.click('#csDialog [data-save]')
    browser.wait("!document.querySelector('#csDialog')", 'admin change saved')
    with app.app_context():
        assert {d.madv for d in db.session.get(LichHen, booked).chitiet} == {service_id}
    assert not browser.evaluate('window.__uiErrors')
    print('PASS change services from customer profile and admin list', flush=True)

    # GĐ5: widget AI → bản nháp (chưa có lịch) → khách bấm xác nhận → đúng 1 lịch mới.
    browser.viewport(390)
    browser.navigate('/')
    browser.wait("document.querySelector('.ai-fab')", 'AI widget')
    browser.click('.ai-fab')
    browser.evaluate("const i=document.querySelector('.ai-input input');i.value='Đặt chăm sóc da 14h ngày kia';document.querySelector('.ai-input').requestSubmit();")
    browser.wait("document.querySelector('.ai-draft [data-confirm]')", 'AI draft card')
    with app.app_context():
        before = LichHen.query.count()
    browser.layout_ok(390, 'ai widget')
    browser.screenshot('390-ai-draft.png')
    browser.click('.ai-draft [data-confirm]')
    browser.wait("document.querySelector('.ai-draft-status').textContent.includes('Mã lịch')", 'AI confirm')
    with app.app_context():
        assert LichHen.query.count() == before + 1 and LichHen.query.order_by(LichHen.malh.desc()).first().booking_source == 'ai'
    browser.viewport(1440)
    browser.navigate('/admin/dashboard')
    browser.wait("!document.querySelector('#ai-summary-panel').hidden", 'AI summary panel')
    browser.click('#ai-summary-btn')
    browser.wait("document.querySelector('#ai-summary-body').textContent.includes('FACTS')", 'AI summary')
    assert browser.evaluate("document.querySelector('#ai-summary-body').textContent.includes('1.500.000đ')")
    browser.screenshot('1440-ai-summary.png')
    assert not browser.evaluate('window.__uiErrors')
    print('PASS AI widget draft → confirm and dashboard AI summary (mocked Gemini)', flush=True)

    # F10: hồ sơ mở tab Lịch hẹn mặc định; link trực tiếp giữ tab.
    browser.navigate('/profile')
    browser.wait("document.querySelector('#appointments-section.active')", 'default appointments tab')
    assert browser.evaluate("document.querySelector('.profile-menu a').dataset.section") == 'appointments'
    browser.navigate('/profile#loyalty')
    browser.wait("document.querySelector('#loyalty-section.active')&&document.querySelector('.loyalty-tier-card')", 'loyalty tab + tier')
    assert not browser.evaluate('window.__uiErrors')

    # F11: bộ lọc lương chỉ hiện trường đang dùng; Xuất PDF là nút phụ.
    browser.viewport(1440)
    browser.navigate('/admin/salary')
    browser.wait("document.querySelector('#salary-filter-summary').textContent.includes('tháng')", 'salary month')
    visible = "(id=>document.getElementById(id).getClientRects().length>0)"
    assert browser.evaluate(f"{visible}('filter-month-group')&&!{visible}('filter-day-group')")
    browser.evaluate("const t=document.querySelector('#filter-type');t.value='day';t.dispatchEvent(new Event('change'));")
    browser.wait("document.querySelector('#salary-filter-summary').textContent.includes('ngày')", 'salary day')
    assert browser.evaluate(f"!{visible}('filter-month-group')&&{visible}('filter-day-group')")
    assert browser.evaluate("!!document.querySelector('.salary-filter-actions .btn-secondary .fa-file-pdf')&&!document.querySelector('.salary-filter-actions .btn-danger')")
    assert not browser.evaluate('window.__uiErrors')
    print('PASS salary filter shows only the active field; PDF export is a secondary button', flush=True)
    (artifacts / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS booking submit with package session, profile tabs and tier card; no real payment or email sent', flush=True)
finally:
    try:
        browser.call('Browser.close') if browser else process.terminate()
    except Exception:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    server.shutdown()
    with app.app_context():
        db.engine.dispose()

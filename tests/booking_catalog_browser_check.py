"""Booking images/pagination/available times in real Chrome, using only an isolated test DB.

Run after npm run build: venv/Scripts/python tests/booking_catalog_browser_check.py
"""
import base64
from datetime import datetime, time as day_time
import json
import logging
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
from flask import session
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler
import conftest
from billing_browser_check import Browser, free_port
from app.extensions import db
from app.models import DanhMucDichVu, DichVu, CaLam, nhanvien_calam, LichHen, ChiTietLichHen
from app.services import appointment_service, email_service


class BookingBrowser(Browser):
    def wait(self, expression):
        return super().wait('Boolean(' + expression + ')')


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__(); app = next(fixture)
    app.config['CUSTOMER_BOOKING_REACT_ENABLED'] = True
    appointment_service.vn_now = lambda: datetime(2026, 10, 15, 9, 10)
    email_service.send_email = lambda *a, **k: (_ for _ in ()).throw(AssertionError('No email should be sent'))
    artifacts = ROOT / '.test-tmp' / ('booking-catalog-' + uuid4().hex[:8]); artifacts.mkdir(parents=True)
    with app.app_context():
        body = DanhMucDichVu(name='Chăm sóc cơ thể', slug='body-care')
        face = DanhMucDichVu(name='Chăm sóc da', slug='facial')
        db.session.add_all([body, face]); db.session.flush()
        names = ['Spa chân', 'Massage body thư giãn', 'Chăm sóc da mặt cơ bản', 'Massage đá nóng', 'Tắm trắng dưỡng ẩm', 'Gội đầu dưỡng sinh', 'Chăm sóc da chuyên sâu', 'Phục hồi da', 'Làm nail', 'Dưỡng da tay', 'Massage thảo dược', 'Chăm sóc móng', 'Chăm sóc tóc']
        image = (ROOT / 'app/static/images/default-service.jpg').read_bytes()
        services = [DichVu(tendv=name, gia=150000 + i * 10000, thoiluong=30, active=True,
                          category_id=body.id if i % 2 == 0 else face.id,
                          anhdichvu=image if i == 0 else b'broken-image' if i == 1 else None) for i, name in enumerate(names)]
        shift = CaLam(ngay=datetime(2026, 10, 15).date(), giobatdau=day_time(8), gioketthuc=day_time(18), sogio=10)
        db.session.add_all([*services, shift]); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'], maca=shift.maca))
        apt = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'], ngaygio=datetime(2026, 10, 15, 10), trangthai='confirmed')
        db.session.add(apt); db.session.flush(); db.session.add(ChiTietLichHen(malh=apt.malh, madv=services[0].madv)); db.session.commit()
        token = create_access_token(identity=f"customer:{app.config['TEST_CUSTOMER_ID']}")

    @app.before_request
    def bootstrap_session():
        session.update(user_id=app.config['TEST_CUSTOMER_ID'], user_type='customer')

    class QuietHandler(WSGIRequestHandler):
        def log(self, *a, **k): pass
    server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = free_port()
    chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    process = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts / "profile"}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = browser = None
    try:
        for _ in range(100):
            try:
                tabs = json.load(urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1)); break
            except Exception: time.sleep(.1)
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        browser = BookingBrowser(ws); browser.call('Page.enable')
        # Deliberately use an overseas device timezone; spa bookings must still use UTC+7.
        browser.call('Emulation.setTimezoneOverride', dict(timezoneId='America/Los_Angeles'))
        browser.call('Page.addScriptToEvaluateOnNewDocument', dict(source='localStorage.setItem("access_token",' + json.dumps(token) + ');'
            'window.__uiErrors=[];addEventListener("error",e=>{if(e.message)__uiErrors.push(e.message)});addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
            'const OriginalDate=Date;window.__now=OriginalDate.parse("2026-10-15T09:10:00+07:00");window.Date=class extends OriginalDate{constructor(...args){super(...(args.length?args:[window.__now]))}static now(){return window.__now}};'))

        def click(selector):
            browser.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')
        def value(selector, text, select=False):
            browser.evaluate('(()=>{const e=document.querySelector(' + json.dumps(selector) + ');Object.getOwnPropertyDescriptor(' + ('HTMLSelectElement' if select else 'HTMLInputElement') + '.prototype,"value").set.call(e,' + json.dumps(text) + ');e.dispatchEvent(new Event(' + json.dumps('change' if select else 'input') + ',{bubbles:true}));})()')
        def screenshot(name):
            browser.evaluate('window.scrollTo(0,180)'); time.sleep(.3)
            assert browser.evaluate('document.documentElement.scrollWidth<=innerWidth+1 && !__uiErrors.length'), browser.evaluate('__uiErrors')
            (artifacts / (name + '.png')).write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))

        for width in (360, 390, 768, 1440):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))
            browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/appointments/create'))
            browser.wait('document.querySelectorAll("[data-service-id]").length===6')
            first = browser.evaluate('document.querySelector("[data-service-id]").dataset.serviceId')
            click(f'[data-service-id="{first}"]'); click('[aria-label="Trang dịch vụ sau"]')
            browser.wait('document.querySelector(`[aria-label="Phân trang dịch vụ"]`).textContent.includes("Trang 2 / 3")')
            second = browser.evaluate('document.querySelector("[data-service-id]").dataset.serviceId')
            click(f'[data-service-id="{second}"]'); click('[aria-label="Trang dịch vụ sau"]')
            browser.wait('document.querySelectorAll("[data-service-id]").length===1')
            assert browser.evaluate('document.querySelector(`[aria-label="Trang dịch vụ sau"]`).disabled')
            value('[aria-label="Tìm dịch vụ"]', 'Spa chân')
            browser.wait('document.querySelectorAll("[data-service-id]").length===1 && !document.querySelector(`[aria-label="Phân trang dịch vụ"]`)')
            value('[aria-label="Tìm dịch vụ"]', '')
            browser.wait('document.querySelectorAll("[data-service-id]").length===6')
            assert browser.evaluate(f'document.querySelector(`[data-service-id="{first}"]`).getAttribute("aria-pressed")==="true"')
            value('[aria-label="Nhóm dịch vụ"]', 'Chăm sóc da', True)
            browser.wait('document.querySelectorAll("[data-service-id]").length===6 && !document.querySelector(`[aria-label="Phân trang dịch vụ"]`)')
            value('[aria-label="Nhóm dịch vụ"]', '', True)
            browser.wait('document.querySelector(`[aria-label="Phân trang dịch vụ"]`)')
            # Loading an invalid image must fall back without breaking its card.
            value('[aria-label="Tìm dịch vụ"]', 'Massage body thư giãn')
            browser.wait('document.querySelectorAll("[data-service-id]").length===1')
            browser.wait('document.querySelector(".booking-service-image").src.endsWith("/static/images/default-service.jpg") && document.querySelector(".booking-service-image").naturalWidth>0')
            value('[aria-label="Tìm dịch vụ"]', '')
            browser.wait('document.querySelectorAll("[data-service-id]").length===6')
            browser.evaluate('document.querySelectorAll(".booking-service-image").forEach(e=>{e.loading="eager"})')
            browser.wait('[...document.querySelectorAll(".booking-service-image")].every(e=>e.complete&&e.naturalWidth>0)')
            assert browser.evaluate('document.querySelectorAll("[data-treatment-service]").length===2')
            screenshot(f'{width}-services')
            click('[data-testid=booking-next]')
            browser.wait('document.querySelector("[data-slot]")')
            shown = browser.evaluate('[...document.querySelectorAll("[data-slot]")].map(e=>e.dataset.slot)')
            with app.app_context():
                expected = [s['time'] for s in appointment_service.day_availability('2026-10-15', madv_list=[int(first), int(second)])['slots'] if s['available']]
            assert shown == expected and '09:00' not in shown and '10:00' not in shown, (shown, expected)
            click('[data-slot="10:30"]')
            browser.wait('!document.querySelector("[data-testid=booking-next]").disabled')
            # A selected slot expires while the tab is open, without leaving a stale next-step button enabled.
            browser.evaluate('window.__now=Date.parse("2026-10-15T10:31:00+07:00");window.dispatchEvent(new Event("focus"))')
            browser.wait('!document.querySelector(`[data-slot="10:30"]`) && document.querySelector("[data-testid=booking-next]").disabled')
            screenshot(f'{width}-available-times')
            value('[data-testid=booking-date]', '2026-10-16')
            browser.wait('document.body.textContent.includes("Ngày này không còn giờ trống phù hợp")')
            assert not browser.evaluate('document.querySelector("[data-slot]")')
            screenshot(f'{width}-no-slots')
            print(f'PASS {width}px: images/fallback, 6 per page, selections/filters, future free slots, expiry, no slots', flush=True)
        print('Screenshots: ' + str(artifacts), flush=True)
    except Exception:
        if browser:
            (artifacts / 'failure.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
            (artifacts / 'failure.txt').write_text(browser.evaluate('document.body.innerText'), encoding='utf-8')
            print('Failure artifacts: ' + str(artifacts), flush=True)
        raise
    finally:
        if ws: ws.close()
        server.shutdown(); process.terminate(); process.wait(timeout=10)
        fixture.close()


if __name__ == '__main__':
    main()

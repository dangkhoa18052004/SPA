"""Real Chrome: CRM roles/history, email opt-in and recommendation attribution. Isolated DB, no mail."""
import base64
from datetime import datetime, time as day_time, timedelta
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
from test_recommendations import catalog
from app.extensions import db
from app.models import (NhanVien, LichHen, ChiTietLichHen, CaLam, nhanvien_calam, CustomerPreference,
                        RecommendationImpression, CustomerBehavior, NotificationJob)
from app.services import appointment_service, email_service, package_service as ps


class CRMTestBrowser(Browser):
    def wait(self, expression):
        return super().wait('Boolean(' + expression + ')')


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__(); app = next(fixture)
    app.config.update(CRM_ENABLED=True, CUSTOMER_CONSENT_ENABLED=True, RECOMMENDATION_METRICS_ENABLED=True,
        BUSINESS_PORTAL_ENABLED=True, CUSTOMER_BOOKING_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True)
    data = catalog.__wrapped__(app)
    appointment_service.send_appointment_confirmation_email_async = lambda *a, **k: None
    # Any unexpected send is a test failure, never a real provider call.
    email_service.send_email = lambda *a, **k: (_ for _ in ()).throw(AssertionError('No email should be sent in browser checks'))
    artifacts = ROOT / '.test-tmp' / ('phase5-browser-' + uuid4().hex[:8]); artifacts.mkdir(parents=True)
    with app.app_context():
        admin = db.session.get(NhanVien, app.config['TEST_ADMIN_ID'])
        staff = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        manager = db.session.get(NhanVien, app.config['TEST_STAFF2_ID']); manager.role = 'manager'
        reception = NhanVien(hoten='Lễ tân kiểm thử', taikhoan='crm-reception', matkhau='hash', macv=admin.macv, role='letan', trangthai=True)
        db.session.add(reception); db.session.flush()
        now = ps.local_now(); day = now.date() + timedelta(days=3)
        for customer, days in ((data['a'], 45), (data['b'], 5)):
            apt = LichHen(makh=customer, manv=staff.manv, ngaygio=now - timedelta(days=days), trangthai='completed')
            db.session.add(apt); db.session.flush(); db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['services'][0]))
        apt = LichHen(makh=data['a'], manv=staff.manv, ngaygio=datetime.combine(day, day_time(9)), trangthai='confirmed')
        shift = CaLam(ngay=day, giobatdau=day_time(8), gioketthuc=day_time(18), sogio=10)
        db.session.add_all([apt, shift]); db.session.flush()
        db.session.add(ChiTietLichHen(malh=apt.malh, madv=data['services'][0]))
        db.session.execute(nhanvien_calam.insert().values(manv=staff.manv, maca=shift.maca)); db.session.commit()
        tokens = {role: create_access_token(identity=f'staff:{person.manv}') for role, person in [('admin', admin), ('manager', manager), ('letan', reception), ('staff', staff)]}
        customer_token = create_access_token(identity=f'customer:{data["a"]}')
    app.config['BROWSER_ROLE'] = 'admin'

    @app.before_request
    def bootstrap_session():
        session.update(user_id=data['a'], user_type='customer')

    @app.after_request
    def bootstrap_tokens(response):
        if response.mimetype == 'text/html':
            init = ('window.__uiErrors=[];window.__requests=[];window.addEventListener("error",e=>{if(e.message)__uiErrors.push(e.message)});'
                    'window.addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
                    'const realFetch=window.fetch.bind(window);window.fetch=(url,...rest)=>{__requests.push(String(url));return realFetch(url,...rest)};')
            init += 'localStorage.setItem("access_token",' + json.dumps(customer_token) + ');'
            init += 'localStorage.setItem("admin_token",' + json.dumps(tokens[app.config['BROWSER_ROLE']]) + ');'
            init += 'localStorage.setItem("admin_role",' + json.dumps(app.config['BROWSER_ROLE']) + ');'
            response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + init + '</script>', 1))
        return response

    class QuietHandler(WSGIRequestHandler):
        def log(self, *a, **k): pass
    server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    port = free_port()
    chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    process = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts / "profile"}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws, browser = None, None
    try:
        for _ in range(100):
            try:
                tabs = json.load(urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1)); break
            except Exception: time.sleep(.1)
        tab = next(t for t in tabs if t['type'] == 'page')
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        browser = CRMTestBrowser(ws); browser.call('Page.enable')
        browser.call('Emulation.setTimezoneOverride', dict(timezoneId='Asia/Ho_Chi_Minh'))

        def navigate(path):
            browser.call('Page.navigate', dict(url=base + path)); browser.wait('location.pathname===' + json.dumps(path.split('?')[0].split('#')[0]) + '&&document.readyState==="complete"')
        def viewport(width):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))
        def click(selector):
            browser.evaluate('document.querySelector(' + json.dumps(selector) + ').scrollIntoView({block:"center",behavior:"instant"})'); time.sleep(.2)
            point = browser.evaluate('(()=>{const e=document.querySelector(' + json.dumps(selector) + '),r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y);return{x,y,covered:!(h===e||e.contains(h))}})()')
            assert not point['covered'], (selector, point)
            for kind in ('mousePressed', 'mouseReleased'): browser.call('Input.dispatchMouseEvent', dict(type=kind, x=point['x'], y=point['y'], button='left', clickCount=1))
        def value(selector, text):
            browser.evaluate('(()=>{const e=document.querySelector(' + json.dumps(selector) + ');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(e,' + json.dumps(text) + ');e.dispatchEvent(new Event("input",{bubbles:true}));})()')
        def screenshot(label):
            browser.wait('!document.querySelector(".ant-skeleton")'); time.sleep(.3)
            state = browser.evaluate('({w:innerWidth,s:document.documentElement.scrollWidth,errors:__uiErrors})')
            assert state['s'] <= state['w'] + 1 and not state['errors'], (label, state)
            (artifacts / (label + '.png')).write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))

        hidden = browser.call('Page.addScriptToEvaluateOnNewDocument', dict(source='Object.defineProperty(document,"visibilityState",{get:()=>window.__testVisibility||"hidden",configurable:true});'))['identifier']
        viewport(390); navigate('/appointments/create')
        browser.wait('document.querySelector("[data-service-id]")')
        time.sleep(.9)
        assert not browser.evaluate('window.__requests.some(u=>u==="/api/recommendations/impressions")'), 'Hidden tab must not record impressions'
        browser.evaluate('window.__testVisibility="visible";document.dispatchEvent(new Event("visibilitychange"))')
        browser.call('Page.removeScriptToEvaluateOnNewDocument', dict(identifier=hidden))
        browser.wait('window.__requests.some(u=>u==="/api/recommendations/impressions")')
        click(f'[data-service-id="{data["services"][0]}"]')
        browser.wait('window.__requests.some(u=>u.includes("/impressions/")&&u.endsWith("/click"))')
        click('[data-testid=booking-next]'); value('[data-testid=booking-date]', day.isoformat())
        browser.wait('document.querySelector(`[data-slot="13:00"]:not([disabled])`)'); click('[data-slot="13:00"]')
        click('[data-testid=booking-next]'); browser.wait('document.querySelector("[data-testid=booking-submit]")'); click('[data-testid=booking-submit]')
        browser.wait('document.querySelector("[data-testid=booking-success]")')
        with app.app_context():
            assert CustomerBehavior.query.filter_by(makh=data['a'], source='backend', action='book_service').count() == 1
            assert RecommendationImpression.query.filter(RecommendationImpression.clicked_at.isnot(None)).count() >= 1
            assert CustomerBehavior.query.filter_by(makh=data['a'], action='select_service', source='frontend').count() == 1
        screenshot('booking-attribution')

        for width in (360, 390, 768, 1440):
            viewport(width)
            for role in ('admin', 'manager', 'letan', 'staff'):
                app.config['BROWSER_ROLE'] = role; navigate('/admin/crm')
                if role == 'staff':
                    browser.wait('document.body.textContent.includes("Bạn không có quyền xem")')
                    assert not browser.evaluate('window.__requests.some(u=>u.startsWith("/api/admin/crm"))'); continue
                browser.wait('document.querySelector("[data-customer-id]")')
                if role == 'letan': assert not browser.evaluate('window.__requests.some(u=>u.startsWith("/api/admin/recommendations"))')
                else: browser.wait('document.querySelector("[data-testid=recommendation-baseline]")')
                screenshot(f'{width}-crm-{role}')
                if role == 'admin':
                    card = ('.mobile-cards ' if width <= 1100 else '.desktop-table ') + f'[data-customer-id="{data["a"]}"]'
                    click(card); browser.wait('document.querySelector(".ant-drawer-body")?.textContent.includes("Nhắc lịch")')
                    screenshot(f'{width}-history'); click('.ant-drawer-close'); browser.wait('!document.querySelector(".ant-drawer-mask")')
                    browser.evaluate('document.querySelector("[data-testid=recommendation-baseline]").scrollIntoView({block:"start"});window.scrollBy(0,-90)')
                    screenshot(f'{width}-baseline')
            navigate('/profile#communication')
            browser.wait('document.querySelector("#communicationPreferences [type=submit]")?.disabled===false')
            assert browser.evaluate('!document.querySelector("[name=reminders]").checked')
            screenshot(f'{width}-preferences')
            print(f'PASS {width}px CRM roles, history, KPI and customer preferences', flush=True)

        viewport(390); click('[name=reminders]'); click('#communicationPreferences [type=submit]')
        browser.wait('document.querySelector("#communicationStatus").textContent.includes("Đã lưu")')
        with app.app_context():
            assert CustomerPreference.query.one().reminders
            assert NotificationJob.query.filter(NotificationJob.type.like('appointment_reminder%'), NotificationJob.status == 'pending').count() == 4
        screenshot('reminders-opted-in')
        click('[name=reminders]'); click('[name=personalization]'); click('#communicationPreferences [type=submit]')
        browser.wait('document.querySelector("#communicationStatus").textContent.includes("Đã lưu")')
        with app.app_context():
            assert not db.session.get(CustomerPreference, data['a']).personalization
            assert RecommendationImpression.query.filter_by(makh=data['a']).count() == 0
            assert CustomerBehavior.query.filter_by(makh=data['a'], source='frontend').count() == 0
            assert NotificationJob.query.filter_by(status='pending').count() == 0
        screenshot('withdrawn-consent')
        print(json.dumps(dict(result='passed', screenshots=len(list(artifacts.glob('*.png'))), artifacts=str(artifacts))), flush=True)
    except Exception:
        if browser:
            (artifacts / 'failure.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
            (artifacts / 'failure.txt').write_text(browser.evaluate('document.body.innerText'), encoding='utf-8')
            print('Failure artifacts: ' + str(artifacts), flush=True)
        raise
    finally:
        if ws: ws.close()
        server.shutdown(); process.terminate(); process.wait(timeout=10)
        try: next(fixture)
        except StopIteration: pass


if __name__ == '__main__': main()

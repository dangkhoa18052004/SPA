"""Real Chrome: BI permissions, filters/export, runtime visibility and AI transport recovery.

Uses a private in-memory database. No provider requests, email or live business writes.
"""
import base64
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
from billing_browser_check import Browser, free_port
from test_bi_release import bi_records
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, LichHen, ReportExportAudit
from app.services import runtime_service, ai_service, email_service


class ReportBrowser(Browser):
    def wait(self, expression): return super().wait('Boolean(' + expression + ')')


def main():
    artifacts = ROOT / '.test-tmp' / ('phase6-browser-' + uuid4().hex[:8]); artifacts.mkdir(parents=True)
    app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
        SECRET_KEY='phase6-session', JWT_SECRET_KEY='phase6-browser-only-secret-at-least-32-characters',
        BI_REPORTS_ENABLED=True, OBSERVABILITY_ENABLED=True, AUTH_RATE_LIMIT_ENABLED=False,
        AI_CHAT_JOBS_ENABLED=False,
        BUSINESS_PORTAL_ENABLED=True, CUSTOMER_BOOKING_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=True,
        ATTENDANCE_ENABLED=False, ATTENDANCE_SIMPLE_MODE=False, CRM_ENABLED=False,
        RECOMMENDATION_METRICS_ENABLED=False, SEPAY_POLL_ENABLED=False, GEMINI_API_KEY='mock-only'))
    app.logger.setLevel(logging.ERROR)
    email_service.send_email = lambda *a, **k: (_ for _ in ()).throw(AssertionError('No real mail'))
    ai_service.call_gemini = lambda payload: {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'Kết nối đã phục hồi. Bạn có thể xem các dịch vụ tại trang Đặt lịch.'}]}}]}
    with app.app_context():
        db.create_all(); position = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
        db.session.add(position); db.session.flush()
        people = {r: NhanVien(hoten='Kiểm thử ' + r, taikhoan=r, matkhau='hash', role=r if r != 'manager' else 'staff', macv=position.macv, trangthai=True) for r in ('admin', 'staff', 'manager', 'letan')}
        customer = KhachHang(hoten='Khách kiểm thử', taikhoan='customer', matkhau='hash', trangthai='active')
        db.session.add_all([*people.values(), customer]); db.session.commit()
        app.config.update(TEST_ADMIN_ID=people['admin'].manv, TEST_STAFF_ID=people['staff'].manv, TEST_STAFF2_ID=people['manager'].manv, TEST_CUSTOMER_ID=customer.makh)
        actor_ids = {role: person.manv for role, person in people.items()}
    data = bi_records.__wrapped__(app)
    with app.app_context():
        tokens = {role: create_access_token(identity=f'staff:{sid}') for role, sid in actor_ids.items()}
        customer_token = create_access_token(identity=f'customer:{app.config["TEST_CUSTOMER_ID"]}')
        runtime_service.heartbeat()
    app.config['BROWSER_ROLE'] = 'admin'

    @app.before_request
    def bootstrap_session(): session.update(user_id=app.config['TEST_CUSTOMER_ID'], user_type='customer')

    @app.after_request
    def bootstrap_tokens(response):
        if response.mimetype == 'text/html':
            script = 'window.__uiErrors=[];window.__requests=[];addEventListener("error",e=>{if(e.message)__uiErrors.push(e.message)});addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
            script += 'localStorage.setItem("admin_token",' + json.dumps(tokens[app.config['BROWSER_ROLE']]) + ');localStorage.setItem("access_token",' + json.dumps(customer_token) + ');'
            script += 'const originalFetch=fetch.bind(window);window.fetch=(url,...args)=>{__requests.push(String(url));if(window.__failChat&&url==="/api/ai/chat"){window.__failChat=false;return Promise.reject(new TypeError("Failed to fetch"))}return originalFetch(url,...args)};'
            response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + script + '</script>', 1))
        return response

    class QuietHandler(WSGIRequestHandler):
        def log(self, *a, **k): pass
    server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = free_port(); chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    process = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts / "profile"}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = browser = None
    try:
        for _ in range(100):
            try: tabs = json.load(urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1)); break
            except Exception: time.sleep(.1)
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        browser = ReportBrowser(ws); browser.call('Page.enable')
        browser.call('Emulation.setTimezoneOverride', dict(timezoneId='Asia/Ho_Chi_Minh'))
        browser.call('Browser.setDownloadBehavior', dict(behavior='allow', downloadPath=str(artifacts)))
        def navigate(path):
            browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}' + path)); browser.wait('document.readyState==="complete"&&location.pathname===' + json.dumps(path))
        def click(selector): browser.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')
        def screenshot(name):
            time.sleep(.2)
            state = browser.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:__uiErrors})')
            assert state['scroll'] <= state['width'] + 1 and not state['errors'], (name, state)
            (artifacts / (name + '.png')).write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
        def range_values():
            browser.evaluate('for(const [label,value] of [["Báo cáo từ ngày","2026-10-01"],["Báo cáo đến ngày","2026-10-15"]]){const e=document.querySelector(`[aria-label="${label}"]`);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(e,value);e.dispatchEvent(new Event("input",{bubbles:true}))}')
            browser.evaluate('document.querySelector(".report-filters form").requestSubmit()')
        for width in (360, 390, 768, 1440):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))
            for role in ('admin', 'manager', 'letan', 'staff'):
                app.config['BROWSER_ROLE'] = role; navigate('/admin/reports')
                if role in ('staff', 'letan'):
                    browser.wait('document.body.textContent.includes("Bạn không có quyền xem báo cáo này")')
                    assert not browser.evaluate('__requests.some(u=>u.startsWith("/api/admin/bi/"))')
                    screenshot(f'{width}-{role}-forbidden'); continue
                browser.wait('document.querySelector(".report-filters form")'); range_values()
                browser.wait('!document.querySelector(".ant-skeleton") && document.querySelector("[data-testid=bi-report]")')
                browser.wait('document.body.textContent.includes("550.000")' if role == 'admin' else 'document.body.textContent.includes("chưa có thông tin cơ sở đáng tin cậy")')
                assert not browser.evaluate('document.body.textContent.includes("550.000")') if role == 'manager' else True
                screenshot(f'{width}-{role}-report')
                browser.evaluate('document.querySelector("[data-testid=bi-report]").scrollIntoView({block:"start"})'); screenshot(f'{width}-{role}-numbers')
                if role == 'admin':
                    click('[data-testid=bi-export]')
                    browser.wait('!document.querySelector("[data-testid=bi-export]").classList.contains("ant-btn-loading")')
                    browser.evaluate('[...document.querySelectorAll("button")].find(e=>e.textContent==="Giám sát hệ thống").click()')
                    browser.wait('document.querySelector("[data-testid=runtime-panel]") && !document.querySelector(".ant-skeleton")')
                    browser.evaluate('window.scrollTo(0,0)'); screenshot(f'{width}-runtime')
                else:
                    assert not browser.evaluate('__requests.some(u=>u.startsWith("/api/admin/runtime/"))')
            app.config['BROWSER_ROLE'] = 'admin'; navigate('/')
            browser.wait('document.querySelector(".ai-fab")'); click('.ai-fab')
            prior_messages = browser.evaluate('document.querySelectorAll(".ai-user").length')
            browser.evaluate('window.__failChat=true'); click('[data-quick] button')
            browser.wait('document.querySelector("[data-retry]")')
            assert browser.evaluate('document.querySelector(".ai-error").textContent.includes("Mất kết nối")')
            screenshot(f'{width}-ai-network-error')
            click('[data-retry]'); browser.wait('document.querySelector(".ai-log").textContent.includes("Kết nối đã phục hồi")')
            assert browser.evaluate('document.querySelectorAll(".ai-user").length') == prior_messages + 1
            screenshot(f'{width}-ai-recovered')
            print(f'PASS {width}px: report scopes/roles/CSV, admin runtime, AI network error and explicit retry', flush=True)
        with app.app_context():
            assert ReportExportAudit.query.count() == 4
            assert LichHen.query.count() == 7, 'Chat must not create bookings'
        # Headless Chrome may overwrite repeated same-name downloads; every request
        # is independently verified by its export audit, and the saved CSV by content.
        exports = list(artifacts.glob('*.csv'))
        assert exports and all('550000.00' in path.read_text(encoding='utf-8-sig') for path in exports)
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


if __name__ == '__main__': main()

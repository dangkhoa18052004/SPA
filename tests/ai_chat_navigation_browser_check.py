"""Real page unload, lost enqueue acknowledgement, restored draft and account isolation.

Private SQLite file and mocked AI/email. The AI worker runs independently of the page.
"""
import base64
from datetime import datetime, timedelta, time as day_time
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

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import websocket
from flask import session
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler
from billing_browser_check import Browser, free_port
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, DichVu, CaLam, nhanvien_calam, AIChatJob, LichHen
from app.services import ai_service, ai_chat_jobs, appointment_service, package_service as ps, email_service


class ChatBrowser(Browser):
    def wait(self, expression): return super().wait('Boolean(' + expression + ')')


def main():
    artifacts = ROOT / '.test-tmp' / ('ai-chat-navigation-' + uuid4().hex[:8]); artifacts.mkdir(parents=True)
    app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite:///' + (artifacts / 'test.db').as_posix(),
        SECRET_KEY='chat-navigation-session', JWT_SECRET_KEY='chat-navigation-private-at-least-32-chars',
        AI_CHAT_JOBS_ENABLED=True, GEMINI_API_KEY='mock-only', AUTH_RATE_LIMIT_ENABLED=False, OBSERVABILITY_ENABLED=False,
        ATTENDANCE_ENABLED=False, CUSTOMER_BOOKING_REACT_ENABLED=True, RECOMMENDATION_METRICS_ENABLED=False, SEPAY_POLL_ENABLED=False))
    app.logger.setLevel(logging.ERROR)
    appointment_service.send_appointment_confirmation_email_async = lambda *a, **k: None
    email_service.send_email = lambda *a, **k: (_ for _ in ()).throw(AssertionError('No mail'))
    with app.app_context():
        db.create_all()
        role = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000); db.session.add(role); db.session.flush()
        staff = NhanVien(hoten='Nhân viên kiểm thử', taikhoan='staff', matkhau='hash', role='staff', macv=role.macv, trangthai=True)
        users = [KhachHang(hoten='Khách ' + k, taikhoan='customer-' + k, matkhau='hash', trangthai='active') for k in ('A', 'B')]
        service = DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=30, active=True)
        db.session.add_all([staff, *users, service]); db.session.flush()
        day = ps.local_now().date() + timedelta(days=3)
        shift = CaLam(ngay=day, giobatdau=day_time(9), gioketthuc=day_time(18), sogio=9)
        db.session.add(shift); db.session.flush(); db.session.execute(nhanvien_calam.insert().values(manv=staff.manv, maca=shift.maca)); db.session.commit()
        user_ids = [u.makh for u in users]
        tokens = [create_access_token(identity=f'customer:{uid}') for uid in user_ids]
        service_id = service.madv
    app.config['BROWSER_OWNER'] = 0
    started, finish, stop = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def respond(message, history=None, actor=None):
        calls.append(message); started.set()
        assert finish.wait(15), 'Browser must release the mocked AI after navigation'
        draft = ai_service.create_booking_draft_tool(madv_list=[service_id], ngaygio=day.isoformat() + 'T10:00', actor=actor) if 'bản nháp' in message else None
        return dict(reply='Câu trả lời vẫn được giữ khi bạn chuyển trang.', draft=draft, tools_used=[], guarded=False)
    ai_service.chat = respond
    def worker():
        while not stop.is_set():
            with app.app_context(): ai_chat_jobs.process_next()
            stop.wait(.05)
    thread = threading.Thread(target=worker, daemon=True); thread.start()

    @app.before_request
    def bootstrap_owner():
        session.update(user_id=user_ids[app.config['BROWSER_OWNER']], user_type='customer')

    @app.after_request
    def bootstrap_tokens(response):
        if response.mimetype == 'text/html':
            script = 'localStorage.setItem("access_token",' + json.dumps(tokens[app.config['BROWSER_OWNER']]) + ');'
            script += 'window.__uiErrors=[];addEventListener("error",e=>{if(e.message)__uiErrors.push(e.message)});addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
            script += 'const realFetch=fetch.bind(window);window.fetch=async(url,...args)=>{const r=await realFetch(url,...args);if(window.__loseAck&&url==="/api/ai/chat/jobs"){window.__loseAck=false;throw new TypeError("acknowledgement lost")}return r};'
            response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + script + '</script>', 1))
        return response
    class QuietHandler(WSGIRequestHandler):
        def log(self, *a, **k): pass
    server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = free_port(); chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    process = subprocess.Popen([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts / "profile"}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = browser = None
    try:
        for _ in range(100):
            try: tabs = json.load(urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1)); break
            except Exception: time.sleep(.1)
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        browser = ChatBrowser(ws); browser.call('Page.enable')
        def navigate(path):
            browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}' + path))
            browser.wait('location.pathname===' + json.dumps(path) + '&&document.readyState==="complete"&&document.querySelector(".ai-fab")')
        def click(selector): browser.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')
        def send(text):
            started.clear(); finish.clear()
            browser.evaluate('document.querySelector("[data-form] input").value=' + json.dumps(text) + ';document.querySelector("[data-form]").requestSubmit()')
            assert started.wait(5), 'AI worker did not receive the question'
        def screenshot(name):
            assert browser.evaluate('document.documentElement.scrollWidth<=innerWidth+1&&!__uiErrors.length'), browser.evaluate('__uiErrors')
            (artifacts / (name + '.png')).write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
        def pending_id():
            return browser.evaluate('JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.endsWith(".pending")))).id')
        for width in (360, 1440):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))
            navigate('/')
            if width == 360: browser.evaluate('Object.defineProperty(crypto,"randomUUID",{value:undefined,configurable:true})')
            if browser.evaluate('document.querySelector(".ai-panel").hidden'): click('.ai-fab')
            before = len(calls); send('Hỏi khi chuyển trang ' + str(width)); request_id = pending_id()
            navigate('/services'); browser.wait('!document.querySelector(".ai-panel").hidden')
            assert pending_id() == request_id
            navigate('/appointments/create'); browser.wait('!document.querySelector(".ai-panel").hidden')
            screenshot(f'{width}-waiting-after-navigation')
            finish.set(); browser.wait('!document.querySelector("[data-form] button").disabled && !document.querySelector(".ai-progress")')
            screenshot(f'{width}-answer-on-booking-page')
            browser.call('Page.reload'); browser.wait('document.querySelector(".ai-log")?.textContent.includes("Hỏi khi chuyển trang ' + str(width) + '")')
            assert browser.evaluate('document.querySelector(".ai-log").textContent.split(' + json.dumps('Hỏi khi chuyển trang ' + str(width)) + ').length-1') == 1
            assert len(calls) == before + 1
            print(f'PASS {width}px: home -> services -> React booking -> reload, AI called once', flush=True)

        browser.evaluate('window.__loseAck=true'); before = len(calls)
        send('Kiểm tra mất phản hồi nhận câu hỏi'); request_id = pending_id()
        navigate('/packages'); browser.wait('document.querySelector(".ai-log").textContent.includes("Kiểm tra mất phản hồi")')
        assert pending_id() == request_id
        finish.set(); browser.wait('!document.querySelector("[data-form] button").disabled')
        assert len(calls) == before + 1
        screenshot('lost-ack-recovered')

        send('Tạo bản nháp giúp tôi'); finish.set(); browser.wait('document.querySelector("[data-confirm]")')
        navigate('/services'); browser.wait('document.querySelector("[data-confirm]")')
        screenshot('draft-restored-after-navigation')
        click('[data-confirm]'); browser.wait('document.querySelector(".ai-draft-status").textContent.includes("Mã lịch")')
        navigate('/profile'); browser.wait('document.querySelector(".ai-draft-status")?.textContent.includes("Đã xác nhận lịch")')
        assert not browser.evaluate('document.querySelector("[data-confirm]")')
        screenshot('confirmed-draft-restored')
        app.config['BROWSER_OWNER'] = 1; navigate('/services'); click('.ai-fab')
        assert not browser.evaluate('document.querySelector(".ai-log").textContent.includes("Hỏi khi chuyển trang")')
        assert browser.evaluate('fetch("/api/ai/chat/jobs/' + request_id + '",{headers:{Authorization:"Bearer "+localStorage.getItem("access_token")}}).then(r=>r.status)') == 404
        screenshot('other-customer-isolated')
        with app.app_context():
            assert AIChatJob.query.count() == 4 and LichHen.query.count() == 1
        print('PASS lost ack, draft/confirmation persistence, private account switch', flush=True)
        print('Screenshots: ' + str(artifacts), flush=True)
    except Exception:
        if browser:
            (artifacts / 'failure.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
            (artifacts / 'failure.txt').write_text(browser.evaluate('document.body.innerText'), encoding='utf-8')
            print('Failure artifacts: ' + str(artifacts), flush=True)
        raise
    finally:
        finish.set(); stop.set(); thread.join(timeout=10)
        if ws: ws.close()
        server.shutdown(); process.terminate(); process.wait(timeout=10)


if __name__ == '__main__': main()

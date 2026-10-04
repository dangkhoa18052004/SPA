"""Real Edge check of the gift desk: letan looks up a code, hands over the gift, customer sees it received."""
import base64
import json
import logging
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import websocket
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from billing_browser_check import Browser, free_port
from app.extensions import db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app.models import ChucVu, LoyaltyRewardRedemption, NhanVien
from app.services import loyalty_service as loyalty

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    with app.app_context():
        customer = app.config['TEST_CUSTOMER_ID']
        loyalty.admin_adjust_points(customer, 500, 'Initial', app.config['TEST_ADMIN_ID'], 'initial')
        gift = loyalty.save_reward(dict(name='Khăn tắm Bin Spa', reward_type='physical_gift', points_cost=100, validity_days=30))
        fresh = loyalty.redeem_reward(customer, gift.id, 'fresh')
        expired = loyalty.redeem_reward(customer, gift.id, 'expired')
        expired.expires_at = datetime.utcnow() - timedelta(days=1)
        letan = NhanVien(hoten='Lễ tân Hoa', sdt='0911000111', diachi='Bin Spa', email='letan@example.com', taikhoan='letan_desk',
                         matkhau=generate_password_hash('password'), macv=ChucVu.query.first().macv, role='letan', trangthai=True)
        db.session.add(letan)
        db.session.commit()
        fresh_id, fresh_code, expired_code, letan_id = fresh.id, fresh.code, expired.code, letan.manv
        letan_token = create_access_token(identity=f'staff:{letan_id}')
        customer_token = create_access_token(identity=f'customer:{customer}')
    server = make_server('127.0.0.1', 0, app, threaded=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    port = free_port()
    artifacts = Path('tests') / ('loyalty-gift-desk-' + str(port) + '.tmp')
    artifacts.mkdir()
    process = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts.resolve() / "profile"}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1) as r:
                    tab = next(t for t in json.load(r) if t['type'] == 'page')
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(.2)
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        b = Browser(ws)
        b.call('Page.enable')
        b.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        b.call('Page.addScriptToEvaluateOnNewDocument', dict(source=
            'window.__doc=Math.random();window.__errors=[];window.addEventListener("error",e=>{if(e.message)__errors.push(e.message)});'
            'window.addEventListener("unhandledrejection",e=>__errors.push(String(e.reason)));'
            'localStorage.setItem("admin_token",' + json.dumps(letan_token) + ');localStorage.setItem("admin_role","letan");'
            'localStorage.setItem("admin_user",JSON.stringify({hoten:"Lễ tân",role:"letan"}));'
            'localStorage.setItem("access_token",' + json.dumps(customer_token) + ');'))

        def navigate(path):
            old = b.evaluate('window.__doc')
            b.call('Page.navigate', dict(url=base + path))
            b.wait('window.__doc && window.__doc!==' + json.dumps(old) + ' && document.readyState==="complete"')

        def screenshot(name):
            (artifacts / name).write_bytes(base64.b64decode(b.call('Page.captureScreenshot', dict(format='png'))['data']))

        def search(term):
            b.evaluate('(()=>{const f=document.querySelector("[data-desk]");f.elements.search.value=' + json.dumps(term) + ';f.requestSubmit()})()')
            b.wait('document.querySelectorAll("[data-redemption]").length===1 && document.querySelector("[data-redemption] code").textContent===' + json.dumps(term))

        navigate('/admin/loyalty?tab=redemptions')
        b.wait('!!document.querySelector("[data-desk]") && [...document.querySelectorAll("#sidebar-menu a")].some(a=>a.textContent.includes("Đổi quà / Tra mã"))')
        assert b.evaluate('[...document.querySelectorAll("[data-tab]")].map(t=>t.dataset.tab)') == ['redemptions']
        assert b.evaluate('location.pathname') == '/admin/loyalty'
        search(expired_code)
        row = b.evaluate('document.querySelector("[data-redemption]").innerText')
        assert 'Hết hạn' in row and not b.evaluate('!!document.querySelector("[data-fulfill]")'), row
        search(fresh_code)
        row = b.evaluate('document.querySelector("[data-redemption]").innerText')
        for expected in ('Khách hàng Test', '0900000002', 'Khăn tắm Bin Spa', 'Quà tại cửa hàng', fresh_code, '100', 'Chờ nhận quà'):
            assert expected in row, (expected, row)
        screenshot('desk-lookup.png')
        b.evaluate('document.querySelector("[data-fulfill]").click()')
        b.wait('document.getElementById("giftHandover").open')
        assert fresh_code in b.evaluate('document.getElementById("giftHandover").innerText')
        assert b.evaluate('document.activeElement.id') == 'giftHandoverConfirm'
        screenshot('desk-confirm.png')
        b.evaluate('document.getElementById("giftHandoverConfirm").click()')
        b.wait('!document.getElementById("giftHandover").open && document.getElementById("loyaltyMessage").textContent.includes("Đã xác nhận giao")')
        b.wait('document.querySelector("[data-redemption]")?.innerText.includes("Đã giao quà")')
        row = b.evaluate('document.querySelector("[data-redemption]").innerText')
        assert 'Lễ tân Hoa' in row and not b.evaluate('!!document.querySelector("[data-fulfill]")'), row
        with app.app_context():
            saved = db.session.get(LoyaltyRewardRedemption, fresh_id)
            assert (saved.status, saved.fulfilled_by_staff) == ('fulfilled', letan_id) and saved.fulfilled_at
        screenshot('desk-done.png')

        b.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=2, mobile=True))
        navigate('/admin/loyalty?tab=redemptions'); b.wait('document.querySelectorAll("[data-redemption]").length===2')
        assert b.evaluate('document.querySelector(".loyalty-table").getBoundingClientRect().right') <= 390
        screenshot('desk-390.png')

        navigate('/profile?loyalty_view=mine&loyalty_status=done#loyalty')
        b.wait('document.querySelectorAll(".loyalty-offer").length===1')
        offer = b.evaluate('document.querySelector(".loyalty-offer").innerText')
        assert 'Đã nhận quà' in offer and 'Ngày nhận quà' in offer and 'Bạn đã nhận quà lúc' in offer, offer
        screenshot('customer-received.png')
        assert b.evaluate('window.__errors') == [], b.evaluate('window.__errors')
        print('PASS: letan sees only the gift desk, code lookup, expired has no handover, confirm dialog, fulfilled by letan, 390px, customer sees received date.')
        print('Artifacts:', artifacts)
    except Exception:
        if ws:
            try:
                screenshot('failure.png')
                (artifacts / 'failure.json').write_text(json.dumps(b.evaluate('({url:location.href,errors:window.__errors,text:document.body.innerText})'),
                    ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass
        raise
    finally:
        if ws:
            ws.close()
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
        server.shutdown()
        try:
            next(fixture)
        except StopIteration:
            pass


if __name__ == '__main__':
    main()

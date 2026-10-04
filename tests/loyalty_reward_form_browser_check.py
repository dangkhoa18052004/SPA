"""Real Edge check of the admin reward form (voucher terms vs physical gift), isolated SQLite."""
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
from app.models import LoyaltyReward

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    with app.app_context():
        admin_token = create_access_token(identity=f"staff:{app.config['TEST_ADMIN_ID']}")
    server = make_server('127.0.0.1', 0, app, threaded=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    port = free_port()
    artifacts = Path('tests') / ('loyalty-reward-form-' + str(port) + '.tmp')
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
            'localStorage.setItem("admin_token",' + json.dumps(admin_token) + ');localStorage.setItem("admin_role","admin");'
            'localStorage.setItem("admin_user",JSON.stringify({hoten:"Admin",role:"admin"}));'))

        def navigate(path):
            old = b.evaluate('window.__doc')
            b.call('Page.navigate', dict(url=base + path))
            b.wait('window.__doc && window.__doc!==' + json.dumps(old) + ' && document.readyState==="complete"')

        def screenshot(name):
            (artifacts / name).write_bytes(base64.b64decode(b.call('Page.captureScreenshot', dict(format='png'))['data']))

        def visible(name):
            return b.evaluate(f'(()=>{{const e=document.getElementById("rewardForm").elements[{json.dumps(name)}];return !!e && e.offsetParent!==null}})()')

        def submit_and_wait():
            b.evaluate('document.getElementById("rewardForm").requestSubmit()')
            b.wait('!document.getElementById("loyaltyRewardEditor").open')

        def form(js):
            return b.evaluate('(()=>{const f=document.getElementById("rewardForm");' + js + '})()')

        navigate('/admin/loyalty')
        # A failing tab must replace the previous tab's content with a clear error, and retry must recover.
        b.wait('document.querySelectorAll(".loyalty-cards .loyalty-card").length>0')
        b.evaluate('window.__realFetch=window.fetch;window.fetch=(u,o)=>String(u).includes("/api/admin/loyalty/rewards")?Promise.resolve(new Response("<h1>500</h1>",{status:500})):window.__realFetch(u,o)')
        b.evaluate('document.querySelector(\'[data-tab="rewards"]\').click()')
        b.wait('!!document.querySelector("#loyaltyContent [data-reload]")')
        failed = b.evaluate('document.getElementById("loyaltyContent").innerText')
        assert 'Không tải được “Quà đổi thưởng”' in failed and 'mã 500' in failed, failed
        assert not b.evaluate('!!document.querySelector("#loyaltyContent .loyalty-cards")'), 'stale overview content still shown'
        screenshot('tab-error.png')
        b.evaluate('window.fetch=window.__realFetch;document.querySelector("#loyaltyContent [data-reload]").click()')
        b.wait('!!document.querySelector("[data-new]")')
        b.evaluate('document.querySelector("[data-new]").click()')
        b.wait('document.getElementById("loyaltyRewardEditor").open')
        assert all(visible(n) for n in ('name', 'description', 'points_cost', 'reward_value', 'apply_to', 'minimum_spend', 'stock', 'validity_days', 'active'))
        assert form('return f.querySelector("[data-name-label]").textContent') == 'Tên voucher'
        assert form('return [...f.elements.apply_to.options].map(o=>o.textContent)') == ['Cả hai', 'Hóa đơn dịch vụ', 'Mua gói']
        screenshot('voucher-form.png')
        # An empty voucher value is blocked by the browser before any request.
        form('f.elements.name.value="Voucher 50k";f.elements.points_cost.value="200";return 1')
        assert form('return f.checkValidity()') is False
        form('f.elements.reward_value.value="50000";f.elements.apply_to.value="service_invoice";f.elements.minimum_spend.value="300000";'
             'f.elements.stock.value="5";f.elements.validity_days.value="30";return 1')
        submit_and_wait()
        b.wait('document.getElementById("loyaltyContent").textContent.includes("Đơn từ")')
        assert b.evaluate('document.getElementById("loyaltyContent").textContent.includes("Hóa đơn dịch vụ")')

        b.evaluate('document.querySelector("[data-new]").click()')
        b.wait('document.getElementById("loyaltyRewardEditor").open')
        form('f.elements.reward_type.value="physical_gift";f.elements.reward_type.dispatchEvent(new Event("change"));return 1')
        assert not any(visible(n) for n in ('reward_value', 'apply_to', 'minimum_spend'))
        assert all(visible(n) for n in ('name', 'description', 'points_cost', 'stock', 'validity_days', 'active'))
        assert form('return f.querySelector("[data-name-label]").textContent') == 'Tên quà'
        form('f.elements.name.value="Khăn Bin Spa";f.elements.points_cost.value="100";return 1')
        assert form('return f.checkValidity()') is True
        screenshot('gift-form.png')
        submit_and_wait()
        b.wait('document.getElementById("loyaltyContent").textContent.includes("Khăn Bin Spa")')

        with app.app_context():
            voucher = LoyaltyReward.query.filter_by(name='Voucher 50k').one()
            gift = LoyaltyReward.query.filter_by(name='Khăn Bin Spa').one()
            assert (voucher.apply_to, int(voucher.minimum_spend), int(voucher.reward_value), voucher.stock, voucher.validity_days) == ('service_invoice', 300000, 50000, 5, 30)
            assert (gift.reward_type, int(gift.reward_value), gift.apply_to, gift.minimum_spend) == ('physical_gift', 0, None, None)
            voucher_id = voucher.id

        # Editing loads stored terms; switching back to voucher re-enables its fields.
        b.evaluate(f'document.querySelector(\'[data-edit="{voucher_id}"]\').click()')
        b.wait('document.getElementById("loyaltyRewardEditor").open')
        assert form('return [f.elements.apply_to.value,f.elements.minimum_spend.value,f.elements.reward_value.value]') == ['service_invoice', '300000', '50000']
        form('f.elements.apply_to.value="package_purchase";return 1')
        submit_and_wait()
        with app.app_context():
            db.session.expire_all()
            assert db.session.get(LoyaltyReward, voucher_id).apply_to == 'package_purchase'

        # Percentage voucher: % and cap replace the fixed value; scope/minimum stay.
        b.evaluate('document.querySelector("[data-new]").click()')
        b.wait('document.getElementById("loyaltyRewardEditor").open')
        form('f.elements.reward_type.value="voucher_percent";f.elements.reward_type.dispatchEvent(new Event("change"));return 1')
        assert all(visible(n) for n in ('percentage_value', 'max_discount_amount', 'apply_to', 'minimum_spend', 'points_cost', 'stock', 'validity_days', 'active'))
        assert not visible('reward_value')
        form('f.elements.name.value="GIẢM 10%";f.elements.points_cost.value="300";f.elements.percentage_value.value="101";return 1')
        assert form('return f.checkValidity()') is False
        form('f.elements.percentage_value.value="10";f.elements.max_discount_amount.value="100000";f.elements.minimum_spend.value="300000";'
             'f.elements.apply_to.value="both";f.elements.validity_days.value="30";return 1')
        screenshot('percent-form.png')
        submit_and_wait()
        b.wait('document.getElementById("loyaltyContent").textContent.includes("Voucher giảm 10%")')
        assert 'tối đa 100.000' in b.evaluate('document.getElementById("loyaltyContent").textContent')
        with app.app_context():
            percent = LoyaltyReward.query.filter_by(name='GIẢM 10%').one()
            assert (percent.reward_type, float(percent.percentage_value), int(percent.max_discount_amount), int(percent.reward_value), percent.apply_to) == (
                'voucher_percent', 10.0, 100000, 0, 'both')
            percent_id = percent.id
        b.evaluate('document.querySelector(' + json.dumps(f'[data-edit="{percent_id}"]') + ').click()')
        b.wait('document.getElementById("loyaltyRewardEditor").open')
        assert form('return [f.elements.reward_type.value,f.elements.percentage_value.value,f.elements.max_discount_amount.value]') == ['voucher_percent', '10', '100000']
        b.evaluate('document.getElementById("loyaltyRewardEditor").close()')

        b.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=2, mobile=True))
        b.evaluate('document.querySelector("[data-new]").click()')
        b.wait('document.getElementById("loyaltyRewardEditor").open')
        assert b.evaluate('document.getElementById("loyaltyRewardEditor").getBoundingClientRect().width') <= 390
        screenshot('voucher-form-390.png')
        assert b.evaluate('window.__errors') == [], b.evaluate('window.__errors')
        print('PASS: voucher form shows value/scope/minimum, percent form shows %/cap, gift form hides them, browser validation, create/edit persisted, 390px dialog, no JS errors.')
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

"""Real Edge checks for customer Đổi thưởng / Ưu đãi của tôi. Isolated SQLite, no real money.

Run: venv\\Scripts\\python.exe tests\\loyalty_customer_browser_check.py
"""
import base64
import json
import logging
from datetime import datetime, timedelta
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
from app.models import HoaDon, LoyaltyRewardRedemption, LoyaltyWallet
from app.services import loyalty_service as loyalty

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__(); app = next(fixture)
    with app.app_context():
        customer = app.config['TEST_CUSTOMER_ID']; staff = app.config['TEST_ADMIN_ID']
        loyalty.admin_adjust_points(customer, 1000, 'Initial', staff, 'initial')
        voucher = loyalty.save_reward(dict(name='Voucher 50.000', description='Giảm trực tiếp khi thanh toán', reward_type='voucher_amount', points_cost=200, reward_value=50000, stock=3, validity_days=30, apply_to='both', minimum_spend=200000))
        gift = loyalty.save_reward(dict(name='Khăn tắm Bin Spa', reward_type='physical_gift', points_cost=100, reward_value=0, stock=2))
        loyalty.save_reward(dict(name='Liệu trình VIP', reward_type='voucher_amount', points_cost=5000, reward_value=900000))
        old = loyalty.redeem_reward(customer, voucher.id, 'old-voucher')
        old.expires_at = datetime.utcnow() - timedelta(days=1)
        invoice = HoaDon(makh=customer, manv=staff, tongtien=500000); db.session.add(invoice); db.session.flush()
        # 100 points held by a pending invoice: customers must see 700 available, never 800 or "đang giữ".
        loyalty.reserve_points(invoice, 100)
        db.session.commit()
        iid, voucher_id, gift_id = invoice.mahd, voucher.id, gift.id
        admin_token = create_access_token(identity=f'staff:{staff}')
        customer_token = create_access_token(identity=f'customer:{customer}')
    server = make_server('127.0.0.1', 0, app, threaded=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'; port = free_port()
    artifacts = Path('tests') / ('loyalty-customer-browser-' + str(port) + '.tmp'); artifacts.mkdir()
    process = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-allow-origins=*', f'--remote-debugging-port={port}', f'--user-data-dir={artifacts.resolve()/"profile"}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1) as r: tabs = json.load(r)
                tab = next(t for t in tabs if t['type'] == 'page'); break
            except Exception:
                if time.monotonic() > deadline: raise
                time.sleep(.2)
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=20, suppress_origin=True)
        b = Browser(ws); b.call('Page.enable')
        b.call('Emulation.setTimezoneOverride', dict(timezoneId='Asia/Ho_Chi_Minh'))
        b.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        b.call('Page.addScriptToEvaluateOnNewDocument', dict(source=
            'window.__doc=Math.random();window.__errors=[];window.addEventListener("error",e=>{if(e.message)__errors.push(e.message)});window.addEventListener("unhandledrejection",e=>__errors.push(String(e.reason)));' +
            'localStorage.setItem("admin_token",' + json.dumps(admin_token) + ');localStorage.setItem("admin_role","admin");localStorage.setItem("admin_user",JSON.stringify({hoten:"Admin",role:"admin"}));' +
            'localStorage.setItem("access_token",' + json.dumps(customer_token) + ');'))

        def navigate(path):
            old_doc = b.evaluate('window.__doc'); b.call('Page.navigate', dict(url=base + path))
            b.wait('window.__doc && window.__doc!==' + json.dumps(old_doc) + ' && document.readyState==="complete"')
        def reload():
            old_doc = b.evaluate('window.__doc'); b.call('Page.reload')
            b.wait('window.__doc && window.__doc!==' + json.dumps(old_doc) + ' && document.readyState==="complete"')
        def click(selector): b.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')
        def text(selector='#loyalty-section'): return b.evaluate('document.querySelector(' + json.dumps(selector) + ')?.innerText||""')
        def screenshot(name): (artifacts / name).write_bytes(base64.b64decode(b.call('Page.captureScreenshot', dict(format='png'))['data']))
        def errors(): assert b.evaluate('window.__errors') == [], b.evaluate('window.__errors')
        def redemptions():
            with app.app_context(): return LoyaltyRewardRedemption.query.count()
        def no_reserved(where):
            body = text(where).lower()
            assert 'đang giữ' not in body and 'điểm giữ' not in body, (where, body)

        # T01/T02: wallet shows three metrics and only spendable points.
        navigate('/profile#loyalty'); b.wait('document.querySelectorAll("#loyaltyBalance .loyalty-card").length===4 && !!document.querySelector("#loyaltyBalance .loyalty-tier-card")')
        assert '700' in text('#loyaltyBalance') and '800' not in text('#loyaltyBalance'), text('#loyaltyBalance')
        no_reserved('#loyalty-section'); screenshot('wallet.png')

        # Catalog: tab URL, missing points hint, backend filters.
        click('[data-loyalty-view="rewards"]'); b.wait('document.querySelectorAll("[data-redeem]").length===3')
        assert 'loyalty_view=rewards' in b.evaluate('location.search')
        assert 'Cần thêm 4300 điểm' in text()
        b.evaluate('document.querySelector("[data-filter] [name=affordable_only]").click()')
        b.wait('document.querySelectorAll("[data-redeem]").length===2')
        b.evaluate('{const f=document.querySelector("[data-filter]");f.elements.reward_type.value="physical_gift";f.elements.reward_type.dispatchEvent(new Event("change"))}')
        b.wait('document.querySelectorAll("[data-redeem]").length===1 && document.querySelector("[data-redeem]").dataset.redeem==="%d"' % gift_id)
        b.evaluate('{const f=document.querySelector("[data-filter]");f.elements.reward_type.value="";f.elements.affordable_only.checked=false;f.requestSubmit()}')
        b.wait('document.querySelectorAll("[data-redeem]").length===3'); screenshot('catalog.png')
        card = b.evaluate('document.querySelector(' + json.dumps(f'[data-redeem="{voucher_id}"]') + ').closest("article").innerText')
        for expected in ('Voucher 50.000', '200 điểm', 'Giảm', '50.000', 'Dịch vụ và gói', 'Đơn tối thiểu', '200.000', '30 ngày sau khi đổi', 'Còn 2 quà'):
            assert expected in card, (expected, card)
        vip_text = b.evaluate('[...document.querySelectorAll("article.loyalty-reward")].find(a=>a.innerText.includes("Liệu trình VIP")).innerText')
        assert 'Cần thêm 4300 điểm' in vip_text and 'Chưa đủ điểm' in vip_text, vip_text
        assert b.evaluate('[...document.querySelectorAll("article.loyalty-reward")].find(a=>a.innerText.includes("Liệu trình VIP")).querySelector("[data-redeem]").disabled')
        gift_card = b.evaluate('document.querySelector(' + json.dumps(f'[data-redeem="{gift_id}"]') + ').closest("article").innerText')
        assert 'Quà nhận tại Bin Spa' in gift_card and 'Đơn tối thiểu' not in gift_card, gift_card

        # T04: opening and cancelling the dialog never redeems.
        before = redemptions()
        click(f'[data-redeem="{voucher_id}"]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        dialog_text = text('#loyaltyRewardDialog')
        for expected in ('Điểm hiện có', '700 điểm', 'Điểm dùng', 'Điểm còn lại', '500 điểm', 'Giảm', 'Dịch vụ và gói', 'Đơn tối thiểu', '200.000', '30 ngày sau khi đổi'):
            assert expected in dialog_text, (expected, dialog_text)
        no_reserved('#loyaltyRewardDialog'); screenshot('confirm.png')
        click('#loyaltyRewardDialog [data-cancel]'); b.wait('!document.getElementById("loyaltyRewardDialog").open')
        assert redemptions() == before

        # T05/T07: double click on confirm creates exactly one redemption and lands on the new offer.
        click(f'[data-redeem="{voucher_id}"]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        b.evaluate('{const c=document.querySelector("#loyaltyRewardDialog [data-confirm]");c.click();c.click()}')
        b.wait('location.search.includes("loyalty_view=mine") && !!document.querySelector(".loyalty-offer.is-new") && !!document.querySelector("#loyaltyRewardDialog [data-success]")')
        assert redemptions() == before + 1
        assert 'thành công' in text('#customerLoyaltyMessage')
        success = text('#loyaltyRewardDialog')
        for expected in ('Đổi thưởng thành công', 'Voucher 50.000', 'BIN-', 'Điểm đã dùng', '200 điểm', 'Điểm còn lại', '500 điểm', 'Xem ưu đãi của tôi'):
            assert expected in success, (expected, success)
        assert b.evaluate('document.activeElement.hasAttribute("data-view-offers")')
        no_reserved('#loyaltyRewardDialog'); screenshot('success.png')
        click('#loyaltyRewardDialog [data-view-offers]'); b.wait('!document.getElementById("loyaltyRewardDialog").open')
        assert b.evaluate('document.activeElement.classList.contains("is-new")')
        new_offer = b.evaluate('document.activeElement.innerText')
        for expected in ('Có thể sử dụng', 'Mã ưu đãi', 'Dịch vụ và gói', 'Đơn tối thiểu', 'Ngày đổi', 'Hạn dùng'):
            assert expected in new_offer, (expected, new_offer)
        assert '500' in text('#loyaltyBalance'); screenshot('mine-new.png')

        # T07: response lost after the server processed it -> retry (even after reload) reuses the key.
        click('[data-loyalty-view="rewards"]'); b.wait(f'!!document.querySelector(\'[data-redeem="{gift_id}"]\')')
        b.evaluate('{const real=CustomerAuth.fetch.bind(CustomerAuth);CustomerAuth.fetch=async(u,o)=>{const r=await real(u,o);if(u.includes("/redeem"))throw new TypeError("Failed to fetch");return r;}}')
        click(f'[data-redeem="{gift_id}"]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        click('#loyaltyRewardDialog [data-confirm]')
        b.wait('document.querySelector("#loyaltyRewardDialog [data-confirm]").textContent==="Thử lại"')
        assert redemptions() == before + 2
        assert b.evaluate('JSON.parse(sessionStorage.getItem("binspa.loyalty.pendingRedeem")).reward_id') == gift_id
        assert 'loyalty_view=rewards' in b.evaluate('location.search')
        reload(); b.wait('!!document.querySelector("[data-pending-retry]")')
        click('[data-pending-retry]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        assert 'không trừ điểm hai lần' in text('#loyaltyRewardDialog')
        click('#loyaltyRewardDialog [data-confirm]')
        b.wait('location.search.includes("loyalty_status=pickup") && !!document.querySelector(".loyalty-offer.is-new") && !!document.querySelector("#loyaltyRewardDialog [data-success]")')
        click('#loyaltyRewardDialog [data-view-offers]'); b.wait('!document.getElementById("loyaltyRewardDialog").open')
        assert redemptions() == before + 2 and b.evaluate('sessionStorage.getItem("binspa.loyalty.pendingRedeem")') is None
        with app.app_context():
            assert LoyaltyWallet.query.one().available_points == 400
        assert 'Chờ nhận quà' in text() and 'Vui lòng đưa mã này cho nhân viên Bin Spa' in text()

        # T09/T10: status groups, expired derived from time, details and copy.
        click('[data-group="closed"]'); b.wait('!document.querySelector("[data-list]").hasAttribute("aria-busy") && document.querySelectorAll(".loyalty-offer").length===1')
        closed = text('#customerLoyaltyContent [data-list]')
        assert 'Đã hết hạn' in closed and 'Sao chép' not in closed, closed
        click('[data-group="all"]'); b.wait('!document.querySelector("[data-list]").hasAttribute("aria-busy") && document.querySelectorAll(".loyalty-offer").length===3')
        click('[data-group="usable"]'); b.wait('!document.querySelector("[data-list]").hasAttribute("aria-busy") && document.querySelectorAll(".loyalty-offer").length===1')
        click('[data-detail]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        detail = text('#loyaltyRewardDialog')
        assert 'BIN-' in detail and '200 điểm' in detail and 'Ưu đãi của khách' in detail, detail
        click('#loyaltyRewardDialog [data-copy]'); b.wait('/sao chép/i.test(document.getElementById("customerLoyaltyMessage").textContent)')
        screenshot('detail.png'); click('#loyaltyRewardDialog [data-close]')

        # T12-style reload keeps tab and filter.
        assert b.evaluate('location.search') == '?loyalty_view=mine&loyalty_status=usable'
        reload()
        b.wait('document.querySelector("[data-loyalty-view=mine]").getAttribute("aria-selected")==="true" && document.querySelectorAll(".loyalty-offer").length===1')
        assert b.evaluate('document.querySelector("[data-group=usable]").getAttribute("aria-pressed")') == 'true'

        # T13/T14: customer invoice payment hides reserved points; voucher applies and shows "Đang áp dụng".
        b.evaluate(f'LoyaltyPayment.openCustomerInvoice({iid})'); b.wait('!!document.querySelector("#customerLoyaltyPayment [data-apply-voucher]")')
        assert 'Khả dụng: 400 điểm' in text('#customerLoyaltyPayment'); no_reserved('#customerLoyaltyPayment')
        b.evaluate('document.querySelector("#customerLoyaltyPayment [data-voucher]").selectedIndex=1'); click('#customerLoyaltyPayment [data-apply-voucher]')
        b.wait('!!document.querySelector("#customerLoyaltyPayment [data-remove-voucher]")'); no_reserved('#customerLoyaltyPayment')
        screenshot('customer-payment.png'); click('#customerLoyaltyPayment [data-close]')
        b.wait('!document.getElementById("customerLoyaltyPayment")')
        click('[data-group="applied"]'); b.wait('!document.querySelector("[data-list]").hasAttribute("aria-busy") && document.querySelectorAll(".loyalty-offer").length===1')
        assert 'Đang áp dụng' in text() and f'HD{iid:06d}' in text() and 'Tiếp tục thanh toán' in text()
        errors()

        # T17: tablet and mobile have no horizontal overflow, dialogs fit.
        b.call('Emulation.setDeviceMetricsOverride', dict(width=768, height=1024, deviceScaleFactor=1, mobile=True))
        navigate('/profile?loyalty_view=rewards#loyalty'); b.wait('document.querySelectorAll("[data-redeem]").length===3')
        assert b.evaluate('document.documentElement.scrollWidth') <= 768, b.evaluate('document.documentElement.scrollWidth')
        click(f'[data-redeem="{gift_id}"]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        assert b.evaluate('document.getElementById("loyaltyRewardDialog").getBoundingClientRect().right') <= 768
        screenshot('tablet-confirm.png'); click('#loyaltyRewardDialog [data-cancel]')
        b.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
        reload(); b.wait('document.querySelectorAll("[data-redeem]").length===3')
        assert b.evaluate('document.documentElement.scrollWidth') <= 390, b.evaluate('document.documentElement.scrollWidth')
        screenshot('mobile-catalog.png')
        click(f'[data-redeem="{gift_id}"]'); b.wait('document.getElementById("loyaltyRewardDialog").open')
        assert b.evaluate('document.getElementById("loyaltyRewardDialog").getBoundingClientRect().right') <= 390
        screenshot('mobile-confirm.png'); click('#loyaltyRewardDialog [data-cancel]')
        # The only voucher is now applied to the invoice, so "Có thể sử dụng" shows its empty state.
        click('[data-loyalty-view="mine"]'); b.wait('!!document.querySelector("[data-list] [data-goto=rewards]")')
        assert 'Bạn chưa có voucher nào có thể sử dụng' in text()
        assert b.evaluate('document.documentElement.scrollWidth') <= 390
        b.evaluate('document.querySelector("[data-loyalty-view=mine]").focus()')
        b.call('Input.dispatchKeyEvent', dict(type='keyDown', key='ArrowLeft', code='ArrowLeft', windowsVirtualKeyCode=37))
        b.wait('document.activeElement.dataset.loyaltyView==="rewards" && location.search.includes("loyalty_view=rewards")')
        screenshot('mobile-mine.png'); errors()

        # T03: staff still see the reserved balance.
        b.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        navigate('/admin/invoices'); b.wait('!!window.openInvoicePayment')
        b.evaluate(f'openInvoicePayment({iid})'); b.wait('!!document.querySelector("#sharedInvoicePayment .loyalty-payment h4")')
        assert 'Đang giữ: 100 điểm' in text('#sharedInvoicePayment'), text('#sharedInvoicePayment')
        errors()
        print('PASS: 3-metric wallet without reserved points; catalog filters; confirm/cancel; double-click; lost-response retry after reload; offer groups/detail/copy; URL tab restore; customer payment hides reserved; admin keeps it; mobile 390px + keyboard tabs.')
        print('Artifacts:', artifacts)
    except Exception:
        if ws:
            try:
                screenshot('failure.png'); (artifacts / 'failure.json').write_text(json.dumps(b.evaluate('({url:location.href,errors:window.__errors,text:document.body.innerText})'), ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception: pass
        raise
    finally:
        if ws: ws.close()
        process.terminate()
        try: process.wait(timeout=8)
        except subprocess.TimeoutExpired: process.kill()
        server.shutdown()
        try: next(fixture)
        except StopIteration: pass


if __name__ == '__main__': main()

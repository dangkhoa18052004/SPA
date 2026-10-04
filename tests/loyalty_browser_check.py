"""Real Edge DOM checks, isolated SQLite, no actual money or email."""
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

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import conftest
from billing_browser_check import Browser,free_port
from app.extensions import db
from app.models import HoaDon,DichVu,ThanhToan,LoyaltyPointTransaction,GoiDichVuPurchase
from app.services import loyalty_service as loyalty,package_service


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture=conftest.app.__wrapped__();app=next(fixture)
    app.config.update(VIETQR_BANK_ID='970407',VIETQR_ACCOUNT_NO='1234',VIETQR_ACCOUNT_NAME='BIN SPA TEST')
    with app.app_context():
        customer=app.config['TEST_CUSTOMER_ID'];staff=app.config['TEST_ADMIN_ID']
        loyalty.admin_adjust_points(customer,1000,'Initial',staff,'initial')
        reward=loyalty.save_reward(dict(name='Voucher 50.000',reward_type='voucher_amount',points_cost=200,reward_value=50000,stock=3))
        voucher=loyalty.redeem_reward(customer,reward.id,'voucher')
        loyalty.save_reward(dict(name='Quà Bin Spa',reward_type='physical_gift',points_cost=100,reward_value=0,stock=2))
        service=DichVu(tendv='Massage loyalty',gia=500000,active=True);db.session.add(service);db.session.flush()
        package=package_service.save_package(dict(tengoi='Gói Loyalty',giagoi=1200000,validity_months=6,items=[dict(madv=service.madv,total_sessions=10)]))
        invoice=HoaDon(makh=customer,manv=staff,tongtien=500000)
        db.session.add(invoice);db.session.commit()
        iid,pid=invoice.mahd,package.magoi
        admin_token=create_access_token(identity=f'staff:{staff}')
        customer_token=create_access_token(identity=f'customer:{customer}')
    server=make_server('127.0.0.1',0,app,threaded=False)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}';port=free_port()
    artifacts=Path('tests')/('loyalty-browser-'+str(port)+'.tmp');artifacts.mkdir()
    process=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-allow-origins=*',f'--remote-debugging-port={port}',f'--user-data-dir={artifacts.resolve()/"profile"}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    ws=None
    try:
        deadline=time.monotonic()+20
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1) as r:tabs=json.load(r)
                tab=next(t for t in tabs if t['type']=='page');break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(.2)
        ws=websocket.create_connection(tab['webSocketDebuggerUrl'],timeout=20,suppress_origin=True)
        b=Browser(ws);b.call('Page.enable')
        b.call('Emulation.setTimezoneOverride',dict(timezoneId='Asia/Ho_Chi_Minh'))
        b.call('Emulation.setDeviceMetricsOverride',dict(width=1280,height=900,deviceScaleFactor=1,mobile=False))
        b.call('Page.addScriptToEvaluateOnNewDocument',dict(source=
            'window.__doc=Math.random();window.__errors=[];window.addEventListener("error",e=>{if(e.message)__errors.push(e.message)});window.addEventListener("unhandledrejection",e=>__errors.push(String(e.reason)));'+
            'localStorage.setItem("admin_token",'+json.dumps(admin_token)+');localStorage.setItem("admin_role","admin");localStorage.setItem("admin_user",JSON.stringify({hoten:"Admin",role:"admin"}));'+
            'localStorage.setItem("access_token",'+json.dumps(customer_token)+');'))
        def navigate(path):
            old=b.evaluate('window.__doc');b.call('Page.navigate',dict(url=base+path))
            b.wait('window.__doc && window.__doc!=='+json.dumps(old)+' && document.readyState==="complete"')
        def click(selector):b.evaluate('document.querySelector('+json.dumps(selector)+').click()')
        def screenshot(name):
            b.wait('!document.getElementById("sharedInvoicePayment") || getComputedStyle(document.getElementById("sharedInvoicePayment")).opacity==="1" && getComputedStyle(document.querySelector("#sharedInvoicePayment .modal-content")).opacity==="1"')
            (artifacts/name).write_bytes(base64.b64decode(b.call('Page.captureScreenshot',dict(format='png'))['data']))
        def errors():assert b.evaluate('window.__errors')==[],b.evaluate('window.__errors')
        navigate('/admin/loyalty');b.wait('[...document.querySelectorAll(".loyalty-cards strong")].some(e=>e.textContent==="1")')
        click('[data-tab="config"]');b.wait('!!document.getElementById("loyaltyRules")')
        b.evaluate('document.getElementById("loyaltyRules").elements.maximum_redeem_percent.value="100";document.getElementById("loyaltyRules").requestSubmit()')
        b.wait('document.getElementById("loyaltyMessage").textContent.includes("Đã lưu")')
        click('[data-tab="customers"]');b.wait('!!document.querySelector("[data-adjust]")');click('[data-adjust]')
        b.evaluate('document.getElementById("adjustForm").elements.points.value="50";document.getElementById("adjustForm").elements.reason.value="Chăm sóc khách hàng";document.getElementById("adjustForm").requestSubmit()')
        b.wait('!document.getElementById("loyaltyAdjust").open');screenshot('admin-loyalty.png');errors()
        navigate('/admin/invoices');b.wait('!!window.openInvoicePayment')
        b.evaluate(f'openInvoicePayment({iid})');b.wait('!!document.querySelector("[data-apply-voucher]")')
        b.evaluate('document.querySelector("[data-voucher]").selectedIndex=1');click('[data-apply-voucher]')
        b.wait('!!document.querySelector("[data-remove-voucher]")')
        click('[data-enable]');b.evaluate('document.querySelector("[data-points]").value="100"');click('[data-preview]')
        b.wait('document.querySelector("[data-result]").textContent.includes("350.000")');click('[data-apply]')
        b.wait('!!document.querySelector("[data-remove]")');click('#sharedInvoicePayment [data-close]')
        navigate('/admin/invoices');b.evaluate(f'openInvoicePayment({iid})')
        b.wait('document.querySelector("[data-points]")?.value==="100"')
        screenshot('invoice-resumed.png');click('[data-qr]')
        b.wait('!!document.querySelector("#sharedInvoicePayment img")')
        assert 'amount=350000' in b.evaluate('document.querySelector("#sharedInvoicePayment img").src')
        click('#sharedInvoicePayment [data-close]');b.evaluate(f'openInvoicePayment({iid})')
        b.wait('!!document.querySelector("[data-cash]")');click('[data-cash]')
        b.evaluate('document.querySelector("#sharedInvoicePayment form input").value="400000";document.querySelector("#sharedInvoicePayment form").requestSubmit()')
        b.wait('!document.getElementById("sharedInvoicePayment")')
        b.evaluate(f'viewInvoiceDetail({iid},"service")');b.wait('!document.getElementById("receiptPrint").disabled')
        assert b.evaluate('document.getElementById("invoice-detail-content").textContent.includes("Giảm bằng điểm")')
        screenshot('loyalty-receipt.png');errors()
        navigate('/profile#loyalty');b.wait('!!document.querySelector("#loyaltyBalance strong")');click('[data-loyalty-view="rewards"]')
        b.wait('!!document.querySelector("[data-redeem]")');click('#customerLoyaltyContent [data-redeem]:not([disabled])')
        b.wait('document.getElementById("loyaltyRewardDialog").open');click('#loyaltyRewardDialog [data-confirm]')
        b.wait('document.getElementById("customerLoyaltyMessage").textContent.includes("thành công")')
        screenshot('customer-rewards.png');errors()
        navigate(f'/packages/{pid}');b.wait('!!document.querySelector("[data-buy]")')
        b.evaluate(f'document.getElementById("packageMethod-{pid}").value="cash"');click('[data-buy]')
        b.wait('!!document.querySelector("[data-enable]")');click('[data-enable]')
        b.evaluate('document.querySelector("[data-points]").value="200"');click('[data-apply]')
        b.wait('document.querySelector("[data-points]")?.value==="200" && !!document.querySelector("[data-remove]")')
        screenshot('customer-package.png');errors()
        with app.app_context():
            purchase=GoiDichVuPurchase.query.one();purchase_id=purchase.id
            assert purchase.status=='pending' and purchase.payable_amount==1000000
            assert ThanhToan.query.one().sotien==350000
            assert LoyaltyPointTransaction.query.filter_by(type='earn').one().points_delta==30
        click('#closePackagePayment');navigate(f'/packages?purchase={purchase_id}')
        b.wait('document.querySelector("[data-points]")?.value==="200"')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
        screenshot('package-mobile.png')
        assert b.evaluate('document.getElementById("packagePaymentDialog").getBoundingClientRect().width')<=390
        navigate('/admin/invoices');b.wait('!!window.payBillingTransaction');b.evaluate(f'payBillingTransaction("package",{purchase_id})')
        b.wait('document.getElementById("billingCashDialog").open && !!document.querySelector("[data-points]")')
        b.evaluate('document.getElementById("billingCashReceived").value="1100000";document.getElementById("billingCashForm").requestSubmit()')
        b.wait('document.getElementById("invoiceDetailModal").open && !document.getElementById("receiptPrint").disabled')
        assert b.evaluate('document.getElementById("invoice-detail-content").textContent.includes("100 điểm")')
        errors()
        print('PASS: admin rules/adjustments; voucher + points preview/apply; invoice resume; payable QR/cash; receipt; customer wallet/reward redemption; package reserve/resume/cash; mobile layout.')
        print('Artifacts:',artifacts)
    except Exception:
        if ws:
            try:
                screenshot('failure.png');(artifacts/'failure.json').write_text(json.dumps(b.evaluate('({url:location.href,errors:window.__errors,text:document.body.innerText})'),ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception:pass
        raise
    finally:
        if ws:ws.close()
        process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill()
        server.shutdown()
        try:next(fixture)
        except StopIteration:pass


if __name__=='__main__':main()

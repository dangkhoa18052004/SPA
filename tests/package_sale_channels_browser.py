"""Opt-in Chromium check of sale flags and counter sales with an isolated test DB.

Run: python tests/package_sale_channels_browser.py
"""
import base64
import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

import pytest
import websocket
from flask import session
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from billing_browser_check import Browser, free_port
from test_package_completion import catalog
from app.extensions import db
from app.models import GoiDichVuPurchase, TheLieuTrinh


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    patch = pytest.MonkeyPatch()
    data = catalog.__wrapped__(app, patch)
    with app.app_context():
        admin_token = create_access_token(identity=f"staff:{app.config['TEST_ADMIN_ID']}")
        customer_token = create_access_token(identity=f"customer:{data['customer']}")

    @app.before_request
    def customer_session():
        session.update(user_id=data['customer'], user_type='customer', hoten='Khách kiểm thử')

    server = make_server('127.0.0.1', 0, app, threaded=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    artifacts = Path('tests/runtime_phase4_sale_channels').resolve()
    artifacts.mkdir(exist_ok=True)
    port = free_port()
    browser_path = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    if not browser_path.exists():
        browser_path = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    process = subprocess.Popen([str(browser_path),
        '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--remote-allow-origins=*', f'--remote-debugging-port={port}',
        f'--user-data-dir={artifacts / ("profile-" + str(port))}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1) as response:
                    tabs = json.load(response)
                tab = next(t for t in tabs if t['type'] == 'page')
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(.2)
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=15, suppress_origin=True)
        browser = Browser(ws)
        browser.call('Page.enable')
        browser.call('Page.addScriptToEvaluateOnNewDocument', dict(source=
            'window.__uiErrors=[];window.addEventListener("error",e=>__uiErrors.push(e.message));'
            'window.addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
            'localStorage.setItem("admin_token",' + json.dumps(admin_token) + ');'
            'localStorage.setItem("access_token",' + json.dumps(customer_token) + ');'
            'localStorage.setItem("admin_role","admin");'
            'localStorage.setItem("admin_user",JSON.stringify({hoten:"Admin",role:"admin"}));'))
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        base = f'http://127.0.0.1:{server.server_port}'

        def navigate(path, condition):
            browser.call('Page.navigate', dict(url=base + path))
            browser.wait('document.readyState === "complete" && (' + condition + ')')
            assert browser.evaluate('window.__uiErrors') == []

        def screenshot(name):
            shot = browser.call('Page.captureScreenshot', dict(format='png', captureBeyondViewport=True))
            (artifacts / name).write_bytes(base64.b64decode(shot['data']))

        navigate('/admin/packages/new', 'document.querySelector(".package-item") !== null')
        assert browser.evaluate('packageForm.elements.customer_sale_enabled.checked && packageForm.elements.staff_sale_enabled.checked')
        edit = f"/admin/packages/{data['package']}/edit"
        navigate(edit, 'packageForm.elements.tengoi.value === "Test package"')
        browser.evaluate('packageForm.elements.customer_sale_enabled.checked=false;packageForm.elements.staff_sale_enabled.checked=true;packageForm.requestSubmit()')
        browser.wait('location.pathname === "/admin/packages" && document.getElementById("adminPackageRows")?.textContent.includes("Chỉ bán tại quầy")')
        screenshot('management-staff-only.png')
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=900, deviceScaleFactor=1, mobile=True))
        navigate('/admin/packages', 'document.getElementById("adminPackageCards").textContent.includes("Chỉ bán tại quầy")')
        screenshot('management-staff-only-mobile.png')
        badge_bounds = browser.evaluate('(()=>{const r=document.querySelector("#adminPackageCards .package-status").getBoundingClientRect();return {left:r.left,right:r.right}})()')
        assert badge_bounds['left'] >= 0 and badge_bounds['right'] <= 390, badge_bounds
        screenshot('management-staff-only-mobile.png')
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        navigate(edit, 'packageForm.elements.tengoi.value === "Test package"')
        assert browser.evaluate('!packageForm.elements.customer_sale_enabled.checked && packageForm.elements.staff_sale_enabled.checked && packageForm.elements.active.checked')
        screenshot('edit-sale-flags.png')
        navigate(f"/admin/packages/{data['package']}", 'document.getElementById("packageDetail").textContent.includes("Chỉ bán tại quầy")')
        navigate('/packages', '!document.getElementById("packageList").textContent.includes("Đang tải")')
        assert browser.evaluate('document.querySelectorAll("[data-buy]").length') == 0
        assert 'Test package' not in browser.evaluate('document.getElementById("packageList").textContent')
        navigate('/admin/package-sales', '!document.getElementById("createPackageSale").disabled')
        assert browser.evaluate('Array.from(salePackage.options).some(o=>o.textContent.includes("Chỉ bán tại quầy"))')
        browser.evaluate('salePackageSearch.value=' + json.dumps(str(data['package'])) + ';salePackageSearch.dispatchEvent(new Event("input"));')
        assert browser.evaluate('salePackage.options.length') == 2
        browser.evaluate(f'salePackage.value="{data["package"]}";salePackage.dispatchEvent(new Event("change"));saleCustomer.value="{data["customer"]}";')
        assert browser.evaluate('salePackagePreview.textContent.includes("Chỉ bán tại quầy")')
        screenshot('counter-staff-only.png')
        browser.evaluate('saleForm.requestSubmit()')
        browser.wait('!cashSalePanel.classList.contains("package-hidden") && cashSaleSummary.textContent.includes("PG")')
        browser.evaluate('cashReceived.value="1500000";cashReceived.dispatchEvent(new Event("input"));confirmPackageCash.click()')
        browser.wait('saleReceiptDialog.open && packageMessage.textContent.includes("Thanh toán thành công")')
        browser.evaluate('closeSaleReceipt.click()')
        with app.app_context():
            cash = GoiDichVuPurchase.query.one()
            assert cash.status == 'paid'
            assert TheLieuTrinh.query.filter_by(purchase_id=cash.id).count() == 1
        browser.evaluate('saleMethod.value="vietqr";saleForm.requestSubmit()')
        browser.wait('packagePaymentDialog.open && document.querySelector("[data-reveal-qr]") !== null')
        # Use the single server thread for the webhook too: the in-memory fixture
        # shares one SQLite connection and must not run concurrent transactions.
        with urlopen(Request(base + '/api/admin/package-sales', headers={'Authorization': 'Bearer ' + admin_token})) as response:
            qr_id = next(p['id'] for p in json.load(response)['purchases'] if p['payment_method'] == 'vietqr')
        event = dict(id='browser-staff-only', content=f'PKG{qr_id}', transferAmount=1200000, transferType='in')
        with urlopen(Request(base + '/api/payment/webhook/sepay', data=json.dumps(event).encode(),
                headers={'Authorization': 'Apikey test-sepay-key', 'Content-Type': 'application/json'})) as response:
            assert response.status == 200
        browser.evaluate('document.getElementById("checkPackagePayment").click()')
        browser.wait('packagePayment.textContent.includes("Thanh toán thành công")')
        assert browser.evaluate('window.__uiErrors') == []
        browser.call('Page.navigate', dict(url='about:blank'))
        with app.app_context():
            assert TheLieuTrinh.query.count() == 2
        print('PASS: create defaults, edit/save/reload, management/detail badges, hidden customer listing, counter search/preview, cash/VietQR activation, no JavaScript errors')
        print('Screenshots: ' + str(artifacts))
    finally:
        if ws:
            ws.close()
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()
        patch.undo()
        try:
            next(fixture)
        except StopIteration:
            pass


if __name__ == '__main__':
    main()

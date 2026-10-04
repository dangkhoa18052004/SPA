"""Edge DOM smoke test of staff package booking against an isolated test database."""
import base64
import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import pytest
import websocket
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from billing_browser_check import Browser, free_port
from test_phase4_packages_care import package_data
from test_admin_package_booking import entitlements
from app.extensions import db
from app.models import LieuTrinhUsage, LichHen


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    patch = pytest.MonkeyPatch()
    data = package_data.__wrapped__(app, patch)
    records = entitlements.__wrapped__(app, data)
    with app.app_context():
        # Exercise the least-privileged booking role in the real UI.
        token = create_access_token(identity=f"staff:{records['actors']['letan']['id']}")
    server = make_server('127.0.0.1', 0, app, threaded=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    artifacts = Path('tests/admin-package-booking-preview.tmp').resolve()
    artifacts.mkdir(exist_ok=True)
    port = free_port()
    process = subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
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
                if time.monotonic() > deadline: raise
                time.sleep(.2)
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=15, suppress_origin=True)
        browser = Browser(ws)
        browser.call('Page.enable')
        browser.call('Emulation.setTimezoneOverride', dict(timezoneId='Asia/Ho_Chi_Minh'))
        browser.call('Page.addScriptToEvaluateOnNewDocument', dict(source=
            'window.__uiErrors=[];window.addEventListener("error",e=>__uiErrors.push(e.message));'
            'window.addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));'
            'localStorage.setItem("admin_token",' + json.dumps(token) + ');'
            'localStorage.setItem("admin_role","letan");'
            'localStorage.setItem("admin_user",JSON.stringify({hoten:"Lễ tân",role:"letan"}));'))
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        base = f'http://127.0.0.1:{server.server_port}'
        browser.call('Page.navigate', dict(url=base + '/admin/appointments'))
        browser.wait('document.readyState === "complete" && allCustomers.length >= 2 && allServices.length === 2')
        browser.evaluate('openAddAppointmentModal()')
        assert browser.evaluate('document.getElementById("booking-service-method").hidden') is True
        def choose_customer(customer):
            browser.evaluate('document.querySelector(' + json.dumps(f'.customer-item[data-makh="{customer}"]') + ').click()')
            browser.wait('treatmentLoadState === "ready"')
        choose_customer(data['customer'])
        assert browser.evaluate('bookingServiceMethod') == 'regular'
        browser.evaluate('document.querySelector("input[name=service-method][value=treatment]").click()')
        assert browser.evaluate('document.getElementById("booking-treatment-panel").hidden') is False
        assert set(browser.evaluate('customerTreatments.map(t=>t.mathe)')) == {records['record'], records['second']}
        browser.evaluate(f'togglePackageItem({records["record"]},{records["original"]})')
        assert browser.evaluate('selectedPackageItems.size') == 1
        choose_customer(records['other_customer'])
        assert browser.evaluate('selectedPackageItems.size') == 0
        assert browser.evaluate('selectedServiceIds.length') == 0
        assert browser.evaluate('customerTreatments.map(t=>t.mathe)') == [records['other_record']]
        choose_customer(data['customer'])
        # Select an exact gift and then switch to the matching original package entitlement.
        browser.evaluate(f'togglePackageItem({records["record"]},{records["gift"]})')
        assert browser.evaluate(f'selectedPackageItems.get({data["service"]}).item.id') == records['gift']
        browser.evaluate(f'togglePackageItem({records["record"]},{records["original"]})')
        assert browser.evaluate('selectedServiceIds.length') == 1
        assert browser.evaluate(f'selectedPackageItems.get({data["service"]}).item.id') == records['original']
        # Use the ordinary-service label click, exercising native checkbox behavior.
        browser.evaluate(f'document.querySelector("label[for=service-checkbox-{data["other_service"]}]").click()')
        assert set(browser.evaluate('selectedServiceIds')) == {data['service'], data['other_service']}
        browser.evaluate('document.getElementById("appointment-date").value=' + json.dumps(data['slot'].strftime('%Y-%m-%d')) + ';bookingDateChanged();'
            'document.getElementById("appointment-time").value="09:00";loadAvailableStaff()')
        browser.wait('availableStaff.length > 0')
        for width, name in ((1280, 'desktop'), (768, 'tablet'), (390, 'mobile')):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 600))
            browser.evaluate('document.getElementById("booking-service-method").scrollIntoView({block:"start"})')
            bounds = browser.evaluate('(()=>{const r=document.querySelector("#appointmentModal .modal-content").getBoundingClientRect();return {x:r.x,right:r.right,width:r.width}})()')
            assert bounds['x'] >= 0 and bounds['right'] <= width + 1, bounds
            assert browser.evaluate('document.getElementById("booking-treatment-list").scrollWidth <= document.getElementById("booking-treatment-list").clientWidth + 1')
            (artifacts / f'{name}.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot', dict(format='png'))['data']))
        browser.evaluate('document.getElementById("appointment-save").click()')
        browser.wait('!appointmentSubmitting && document.getElementById("appointmentModal").style.display === "none"')
        browser.wait('allAppointments.length === 1')
        with app.app_context():
            appointment = LichHen.query.one()
            apt_id = appointment.malh
            usage = LieuTrinhUsage.query.one()
            assert usage.the_item_id == records['original'] and usage.state == 'reserved'
            assert appointment.created_by_staff == records['actors']['letan']['id']
        browser.call('Page.reload')
        browser.wait('document.readyState === "complete" && allAppointments.length === 1')
        browser.evaluate(f'viewAppointmentDetail({apt_id})')
        browser.wait('document.getElementById("appointmentDetailModal").style.display === "flex"')
        services_text = browser.evaluate('document.getElementById("detail-services-list").textContent')
        assert 'Đã giữ buổi' in services_text and 'Thanh toán riêng' in services_text
        assert 'Bin Spa hỗ trợ đặt lịch' in browser.evaluate('document.getElementById("detail-booking-source").textContent')
        assert browser.evaluate('window.__uiErrors') == [], browser.evaluate('window.__uiErrors')
        print(json.dumps(dict(result='passed', role='letan', appointment=apt_id,
            checks=['exact customer load', 'customer reset', 'package/gift source selection',
                    'mixed booking', 'reservation', 'reload', 'detail coverage', 'desktop/tablet/mobile', 'no JS errors']), ensure_ascii=True))
    finally:
        if ws: ws.close()
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()
        patch.undo()
        try: next(fixture)
        except StopIteration: pass


if __name__ == '__main__': main()

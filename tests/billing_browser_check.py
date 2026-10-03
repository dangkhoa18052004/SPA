"""Manual Edge smoke check with an isolated in-memory test DB; no live data."""
import base64
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

import fitz
import websocket
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from test_billing_transactions import billing_records
from app.extensions import db
from app.models import GoiDichVuPurchase, ThanhToan
from app.services import package_service
from app.services import notification_service, email_service
from app.models import NotificationJob
from app.models import LichHen
from test_appointment_completion_flow import appointment


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Browser:
    def __init__(self, ws):
        self.ws = ws
        self.sequence = 0

    def call(self, method, params=None):
        self.sequence += 1
        sequence = self.sequence
        self.ws.send(json.dumps(dict(id=sequence, method=method, params=params or {})))
        while True:
            result = json.loads(self.ws.recv())
            if result.get('id') == sequence:
                if 'error' in result:
                    raise RuntimeError(result['error'])
                return result.get('result', {})

    def evaluate(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
        if 'exceptionDetails' in result:
            raise AssertionError(result['exceptionDetails'])
        return result['result'].get('value')

    def wait(self, expression):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.evaluate(expression):
                return
            time.sleep(.1)
        raise AssertionError('Browser condition timed out: ' + expression)


def main():
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    records = billing_records.__wrapped__(app)
    with app.app_context():
        token = create_access_token(identity=f"staff:{app.config['TEST_ADMIN_ID']}")
    # The fixture uses one shared SQLite in-memory connection.
    server = make_server('127.0.0.1', 0, app, threaded=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = free_port()
    artifacts = Path('tests/billing-preview.tmp').resolve()
    artifacts.mkdir(exist_ok=True)
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    process = subprocess.Popen([str(edge), '--headless=new', '--disable-gpu', '--no-first-run',
        '--no-default-browser-check', '--remote-allow-origins=*', f'--remote-debugging-port={port}',
        f'--user-data-dir={artifacts / "profile"}', 'about:blank'], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1) as response:
                    tabs = json.load(response)
                tab = next(tab for tab in tabs if tab['type'] == 'page')
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(.2)
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=15, suppress_origin=True)
        browser = Browser(ws)
        browser.call('Page.enable')
        browser.call('Emulation.setTimezoneOverride', dict(timezoneId='Asia/Ho_Chi_Minh'))
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        browser.call('Page.addScriptToEvaluateOnNewDocument', dict(source=
            'localStorage.setItem("admin_token",' + json.dumps(token) + ');'
            'localStorage.setItem("admin_role","admin");'
            'localStorage.setItem("admin_user",JSON.stringify({hoten:"Admin Test",role:"admin"}));'))
        browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/admin/invoices'))
        browser.wait('document.querySelectorAll("#invoices-table tbody tr").length === 2')
        assert browser.evaluate('document.getElementById("stat-total").textContent') == '2'
        for kind in ('service', 'package'):
            browser.evaluate(f'document.getElementById("typeFilter").value="{kind}"; applyFilters()')
            browser.wait('document.querySelectorAll("#invoices-table tbody tr").length === 1')
            assert browser.evaluate('document.getElementById("stat-total").textContent') == '1'
            browser.evaluate(f'viewInvoiceDetail({records[kind]}, "{kind}")')
            browser.wait('!document.getElementById("receiptPrint").disabled')
            assert browser.evaluate('document.querySelector(".billing-receipt h2").textContent') == 'BIN SPA'
            assert browser.evaluate('document.querySelectorAll("#invoice-detail-content .info-card").length') == 0
            screenshot = browser.call('Page.captureScreenshot', dict(format='png'))
            (artifacts / f'{kind}-receipt.png').write_bytes(base64.b64decode(screenshot['data']))
            browser.evaluate('window.print=()=>{}; document.getElementById("receiptPrint").click()')
            pdf = browser.call('Page.printToPDF', dict(preferCSSPageSize=True, printBackground=True))
            pdf_path = artifacts / f'{kind}-receipt.pdf'
            pdf_path.write_bytes(base64.b64decode(pdf['data']))
            with fitz.open(pdf_path) as document:
                text = ''.join(page.get_text() for page in document)
                assert len(document) == 1, 'Receipt should fit on one A5 page'
                assert 'BIN SPA' in text and ('HD000001' if kind == 'service' else 'PG000001') in text
                assert 'Dashboard' not in text and 'In phiếu' not in text
            browser.evaluate('document.getElementById("invoiceDetailModal").close()')
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
        browser.call('Page.reload')
        browser.wait('document.querySelectorAll("#invoices-table tbody tr").length === 2')
        browser.evaluate(f'viewInvoiceDetail({records["package"]}, "package")')
        browser.wait('!document.getElementById("receiptPrint").disabled')
        assert browser.evaluate('document.getElementById("invoiceDetailModal").getBoundingClientRect().width') <= 390
        screenshot = browser.call('Page.captureScreenshot', dict(format='png'))
        (artifacts / 'package-receipt-mobile.png').write_bytes(base64.b64decode(screenshot['data']))
        browser.evaluate('document.getElementById("invoiceDetailModal").close()')
        browser.call('Emulation.setDeviceMetricsOverride', dict(width=1280, height=900, deviceScaleFactor=1, mobile=False))
        browser.evaluate(f'viewInvoiceDetail({records["service"]}, "service")')
        browser.wait('!document.getElementById("receiptPrint").disabled')
        browser.evaluate('document.getElementById("receiptPay").click()')
        browser.wait('!!document.querySelector("#sharedInvoicePayment [data-cash]")')
        browser.evaluate('document.querySelector("#sharedInvoicePayment [data-cash]").click(); document.querySelector("#sharedInvoicePayment input").value="350000"; document.querySelector("#sharedInvoicePayment form").requestSubmit()')
        browser.wait('!document.getElementById("sharedInvoicePayment")')
        with app.app_context():
            assert ThanhToan.query.filter_by(mahd=records['service']).count() == 1
            pending_cash = package_service.create_purchase(records['catalog'], app.config['TEST_CUSTOMER_ID'], 'cash')
            pending_qr = package_service.create_purchase(records['catalog'], app.config['TEST_CUSTOMER_ID'], 'vietqr')
            db.session.commit()
            cash_id, qr_id = pending_cash.id, pending_qr.id
            app.config.update(VIETQR_BANK_ID='970407', VIETQR_ACCOUNT_NO='123456', VIETQR_ACCOUNT_NAME='TEST')
        browser.evaluate(f'payBillingTransaction("package", {cash_id})')
        browser.wait('document.getElementById("billingCashDialog").open')
        browser.evaluate('document.getElementById("billingCashReceived").value="240000"; document.getElementById("billingCashForm").requestSubmit()')
        browser.wait('document.getElementById("invoiceDetailModal").open && !document.getElementById("receiptPrint").disabled')
        assert browser.evaluate('document.getElementById("invoice-detail-content").textContent.includes("Đã thanh toán")')
        browser.evaluate('document.getElementById("invoiceDetailModal").close()')
        for _ in range(2):
            browser.evaluate(f'payBillingTransaction("package", {qr_id})')
            browser.wait('document.getElementById("packagePaymentDialog").open')
            assert browser.evaluate(f'document.getElementById("packagePayment").textContent.includes("PKG{qr_id}")')
            browser.evaluate('document.getElementById("closePackagePayment").click()')
        with app.app_context():
            assert db.session.get(GoiDichVuPurchase, qr_id).status == 'pending'
            assert GoiDichVuPurchase.query.count() == 3
        service_appointment = appointment(app)
        full_package_appointment = appointment(app, package=True)
        mixed_appointment = appointment(app, package=True, mixed=True)
        browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/admin/appointments'))
        selector = lambda apt_id: f"document.querySelector('[data-appointment-id=\"{apt_id}\"]')"
        browser.wait(f'{selector(service_appointment)}?.textContent.includes("Hoàn thành")')
        browser.evaluate(f'{selector(service_appointment)}.querySelector("[onclick^=completeAppointment]").click(); document.getElementById("confirm-btn-ok").click()')
        browser.wait(f'{selector(service_appointment)}?.textContent.includes("Tạo hóa đơn")')
        assert not browser.evaluate(f'{selector(service_appointment)}.textContent.includes("Hoàn thành")')
        with app.app_context():
            assert NotificationJob.query.filter_by(malh=service_appointment, type='post_care').count() == 1
        browser.evaluate(f'{selector(service_appointment)}.querySelector("[onclick^=createInvoiceForAppointment]").click()')
        browser.wait('!!document.getElementById("sharedInvoicePayment")')
        browser.evaluate('document.querySelector("#sharedInvoicePayment [data-close]").click()')
        browser.wait(f'{selector(service_appointment)}?.textContent.includes("Thanh toán hóa đơn")')
        browser.call('Page.reload')
        browser.wait(f'{selector(service_appointment)}?.textContent.includes("Thanh toán hóa đơn")')
        browser.evaluate(f'{selector(service_appointment)}.querySelector("[onclick^=openInvoicePayment]").click()')
        browser.wait('!!document.querySelector("#sharedInvoicePayment [data-cash]")')
        browser.evaluate('document.querySelector("#sharedInvoicePayment [data-cash]").click();document.querySelector("#sharedInvoicePayment input").value="350000";document.querySelector("#sharedInvoicePayment form").requestSubmit()')
        browser.wait(f'{selector(service_appointment)}?.textContent.includes("Xem hóa đơn")')
        assert browser.evaluate(f'{selector(service_appointment)}.textContent.includes("Đã hoàn thành")')
        browser.evaluate(f'{selector(service_appointment)}.querySelector("[onclick^=viewAppointmentInvoice]").click()')
        browser.wait('document.getElementById("sharedBillingReceipt")?.open')
        browser.evaluate('document.querySelector("#sharedBillingReceipt [data-close]").click()')
        for apt_id in (full_package_appointment, mixed_appointment):
            browser.evaluate(f'{selector(apt_id)}.querySelector("[onclick^=completeAppointment]").click();document.getElementById("confirm-btn-ok").click()')
            browser.wait(f'{selector(apt_id)}?.textContent.includes("Đã hoàn thành")')
        assert browser.evaluate(f'{selector(full_package_appointment)}.textContent.includes("Đã thanh toán bằng gói")')
        assert not browser.evaluate(f'{selector(full_package_appointment)}.textContent.includes("Tạo hóa đơn")')
        assert browser.evaluate(f'{selector(mixed_appointment)}.textContent.includes("Tạo hóa đơn")')
        screenshot = browser.call('Page.captureScreenshot', dict(format='png'))
        (artifacts / 'appointment-action-flow.png').write_bytes(base64.b64decode(screenshot['data']))
        staff_appointment = appointment(app, state='in_progress')
        with app.app_context():
            staff_token = create_access_token(identity=f"staff:{app.config['TEST_STAFF_ID']}")
            staff_day = db.session.get(LichHen, staff_appointment).ngaygio.date().isoformat()
        # Replace the test-only bootstrap storage and reload as the assigned technician.
        bootstrap = browser.call('Page.addScriptToEvaluateOnNewDocument', dict(source=
            'localStorage.setItem("admin_token",' + json.dumps(staff_token) + ');localStorage.setItem("admin_role","staff");'))
        browser.call('Page.reload')
        browser.wait('typeof currentUserRole !== "undefined" && currentUserRole === "staff"')
        browser.evaluate('loadAppointments({startDate:' + json.dumps(staff_day) + ',endDate:' + json.dumps(staff_day) + '})')
        try:
            browser.wait(f'{selector(staff_appointment)}?.textContent.includes("Hoàn thành")')
        except AssertionError:
            print(browser.evaluate('JSON.stringify({path:location.pathname,role:localStorage.getItem("admin_role"),time:new Date().toString(),rows:typeof allAppointments==="undefined"?null:allAppointments})'))
            raise
        browser.evaluate(f'{selector(staff_appointment)}.querySelector("[onclick^=completeAppointment]").click();document.getElementById("confirm-btn-ok").click()')
        browser.wait(f'{selector(staff_appointment)}?.textContent.includes("Đã hoàn thành")')
        assert not browser.evaluate(f'{selector(staff_appointment)}.textContent.includes("Tạo hóa đơn")')
        browser.call('Page.removeScriptToEvaluateOnNewDocument', dict(identifier=bootstrap['identifier']))
        with app.app_context():
            captured = []
            original_send = email_service.send_email
            try:
                email_service.send_email = lambda *args, **kwargs: captured.append(kwargs['idempotency_key']) or True
                notification_service.process_jobs()
                assert len(captured) == 4 and len(set(captured)) == 4
            finally:
                email_service.send_email = original_send
        print('PASS: appointment completion/action flow, close/reload payment resume, paid receipt, package coverage, staff completion, 4 unique post-care sends via mocked provider.')
        for width, height in ((1920, 1080), (1440, 900), (1024, 768), (768, 1024), (390, 844)):
            browser.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=height, deviceScaleFactor=1, mobile=width < 600))
            browser.call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/admin/packages#treatments'))
            browser.wait('!!document.querySelector("[data-treatment-id]")')
            browser.evaluate('document.querySelector("[data-treatment-id]").click()')
            browser.wait('document.getElementById("treatmentDetailDialog").open && !!document.getElementById("treatmentDetailTitle")')
            centered = '''(() => {const d=document.getElementById('treatmentDetailDialog'),r=d.getBoundingClientRect();
                return Math.abs(r.left+r.width/2-document.documentElement.clientWidth/2)<2 && Math.abs(r.top+r.height/2-document.documentElement.clientHeight/2)<2
                    && r.left>=0 && r.right<=innerWidth && r.top>=0 && r.bottom<=innerHeight;})()'''
            assert browser.evaluate(centered), f'Treatment modal is not centered at {width}px'
            screenshot = browser.call('Page.captureScreenshot', dict(format='png'))
            (artifacts / f'treatment-{width}.png').write_bytes(base64.b64decode(screenshot['data']))
            browser.evaluate("document.getElementById('treatmentDetailContent').insertAdjacentHTML('beforeend', '<p>Scroll test</p>'.repeat(100))")
            assert browser.evaluate(centered), f'Long treatment modal is not centered at {width}px'
            assert browser.evaluate("(() => {const d=document.getElementById('treatmentDetailDialog');d.scrollTop=100;return d.scrollTop>0 && d.scrollHeight>d.clientHeight;})()")
            browser.evaluate("document.getElementById('treatmentDetailDialog').scrollTop=0;document.querySelector('[data-close-treatment]').click()")
            assert browser.evaluate("!document.getElementById('treatmentDetailDialog').open")
            browser.evaluate('document.querySelector("[data-treatment-id]").click()')
            browser.wait('document.getElementById("treatmentDetailDialog").open')
            browser.call('Input.dispatchKeyEvent', dict(type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27))
            browser.call('Input.dispatchKeyEvent', dict(type='keyUp', key='Escape', code='Escape', windowsVirtualKeyCode=27))
            browser.wait('!document.getElementById("treatmentDetailDialog").open')
        print('PASS: treatment modal centered at 1920/1440/1024/768/390px; long-content scroll, close button and Escape.')
        print('PASS: mixed list, filters, receipt details, mobile modal, cash resume for both types, QR close/reopen, service/package A5 PDFs (one page each).')
        print('Artifacts: tests/billing-preview.tmp')
    finally:
        if ws:
            try:
                ws.send(json.dumps(dict(id=99999, method='Browser.close')))
            except Exception:
                pass
            ws.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        server.shutdown()
        fixture.close()


if __name__ == '__main__':
    main()

"""Chrome: khách CHƯA đăng nhập bấm "Mua gói" → hộp "Vui lòng đăng nhập"; đăng nhập xong quay lại tự mua đúng gói.

Run: python tests/package_login_browser_check.py  (DB trong bộ nhớ, không thanh toán thật)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json, subprocess, threading, time, urllib.request, uuid
import websocket
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import KhachHang, DichVu, GoiDichVuPurchase
from app.services import package_service

root = Path(__file__).resolve().parents[1]
artifacts = root / 'tests' / 'runtime_ui_improvements'
artifacts.mkdir(exist_ok=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI='sqlite://', SECRET_KEY='ui',
                      JWT_SECRET_KEY='ui-test-secret-at-least-32-characters', VIETQR_BANK_ID='970416',
                      VIETQR_ACCOUNT_NO='27572201', VIETQR_ACCOUNT_NAME='DANG VAN KHOA', SEPAY_POLL_ENABLED=False,
                      GEMINI_API_KEY=''))
with app.app_context():
    db.create_all()
    db.session.add(KhachHang(hoten='Khách', taikhoan='khach_ui', matkhau=generate_password_hash('password'), trangthai='active'))
    service = DichVu(tendv='Massage', gia=300000, thoiluong=60, active=True)
    db.session.add(service); db.session.flush()
    package = package_service.save_package(dict(tengoi='Combo 5 buổi', giagoi=1200000, validity_months=6,
                                                items=[dict(madv=service.madv, total_sessions=5)]))
    db.session.commit()
    pid = package.magoi


class Quiet(WSGIRequestHandler):
    def log(self, *a, **k):
        pass


server = make_server('127.0.0.1', 0, app, threaded=False, request_handler=Quiet)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
profile = artifacts / ('chrome-profile-' + uuid.uuid4().hex)
proc = subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless', '--disable-gpu',
                         '--remote-allow-origins=*', '--remote-debugging-port=0', '--user-data-dir=' + str(profile), 'about:blank'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            port = int((profile / 'DevToolsActivePort').read_text().splitlines()[0]); break
        except (OSError, ValueError, IndexError):
            time.sleep(.1)
    target = next(t for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json')) if t['type'] == 'page')
    ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=20)
    n = [0]

    def call(method, params=None):
        n[0] += 1; ws.send(json.dumps(dict(id=n[0], method=method, params=params or {})))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == n[0]:
                return m.get('result', {})

    def ev(expr):
        r = call('Runtime.evaluate', dict(expression=expr, returnByValue=True, awaitPromise=True))
        if 'exceptionDetails' in r:
            raise RuntimeError(r['exceptionDetails'])
        return r.get('result', {}).get('value')

    def wait(expr, label, seconds=15):
        # Chuyển trang giữa chừng làm hủy ngữ cảnh JS (CDP trả lỗi, không có kết quả): thử lại tới khi đúng.
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                if ev("(async()=>{for(let i=0;i<20;i++){if(" + expr + ")return 1;await new Promise(r=>setTimeout(r,50));}return 0;})()") == 1:
                    return
            except RuntimeError:
                pass
            time.sleep(0.2)
        raise AssertionError('timeout: ' + label)

    call('Page.enable')
    call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
    call('Page.navigate', {'url': f'{base}/packages/{pid}'})
    wait("document.querySelector('[data-buy]')", 'buy button')
    ev("document.querySelector('[data-buy]').click()")
    wait("!document.getElementById('packageLoginModal').hidden", 'login modal')
    href = ev("document.querySelector('#packageLoginModal [data-login-link]').getAttribute('href')")
    assert f'buy%3D{pid}' in href and 'redirect=' in href, href
    shot = call('Page.captureScreenshot', {'format': 'png'})['data']
    (artifacts / '390-package-login-required.png').write_bytes(__import__('base64').b64decode(shot))
    with app.app_context():
        assert GoiDichVuPurchase.query.count() == 0
    # Đăng nhập rồi quay lại theo link trong hộp → tự mua tiếp đúng gói (hiện QR).
    call('Page.navigate', {'url': base + href})
    wait("document.readyState==='complete' && document.querySelector('[name=taikhoan]')", 'login form')
    ev("document.querySelector('[name=taikhoan]').value='khach_ui';document.querySelector('[name=matkhau]').value='password';document.getElementById('loginForm').requestSubmit()")
    wait(f"location.search==='' && location.pathname==='/packages/{pid}' && document.getElementById('packagePayment').innerText.includes('PKG') && !!document.querySelector('#packagePayment img')", 'resume purchase QR')
    with app.app_context():
        db.session.remove()
        purchase = GoiDichVuPurchase.query.one()
        assert purchase.magoi == pid and purchase.payment_method == 'vietqr' and purchase.status == 'pending'
    print('PASS: chưa đăng nhập → hộp đăng nhập; đăng nhập xong quay lại và tiếp tục mua đúng gói bằng VietQR')
finally:
    try:
        call('Browser.close')
    except Exception:
        proc.terminate()
    server.shutdown()

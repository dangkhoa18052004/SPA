"""Opt-in Chrome UI check using an isolated, seeded DB; no real payments/emails.

Run: python tests/phase4_ui_check.py
Requires local Chrome and websocket-client (verification tool, not app dependency).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import base64
import json
import subprocess
import threading
import time as clock
from datetime import datetime, timedelta, time
import urllib.request
import websocket
import uuid
import re
from flask import session
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server, WSGIRequestHandler
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, DichVu, CaLam, nhanvien_calam, LieuTrinhUsage, LichHen
from app.services import package_service, appointment_service, email_service
from PIL import Image
from io import BytesIO

root = Path(__file__).resolve().parents[1]
artifacts = root / 'tests' / 'runtime_phase4_ui'
artifacts.mkdir(exist_ok=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='ui-test-only', JWT_SECRET_KEY='ui-test-secret-at-least-32-characters',
    VIETQR_BANK_ID='TESTBANK', VIETQR_ACCOUNT_NO='123456', VIETQR_ACCOUNT_NAME='TEST SPA',
    SEPAY_API_KEY='test-sepay-key'))
appointment_service.send_appointment_confirmation_email_async = lambda *args: None
email_service.send_email = lambda *args, **kwargs: True
with app.app_context():
    db.create_all()
    role=ChucVu(tencv='Kỹ thuật viên',dongiagio=100000)
    db.session.add(role);db.session.flush()
    customer=KhachHang(hoten='Khách thử nghiệm',email='nobody@example.test',sdt='0900000000',taikhoan='ui_customer',matkhau='hash',trangthai='active')
    staff=NhanVien(hoten='Kỹ thuật viên thử nghiệm',taikhoan='ui_staff',matkhau='hash',macv=role.macv,role='staff',trangthai=True)
    admin=NhanVien(hoten='Admin thử nghiệm',taikhoan='ui_admin',matkhau='hash',macv=role.macv,role='admin',trangthai=True)
    service=DichVu(tendv='Massage thư giãn',gia=300000,thoiluong=45,active=True,mota='Dịch vụ thử nghiệm')
    db.session.add_all([customer,staff,admin,service]);db.session.flush()
    day=package_service.local_now().date()+timedelta(days=3)
    shift=CaLam(ngay=day,giobatdau=time(8),gioketthuc=time(18))
    db.session.add(shift);db.session.flush()
    db.session.execute(nhanvien_calam.insert().values(manv=staff.manv,maca=shift.maca))
    package=package_service.save_package(dict(tengoi='Combo Massage 5 buổi',mota='Massage thư giãn theo liệu trình',giagoi=1200000,validity_months=6,items=[dict(madv=service.madv,total_sessions=5)]))
    infinite=package_service.save_package(dict(tengoi='Massage vô thời hạn',mota='Chăm sóc theo nhịp sống của bạn',giagoi=1100000,validity_months=None,items=[dict(madv=service.madv,total_sessions=5)]))
    package_service.save_package(dict(tengoi='Gói chăm sóc chuyên sâu',mota='Dịch vụ bổ sung và liệu trình tại Bin Spa',giagoi=2000000,validity_months=8,items=[dict(madv=service.madv,total_sessions=5)]))
    purchase=package_service.create_purchase(package.magoi,customer.makh,'cash')
    _, record, _=package_service.confirm_purchase(purchase.id,1200000,method='cash')
    package_service.create_purchase(package.magoi,customer.makh,'cash')
    db.session.commit()
    customer_id, service_id, package_id, record_id=customer.makh,service.madv,package.magoi,record.mathe
    item_id=record.items[0].id  # option value của select liệu trình là the_item_id
    customer_token=create_access_token(identity=f'customer:{customer.makh}')
    admin_token=create_access_token(identity=f'staff:{admin.manv}')
    infinite_id=infinite.magoi
    receptionist=NhanVien(hoten='Lễ tân thử nghiệm',taikhoan='ui_reception',matkhau='hash',macv=role.macv,role='letan',trangthai=True)
    db.session.add(receptionist);db.session.commit()
    receptionist_token=create_access_token(identity=f'staff:{receptionist.manv}')


@app.before_request
def test_session():
    session.update(user_id=customer_id,user_type='customer',hoten='Khách thử nghiệm')


@app.after_request
def test_browser_tokens(response):
    if response.mimetype=='text/html':
        init="window.__uiErrors=[];window.addEventListener('error',e=>{if(e.message)__uiErrors.push(e.message)});window.addEventListener('unhandledrejection',e=>__uiErrors.push(String(e.reason)));"
        init+=f"localStorage.setItem('access_token',{json.dumps(customer_token)});localStorage.setItem('admin_token',{json.dumps(admin_token)});localStorage.setItem('admin_role','admin');localStorage.setItem('admin_user',JSON.stringify({{role:'admin',hoten:'Admin'}}));"
        response.set_data(response.get_data(as_text=True).replace('<head>','<head><script>'+init+'</script>',1))
    return response


class QuietHandler(WSGIRequestHandler):
    def log(self,*args,**kwargs):pass
server=make_server('127.0.0.1',0,app,threaded=False,request_handler=QuietHandler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base=f'http://127.0.0.1:{server.server_port}'
chrome=r'C:\Program Files\Google\Chrome\Application\chrome.exe'
profile_path=artifacts/('chrome-profile-'+uuid.uuid4().hex)
process=subprocess.Popen([chrome,'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
    '--remote-allow-origins=*','--remote-debugging-port=0','--user-data-dir='+str(profile_path), 'about:blank'],
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


class Browser:
    def __init__(self):
        portfile=profile_path/'DevToolsActivePort'
        for _ in range(100):
            if portfile.exists():break
            clock.sleep(.1)
        port=int(portfile.read_text().splitlines()[0])
        targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
        target=next(t for t in targets if t['type']=='page')
        self.ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=15)
        self.counter=0
        self.call('Page.enable')
    def call(self,method,params=None):
        self.counter+=1;identifier=self.counter
        self.ws.send(json.dumps(dict(id=identifier,method=method,params=params or {})))
        while True:
            message=json.loads(self.ws.recv())
            if message.get('id')==identifier:
                if message.get('error'):raise RuntimeError(message['error'])
                return message.get('result',{})
    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
        if 'exceptionDetails' in result:raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')
    def wait(self,expression):
        return self.evaluate("(async()=>{for(let n=0;n<100;n++){if("+expression+")return true;await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait timeout');})()")
    def navigate(self,url):
        self.call('Page.navigate',{'url':base+url})
        pathname=url.split('?')[0].split('#')[0]
        self.wait("location.pathname==="+json.dumps(pathname)+"&&document.readyState!=='loading'")
    def screenshot(self,name):
        data=self.call('Page.captureScreenshot',{'format':'png'})['data']
        (artifacts/name).write_bytes(base64.b64decode(data))


results=[]
try:
    browser=Browser()
    for width in [1920,1440,1024,768,390]:
        browser.call('Emulation.setDeviceMetricsOverride',dict(width=width,height=1000,deviceScaleFactor=1,mobile=width<768))
        for url,ready in [('/packages',"document.querySelector('[data-buy]')"),(f'/packages/{package_id}',"document.querySelector('[data-buy]')"),('/profile#treatments',"document.querySelector('#myTreatments .package-panel')"),('/admin/packages',"document.querySelector('#adminPackageRows tr')"),('/admin/packages/new',"document.querySelector('#packageItems .package-item')"),(f'/admin/packages/{package_id}',"document.querySelector('#packageDetail .package-detail-card')"),(f'/admin/packages/{package_id}/edit',"document.querySelector('#packageForm').elements.tengoi.value.length>0")]:
            browser.navigate(url);browser.wait(ready)
            layout=browser.evaluate("(()=>{const root=document.querySelector('.package-section,.admin-packages');const nodes=[...root.querySelectorAll('input,select,textarea,button,.package-panel,.package-form-card')].filter(e=>e.getClientRects().length);return {width:innerWidth,overflow:nodes.filter(e=>{const r=e.getBoundingClientRect();return r.right>innerWidth+1||r.left<0}).map(e=>e.id||e.className),errors:window.__uiErrors};})()")
            assert layout['width']==width and not layout['overflow'] and not layout['errors'],(width,url,layout)
            browser.wait("[...document.querySelectorAll('.package-cover')].every(i=>i.complete&&i.naturalWidth>0)")
            if url=='/packages':
                columns=browser.evaluate("getComputedStyle(document.querySelector('#packageList')).gridTemplateColumns.split(' ').length")
                assert columns==(3 if width>=1100 else 2 if width>=768 else 1),(width,columns)
                assert not browser.evaluate("[...document.querySelectorAll('.package-saving')].some(e=>e.textContent.includes('0 ₫')&&e.textContent.includes('Tiết kiệm: 0'))")
            if url=='/packages': name='packages-list'
            elif url.startswith('/packages/'): name='package-detail'
            elif url=='/admin/packages': name='admin-packages'
            elif url=='/admin/packages/new': name='admin-package-new'
            elif url.endswith('/edit'): name='admin-package-edit'
            elif url.startswith('/admin/packages/'): name='admin-package-detail'
            else: name=url.split('/')[1].split('#')[0]
            browser.screenshot(f'{width}-{name}.png')
            results.append(dict(page=url,**layout))
            if url=='/admin/packages':
                browser.evaluate("document.querySelector('[data-package-tab=\"treatments\"]').click()")
                browser.wait("document.querySelector('#adminTreatmentRows tr')")
                treatment_layout=browser.evaluate("({overflow:document.documentElement.scrollWidth>innerWidth+1,errors:window.__uiErrors})")
                assert not treatment_layout['overflow'] and not treatment_layout['errors'],(width,treatment_layout)
                browser.screenshot(f'{width}-admin-treatments.png')
        browser.navigate('/appointments/create')
        browser.wait("document.querySelector('[data-service-id]')")
        browser.evaluate(f"toggleServiceSelection({service_id});document.querySelector('#appointmentDate').value='{day}';loadTimeSlots();")
        browser.wait("document.querySelector('#appointmentTime option[value=\"09:00\"]:not([disabled])')")
        browser.evaluate("document.querySelector('#appointmentTime').value='09:00';refreshBookingSummary();")
        browser.wait("document.querySelector('[data-treatment-service]')")
        browser.evaluate(f"const s=document.querySelector('[data-treatment-service]');s.value='{item_id}';s.dispatchEvent(new Event('change'));")
        browser.wait("PackageCare.getUsages().length===1")
        booking=browser.evaluate("({usages:PackageCare.getUsages(),total:document.querySelector('#summaryTotal').textContent,errors:window.__uiErrors,overflow:document.querySelector('#bookingTreatments').getBoundingClientRect().right>innerWidth})")
        assert booking['usages']==[dict(mathe=record_id,the_item_id=item_id,madv=service_id,quantity=1)] and not booking['errors'] and not booking['overflow'],booking
        assert not any(c in booking['total'] for c in '123456789'),booking
        results.append(dict(width=width,page='/appointments/create',**booking))
        print(f'PASS responsive {width}px',flush=True)
    # Exercise real purchase API from customer UI (cash and VietQR), without paying.
    browser.navigate(f'/packages/{package_id}');browser.wait("document.querySelector('[data-buy]')")
    browser.evaluate(f"document.querySelector('#packageMethod-{package_id}').value='cash';document.querySelector('[data-buy]').click();")
    browser.wait("document.querySelector('#packagePayment').textContent.includes('PKG')")
    assert browser.evaluate("document.querySelector('#packagePayment').textContent.includes('Vui lòng đến quầy')")
    browser.navigate(f'/packages/{package_id}');browser.wait("document.querySelector('[data-buy]')")
    browser.evaluate("document.querySelector('[data-buy]').click();")
    browser.wait("document.querySelector('#packagePayment img')")
    assert browser.evaluate("document.querySelector('#packagePayment').textContent.includes('Chuyển đúng')")
    for action in ['cancel','complete']:
        browser.navigate('/appointments/create');browser.wait("document.querySelector('[data-service-id]')")
        browser.evaluate(f"toggleServiceSelection({service_id});document.querySelector('#appointmentDate').value='{day}';loadTimeSlots();")
        browser.wait("document.querySelector('#appointmentTime option[value=\"09:00\"]:not([disabled])')")
        browser.evaluate("document.querySelector('#appointmentTime').value='09:00';refreshBookingSummary();")
        browser.wait("document.querySelector('[data-treatment-service]')")
        browser.evaluate(f"const s=document.querySelector('[data-treatment-service]');s.value='{item_id}';s.dispatchEvent(new Event('change'));document.querySelector('#appointmentForm').dispatchEvent(new Event('submit',{{bubbles:true,cancelable:true}}));")
        clock.sleep(2.5)
        with app.app_context():
            apt=LichHen.query.order_by(LichHen.malh.desc()).first()
            assert apt and LieuTrinhUsage.query.filter_by(malh=apt.malh,state='reserved').count()==1
            appointment_id=apt.malh
        browser.navigate('/profile#treatments');browser.wait("document.querySelector('[data-history]')")
        browser.evaluate(f"document.querySelector('[data-history=\"{record_id}\"]').click();")
        browser.wait(f"document.querySelector('#history-{record_id}').textContent.includes('Đang giữ')")
        browser.evaluate("fetch('/api/admin/appointments/"+str(appointment_id)+"/"+action+"',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('admin_token'),'Content-Type':'application/json'},body:'{}'}).then(r=>r.json())")
        with app.app_context():
            db.session.expire_all()
            assert LieuTrinhUsage.query.filter_by(malh=appointment_id,state='released' if action=='cancel' else 'consumed').count()==1
        browser.navigate('/profile#treatments');browser.wait("document.querySelector('[data-history]')")
        if action=='complete':
            browser.navigate(f'/profile?review={appointment_id}#appointments');browser.wait("document.querySelector('#spaReviewDialog[open]')")
            assert not browser.evaluate('window.__uiErrors')
    # Actual admin form upload + unlimited validity, on the isolated database.
    browser.navigate('/admin/packages/new');browser.wait("document.querySelector('#packageItems .package-item')")
    image_path=artifacts/'upload-test.png';Image.new('RGB',(64,64),'#527A5E').save(image_path)
    browser.call('DOM.enable');root_node=browser.call('DOM.getDocument')['root']['nodeId']
    file_node=browser.call('DOM.querySelector',{'nodeId':root_node,'selector':'#packageImage'})['nodeId']
    browser.call('DOM.setFileInputFiles',{'nodeId':file_node,'files':[str(image_path)]})
    browser.evaluate(f"const f=document.querySelector('#packageForm');f.elements.tengoi.value='Gói ảnh thử nghiệm';f.elements.giagoi.value='1000000';f.elements.unlimited.checked=true;f.elements.unlimited.dispatchEvent(new Event('change'));f.querySelector('.package-item-service').value='{service_id}';f.querySelector('.package-item-sessions').value=5;f.dispatchEvent(new Event('input',{{bubbles:true}}));window.__formValid=f.reportValidity();f.dispatchEvent(new Event('submit',{{bubbles:true,cancelable:true}}));")
    clock.sleep(2)
    create_state=browser.evaluate("({path:location.pathname,message:document.querySelector('#packageMessage').textContent,visible:document.querySelector('#packageMessage').classList.contains('visible'),valid:window.__formValid,invalid:[...document.querySelectorAll('#packageForm :invalid')].map(e=>({name:e.name||e.className,value:e.value,disabled:e.disabled})),errors:window.__uiErrors})")
    assert create_state['path']=='/admin/packages',create_state
    browser.wait("document.querySelector('#packageMessage').textContent.length>0")
    with app.app_context():
        from app.models import GoiDichVu
        created=GoiDichVu.query.filter_by(tengoi='Gói ảnh thử nghiệm').one()
        assert created.anhgoi and created.validity_months is None
        created_id=created.magoi
    # Edit uses the separate route and must update the same package.
    browser.navigate(f'/admin/packages/{created_id}/edit');browser.wait("document.querySelector('#packageForm').elements.tengoi.value.length>0")
    browser.evaluate("const f=document.querySelector('#packageForm');f.elements.tengoi.value='Gói ảnh đã sửa';f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
    clock.sleep(1)
    browser.wait("location.pathname==='/admin/packages'")
    with app.app_context():
        assert GoiDichVu.query.count()==4
        assert db.session.get(GoiDichVu,created_id).tengoi=='Gói ảnh đã sửa'
    # Post-care instructions are now managed from the service modal.
    browser.navigate('/admin/services');browser.wait("document.querySelector('#services-table tbody tr')")
    browser.evaluate("openAddServiceModal()")
    assert browser.evaluate("document.querySelector('#service-post-care')&&document.querySelector('#serviceModal').style.display==='flex'")
    # Receptionist creates/collects cash, including tender/change and a printable receipt.
    browser.evaluate(f"localStorage.setItem('admin_token',{json.dumps(receptionist_token)});localStorage.setItem('admin_role','letan');")
    browser.navigate('/admin/package-sales')
    # Test server injects admin tokens on each page; switch to receptionist before requests.
    browser.wait("document.querySelector('#salePackage option[value=\""+str(package_id)+"\"]')")
    browser.wait("document.querySelector('#saleCustomer option[value=\""+str(customer_id)+"\"]')")
    browser.wait("!document.querySelector('#createPackageSale').disabled")
    browser.evaluate(f"localStorage.setItem('admin_token',{json.dumps(receptionist_token)});localStorage.setItem('admin_role','letan');document.querySelector('#saleCustomer').value='{customer_id}';document.querySelector('#salePackage').value='{package_id}';document.querySelector('#salePackage').dispatchEvent(new Event('change'));document.querySelector('#saleForm').dispatchEvent(new Event('submit',{{bubbles:true,cancelable:true}}));")
    browser.wait("!document.querySelector('#cashSalePanel').classList.contains('package-hidden')")
    browser.evaluate("document.querySelector('#cashReceived').value='1000';document.querySelector('#cashReceived').dispatchEvent(new Event('input'));")
    assert browser.evaluate("document.querySelector('#confirmPackageCash').disabled")
    browser.evaluate("document.querySelector('#cashReceived').value='1500000';document.querySelector('#cashReceived').dispatchEvent(new Event('input'));")
    assert browser.evaluate("document.querySelector('#cashChange').textContent.includes('300.000')")
    browser.evaluate("document.querySelector('#confirmPackageCash').click()")
    browser.wait("document.querySelector('#saleReceiptDialog').open")
    assert browser.evaluate("document.querySelector('#saleReceipt').textContent.includes('PG')&&document.querySelector('#saleReceipt').textContent.includes('Đã thanh toán')")
    browser.call('Emulation.setEmulatedMedia',{'media':'print'})
    print_styles=browser.evaluate("({receipt:getComputedStyle(document.querySelector('#saleReceipt')).visibility,button:getComputedStyle(document.querySelector('#printSaleReceipt')).display,open:document.querySelector('#saleReceiptDialog').open})")
    assert print_styles['receipt']=='visible' and print_styles['button']=='none',print_styles
    pdf=browser.call('Page.printToPDF',{'printBackground':True})['data']
    pdf_bytes=base64.b64decode(pdf)
    assert len(re.findall(rb'/Type\s*/Page\b',pdf_bytes))==1, 'Single-item receipt should print without blank pages'
    (artifacts/'package-receipt.pdf').write_bytes(pdf_bytes)
    browser.call('Emulation.setEmulatedMedia',{'media':''})
    browser.evaluate("document.querySelector('#closeSaleReceipt').click();document.querySelector('#saleMethod').value='vietqr';document.querySelector('#saleForm').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
    browser.wait("document.querySelector('#packagePaymentDialog').open&&document.querySelector('#packagePayment img')")
    with app.app_context():
        from app.models import GoiDichVuPurchase
        counter_purchase=GoiDichVuPurchase.query.order_by(GoiDichVuPurchase.id.desc()).first()
        counter_id=counter_purchase.id
        assert counter_purchase.created_by_staff==receptionist.manv
    # Mock bank event via authenticated webhook (no real payment).
    response=app.test_client().post('/api/payment/webhook/sepay',json={'id':'ui-counter-transfer','content':f'PKG{counter_id}','transferAmount':1200000,'transferType':'in'},headers={'Authorization':'Apikey test-sepay-key'})
    assert response.status_code==200
    browser.wait("document.querySelector('#packagePayment').textContent.includes('Thanh toán thành công')")
    assert not browser.evaluate('window.__uiErrors')
    browser.evaluate("document.querySelector('#closePackagePayment').click()")
    for width in [1920,1440,1024,768,390]:
        browser.call('Emulation.setDeviceMetricsOverride',dict(width=width,height=1000,deviceScaleFactor=1,mobile=width<768))
        assert browser.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
        browser.screenshot(f'{width}-package-sales.png')
    print('PASS upload/unlimited validity, receptionist cash/change/receipt and counter VietQR polling',flush=True)
    (artifacts/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS purchase, cash confirmation, reserve, release, consume, usage history and review link; no real payment or email sent',flush=True)
finally:
    try:
        browser.call('Browser.close')
    except Exception:
        process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill()
    server.shutdown()
    with app.app_context():db.engine.dispose()

"""Opt-in Edge browser checks: real DOM/login/CRUD, isolated DB, mail mocked."""
import base64
import json
import logging
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import timedelta
from urllib.request import urlopen

import pytest
import websocket
from flask_jwt_extended import create_access_token
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from billing_browser_check import Browser, free_port
from test_phase4_packages_care import package_data
from test_booking_gifts_reviews import review_data
from app.extensions import db
from app.models import NhanVien, DanhGia, TheLieuTrinhItem, TheLieuTrinh
from app.services import package_service as ps, email_service


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    fixture=conftest.app.__wrapped__();app=next(fixture)
    patch=pytest.MonkeyPatch();patch.setattr(email_service,'send_email',lambda *args,**kwargs:True)
    data=package_data.__wrapped__(app,patch)
    reviews=review_data.__wrapped__(app,data)
    with app.app_context():
        purchase=ps.create_purchase(data['id'],data['customer'],'cash')
        _,single,_=ps.confirm_purchase(purchase.id,purchase.amount,method='cash')
        single_id, original=single.mathe,single.items[0].id
        multi_package=ps.save_package(dict(tengoi='Combo hai dịch vụ',giagoi=500000,validity_months=None,
            items=[dict(madv=data['service'],total_sessions=2),dict(madv=data['other_service'],total_sessions=2)]))
        purchase=ps.create_purchase(multi_package.magoi,data['customer'],'cash')
        _,multi,_=ps.confirm_purchase(purchase.id,purchase.amount,method='cash')
        multi_id=multi.mathe
        db.session.commit()
        admin_token=create_access_token(identity=f"staff:{app.config['TEST_ADMIN_ID']}")
        staff_token=create_access_token(identity=f"staff:{app.config['TEST_STAFF_ID']}")
    server=make_server('127.0.0.1',0,app,threaded=False)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    port=free_port();artifacts=Path('tests/booking-gifts-reviews-preview.tmp').resolve();artifacts.mkdir(exist_ok=True)
    process=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-allow-origins=*',
        f'--remote-debugging-port={port}',f'--user-data-dir={artifacts / ("profile-"+str(port))}','about:blank'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    ws=None
    try:
        deadline=time.monotonic()+15
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1) as response:tabs=json.load(response)
                tab=next(t for t in tabs if t['type']=='page');break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(.2)
        ws=websocket.create_connection(tab['webSocketDebuggerUrl'],timeout=15,suppress_origin=True)
        b=Browser(ws);base_wait=b.wait
        b.wait=lambda expression:base_wait('Boolean('+expression+')')
        b.call('Page.enable')
        b.call('Network.clearBrowserCookies')
        b.call('Emulation.setTimezoneOverride',dict(timezoneId='Asia/Ho_Chi_Minh'))
        b.call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=900,deviceScaleFactor=1,mobile=False))
        b.call('Page.addScriptToEvaluateOnNewDocument',dict(source="window.__testDocumentToken=Math.random().toString(36);window.__uiErrors=[];window.addEventListener('error',e=>__uiErrors.push(e.message));window.addEventListener('unhandledrejection',e=>__uiErrors.push(String(e.reason)));"))
        def navigate(path):
            previous=b.evaluate('window.__testDocumentToken')
            b.call('Page.navigate',dict(url=base+path))
            b.wait('window.__testDocumentToken && window.__testDocumentToken!=='+json.dumps(previous)+' && document.readyState==="complete"')
        def reload():
            previous=b.evaluate('window.__testDocumentToken')
            b.call('Page.reload')
            b.wait('window.__testDocumentToken!=='+json.dumps(previous)+' && document.readyState==="complete"')
        def screenshot(name):
            (artifacts/name).write_bytes(base64.b64decode(b.call('Page.captureScreenshot',dict(format='png'))['data']))
        def check_errors():
            assert b.evaluate('window.__uiErrors')==[],b.evaluate('window.__uiErrors')
        def wait_selected(service):
            b.wait(q(f'.service-card-small.selected[data-service-id="{service}"]'))
        def q(selector):return 'document.querySelector('+json.dumps(selector)+')'
        def centered(selector,width):
            rect=b.evaluate(f'(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:r.x,y:r.y,w:r.width,h:r.height}}}})()')
            assert abs(rect['x']+rect['w']/2-width/2)<2,rect
            assert abs(rect['y']+rect['h']/2-450)<2,rect
            assert rect['w']<=width and rect['h']<=900,rect

        # Service CTA -> anonymous login -> exact URL -> selected service; reload stable.
        navigate(f"/services/{data['service']}")
        b.wait('document.querySelector("[data-service-reviews] [data-list]").textContent.includes("Chưa có đánh giá")')
        b.wait(q('a[href*="appointments/create?service="]'))
        b.evaluate(q('a[href*="appointments/create?service="]')+'.click()')
        b.wait('!!document.getElementById("loginModal")')
        b.evaluate('document.querySelector("#loginModal a.btn-primary").click()')
        b.wait('document.readyState==="complete" && !!document.getElementById("loginForm")')
        assert b.evaluate('new URLSearchParams(location.search).get("redirect")')==f"/appointments/create?service={data['service']}"
        b.evaluate('document.querySelector("[name=taikhoan]").value="customer_test";document.querySelector("[name=matkhau]").value="password";document.getElementById("loginForm").requestSubmit()')
        b.wait('!!document.getElementById("appointmentForm")');wait_selected(data['service'])
        assert b.evaluate('document.querySelectorAll(".service-card-small.selected").length')==1
        reload();wait_selected(data['service']);check_errors()
        navigate(f'/appointments/create?treatment={single_id}')
        wait_selected(data['service']);b.wait(f'PackageCare.getUsages()[0]?.the_item_id==={original}')
        assert '0' in b.evaluate('document.getElementById("summaryTotal").textContent')
        navigate(f'/appointments/create?treatment={multi_id}')
        b.wait('document.querySelectorAll("[data-booking-item]").length===2')
        assert b.evaluate('document.querySelectorAll(".service-card-small.selected").length')==0
        b.evaluate('document.querySelector("[data-booking-item]").click()');wait_selected(data['service'])
        assert b.evaluate('PackageCare.getUsages().length')==1
        navigate(f"/appointments/create?treatment={single_id}&service={data['service']}")
        wait_selected(data['service']);b.wait(f'PackageCare.getUsages()[0]?.the_item_id==={original}');check_errors()
        b.evaluate('window.savedCustomerFetch=CustomerAuth.fetch;CustomerAuth.fetch=(url,options)=>url==="/api/packages/my-treatments"?Promise.reject(new Error("temporary failure")):savedCustomerFetch(url,options)')
        b.evaluate(f'PackageCare.renderBooking([{data["service"]}],"2099-01-01")')
        assert b.evaluate('PackageCare.getUsages()[0].the_item_id')==original
        assert b.evaluate('document.querySelector("#bookingTreatments button").textContent')=='Thử lại'
        b.evaluate('CustomerAuth.fetch=savedCustomerFetch')
        navigate(f'/appointments/create?service=999999')
        b.wait('document.getElementById("bookingContext").textContent.includes("không tồn tại")')
        assert b.evaluate('document.querySelectorAll(".service-card-small.selected").length')==0
        navigate(f'/appointments/create?treatment={single_id}&service=999999')
        b.wait('document.getElementById("bookingContext").textContent.includes("không thuộc liệu trình")')
        assert b.evaluate('PackageCare.getUsages().length')==0

        # Staff treatment UI -> real gift form; centered across all requested widths.
        b.evaluate('localStorage.setItem("admin_token",'+json.dumps(staff_token)+');localStorage.setItem("admin_role","staff");localStorage.setItem("admin_user",JSON.stringify({role:"staff",hoten:"Staff Test"}))')
        navigate('/admin/packages#treatments')
        b.wait(q(f'[data-treatment-id="{single_id}"]'))
        assert b.evaluate('document.querySelector("[data-package-tab=packages]").hidden')
        b.evaluate(q(f'[data-treatment-id="{single_id}"]')+'.click()')
        b.wait('!!document.getElementById("giftServiceButton")')
        for width in (1920,1440,1024,768,390):
            b.call('Emulation.setDeviceMetricsOverride',dict(width=width,height=900,deviceScaleFactor=1,mobile=width<768))
            centered('#treatmentDetailDialog',width)
        b.evaluate('document.getElementById("giftServiceButton").click()')
        b.wait('document.getElementById("giftServiceDialog").open');centered('#giftServiceDialog',390)
        b.evaluate(f'document.querySelector("#giftServiceDialog [name=madv]").value="{data["service"]}";document.querySelector("#giftServiceDialog [name=gift_note]").value="Tặng thử trình duyệt";document.querySelector("#giftServiceDialog form").requestSubmit()')
        b.wait('document.getElementById("treatmentDetailContent").textContent.includes("Tặng thử trình duyệt")')
        screenshot('gift-treatment-mobile.png');check_errors()
        with app.app_context():gift_id=TheLieuTrinhItem.query.filter_by(source_type='gift').one().id
        # One service with separate package/gift rows must still preselect exactly one source.
        navigate(f'/appointments/create?treatment={single_id}')
        wait_selected(data['service']);b.wait(f'PackageCare.getUsages()[0]?.the_item_id==={original}')
        assert b.evaluate('PackageCare.getUsages().length')==1
        with app.app_context():
            staff=db.session.get(NhanVien,app.config['TEST_STAFF_ID'])
            _,expiring=ps.gift_service(single_id,dict(madv=data['service'],quantity=2,validity_days=7),staff)
            expiring_id=expiring.id
            db.session.get(TheLieuTrinh,single_id).expires_at=ps.local_now()-timedelta(days=1)
            db.session.commit()
        navigate(f'/appointments/create?treatment={single_id}')
        wait_selected(data['service']);b.wait(f'PackageCare.getUsages()[0]?.the_item_id==={expiring_id}')
        assert b.evaluate('PackageCare.getUsages().length')==1
        assert b.evaluate('document.getElementById("summaryTotal").textContent.replace(/[^0-9]/g,"")')=='0'
        check_errors()
        navigate('/profile#treatments');b.wait(q(f'a[href*="item={gift_id}"]'))
        b.evaluate(q(f'a[href*="item={gift_id}"]')+'.click()')
        wait_selected(data['service']);b.wait(f'PackageCare.getUsages()[0]?.the_item_id==={gift_id}');check_errors()

        # Completed multi-service review -> chosen service only -> profile edit -> staff reply -> public -> delete.
        apt=reviews['appointments'][0]
        navigate(f'/profile?review={apt}#appointments')
        b.wait('document.getElementById("spaReviewDialog")?.open')
        assert b.evaluate('document.querySelectorAll("#spaReviewDialog [name=rating]").length')==5
        assert b.evaluate('document.querySelector("#spaReviewDialog select")===null')
        def star_point(n):
            return b.evaluate(f'(()=>{{const r=document.querySelectorAll(".review-rating-option span")[{n-1}].getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=900,deviceScaleFactor=1,mobile=False))
        point=star_point(2)
        b.call('Input.dispatchMouseEvent',dict(type='mouseMoved',**point))
        assert b.evaluate('document.querySelectorAll("#spaReviewDialog .is-active").length')==2
        assert b.evaluate('document.querySelector("#spaReviewDialog [name=rating]:checked").value')=='5'
        b.call('Input.dispatchMouseEvent',dict(type='mouseMoved',x=2,y=2))
        assert b.evaluate('document.querySelectorAll("#spaReviewDialog .is-active").length')==5
        point=star_point(3)
        b.call('Input.dispatchMouseEvent',dict(type='mousePressed',button='left',clickCount=1,**point))
        b.call('Input.dispatchMouseEvent',dict(type='mouseReleased',button='left',clickCount=1,**point))
        assert b.evaluate('document.querySelector("#spaReviewDialog [name=rating]:checked").value')=='3'
        b.call('Emulation.setDeviceMetricsOverride',dict(width=390,height=900,deviceScaleFactor=1,mobile=True))
        b.call('Emulation.setTouchEmulationEnabled',dict(enabled=True))
        point=star_point(5)
        b.call('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[point]))
        b.call('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
        b.wait('document.querySelector("#spaReviewDialog [name=rating]:checked").value==="5"')
        screenshot('review-create-mobile.png')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=320,height=900,deviceScaleFactor=1,mobile=True))
        assert b.evaluate('document.querySelector("#spaReviewDialog").scrollWidth<=document.querySelector("#spaReviewDialog").clientWidth')
        b.call('Emulation.setDeviceMetricsOverride',dict(width=390,height=900,deviceScaleFactor=1,mobile=True))
        b.evaluate(q(f'#spaReviewDialog [name=service][value="{data["service"]}"]')+'.checked=true;document.querySelector("#spaReviewDialog textarea").value="Chăm sóc tốt <script>escaped</script>";document.querySelector("#spaReviewDialog form").requestSubmit()')
        b.wait('document.querySelectorAll("#myReviews .review-card").length===1')
        assert b.evaluate('document.querySelector("#myReviews script")===null')
        navigate('/profile#reviews');b.wait('!!document.querySelector("[data-edit-review]")')
        b.evaluate('document.querySelector("[data-edit-review]").click()');b.wait('document.getElementById("spaReviewDialog")?.open')
        assert b.evaluate('document.querySelector("#spaReviewDialog [name=rating]:checked").value')=='5'
        b.evaluate('document.querySelectorAll("#spaReviewDialog [name=rating]")[3].click()')
        assert b.evaluate('document.querySelector("#spaReviewDialog .review-rating-value").textContent')=='4/5'
        assert b.evaluate('document.querySelectorAll("#spaReviewDialog .is-active").length')==4
        b.evaluate('document.querySelector("#spaReviewDialog form").requestSubmit()')
        b.wait('document.querySelector("#myReviews .review-stars").getAttribute("aria-label")==="4 sao"')
        b.evaluate('document.querySelector("[data-edit-review]").click()');b.wait('document.getElementById("spaReviewDialog")?.open')
        assert b.evaluate('document.querySelector("#spaReviewDialog [name=rating]:checked").value')=='4'
        b.evaluate('document.querySelector(".review-close-button").click()');b.wait('!document.getElementById("spaReviewDialog")')
        navigate('/admin/reviews');b.wait('!!document.querySelector("[data-reply-review]")')
        assert b.evaluate('document.querySelectorAll("#adminReviews .review-card").length')==1
        b.evaluate('document.querySelector("[data-reply-review]").click()');b.wait('document.getElementById("spaReviewDialog")?.open')
        centered('#spaReviewDialog',390)
        b.evaluate('document.querySelector("#spaReviewDialog textarea").value="Spa cảm ơn bạn";document.querySelector("#spaReviewDialog form").requestSubmit()')
        b.wait('document.querySelector("#adminReviews .review-reply")?.textContent.includes("Spa cảm ơn bạn")');check_errors()
        navigate(f"/services/{data['service']}");b.wait('document.querySelector("[data-service-reviews] .review-reply")?.textContent.includes("Spa cảm ơn bạn")')
        b.evaluate('document.querySelector("[data-service-reviews]").scrollIntoView({block:"center"})')
        screenshot('service-review-mobile.png');check_errors()
        navigate(f'/profile?review={apt}#appointments');b.wait('document.getElementById("spaReviewDialog")?.open')
        assert b.evaluate('document.querySelector("#spaReviewDialog form")===null')
        assert b.evaluate('getComputedStyle(document.querySelector(".review-close-button")).color')=='rgb(0, 0, 0)'
        close_point=b.evaluate('(()=>{const r=document.querySelector(".review-close-button").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')
        b.call('Input.dispatchMouseEvent',dict(type='mouseMoved',**close_point))
        assert b.evaluate('getComputedStyle(document.querySelector(".review-close-button")).color')=='rgb(0, 0, 0)'
        screenshot('review-view-mobile.png')
        b.evaluate('document.querySelector(".review-dialog-close").click()')
        b.wait('!document.getElementById("spaReviewDialog")')
        b.evaluate(f'ReviewUI.openAppointmentReview({apt})');b.wait('document.getElementById("spaReviewDialog")?.open')
        b.call('Input.dispatchKeyEvent',dict(type='keyDown',key='Escape',code='Escape',windowsVirtualKeyCode=27))
        b.call('Input.dispatchKeyEvent',dict(type='keyUp',key='Escape',code='Escape',windowsVirtualKeyCode=27))
        b.wait('!document.getElementById("spaReviewDialog")')
        b.evaluate(f'ReviewUI.openAppointmentReview({apt})');b.wait('document.getElementById("spaReviewDialog")?.open')
        b.call('Input.dispatchMouseEvent',dict(type='mousePressed',x=2,y=2,button='left',clickCount=1))
        b.call('Input.dispatchMouseEvent',dict(type='mouseReleased',x=2,y=2,button='left',clickCount=1))
        b.wait('!document.getElementById("spaReviewDialog")')
        navigate('/profile#reviews');b.wait('!!document.querySelector("[data-delete-review]")')
        b.evaluate('window.confirm=()=>true;document.querySelector("[data-delete-review]").click()')
        b.wait('document.getElementById("myReviews").textContent.includes("chưa có đánh giá")')
        navigate(f"/services/{data['service']}");b.wait('document.querySelector("[data-service-reviews] [data-list]").textContent.includes("Chưa có đánh giá")');check_errors()
        print('PASS: service CTA/login/reload; single/multi/exact package+gift selection; gift UI; 5 viewport centering checks; review create/edit/view/delete; staff reply; public statistics and safe HTML rendering.')
        print('Artifacts: '+str(artifacts))
    except Exception:
        if ws:
            try:
                screenshot('failure.png')
                (artifacts/'failure.json').write_text(json.dumps(b.evaluate('({url:location.href,errors:window.__uiErrors,text:document.body.innerText,links:[...document.querySelectorAll("a")].map(a=>a.getAttribute("href"))})'),ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception:pass
        raise
    finally:
        if ws:ws.close()
        process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill()
        server.shutdown();patch.undo()
        try:next(fixture)
        except StopIteration:pass


if __name__=='__main__':main()

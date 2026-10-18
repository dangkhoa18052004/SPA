"""Headless Chrome: services, packages and customer treatments on the shared React admin shell (đợt 4).

Run after frontend build: python tests/admin_catalog_browser_check.py
In-memory database; no external services. Journey: add a service with image and category, edit and
deactivate it; create a package (savings, duplicate guard), edit it, deep links /new /<id> /<id>/edit;
legacy #treatments link opens treatments; treatment detail and gifting a service; role checks; 360–1440 px.
"""
import base64
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, DichVu, DanhMucDichVu, GoiDichVu, TheLieuTrinh
from app.services import email_service, package_service as ps
from admin_browser import Harness

artifacts = ROOT / '.test-tmp' / ('admin-catalog-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
image = artifacts / 'service.png'
image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEklEQVR4nGNgYPj/n4GBgYEBACXcA/3Zp8QpAAAAAElFTkSuQmCC'))
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='admin-catalog-browser-only-at-least-32-characters',
    BUSINESS_PORTAL_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=True, ADMIN_BILLING_REACT_ENABLED=True, ADMIN_CATALOG_REACT_ENABLED=True,
    EMPLOYEE_PORTAL_ENABLED=False, CRM_ENABLED=False, BI_REPORTS_ENABLED=False, AI_CHAT_JOBS_ENABLED=False, GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False))
email_service.send_email = lambda *args, **kwargs: True

with app.app_context():
    db.create_all()
    position = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
    db.session.add(position); db.session.flush()
    customer = KhachHang(hoten='Phạm Ngọc Lan', sdt='0904444555', taikhoan='lan', matkhau='hash', trangthai='active')
    actors = {role: NhanVien(hoten=f'Kiểm thử {role}', taikhoan=role, matkhau='hash', macv=position.macv, role=role, trangthai=True)
              for role in ('staff', 'manager', 'admin', 'letan')}
    skin = DanhMucDichVu(name='Chăm sóc da', slug='cham-soc-da')
    massage = DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=60, active=True)
    facial = DichVu(tendv='Chăm sóc da cơ bản', gia=500000, thoiluong=90, active=True)
    db.session.add_all([customer, *actors.values(), skin, massage, facial]); db.session.flush()
    package = ps.save_package(dict(tengoi='Combo thư giãn 5 buổi', giagoi=1200000, validity_months=6, items=[dict(madv=massage.madv, total_sessions=5)]))
    purchase = ps.create_purchase(package.magoi, customer.makh, 'cash')
    _, treatment, _ = ps.confirm_purchase(purchase.id, 1200000, method='cash')
    db.session.commit()
    ids = dict(massage=massage.madv, facial=facial.madv, package=package.magoi, treatment=treatment.mathe, category=skin.id)
    tokens = {role: create_access_token(identity=f'staff:{person.manv}') for role, person in actors.items()}
app.config['BROWSER_ROLE'] = 'admin'
h = Harness(app, tokens, artifacts)
browser = h.browser

try:
    browser.viewport(1440)

    # 1. Add a service with image, category and post-care text.
    browser.navigate('/admin/services')
    browser.wait("document.body.textContent.includes('Massage thư giãn')")
    browser.screenshot('services-1440')
    browser.click('[data-testid="service-new"]')
    browser.wait("document.querySelector('.ant-drawer-open input#tendv')", 'service form')
    browser.type('.ant-drawer-open input#tendv', 'Gội đầu dưỡng sinh')
    browser.type('.ant-drawer-open input#gia', '250000')
    browser.type('.ant-drawer-open input#thoiluong', '45')
    browser.choose('Danh mục dịch vụ', 'Chăm sóc da', search='da')
    browser.type('.ant-drawer-open textarea#post_care_instructions', 'Tránh gội lại trong 6 giờ.')
    browser.upload('.ant-drawer-open input[aria-label="Ảnh dịch vụ"]', image)
    browser.wait("document.querySelector('.ant-drawer-open .catalog-image-field img').src.startsWith('blob:')", 'image preview')
    browser.screenshot('service-form-1440')
    browser.click('[data-testid="service-save"]')
    browser.wait("!document.querySelector('.ant-drawer-open input#tendv') && document.body.textContent.includes('Gội đầu dưỡng sinh')", 'service saved')
    created = h.query(lambda: (lambda s: (float(s.gia), s.thoiluong, s.category_id, bool(s.anhdichvu), s.post_care_instructions, s.active))(DichVu.query.filter_by(tendv='Gội đầu dưỡng sinh').one()))
    assert created == (250000.0, 45, ids['category'], True, 'Tránh gội lại trong 6 giờ.', True), created

    # 2. Edit: new price and deactivate; the status filter (kept in the URL) finds it.
    hair = h.query(lambda: DichVu.query.filter_by(tendv='Gội đầu dưỡng sinh').one().madv)
    browser.button('Sửa', f"document.querySelector(\"tr[data-row-key='{hair}']\")")
    browser.wait("document.querySelector('.ant-drawer-open input#gia')")
    browser.type('.ant-drawer-open input#gia', '280000')
    browser.click('.ant-drawer-open button#active')
    browser.click('[data-testid="service-save"]')
    browser.wait("!document.querySelector('.ant-drawer-open input#gia')")
    assert h.query(lambda: (lambda s: (float(s.gia), s.active))(db.session.get(DichVu, hair))) == (280000.0, False)
    browser.choose('Trạng thái dịch vụ', 'Ngừng hoạt động')
    browser.wait(f"location.search.includes('status=false') && document.querySelectorAll('.desktop-table tbody tr.ant-table-row').length===1", 'inactive filter')

    # 3. Create a package from the list (in-app navigation), with savings and duplicate guard.
    browser.navigate('/admin/packages')
    browser.wait("document.body.textContent.includes('Combo thư giãn 5 buổi')")
    browser.screenshot('packages-1440')
    browser.js('window.__same = true')
    browser.js("[...document.querySelectorAll('a')].find(a=>a.textContent.includes('Tạo gói mới')).click()")
    browser.wait("location.pathname==='/admin/packages/new' && document.querySelector('input#tengoi')", 'new form')
    assert browser.js('window.__same === true'), 'create link reloaded the page'
    browser.type('input#tengoi', 'Liệu trình da 6 buổi')
    browser.type('input#giagoi', '2500000')
    browser.choose('Dịch vụ dòng 1', 'Chăm sóc da cơ bản', search='da')
    browser.type('input[aria-label="Số buổi dòng 1"]', '4')
    browser.button('+ Thêm dịch vụ')
    browser.wait("document.querySelector('input[aria-label=\"Dịch vụ dòng 2\"]')")
    assert browser.js("""(()=>{const i=document.querySelector('input[aria-label="Dịch vụ dòng 2"]');
        i.closest('.ant-select').querySelector('.ant-select-selector').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return true})()""")
    browser.wait("[...document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option-disabled')].some(o=>o.textContent.includes('Chăm sóc da cơ bản'))", 'duplicate disabled')
    browser.key('Escape', 27)
    browser.choose('Dịch vụ dòng 2', 'Massage thư giãn', search='massage')
    browser.type('input[aria-label="Số buổi dòng 2"]', '2')
    browser.wait("document.querySelector('[data-testid=package-savings]').textContent.includes('100.000')", 'savings 100k')
    browser.screenshot('package-form-1440')
    browser.click('[data-testid="package-save"]')
    browser.wait("/^\\/admin\\/packages\\/\\d+$/.test(location.pathname) && document.querySelector('h1')?.textContent.includes('Liệu trình da 6 buổi')", 'detail after create')
    new_id = int(browser.js("location.pathname.split('/').pop()"))
    assert h.query(lambda: sorted((i.madv, i.total_sessions) for i in db.session.get(GoiDichVu, new_id).items)) == sorted([(ids['facial'], 4), (ids['massage'], 2)])
    browser.screenshot('package-detail-1440')

    # 4. Edit via deep link; leaving with unsaved changes asks first; saving updates the price.
    browser.navigate(f'/admin/packages/{new_id}/edit')
    browser.wait("document.querySelector('input#tengoi')?.value==='Liệu trình da 6 buổi'", 'edit form filled')
    browser.type('input#giagoi', '2400000')
    browser.button('Hủy')
    browser.wait("document.querySelector('.ant-modal-confirm')", 'unsaved warning')
    browser.button('Tiếp tục sửa', "document.querySelector('.ant-modal-confirm')")
    browser.click('[data-testid="package-save"]')
    browser.wait(f"location.pathname==='/admin/packages/{new_id}'", 'saved edit')
    assert h.query(lambda: float(db.session.get(GoiDichVu, new_id).giagoi)) == 2400000.0

    # 5. Legacy #treatments link, treatment detail and gifting a service.
    browser.navigate('/admin/packages#treatments', ready="document.body.textContent.includes('Phạm Ngọc Lan')")
    assert browser.js("location.search.includes('tab=treatments') && !location.hash")
    browser.button('Chi tiết', f"document.querySelector(\".ant-tabs-tabpane-active tr[data-row-key='{ids['treatment']}']\")")
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Dịch vụ trong gói')", 'treatment detail')
    browser.screenshot('treatment-detail-1440')
    browser.button('Tặng dịch vụ', "document.querySelector('.ant-drawer-open')")
    browser.choose('Dịch vụ tặng', 'Chăm sóc da cơ bản', search='da')
    browser.type('.ant-modal input#quantity', '2')
    browser.js("[...document.querySelectorAll('.ant-modal .ant-radio-button-wrapper')].find(e=>e.textContent.includes('Số ngày')).click()")
    browser.wait("document.querySelector('.ant-modal input#validity_days')")
    browser.button('Xác nhận tặng', "document.querySelector('.ant-modal')")
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Dịch vụ tặng')", 'gift listed')
    gift = h.query(lambda: [(i.madv, i.total_sessions, i.source_type, i.expires_at is not None) for i in db.session.get(TheLieuTrinh, ids['treatment']).items if i.source_type == 'gift'])
    assert gift == [(ids['facial'], 2, 'gift', True)], gift
    browser.close_modals()

    # 6. Roles: technicians see treatments only; front desk has no access or menu link.
    app.config['BROWSER_ROLE'] = 'staff'
    browser.navigate('/admin/packages', ready="document.body.textContent.includes('Phạm Ngọc Lan')")
    assert not browser.js("[...document.querySelectorAll('a,button')].some(e=>e.textContent.includes('Tạo gói mới'))")
    browser.navigate('/admin/services', ready="document.body.textContent.includes('Không có quyền')")
    app.config['BROWSER_ROLE'] = 'letan'
    browser.navigate('/admin/packages', ready="document.body.textContent.includes('Không có quyền')")
    browser.js("document.querySelectorAll('.admin-sidebar .ant-menu-submenu-title').forEach(e=>e.click())")
    assert not browser.js("!!document.querySelector(\".admin-sidebar a[href='/admin/packages']\")"), 'front desk must not get a packages link'

    # 7. Responsive.
    app.config['BROWSER_ROLE'] = 'manager'
    for width in [360, 390, 768, 1024]:
        browser.viewport(width)
        for path in ['/admin/services', '/admin/packages', f'/admin/packages/{new_id}/edit', '/admin/packages?tab=treatments']:
            browser.navigate(path, ready="document.querySelector('.admin-shell h1')")
            browser.screenshot(f"catalog{path.replace('/', '-').replace('?', '-').replace('=', '-')}-{width}")
    print('Admin catalog browser check passed. Screenshots:', artifacts)
finally:
    h.close()

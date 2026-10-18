"""Headless Chrome: invoices and counter package sales on the shared React admin shell (đợt 3).

Run after frontend build: python tests/admin_billing_browser_check.py
In-memory database; VietQR uses test bank details and the bank confirmation is simulated by calling
the same service the webhook uses — no request leaves the machine except the QR image URL.
Journey: cash sale with change → treatment activated → receipt; lost create response reconciled
without a duplicate purchase; VietQR sale confirmed while the dialog waits; invoices list filters in
the URL; service invoice and pending package paid from the list; role check; 360–1440 px.
"""
from datetime import timedelta
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, DichVu, HoaDon, ChiTietHoaDon, ThanhToan, GoiDichVuPurchase, TheLieuTrinh
from app.services import email_service, package_service as ps
from admin_browser import Harness

artifacts = ROOT / '.test-tmp' / ('admin-billing-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='admin-billing-browser-only-at-least-32-characters',
    BUSINESS_PORTAL_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=True, ADMIN_BILLING_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=False,
    CRM_ENABLED=False, BI_REPORTS_ENABLED=False, AI_CHAT_JOBS_ENABLED=False, GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False,
    VIETQR_BANK_ID='TESTBANK', VIETQR_ACCOUNT_NO='123456', VIETQR_ACCOUNT_NAME='TEST SPA'))
email_service.send_email = lambda *args, **kwargs: True

with app.app_context():
    db.create_all()
    position = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
    db.session.add(position); db.session.flush()
    customer = KhachHang(hoten='Trần Thu Hà', sdt='0902222333', taikhoan='ha', matkhau='hash', trangthai='active')
    second = KhachHang(hoten='Lê Minh Quân', sdt='0903333444', taikhoan='quan', matkhau='hash', trangthai='active')
    actors = {role: NhanVien(hoten=f'Kiểm thử {role}', taikhoan=role, matkhau='hash', macv=position.macv, role=role, trangthai=True)
              for role in ('staff', 'manager', 'admin', 'letan')}
    massage = DichVu(tendv='Massage thư giãn', gia=300000, thoiluong=60, active=True)
    facial = DichVu(tendv='Chăm sóc da', gia=500000, thoiluong=90, active=True)
    db.session.add_all([customer, second, *actors.values(), massage, facial]); db.session.flush()
    package = ps.save_package(dict(tengoi='Combo thư giãn 5 buổi', giagoi=1200000, validity_months=6, items=[dict(madv=massage.madv, total_sessions=5)]))
    counter = ps.save_package(dict(tengoi='Liệu trình da 3 buổi', giagoi=1350000, validity_months=3, customer_sale_enabled=False,
                                   items=[dict(madv=facial.madv, total_sessions=3)]))
    unpaid = HoaDon(makh=second.makh, manv=actors['letan'].manv, tongtien=500000, trangthai='Chưa thanh toán')
    db.session.add(unpaid); db.session.flush()
    db.session.add(ChiTietHoaDon(mahd=unpaid.mahd, madv=facial.madv, soluong=1, dongia=500000, thanhtien=500000))
    db.session.commit()
    ids = dict(customer=customer.makh, second=second.makh, package=package.magoi, counter=counter.magoi, unpaid=unpaid.mahd)
    tokens = {role: create_access_token(identity=f'staff:{person.manv}') for role, person in actors.items()}
app.config['BROWSER_ROLE'] = 'letan'
h = Harness(app, tokens, artifacts)
browser = h.browser


def purchases():
    return h.query(lambda: [(p.id, p.magoi, p.makh, p.status, p.payment_method) for p in GoiDichVuPurchase.query.order_by(GoiDichVuPurchase.id)])


try:
    browser.viewport(1440)
    browser.navigate('/admin/package-sales')
    assert browser.js("document.querySelectorAll('#root').length===1 && !!document.querySelector('.admin-menu .ant-menu-item-selected')")

    # 1. Cash sale with change; the treatment is activated only after payment.
    browser.choose('Khách hàng', 'Trần Thu Hà', search='0902')
    browser.choose('Gói dịch vụ', 'Combo thư giãn', search='combo')
    browser.wait("document.querySelector('[data-testid=sale-package-preview]')?.textContent.includes('5 buổi')", 'preview')
    browser.screenshot('package-sale-form-1440')
    browser.click('[data-testid="sale-create"]')
    browser.wait("document.querySelector('[data-testid=package-payable]')?.textContent.includes('1.200.000')", 'payment dialog')
    sale = purchases()[-1]
    assert sale[3] == 'pending' and h.query(lambda: TheLieuTrinh.query.filter_by(purchase_id=sale[0]).count()) == 0
    browser.type('#package-cash', '1500000')
    browser.wait("document.querySelector('[data-testid=package-change]').textContent.includes('300.000')", 'change')
    browser.screenshot('package-cash-1440')
    browser.button('Xác nhận đã nhận tiền', "document.querySelector('.ant-modal')")
    browser.wait("document.querySelector('[data-testid=package-paid]')", 'paid result')
    assert h.query(lambda: (db.session.get(GoiDichVuPurchase, sale[0]).status, TheLieuTrinh.query.filter_by(purchase_id=sale[0]).count())) == ('paid', 1)
    browser.button('Xem / in phiếu', "document.querySelector('.ant-modal')")
    browser.wait("document.querySelector('[data-testid=receipt]')?.textContent.includes('Tiền thối')", 'receipt')
    assert browser.js("document.querySelector('[data-testid=receipt]').textContent.includes('300.000')")
    browser.screenshot('package-receipt-1440')
    browser.close_modals()

    # 2. Lost create response: one purchase only, payment continues on it.
    before = len(purchases())
    browser.drop_response('/api/admin/package-sales')
    browser.choose('Khách hàng', 'Lê Minh Quân', search='Quân')
    browser.choose('Gói dịch vụ', 'Liệu trình da', search='#' + str(ids['counter']))
    assert browser.js("document.querySelector('[data-testid=sale-package-preview]').textContent.includes('Chỉ bán tại quầy')")
    browser.click('[data-testid="sale-create"]')
    browser.wait("document.body.textContent.includes('đã được tạo trước đó')", 'reconciled')
    assert len(purchases()) == before + 1, 'lost response must not create a second purchase'
    browser.wait("document.querySelector('[data-testid=package-payable]')?.textContent.includes('1.350.000')", 'payment for reconciled sale')
    browser.close_modals()
    pending_sale = purchases()[-1][0]

    # 3. VietQR sale: the bank confirmation (same service as the webhook) completes the open dialog.
    browser.choose('Khách hàng', 'Trần Thu Hà', search='0902')
    browser.choose('Gói dịch vụ', 'Combo thư giãn', search='combo')
    browser.js("[...document.querySelectorAll('.ant-radio-button-wrapper')].find(e=>e.textContent.trim()==='VietQR').click()")
    browser.click('[data-testid="sale-create"]')
    browser.wait("document.querySelector('.invoice-qr')?.textContent.includes('PKG')", 'qr shown')
    browser.screenshot('package-vietqr-1440')
    qr_sale = purchases()[-1]
    assert qr_sale[3:] == ('pending', 'vietqr')
    h.query(lambda: (ps.confirm_purchase(qr_sale[0], 1200000, external_id='TEST-BANK-1', method='vietqr'), db.session.commit()))
    browser.wait("document.querySelector('[data-testid=package-paid]')", 'vietqr paid', seconds=15)
    browser.close_modals()

    # 4. Invoices: both sources, filters in the URL, Back restores them.
    browser.navigate('/admin/invoices')
    browser.wait(f"document.body.textContent.includes('HD{ids['unpaid']:06d}') && document.body.textContent.includes('PG{sale[0]:06d}')", 'both kinds')
    browser.screenshot('invoices-1440')
    browser.choose('Loại hóa đơn', 'Gói dịch vụ')
    browser.wait("location.search.includes('type=package') && !document.body.textContent.includes('HD0')", 'package filter')
    browser.choose('Trạng thái thanh toán', 'Chưa thanh toán')
    browser.wait(f"location.search.includes('status=') && document.querySelectorAll('.desktop-table tbody tr.ant-table-row').length===1", 'one pending package')
    browser.js('history.back()')
    browser.wait("location.search.includes('type=package') && !location.search.includes('status=')")
    browser.navigate(f'/admin/invoices?q={ids["unpaid"]}')

    # 5. Collect a service invoice from the list (cash), then the pending package (cash).
    browser.wait(f"document.querySelector(\"tr[data-row-key='service-{ids['unpaid']}']\")", 'service row')
    browser.button('Thu tiền', f"document.querySelector(\"tr[data-row-key='service-{ids['unpaid']}']\")")
    browser.wait("document.querySelector('[data-testid=invoice-payable]')?.textContent.includes('500.000')", 'invoice dialog')
    browser.button('Tiền mặt', "document.querySelector('.ant-modal')")
    browser.button('Xác nhận đã thu tiền', "document.querySelector('.ant-modal')")
    browser.wait(f"document.querySelector(\"tr[data-row-key='service-{ids['unpaid']}']\")?.textContent.includes('Đã thanh toán')", 'service paid')
    assert h.query(lambda: (db.session.get(HoaDon, ids['unpaid']).trangthai, ThanhToan.query.filter_by(mahd=ids['unpaid']).count())) == ('Đã thanh toán', 1)
    browser.navigate('/admin/invoices?type=package&status=Ch%C6%B0a+thanh+to%C3%A1n')
    browser.button('Thu tiền', f"document.querySelector(\"tr[data-row-key='package-{pending_sale}']\")")
    browser.wait("document.querySelector('[data-testid=package-payable]')", 'package dialog from invoices')
    browser.button('Xác nhận đã nhận tiền', "document.querySelector('.ant-modal')")
    browser.wait("document.querySelector('[data-testid=package-paid]')")
    assert h.query(lambda: db.session.get(GoiDichVuPurchase, pending_sale).status) == 'paid'
    browser.close_modals()
    browser.navigate(f'/admin/invoices?q={ids["unpaid"]}')
    browser.button('Xem', f"document.querySelector(\"tr[data-row-key='service-{ids['unpaid']}']\")")
    browser.wait("document.querySelector('[data-testid=receipt]')?.textContent.includes('Tiền mặt')")
    assert not browser.js("[...document.querySelectorAll('.ant-modal button')].some(b=>b.textContent.includes('Thanh toán ngay'))")

    # 6. Roles: staff cannot open billing.
    app.config['BROWSER_ROLE'] = 'staff'
    browser.navigate('/admin/invoices', ready="document.body.textContent.includes('Không có quyền')")
    browser.navigate('/admin/package-sales', ready="document.body.textContent.includes('Không có quyền')")

    # 7. Responsive.
    app.config['BROWSER_ROLE'] = 'letan'
    for width in [360, 390, 768, 1024]:
        browser.viewport(width)
        browser.navigate('/admin/invoices')
        browser.screenshot(f'invoices-{width}')
        browser.navigate('/admin/package-sales')
        browser.screenshot(f'package-sales-{width}')
    print('Admin billing browser check passed. Screenshots:', artifacts)
finally:
    h.close()

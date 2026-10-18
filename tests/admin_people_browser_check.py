"""Headless Chrome: staff, positions, shifts, registrations, personal schedule and old payroll history (đợt 5).

Run after frontend build: python tests/admin_people_browser_check.py
In-memory database; shift e-mails are stubbed. Journey: admin adds/edits/deactivates staff and manages
positions; a manager creates a shift and assigns/unassigns staff; a technician registers for a shift,
the manager approves it and it appears in the technician's week; admin reads old payroll; role checks;
360–1440 px.
"""
from datetime import date, time, timedelta
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, CaLam, DangKyCaLam, Luong
from app.admin import shift_manage_bp
from app.services import email_service, package_service as ps
from admin_browser import Harness

artifacts = ROOT / '.test-tmp' / ('admin-people-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='admin-people-browser-only-at-least-32-characters',
    BUSINESS_PORTAL_ENABLED=True, ADMIN_PEOPLE_REACT_ENABLED=True, ATTENDANCE_ENABLED=False, PAYROLL_V2_ENABLED=True,
    EMPLOYEE_PORTAL_ENABLED=False, CRM_ENABLED=False, BI_REPORTS_ENABLED=False, AI_CHAT_JOBS_ENABLED=False, GEMINI_API_KEY='', SEPAY_POLL_ENABLED=False))
email_service.send_email = lambda *args, **kwargs: True
shift_manage_bp.send_shift_notification_email = lambda *args, **kwargs: None

with app.app_context():
    db.create_all()
    technician = ChucVu(tencv='Kỹ thuật viên', dongiagio=40000)
    desk = ChucVu(tencv='Lễ tân', dongiagio=35000)
    db.session.add_all([technician, desk]); db.session.flush()
    actors = {role: NhanVien(hoten=f'Kiểm thử {role}', taikhoan=role, matkhau='hash', macv=technician.macv, role=role, trangthai=True)
              for role in ('staff', 'manager', 'admin', 'letan')}
    db.session.add_all(actors.values()); db.session.flush()
    today = ps.local_now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(days=7)  # next week: every shift is in the future
    open_shift = CaLam(ngay=monday + timedelta(days=2), giobatdau=time(13), gioketthuc=time(17), sogio=4, hesoluong=1)
    db.session.add(open_shift); db.session.flush()
    db.session.add(Luong(manv=actors['staff'].manv, thang=9, nam=2026, luongcoban=3200000, thuong=200000, khautru=0, tongluong=3400000, hoahong=0))
    db.session.commit()
    ids = dict(open_shift=open_shift.maca, staff=actors['staff'].manv, technician=technician.macv, desk=desk.macv)
    tokens = {role: create_access_token(identity=f'staff:{person.manv}') for role, person in actors.items()}
week = monday.isoformat()
app.config['BROWSER_ROLE'] = 'admin'
h = Harness(app, tokens, artifacts)
browser = h.browser

try:
    browser.viewport(1440)

    # 1. Staff: add, edit role, deactivate and reactivate.
    browser.navigate('/admin/staff')
    browser.wait("document.body.textContent.includes('Kiểm thử manager')")
    browser.screenshot('staff-1440')
    browser.click('[data-testid="staff-new"]')
    browser.wait("document.querySelector('.ant-drawer-open input#hoten')")
    browser.type('.ant-drawer-open input#hoten', 'Trần Thị Mai')
    browser.type('.ant-drawer-open input#taikhoan', 'mai.tran')
    browser.type('.ant-drawer-open input#matkhau', 'matkhau-123')
    browser.type('.ant-drawer-open input#sdt', '0905556677')
    browser.choose('Chức vụ', 'Kỹ thuật viên', search='kỹ')
    browser.screenshot('staff-form-1440')
    browser.click('[data-testid="staff-save"]')
    browser.wait("!document.querySelector('.ant-drawer-open input#hoten') && document.body.textContent.includes('Trần Thị Mai')", 'staff added')
    mai = h.query(lambda: (lambda s: (s.manv, s.role, s.trangthai, s.macv))(NhanVien.query.filter_by(taikhoan='mai.tran').one()))
    assert mai[1:] == ('staff', True, ids['technician']), mai
    browser.button('Sửa', f"document.querySelector(\"tr[data-row-key='{mai[0]}']\")")
    browser.wait("document.querySelector('.ant-drawer-open input#hoten')?.value==='Trần Thị Mai'")
    browser.choose('Vai trò', 'Lễ tân')
    browser.choose('Chức vụ', 'Lễ tân ·', search='lễ')
    browser.click('[data-testid="staff-save"]')
    browser.wait("!document.querySelector('.ant-drawer-open input#hoten')")
    got = h.query(lambda: (lambda s: (s.role, s.macv))(db.session.get(NhanVien, mai[0]))); assert got == ('letan', ids['desk']), (got, ids)
    browser.button('Vô hiệu hóa', f"document.querySelector(\"tr[data-row-key='{mai[0]}']\")")
    browser.confirm_modal('Vô hiệu hóa')
    browser.wait(f"document.querySelector(\"tr[data-row-key='{mai[0]}']\")?.textContent.includes('Đã vô hiệu')")
    assert h.query(lambda: db.session.get(NhanVien, mai[0]).trangthai) is False
    browser.button('Kích hoạt', f"document.querySelector(\"tr[data-row-key='{mai[0]}']\")")
    browser.confirm_modal('Kích hoạt')
    browser.wait(f"document.querySelector(\"tr[data-row-key='{mai[0]}']\")?.textContent.includes('Đang hoạt động')")

    # 2. Positions: add, edit the hourly rate, deleting one still in use is refused.
    browser.navigate('/admin/roles')
    browser.click('[data-testid="position-new"]')
    browser.wait("document.querySelector('.ant-modal input#tencv')")
    browser.type('.ant-modal input#tencv', 'Thực tập sinh')
    browser.type('.ant-modal input#dongiagio', '25000')
    browser.click('[data-testid="position-save"]')
    browser.wait("document.body.textContent.includes('Thực tập sinh') && !document.querySelector('.ant-modal input#tencv')")
    intern = h.query(lambda: ChucVu.query.filter_by(tencv='Thực tập sinh').one().macv)
    browser.button('Sửa', f"document.querySelector(\"tr[data-row-key='{intern}']\")")
    browser.wait("document.querySelector('.ant-modal input#dongiagio')")
    browser.type('.ant-modal input#dongiagio', '27000')
    browser.click('[data-testid="position-save"]')
    browser.wait("!document.querySelector('.ant-modal input#tencv')")
    assert h.query(lambda: float(db.session.get(ChucVu, intern).dongiagio)) == 27000.0
    browser.button('Xóa', f"document.querySelector(\"tr[data-row-key='{ids['technician']}']\")")
    browser.wait("document.body.textContent.includes('nhân viên giữ chức vụ này')", 'in-use warning')
    browser.button('Xóa', f"document.querySelector(\"tr[data-row-key='{intern}']\")")
    browser.confirm_modal('Xóa')
    browser.wait("!document.body.textContent.includes('Thực tập sinh')")
    browser.screenshot('positions-1440')

    # 3. Manager creates a shift next week, assigns and unassigns a technician.
    app.config['BROWSER_ROLE'] = 'manager'
    browser.navigate(f'/admin/shifts?from={week}&to={(monday + timedelta(days=6)).isoformat()}')
    browser.wait(f"document.querySelector(\"tr[data-row-key='{ids['open_shift']}']\")", 'seeded shift')
    browser.click('[data-testid="shift-new"]')
    browser.wait("document.querySelector('.ant-modal input[aria-label=\"Ngày ca\"]')")
    browser.date('Ngày ca', (monday + timedelta(days=1)).isoformat())
    browser.wait("document.querySelector('.ant-modal')?.textContent.includes('9 giờ')", 'hours preview')
    browser.click('[data-testid="shift-save"]')
    browser.wait("!document.querySelector('.ant-modal input[aria-label=\"Ngày ca\"]')")
    created = h.query(lambda: CaLam.query.filter_by(ngay=monday + timedelta(days=1)).one().maca)
    browser.wait(f"document.querySelector(\"tr[data-row-key='{created}']\")", 'new shift listed')
    browser.screenshot('shifts-1440')
    browser.button('Phân ca', f"document.querySelector(\"tr[data-row-key='{created}']\")")
    browser.wait("document.querySelector('.ant-drawer-open input[aria-label=\"Nhân viên cần phân\"]')")
    browser.choose('Nhân viên cần phân', 'Kiểm thử staff', search='staff')
    browser.button('Phân ca', "document.querySelector('.ant-drawer-open')")
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Nhân viên trong ca (1)')", 'assigned')
    assert h.query(lambda: [n.manv for n in db.session.get(CaLam, created).nhanvien]) == [ids['staff']]
    browser.screenshot('shift-assign-1440')
    browser.button('Bỏ phân ca', "document.querySelector('.ant-drawer-open')")
    browser.confirm_modal('Bỏ phân ca')
    browser.wait("document.querySelector('.ant-drawer-open')?.textContent.includes('Nhân viên trong ca (0)')", 'unassigned')
    browser.close_modals()
    browser.button('Xóa', f"document.querySelector(\"tr[data-row-key='{created}']\")")
    browser.confirm_modal('Xóa ca')
    browser.wait(f"!document.querySelector(\"tr[data-row-key='{created}']\")")
    assert h.query(lambda: db.session.get(CaLam, created)) is None

    # 4. Technician registers for an open shift; the manager approves; it shows in the week.
    app.config['BROWSER_ROLE'] = 'staff'
    browser.navigate(f'/admin/register-shift?week={week}')
    browser.wait(f"document.querySelector('[data-shift=\"{ids['open_shift']}\"] button')", 'open shift')
    browser.button('Đăng ký', f"document.querySelector('[data-shift=\"{ids['open_shift']}\"]')")
    browser.wait(f"document.querySelector('[data-shift=\"{ids['open_shift']}\"]')?.textContent.includes('Chờ duyệt')", 'pending')
    assert h.query(lambda: DangKyCaLam.query.filter_by(manv=ids['staff'], maca=ids['open_shift']).one().trangthai) == 'pending'
    browser.screenshot('register-shift-1440')
    app.config['BROWSER_ROLE'] = 'manager'
    browser.navigate('/admin/approve-shifts')
    browser.wait("document.body.textContent.includes('Kiểm thử staff')")
    browser.button('Duyệt')
    browser.wait("document.body.textContent.includes('Không có đăng ký nào chờ duyệt')", 'approved')
    assert h.query(lambda: ids['staff'] in [n.manv for n in db.session.get(CaLam, ids['open_shift']).nhanvien])
    app.config['BROWSER_ROLE'] = 'staff'
    browser.navigate(f'/admin/my-schedule?week={week}')
    browser.wait("document.querySelector('.week-shift.approved')?.textContent.includes('13:00–17:00')", 'my week')
    browser.screenshot('my-schedule-1440')
    browser.navigate(f'/admin/register-shift?week={week}')
    browser.wait(f"document.querySelector('[data-shift=\"{ids['open_shift']}\"]')?.textContent.includes('Đã được phân')", 'assigned state')

    # 5. Old payroll history is read-only for admin.
    app.config['BROWSER_ROLE'] = 'admin'
    browser.navigate('/admin/salary?month=2026-09')
    browser.wait("document.body.textContent.includes('Kiểm thử staff') && document.body.textContent.includes('3.400.000')", 'history row')
    assert not browser.js("[...document.querySelectorAll('button')].some(b=>/Tính lương|Lưu/.test(b.textContent))")
    browser.screenshot('legacy-salary-1440')

    # 6. Roles.
    app.config['BROWSER_ROLE'] = 'letan'
    browser.navigate('/admin/shifts', ready="document.body.textContent.includes('Chỉ quản lý')")
    app.config['BROWSER_ROLE'] = 'manager'
    browser.navigate('/admin/staff', ready="document.body.textContent.includes('Chỉ quản trị viên')")
    browser.navigate('/admin/salary', ready="document.body.textContent.includes('Không có quyền')")

    # 7. Responsive.
    for width in [360, 390, 768, 1024]:
        browser.viewport(width)
        app.config['BROWSER_ROLE'] = 'admin'
        for path in ['/admin/staff', '/admin/roles', f'/admin/shifts?from={week}']:
            browser.navigate(path)
            browser.screenshot(f"people{path.split('?')[0].replace('/', '-')}-{width}")
        app.config['BROWSER_ROLE'] = 'staff'
        for path in [f'/admin/my-schedule?week={week}', f'/admin/register-shift?week={week}']:
            browser.navigate(path)
            browser.screenshot(f"people{path.split('?')[0].replace('/', '-')}-{width}")
    print('Admin people browser check passed. Screenshots:', artifacts)
finally:
    h.close()

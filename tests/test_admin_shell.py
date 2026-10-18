"""Shared admin shell rollout: React pages behind the flag, legacy pages kept as a fallback."""
import json


def _build(tmp_path):
    folder = tmp_path / 'portal'
    (folder / '.vite').mkdir(parents=True)
    (folder / 'portal.js').write_text('')
    (folder / '.vite/manifest.json').write_text(json.dumps({'src/main.tsx': {'file': 'portal.js', 'css': ['admin.css']}}))


def test_profile_and_login_use_shared_shell_only_when_enabled(app, client, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    app.config.update(BUSINESS_PORTAL_ENABLED=True)
    # An unbuilt release keeps the legacy pages working.
    assert b'type="module"' not in client.get('/admin/profile').data
    assert b'adminLoginForm' in client.get('/admin/login').data
    _build(tmp_path)
    for path in ['/admin/profile', '/admin/login', '/admin/dashboard']:
        page = client.get(path).data
        assert b'portal.js' in page and page.count(b'id="root"') == 1, path
        legacy = client.get(f'{path}?ui=legacy').data
        assert b'portal.js' not in legacy, path
    assert b'adminLoginForm' in client.get('/admin/login?ui=legacy').data
    app.config.update(BUSINESS_PORTAL_ENABLED=False)
    for path in ['/admin/profile', '/admin/login', '/admin/dashboard']:
        assert b'portal.js' not in client.get(path).data, path


def test_staff_context_reports_business_portal_flag(app, client, staff_auth_headers):
    app.config.update(BUSINESS_PORTAL_ENABLED=True)
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['business_portal'] is True
    app.config.update(BUSINESS_PORTAL_ENABLED=False)
    body = client.get('/api/me/operations', headers=staff_auth_headers).json
    assert body['features']['business_portal'] is False and body['user']['role'] == 'staff'


def test_login_still_lands_on_profile(app, client):
    with app.app_context():
        from werkzeug.security import generate_password_hash
        from app.extensions import db
        from app.models import NhanVien
        staff = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        staff.matkhau = generate_password_hash('secret-123')
        account = staff.taikhoan
        db.session.commit()
    result = client.post('/api/auth/login/staff', json={'taikhoan': account, 'matkhau': 'secret-123'})
    assert result.status_code == 200 and result.json['redirect_url'] == '/admin/profile'


def test_booking_screens_switch_by_flag_with_legacy_fallback(app, client, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    _build(tmp_path)
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=False)
    for path in ['/admin/appointments', '/admin/customers']:
        assert b'portal.js' not in client.get(path).data, path
    app.config.update(ADMIN_BOOKING_REACT_ENABLED=True)
    for path in ['/admin/appointments', '/admin/customers']:
        assert b'portal.js' in client.get(path).data, path
        assert b'portal.js' not in client.get(f'{path}?ui=legacy').data, path
    # The booking flag alone never bypasses the shared-shell switch.
    app.config.update(BUSINESS_PORTAL_ENABLED=False)
    assert b'portal.js' not in client.get('/admin/appointments').data


def test_staff_context_reports_booking_flag(app, client, staff_auth_headers):
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=True)
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_booking'] is True
    app.config.update(BUSINESS_PORTAL_ENABLED=False)
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_booking'] is False


def test_appointment_list_adds_customer_fields_and_filter(app, client, admin_auth_headers, staff_auth_headers):
    from datetime import datetime, time, timedelta
    from app.extensions import db
    from app.models import KhachHang, LichHen
    with app.app_context():
        other = KhachHang(hoten='Khách khác', sdt='0900000999', taikhoan='other_shell', matkhau='x', trangthai='active')
        db.session.add(other); db.session.flush()
        day = datetime.combine(datetime.now().date() + timedelta(days=1), time(10))
        db.session.add_all([LichHen(makh=app.config['TEST_CUSTOMER_ID'], ngaygio=day, trangthai='pending'),
                            LichHen(makh=other.makh, ngaygio=day, trangthai='pending')])
        db.session.commit()
        other_id = other.makh
        phone = db.session.get(KhachHang, app.config['TEST_CUSTOMER_ID']).sdt
    rows = client.get('/api/admin/appointments', headers=admin_auth_headers).json
    assert {r['makh'] for r in rows} >= {app.config['TEST_CUSTOMER_ID'], other_id}
    mine = client.get(f"/api/admin/appointments?makh={app.config['TEST_CUSTOMER_ID']}", headers=admin_auth_headers).json
    assert mine and all(r['makh'] == app.config['TEST_CUSTOMER_ID'] and r['khachhang_sdt'] == phone for r in mine)
    # Existing fields are unchanged for current callers, and staff still cannot read the desk list.
    assert {'malh', 'ngaygio', 'khachhang_hoten', 'dichvu_ten', 'nhanvien_hoten', 'trangthai', 'permissions'} <= set(mine[0])
    assert client.get('/api/admin/appointments', headers=staff_auth_headers).status_code == 403


def test_billing_screens_switch_by_flag_with_legacy_fallback(app, client, staff_auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    _build(tmp_path)
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_BILLING_REACT_ENABLED=False)
    for path in ['/admin/invoices', '/admin/package-sales']:
        assert b'portal.js' not in client.get(path).data, path
    app.config.update(ADMIN_BILLING_REACT_ENABLED=True)
    for path in ['/admin/invoices', '/admin/package-sales']:
        assert b'portal.js' in client.get(path).data, path
        assert b'portal.js' not in client.get(f'{path}?ui=legacy').data, path
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_billing'] is True
    app.config.update(BUSINESS_PORTAL_ENABLED=False)
    assert b'portal.js' not in client.get('/admin/package-sales').data
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_billing'] is False


def test_catalog_screens_switch_by_flag_with_legacy_fallback(app, client, staff_auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    _build(tmp_path)
    paths = ['/admin/services', '/admin/packages', '/admin/packages/new', '/admin/packages/3', '/admin/packages/3/edit']
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_CATALOG_REACT_ENABLED=False)
    for path in paths:
        assert b'portal.js' not in client.get(path).data, path
    app.config.update(ADMIN_CATALOG_REACT_ENABLED=True)
    for path in paths:
        assert b'portal.js' in client.get(path).data, path
        assert b'portal.js' not in client.get(f'{path}?ui=legacy').data, path
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_catalog'] is True
    app.config.update(BUSINESS_PORTAL_ENABLED=False)
    assert b'portal.js' not in client.get('/admin/packages').data


def test_people_screens_switch_by_flag_with_legacy_fallback(app, client, staff_auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    _build(tmp_path)
    paths = ['/admin/staff', '/admin/roles', '/admin/shifts', '/admin/approve-shifts', '/admin/my-schedule', '/admin/register-shift', '/admin/salary']
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_PEOPLE_REACT_ENABLED=False)
    for path in paths:
        assert b'portal.js' not in client.get(path).data, path
    app.config.update(ADMIN_PEOPLE_REACT_ENABLED=True)
    for path in paths:
        assert b'portal.js' in client.get(path).data, path
        assert b'portal.js' not in client.get(f'{path}?ui=legacy').data, path
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_people'] is True


def test_staff_list_and_personal_schedule_expose_ids(app, client, admin_auth_headers, staff_auth_headers):
    from datetime import date, time
    from app.extensions import db
    from app.models import CaLam, NhanVien, DangKyCaLam
    rows = client.get('/api/admin/staff/list-all', headers=admin_auth_headers).json
    assert rows and all('macv' in r and 'chucvu' in r for r in rows)
    with app.app_context():
        staff = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        assigned = CaLam(ngay=date(2026, 10, 20), giobatdau=time(9), gioketthuc=time(12), sogio=3, hesoluong=1)
        open_shift = CaLam(ngay=date(2026, 10, 21), giobatdau=time(13), gioketthuc=time(17), sogio=4, hesoluong=1)
        db.session.add_all([assigned, open_shift]); db.session.flush()
        staff.calam.append(assigned)
        db.session.add(DangKyCaLam(manv=staff.manv, maca=open_shift.maca, trangthai='pending'))
        db.session.commit()
        ids = (assigned.maca, open_shift.maca)
    result = client.get('/api/admin/my-schedule-list?start_date=2026-10-19&end_date=2026-10-25', headers=staff_auth_headers).json['schedule']
    by_code = {r['trangthai_code']: r for r in result}
    assert by_code['approved']['maca'] == ids[0] and by_code['pending']['maca'] == ids[1] and by_code['pending']['reg_id']
    # Existing fields are unchanged.
    assert {'ngay', 'ten_ca', 'giobatdau', 'gioketthuc', 'trangthai_text', 'colleagues'} <= set(by_code['approved'])

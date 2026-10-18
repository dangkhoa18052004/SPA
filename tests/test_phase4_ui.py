"""Phase 4 rollout and dashboard authorization, without writing live data."""
import json
from datetime import datetime, time

from app.extensions import db
from app.models import LichHen, NhanVien


def test_ui_entries_are_independent_with_legacy_fallback(app, client, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    app.config.update(BUSINESS_PORTAL_ENABLED=True, CUSTOMER_BOOKING_REACT_ENABLED=True)
    assert b'booking.js' not in client.get('/appointments/create?service=1').data
    assert b'portal.js' not in client.get('/admin/dashboard').data
    folder = tmp_path / 'portal'
    (folder / '.vite').mkdir(parents=True)
    (folder / 'booking.js').write_text('')
    (folder / 'portal.js').write_text('')
    (folder / '.vite/manifest.json').write_text(json.dumps({
        'src/main.tsx': {'file': 'portal.js', 'css': ['admin.css']},
        'src/booking-main.tsx': {'file': 'booking.js', 'css': ['customer.css']}
    }))
    booking = client.get('/appointments/create?treatment=1&service=1&item=2').data
    assert b'booking.js' in booking and b'customer.css' in booking and b'admin.css' not in booking
    assert b'js/customers/auth-session.js' in booking and b'js/loyalty-payment.js' in booking
    admin = client.get('/admin/dashboard').data
    assert b'portal.js' in admin and b'admin.css' in admin and b'customer.css' not in admin
    # Entry URLs must match imports from split chunks, avoiding a second root via ?v=.
    assert b'portal.js?' not in admin and b'booking.js?' not in booking
    assert b'booking.js' not in client.get('/appointments/create?ui=legacy').data
    assert b'portal.js' not in client.get('/admin/dashboard?ui=legacy').data
    app.config.update(BUSINESS_PORTAL_ENABLED=False, CUSTOMER_BOOKING_REACT_ENABLED=False)
    assert b'booking.js' not in client.get('/appointments/create').data
    assert b'portal.js' not in client.get('/admin/dashboard').data


def test_dashboard_uses_current_role_and_only_own_staff_appointments(app, client, staff_auth_headers, customer_auth_headers):
    with app.app_context():
        ids = [app.config['TEST_STAFF_ID'], app.config['TEST_STAFF2_ID']]
        for staff_id in ids:
            db.session.add(LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=staff_id,
                                  ngaygio=datetime.combine(datetime.now().date(), time(11)), trangthai='pending'))
        db.session.commit()
    response = client.get('/api/dashboard/appointments/my-schedule-today', headers=staff_auth_headers)
    assert response.status_code == 200 and len(response.json['appointments']) == 1
    for path in ['/api/analytics/summary', '/api/analytics/revenue-timeseries', '/api/dashboard/appointments/today']:
        assert client.get(path, headers=staff_auth_headers).status_code == 403
        assert client.get(path, headers=customer_auth_headers).status_code == 403
    with app.app_context():
        staff = db.session.get(NhanVien, ids[0])
        staff.role = 'letan'
        db.session.commit()
    assert client.get('/api/dashboard/appointments/today', headers=staff_auth_headers).status_code == 200
    assert client.get('/api/analytics/summary', headers=staff_auth_headers).status_code == 403
    with app.app_context():
        staff = db.session.get(NhanVien, ids[0])
        staff.trangthai = False
        db.session.commit()
    assert client.get('/api/dashboard/appointments/today', headers=staff_auth_headers).status_code == 403


def test_dashboard_today_follows_vietnam_date_even_when_server_date_differs(app, client, admin_auth_headers, monkeypatch):
    import importlib
    module = importlib.import_module('app.routes.dashboard_api_bp')
    monkeypatch.setattr(module, 'local_now', lambda: datetime(2030, 1, 2, 0, 15))
    with app.app_context():
        for target in (datetime(2030, 1, 1, 23, 30), datetime(2030, 1, 2, 9)):
            db.session.add(LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'], ngaygio=target, trangthai='pending'))
        db.session.commit()
    response = client.get('/api/dashboard/appointments/today', headers=admin_auth_headers)
    assert response.status_code == 200 and len(response.json['appointments']) == 1
    assert response.json['appointments'][0]['ngaygio'].startswith('2030-01-02')

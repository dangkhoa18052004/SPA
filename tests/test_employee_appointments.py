"""Employees can see their full appointment history without accessing another employee's customers."""
from datetime import datetime
import pytest
from app.extensions import db
from app.models import LichHen, ChiTietLichHen, DichVu, NhanVien
from app.services import attendance_service as att


@pytest.fixture
def bookings(app, monkeypatch):
    monkeypatch.setattr(att, 'now_utc', lambda: datetime(2026, 10, 15, 6, tzinfo=att.UTC))
    with app.app_context():
        service = DichVu(tendv='Massage thử', gia=300000, thoiluong=60, active=True)
        db.session.add(service); db.session.flush()
        own_ids = []
        for day, hour, status in [(15, 14, 'pending'), (16, 9, 'confirmed'), (15, 12, 'in_progress'),
                (13, 9, 'completed'), (14, 10, 'cancelled')]:
            booking = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'],
                ngaygio=datetime(2026, 10, day, hour), trangthai=status, ghichu='Khách muốn phòng yên tĩnh')
            db.session.add(booking); db.session.flush()
            db.session.add(ChiTietLichHen(malh=booking.malh, madv=service.madv))
            own_ids.append(booking.malh)
        foreign = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF2_ID'],
            ngaygio=datetime(2026, 10, 15, 15), trangthai='confirmed', ghichu='PRIVATE OTHER EMPLOYEE')
        unassigned = LichHen(makh=app.config['TEST_CUSTOMER_ID'], manv=None,
            ngaygio=datetime(2026, 10, 15, 16), trangthai='pending', ghichu='PRIVATE UNASSIGNED')
        db.session.add_all([foreign, unassigned]); db.session.commit()
        return dict(ids=own_ids, foreign_id=foreign.malh, unassigned_id=unassigned.malh)


def test_all_history_and_details_are_scoped_to_current_employee(client, staff_auth_headers, bookings):
    result = client.get('/api/me/appointments', headers=staff_auth_headers)
    assert result.status_code == 200
    data = result.json
    assert data['total'] == 5 and {item['id'] for item in data['items']} == set(bookings['ids'])
    assert data['summary'] == dict(total=5, today=2, upcoming=2)
    assert data['today'] == '2026-10-15'
    assert data['items'][0]['id'] == bookings['ids'][0]  # Closest future appointment first.
    first = data['items'][0]
    assert first['scheduled_at'] == '2026-10-15T14:00:00+07:00'
    assert first['ends_at'] == '2026-10-15T15:00:00+07:00'
    assert first['customer_name'] == 'Khách hàng Test' and first['customer_phone'] == '0900000002'
    assert first['services'][0]['name'] == 'Massage thử'
    assert first['status_label'] == 'Chờ xác nhận'
    assert 'PRIVATE' not in result.get_data(as_text=True)
    assert 'matkhau' not in result.get_data(as_text=True)


def test_staff_id_spoofing_and_admin_role_do_not_broaden_personal_view(app, client, staff_auth_headers, admin_auth_headers, bookings):
    response = client.get(f"/api/me/appointments?staff_id={app.config['TEST_STAFF2_ID']}&manv={app.config['TEST_STAFF2_ID']}", headers=staff_auth_headers)
    assert {item['id'] for item in response.json['items']} == set(bookings['ids'])
    admin = client.get('/api/me/appointments', headers=admin_auth_headers)
    assert admin.status_code == 200 and admin.json['items'] == [] and admin.json['total'] == 0


def test_filters_and_pagination_keep_ownership(client, staff_auth_headers, bookings):
    today = client.get('/api/me/appointments?from_date=2026-10-15&to_date=2026-10-15', headers=staff_auth_headers)
    assert today.status_code == 200 and today.json['total'] == 2
    assert {item['id'] for item in today.json['items']} == set(bookings['ids'][::2][:2])
    for status in ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']:
        filtered = client.get('/api/me/appointments?status=' + status, headers=staff_auth_headers)
        assert filtered.status_code == 200 and filtered.json['total'] == 1
        assert filtered.json['items'][0]['status'] == status
    first = client.get('/api/me/appointments?per_page=2&page=1', headers=staff_auth_headers).json
    second = client.get('/api/me/appointments?per_page=2&page=2', headers=staff_auth_headers).json
    assert first['total'] == second['total'] == 5
    assert not {item['id'] for item in first['items']} & {item['id'] for item in second['items']}


def test_customer_search_is_case_insensitive_and_escapes_wildcards(client, staff_auth_headers, bookings):
    for value in ['khách', '0900000002']:
        result = client.get('/api/me/appointments', query_string=dict(q=value), headers=staff_auth_headers)
        assert result.status_code == 200 and result.json['total'] == 5
    assert client.get('/api/me/appointments', query_string=dict(q='%'), headers=staff_auth_headers).json['total'] == 0


@pytest.mark.parametrize('query', ['from_date=wrong', 'to_date=wrong', 'from_date=2026-10-16&to_date=2026-10-15',
    'status=unknown', 'page=0', 'per_page=101'])
def test_invalid_filters_return_actionable_error(client, staff_auth_headers, bookings, query):
    result = client.get('/api/me/appointments?' + query, headers=staff_auth_headers)
    assert result.status_code == 400 and result.json['message']


def test_customer_anonymous_and_inactive_staff_cannot_access(app, client, customer_auth_headers, staff_auth_headers, bookings):
    assert client.get('/api/me/appointments').status_code == 401
    assert client.get('/api/me/appointments', headers=customer_auth_headers).status_code == 403
    with app.app_context():
        db.session.get(NhanVien, app.config['TEST_STAFF_ID']).trangthai = False
        db.session.commit()
    assert client.get('/api/me/appointments', headers=staff_auth_headers).status_code == 403

"""Admin care rollout and chat parity, using the isolated fixture database only."""
from datetime import datetime, timedelta
import json
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import Hoithoai, TinNhan, NhanVien, KhachHang


def test_care_flags_and_unknown_page(app, client, tmp_path, monkeypatch, staff_auth_headers):
    folder = tmp_path / 'portal'
    (folder / '.vite').mkdir(parents=True)
    (folder / 'portal-test.js').write_text('')
    (folder / '.vite/manifest.json').write_text(json.dumps({'src/main.tsx': {'file': 'portal-test.js'}}))
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    paths = ['/admin/loyalty', '/admin/reviews', '/admin/chat']
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_CARE_REACT_ENABLED=False)
    for path in paths:
        assert b'portal-test.js' not in client.get(path).data
    app.config['ADMIN_CARE_REACT_ENABLED'] = True
    for path in paths:
        assert b'portal-test.js' in client.get(path).data
        assert b'portal-test.js' not in client.get(path + '?ui=legacy').data
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_care'] is True
    unknown = client.get('/admin/page-does-not-exist')
    assert unknown.status_code == 404 and b'portal-test.js' in unknown.data
    app.config['BUSINESS_PORTAL_ENABLED'] = False
    assert client.get('/api/me/operations', headers=staff_auth_headers).json['features']['admin_care'] is False
    for path in paths:
        assert b'portal-test.js' not in client.get(path).data
    (folder / 'portal-test.js').unlink()
    app.config['BUSINESS_PORTAL_ENABLED'] = True
    assert b'portal-test.js' not in client.get('/admin/chat').data


@pytest.fixture
def conversation(app):
    with app.app_context():
        row = Hoithoai(makh=app.config['TEST_CUSTOMER_ID'], manv=app.config['TEST_STAFF_ID'])
        db.session.add(row); db.session.flush()
        db.session.add(TinNhan(maht=row.maht, noidung='Cần tư vấn dịch vụ', nguoigui_makh=row.makh, da_doc=False))
        db.session.commit()
        return row.maht


def test_chat_reads_marks_seen_sends_utc_and_keeps_assignment(app, client, conversation, staff_auth_headers, admin_auth_headers):
    listing = client.get('/api/chat/conversations', headers=admin_auth_headers)
    assert listing.status_code == 200, listing.json
    row = listing.json['conversations'][0]
    assert row['unread_count'] == 1 and row['assigned_staff_id'] == app.config['TEST_STAFF_ID'] and row['assigned_staff_name']
    messages = client.get(f'/api/chat/conversations/{conversation}/messages', headers=staff_auth_headers)
    assert messages.status_code == 200 and len(messages.json['messages']) == 1
    assert client.get('/api/chat/conversations', headers=staff_auth_headers).json['conversations'][0]['unread_count'] == 0
    before = datetime.utcnow()
    sent = client.post(f'/api/chat/conversations/{conversation}/messages', headers=staff_auth_headers, json={'noidung': '  Spa xin chào  '})
    assert sent.status_code == 201
    with app.app_context():
        message = db.session.get(TinNhan, sent.json['matn'])
        assert message.noidung == 'Spa xin chào' and before <= message.thoigiangui <= datetime.utcnow() + timedelta(seconds=1)
        assert message.nguoigui_manv == app.config['TEST_STAFF_ID']


def test_chat_denies_other_staff_inactive_and_wrong_customer(app, client, conversation, staff_auth_headers, customer_auth_headers):
    with app.app_context():
        original = db.session.get(NhanVien, app.config['TEST_STAFF_ID'])
        other = NhanVien.query.filter(NhanVien.role == 'staff', NhanVien.manv != original.manv).first()
        other_headers = {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{other.manv}')}
        original.trangthai = False; db.session.commit()
    path = f'/api/chat/conversations/{conversation}/messages'
    assert client.get('/api/chat/conversations', headers=staff_auth_headers).status_code == 403
    assert client.get(path, headers=staff_auth_headers).status_code == 403
    assert client.post(path, headers=staff_auth_headers, json={'noidung': 'test'}).status_code == 403
    assert client.get(path, headers=other_headers).status_code == 403
    assert client.post(path, headers=other_headers, json={'noidung': 'test'}).status_code == 403
    with app.app_context():
        outsider = KhachHang(hoten='Other customer', taikhoan='outsider_chat', matkhau='hash', trangthai='active')
        db.session.add(outsider); db.session.commit()
        outsider_headers = {'Authorization': 'Bearer ' + create_access_token(identity=f'customer:{outsider.makh}')}
    assert client.get(path, headers=outsider_headers).status_code == 403
    assert client.post(path, headers=outsider_headers, json={'noidung': 'test'}).status_code == 403
    with app.app_context():
        customer = db.session.get(KhachHang, app.config['TEST_CUSTOMER_ID']); customer.trangthai = 'inactive'; db.session.commit()
    assert client.get(path, headers=customer_auth_headers).status_code == 403


@pytest.mark.parametrize('body', [None, [], {'noidung': ' '}, {'noidung': 123}, {'noidung': 'a' * 5001}])
def test_chat_rejects_invalid_message_without_writing(app, client, conversation, admin_auth_headers, body):
    assert client.post(f'/api/chat/conversations/{conversation}/messages', headers=admin_auth_headers, json=body).status_code == 400
    with app.app_context():
        assert TinNhan.query.count() == 1


def test_chat_assignment_roles_and_data(app, client, conversation, admin_auth_headers, staff_auth_headers):
    response = client.get('/api/admin/conversations/assignees', headers=admin_auth_headers)
    assert response.status_code == 200 and response.json['items']
    assert all(set(r) == {'manv', 'hoten'} for r in response.json['items'])
    assert client.get('/api/admin/conversations/assignees', headers=staff_auth_headers).status_code == 403
    path = f'/api/admin/conversations/{conversation}/assign'
    assert client.put(path, headers=admin_auth_headers, json={'manv': app.config['TEST_STAFF_ID']}).status_code == 200
    assert client.put(path, headers=staff_auth_headers, json={'manv': app.config['TEST_STAFF_ID']}).status_code == 403
    assert client.put(path, headers=admin_auth_headers, json={'manv': True}).status_code == 400
    with app.app_context():
        db.session.get(NhanVien, app.config['TEST_STAFF_ID']).trangthai = False; db.session.commit()
    assert client.put(path, headers=admin_auth_headers, json={'manv': app.config['TEST_STAFF_ID']}).status_code == 400


def test_customer_service_picker_photo_remains_supported(client, conversation, customer_auth_headers):
    content = '[SERVICE_CARD:1|Massage|300000|60|data:image/jpeg;base64,' + 'YQ==' * 1800 + '] Tôi muốn đặt lịch'
    response = client.post(f'/api/chat/conversations/{conversation}/messages', headers=customer_auth_headers, json={'noidung': content})
    assert response.status_code == 201
    bad = content.replace('image/jpeg', 'image/svg+xml')
    assert client.post(f'/api/chat/conversations/{conversation}/messages', headers=customer_auth_headers, json={'noidung': bad}).status_code == 400

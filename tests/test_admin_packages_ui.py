from app.extensions import db
from app.models import DichVu, GoiDichVu
from app.services import package_service


def test_admin_package_pages_are_separated(client):
    list_page = client.get('/admin/packages')
    assert list_page.status_code == 200
    assert b'data-admin-packages-page="list"' in list_page.data
    assert b'id="packageForm"' not in list_page.data
    assert b'id="postCareForm"' not in list_page.data

    create_page = client.get('/admin/packages/new')
    assert create_page.status_code == 200
    assert b'data-admin-packages-page="form"' in create_page.data
    assert b'data-form-mode="create"' in create_page.data
    assert b'id="packageForm"' in create_page.data

    detail_page = client.get('/admin/packages/123')
    edit_page = client.get('/admin/packages/123/edit')
    assert detail_page.status_code == 200
    assert b'data-admin-packages-page="detail"' in detail_page.data
    assert edit_page.status_code == 200
    assert b'data-form-mode="edit"' in edit_page.data


def test_admin_can_read_inactive_package_detail(app, client, admin_auth_headers):
    with app.app_context():
        item = DichVu(tendv='Dịch vụ kiểm thử', gia=200000, active=True)
        db.session.add(item)
        db.session.flush()
        package = package_service.save_package({
            'tengoi': 'Gói ngừng bán',
            'giagoi': 180000,
            'validity_months': 3,
            'active': False,
            'items': [{'madv': item.madv, 'total_sessions': 1}],
        })
        db.session.commit()
        package_id = package.magoi

    response = client.get(f'/api/admin/packages/{package_id}', headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.json['package']['active'] is False


def test_post_care_is_managed_from_service_form(app, client, admin_auth_headers):
    services_page = client.get('/admin/services')
    assert services_page.status_code == 200
    assert b'id="service-post-care"' in services_page.data

    response = client.post('/api/admin/services', headers=admin_auth_headers, data={
        'tendv': 'Chăm sóc da kiểm thử',
        'gia': '300000',
        'post_care_instructions': 'Dưỡng ẩm và tránh nắng trong 24 giờ.',
    })
    assert response.status_code == 201
    service_id = response.json['madv']

    listing = client.get('/api/admin/services', headers=admin_auth_headers)
    created = next(item for item in listing.json if item['madv'] == service_id)
    assert created['post_care_instructions'] == 'Dưỡng ẩm và tránh nắng trong 24 giờ.'

    response = client.put(f'/api/admin/services/{service_id}', headers=admin_auth_headers, data={
        'post_care_instructions': 'Không dùng nước nóng trong 24 giờ.',
    })
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(DichVu, service_id).post_care_instructions == 'Không dùng nước nóng trong 24 giờ.'


def test_post_care_rejects_oversized_content(client, admin_auth_headers):
    response = client.post('/api/admin/services', headers=admin_auth_headers, data={
        'tendv': 'Dịch vụ lỗi',
        'gia': '100000',
        'post_care_instructions': 'x' * 10001,
    })
    assert response.status_code == 400

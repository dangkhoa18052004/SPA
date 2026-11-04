"""Unknown pages get a Vietnamese 404 with ways back; APIs and assets keep their own 404 responses."""


def test_unknown_page_renders_friendly_404(client):
    response = client.get('/khong-ton-tai', headers={'Accept': 'text/html'})
    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'Không tìm thấy trang' in body and 'href="/"' in body and 'href="/services"' in body


def test_unknown_staff_area_page_points_back_to_admin(client, app):
    app.config['BUSINESS_PORTAL_ENABLED'] = False  # legacy admin: abort(404) from the admin blueprint
    response = client.get('/admin/khong-ton-tai', headers={'Accept': 'text/html'})
    assert response.status_code == 404
    assert 'href="/admin/dashboard"' in response.get_data(as_text=True)


def test_unknown_customer_package_uses_404_page_with_reason(client):
    response = client.get('/packages/999999', headers={'Accept': 'text/html'})
    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'Gói dịch vụ không tồn tại hoặc đã ngừng bán.' in body and '<html' in body.lower()


def test_api_and_static_404_are_not_rendered_as_pages(client):
    for path in ['/api/khong-ton-tai', '/static/css/khong-ton-tai.css']:
        response = client.get(path, headers={'Accept': 'text/html'})
        assert response.status_code == 404
        assert 'Không tìm thấy trang' not in response.get_data(as_text=True)

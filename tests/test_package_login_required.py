"""Khách chưa đăng nhập bấm "Mua gói" → hộp yêu cầu đăng nhập (giống trang đặt lịch)."""
from app.extensions import db
from app.models import GoiDichVu


def _package(app):
    with app.app_context():
        p = GoiDichVu(tengoi='Gói thử', giagoi=100000, validity_months=1, active=True)
        db.session.add(p); db.session.commit()
        return p.magoi


def test_anonymous_page_has_login_modal(app, client):
    pid = _package(app)
    for url in ('/packages', f'/packages/{pid}'):
        html = client.get(url).get_data(as_text=True)
        assert 'data-logged-in="0"' in html and 'id="packageLoginModal"' in html
        assert 'Bạn cần đăng nhập để mua gói dịch vụ' in html


def test_logged_in_customer_flag(app, client):
    with client.session_transaction() as s:
        s.update(user_id=app.config['TEST_CUSTOMER_ID'], user_type='customer')
    assert 'data-logged-in="1"' in client.get('/packages').get_data(as_text=True)


def test_purchase_api_still_requires_login(app, client):
    pid = _package(app)
    assert client.post(f'/api/packages/{pid}/purchase', json={'payment_method': 'vietqr'}).status_code == 401


def test_js_requires_login_and_resumes_purchase():
    with open('app/static/js/packages.js', encoding='utf-8') as f:
        js = f.read()
    assert 'if(!(await customerLoggedIn())) return requireLogin(id);' in js and 'restoreAccessToken()' in js
    assert "back.searchParams.set('buy',id)" in js and "get('buy')" in js

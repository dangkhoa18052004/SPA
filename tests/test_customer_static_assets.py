"""Verify customer pages reference assets served by Flask, including package pages."""
import re
from urllib.parse import urlsplit

from app.models import GoiDichVu
from app.extensions import db


def test_customer_pages_static_assets(app, client):
    with app.app_context():
        package = GoiDichVu(tengoi="Static check", giagoi=100000, validity_months=1, active=True)
        db.session.add(package)
        db.session.commit()
        package_id = package.magoi
    pages = ["/", "/services", "/profile", "/appointments/create", "/packages", f"/packages/{package_id}"]
    adapter = app.url_map.bind("localhost")
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200, page
        html = response.get_data(as_text=True)
        for expected in ["/static/css/customers/style.css", "/static/css/customers/responsive.css", "/static/images/logo.jpg"]:
            assert expected in html, (page, expected)
        urls = set(re.findall(r'(?:href|src)=[\"\'](/static/[^\"\']+)', html))
        for url in urls:
            path = urlsplit(url).path
            assert adapter.match(path)[0] == "static", (page, url)
            asset = client.get(url)
            assert asset.status_code == 200, (page, url, asset.status_code)
            assert asset.data, (page, url)
            if path.endswith(".css"):
                assert asset.mimetype == "text/css", (page, url, asset.content_type)
            elif path.endswith(".js"):
                assert asset.mimetype in ("text/javascript", "application/javascript"), (page, url, asset.content_type)
            elif path.endswith(".jpg"):
                assert asset.mimetype == "image/jpeg", (page, url, asset.content_type)

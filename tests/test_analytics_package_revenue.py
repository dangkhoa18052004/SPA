"""F01: doanh thu bán gói phải nằm trong analytics/dashboard, tách riêng dịch vụ/gói/tổng."""
from datetime import timedelta

from app.extensions import db
from app.models import HoaDon, ThanhToan, GoiDichVuPurchase
from app.services import package_service, analytics_service

from test_phase4_packages_care import package_data, activate, purchase  # noqa: F401


def _today():
    return package_service.local_now().date().isoformat()


def _summary(client, headers):
    today = _today()
    chart = client.get(f'/api/analytics/revenue-timeseries?from={today}&to={today}', headers=headers).json
    stats = client.get('/api/dashboard/stats', headers=headers).json['stats']
    return chart, stats


def _pay_service(app, customer_id, amount=300000):
    with app.app_context():
        invoice = HoaDon(makh=customer_id, manv=app.config['TEST_STAFF_ID'], tongtien=amount, trangthai='Đã thanh toán')
        db.session.add(invoice)
        db.session.flush()
        db.session.add(ThanhToan(mahd=invoice.mahd, sotien=amount, phuongthuc='Tiền mặt',
                                 ngaythanhtoan=package_service.local_now()))
        db.session.commit()


def test_package_and_service_revenue_combined(app, client, customer_auth_headers, admin_auth_headers, package_data):
    activate(client, customer_auth_headers, admin_auth_headers, package_data)
    chart, stats = _summary(client, admin_auth_headers)
    assert chart['total_revenue'] == 1200000
    assert chart['package_revenue'] == 1200000 and chart['service_revenue'] == 0
    assert stats['today']['revenue'] == 1200000
    assert stats['month']['revenue'] == 1200000

    _pay_service(app, package_data['customer'])
    chart, stats = _summary(client, admin_auth_headers)
    assert chart['total_revenue'] == 1500000
    assert chart['service_revenue'] == 300000 and chart['package_revenue'] == 1200000
    assert chart['chart_data']['datasets'][0]['data'] == [1500000]
    assert stats['today']['revenue'] == 1500000
    assert stats['today']['service_revenue'] == 300000
    assert stats['today']['package_revenue'] == 1200000
    assert stats['month']['revenue'] == 1500000


def test_repeated_confirmation_does_not_double_revenue(app, client, customer_auth_headers, admin_auth_headers, package_data):
    p = purchase(client, customer_auth_headers, package_data)
    url = f"/api/admin/packages/purchases/{p['id']}/confirm-payment"
    for _ in range(3):
        r = client.post(url, headers=admin_auth_headers, json={'amount': 1200000})
        assert r.status_code == 200, r.json
    chart, stats = _summary(client, admin_auth_headers)
    assert chart['total_revenue'] == 1200000
    assert stats['today']['revenue'] == 1200000


def test_package_session_usage_is_not_revenue_again(app, client, customer_auth_headers, admin_auth_headers, package_data):
    record = activate(client, customer_auth_headers, admin_auth_headers, package_data)
    r = client.post('/api/appointments/create', headers=customer_auth_headers, json={
        'madv_list': [package_data['service']],
        'ngaygio': package_data['slot'].strftime('%Y-%m-%dT%H:%M'),
        'package_usages': [dict(mathe=record, madv=package_data['service'], quantity=1)]})
    assert r.status_code == 201, r.json
    malh = r.json['appointment']['malh']
    for _ in range(2):
        assert client.post(f'/api/admin/appointments/{malh}/complete', headers=admin_auth_headers).status_code in (200, 400, 409)
    with app.app_context():
        assert ThanhToan.query.filter(ThanhToan.sotien > 0).count() == 0
    chart, _ = _summary(client, admin_auth_headers)
    assert chart['total_revenue'] == 1200000


def test_pending_and_points_purchases_excluded(app, client, customer_auth_headers, admin_auth_headers, package_data):
    purchase(client, customer_auth_headers, package_data)  # pending, not paid
    with app.app_context():
        paid = GoiDichVuPurchase.query.first()
        start = package_service.local_now() - timedelta(days=1)
        end = package_service.local_now() + timedelta(days=1)
        assert analytics_service.revenue_breakdown(start, end)['total'] == 0
        # Gói trả hết bằng điểm: thực thu 0đ không được tính.
        paid.status, paid.paid_at, paid.payable_amount = 'paid', package_service.local_now(), 0
        db.session.commit()
        assert analytics_service.revenue_breakdown(start, end)['total'] == 0


def test_average_invoice_includes_package_transactions(app, client, customer_auth_headers, admin_auth_headers, package_data):
    activate(client, customer_auth_headers, admin_auth_headers, package_data)
    _pay_service(app, package_data['customer'])
    today = _today()
    res = client.get(f'/api/analytics/average-invoice?from={today}&to={today}', headers=admin_auth_headers).json
    assert res['total_revenue'] == 1500000
    assert res['total_transactions'] == 2
    assert res['average_invoice'] == 750000


def test_summary_uses_one_range_for_all_kpis(app, client, customer_auth_headers, admin_auth_headers, package_data):
    activate(client, customer_auth_headers, admin_auth_headers, package_data)
    _pay_service(app, package_data['customer'])
    today = _today()
    res = client.get(f'/api/analytics/summary?from={today}&to={today}', headers=admin_auth_headers).json
    assert res['revenue'] == dict(total=1500000, service=300000, package=1200000,
                                  transactions=2, average_transaction=750000)
    assert set(res['appointments']) == {'total', 'completed', 'cancelled', 'cancel_rate'}
    # Khoảng ngày trước đó không chứa giao dịch nào.
    old = '2020-01-01'
    res = client.get(f'/api/analytics/summary?from={old}&to={old}', headers=admin_auth_headers).json
    assert res['revenue']['total'] == 0 and res['revenue']['average_transaction'] == 0


def test_summary_requires_manager(client, customer_auth_headers, staff_auth_headers):
    assert client.get('/api/analytics/summary', headers=customer_auth_headers).status_code in (401, 403)
    assert client.get('/api/analytics/summary', headers=staff_auth_headers).status_code == 403


def test_summary_rejects_bad_date(client, admin_auth_headers):
    assert client.get('/api/analytics/summary?from=abc', headers=admin_auth_headers).status_code == 400

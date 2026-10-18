"""One employee income page; previous monthly aggregates cannot duplicate GPS payroll."""
from decimal import Decimal
import pytest
from app.extensions import db
from app.models import Luong


@pytest.fixture
def salary_history(app):
    app.config.update(EMPLOYEE_PORTAL_ENABLED=True, PAYROLL_V2_ENABLED=True, PAYROLL_V2_CUTOVER_DATE='2026-10-01')
    with app.app_context():
        previous = Luong(manv=app.config['TEST_STAFF_ID'], nam=2026, thang=9,
            luongcoban=100000, hoahong=5000, thuong=10000, khautru=2000, tongluong=113000)
        overlap = Luong(manv=app.config['TEST_STAFF_ID'], nam=2026, thang=10,
            luongcoban=2660000, hoahong=0, thuong=0, khautru=0, tongluong=2660000)
        other = Luong(manv=app.config['TEST_STAFF2_ID'], nam=2026, thang=9,
            luongcoban=999000, hoahong=0, thuong=0, khautru=0, tongluong=999000)
        db.session.add_all([previous, overlap, other]); db.session.commit()
        return dict(previous=previous.maluong, overlap=overlap.maluong)


def test_old_page_redirects_to_single_income_page(app, client, salary_history):
    response = client.get('/admin/my-salary')
    assert response.status_code == 302 and response.headers['Location'] == '/employee/income'
    assert client.get('/admin/my-salary', follow_redirects=True).status_code == 200
    app.config['PAYROLL_V2_ENABLED'] = False
    assert client.get('/admin/my-salary').status_code == 200


def test_history_excludes_overlap_and_other_staff_without_deleting_data(app, client, staff_auth_headers, salary_history):
    response = client.get('/api/profile/my-salary?manv=' + str(app.config['TEST_STAFF2_ID']), headers=staff_auth_headers)
    assert response.status_code == 200
    assert response.json['gps_payroll_enabled'] and response.json['cutover_date'] == '2026-10-01'
    assert response.json['income_url'] == '/employee/income'
    assert [item['maluong'] for item in response.json['salaries']] == [salary_history['previous']]
    assert Decimal(response.json['salaries'][0]['tongluong']) == 113000
    summary = client.get('/api/me/income-summary', headers=staff_auth_headers)
    assert summary.status_code == 200 and Decimal(summary.json['approved_earnings']) == 0
    with app.app_context():
        assert Luong.query.count() == 3
        assert db.session.get(Luong, salary_history['overlap']).tongluong == 2660000


def test_partial_cutover_month_cannot_double_count_monthly_aggregate(app, client, staff_auth_headers, salary_history):
    app.config['PAYROLL_V2_CUTOVER_DATE'] = '2026-10-15'
    rows = client.get('/api/profile/my-salary', headers=staff_auth_headers).json['salaries']
    assert [item['maluong'] for item in rows] == [salary_history['previous']]


def test_missing_cutover_does_not_show_ambiguous_legacy_salary(app, client, staff_auth_headers, salary_history):
    app.config['PAYROLL_V2_CUTOVER_DATE'] = ''
    response = client.get('/api/profile/my-salary', headers=staff_auth_headers)
    assert response.status_code == 200 and response.json['salaries'] == []


def test_legacy_mode_keeps_previous_employee_salary_contract(app, client, staff_auth_headers, salary_history):
    app.config['PAYROLL_V2_ENABLED'] = False
    response = client.get('/api/profile/my-salary', headers=staff_auth_headers)
    assert response.status_code == 200 and not response.json['gps_payroll_enabled']
    assert {item['maluong'] for item in response.json['salaries']} == set(salary_history.values())
    assert all('luongcoban' in item and 'tongluong' in item for item in response.json['salaries'])


def test_customer_and_anonymous_cannot_read_employee_salary(client, customer_auth_headers, salary_history):
    assert client.get('/api/profile/my-salary').status_code == 401
    assert client.get('/api/profile/my-salary', headers=customer_auth_headers).status_code == 403

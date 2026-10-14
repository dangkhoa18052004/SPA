from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import (DanhMucDichVu, DichVu, KhachHang, CustomerBehavior, LichHen,
    ChiTietLichHen, HoaDon, ChiTietHoaDon, DanhGia, DanhGiaDichVu,
    CaLam, nhanvien_calam)
from app.services.recommendation_service import Ranking, record_business_event, rank_services_for_customer, get_related_recommendations
from app.services.package_service import save_package, create_purchase, confirm_purchase, local_now


@pytest.fixture
def catalog(app):
    with app.app_context():
        massage = DanhMucDichVu(name='Massage', slug='massage')
        acne = DanhMucDichVu(name='Da mụn', slug='acne')
        db.session.add_all([massage, acne]); db.session.flush()
        # Deliberately misleading names prove category FK, not keywords, drives matching.
        services = [DichVu(tendv='Dịch vụ A', gia=100000, thoiluong=30, category_id=massage.id),
                    DichVu(tendv='Dịch vụ B', gia=150000, thoiluong=30, category_id=massage.id),
                    DichVu(tendv='Massage trong tên nhưng thuộc acne', gia=200000, thoiluong=30, category_id=acne.id),
                    DichVu(tendv='Dịch vụ cũ chưa phân loại', gia=200000, thoiluong=30)]
        customer = KhachHang(hoten='B', taikhoan='b', matkhau='x', trangthai='active')
        db.session.add_all([*services, customer]); db.session.flush()
        packages = [save_package(dict(tengoi='Gói A', giagoi=200000, items=[dict(madv=s.madv, total_sessions=2) for s in services[:2]])),
                    save_package(dict(tengoi='Gói B', giagoi=200000, items=[dict(madv=services[2].madv, total_sessions=2)]))]
        db.session.commit()
        return dict(a=app.config['TEST_CUSTOMER_ID'], b=customer.makh,
                    services=[s.madv for s in services], packages=[p.magoi for p in packages])


def behavior(customer, sid, action='select_service', age=0, count=1):
    for i in range(count):
        db.session.add(CustomerBehavior(makh=customer, madv=sid, action=action,
            created_at=datetime.utcnow() - timedelta(days=age, seconds=i), source='frontend', dedupe_key=str(uuid4())))
    db.session.commit()


def appointment(app, customer, sid, status='completed'):
    apt = LichHen(makh=customer, manv=app.config['TEST_STAFF_ID'], ngaygio=local_now(), trangthai=status)
    db.session.add(apt); db.session.flush()
    db.session.add(ChiTietLichHen(malh=apt.malh, madv=sid)); db.session.commit()
    return apt


def test_two_customers_receive_different_category_rankings(app, catalog):
    with app.app_context():
        m1, m2, acne, _ = catalog['services']
        behavior(catalog['a'], m1, count=10)
        behavior(catalog['b'], acne, count=10)
        a, b = Ranking(catalog['a']), Ranking(catalog['b'])
        assert a.scores[m1] > a.scores[acne]
        assert a.scores[m2] > a.scores[acne]
        assert b.scores[acne] > b.scores[m1]
        assert a.recommend_services()[0]['madv'] != b.recommend_services()[0]['madv']
        assert a.category['massage'] > a.category['acne']


def test_cold_start_popularity_and_anonymous_never_write(app, client, catalog):
    with app.app_context():
        appointment(app, catalog['a'], catalog['services'][2])
        result = Ranking(catalog['b'])
        assert result.strategy == 'popular'
        assert result.recommend_services()[0]['madv'] == catalog['services'][2]
    response = client.get('/api/recommendations')
    assert response.status_code == 200
    assert response.json['strategy'] == 'popular'
    assert response.json['services'] and response.json['packages']
    assert 'no-store' in response.headers['Cache-Control']
    assert all('score' not in row for row in response.json['services'] + response.json['packages'])
    assert client.post('/api/recommendations/events', json={'action':'view_service', 'madv':catalog['services'][0]}).status_code == 401
    with app.app_context():
        assert CustomerBehavior.query.count() == 0


def test_package_content_matching_and_sale_filters(app, catalog):
    with app.app_context():
        behavior(catalog['a'], catalog['services'][0])
        assert Ranking(catalog['a']).recommend_packages()[0]['magoi'] == catalog['packages'][0]
        from app.models import GoiDichVu
        p = db.session.get(GoiDichVu, catalog['packages'][0]); p.customer_sale_enabled = False
        db.session.commit()
        assert p.magoi not in [r['magoi'] for r in Ranking(catalog['a']).recommend_packages()]
        p.customer_sale_enabled = True; p.active = False; db.session.commit()
        assert p.magoi not in [r['magoi'] for r in Ranking(catalog['a']).recommend_packages()]
        p.active = True
        db.session.get(DichVu, catalog['services'][1]).active = False; db.session.commit()
        ranking = Ranking(catalog['a'])
        assert catalog['services'][1] not in [r['madv'] for r in ranking.recommend_services()]
        assert p.magoi not in [r['magoi'] for r in ranking.recommend_packages()]


def test_packages_hidden_when_online_payment_is_unavailable(app, catalog):
    with app.app_context():
        app.config.update(PACKAGE_CUSTOMER_CASH_ENABLED=False, VIETQR_BANK_ID='', VIETQR_ACCOUNT_NO='', VIETQR_ACCOUNT_NAME='')
        assert Ranking(catalog['a']).recommend_packages() == []


@pytest.mark.parametrize('linked', [True, False])
def test_low_rating_reduces_service_and_related_category(app, catalog, linked):
    with app.app_context():
        sid, similar, _, _ = catalog['services']
        apt = appointment(app, catalog['a'], sid)
        before = Ranking(catalog['a']).scores
        review = DanhGia(makh=catalog['a'], malh=apt.malh, rating=1)
        db.session.add(review); db.session.flush()
        if linked: db.session.add(DanhGiaDichVu(madg=review.madg, madv=sid))
        db.session.commit()
        after = Ranking(catalog['a']).scores
        assert after[sid] < before[sid]
        assert after[similar] < before[similar]


def test_recent_interest_overrides_old_history(app, catalog):
    with app.app_context():
        massage, _, acne, _ = catalog['services']
        behavior(catalog['a'], massage, age=365, count=100)
        behavior(catalog['a'], acne, age=2)
        rank = Ranking(catalog['a'])
        assert rank.scores[acne] > rank.scores[massage]
        assert rank.category['acne'] > rank.category['massage']


def test_reloads_are_deduplicated_and_daily_contribution_capped(app, client, catalog, customer_auth_headers):
    payload = {'action':'view_service', 'madv':catalog['services'][0]}
    first = client.post('/api/recommendations/events', json=payload, headers=customer_auth_headers)
    assert first.status_code == 201 and first.json['recorded']
    for _ in range(5):
        assert client.post('/api/recommendations/events', json=payload, headers=customer_auth_headers).json['recorded'] is False
    with app.app_context():
        assert CustomerBehavior.query.count() == 1
        behavior(catalog['b'], catalog['services'][0], 'view_service', count=100)
        behavior(catalog['a'], catalog['services'][0], 'view_service', count=2)
        a, b = Ranking(catalog['a']), Ranking(catalog['b'])
        assert a.behavior[catalog['services'][0]] == pytest.approx(b.behavior[catalog['services'][0]])


@pytest.mark.parametrize('payload', [None, [], 'x', {}, {'action':[]},
    {'action':'view_service','madv':True}, {'action':'view_service','madv':1.1},
    {'action':'view_service','madv':'1'}, {'action':'view_service','madv':-1},
    {'action':'view_service','madv':2**40}, {'action':'unknown','madv':1},
    {'action':'book_service','madv':1}, {'action':'complete_service','madv':1},
    {'action':'purchase_package','magoi':1}, {'action':'view_service','madv':1,'makh':9},
    {'action':'view_service','madv':1,'score':100}, {'action':'view_service','madv':1,'magoi':1}])
def test_event_validation(client, customer_auth_headers, payload):
    assert client.post('/api/recommendations/events', json=payload, headers=customer_auth_headers).status_code == 400


def test_tracking_auth_ownership_and_unknown_target(app, client, catalog, customer_auth_headers, staff_auth_headers):
    payload = dict(action='view_service', madv=catalog['services'][0])
    assert client.post('/api/recommendations/events', json=payload, headers=staff_auth_headers).status_code == 403
    assert client.post('/api/recommendations/events', json=dict(action='view_service', madv=9999), headers=customer_auth_headers).status_code == 404
    assert client.post('/api/recommendations/events', data='{', content_type='application/json', headers=customer_auth_headers).status_code == 400
    assert client.post('/api/recommendations/events', json=payload, headers=customer_auth_headers).status_code == 201
    with app.app_context():
        assert CustomerBehavior.query.one().makh == catalog['a']
        db.session.get(KhachHang, catalog['a']).trangthai='inactive'; db.session.commit()
    assert client.post('/api/recommendations/events', json=payload, headers=customer_auth_headers).status_code == 403
    assert client.get('/api/recommendations', headers=customer_auth_headers).status_code == 403


def test_rate_limit(app, client, catalog, customer_auth_headers):
    with app.app_context():
        behavior(catalog['a'], catalog['services'][0], count=60)
    r = client.post('/api/recommendations/events', json=dict(action='view_service', madv=catalog['services'][2]), headers=customer_auth_headers)
    assert r.status_code == 429 and r.headers['Retry-After'] == '60'


def test_history_invoice_and_business_event_do_not_double_count(app, catalog):
    with app.app_context():
        sid = catalog['services'][0]
        apt = appointment(app, catalog['a'], sid)
        before = Ranking(catalog['a']).booking[sid]
        record_business_event(catalog['a'], 'book_service', apt.malh, madv=sid)
        record_business_event(catalog['a'], 'complete_service', apt.malh, madv=sid)
        invoice = HoaDon(makh=catalog['a'], manv=app.config['TEST_STAFF_ID'], malh=apt.malh,
                         tongtien=100000, trangthai='Đã thanh toán')
        db.session.add(invoice); db.session.flush()
        db.session.add(ChiTietHoaDon(mahd=invoice.mahd, madv=sid, dongia=100000, thanhtien=100000))
        db.session.commit()
        assert Ranking(catalog['a']).booking[sid] == pytest.approx(before)
        invoice.malh = None; db.session.commit()
        assert Ranking(catalog['a']).booking[sid] > before
        invoice.trangthai = 'Chưa thanh toán'; apt.trangthai = 'cancelled'; db.session.commit()
        assert Ranking(catalog['a']).booking[sid] == 0


def test_paid_package_snapshot_and_treatment_are_counted_once(app, catalog):
    with app.app_context():
        purchase = create_purchase(catalog['packages'][0], catalog['a'], 'cash')
        purchase, record, _ = confirm_purchase(purchase.id, purchase.amount)
        db.session.commit()
        ranking = Ranking(catalog['a'])
        assert ranking.strategy == 'personalized'
        assert catalog['packages'][0] in ranking.owned_packages
        assert ranking.booking[catalog['services'][0]] == pytest.approx(5, abs=.05)
        assert CustomerBehavior.query.filter_by(action='purchase_package').count() == 1
        confirm_purchase(purchase.id, purchase.amount); db.session.commit()
        assert CustomerBehavior.query.filter_by(action='purchase_package').count() == 1
        # Old ledger without a purchase snapshot still supplies a profile.
        purchase.snapshot_json = {}; db.session.commit()
        assert Ranking(catalog['a']).booking[catalog['services'][0]] == pytest.approx(5, abs=.05)


def test_public_response_is_personalized_without_gemini(app, client, catalog, customer_auth_headers):
    with app.app_context(): behavior(catalog['a'], catalog['services'][0])
    response = client.get('/api/recommendations', headers=customer_auth_headers)
    assert response.status_code == 200
    assert response.json['strategy'] == 'personalized'
    assert response.json['services'][0]['madv'] == catalog['services'][0]
    assert response.json['packages'][0]['magoi'] == catalog['packages'][0]


def test_query_count_does_not_grow_with_catalog(app, catalog):
    with app.app_context():
        def count_queries():
            queries = []
            def capture(*args): queries.append(args[2])
            event.listen(db.engine, 'before_cursor_execute', capture)
            try: Ranking(catalog['a']).response()
            finally: event.remove(db.engine, 'before_cursor_execute', capture)
            return len(queries)
        small = count_queries()
        for i in range(20):
            service = DichVu(tendv=f'Thêm {i}', gia=100000, thoiluong=30)
            db.session.add(service); db.session.flush()
            save_package(dict(tengoi=f'Gói {i}', giagoi=100000, items=[dict(madv=service.madv, total_sessions=2)]))
        db.session.commit(); db.session.expire_all()
        assert count_queries() <= small + 1


def test_admin_category_assignment_and_permissions(app, client, catalog, admin_auth_headers, customer_auth_headers):
    url = f"/api/admin/services/{catalog['services'][3]}"
    categories = client.get('/api/admin/service-categories', headers=admin_auth_headers).json['categories']
    category_id = categories[0]['id']
    assert client.put(url, data={'category_id':str(category_id)}, headers=admin_auth_headers).status_code == 200
    assert client.put(url, data={'category_id':'99999'}, headers=admin_auth_headers).status_code == 400
    assert client.put(url, data={'category_id':str(category_id)}, headers=customer_auth_headers).status_code == 403
    with app.app_context(): assert db.session.get(DichVu, catalog['services'][3]).category_id == category_id
    assert client.put(url, data={'category_id':''}, headers=admin_auth_headers).status_code == 200


def test_recommendation_database_error_is_safe(app, client, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    def broken(*args, **kwargs): raise SQLAlchemyError('private database connection details')
    monkeypatch.setattr('app.routes.recommendation_bp.Ranking', broken)
    result = client.get('/api/recommendations')
    assert result.status_code == 503
    assert 'private database' not in result.get_data(as_text=True)


def test_booking_and_completion_events_are_atomic_and_idempotent(app, client, catalog, customer_auth_headers):
    from datetime import time
    from app.services import appointment_service
    with app.app_context():
        day = (local_now() + timedelta(days=2)).date()
        shift = CaLam(ngay=day, giobatdau=time(9), gioketthuc=time(17))
        db.session.add(shift); db.session.flush()
        db.session.execute(nhanvien_calam.insert().values(manv=app.config['TEST_STAFF_ID'], maca=shift.maca))
        db.session.commit()
    payload = dict(madv_list=catalog['services'][:2], ngaygio=f'{day}T10:00:00', manv=app.config['TEST_STAFF_ID'])
    result = client.post('/api/appointments/create', json=payload, headers=customer_auth_headers)
    assert result.status_code == 201
    with app.app_context():
        apt = LichHen.query.one()
        assert CustomerBehavior.query.filter_by(action='book_service').count() == 2
        appointment_service.update_appointment_status(apt.malh, 'completed', user_id=app.config['TEST_ADMIN_ID'], role='admin')
        appointment_service.update_appointment_status(apt.malh, 'completed', user_id=app.config['TEST_ADMIN_ID'], role='admin')
        assert CustomerBehavior.query.filter_by(action='complete_service').count() == 2
        assert all(e.source == 'backend' for e in CustomerBehavior.query.all())
        record_business_event(catalog['a'], 'book_service', 'rollback', madv=catalog['services'][0])
        db.session.flush(); db.session.rollback()
        assert CustomerBehavior.query.filter(CustomerBehavior.dedupe_key.like('%rollback%')).count() == 0


def test_catalog_personalizes_entire_list_for_each_customer(app, client, catalog, customer_auth_headers):
    from flask_jwt_extended import create_access_token
    with app.app_context():
        massage, similar, acne, legacy = catalog['services']
        appointment(app, catalog['a'], massage)
        behavior(catalog['b'], acne, count=3)
        token_b = create_access_token(identity=f"customer:{catalog['b']}")
    a = client.get('/api/services', headers=customer_auth_headers)
    b = client.get('/api/services', headers={'Authorization': f'Bearer {token_b}'})
    assert a.status_code == b.status_code == 200
    ids_a = [s['madv'] for s in a.json['services']]
    ids_b = [s['madv'] for s in b.json['services']]
    assert ids_a.index(massage) < ids_a.index(acne) and ids_a.index(similar) < ids_a.index(acne)
    assert ids_b[0] == acne
    assert set(ids_a) == set(ids_b) == set(catalog['services'])
    assert len(ids_a) == len(set(ids_a)) == 4
    assert all('score' not in row for row in a.json['services'])
    assert 'no-store' in a.headers['Cache-Control'] and 'Authorization' in a.headers['Vary']
    # A query string cannot select another customer's profile.
    assert client.get(f"/api/services?customer_id={catalog['b']}", headers=customer_auth_headers).json == a.json


def test_catalog_anonymous_fallback_contains_all_services(app, client, catalog):
    with app.app_context():
        appointment(app, catalog['a'], catalog['services'][2])
    response = client.get('/api/services')
    assert response.status_code == 200
    assert response.json['total'] == 4
    assert response.json['services'][0]['madv'] == catalog['services'][2]
    with app.app_context():
        assert CustomerBehavior.query.count() == 0


def test_catalog_filters_candidates_before_personalized_ranking(app, client, catalog, customer_auth_headers):
    with app.app_context():
        behavior(catalog['a'], catalog['services'][1], count=3)
    data = client.get('/api/services?category=massage', headers=customer_auth_headers).json
    assert [s['madv'] for s in data['services']] == catalog['services'][1::-1]
    assert all(s['category_slug'] == 'massage' for s in data['services'])
    assert client.get('/api/services?category=hair', headers=customer_auth_headers).json['services'] == []


def test_catalog_search_limits_candidates_and_escapes_wildcards(app, client, catalog, customer_auth_headers):
    with app.app_context():
        db.session.get(DichVu, catalog['services'][2]).mota = 'Chăm sóc da'
        db.session.get(DichVu, catalog['services'][3]).mota = 'Phục hồi da'
        db.session.commit()
        behavior(catalog['a'], catalog['services'][3])
    data = client.get('/api/services?search=da', headers=customer_auth_headers).json
    assert [s['madv'] for s in data['services']] == [catalog['services'][3], catalog['services'][2]]
    assert all('da' in (s['tendv'] + ' ' + s['mota']).lower() for s in data['services'])
    assert client.get('/api/services?search=da&category=massage', headers=customer_auth_headers).json['services'] == []
    assert client.get('/api/services?search=%25', headers=customer_auth_headers).json['services'] == []


@pytest.mark.parametrize('sort', ['price-asc', 'price-desc', 'name-asc', 'name-desc'])
def test_catalog_manual_sort_overrides_personalization(app, client, catalog, customer_auth_headers, sort):
    with app.app_context():
        behavior(catalog['a'], catalog['services'][1], count=3)
    response = client.get('/api/services?category=massage&sort=' + sort, headers=customer_auth_headers)
    rows = response.json['services']
    assert len(rows) == 2
    values = [float(s['gia']) if sort.startswith('price') else s['tendv'].casefold() for s in rows]
    assert values == sorted(values, reverse=sort.endswith('desc'))
    default = client.get('/api/services?category=massage', headers=customer_auth_headers).json
    assert default['services'][0]['madv'] == catalog['services'][1]


def test_candidate_rank_preserves_unique_active_candidates(app, catalog):
    with app.app_context():
        services = [db.session.get(DichVu, sid) for sid in catalog['services']]
        services[-1].active = False
        db.session.commit()
        behavior(catalog['a'], services[1].madv)
        result = rank_services_for_customer(catalog['a'], services + services)
        assert len(result) == 3 and result[0].madv == services[1].madv


def test_popularity_cannot_override_a_positive_category_preference(app, catalog):
    with app.app_context():
        massage, similar, acne, _ = catalog['services']
        behavior(catalog['a'], massage, 'view_service')
        for _ in range(6):
            appointment(app, catalog['b'], acne)
        rank = Ranking(catalog['a'])
        assert rank.popularity[acne] > rank.popularity[similar]
        ids = [s.madv for s in rank.rank_services(rank.services.values())]
        assert ids.index(similar) < ids.index(acne)


def test_detail_context_precedes_personal_history_and_excludes_current(app, client, catalog, customer_auth_headers):
    with app.app_context():
        current, same_group, unrelated, _ = catalog['services']
        appointment(app, catalog['a'], unrelated)
        behavior(catalog['a'], unrelated, count=3)
        matching_group_package = save_package(dict(tengoi='Cùng nhóm', giagoi=200000,
            items=[dict(madv=same_group, total_sessions=2)]))
        db.session.commit()
        group_package_id = matching_group_package.magoi
        # Even an owned current-service package keeps its context priority.
        rank = Ranking(catalog['a'])
        rank.owned_packages.add(catalog['packages'][0])
        assert rank.related(current)['items'][0]['magoi'] == catalog['packages'][0]
    response = client.get(f'/api/recommendations/related/{current}', headers=customer_auth_headers)
    assert response.status_code == 200
    items = response.json['items']
    services = [r for r in items if r['type'] == 'service']
    packages = [r for r in items if r['type'] == 'package']
    assert services[0]['madv'] == same_group
    assert current not in [r['madv'] for r in services]
    assert [r['magoi'] for r in packages] == [catalog['packages'][0], group_package_id]
    assert items[0]['type'] == 'package' and items[0]['magoi'] == catalog['packages'][0]
    assert len(services) <= 3 and len(packages) <= 2
    assert all('score' not in row for row in items)
    assert 'no-store' in response.headers['Cache-Control']
    anonymous = client.get(f'/api/recommendations/related/{current}')
    assert anonymous.status_code == 200 and anonymous.json['items'][0]['magoi'] == catalog['packages'][0]


@pytest.mark.parametrize('hidden_reason', ['inactive', 'not_for_sale', 'inactive_service', 'empty'])
def test_detail_excludes_unsellable_packages(app, catalog, hidden_reason):
    from app.models import GoiDichVu
    with app.app_context():
        package = db.session.get(GoiDichVu, catalog['packages'][0])
        if hidden_reason == 'inactive':
            package.active = False
        elif hidden_reason == 'not_for_sale':
            package.customer_sale_enabled = False
        elif hidden_reason == 'inactive_service':
            db.session.get(DichVu, catalog['services'][1]).active = False
        else:
            package.items.clear()
        db.session.commit()
        result = get_related_recommendations(catalog['a'], catalog['services'][0])
        assert package.magoi not in [r['magoi'] for r in result['items'] if r['type'] == 'package']
        if hidden_reason == 'inactive_service':
            assert catalog['services'][1] not in [r['madv'] for r in result['items'] if r['type'] == 'service']


def test_detail_payment_unavailable_and_inactive_service(app, client, catalog):
    with app.app_context():
        app.config.update(PACKAGE_CUSTOMER_CASH_ENABLED=False, VIETQR_BANK_ID='', VIETQR_ACCOUNT_NO='', VIETQR_ACCOUNT_NAME='')
    data = client.get(f"/api/recommendations/related/{catalog['services'][0]}").json
    assert all(r['type'] == 'service' for r in data['items'])
    with app.app_context():
        db.session.get(DichVu, catalog['services'][0]).active = False
        db.session.commit()
    assert client.get(f"/api/recommendations/related/{catalog['services'][0]}").status_code == 404
    assert client.get(f"/api/services/{catalog['services'][0]}").status_code == 404
    assert catalog['services'][0] not in [s['madv'] for s in client.get('/api/services').json['services']]
    assert client.get('/api/recommendations/related/999999').status_code == 404


def test_catalog_template_has_no_separate_recommendation_sections(client):
    html = client.get('/services').get_data(as_text=True)
    assert 'servicesGrid' in html and 'filter-categories' in html and 'sortSelect' in html
    assert 'Dịch vụ dành cho bạn' not in html and 'Gói phù hợp với bạn' not in html
    assert 'data-recommended-services' not in html and 'data-recommended-packages' not in html
    detail = client.get('/services/1').get_data(as_text=True)
    assert detail.count('Có thể bạn cũng quan tâm') == 1
    assert 'data-related-items' in detail and 'relatedServicesGrid' not in detail

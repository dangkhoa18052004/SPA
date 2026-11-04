"""Approved mappings, admin drafts, customer cache and database constraints (all Gemini calls mocked)."""
import importlib.util
import json
import threading
import time

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import DichVu, DanhMucDichVu, NhanVien
from app.skin_models import SkinServiceMap
from app.services import ai_service, skin_service_map_service as maps, skin_recommendation_service as recs
from app.services.skin_analysis_service import TYPE_LABELS
from test_skin_analysis import enabled, fake_ai, post, suggest, ai_result
from test_loyalty_migration import migration_engine

API = '/api/admin/skin-service-map'


def test_admin_page_uses_care_react_shell_and_keeps_legacy_override(app, client):
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_CARE_REACT_ENABLED=True)
    page = client.get('/admin/skin-service-map')
    assert page.status_code == 200 and b'portal/' in page.data
    assert b'id="skin-map-groups"' not in page.data
    legacy = client.get('/admin/skin-service-map?ui=legacy')
    assert legacy.status_code == 200 and b'id="skin-map-groups"' in legacy.data
    app.config['ADMIN_CARE_REACT_ENABLED'] = False
    assert b'id="skin-map-groups"' in client.get('/admin/skin-service-map').data


def test_mapping_migration_on_postgresql_and_sqlite(migration_engine):
    spec = importlib.util.spec_from_file_location('skin_map_migration', 'migrations/versions/20261024_0026_skin_service_map.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with migration_engine.begin() as connection:
        connection.execute(text('CREATE TABLE dichvu (madv INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)'))
        connection.execute(text('INSERT INTO dichvu VALUES (1)'))
        connection.execute(text('INSERT INTO nhanvien VALUES (1)'))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            connection.execute(text("INSERT INTO skin_service_map (id,type_code,madv,approved_by,approved_at) VALUES (1,'papule',1,1,CURRENT_TIMESTAMP)"))
            assert connection.execute(text('SELECT COUNT(*) FROM skin_service_map')).scalar() == 1
            assert connection.execute(text('SELECT COUNT(*) FROM dichvu')).scalar() == 1
            module.downgrade()
        assert not inspect(connection).has_table('skin_service_map')
        assert connection.execute(text('SELECT COUNT(*) FROM dichvu')).scalar() == 1


@pytest.fixture()
def catalog(app):
    maps.reset()
    recs.reset()
    with app.app_context():
        category = DanhMucDichVu(name='Chăm sóc da', slug='map-skin')
        hidden = DanhMucDichVu(name='Danh mục ẩn', slug='map-hidden', active=False)
        db.session.add_all([category, hidden])
        db.session.flush()
        rows = [DichVu(tendv=f'Làm sạch da {i}', mota='Mô tả ' * 100, gia=987654,
                       active=True, category_id=category.id if i != 1 else hidden.id) for i in range(12)]
        rows.append(DichVu(tendv='Dịch vụ ngừng', gia=654321, active=False))
        db.session.add_all(rows)
        db.session.commit()
        ids = [s.madv for s in rows]
    app.config['SKIN_SERVICE_MAP'] = {'papule': [ids[0]], 'alien': [ids[1]]}
    yield ids
    maps.reset()
    recs.reset()


@pytest.fixture()
def gemini(monkeypatch):
    def fake(payload):
        fake.calls.append(payload)
        if isinstance(fake.reply, Exception):
            raise fake.reply
        value = fake.reply if isinstance(fake.reply, str) else json.dumps(fake.reply)
        return {'candidates': [{'content': {'parts': [{'text': value}]}}]}
    fake.calls = []
    fake.reply = {'assignments': []}
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    return fake


@pytest.mark.parametrize('role,status', [('anonymous', 401), ('customer', 403), ('staff', 403),
                                       ('letan', 403), ('admin', 200), ('manager', 200)])
def test_roles_all_endpoints(app, client, catalog, gemini, role, status):
    headers = {}
    if role != 'anonymous':
        with app.app_context():
            if role == 'customer':
                identity = f"customer:{app.config['TEST_CUSTOMER_ID']}"
            else:
                row = db.session.get(NhanVien, app.config['TEST_ADMIN_ID'])
                row.role = role
                db.session.commit()
                identity = f'staff:{row.manv}'
            headers = {'Authorization': 'Bearer ' + create_access_token(identity=identity)}
    for method, url, kwargs in [('get', API, {}), ('post', API + '/proposal', {}),
                                ('put', API, {'json': {'map': {'papule': [catalog[0]]}}})]:
        response = getattr(client, method)(url, headers=headers, **kwargs)
        assert response.status_code == status
        assert response.json['success'] is (status == 200)


def test_db_precedence_sorted_inactive_and_env_fallback(app, catalog):
    a, b, inactive = catalog[0], catalog[1], catalog[-1]
    with app.app_context():
        assert recs.service_map() == {'papule': [a]}
        assert maps.current()['source'] == 'env'
        db.session.add_all([SkinServiceMap(type_code='papule', madv=b),
                            SkinServiceMap(type_code='papule', madv=inactive)])
        db.session.commit()
        assert recs.service_map() == {'papule': [b, inactive]}
        services, allowed, _ = recs.candidates([{'type': 'papule'}])
        assert [s.madv for s in services] == [b] and allowed == {b: ['papule']}
        maps.save({}, app.config['TEST_ADMIN_ID'])
        assert recs.service_map() == {'papule': [a]}
        app.config['SKIN_SERVICE_MAP'] = ''
        assert maps.current()['source'] == 'empty'


def test_missing_schema_keeps_explicit_mapping_readable_and_blocks_saving(app, client, catalog, admin_auth_headers):
    with app.app_context():
        SkinServiceMap.__table__.drop(db.engine)
        assert recs.service_map() == {'papule': [catalog[0]]}
        assert maps.current()['schema_ready'] is False
        assert db.session.execute(text('SELECT 1')).scalar() == 1
    loaded = client.get(API, headers=admin_auth_headers)
    assert loaded.status_code == 200 and loaded.json['schema_ready'] is False
    saved = client.put(API, headers=admin_auth_headers, json={'map': {'papule': [catalog[0]]}})
    assert saved.status_code == 503 and saved.json['code'] == 'schema_not_ready'


def test_missing_schema_without_approved_mapping_does_not_invent_services(enabled, client, catalog, fake_ai, customer_auth_headers, gemini):
    fake_ai.result = ai_result()
    analysis = post(client, customer_auth_headers).json['data']['id']
    with enabled.app_context():
        SkinServiceMap.__table__.drop(db.engine)
    enabled.config['SKIN_SERVICE_MAP'] = {}
    response = suggest(client, customer_auth_headers, analysis)
    assert response.status_code == 200, response.json
    assert response.json['data']['status'] == 'no_matching_services'
    assert gemini.calls == []


def test_proposal_filters_merges_limits_and_never_saves(app, client, catalog, admin_auth_headers, gemini):
    a, b, c = catalog[:3]
    gemini.reply = {'assignments': [
        {'type_code': 'alien', 'items': [{'service_id': a}]},
        {'type_code': [], 'items': []}, 'garbage',
        {'type_code': 'papule', 'items': [None, {'service_id': True}, {'service_id': 'rác'}, {'service_id': '²'},
            {'service_id': 999999}, {'service_id': catalog[-1]},
            {'service_id': a, 'reason': 'chữa khỏi'}, {'service_id': a, 'reason': 'Trùng'},
            {'service_id': str(b), 'reason': '100%'}, {'service_id': c, 'reason': 'https://example.com'}]},
        {'type_code': 'papule', 'items': [{'service_id': sid, 'reason': 'Có thể tham khảo.'} for sid in catalog[3:8]]},
        {'type_code': 'nodule', 'items': [{'service_id': a, 'reason': '<script>alert(1)</script>'}]},
    ]}
    with app.app_context():
        maps.save({'papule': [a]}, app.config['TEST_ADMIN_ID'])
    response = client.post(API + '/proposal', headers=admin_auth_headers)
    assert response.status_code == 200
    groups = {g['type_code']: g['items'] for g in response.json['assignments']}
    assert set(groups) == set(TYPE_LABELS)
    assert [i['service_id'] for i in groups['papule']] == catalog[:5]
    assert all(i['reason'] == maps.NEUTRAL_REASON for i in groups['papule'][:3])
    assert groups['papule'][0]['approved'] is True and groups['papule'][1]['approved'] is False
    assert groups['papule'][0]['tendv'] == 'Làm sạch da 0'
    assert groups['nodule'][0]['reason'] == maps.NEUTRAL_REASON
    payload = gemini.calls[0]
    facts = json.loads(payload['contents'][0]['parts'][0]['text'].split('DỮ LIỆU: ', 1)[1])
    assert {s['service_id'] for s in facts['services']} == set(catalog[:-1])
    assert all(set(s) == {'service_id', 'name', 'description', 'category'} for s in facts['services'])
    assert all(len(s['description']) <= 400 for s in facts['services'])
    assert facts['services'][1]['category'] is None
    assert facts['types'] == [{'type_code': t, 'name': name} for t, name in TYPE_LABELS.items()]
    for forbidden in ('"gia"', '987654', '654321', 'Bearer', 'customer@example.com', 'admin@example.com', '/uploads'):
        assert forbidden not in json.dumps(payload)
    assert payload['generationConfig']['temperature'] == 0.1
    with app.app_context():
        assert [(r.type_code, r.madv) for r in SkinServiceMap.query.all()] == [('papule', a)]


@pytest.mark.parametrize('reply,status', [('broken JSON', 502), ({}, 502), ({'assignments': None}, 502),
    (ai_service.AINotConfigured('no key'), 503), (ai_service.AIUpstreamError('down'), 502),
    ({'assignments': []}, 200)])
def test_proposal_errors_and_empty(app, client, catalog, admin_auth_headers, gemini, reply, status):
    gemini.reply = reply
    response = client.post(API + '/proposal', headers=admin_auth_headers)
    assert response.status_code == status and not maps._running
    if status == 200:
        assert len(response.json['assignments']) == 5
        assert all(g['items'] == [] for g in response.json['assignments'])
    with app.app_context():
        assert SkinServiceMap.query.count() == 0


def test_no_active_services_skips_gemini(app, client, catalog, admin_auth_headers, gemini):
    with app.app_context():
        DichVu.query.update({'active': False})
        db.session.commit()
    response = client.post(API + '/proposal', headers=admin_auth_headers)
    assert response.status_code == 200 and response.json['message']
    assert len(response.json['assignments']) == 5 and gemini.calls == [] and not maps._calls


def test_real_single_flight_and_call_budget(app, client, catalog, admin_auth_headers, gemini, monkeypatch):
    started, release = threading.Event(), threading.Event()
    original = ai_service.call_gemini
    def blocking(payload):
        started.set()
        assert release.wait(10)
        return original(payload)
    monkeypatch.setattr(ai_service, 'call_gemini', blocking)
    responses = []
    def request():
        with app.test_client() as other:
            responses.append(other.post(API + '/proposal', headers=admin_auth_headers).status_code)
    worker = threading.Thread(target=request)
    worker.start()
    try:
        assert started.wait(10)
        assert client.post(API + '/proposal', headers=admin_auth_headers).status_code == 409
    finally:
        release.set()
        worker.join(10)
    assert responses == [200] and not maps._running
    for _ in range(4):
        assert client.post(API + '/proposal', headers=admin_auth_headers).status_code == 200
    assert client.post(API + '/proposal', headers=admin_auth_headers).status_code == 429
    assert len(gemini.calls) == 5
    maps._calls[app.config['TEST_ADMIN_ID']] = [time.monotonic() - 601] * 5
    assert client.post(API + '/proposal', headers=admin_auth_headers).status_code == 200


@pytest.mark.parametrize('case', ['not_dict', 'unknown_type', 'not_list', 'bool', 'string', 'zero', 'negative',
                                  'float', 'missing', 'inactive', 'too_many'])
def test_invalid_save_keeps_previous_map(app, client, catalog, admin_auth_headers, case):
    a = catalog[0]
    values = {'not_dict': [], 'unknown_type': {'alien': []}, 'not_list': {'papule': a},
              'bool': {'papule': [True]}, 'string': {'papule': [str(a)]}, 'zero': {'papule': [0]},
              'negative': {'papule': [-1]}, 'float': {'papule': [1.5]}, 'missing': {'papule': [999999]},
              'inactive': {'papule': [catalog[-1]]}, 'too_many': {'papule': catalog[:11]}}
    with app.app_context():
        maps.save({'papule': [a]}, app.config['TEST_ADMIN_ID'])
        before = maps.current()
    response = client.put(API, json={'map': values[case]}, headers=admin_auth_headers)
    assert response.status_code == 400 and response.json['message']
    with app.app_context():
        assert maps.current() == before


def test_save_replaces_map_audits_and_empty_falls_back(app, client, catalog, admin_auth_headers):
    a, b = catalog[:2]
    assert client.put(API, json={'map': {'papule': [a]}}, headers=admin_auth_headers).status_code == 200
    response = client.put(API, json={'map': {'nodule': [b, b]}}, headers=admin_auth_headers)
    assert response.status_code == 200 and response.json['map']['papule'] == []
    assert response.json['map']['nodule'] == [b] and response.json['source'] == 'database'
    assert response.json['approved_at'].endswith('Z') and response.json['approved_by_name'] == 'Admin Test'
    with app.app_context():
        assert SkinServiceMap.query.one().approved_by == app.config['TEST_ADMIN_ID']
    response = client.put(API, json={'map': {t: [] for t in TYPE_LABELS}}, headers=admin_auth_headers)
    assert response.json['source'] == 'env' and '.env' in response.json['message']
    assert response.json['map']['papule'] == [a]
    assert client.get(API, headers=admin_auth_headers).json['services'][0]['madv'] == a


def test_save_insert_failure_rolls_back(app, client, catalog, admin_auth_headers):
    with app.app_context():
        maps.save({'papule': [catalog[0]]}, app.config['TEST_ADMIN_ID'])
        before = maps.current()
    def fail(*args):
        raise IntegrityError('simulated insert failure', None, None)
    event.listen(SkinServiceMap, 'before_insert', fail)
    try:
        response = client.put(API, json={'map': {'nodule': [catalog[1]]}}, headers=admin_auth_headers)
        assert response.status_code == 500
    finally:
        event.remove(SkinServiceMap, 'before_insert', fail)
    with app.app_context():
        assert maps.current() == before


def test_db_mapping_change_invalidates_customer_cache(enabled, client, catalog, fake_ai, gemini, customer_auth_headers):
    a = catalog[0]
    with enabled.app_context():
        maps.save({'papule': [a]}, enabled.config['TEST_ADMIN_ID'])
    fake_ai.result = ai_result()
    fake_ai.result['predictions'][1]['type_status'] = 'confident'
    analysis = post(client, customer_auth_headers).json['data']['id']
    gemini.reply = {'summary': '', 'recommendations': [
        {'service_id': a, 'matched_type_codes': ['papule'], 'reason': 'Có thể tham khảo.'}]}
    first = suggest(client, customer_auth_headers, analysis).json['data']
    assert first['status'] == 'ok'
    assert suggest(client, customer_auth_headers, analysis).json['data'] == first and len(gemini.calls) == 1
    # An unrelated mapping change leaves the actual candidate version intact.
    with enabled.app_context():
        maps.save({'papule': [a], 'closed_comedo': [a]}, enabled.config['TEST_ADMIN_ID'])
        # closed_comedo is absent from evidence, so it must not invalidate this request.
        assert suggest(client, customer_auth_headers, analysis).json['data'] == first
    assert len(gemini.calls) == 1
    with enabled.app_context():
        maps.save({'papule': [a], 'pustule': [a]}, enabled.config['TEST_ADMIN_ID'])
    gemini.reply = {'summary': '', 'recommendations': [
        {'service_id': a, 'matched_type_codes': ['pustule'], 'reason': 'Có thể tham khảo.'}]}
    second = suggest(client, customer_auth_headers, analysis).json['data']
    assert second['recommendations'][0]['madv'] == a and len(gemini.calls) == 2
    assert second['recommendations'][0]['matched_types'][0]['type'] == 'pustule'


def test_allowed_type_codes_change_version(app, catalog):
    evidence = [{'type': 'papule'}, {'type': 'pustule'}]
    with app.app_context():
        maps.save({'papule': [catalog[0]]}, app.config['TEST_ADMIN_ID'])
        version = recs.candidates(evidence)[2]
        maps.save({'papule': [catalog[0]], 'pustule': [catalog[0]]}, app.config['TEST_ADMIN_ID'])
        assert recs.candidates(evidence)[2] != version


def test_migration_round_trip_constraints_and_cascades():
    spec = importlib.util.spec_from_file_location('map_migration',
        'migrations/versions/20261024_0026_skin_service_map.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == '20261024_0026' and migration.down_revision == '20261023_0025'
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        conn.exec_driver_sql('CREATE TABLE dichvu (madv INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            conn.exec_driver_sql('INSERT INTO dichvu VALUES (1)')
            conn.exec_driver_sql('INSERT INTO nhanvien VALUES (1)')
            sql = "INSERT INTO skin_service_map(type_code,madv,approved_by,approved_at) VALUES (:t,1,1,CURRENT_TIMESTAMP)"
            conn.execute(text(sql), {'t': 'papule'})
            for code in ('alien', 'papule'):
                with pytest.raises(IntegrityError):
                    conn.execute(text(sql), {'t': code})
            conn.exec_driver_sql('DELETE FROM nhanvien WHERE manv=1')
            assert conn.exec_driver_sql('SELECT approved_by FROM skin_service_map').scalar() is None
            conn.exec_driver_sql('DELETE FROM dichvu WHERE madv=1')
            assert conn.exec_driver_sql('SELECT COUNT(*) FROM skin_service_map').scalar() == 0
            migration.downgrade()
            assert not conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='skin_service_map'").fetchall()
    engine.dispose()

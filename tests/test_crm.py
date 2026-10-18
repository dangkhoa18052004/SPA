"""Phase 5 consent, worker recheck, CRM scope and measured conversion; mail mocked."""
from datetime import datetime, timedelta
from uuid import uuid4
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import (CustomerPreference, CustomerPreferenceAudit, CustomerBehavior, RecommendationImpression,
                        NotificationJob, KhachHang, NhanVien, LichHen, ChiTietLichHen)
from app.services import crm_service as crm, notification_service as notifications, email_service
from app.services.recommendation_service import Ranking
from test_recommendations import catalog  # noqa: F401
from test_fresh_migration import db_url, make_app  # noqa: F401


@pytest.fixture
def enabled(app):
    app.config.update(CRM_ENABLED=True, RECOMMENDATION_METRICS_ENABLED=True)
    return app


def preferences(**changes):
    return dict(version=0, reminders=False, post_care=False, review_requests=False, personalization=True, **changes)


def test_opt_in_is_explicit_versioned_self_scoped_and_audited(enabled, client, customer_auth_headers, staff_auth_headers):
    path = '/api/me/communication-preferences'
    before = client.get(path, headers=customer_auth_headers).json
    assert before['version'] == 0 and not any(before[k] for k in ('reminders', 'post_care', 'review_requests'))
    with enabled.app_context(): assert CustomerPreference.query.count() == 0
    data = preferences(); data['reminders'] = True
    response = client.put(path, headers=customer_auth_headers, json=data)
    assert response.status_code == 200 and response.json['version'] == 1
    assert client.put(path, headers=customer_auth_headers, json=data).status_code == 409
    assert client.put(path, headers=staff_auth_headers, json=data).status_code == 403
    bad = dict(data, makh=123)
    assert client.put(path, headers=customer_auth_headers, json=bad).status_code == 400
    bad = dict(data, version=1, reminders='true')
    assert client.put(path, headers=customer_auth_headers, json=bad).status_code == 400
    with enabled.app_context():
        assert CustomerPreferenceAudit.query.one().settings['reminders'] is True
        db.session.get(KhachHang, enabled.config['TEST_CUSTOMER_ID']).trangthai = 'disabled'; db.session.commit()
    assert client.get(path, headers=customer_auth_headers).status_code == 403


def test_withdrawal_clears_only_interaction_data_and_stops_optional_jobs(enabled, client, customer_auth_headers, catalog):
    with enabled.app_context():
        customer = db.session.get(KhachHang, catalog['a'])
        for source in ('frontend', 'backend'):
            db.session.add(CustomerBehavior(makh=customer.makh, madv=catalog['services'][0], action='book_service' if source == 'backend' else 'view_service', source=source, dedupe_key=str(uuid4())))
        db.session.add(RecommendationImpression(id=str(uuid4()), makh=customer.makh, madv=catalog['services'][0], placement='catalog', position=1, strategy='enabled', dedupe_key=str(uuid4())))
        db.session.add(NotificationJob(type='review_request', makh=customer.makh, scheduled_at=datetime.utcnow(), status='pending', unique_key='consent-test', payload_json={}))
        db.session.commit()
    data = preferences(); data['personalization'] = False
    assert client.put('/api/me/communication-preferences', headers=customer_auth_headers, json=data).status_code == 200
    with enabled.app_context():
        assert CustomerBehavior.query.filter_by(source='frontend').count() == 0
        assert CustomerBehavior.query.filter_by(source='backend').count() == 1
        assert RecommendationImpression.query.count() == 0
        assert NotificationJob.query.one().status == 'cancelled'
        assert Ranking(catalog['a']).strategy == 'popular'
    response = client.post('/api/recommendations/events', headers=customer_auth_headers, json=dict(action='view_service', madv=catalog['services'][0]))
    assert response.status_code == 200 and response.json['recorded'] is False


def test_worker_rechecks_consent_but_keeps_transactional_confirmation(enabled, monkeypatch, catalog):
    calls = []
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **k: calls.append(a) or True)
    with enabled.app_context():
        now = datetime.utcnow()
        apt = LichHen(makh=catalog['a'], manv=enabled.config['TEST_STAFF_ID'], ngaygio=now + timedelta(days=4, hours=7), trangthai='confirmed')
        db.session.add(apt); db.session.flush()
        notifications.sync_appointment_jobs(apt, now)
        assert NotificationJob.query.count() == 0
        for kind in ('appointment_reminder_2h', 'booking_confirmation'):
            db.session.add(NotificationJob(type=kind, makh=apt.makh, malh=apt.malh, scheduled_at=now, status='pending', unique_key=kind, payload_json=dict(to='nobody@example.test', subject='test', body='test')))
        db.session.commit()
        result = notifications.process_jobs(now=now)
        assert result['sent'] == 1 and result['cancelled'] == 1 and len(calls) == 1


def test_turning_reminders_on_schedules_future_confirmed_only(enabled, client, customer_auth_headers, catalog):
    with enabled.app_context():
        now = datetime.utcnow()
        for state in ('confirmed', 'completed'):
            db.session.add(LichHen(makh=catalog['a'], manv=enabled.config['TEST_STAFF_ID'], ngaygio=now + timedelta(days=4, hours=7), trangthai=state))
        db.session.commit()
    data = preferences(); data['reminders'] = True; data['post_care'] = True
    assert client.put('/api/me/communication-preferences', headers=customer_auth_headers, json=data).status_code == 200
    with enabled.app_context():
        assert {j.type for j in NotificationJob.query.all()} == {'appointment_reminder_24h', 'appointment_reminder_2h'}


def test_impressions_clicks_conversion_are_owned_deduped_and_measured(enabled, client, catalog, customer_auth_headers, admin_auth_headers):
    sid = catalog['services'][0]
    body = dict(placement='booking', items=[dict(type='service', id=sid, position=1)])
    response = client.post('/api/recommendations/impressions', headers=customer_auth_headers, json=body)
    assert response.status_code == 200, response.json
    impression = response.json['items'][0]['id']
    assert client.post('/api/recommendations/impressions', headers=customer_auth_headers, json=body).json['items'][0]['id'] == impression
    with enabled.app_context():
        other = create_access_token(identity=f'customer:{catalog["b"]}')
    assert client.post(f'/api/recommendations/impressions/{impression}/click', headers={'Authorization':f'Bearer {other}'}).status_code == 404
    assert client.post(f'/api/recommendations/impressions/{impression}/click', headers=customer_auth_headers).status_code == 200
    with enabled.app_context():
        db.session.add(CustomerBehavior(makh=catalog['a'], madv=sid, action='book_service', source='backend', dedupe_key='canonical-booking-conversion'))
        db.session.commit()
    response = client.get('/api/admin/recommendations/baseline', headers=admin_auth_headers)
    assert response.status_code == 200, response.json
    assert response.json['impressions'] == response.json['clicks'] == response.json['conversions'] == 1
    assert response.json['ctr'] == response.json['conversion_rate'] == 100
    assert client.get('/api/admin/recommendations/baseline', headers=customer_auth_headers).status_code == 403
    assert client.get('/api/admin/recommendations/baseline?from=2020-01-01&to=2030-01-01', headers=admin_auth_headers).status_code == 400


@pytest.mark.parametrize('item', [dict(type='service', id=True, position=1), dict(type='service', id=1, position=7), dict(type='service', id=1, position=1, makh=7)])
def test_impression_payload_validation(enabled, client, customer_auth_headers, item):
    assert client.post('/api/recommendations/impressions', headers=customer_auth_headers, json=dict(placement='catalog', items=[item])).status_code == 400


def test_baseline_empty_is_unknown_and_latency_is_real(enabled, client, admin_auth_headers, catalog):
    before = client.get('/api/admin/recommendations/baseline', headers=admin_auth_headers).json
    assert before['ctr'] is None and before['conversion_rate'] is None and before['p95_ms'] is None
    response = client.get('/api/services')
    assert response.status_code == 200 and 'recommendation;dur=' in response.headers['Server-Timing']
    after = client.get('/api/admin/recommendations/baseline', headers=admin_auth_headers).json
    assert after['latency_samples'] == 1 and after['p95_ms'] >= 0


def test_crm_segments_history_scope_and_flags(enabled, client, staff_auth_headers, admin_auth_headers, customer_auth_headers, catalog):
    with enabled.app_context():
        db.session.add(LichHen(makh=catalog['a'], manv=enabled.config['TEST_STAFF_ID'], ngaygio=datetime.utcnow() + timedelta(hours=7) - timedelta(days=45), trangthai='completed'))
        db.session.commit()
    response = client.get('/api/admin/crm/customers?segment=due', headers=admin_auth_headers)
    assert response.status_code == 200, response.json
    assert [c['id'] for c in response.json['items']] == [catalog['a']]
    for headers in (staff_auth_headers, customer_auth_headers):
        assert client.get('/api/admin/crm/customers', headers=headers).status_code == 403
        assert client.get(f'/api/admin/crm/customers/{catalog["a"]}', headers=headers).status_code == 403
    with enabled.app_context():
        staff = db.session.get(NhanVien, enabled.config['TEST_STAFF_ID']); staff.role = 'letan'; db.session.commit()
    assert client.get('/api/admin/crm/customers', headers=staff_auth_headers).status_code == 200
    assert client.get('/api/admin/recommendations/baseline', headers=staff_auth_headers).status_code == 403
    assert client.get(f'/api/admin/crm/customers/{catalog["a"]}', headers=admin_auth_headers).json['total'] == 1
    enabled.config.update(CRM_ENABLED=False, RECOMMENDATION_METRICS_ENABLED=False)
    assert client.get('/api/admin/crm/customers', headers=admin_auth_headers).status_code == 404
    assert client.get('/api/me/communication-preferences', headers=customer_auth_headers).status_code == 404
    assert client.get('/api/admin/recommendations/baseline', headers=admin_auth_headers).status_code == 404


def test_personalization_kill_switch_keeps_popular_catalog(app, client, catalog, customer_auth_headers):
    app.config['PERSONALIZATION_ENABLED'] = False
    with app.app_context(): assert Ranking(catalog['a']).strategy == 'popular'
    assert client.get('/api/services', headers=customer_auth_headers).status_code == 200


def test_consent_is_preserved_when_crm_screen_is_rolled_back(enabled, client, customer_auth_headers):
    enabled.config.update(CRM_ENABLED=False, CUSTOMER_CONSENT_ENABLED=True)
    assert client.get('/api/me/communication-preferences', headers=customer_auth_headers).status_code == 200
    assert b'communication-section' in client.get('/profile').data
    with enabled.app_context():
        assert not crm.notification_allowed(enabled.config['TEST_CUSTOMER_ID'], 'review_request')


def test_conversion_excludes_late_and_other_customer_business_events(enabled, client, catalog, customer_auth_headers, admin_auth_headers):
    now = datetime.utcnow()
    with enabled.app_context():
        sid = catalog['services'][0]
        db.session.add(RecommendationImpression(id=str(uuid4()), makh=catalog['a'], madv=sid, placement='catalog', position=1,
            strategy='enabled', dedupe_key=str(uuid4()), created_at=now - timedelta(days=9), clicked_at=now - timedelta(days=9)))
        for customer_id, at in [(catalog['a'], now), (catalog['b'], now - timedelta(days=8))]:
            db.session.add(CustomerBehavior(makh=customer_id, madv=sid, action='book_service', source='backend', created_at=at, dedupe_key=str(uuid4())))
        db.session.commit()
    start = (now - timedelta(days=10)).date().isoformat()
    assert client.get(f'/api/admin/recommendations/baseline?from={start}', headers=admin_auth_headers).json['conversions'] == 0


def test_prune_does_not_remove_business_facts_or_preferences(enabled, catalog):
    with enabled.app_context():
        for source in ('frontend', 'backend'):
            db.session.add(CustomerBehavior(makh=catalog['a'], madv=catalog['services'][0], action='view_service', source=source,
                created_at=datetime.utcnow() - timedelta(days=100), dedupe_key=str(uuid4())))
        db.session.commit()
    result = enabled.test_cli_runner().invoke(args=['crm', 'prune-metrics', '--dry-run'])
    assert result.exit_code == 0 and 'interactions=1' in result.output
    result = enabled.test_cli_runner().invoke(args=['crm', 'prune-metrics'])
    assert result.exit_code == 0
    with enabled.app_context(): assert CustomerBehavior.query.one().source == 'backend'


def test_baseline_query_on_database_dialects(db_url, make_app):
    from app.models import DichVu
    from app.services.recommendation_metrics import baseline
    application = make_app(db_url)
    result = application.test_cli_runner().invoke(args=['db', 'upgrade'])
    assert result.exit_code == 0, result.output
    with application.app_context():
        now = datetime.utcnow()
        customer = KhachHang(hoten='Dialect test', taikhoan='dialect', matkhau='hash', trangthai='active')
        service = DichVu(tendv='Dialect test service', gia=100000, thoiluong=30, active=True)
        db.session.add_all([customer, service]); db.session.flush()
        db.session.add(RecommendationImpression(id=str(uuid4()), makh=customer.makh, madv=service.madv, placement='catalog', position=1,
            strategy='enabled', dedupe_key=str(uuid4()), created_at=now - timedelta(minutes=3), clicked_at=now - timedelta(minutes=2)))
        db.session.add(CustomerBehavior(makh=customer.makh, madv=service.madv, action='book_service', source='backend', created_at=now - timedelta(minutes=1), dedupe_key=str(uuid4())))
        db.session.commit()
        stats = baseline(now - timedelta(days=1), now + timedelta(days=1), now=now)
        assert stats['impressions'] == stats['clicks'] == stats['conversions'] == 1

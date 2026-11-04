"""Customer skin (acne) analysis: consent, AI proxy (mocked), private storage, ownership, deletion."""
import io
import json
import os

import pytest
from flask_jwt_extended import create_access_token
from PIL import Image
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import KhachHang
from app.services import skin_analysis_service as skin
from app.skin_models import SkinAnalysis

API = '/api/me/skin-analyses'


def photo(size=(60, 40), orientation=None):
    img = Image.new('RGB', size, (200, 160, 140))
    out = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        img.save(out, 'JPEG', exif=exif)
    else:
        img.save(out, 'JPEG')
    out.seek(0)
    return out


def ai_result(status='ok'):
    base = dict(analysis_status=status, image_size=[60, 40], disclaimer='Chỉ tham khảo.')
    if status == 'retake_photo':
        return dict(base, lesion_count=None, predictions=[],
                    input_check=dict(passed=False, reasons=[dict(code='blurry', message='Ảnh bị mờ.')]))
    preds = [dict(bbox=[10, 10, 14, 14], type_status='confident', top3=[dict(type='papule', probability=0.95)]),
             dict(bbox=[30, 20, 33, 23], type_status='uncertain',
                  top3=[dict(type='pustule', probability=0.6), dict(type='papule', probability=0.3)])]
    return dict(base, lesion_count=2, predictions=preds,
                message={'location_only': 'Chỉ hiển thị vị trí.', 'demo': 'Chế độ thử nghiệm.'}.get(status))


@pytest.fixture()
def enabled(app):
    app.config['SKIN_ANALYSIS_ENABLED'] = True
    return app


@pytest.fixture()
def fake_ai(monkeypatch):
    calls = []

    def fake(jpeg, result=None):
        calls.append(jpeg)
        return fake.result
    fake.result = ai_result()
    monkeypatch.setattr(skin, 'call_ai', fake)
    fake.calls = calls
    return fake


def post(client, headers, consent=skin.CONSENT_VERSION, image=None):
    data = {'image': (image or photo(), 'face.jpg')}
    if consent:
        data['consent'] = consent
    return client.post(API, data=data, headers=headers, content_type='multipart/form-data')


def test_disabled_by_default(app, client, customer_auth_headers):
    app.config['SKIN_ANALYSIS_ENABLED'] = False  # a local .env may turn it on
    assert client.get('/skin-analysis').status_code == 404
    assert client.get('/skin-analysis/1').status_code == 404
    assert client.get(API, headers=customer_auth_headers).status_code == 404


def test_page_renders(enabled, client):
    r = client.get('/skin-analysis')
    assert r.status_code == 200
    assert skin.CONSENT_VERSION.encode() in r.data
    assert r.headers['Cache-Control'] == 'private, no-store'


def test_detail_page_is_private_shell_and_not_embedded_customer_data(enabled, client):
    r = client.get('/skin-analysis/123')
    assert r.status_code == 200
    assert r.headers['Cache-Control'] == 'private, no-store'
    assert b'data-analysis-id="123"' in r.data
    assert b'/skin-analysis?analysis=123' in r.data
    assert b'/api/me/skin-analyses/123/image' not in r.data
    # Private data and photos still require the existing owner-authorized APIs.
    assert client.get(f'{API}/123').status_code == 401
    assert client.get(f'{API}/123/image').status_code == 401


def test_requires_login_and_customer(enabled, client, staff_auth_headers):
    assert post(client, {}).status_code == 401
    assert post(client, staff_auth_headers).status_code == 403


def test_consent_required(enabled, client, customer_auth_headers, fake_ai):
    r = post(client, customer_auth_headers, consent=None)
    assert r.status_code == 400
    assert post(client, customer_auth_headers, consent='old-version').status_code == 400
    assert fake_ai.calls == []


def test_retake_is_returned_not_stored(enabled, client, customer_auth_headers, fake_ai):
    fake_ai.result = ai_result('retake_photo')
    r = post(client, customer_auth_headers)
    body = r.get_json()['data']
    assert r.status_code == 200 and body['saved'] is False and body['status'] == 'retake_photo'
    assert body['reasons'] == ['Ảnh bị mờ.']
    with enabled.app_context():
        assert SkinAnalysis.query.count() == 0


def test_ok_is_stored_listed_served_and_deleted(enabled, client, customer_auth_headers, fake_ai):
    r = post(client, customer_auth_headers)
    data = r.get_json()['data']
    assert r.status_code == 200 and data['saved'] is True and data['status'] == 'ok'
    assert data['lesion_count'] == 2 and data['type_counts'] == {'papule': 1}
    assert [l['type'] for l in data['lesions']] == ['papule', None]
    assert data['lesions'][1]['label'] == 'Chưa xác định loại'

    listed = client.get(API, headers=customer_auth_headers).get_json()['data']
    assert [a['id'] for a in listed] == [data['id']]
    detail = client.get(f"{API}/{data['id']}", headers=customer_auth_headers).get_json()['data']
    assert detail['image_url'] == f"{API}/{data['id']}/image"

    img = client.get(detail['image_url'], headers=customer_auth_headers)
    assert img.status_code == 200 and img.mimetype == 'image/jpeg'
    assert img.data == fake_ai.calls[0]  # stored bytes are exactly what the AI analysed
    assert img.headers['Cache-Control'] == 'private, no-store'

    with enabled.app_context():
        row = db.session.get(SkinAnalysis, data['id'])
        path = os.path.join(enabled.config['UPLOAD_FOLDER'], 'skin', str(row.makh), row.image_file)
        assert row.consent_version == skin.CONSENT_VERSION and os.path.isfile(path)
    assert client.delete(f"{API}/{data['id']}", headers=customer_auth_headers).status_code == 200
    assert not os.path.exists(path)
    assert client.get(f"{API}/{data['id']}", headers=customer_auth_headers).status_code == 404


def test_location_only_hides_types(enabled, client, customer_auth_headers, fake_ai):
    fake_ai.result = ai_result('location_only')
    data = post(client, customer_auth_headers).get_json()['data']
    assert data['status'] == 'location_only' and data['type_counts'] == {}
    assert all(l['type'] is None for l in data['lesions'])
    assert data['message'] == 'Chỉ hiển thị vị trí.'


def test_demo_shows_every_type_and_flags_low_confidence(enabled, client, customer_auth_headers, fake_ai):
    fake_ai.result = ai_result('demo')
    data = post(client, customer_auth_headers).get_json()['data']
    assert data['saved'] is True and data['status'] == 'demo' and data['message'] == 'Chế độ thử nghiệm.'
    assert [l['type'] for l in data['lesions']] == ['papule', 'pustule']
    assert [l['low_confidence'] for l in data['lesions']] == [False, True]
    assert data['lesions'][1]['alternatives'] == [dict(type='papule', label='Sẩn viêm', probability=0.3)]
    assert data['type_counts'] == {'papule': 1, 'pustule': 1}
    with enabled.app_context():
        assert db.session.get(SkinAnalysis, data['id']).confident_count == 1
    assert client.get(API, headers=customer_auth_headers).get_json()['data'][0]['status'] == 'demo'


def test_other_customer_cannot_read_or_delete(enabled, client, customer_auth_headers, fake_ai):
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    with enabled.app_context():
        other = KhachHang(hoten='Khách khác', sdt='0900000099', email='other@example.com', taikhoan='other_skin',
                          matkhau=generate_password_hash('password'), trangthai='active')
        db.session.add(other)
        db.session.commit()
        headers = {'Authorization': f"Bearer {create_access_token(identity=f'customer:{other.makh}')}"}
    for method, url in (('get', f'{API}/{analysis_id}'), ('get', f'{API}/{analysis_id}/image'),
                        ('delete', f'{API}/{analysis_id}')):
        assert getattr(client, method)(url, headers=headers).status_code == 404
    assert client.get(API, headers=headers).get_json()['data'] == []


def test_exif_orientation_applied_before_analysis(enabled, client, customer_auth_headers, fake_ai):
    post(client, customer_auth_headers, image=photo((60, 40), orientation=6))  # 6 = rotate 90° on display
    assert Image.open(io.BytesIO(fake_ai.calls[0])).size == (40, 60)


def test_rejects_non_images(enabled, client, customer_auth_headers, fake_ai):
    r = post(client, customer_auth_headers, image=io.BytesIO(b'not an image'))
    assert r.status_code == 400 and fake_ai.calls == []


def test_ai_unreachable_gives_503(enabled, client, customer_auth_headers, monkeypatch):
    import requests

    def down(*a, **k):
        raise requests.ConnectionError('refused')
    monkeypatch.setattr(skin.requests, 'post', down)
    r = post(client, customer_auth_headers)
    assert r.status_code == 503 and 'tạm ngừng' in r.get_json()['message']
    with enabled.app_context():
        assert SkinAnalysis.query.count() == 0


# ---------------------------------------------------------------------------
# Result DTO: stable ids, validation, highlights
# ---------------------------------------------------------------------------

def pred(t, p, status='confident', bbox=(10, 10, 14, 14), alt=None):
    top3 = [dict(type=t, probability=p)] + ([alt] if alt else [])
    return dict(bbox=list(bbox), type_status=status, top3=top3)


def test_lesion_ids_and_invalid_data_never_promoted():
    result = dict(analysis_status='ok', predictions=[
        pred('papule', 0.9),
        pred('papule', float('nan')),
        pred('papule', 1.5),
        pred('alien', 0.9),                                       # unknown label
        pred('pustule', 0.8, bbox=(20, 20, 10, 10)),              # inverted box
        dict(bbox=[1, 1, 3, 3], top3=[dict(type='nodule', probability=0.99)]),  # no type_status
        pred('papule', 0.9, alt=dict(type='pustule', probability='x')),
        'garbage',
        dict(bbox=[1, 1, 3, 3], type_status='confident',
             top3=[dict(type='bad', probability=0.9), dict(type='nodule', probability=0.8)]),
    ])
    data = skin.public_result(result)
    items = data['lesions']
    assert [x['id'] for x in items] == list(range(1, 10)) and data['lesion_count'] == 9
    assert [x['type'] for x in items] == ['papule', None, None, None, 'pustule', None, 'papule', None, None]
    assert items[4]['bbox'] is None and items[7]['bbox'] is None and items[0]['bbox'] == [10, 10, 14, 14]
    assert items[6]['alternatives'] == []                          # invalid alternative dropped
    assert items[8]['probability'] is None                         # invalid top-1 is not replaced by top-2
    assert data['reliable_count'] == 3 and data['highlights'] == [
        dict(type='papule', label='Sẩn viêm', count=2, max_probability=0.9),
        dict(type='pustule', label='Mụn mủ', count=1, max_probability=0.8)]


def test_highlights_top3_order_and_ties():
    result = dict(analysis_status='ok', predictions=[
        pred('open_comedo', 0.7), pred('papule', 0.8), pred('pustule', 0.8), pred('pustule', 0.6),
        pred('nodule', 0.99, status='uncertain'), pred('closed_comedo', 0.8)])
    highlights = skin.public_result(result)['highlights']
    # equal max -> more lesions first -> type code; uncertain nodule never highlighted; at most 3 types
    assert [h['type'] for h in highlights] == ['pustule', 'closed_comedo', 'papule']
    for status in ('demo', 'location_only'):
        assert skin.public_result(dict(result, analysis_status=status))['highlights'] == []


def test_empty_result_has_no_highlights():
    data = skin.public_result(dict(analysis_status='ok', predictions=[]))
    assert data['lesion_count'] == 0 and data['highlights'] == [] and data['reliable_count'] == 0


# ---------------------------------------------------------------------------
# Gemini service suggestions
# ---------------------------------------------------------------------------

from app.models import DichVu  # noqa: E402
from app.services import ai_service  # noqa: E402
from app.services import skin_recommendation_service as recs  # noqa: E402


def gemini_reply(obj):
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return {'candidates': [{'content': {'parts': [{'text': text}]}}]}


@pytest.fixture()
def recommend(enabled, monkeypatch):
    """Recommendations on, 6 services mapped (#5 inactive, #6 only for pustule), Gemini mocked."""
    recs.reset()
    enabled.config['SKIN_RECOMMENDATIONS_ENABLED'] = True
    with enabled.app_context():
        services = [DichVu(tendv=f'Dịch vụ {i}', gia=100000 * i, thoiluong=30 + i, active=i != 5,
                           mota=f'Mô tả thật {i}') for i in range(1, 7)]
        db.session.add_all(services)
        db.session.commit()
        ids = [s.madv for s in services]
    enabled.config['SKIN_SERVICE_MAP'] = json.dumps({'papule': ids[:5], 'pustule': [ids[5]]})
    calls = []

    def fake(payload):
        calls.append(payload)
        if isinstance(fake.reply, Exception):
            raise fake.reply
        return gemini_reply(fake.reply)
    fake.reply = dict(summary='Gợi ý theo kết quả.', recommendations=[])
    monkeypatch.setattr(ai_service, 'call_gemini', fake)
    fake.calls, fake.ids = calls, ids
    yield fake
    recs.reset()


def suggest(client, headers, analysis_id, consent=recs.CONSENT_VERSION):
    return client.post(f'{API}/{analysis_id}/recommendations', json={'consent': consent}, headers=headers)


def test_recommendations_disabled_by_flag(enabled, client, customer_auth_headers, fake_ai):
    enabled.config['SKIN_RECOMMENDATIONS_ENABLED'] = False
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    assert suggest(client, customer_auth_headers, analysis_id).status_code == 404


def test_recommendations_need_consent_before_gemini(recommend, client, customer_auth_headers, fake_ai):
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    for consent in (None, 'old'):
        data = suggest(client, customer_auth_headers, analysis_id, consent).get_json()['data']
        assert data['status'] == 'consent_required' and data['analysis_id'] == analysis_id
    assert recommend.calls == []


def test_no_treatment_suggestions_without_reliable_types(recommend, client, customer_auth_headers, fake_ai):
    fake_ai.result = ai_result('location_only')
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    data = suggest(client, customer_auth_headers, analysis_id).get_json()['data']
    assert data['status'] == 'insufficient_evidence' and data['recommendations'] == [] and data['message']
    assert recommend.calls == []


def test_demo_suggestions_use_every_typed_lesion_and_are_flagged(recommend, client, customer_auth_headers, fake_ai):
    s1, s6 = recommend.ids[0], recommend.ids[5]
    recommend.reply = dict(summary='Gợi ý thử nghiệm.', recommendations=[
        dict(service_id=s6, matched_type_codes=['pustule'], reason=''),
        dict(service_id=s1, matched_type_codes=['papule'], reason='Có thể tham khảo.')])
    fake_ai.result = ai_result('demo')
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    data = suggest(client, customer_auth_headers, analysis_id).get_json()['data']
    assert data['status'] == 'ok' and data['demo'] is True
    assert [c['madv'] for c in data['recommendations']] == [s6, s1]
    assert 'chế độ thử nghiệm' in data['recommendations'][0]['reason']  # fallback reason says demo, not "đủ tin cậy"
    # the uncertain pustule counts in demo; Gemini is told the result is a demo
    facts = json.loads(recommend.calls[0]['contents'][0]['parts'][0]['text'].split('DỮ LIỆU: ', 1)[1])
    assert facts['mode'] == 'demo' and {g['type_code'] for g in facts['evidence']} == {'papule', 'pustule'}


def test_no_mapping_means_no_matching_services(recommend, enabled, client, customer_auth_headers, fake_ai):
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    # empty, broken JSON, only types without evidence, only an inactive service
    for mapping in ('', 'not json', json.dumps({'pustule': recommend.ids}), json.dumps({'papule': [recommend.ids[4]]})):
        enabled.config['SKIN_SERVICE_MAP'] = mapping
        data = suggest(client, customer_auth_headers, analysis_id).get_json()['data']
        assert data['status'] == 'no_matching_services' and data['recommendations'] == []
    assert recommend.calls == []


def test_recommendations_are_validated_against_server_data(recommend, client, customer_auth_headers, fake_ai):
    s1, s2, s3, s4, s5, s6 = recommend.ids
    recommend.reply = dict(summary='Có thể tham khảo các dịch vụ sau.', recommendations=[
        dict(service_id=s6, matched_type_codes=['pustule'], reason='Không có bằng chứng'),
        dict(service_id=s1, matched_type_codes=['papule', 'nodule'], reason='Có thể tham khảo cho sẩn viêm.', price=1),
        dict(service_id=s1, matched_type_codes=['papule'], reason='Trùng'),
        dict(service_id=99999, matched_type_codes=['papule'], reason='Không tồn tại'),
        dict(service_id=s5, matched_type_codes=['papule'], reason='Đã ngừng'),
        dict(service_id=s2, matched_type_codes=['pustule'], reason='Loại không có bằng chứng'),
        dict(service_id=s3, matched_type_codes=['papule'], reason='Cam kết chữa khỏi 100%'),
        dict(service_id=str(s4), matched_type_codes=['papule'], reason='Chỉ 99.000đ <b>hôm nay</b>'),
        dict(service_id=s2, matched_type_codes=['papule'], reason='Quá giới hạn 3'),
    ])
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    r = suggest(client, customer_auth_headers, analysis_id)
    data = r.get_json()['data']
    assert r.status_code == 200 and data['status'] == 'ok' and data['analysis_id'] == analysis_id
    cards = data['recommendations']
    assert [c['madv'] for c in cards] == [s1, s3, s4]
    assert cards[0]['reason'] == 'Có thể tham khảo cho sẩn viêm.'
    assert all('chữa khỏi' not in c['reason'] and '99.000' not in c['reason'] for c in cards)
    assert cards[0]['matched_types'] == [dict(type='papule', label='Sẩn viêm')]
    assert cards[0]['gia'] == '100000.00' and cards[0]['thoiluong'] == 31  # from the database
    assert cards[2]['booking_url'] == f'/appointments/create?service={s4}' and cards[2]['detail_url'] == f'/services/{s4}'

    # Gemini saw derived facts and real candidates only: no photo, boxes, customer data or unmapped services.
    sent = json.dumps(recommend.calls[0], ensure_ascii=False)
    for forbidden in ('bbox', 'image', 'customer@example.com', '0900000002', 'Khách hàng Test', '/uploads', 'Bearer'):
        assert forbidden not in sent
    facts = json.loads(recommend.calls[0]['contents'][0]['parts'][0]['text'].split('DỮ LIỆU: ', 1)[1])
    assert facts['evidence'] == [dict(type_code='papule', name='Sẩn viêm', reliable_point_count=1,
                                      highest_ai_confidence=0.95)]
    assert sorted(s['service_id'] for s in facts['services']) == [s1, s2, s3, s4]

    # Cached per analysis + catalog: no second Gemini call; deleting the analysis drops the cache.
    assert suggest(client, customer_auth_headers, analysis_id).get_json()['data'] == data
    assert len(recommend.calls) == 1
    client.delete(f'{API}/{analysis_id}', headers=customer_auth_headers)
    assert not recs._cache
    assert suggest(client, customer_auth_headers, analysis_id).status_code == 404


def test_catalog_change_invalidates_cache(recommend, enabled, client, customer_auth_headers, fake_ai):
    s1 = recommend.ids[0]
    recommend.reply = dict(summary='', recommendations=[dict(service_id=s1, matched_type_codes=['papule'], reason='Ok.')])
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    assert suggest(client, customer_auth_headers, analysis_id).get_json()['data']['status'] == 'ok'
    with enabled.app_context():
        db.session.get(DichVu, s1).active = False
        db.session.commit()
    recommend.reply = dict(summary='', recommendations=[])
    data = suggest(client, customer_auth_headers, analysis_id).get_json()['data']
    assert len(recommend.calls) == 2 and data['status'] == 'no_matching_services'


def test_gemini_empty_choice_is_no_match(recommend, client, customer_auth_headers, fake_ai):
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    data = suggest(client, customer_auth_headers, analysis_id).get_json()['data']
    assert data['status'] == 'no_matching_services' and data['recommendations'] == []


@pytest.mark.parametrize('reply, status', [
    ('not json', 502),
    ({'recommendations': 'x'}, 502),
    ({'recommendations': [{'service_id': 99999, 'matched_type_codes': ['papule'], 'reason': 'x'}]}, 502),
    (ai_service.AINotConfigured('no key'), 503),
    (ai_service.AIUpstreamError('down'), 502),
])
def test_provider_failure_keeps_scan_result(recommend, client, customer_auth_headers, fake_ai, reply, status):
    recommend.reply = reply
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    r = suggest(client, customer_auth_headers, analysis_id)
    assert r.status_code == status and r.get_json()['success'] is False
    assert client.get(f'{API}/{analysis_id}', headers=customer_auth_headers).status_code == 200
    assert not recs._running and not recs._cache


def test_recommendation_budget_and_single_flight(recommend, enabled, client, customer_auth_headers, fake_ai,
                                                 monkeypatch):
    monkeypatch.setattr(recs, 'CALLS_PER_WINDOW', 1)
    recommend.reply = ai_service.AIUpstreamError('down')  # failures are not cached, so a retry calls Gemini again
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    assert suggest(client, customer_auth_headers, analysis_id).status_code == 502
    assert suggest(client, customer_auth_headers, analysis_id).status_code == 429
    recs.reset()
    recs._running.add((enabled.config['TEST_CUSTOMER_ID'], analysis_id))
    assert suggest(client, customer_auth_headers, analysis_id).status_code == 409
    assert len(recommend.calls) == 1


def test_other_customer_cannot_get_recommendations(recommend, enabled, client, customer_auth_headers, fake_ai):
    analysis_id = post(client, customer_auth_headers).get_json()['data']['id']
    with enabled.app_context():
        other = KhachHang(hoten='Khách khác', sdt='0900000098', email='other2@example.com', taikhoan='other_skin2',
                          matkhau=generate_password_hash('password'), trangthai='active')
        db.session.add(other)
        db.session.commit()
        headers = {'Authorization': f"Bearer {create_access_token(identity=f'customer:{other.makh}')}"}
    assert suggest(client, headers, analysis_id).status_code == 404
    assert suggest(client, {}, analysis_id).status_code == 401
    assert recommend.calls == []


def test_page_shows_recommendation_block_only_when_enabled(enabled, client):
    enabled.config['SKIN_RECOMMENDATIONS_ENABLED'] = False
    assert b'id="skinRecs"' not in client.get('/skin-analysis').data
    enabled.config['SKIN_RECOMMENDATIONS_ENABLED'] = True
    page = client.get('/skin-analysis').data.decode()
    assert 'id="skinRecs"' in page and f'data-consent-version="{recs.CONSENT_VERSION}"' in page

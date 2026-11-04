"""Local preview of /skin-analysis on the disposable SQLite test fixture, with a fake AI service and fake Gemini.

python tests/skin_analysis_preview.py [--port 5078]
Open http://127.0.0.1:5078/__preview/session?customer=1, then switch the fake AI with /__preview/mode?ai=<mode>
(ok | many | few | location_only | demo | empty | retake) and the fake Gemini with &gemini=<ok | fail | none>.
No real AI service, Gemini key, customer photo or production database is used.
"""
import argparse
import io
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from flask import jsonify, redirect, request, session
from PIL import Image
from app.extensions import db
from app.models import DanhMucDichVu, DichVu
from app.services import ai_service, skin_analysis_service, skin_recommendation_service

TYPES = ['papule', 'pustule', 'closed_comedo', 'open_comedo', 'nodule']
MODE = {'ai': 'ok', 'gemini': 'ok'}


def fake_predictions(w, h, n, status):
    rng = random.Random(n)
    preds = []
    for i in range(n):
        x, y = rng.uniform(.2, .75) * w, rng.uniform(.2, .8) * h
        side = max(6, min(w, h) * rng.uniform(.015, .03))
        t = TYPES[rng.choice([0, 0, 1, 1, 2, 3, 4])]
        p = round(rng.uniform(.35, .98), 3)
        alt = TYPES[(TYPES.index(t) + 1) % len(TYPES)]
        confident = p >= .6 and status == 'ok'
        preds.append(dict(bbox=[round(x, 1), round(y, 1), round(x + side, 1), round(y + side, 1)],
                          detection_confidence=round(rng.uniform(.5, .95), 3),
                          type_status='confident' if confident else 'uncertain',
                          top3=[dict(type=t, probability=p), dict(type=alt, probability=round((1 - p) * .7, 3))]))
    return preds


def fake_ai(jpeg):
    w, h = Image.open(io.BytesIO(jpeg)).size
    mode = MODE['ai']
    base = dict(image_size=[w, h], disclaimer='Kết quả chỉ mang tính tham khảo.')
    if mode == 'retake':
        return dict(base, analysis_status='retake_photo', lesion_count=None, predictions=[],
                    input_check=dict(passed=False, reasons=[dict(code='dark', message='Ảnh quá tối.')]))
    status = mode if mode in ('location_only', 'demo') else 'ok'
    n = {'many': 128, 'few': 2, 'empty': 0}.get(mode, 14)
    message = {'location_only': 'Ảnh khác ảnh huấn luyện nên chỉ hiển thị vị trí.',
               'demo': 'Chế độ thử nghiệm.'}.get(status)
    return dict(base, analysis_status=status, message=message, predictions=fake_predictions(w, h, n, status),
                lesion_count=n)


def fake_gemini(payload):
    if MODE['gemini'] == 'fail':
        raise ai_service.AIUpstreamError('preview failure')
    facts = json.loads(payload['contents'][0]['parts'][0]['text'].split('DỮ LIỆU: ', 1)[1])
    picks = [] if MODE['gemini'] == 'none' else facts['services'][:3]
    text = json.dumps(dict(summary='Các dịch vụ này có thể tham khảo cho nhóm mụn AI ghi nhận đủ tin cậy.',
                           recommendations=[dict(service_id=s['service_id'], matched_type_codes=s['allowed_type_codes'][:2],
                                                 reason=f'Có thể tham khảo cho {s["allowed_type_codes"][0]} trong lần phân tích này.')
                                            for s in picks]), ensure_ascii=False)
    return {'candidates': [{'content': {'parts': [{'text': text}]}}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5078)
    args = parser.parse_args()
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    upload = Path(__file__).resolve().parents[1] / '.test-tmp/skin-preview/uploads'
    upload.mkdir(parents=True, exist_ok=True)
    app.config.update(SKIN_ANALYSIS_ENABLED=True, SKIN_RECOMMENDATIONS_ENABLED=True, GEMINI_API_KEY='',
                      MAIL_SUPPRESS_SEND=True, SESSION_COOKIE_SECURE=False, UPLOAD_FOLDER=str(upload))
    skin_analysis_service.call_ai = fake_ai
    ai_service.call_gemini = fake_gemini
    with app.app_context():
        category = DanhMucDichVu(name='Chăm sóc da', slug='skin-care')
        db.session.add(category)
        db.session.flush()
        names = ['Lấy nhân mụn chuẩn y khoa', 'Chăm sóc da mụn chuyên sâu với tên dịch vụ dài để kiểm tra xuống dòng',
                 'Làm sạch sâu lỗ chân lông', 'Massage thư giãn']
        services = [DichVu(tendv=n, gia=250000 + i * 100000, thoiluong=45 + i * 15, active=True,
                           category_id=category.id, mota='Dữ liệu kiểm thử giao diện local.') for i, n in enumerate(names)]
        db.session.add_all(services)
        db.session.commit()
        a, b, c, _ = [s.madv for s in services]
    app.config['SKIN_SERVICE_MAP'] = json.dumps({'papule': [a, b], 'pustule': [b], 'closed_comedo': [c],
                                                 'open_comedo': [c]})

    @app.route('/__preview/session')
    def preview_session():
        # Only present in this loopback-only preview, never registered by create_app.
        session.clear()
        if request.args.get('customer') == '1':
            session.update(user_id=app.config['TEST_CUSTOMER_ID'], user_type='customer')
        return redirect('/skin-analysis')

    @app.route('/__preview/mode')
    def preview_mode():
        MODE.update({k: v for k, v in request.args.items() if k in MODE})
        skin_recommendation_service.reset()
        return jsonify(MODE)

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    try:
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
    finally:
        fixture.close()


if __name__ == '__main__':
    main()

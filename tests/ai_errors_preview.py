"""Disposable loopback fixture for AI error contexts; no real models or customer data."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from flask import jsonify, session
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.skin_models import SkinServiceMap
from app.services import ai_service, skin_analysis_service as skin
from test_skin_analysis import ai_result, post


def main():
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    app.config.update(BUSINESS_PORTAL_ENABLED=True, ADMIN_CARE_REACT_ENABLED=True,
        STAFF_SECURITY_ENABLED=False, SESSION_COOKIE_SECURE=False, GEMINI_API_KEY='fake-preview-key',
        AI_CHAT_JOBS_ENABLED=False, SKIN_ANALYSIS_ENABLED=True, SKIN_RECOMMENDATIONS_ENABLED=True,
        SKIN_SERVICE_MAP={}, MAIL_SUPPRESS_SEND=True)
    skin.call_ai = lambda *args: ai_result()
    def unavailable(payload):
        raise ai_service.AIUpstreamError('Dịch vụ AI chưa phản hồi kịp thời. Vui lòng thử lại sau.', 504)
    ai_service.call_gemini = unavailable

    @app.route('/__qa/login/<role>')
    def login(role):
        kind = 'customer' if role == 'customer' else 'staff'
        uid = app.config['TEST_CUSTOMER_ID' if kind == 'customer' else 'TEST_ADMIN_ID']
        session.clear()
        session.update(user_id=uid, user_type=kind)
        if kind == 'staff': session['user_role'] = 'admin'
        return jsonify(access_token=create_access_token(identity=f'{kind}:{uid}'))

    @app.route('/favicon.ico')
    def favicon(): return '', 204

    with app.app_context():
        customer_token = create_access_token(identity=f"customer:{app.config['TEST_CUSTOMER_ID']}")
    with app.test_client() as client:
        response = post(client, {'Authorization': 'Bearer ' + customer_token})
        assert response.status_code == 200
    with app.app_context():
        SkinServiceMap.__table__.drop(db.engine)

    try: app.run(host='127.0.0.1', port=59150, debug=False, use_reloader=False)
    finally: fixture.close()


if __name__ == '__main__': main()

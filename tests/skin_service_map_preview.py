"""Loopback-only preview: disposable test SQLite database and fake Gemini; no real keys or data."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conftest
from flask import jsonify, request
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import DichVu, NhanVien
from app.services import ai_service, skin_service_map_service as maps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5079)
    parser.add_argument('--react', action='store_true')
    args = parser.parse_args()
    fixture = conftest.app.__wrapped__()
    app = next(fixture)
    app.config.update(STAFF_SECURITY_ENABLED=False, SESSION_COOKIE_SECURE=False,
        BUSINESS_PORTAL_ENABLED=args.react, ADMIN_CARE_REACT_ENABLED=args.react)
    with app.app_context():
        services = [DichVu(tendv=name, gia=250000, active=True, mota='Làm sạch da nhẹ nhàng.')
                    for name in ['Làm sạch da', 'Chăm sóc da <img src=x onerror=alert(1)>', 'Massage thư giãn']]
        db.session.add_all(services)
        db.session.commit()
        ids = [s.madv for s in services]
        admin = db.session.get(NhanVien, app.config['TEST_ADMIN_ID'])
        for role in ('manager', 'letan'):
            staff = NhanVien(hoten='Test ' + role, taikhoan='skin-map-' + role, matkhau='hash', macv=admin.macv, role=role, trangthai=True)
            db.session.add(staff)
            db.session.flush()
            app.config['TEST_' + role.upper() + '_ID'] = staff.manv
        db.session.commit()
        maps.save({'papule': [ids[1]]}, app.config['TEST_ADMIN_ID'])
    app.config['SKIN_SERVICE_MAP'] = {'open_comedo': [ids[0]]}

    def fake_gemini(payload):
        answer = {'assignments': [{'type_code': 'papule', 'items': [
            {'service_id': ids[0], 'reason': 'Có thể tham khảo dịch vụ làm sạch da.'}]},
            {'type_code': 'open_comedo', 'items': [{'service_id': ids[0], 'reason': '<script>alert(1)</script>'}]}]}
        return {'candidates': [{'content': {'parts': [{'text': json.dumps(answer)}]}}]}
    ai_service.call_gemini = fake_gemini

    @app.route('/__preview/login')
    def login():
        maps.reset()  # Each local preview run starts with an independent proposal budget.
        role = request.args.get('role', 'admin')
        uid = app.config['TEST_' + role.upper() + '_ID']
        token = create_access_token(identity=f'staff:{uid}')
        return jsonify(access_token=token, role=role, hoten='Test ' + role)

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    try:
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
    finally:
        fixture.close()


if __name__ == '__main__':
    main()

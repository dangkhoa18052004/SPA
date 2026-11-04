"""Customer skin (acne) analysis: page /skin-analysis and /api/me/skin-analyses (flag SKIN_ANALYSIS_ENABLED)."""
import io

from flask import Blueprint, abort, current_app, g, jsonify, render_template, request, send_file

from ..decorators import customer_required
from ..services import skin_analysis_service as skin
from ..services import skin_recommendation_service as recommender

skin_bp = Blueprint('skin', __name__)


@skin_bp.before_request
def enabled():
    if not current_app.config.get('SKIN_ANALYSIS_ENABLED'):
        abort(404)


@skin_bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization, Cookie'
    return response


@skin_bp.errorhandler(skin.SkinAnalysisError)
def failed(error):
    return jsonify(success=False, message=error.message), error.status_code


def active_customer():
    if g.current_user.trangthai != 'active':
        raise skin.SkinAnalysisError('Tài khoản chưa được kích hoạt.', 403)
    return g.current_user


@skin_bp.get('/skin-analysis')
def page():
    return render_template('customer/skin_analysis.html', consent_version=skin.CONSENT_VERSION,
                           analysis_id=None,
                           recommendations_enabled=bool(current_app.config.get('SKIN_RECOMMENDATIONS_ENABLED')),
                           recommendation_consent_version=recommender.CONSENT_VERSION)


@skin_bp.get('/skin-analysis/<int:analysis_id>')
def detail_page(analysis_id):
    # This shell contains no private data; the customer-owned API authorizes every result/image read.
    return render_template('customer/skin_analysis.html', consent_version=skin.CONSENT_VERSION,
                           analysis_id=analysis_id, recommendations_enabled=False)


@skin_bp.post('/api/me/skin-analyses')
@customer_required
def create():
    customer = active_customer()
    f = request.files.get('image')
    consent = request.form.get('consent') == skin.CONSENT_VERSION
    return jsonify(success=True, data=skin.analyze(customer.makh, f.read() if f else b'', consent))


@skin_bp.get('/api/me/skin-analyses')
@customer_required
def list_analyses():
    return jsonify(success=True, data=skin.history(active_customer().makh))


@skin_bp.get('/api/me/skin-analyses/<int:analysis_id>')
@customer_required
def detail(analysis_id):
    return jsonify(success=True, data=skin.serialize(skin.owned(active_customer().makh, analysis_id)))


@skin_bp.get('/api/me/skin-analyses/<int:analysis_id>/image')
@customer_required
def image(analysis_id):
    # Read into memory: an open file handle would block deleting the photo on Windows.
    with open(skin.image_path(active_customer().makh, analysis_id), 'rb') as f:
        return send_file(io.BytesIO(f.read()), mimetype='image/jpeg', max_age=0)


@skin_bp.post('/api/me/skin-analyses/<int:analysis_id>/recommendations')
@customer_required
def recommendations(analysis_id):
    if not current_app.config.get('SKIN_RECOMMENDATIONS_ENABLED'):
        abort(404)
    body = request.get_json(silent=True)
    consent = body.get('consent') if isinstance(body, dict) else None
    return jsonify(success=True, data=recommender.recommend(active_customer().makh, analysis_id, consent))


@skin_bp.delete('/api/me/skin-analyses/<int:analysis_id>')
@customer_required
def remove(analysis_id):
    skin.delete(active_customer().makh, analysis_id)
    return jsonify(success=True)

import os
from flask_cors import CORS
from flask import Flask, jsonify, request, g
from uuid import uuid4
from werkzeug.exceptions import RequestEntityTooLarge
from .config import Config, validate_production_config
from .extensions import db, migrate, jwt, mail

def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    validate_production_config(app.config)
    hops = app.config.get('TRUSTED_PROXY_HOPS', 0)
    if type(hops) is not int or not 0 <= hops <= 2:
        raise RuntimeError('TRUSTED_PROXY_HOPS phải từ 0 đến 2, theo số proxy tin cậy thực tế.')
    if hops:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_port=0, x_prefix=0)
    if app.config.get('APP_ENV') == 'production' or str(app.config.get('RENDER') or '').lower() == 'true':
        app.config['SESSION_COOKIE_SECURE'] = True
    app.config['MAIL_DEFAULT_SENDER'] = ('Bin Spa', app.config.get('MAIL_FROM'))
    CORS(app, supports_credentials=True, origins=['http://127.0.0.1:5000', 'http://localhost:5000', 'https://binspa.id.vn'])
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)

    @app.before_request
    def assign_request_id():
        g.request_id = uuid4().hex

    from .services.runtime_service import register_runtime
    register_runtime(app)

    @app.after_request
    def operations_response_headers(response):
        response.headers['X-Request-ID'] = g.get('request_id', uuid4().hex)
        if request.blueprint == 'operations':
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'same-origin'
            response.headers['Permissions-Policy'] = 'geolocation=(self)'
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(_error):
        return jsonify({
            "success": False,
            "message": "Tệp tải lên vượt quá dung lượng cho phép"
        }), 413

    from .routes.dashboard_api_bp import dashboard_api_bp
    from .routes.auth_bp import auth_bp
    from .routes.profile_bp import profile_bp
    from .routes.chat_bp import chat_bp
    from .routes.service_bp import service_bp
    from .routes.payment_bp import payment_bp
    from .routes.appointment_bp import appointment_bp
    from .routes.customer_bp import customer_bp
    from .routes.staff_bp import staff_bp
    from .routes.analytics_bp import analytics_bp
    from .routes.review_bp import review_bp

    app.register_blueprint(dashboard_api_bp, url_prefix='/api/dashboard')
    app.register_blueprint(customer_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    from .routes.staff_security_bp import staff_security_bp, register_commands as register_security_commands
    app.register_blueprint(staff_security_bp)
    register_security_commands(app)
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(service_bp, url_prefix="/api/services")
    app.register_blueprint(payment_bp, url_prefix="/api/payment")
    app.register_blueprint(appointment_bp, url_prefix="/api/appointments")
    app.register_blueprint(staff_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(review_bp, url_prefix="/api/reviews")
    from .routes.package_bp import package_bp
    from .services.notification_service import register_commands
    app.register_blueprint(package_bp)
    from .routes.loyalty_bp import loyalty_bp
    from .admin.loyalty_manage_bp import admin_loyalty_bp
    app.register_blueprint(loyalty_bp)
    app.register_blueprint(admin_loyalty_bp)
    from .routes.ai_bp import ai_bp
    app.register_blueprint(ai_bp)
    from .routes.recommendation_bp import recommendation_bp
    app.register_blueprint(recommendation_bp)
    from .routes.crm_bp import crm_bp
    app.register_blueprint(crm_bp)
    from .routes.release_bp import release_bp
    app.register_blueprint(release_bp)
    from .routes.operations_bp import operations_bp, register_commands as register_operations_commands
    app.register_blueprint(operations_bp)
    register_operations_commands(app)
    register_commands(app)

    # Đăng ký blueprints admin
    from .admin.staff_manage_bp import staff_manage_bp
    from .admin.service_manage_bp import service_manage_bp
    from .admin.shift_manage_bp import shift_manage_bp
    from .admin.role_manage_bp import role_manage_bp
    from .admin.salary_manage_bp import salary_manage_bp
    from .admin.invoice_manage_bp import invoice_manage_bp
    from .admin.chat_manage_bp import chat_manage_bp
    from .admin.appointment_manage_bp import appointment_manage_bp
    from .admin.admin_bp import admin_bp
    
    app.register_blueprint(admin_bp, url_prefix="/admin")    
    app.register_blueprint(staff_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(service_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(shift_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(role_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(salary_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(invoice_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(appointment_manage_bp, url_prefix="/api/admin")
    app.register_blueprint(chat_manage_bp, url_prefix="/api/admin")

    # Thêm alias cho GET /api/admin/reviews/stats
    from .decorators import roles_required
    @app.route("/api/admin/reviews/stats", methods=["GET"])
    @roles_required('admin', 'manager')
    def admin_review_stats_alias():
        from .services.review_service import get_admin_review_stats
        return jsonify(get_admin_review_stats()), 200

    return app

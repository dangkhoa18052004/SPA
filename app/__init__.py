
import os
from flask_cors import CORS
from flask import Flask
from .config import Config
from .extensions import db, migrate, jwt, mail

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['MAIL_DEFAULT_SENDER'] = ('Bin Spa', app.config.get('MAIL_FROM'))
    CORS(app, supports_credentials=True, origins=['http://127.0.0.1:5000'])
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)

    from .routes.dashboard_api_bp import dashboard_api_bp
    from .routes.auth_bp import auth_bp
    from .routes.profile_bp import profile_bp
    from .routes.chat_bp import chat_bp
    from .routes.service_bp import service_bp
    from .routes.payment_bp import payment_bp
    from .routes.appointment_bp import appointment_bp
    from .routes.customer_bp import customer_bp
    from .routes.staff_bp import staff_bp

    app.register_blueprint(dashboard_api_bp, url_prefix='/api/dashboard')
    app.register_blueprint(customer_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(service_bp, url_prefix="/api/services")
    app.register_blueprint(payment_bp, url_prefix="/api/payment")
    app.register_blueprint(appointment_bp, url_prefix="/api/appointments")
    app.register_blueprint(staff_bp, url_prefix="/api")

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

    print("MOMO Config check (from Config object):")
    print("PARTNER_CODE:", app.config.get('MOMO_PARTNER_CODE_SANDBOX'))
    print("ACCESS_KEY:", app.config.get('MOMO_ACCESS_KEY_SANDBOX'))

    return app
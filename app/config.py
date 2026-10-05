import os
from datetime import timedelta
from dotenv import load_dotenv

# Chỉ tải file .env khi ứng dụng chạy local
load_dotenv() 

# Không cung cấp credential mặc định trong source. Môi trường chạy phải cấu hình
# DATABASE_URL; test có thể override SQLALCHEMY_DATABASE_URI ở application factory.
DATABASE_URL = os.getenv("DATABASE_URL")

# Điều chỉnh tiền tố URL cho SQLAlchemy
# Nếu đang ở môi trường Production (Render), Render cung cấp postgres://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def _is_truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def validate_production_config(config):
    """Fail fast when production is missing security-critical settings."""
    is_production = (
        str(config.get("APP_ENV", "")).lower() == "production"
        or _is_truthy(config.get("RENDER"))
    )
    if not is_production:
        return

    required = {
        "DATABASE_URL": config.get("SQLALCHEMY_DATABASE_URI"),
        "SECRET_KEY": config.get("SECRET_KEY"),
        "JWT_SECRET_KEY": config.get("JWT_SECRET_KEY"),
        "SEPAY_API_KEY": config.get("SEPAY_API_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Thiếu cấu hình bảo mật bắt buộc cho production: "
            + ", ".join(sorted(missing))
        )

class Config:
    # Sử dụng biến đã được kiểm tra và điều chỉnh tiền tố
    SQLALCHEMY_DATABASE_URI = DATABASE_URL 
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))
    RENDER = os.getenv("RENDER")
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    # Flask session acts as the long-lived, HTTP-only login session. The
    # frontend can use it to obtain a new short-lived JWT without asking the
    # customer to sign in again.
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Mail (SMTP)
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_FROM = os.getenv("MAIL_FROM")

    # Twilio (Chỉ bao gồm các biến bạn đã định nghĩa)
    TWILIO_SID = os.getenv("TWILIO_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_FROM = os.getenv("TWILIO_FROM")
    
    # MoMo
    MOMO_PARTNER_CODE_SANDBOX = os.getenv("MOMO_PARTNER_CODE_SANDBOX")
    MOMO_ACCESS_KEY_SANDBOX = os.getenv("MOMO_ACCESS_KEY_SANDBOX")
    MOMO_SECRET_KEY_SANDBOX = os.getenv("MOMO_SECRET_KEY_SANDBOX")
    MOMO_API_ENDPOINT_SANDBOX = os.getenv("MOMO_API_ENDPOINT_SANDBOX")
    YOUR_REDIRECT_URL = os.getenv("YOUR_REDIRECT_URL")
    YOUR_IPN_URL = os.getenv("YOUR_IPN_URL") 
    YOUR_BASE_DOMAIN = os.getenv("YOUR_BASE_DOMAIN", "http://127.0.0.1:5000")
    PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "https://binspa.id.vn")
    # Số phút sau giờ hẹn mà khách chưa đến thì notification-worker tự hủy lịch.
    NO_SHOW_GRACE_MINUTES = int(os.getenv("NO_SHOW_GRACE_MINUTES", "30"))
    # Gemini AI (giai đoạn 5): chỉ đọc từ môi trường; để trống thì AI tắt, phần còn lại vẫn chạy.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "30"))
    # Model dự phòng (phân tách bằng dấu phẩy) khi model chính quá tải 429/5xx.
    GEMINI_FALLBACK_MODELS = os.getenv("GEMINI_FALLBACK_MODELS", "")
    # Lịch lỡ cũ hơn số giờ này chỉ tự hủy, không gửi email (tránh gửi thư cho lịch tồn đọng).
    NO_SHOW_EMAIL_MAX_AGE_HOURS = int(os.getenv("NO_SHOW_EMAIL_MAX_AGE_HOURS", "24"))
    
    # VietQR & SePay Configuration
    VIETQR_BANK_ID = os.getenv("VIETQR_BANK_ID")
    VIETQR_ACCOUNT_NO = os.getenv("VIETQR_ACCOUNT_NO")
    VIETQR_ACCOUNT_NAME = os.getenv("VIETQR_ACCOUNT_NAME")
    SEPAY_API_KEY = os.getenv("SEPAY_API_KEY")

    # config Upload
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5")) * 1024 * 1024

import os
from datetime import timedelta
from dotenv import load_dotenv

# Chỉ tải file .env khi ứng dụng chạy local
load_dotenv() 

# Lấy DATABASE_URL từ môi trường (OS) trước, nếu không có thì dùng giá trị mặc định
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/Spa1")

# Điều chỉnh tiền tố URL cho SQLAlchemy
# Nếu đang ở môi trường Production (Render), Render cung cấp postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class Config:
    # Sử dụng biến đã được kiểm tra và điều chỉnh tiền tố
    SQLALCHEMY_DATABASE_URI = DATABASE_URL 
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)

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
    
    # config Upload
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'uploads')
from multiprocessing.connection import Client
import random
from flask import current_app

def generate_code(n=6):
    """Sinh mã OTP dạng chuỗi chữ số (6 chữ số)"""
    return ''.join(str(random.randint(0,9)) for _ in range(n))

def send_sms(to_number, body):
    """
    Hàm gửi SMS (giữ lại nếu bạn còn dùng)
    """
    cfg = current_app.config
    sid = cfg.get("TWILIO_SID")
    token = cfg.get("TWILIO_AUTH_TOKEN")
    from_ = cfg.get("TWILIO_FROM")
    if not sid or not token or not from_:
        raise RuntimeError("TWILIO chưa cấu hình")
    
    pass # Tạm thời
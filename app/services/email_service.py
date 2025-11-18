import smtplib
from email.message import EmailMessage
from flask import current_app

def send_email(to_email, subject, body):
    """
    Hàm logic để gửi email qua SMTP.
    """
    cfg = current_app.config
    
    if not all([cfg.get("MAIL_SERVER"), cfg.get("MAIL_USERNAME"), cfg.get("MAIL_PASSWORD"), cfg.get("MAIL_FROM")]):
        current_app.logger.error("Cấu hình MAIL (SMTP) bị thiếu! Vui lòng kiểm tra file .env")
        raise RuntimeError("MAIL_SERVER chưa được cấu hình đầy đủ")

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg.get("MAIL_FROM")
    msg['To'] = to_email
    msg.set_content(body)

    try:
        # Kết nối và gửi
        server = smtplib.SMTP(cfg.get("MAIL_SERVER"), cfg.get("MAIL_PORT"))
        if cfg.get("MAIL_USE_TLS"):
            server.starttls()
        server.login(cfg.get("MAIL_USERNAME"), cfg.get("MAIL_PASSWORD"))
        server.send_message(msg)
        server.quit()
        current_app.logger.info(f"Đã gửi email thành công tới {to_email}")
        
    except Exception as e:
        current_app.logger.error(f"Gửi email thất bại tới {to_email}: {e}")
        raise e
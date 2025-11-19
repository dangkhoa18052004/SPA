import os
import resend
from flask import current_app

# Khởi tạo Resend API Key
resend.api_key = os.getenv('RESEND_API_KEY')

def send_email(to_email, subject, body):
    """
    Hàm gửi email qua Resend API (thay thế SMTP).
    Giữ nguyên interface để tương thích với code cũ.
    
    Args:
        to_email (str): Email người nhận
        subject (str): Tiêu đề email
        body (str): Nội dung email (hỗ trợ HTML)
    
    Returns:
        bool: True nếu gửi thành công, False nếu thất bại
    
    Raises:
        Exception: Nếu có lỗi trong quá trình gửi
    """
    
    if not resend.api_key:
        current_app.logger.error("❌ RESEND_API_KEY chưa được cấu hình trong Environment Variables!")
        raise RuntimeError("RESEND_API_KEY không tồn tại. Vui lòng thêm vào Render Environment.")
    

    from_email = "Bin Spa <noreply@binspa.id.vn>"
    

    
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                    background-color: #f4f4f4;
                }}
                .email-container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: white;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #C9A961 0%, #8B7355 100%);
                    color: white;
                    padding: 30px 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 600;
                }}
                .content {{
                    padding: 30px;
                    background: #ffffff;
                }}
                .footer {{
                    background: #f9f9f9;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                    border-top: 1px solid #eee;
                }}
                .footer a {{
                    color: #C9A961;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>🌸 Bin Spa</h1>
                </div>
                <div class="content">
                    {body}
                </div>
                <div class="footer">
                    <p>Email này được gửi tự động từ hệ thống Bin Spa.</p>
                    <p>Vui lòng không trả lời email này.</p>
                    <p>&copy; 2025 Bin Spa. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        response = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })
        
        current_app.logger.info(f"✅ Email đã gửi thành công tới {to_email} | Response ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"❌ Gửi email thất bại tới {to_email}: {str(e)}")
        
        raise e


def send_booking_confirmation(to_email, booking_details):
    """
    Hàm mở rộng: Gửi email xác nhận đặt lịch với template riêng
    
    Args:
        to_email (str): Email khách hàng
        booking_details (dict): Thông tin đặt lịch
            - customer_name: Tên khách hàng
            - service_name: Tên dịch vụ
            - date: Ngày đặt
            - time: Giờ đặt
            - staff_name: Nhân viên phục vụ
            - total_price: Tổng tiền
    """
    try:
        from_email = "Bin Spa <noreply@binspa.id.vn>"
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #C9A961 0%, #8B7355 100%); 
                          color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: #f9f9f9; }}
                .booking-card {{ background: white; padding: 20px; margin: 20px 0; 
                                border-left: 4px solid #C9A961; border-radius: 5px; }}
                .booking-info {{ margin: 10px 0; padding: 10px; background: #fafafa; }}
                .label {{ font-weight: bold; color: #C9A961; }}
                .value {{ color: #333; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Xác nhận đặt lịch thành công!</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{booking_details.get('customer_name', 'Quý khách')}</strong>,</p>
                    <p>Cảm ơn bạn đã tin tùởng và đặt lịch tại <strong>Bin Spa</strong>!</p>
                    
                    <div class="booking-card">
                        <h3 style="color: #C9A961; margin-top: 0;">📋 Thông tin lịch hẹn</h3>
                        <div class="booking-info">
                            <span class="label">Dịch vụ:</span> 
                            <span class="value">{booking_details.get('service_name', 'N/A')}</span>
                        </div>
                        <div class="booking-info">
                            <span class="label">Ngày:</span> 
                            <span class="value">{booking_details.get('date', 'N/A')}</span>
                        </div>
                        <div class="booking-info">
                            <span class="label">Giờ:</span> 
                            <span class="value">{booking_details.get('time', 'N/A')}</span>
                        </div>
                        <div class="booking-info">
                            <span class="label">Nhân viên phục vụ:</span> 
                            <span class="value">{booking_details.get('staff_name', 'Sẽ được phân công')}</span>
                        </div>
                        <div class="booking-info" style="background: #fff3cd; font-size: 18px;">
                            <span class="label">Tổng tiền:</span> 
                            <span class="value" style="color: #C9A961; font-weight: bold;">
                                {booking_details.get('total_price', '0')} VNĐ
                            </span>
                        </div>
                    </div>
                    
                    <p style="margin-top: 30px;">
                        <strong>Lưu ý:</strong> Vui lòng đến đúng giờ để trải nghiệm dịch vụ tốt nhất. 
                        Nếu cần thay đổi lịch hẹn, vui lòng liên hệ spa trước 24 giờ.
                    </p>
                    
                    <p style="margin-top: 20px;">
                        Chúng tôi rất mong được phục vụ bạn! 💆‍♀️<br>
                        <strong>Trân trọng,<br>Đội ngũ Bin Spa</strong>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": "Xác nhận đặt lịch - Bin Spa",
            "html": html_content
        })
        
        current_app.logger.info(f"✅ Email xác nhận đặt lịch đã gửi tới {to_email}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"❌ Lỗi gửi email xác nhận đặt lịch: {str(e)}")
        return False
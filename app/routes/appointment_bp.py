import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import ChucVu, LichHen, KhachHang, DichVu, NhanVien, ChiTietLichHen
from datetime import datetime, timedelta
from sqlalchemy import and_, func, or_
from flask_mail import Message
from ..extensions import mail
import threading

appointment_bp = Blueprint("appointment", __name__)

# HÀM GỬI EMAIL
def send_async_email(app, msg):
    """Hàm chạy trong thread riêng để gửi mail (tránh làm chậm API)."""
    with app.app_context():
        try:
            mail.send(msg)
            current_app.logger.info(f"Đã gửi email thành công tới {msg.recipients}")
        except Exception as e:
            current_app.logger.error(f"Lỗi khi gửi email: {e}")

def send_appointment_confirmation_email(customer_email, customer_name, appointment_data):
    """Gửi email xác nhận đặt lịch"""
    try:
        app = current_app._get_current_object()
        subject = f"Xác nhận đặt lịch hẹn #{appointment_data['malh']} - Bin Spa"

        # Xử lý danh sách dịch vụ + tính tổng thời lượng
        service_names = []
        services_html = ""
        total_duration = 0

        for service in appointment_data["services"]:
            service_names.append(service["tendv"])
            services_html += f"""
            <tr>
                <td style='padding: 10px; border-bottom: 1px solid #eee;'>{service['tendv']}</td>
                <td style='padding: 10px; border-bottom: 1px solid #eee; text-align: right;'>{service['thoiluong']} phút</td>
            </tr>
            """
            total_duration += service["thoiluong"]

        services_text = ", ".join(service_names)

        # Nhân viên
        staff_name = appointment_data.get("staff_name", "Chưa có")

        # Tính giờ kết thúc
        start_dt = datetime.strptime(appointment_data["ngaygio"], "%Y-%m-%d %H:%M:%S")
        end_time = (start_dt + timedelta(minutes=total_duration)).strftime("%H:%M")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 10px;">
                
                <h2 style="margin-top: 0; color: #C9A961;">Bin Spa</h2>
                <p>Xin chào <strong>{customer_name}</strong>,</p>
                <p>Cảm ơn bạn đã đặt lịch tại <strong>Bin Spa</strong>. Dưới đây là thông tin lịch hẹn của bạn:</p>

                <div style="margin-top: 20px;">
                    <p><strong>Mã lịch hẹn:</strong> #{appointment_data['malh']}</p>
                    <p><strong>Ngày:</strong> {start_dt.strftime("%d/%m/%Y")}</p>
                    <p><strong>Dịch vụ:</strong> {services_text}</p>
                    <p><strong>Nhân viên:</strong> {staff_name}</p>
                    <p><strong>Giờ:</strong> {start_dt.strftime("%H:%M")} - {end_time}</p>
                </div>

                <table style="width: 100%; border-collapse: collapse; margin-top: 25px;">
                    <thead>
                        <tr>
                            <th style="padding: 10px; border-bottom: 2px solid #C9A961; text-align: left;">Dịch vụ</th>
                            <th style="padding: 10px; border-bottom: 2px solid #C9A961; text-align: right;">Thời lượng</th>
                        </tr>
                    </thead>
                    <tbody>
                        {services_html}
                    </tbody>
                </table>

                <p style="margin-top: 20px;">Bạn không cần phản hồi email này </p>
                <p>Trân trọng,<br><strong>Bin Spa</strong></p>
            </div>
        </body>
        </html>
        """

        msg = Message(
            subject=subject,
            recipients=[customer_email],
            html=html_content
        )

        thr = threading.Thread(target=send_async_email, args=[app, msg])
        thr.start()

        current_app.logger.info(f"Email xác nhận lịch hẹn đã gửi cho {customer_email}")
        return True

    except Exception as e:
        current_app.logger.error(f"Lỗi gửi email xác nhận: {e}")
        return False

# HÀM CHECK LỊCH
def check_staff_availability(manv, ngaygio, thoiluong_minutes):
    """Kiểm tra nhân viên có rảnh không"""
    if not manv:
        return True, [] 
    
    end_time = ngaygio + timedelta(minutes=thoiluong_minutes)

    is_available = True
    conflicting_list = []
    
    all_staff_appointments = LichHen.query.filter(
        and_(
            LichHen.manv == manv,
            LichHen.trangthai.in_(['confirmed', 'pending', 'in_progress'])
        )
    ).all()

    for existing_apt in all_staff_appointments:
        existing_duration = 0
        for detail in existing_apt.chitiet:
            if detail.dichvu and detail.dichvu.thoiluong:
                existing_duration += detail.dichvu.thoiluong
        
        if existing_duration == 0:
            existing_duration = 60
            
        existing_start = existing_apt.ngaygio
        existing_end = existing_apt.ngaygio + timedelta(minutes=existing_duration)
        
        new_start = ngaygio
        new_end = end_time
        
        if not (new_end <= existing_start or new_start >= existing_end):
            is_available = False
            conflicting_list.append({
                'malh': existing_apt.malh,
                'ngaygio': existing_apt.ngaygio.strftime("%H:%M %d/%m/%Y"),
                'end_time': existing_end.strftime("%H:%M"),
                'services': [detail.dichvu.tendv for detail in existing_apt.chitiet if detail.dichvu]
            })
    
    return is_available, conflicting_list

@appointment_bp.route("/create", methods=["POST"])
@jwt_required()
def create_appointment():
    """Tạo lịch hẹn mới (khách hàng tự đặt) - ĐÃ SỬA: Báo lỗi khi không có nhân viên rảnh"""
    try:
        # === Lấy Khách hàng ===
        identity = get_jwt_identity() 
        makh = None
        try:
            identity_str = str(identity)
            if ':' in identity_str:
                makh = int(identity_str.split(':')[1])
            else:
                makh = int(identity_str)
        except (IndexError, ValueError, TypeError) as e:
            current_app.logger.error(f"Không thể parse makh từ JWT identity: {identity} - Lỗi: {e}")
            return jsonify({"success": False, "message": "Định dạng token không hợp lệ"}), 401

        if not makh:
             return jsonify({"success": False, "message": "Không tìm thấy mã khách hàng trong token"}), 401
            
        customer = KhachHang.query.get(makh) 
        if not customer:
            return jsonify({"success": False, "message": "Không tìm thấy thông tin khách hàng"}), 401
        
        # === Lấy Dữ liệu ===
        data = request.get_json()
        dichvu_ids = data.get("madv_list", []) 
        manv = data.get("manv") # Sẽ là None nếu khách tự chọn
        ngaygio_str = data.get("ngaygio") 
        
        if not dichvu_ids or not ngaygio_str:
            return jsonify({"success": False, "message": "Thiếu thông tin dịch vụ hoặc thời gian"}), 400
        
        try:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        except:
            return jsonify({"success": False, "message": "Định dạng thời gian không hợp lệ"}), 400
        
        if ngaygio < datetime.now():
            return jsonify({"success": False, "message": "Không thể đặt lịch trong quá khứ"}), 400
        
        services = DichVu.query.filter(DichVu.madv.in_(dichvu_ids)).all()
        if len(services) != len(dichvu_ids):
            return jsonify({"success": False, "message": "Một số dịch vụ không tồn tại"}), 400
        
        total_duration = sum([s.thoiluong for s in services if s.thoiluong])
        if total_duration == 0: 
            total_duration = 60
        
        
        assigned_staff_manv = manv 

        if not manv:
            current_app.logger.info(f"Khách hàng {makh} yêu cầu tự sắp xếp. Bắt đầu tìm nhân viên rảnh...")
            
            available_staff_list = NhanVien.query.filter(
                NhanVien.trangthai == True,
                NhanVien.role == 'staff'
            ).order_by(func.random()).all()
            
            if not available_staff_list:
                current_app.logger.warning("Không tìm thấy nhân viên nào đang hoạt động.")
                return jsonify({
                    "success": False, 
                    "message": "Không có nhân viên nào trong hệ thống. Vui lòng thử lại sau."
                }), 404
            
            found_staff = False
            for staff in available_staff_list:
                is_available, _ = check_staff_availability(staff.manv, ngaygio, total_duration)
                
                if is_available:
                    assigned_staff_manv = staff.manv
                    found_staff = True
                    current_app.logger.info(f"Đã tìm thấy nhân viên rảnh: {staff.hoten} (ID: {staff.manv})")
                    break # Dừng vòng lặp
            
            if not found_staff:
                current_app.logger.warning(f"Không tìm thấy nhân viên nào rảnh vào lúc {ngaygio_str}")
                return jsonify({
                    "success": False, 
                    "message": "Không có nhân viên rảnh vào khung giờ này. Vui lòng chọn giờ khác hoặc chọn nhân viên cụ thể."
                }), 409
        
        else:
            is_available, conflicts = check_staff_availability(manv, ngaygio, total_duration)
            if not is_available:
                staff = NhanVien.query.get(manv)
                staff_name = staff.hoten if staff else "Nhân viên này"
                return jsonify({
                    "success": False,
                    "message": f"{staff_name} đã bận trong khung giờ này!",
                    "conflicts": conflicts
                }), 409 

        new_appointment = LichHen(
            makh=makh,
            ngaygio=ngaygio,
            manv=assigned_staff_manv, # <-- Dùng biến mới
            trangthai='confirmed', 
        )
        db.session.add(new_appointment)
        db.session.flush() 
        
        for madv in dichvu_ids:
            detail = ChiTietLichHen(
                malh=new_appointment.malh,
                madv=madv
            )
            db.session.add(detail)
        
        db.session.commit()
        
        staff = NhanVien.query.get(assigned_staff_manv) if assigned_staff_manv else None
        
        appointment_data = {
            'malh': new_appointment.malh,
            'ngaygio': new_appointment.ngaygio.strftime("%Y-%m-%d %H:%M:%S"),
            'staff_name': staff.hoten if staff else 'Sẽ được sắp xếp',
            'services': [{
                'tendv': s.tendv,
                'thoiluong': s.thoiluong if s.thoiluong else 60
            } for s in services]
        }
        
        if customer and customer.email:
            send_appointment_confirmation_email(
                customer.email,
                customer.hoten,
                appointment_data
            )
        
        return jsonify({
            "success": True,
            "message": "Đặt lịch thành công!",
            "appointment": {
                "malh": new_appointment.malh,
                "ngaygio": new_appointment.ngaygio.isoformat(),
                "trangthai": new_appointment.trangthai,
                "nhanvien": staff.hoten if staff else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating appointment: {e}")
        import traceback 
        traceback.print_exc() 
        return jsonify({"success": False, "message": "Đặt lịch thất bại. Vui lòng thử lại!"}), 500

@appointment_bp.route("/my-appointments", methods=["GET"])
@jwt_required()
def get_my_appointments():
    """Lấy danh sách lịch hẹn của khách hàng hiện tại"""
    try:
        identity = get_jwt_identity() 
        makh = None
        try:
            identity_str = str(identity)
            if ':' in identity_str:
                makh = int(identity_str.split(':')[1])
            else:
                makh = int(identity_str)
        except (IndexError, ValueError, TypeError) as e:
            current_app.logger.error(f"Không thể parse makh từ JWT identity: {identity} - Lỗi: {e}")
            return jsonify({"success": False, "message": "Định dạng token không hợp lệ"}), 401

        if not makh:
             return jsonify({"success": False, "message": "Không tìm thấy mã khách hàng trong token"}), 401
        
        appointments = LichHen.query.filter_by(makh=makh).order_by(LichHen.ngaygio.desc()).all()
        
        result = []
        for apt in appointments:
            services = []
            for detail in apt.chitiet:
                if detail.dichvu:
                    services.append(detail.dichvu.tendv)
            
            staff_name = "Chưa phân công"
            if apt.manv: 
                if apt.nhanvien:
                    staff_name = apt.nhanvien.hoten
                else:
                    staff = NhanVien.query.get(apt.manv)
                    if staff: staff_name = staff.hoten

            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "dichvu": ", ".join(services) if services else "Không có dịch vụ",
                "nhanvien": staff_name,
                "trangthai": apt.trangthai,
            })
        
        return jsonify({"success": True, "appointments": result}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting appointments: {e}")
        import traceback 
        traceback.print_exc()
        return jsonify({"success": False, "message": "Lỗi lấy danh sách lịch hẹn"}), 500

@appointment_bp.route("/<int:malh>/cancel", methods=["PUT"])
@jwt_required()
def cancel_my_appointment(malh):
    """Khách hàng hủy lịch hẹn của mình"""
    try:
        identity = get_jwt_identity() 
        makh = None
        
        try:
            identity_str = str(identity)
            if ':' in identity_str:
                makh = int(identity_str.split(':')[1])
            else:
                makh = int(identity_str)
        except (IndexError, ValueError, TypeError) as e:
            current_app.logger.error(f"Không thể parse makh từ JWT identity: {identity} - Lỗi: {e}")
            return jsonify({"success": False, "message": "Định dạng token không hợp lệ"}), 401

        if not makh:
             return jsonify({"success": False, "message": "Không tìm thấy mã khách hàng trong token"}), 401
        
        appointment = LichHen.query.get(malh)
        
        if not appointment:
            return jsonify({"success": False, "message": "Không tìm thấy lịch hẹn"}), 404
        
        if appointment.makh != makh:
            return jsonify({"success": False, "message": "Bạn không có quyền hủy lịch hẹn này"}), 403

        if appointment.trangthai in ['completed', 'cancelled']:
            return jsonify({"success": False, "message": f"Không thể hủy lịch hẹn đã {appointment.trangthai}"}), 400
        
        if appointment.ngaygio - datetime.now() < timedelta(hours=4):
            return jsonify({
                "success": False,
                "message": "Không thể hủy lịch hẹn trong vòng 4 giờ trước giờ hẹn. Vui lòng liên hệ spa!"
            }), 400
        
        appointment.trangthai = 'cancelled'
        
        db.session.commit()
        
        return jsonify({"success": True, "message": "Hủy lịch hẹn thành công"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling appointment: {e}")
        return jsonify({"success": False, "message": "Hủy lịch hẹn thất bại"}), 500

@appointment_bp.route("/available-slots", methods=["GET"])
def get_available_slots():
    """Lấy các khung giờ còn trống"""
    try:
        date_str = request.args.get("date")
        madv = request.args.get("madv")
        manv = request.args.get("manv")
        
        if not date_str:
            return jsonify({"success": False, "message": "Thiếu ngày"}), 400
        
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        duration = 60 
        if madv:
            service = DichVu.query.get(madv)
            if service:
                duration = service.thoiluong if service.thoiluong else 60

        slots = []
        for hour in range(8, 18): 
            for minute in [0, 30]:
                time_str = f"{hour:02d}:{minute:02d}"
                slot_datetime = datetime.combine(target_date, datetime.strptime(time_str, "%H:%M").time())
                
                if slot_datetime < datetime.now():
                    slots.append({
                        "time": time_str,
                        "available": False
                    })
                    continue

                is_available = True
                if manv:
                    is_available, _ = check_staff_availability(manv, slot_datetime, duration)
                
                slots.append({
                    "time": time_str,
                    "available": is_available
                })
        
        return jsonify({"success": True, "slots": slots}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting available slots: {e}")
        return jsonify({"success": False, "message": "Lỗi lấy khung giờ"}), 500
    
@appointment_bp.route("/check-availability", methods=["POST"])
@jwt_required(optional=True) 
def api_check_staff_availability():
    """API kiểm tra nhân viên có rảnh không"""
    data = request.get_json()
    manv = data.get("manv")
    ngaygio_str = data.get("ngaygio") 
    dichvu_ids = data.get("madv_list", []) 
    
    if not all([manv, ngaygio_str, dichvu_ids]):
        return jsonify({"success": False, "available": False, "message": "Thiếu thông tin"}), 400

    try:
        ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
    except Exception:
        return jsonify({"success": False, "available": False, "message": "Định dạng ngày giờ sai"}), 400

    services = DichVu.query.filter(DichVu.madv.in_(dichvu_ids)).all()
    if not services:
        return jsonify({"success": False, "available": False, "message": "Không tìm thấy dịch vụ"}), 400
    
    total_duration = sum([s.thoiluong for s in services if s.thoiluong])
    if total_duration == 0:
        total_duration = 60 
    
    try:
        is_available, conflicts = check_staff_availability(manv, ngaygio, total_duration)
        
        if is_available:
            return jsonify({"success": True, "available": True}), 200
        else:
            return jsonify({
                "success": True, 
                "available": False,
                "message": "Nhân viên đã bận",
                "conflicts": conflicts
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"Lỗi khi kiểm tra lịch rảnh: {e}")
        import traceback 
        traceback.print_exc() 
        return jsonify({"success": False, "available": False, "message": "Lỗi hệ thống khi kiểm tra"}), 500
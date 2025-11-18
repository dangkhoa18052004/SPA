from flask import Blueprint, request, jsonify, current_app, g
from ..extensions import db
from ..models import LichHen, KhachHang, DichVu, NhanVien, ChiTietLichHen, ChucVu # THÊM ChucVu
from ..decorators import roles_required
from datetime import datetime, date, timedelta
from sqlalchemy import and_, func, or_
from flask_mail import Message
from sqlalchemy.orm import joinedload 

appointment_manage_bp = Blueprint("appointment_manage", __name__)

def check_staff_availability(manv, ngaygio, thoiluong_phut):
    """
    ✅ FIXED: Kiểm tra nhân viên có rảnh không - CHÍNH XÁC
    (Hàm này giữ nguyên)
    """
    if not manv:
        return True, []
    
    # Thời gian lịch hẹn mới
    gio_batdau = ngaygio
    gio_ketthuc = ngaygio + timedelta(minutes=thoiluong_phut)
    
    # Lấy tất cả lịch hẹn của nhân viên trong ngày
    ngay = ngaygio.date()
    ngay_sau = ngay + timedelta(days=1)
    
    existing_appointments = LichHen.query.filter(
        and_(
            LichHen.manv == manv,
            LichHen.ngaygio >= ngay,
            LichHen.ngaygio < ngay_sau,
            LichHen.trangthai.in_(['pending', 'confirmed', 'in_progress'])
        )
    ).all()
    
    conflicting = []
    
    for apt in existing_appointments:
        # ✅ Tính TỔNG thời lượng của tất cả dịch vụ trong lịch hẹn
        tong_thoiluong = 0
        for detail in apt.chitiet:
            if detail.dichvu and detail.dichvu.thoiluong:
                tong_thoiluong += detail.dichvu.thoiluong
        
        # Nếu không có thời lượng, mặc định 60 phút
        if tong_thoiluong == 0:
            tong_thoiluong = 60
        
        apt_batdau = apt.ngaygio
        apt_ketthuc = apt.ngaygio + timedelta(minutes=tong_thoiluong)
        
        # ✅ Kiểm tra xung đột: Hai khoảng thời gian giao nhau
        if gio_batdau < apt_ketthuc and gio_ketthuc > apt_batdau:
            conflicting.append({
                'malh': apt.malh,
                'ngaygio': apt.ngaygio.strftime('%H:%M'),
                'ketthuc': apt_ketthuc.strftime('%H:%M'),
                'khachhang': apt.khachhang.hoten if apt.khachhang else 'N/A',
                'dichvu': ', '.join([d.dichvu.tendv for d in apt.chitiet if d.dichvu])
            })
    
    return len(conflicting) == 0, conflicting

# def send_appointment_confirmation_email(...) # Giữ nguyên như logic cũ

# ========== API MỚI: TÌM NHÂN VIÊN RẢNH CHO LỊCH HẸN (FIX 404) ==========
@appointment_manage_bp.route("/staff/available", methods=["GET"])
@roles_required('admin', 'manager', 'letan')
def get_available_staff_for_appointment():
    """ API được gọi bởi frontend để tìm nhân viên rảnh cho một ngày giờ và dịch vụ cụ thể. """
    try:
        ngaygio_str = request.args.get("ngaygio")
        madv_list_str = request.args.get("madv_list")
        
        if not ngaygio_str or not madv_list_str:
            return jsonify({"success": False, "msg": "Thiếu ngày giờ hoặc danh sách dịch vụ (madv_list)."}), 400
            
        # Chuyển đổi datetime
        try:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            return jsonify({"success": False, "msg": "Định dạng ngày giờ không hợp lệ (cần YYYY-MM-DDTHH:MM)."}), 400
            
        # Chuyển đổi danh sách dịch vụ và tính tổng thời lượng
        madv_list = [int(madv) for madv in madv_list_str.split(',')]
        
        total_duration = 0
        for madv in madv_list:
            service = DichVu.query.get(madv)
            if service and service.thoiluong:
                total_duration += service.thoiluong
        
        if total_duration == 0:
            total_duration = 60 # Default duration
            
        # Lấy danh sách tất cả Kỹ thuật viên (staff) đang hoạt động
        available_staff_list = NhanVien.query.filter(
            NhanVien.trangthai == True,
            NhanVien.role == 'staff'
        ).options(
            db.joinedload(NhanVien.chucvu)
        ).all()
        
        staff_results = []
        for staff in available_staff_list:
            # Sử dụng hàm kiểm tra tính khả dụng đã có
            is_available, _ = check_staff_availability(staff.manv, ngaygio, total_duration)
            
            if is_available:
                staff_results.append({
                    "manv": staff.manv,
                    "hoten": staff.hoten,
                    "chuyenmon": staff.chucvu.tencv if staff.chucvu else "Kỹ thuật viên"
                })

        return jsonify({
            "success": True,
            "available_staff": staff_results,
            "total_duration": total_duration
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi tìm nhân viên rảnh: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống khi tìm kiếm nhân viên rảnh"}), 500

# ... (Các routes khác giữ nguyên) ...

@appointment_manage_bp.route("/appointments/my-appointments", methods=["GET"])
def get_my_appointments():
# ... (Nội dung hàm giữ nguyên) ...
    try:
        customer = g.get('current_user')
        if not customer or not hasattr(customer, 'makh'):
            return jsonify({"success": False, "msg": "Vui lòng đăng nhập"}), 401
        
        appointments = LichHen.query.filter_by(
            makh=customer.makh
        ).order_by(
            LichHen.ngaygio.desc()
        ).all()
        
        result = []
        for apt in appointments:
            services = []
            total_duration = 0
            for detail in apt.chitiet:
                if detail.dichvu:
                    services.append({
                        "madv": detail.madv,
                        "tendv": detail.dichvu.tendv,
                        "gia": str(detail.dichvu.gia),
                        "thoiluong": detail.dichvu.thoiluong
                    })
                    if detail.dichvu.thoiluong:
                        total_duration += detail.dichvu.thoiluong
            
            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "dichvu": ", ".join([s['tendv'] for s in services]),
                "services": services,
                "nhanvien": apt.nhanvien.hoten if apt.nhanvien else "Chưa phân công",
                "trangthai": apt.trangthai,
                "total_duration": total_duration,
                "created_at": apt.created_at.isoformat() if hasattr(apt, 'created_at') and apt.created_at else None
            })
        
        return jsonify({"success": True, "appointments": result}), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy danh sách lịch hẹn: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500

@appointment_manage_bp.route("/appointments/check-availability", methods=["POST"])
def check_appointment_availability():
# ... (Nội dung hàm giữ nguyên) ...
    try:
        data = request.get_json()
        manv = data.get("manv")
        ngaygio_str = data.get("ngaygio")
        madv_list = data.get("madv_list", [])
        
        if not all([ngaygio_str, madv_list]):
            return jsonify({"msg": "Thiếu thông tin"}), 400
        
        try:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        except:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%d %H:%M:%S")
        
        total_duration = 0
        services_info = []
        for madv in madv_list:
            service = DichVu.query.get(madv)
            if service:
                duration = service.thoiluong if service.thoiluong else 60
                total_duration += duration
                services_info.append({
                    'tendv': service.tendv,
                    'thoiluong': duration
                })
        
        if total_duration == 0:
            total_duration = 60
        
        if manv:
            is_available, conflicts = check_staff_availability(manv, ngaygio, total_duration)
            
            if not is_available:
                nhanvien = NhanVien.query.get(manv)
                end_time = (ngaygio + timedelta(minutes=total_duration)).strftime('%H:%M')
                
                return jsonify({
                    "success": False,
                    "available": False,
                    "message": f"Nhân viên {nhanvien.hoten if nhanvien else 'này'} đã bận trong khung giờ {ngaygio.strftime('%H:%M')} - {end_time}",
                    "conflicts": conflicts,
                    "suggestion": "Vui lòng chọn khung giờ khác hoặc chọn nhân viên khác",
                    "total_duration": total_duration,
                    "services": services_info
                }), 200
        
        return jsonify({
            "success": True,
            "available": True,
            "message": "Khung giờ này còn trống",
            "duration": total_duration,
            "services": services_info,
            "end_time": (ngaygio + timedelta(minutes=total_duration)).strftime('%H:%M')
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi kiểm tra tính khả dụng: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@appointment_manage_bp.route("/appointments", methods=["POST"])
@roles_required('admin', 'manager', 'letan')
def create_appointment():
    try:
        data = request.get_json()
        makh = data.get("makh")
        madv_list = data.get("madv_list", [])
        ngaygio_str = data.get("ngaygio")
        manv = data.get("manv") 
        
        if not all([makh, madv_list, ngaygio_str]):
            return jsonify({"msg": "Thiếu thông tin bắt buộc"}), 400
        
        ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        
        total_duration = 0
        for madv in madv_list:
            service = DichVu.query.get(madv)
            if service and service.thoiluong:
                total_duration += service.thoiluong
        
        if total_duration == 0:
            total_duration = 60
        
        
        assigned_staff_manv = manv 
        
        if not manv:
            available_staff_list = NhanVien.query.filter(
                NhanVien.trangthai == True,
                NhanVien.role == 'staff'
            ).order_by(func.random()).all()
            
            found_staff = False
            for staff in available_staff_list:
                # Dùng hàm kiểm tra đã có
                is_available, _ = check_staff_availability(staff.manv, ngaygio, total_duration)
                
                if is_available:
                    assigned_staff_manv = staff.manv 
                    found_staff = True
                    break 
            
            if not found_staff:
                return jsonify({
                    "success": False, 
                    "msg": "Không có nhân viên rảnh vào khung giờ này. Vui lòng chọn giờ khác."
                }), 409
        
        else:
            is_available, conflicts = check_staff_availability(manv, ngaygio, total_duration)
            if not is_available:
                nhanvien = NhanVien.query.get(manv)
                return jsonify({
                    "success": False,
                    "msg": f"Nhân viên {nhanvien.hoten if nhanvien else 'này'} đã bận trong khung giờ này",
                    "conflicts": conflicts
                }), 409 
                
        new_apt = LichHen(
            makh=makh,
            ngaygio=ngaygio,
            manv=assigned_staff_manv,
            trangthai='confirmed'
        )
        db.session.add(new_apt)
        db.session.flush()
        
        for madv in madv_list:
            detail = ChiTietLichHen(
                malh=new_apt.malh,
                madv=madv
            )
            db.session.add(detail)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "msg": "Đặt lịch hẹn thành công",
            "malh": new_apt.malh,
            "manv_assigned": assigned_staff_manv
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi tạo lịch hẹn: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Đặt lịch hẹn thất bại"}), 500
    
@appointment_manage_bp.route("/appointments", methods=["GET"])
@roles_required('admin', 'manager', 'letan')
def get_all_appointments_admin():
# ... (Nội dung hàm giữ nguyên) ...
    try:
        query = db.session.query(LichHen).outerjoin(
            KhachHang, LichHen.makh == KhachHang.makh
        )
        
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        status = request.args.get("status")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(LichHen.ngaygio >= start_date)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)
            query = query.filter(LichHen.ngaygio < end_date)
            
        if status:
            query = query.filter(LichHen.trangthai == status)

        appointments = query.order_by(LichHen.ngaygio.desc()).all()
        
        result = []
        for apt in appointments:
            dichvu_ten = "N/A"
            
            # Lấy tên nhân viên từ apt (LichHen)
            nhanvien_ten = "Chưa gán"
            if apt.nhanvien: 
                nhanvien_ten = apt.nhanvien.hoten
            
            dichvu_count = len(apt.chitiet)
            
            if dichvu_count > 0:
                first_detail = apt.chitiet[0]
                
                if first_detail and first_detail.dichvu:
                    dichvu_ten = first_detail.dichvu.tendv
                    if dichvu_count > 1:
                        dichvu_ten += f" (+{dichvu_count - 1})"
            
            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "khachhang_hoten": apt.khachhang.hoten if apt.khachhang else "N/A",
                "dichvu_ten": dichvu_ten,
                "nhanvien_hoten": nhanvien_ten, 
                "trangthai": apt.trangthai
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy lịch hẹn (admin): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/my-schedule-list", methods=["GET"])
@roles_required('staff', 'letan')
def get_my_schedule_by_date_range():
# ... (Nội dung hàm giữ nguyên) ...
    try:
        staff = g.current_user
        
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        start_date = None
        end_date = None
        
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = date.today() 
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)
        else:
            end_date = start_date + timedelta(days=1) 
        
        query = LichHen.query.filter(
            LichHen.manv == staff.manv,
            LichHen.ngaygio >= start_date,
            LichHen.ngaygio < end_date,
        )

        appointments = query.options(
            db.joinedload(LichHen.khachhang),
            db.joinedload(LichHen.chitiet).joinedload(ChiTietLichHen.dichvu) 
        ).order_by(LichHen.ngaygio).all()
        
        result = []
        for apt in appointments:
            # Xử lý dịch vụ để hiển thị
            dichvu_ten = "N/A"
            dichvu_count = len(apt.chitiet)
            if dichvu_count > 0 and apt.chitiet[0].dichvu:
                dichvu_ten = apt.chitiet[0].dichvu.tendv
                if dichvu_count > 1:
                        dichvu_ten += f" (+{dichvu_count - 1})"
            
            # Trả về format chuẩn (giống yêu cầu của frontend)
            result.append({
                "malh": apt.malh,
                "ngaygio": apt.ngaygio.isoformat(),
                "khachhang_hoten": apt.khachhang.hoten if apt.khachhang else "Khách vãng lai",
                "dichvu_ten": dichvu_ten,
                "nhanvien_hoten": staff.hoten, 
                "trangthai": apt.trangthai,
                "ghichu": apt.ghichu if apt.ghichu else "" # Đảm bảo key ghichu có
            })
        
        return jsonify({"success": True, "appointments": result}), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy lịch của tôi: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500

def get_appointment_status_text(status):
# ... (Nội dung hàm giữ nguyên) ...
    status_map = {
        'pending': 'Chờ xác nhận',
        'confirmed': 'Đã xác nhận',
        'in_progress': 'Đang thực hiện',
        'completed': 'Đã hoàn thành',
        'cancelled': 'Đã hủy'
    }
    # Trả về giá trị từ map, hoặc trả về chính status nếu không tìm thấy
    return status_map.get(status, status)


@appointment_manage_bp.route("/appointments/<int:malh>", methods=["GET"])
@roles_required('admin', 'manager', 'letan', 'staff')
def get_appointment_detail(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
        
        staff = g.current_user
        if staff.role == 'staff' and apt.manv != staff.manv:
            return jsonify({"msg": "Bạn không có quyền xem lịch hẹn này"}), 403
        
        services = []
        for detail in apt.chitiet:
            if detail.dichvu:
                services.append({
                    "madv": detail.madv,
                    "tendv": detail.dichvu.tendv,
                    "gia": str(detail.dichvu.gia),
                    "thoiluong": detail.dichvu.thoiluong
                })
        
        result = {
            "malh": apt.malh,
            "ngaygio": apt.ngaygio.isoformat(),
            "khachhang": {
                "makh": apt.khachhang.makh,
                "hoten": apt.khachhang.hoten,
                "sdt": apt.khachhang.sdt,
                "email": apt.khachhang.email
            } if apt.khachhang else None,
            "nhanvien": {
                "manv": apt.nhanvien.manv,
                "hoten": apt.nhanvien.hoten
            } if apt.nhanvien else None,
            "services": services,
            "trangthai": apt.trangthai,
        }
        
        return jsonify({"success": True, "appointment": result}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy chi tiết lịch hẹn: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@appointment_manage_bp.route("/appointments/<int:malh>", methods=["PUT"])
@roles_required('admin', 'manager', 'letan', 'staff')
def update_appointment(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
        
        staff = g.current_user
        if staff.role == 'staff' and apt.manv != staff.manv:
            return jsonify({"msg": "Bạn không có quyền sửa lịch hẹn này"}), 403
        
        data = request.get_json()
        
        if "ngaygio" in data:
            apt.ngaygio = datetime.strptime(data["ngaygio"], "%Y-%m-%dT%H:%M")
        if "manv" in data:
            apt.manv = data["manv"]
        if "trangthai" in data:
            apt.trangthai = data["trangthai"]
        
        db.session.commit()
        
        return jsonify({"success": True, "msg": "Cập nhật lịch hẹn thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi cập nhật lịch hẹn: {e}")
        return jsonify({"msg": "Cập nhật thất bại"}), 500

@appointment_manage_bp.route("/appointments/<int:malh>/confirm", methods=["POST"])
@roles_required('admin', 'manager', 'letan', 'staff')
def confirm_appointment(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
        
        if apt.trangthai != 'pending':
            return jsonify({"msg": "Lịch hẹn không ở trạng thái chờ xác nhận"}), 400
        
        apt.trangthai = 'confirmed'
        db.session.commit()
        
        return jsonify({"success": True, "msg": "Xác nhận lịch hẹn thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi xác nhận lịch hẹn: {e}")
        return jsonify({"msg": "Xác nhận thất bại"}), 500

@appointment_manage_bp.route("/appointments/<int:malh>/cancel", methods=["POST"])
@roles_required('admin', 'manager', 'letan')
def cancel_appointment(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
        
        data = request.get_json()
        cancel_reason = data.get("reason", "")
        
        apt.trangthai = 'cancelled'
        
        db.session.commit()
        
        return jsonify({"success": True, "msg": "Hủy lịch hẹn thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi hủy lịch hẹn: {e}")
        return jsonify({"msg": "Hủy thất bại"}), 500

@appointment_manage_bp.route("/appointments/<int:malh>/complete", methods=["POST"])
@roles_required('admin', 'manager', 'letan', 'staff')
def complete_appointment(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
        
        apt.trangthai = 'completed'
        db.session.commit()
        
        return jsonify({"success": True, "msg": "Hoàn thành lịch hẹn"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi hoàn thành lịch hẹn: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@appointment_manage_bp.route("/appointments/<int:malh>/assign", methods=["POST"])
@roles_required('admin', 'manager', 'letan')
def assign_staff_to_appointment(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        data = request.get_json() or {}
        manv = data.get("manv")
        if not manv:
            return jsonify({"msg": "Thiếu manv"}), 400

        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404

        staff_member = NhanVien.query.get(manv)
        if not staff_member:
            return jsonify({"msg": "Không tìm thấy nhân viên"}), 404

        apt.manv = manv
        db.session.commit()

        return jsonify({"success": True, "msg": "Gán nhân viên thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi gán nhân viên: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

# ========== API THỐNG KÊ MỚI ==========
@appointment_manage_bp.route("/appointments/statistics", methods=["GET"])
@roles_required('admin', 'manager', 'letan', 'staff')
def get_appointment_statistics():
# ... (Nội dung hàm giữ nguyên) ...
    try:
        staff = g.current_user
        
        # Lấy tham số lọc
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        # Khởi tạo query
        if staff.role == 'staff':
            # Nhân viên chỉ thấy lịch của mình
            query = LichHen.query.filter(LichHen.manv == staff.manv)
        else:
            # Admin/Manager/Letan thấy tất cả
            query = LichHen.query
        
        # Áp dụng bộ lọc ngày
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(LichHen.ngaygio >= start_date)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)
            query = query.filter(LichHen.ngaygio < end_date)
        
        # Đếm tổng số
        total = query.count()
        
        # Đếm theo trạng thái
        pending = query.filter(LichHen.trangthai == 'pending').count()
        confirmed = query.filter(LichHen.trangthai == 'confirmed').count()
        in_progress = query.filter(LichHen.trangthai == 'in_progress').count()
        completed = query.filter(LichHen.trangthai == 'completed').count()
        cancelled = query.filter(LichHen.trangthai == 'cancelled').count()
        
        return jsonify({
            "success": True,
            "statistics": {
                "total": total,
                "pending": pending,
                "confirmed": confirmed,
                "in_progress": in_progress,
                "completed": completed,
                "cancelled": cancelled
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi lấy thống kê: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "msg": "Lỗi hệ thống"}), 500


@appointment_manage_bp.route("/appointments/book", methods=["POST"])
def book_appointment_customer():
# ... (Nội dung hàm giữ nguyên) ...
    try:
        customer = g.get('current_user')
        if not customer or not hasattr(customer, 'makh'):
            return jsonify({"msg": "Vui lòng đăng nhập với tài khoản khách hàng"}), 401
        
        data = request.get_json()
        madv_list = data.get("madv_list", [])
        ngaygio_str = data.get("ngaygio")
        manv = data.get("manv")
        
        if not all([madv_list, ngaygio_str]):
            return jsonify({"msg": "Thiếu thông tin bắt buộc"}), 400
        
        try:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%dT%H:%M")
        except:
            ngaygio = datetime.strptime(ngaygio_str, "%Y-%m-%d %H:%M:%S")
        
        if ngaygio < datetime.now():
            return jsonify({"msg": "Không thể đặt lịch trong quá khứ"}), 400
        
        total_duration = 0
        services_data = []
        for madv in madv_list:
            service = DichVu.query.get(madv)
            if not service:
                return jsonify({"msg": f"Dịch vụ {madv} không tồn tại"}), 404
            
            duration = service.thoiluong if service.thoiluong else 60
            total_duration += duration
            services_data.append({
                'madv': service.madv,
                'tendv': service.tendv,
                'thoiluong': duration,
                'gia': float(service.gia)
            })
        
        if total_duration == 0:
            total_duration = 60
        
        if manv:
            is_available, conflicts = check_staff_availability(manv, ngaygio, total_duration)
            if not is_available:
                nhanvien = NhanVien.query.get(manv)
                end_time = (ngaygio + timedelta(minutes=total_duration)).strftime('%H:%M')
                return jsonify({
                    "success": False,
                    "msg": f"Nhân viên {nhanvien.hoten if nhanvien else 'này'} đã bận trong khung giờ {ngaygio.strftime('%H:%M')} - {end_time}. Vui lòng chọn khung giờ khác hoặc chọn nhân viên khác.",
                    "conflicts": conflicts,
                    "total_duration": total_duration
                }), 409
        
        # Tạo lịch hẹn mới
        new_apt = LichHen(
            makh=customer.makh,
            ngaygio=ngaygio,
            manv=manv,
            trangthai='confirmed',
        )
        db.session.add(new_apt)
        db.session.flush()
        
        # Thêm chi tiết dịch vụ
        for madv in madv_list:
            detail = ChiTietLichHen(
                malh=new_apt.malh,
                madv=madv
            )
            db.session.add(detail)
        
        db.session.commit()
        
        # Lấy tên nhân viên
        nhanvien_name = "Sẽ được thông báo sau"
        if manv:
            nhanvien_obj = NhanVien.query.get(manv)
            nhanvien_name = nhanvien_obj.hoten if nhanvien_obj else "Sẽ được thông báo sau"
        
        current_app.logger.info(f"Appointment {new_apt.malh} created successfully for customer {customer.makh}")
        
        return jsonify({
            "success": True,
            "msg": "Đặt lịch hẹn thành công! Chúng tôi đã gửi email xác nhận đến bạn.",
            "malh": new_apt.malh,
            "appointment": {
                "malh": new_apt.malh,
                "ngaygio": ngaygio.isoformat(),
                "trangthai": "confirmed",
                "services": [s['tendv'] for s in services_data],
                "nhanvien": nhanvien_name if manv else None,
                "total_duration": total_duration,
                "end_time": (ngaygio + timedelta(minutes=total_duration)).strftime('%H:%M')
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi đặt lịch hẹn: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Đặt lịch hẹn thất bại. Vui lòng thử lại"}), 500


@appointment_manage_bp.route("/appointments/<int:malh>/cancel-customer", methods=["PUT"])
def cancel_my_appointment(malh):
# ... (Nội dung hàm giữ nguyên) ...
    try:
        customer = g.get('current_user')
        if not customer or not hasattr(customer, 'makh'):
            return jsonify({"msg": "Vui lòng đăng nhập"}), 401
        
        apt = LichHen.query.get(malh)
        if not apt:
            return jsonify({"msg": "Không tìm thấy lịch hẹn"}), 404
        
        # Kiểm tra quyền sở hữu
        if apt.makh != customer.makh:
            return jsonify({"msg": "Bạn không có quyền hủy lịch hẹn này"}), 403
        
        # Chỉ cho phép hủy nếu trạng thái là pending hoặc confirmed
        if apt.trangthai not in ['pending', 'confirmed']:
            return jsonify({"msg": f"Không thể hủy lịch hẹn ở trạng thái '{apt.trangthai}'"}), 400
        
        # Kiểm tra thời gian - không cho hủy trong vòng 4 giờ
        time_until_appointment = apt.ngaygio - datetime.now()
        if time_until_appointment < timedelta(hours=4):
            return jsonify({
                "success": False,
                "msg": "Không thể hủy lịch hẹn trong vòng 4 giờ trước giờ hẹn. Vui lòng liên hệ spa để được hỗ trợ!"
            }), 400
        
        # Hủy lịch hẹn
        apt.trangthai = 'cancelled'
        
        db.session.commit()
        
        return jsonify({"success": True, "msg": "Hủy lịch hẹn thành công"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi hủy lịch hẹn: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "Hủy lịch hẹn thất bại"}), 500
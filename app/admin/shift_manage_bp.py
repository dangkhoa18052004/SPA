from flask_mail import Message
import threading
from flask import Blueprint, request, jsonify, current_app, g
from ..extensions import db
from ..models import CaLam, NhanVien, DangKyCaLam, nhanvien_calam, ChucVu,BangLuongChiTiet, Luong
from ..decorators import roles_required 
from datetime import date, datetime
from decimal import Decimal
from .. import mail
from sqlalchemy.orm import joinedload
from sqlalchemy import extract


shift_manage_bp = Blueprint("shift_manage", __name__)

def _calculate_and_save_daily_salary(nhanvien, calam):
    """
    Hàm helper: Tự động tính lương cho 1 ca làm và cập nhật lương tháng.
    (Đã sửa lỗi float/Decimal)
    """
    try:
        existing_daily_salary = BangLuongChiTiet.query.filter_by(maca=calam.maca, manv=nhanvien.manv).first()
        if existing_daily_salary:
            current_app.logger.info(f"Ca {calam.maca} đã được tính lương. Bỏ qua.")
            return True 

        chucvu = nhanvien.chucvu
        if not (chucvu and chucvu.dongiagio and calam.sogio):
            raise ValueError(f"Thiếu Đơn giá giờ (dongiagio) hoặc Số giờ (sogio) cho NV {nhanvien.manv} ca {calam.maca}")

        # === SỬA LỖI: Dùng Decimal thay vì float ===
        dongia = Decimal(chucvu.dongiagio or '0')
        sogio = Decimal(calam.sogio or '0')
        luong_ca = dongia * sogio # Phép tính Decimal * Decimal = Decimal

        thang = calam.ngay.month
        nam = calam.ngay.year
        
        luong_thang = Luong.query.filter_by(manv=nhanvien.manv, thang=thang, nam=nam).first()
        if not luong_thang:
            luong_thang = Luong(
                manv=nhanvien.manv, 
                thang=thang, 
                nam=nam, 
                luongcoban=Decimal('0'), # Đặt là Decimal('0')
                thuong=Decimal('0'),
                khautru=Decimal('0'),
                tongluong=Decimal('0')
            )
            db.session.add(luong_thang)
            db.session.flush() 

        new_daily_salary = BangLuongChiTiet(
            manv=nhanvien.manv,
            maca=calam.maca,
            maluong_thang=luong_thang.maluong, 
            ngay_lam=calam.ngay,
            sogio_lam=sogio,
            dongia_gio=dongia,
            luong_ca=luong_ca
        )
        db.session.add(new_daily_salary)

        # === SỬA LỖI: Đảm bảo mọi phép tính đều là Decimal ===
        luong_thang.luongcoban = (luong_thang.luongcoban or Decimal('0')) + luong_ca
        luong_thang.tongluong = (luong_thang.luongcoban or Decimal('0')) + (luong_thang.thuong or Decimal('0')) - (luong_thang.khautru or Decimal('0'))
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"LỖI NGHIÊM TRỌNG KHI TÍNH LƯƠNG NGÀY (Ca {calam.maca}): {e}")
        return False
# API CHO QUẢN LÝ (ADMIN / MANAGER)         
def send_async_email(app, msg):
    """Hàm chạy trong thread riêng để gửi mail (tránh làm chậm API)."""
    with app.app_context():
        try:
            mail.send(msg)
            current_app.logger.info(f"Đã gửi email thành công tới {msg.recipients}")
        except Exception as e:
            current_app.logger.error(f"Lỗi khi gửi email: {e}")

def send_shift_notification_email(employee_email, employee_name, shift):
    """Soạn và gửi email thông báo ca làm."""
    if not employee_email:
        current_app.logger.warning(f"Nhân viên {employee_name} không có email. Bỏ qua gửi mail.")
        return

    # Lấy app context hiện tại
    app = current_app._get_current_object()

    # Định dạng lại ngày giờ cho đẹp
    ngay_str = shift.ngay.strftime('%d/%m/%Y')
    gio_bd = shift.giobatdau.strftime('%H:%M')
    gio_kt = shift.gioketthuc.strftime('%H:%M')

    # Soạn email
    msg_title = f"[Bin Spa] Bạn có lịch làm việc mới vào ngày {ngay_str}"
    msg_body = f"""
    Chào {employee_name},

    Bạn có một ca làm việc mới tại Bin Spa.

    Chi tiết ca làm:
    - Ngày: {ngay_str}
    - Giờ: {gio_bd} - {gio_kt}

    Vui lòng kiểm tra lịch làm việc của bạn trên hệ thống.

    Trân trọng,
    Bin Spa.
    """

    msg = Message(subject=msg_title,
                  recipients=[employee_email], 
                  body=msg_body)

    thr = threading.Thread(target=send_async_email, args=[app, msg])
    thr.start()

@shift_manage_bp.route("/shifts", methods=["GET"])
@roles_required('admin', 'manager')
def get_shifts():
    """(Admin/Manager) Lấy danh sách tất cả các ca làm, có hỗ trợ lọc."""
    try:
        date_from_str = request.args.get("date_from")
        date_to_str = request.args.get("date_to")
        assignment_status = request.args.get("assignment")

        # KHẮC PHỤC: Bỏ joinedload ban đầu để tránh lỗi.
        query = CaLam.query.order_by(CaLam.ngay.desc(), CaLam.giobatdau.desc())

        # 2. ÁP DỤNG LỌC THEO NGÀY (Giữ nguyên)
        if date_from_str:
            # ... (Logic lọc ngày) ...
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                query = query.filter(CaLam.ngay >= date_from)
            except ValueError:
                return jsonify({"msg": "Định dạng ngày bắt đầu không hợp lệ"}), 400

        if date_to_str:
            # ... (Logic lọc ngày) ...
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                query = query.filter(CaLam.ngay <= date_to)
            except ValueError:
                return jsonify({"msg": "Định dạng ngày kết thúc không hợp lệ"}), 400

        # 3. ÁP DỤNG LỌC THEO TRẠNG THÁI GÁN (Giữ nguyên logic JOIN)
        if assignment_status:
            if assignment_status == 'unassigned':
                query = query.outerjoin(nhanvien_calam, CaLam.maca == nhanvien_calam.c.maca) \
                             .filter(nhanvien_calam.c.manv == None)
            
            elif assignment_status == 'assigned':
                # Đảm bảo sử dụng joinedload HOẶC lazy load sau này, không cần thiết ở đây.
                query = query.join(nhanvien_calam, CaLam.maca == nhanvien_calam.c.maca).distinct()

        
        shifts = query.all()
        
        # Phần vòng lặp này sẽ tự động kích hoạt lazy loading và hoạt động bình thường
        result = []
        for s in shifts:
            assigned_staff_list = []
            for nv in s.nhanvien: # <--- Lazy load kích hoạt ở đây
                chucvu_obj = ChucVu.query.get(nv.macv) 
                chucvu_ten = chucvu_obj.tencv if chucvu_obj else "N/A"
                
                assigned_staff_list.append({
                    "manv": nv.manv, 
                    "hoten": nv.hoten,
                    "chucvu": chucvu_ten
                })
            
            result.append({
                "maca": s.maca, 
                "ngay": s.ngay.isoformat(), 
                "start_time": s.giobatdau.strftime('%H:%M'), 
                "end_time": s.gioketthuc.strftime('%H:%M'),
                "sogio": s.sogio, 
                "assigned_staff": assigned_staff_list 
            })
            
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy danh sách ca làm: {e}")
        return jsonify({"msg": "Lỗi hệ thống hoặc lỗi xác thực"}), 500
    
@shift_manage_bp.route("/shifts", methods=["POST"])
@roles_required('admin', 'manager')
def create_shifts():
    """(Admin/Manager) Tạo một hoặc nhiều ca làm việc."""
    data = request.get_json()
    shifts_to_process = [] 
    if isinstance(data, dict): 
        shifts_to_process.append(data)
    elif isinstance(data, list): 
        shifts_to_process = data
    else: 
        return jsonify({"msg": "Dữ liệu không hợp lệ."}), 400
    try:

        for info in shifts_to_process: 
            if not all(k in info for k in ("ngay", "giobatdau", "gioketthuc")): 
                raise ValueError("Thiếu thông tin ca làm.")
            ngay_dt = datetime.strptime(info["ngay"], "%Y-%m-%d").date()
            start_time = datetime.strptime(info["giobatdau"], "%H:%M").time()
            end_time = datetime.strptime(info["gioketthuc"], "%H:%M").time()
            today = date.today()
            start_datetime = datetime.combine(today, start_time)
            end_datetime = datetime.combine(today, end_time)
            duration = end_datetime - start_datetime
            so_gio = duration.total_seconds() / 3600.0

            new_shift = CaLam(
                ngay=ngay_dt, 
                giobatdau=start_time, 
                gioketthuc=end_time,
                sogio=so_gio,
                hesoluong=info.get("hesoluong", 1) 
            )
            db.session.add(new_shift)
            
        db.session.commit()
        return jsonify({"msg": f"Đã tạo thành công {len(shifts_to_process)} ca làm mới."}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi tạo ca làm: {e}")
        return jsonify({"msg": str(e)}), 500
    
@shift_manage_bp.route("/shifts/<int:maca>", methods=["PUT"])
@roles_required('admin', 'manager')
def update_shift(maca):
    """(Admin/Manager) Cập nhật thông tin một ca làm."""
    
    # 1. Tìm ca làm
    shift = CaLam.query.get(maca)
    if not shift:
        return jsonify({"msg": "Không tìm thấy ca làm"}), 404

    data = request.get_json()
    
    try:
        # 2. Cập nhật các trường
        if "ngay" in data:
            shift.ngay = datetime.strptime(data["ngay"], "%Y-%m-%d").date()
        start_time_str = data.get("giobatdau")
        end_time_str = data.get("gioketthuc")
        
        if start_time_str:
            shift.giobatdau = datetime.strptime(start_time_str, "%H:%M").time()
        if end_time_str:
            shift.gioketthuc = datetime.strptime(end_time_str, "%H:%M").time()
        # 3. Tính toán lại số giờ
        if start_time_str and end_time_str:
            today = date.today()
            start_dt = datetime.combine(today, shift.giobatdau)
            end_dt = datetime.combine(today, shift.gioketthuc)
            duration = end_dt - start_dt
            shift.sogio = duration.total_seconds() / 3600.0
        # 4. Lưu thay đổi
        db.session.commit()
        return jsonify({"msg": "Cập nhật ca làm thành công"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi cập nhật ca làm {maca}: {e}")
        return jsonify({"msg": "Cập nhật thất bại"}), 500

@shift_manage_bp.route("/shifts/<int:maca>", methods=["DELETE"])
@roles_required('admin', 'manager')
def delete_shift(maca):
    """(Admin/Manager) Xóa một ca làm."""
    shift = CaLam.query.get(maca)
    if not shift: return jsonify({"msg": "Không tìm thấy ca làm"}), 404
    try:
        # Xóa đăng ký liên quan
        DangKyCaLam.query.filter_by(maca=maca).delete()
        # Xóa gán nhân viên liên quan
        stmt = nhanvien_calam.delete().where(nhanvien_calam.c.maca == maca)
        db.session.execute(stmt)
        # Xóa ca làm
        db.session.delete(shift)
        db.session.commit()
        return jsonify({"msg": "Xóa ca làm thành công"}), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi xóa ca làm: {e}"); return jsonify({"msg": "Xóa thất bại"}), 500

@shift_manage_bp.route("/shifts/registrations/pending", methods=["GET"])
@roles_required('admin', 'manager')
def get_pending_registrations():
    """(Admin/Manager) Xem danh sách các yêu cầu đăng ký ca làm đang chờ."""
    try:
        pending_regs = db.session.query(DangKyCaLam).filter(
            DangKyCaLam.trangthai == 'pending'
        ).join(NhanVien).join(CaLam).order_by(DangKyCaLam.ngaydangky.asc()).all()
        result = []
        for reg in pending_regs:
            result.append({
                "reg_id": reg.id, "ngaydangky": reg.ngaydangky.isoformat(),
                "nhanvien": {"manv": reg.nhanvien.manv, "hoten": reg.nhanvien.hoten},
                "calam": {"maca": reg.calam.maca, "ngay": reg.calam.ngay.isoformat(),
                          "giobatdau": reg.calam.giobatdau.strftime('%H:%M'),
                          "gioketthuc": reg.calam.gioketthuc.strftime('%H:%M')}
            })
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy danh sách đăng ký chờ: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@shift_manage_bp.route("/shifts/unassign", methods=["DELETE"])
@roles_required('admin', 'manager')
def unassign_staff_from_shift():
    """(Admin/Manager) Xóa một nhân viên khỏi một ca làm (Đã cập nhật hoàn trả lương)."""
    
    data = request.get_json()
    maca, manv = data.get("maca"), data.get("manv")
    if not maca or not manv: 
        return jsonify({"msg": "Thiếu mã ca hoặc mã nhân viên"}), 400
        
    shift = CaLam.query.get(maca)
    staff = NhanVien.query.get(manv)
    if not shift or not staff: 
        return jsonify({"msg": "Không tìm thấy ca làm hoặc nhân viên"}), 404
        
    try:
        # 1. Kiểm tra xem có gán không
        if shift not in staff.calam:
            return jsonify({"msg": f"NV {manv} không được gán cho ca {maca}."}), 404

        # 2. Xóa gán ca (Thao tác chính)
        staff.calam.remove(shift)
        
        # 3. HOÀN TRẢ LƯƠNG (Logic mới)
        # Tìm bản ghi lương chi tiết của ca này
        daily_salary_entry = BangLuongChiTiet.query.filter_by(maca=maca, manv=manv).first()
        
        if daily_salary_entry:
            luong_ca_bi_huy = Decimal(daily_salary_entry.luong_ca or '0')
            maluong_thang = daily_salary_entry.maluong_thang
            
            # Xóa bản ghi lương chi tiết
            db.session.delete(daily_salary_entry)
            
            # Cập nhật lại lương tháng (nếu có)
            if maluong_thang:
                luong_thang = Luong.query.get(maluong_thang)
                if luong_thang:
                    luong_thang.luongcoban = (luong_thang.luongcoban or Decimal('0')) - luong_ca_bi_huy
                    luong_thang.tongluong = (luong_thang.luongcoban or Decimal('0')) + (luong_thang.thuong or Decimal('0')) - (luong_thang.khautru or Decimal('0'))
        else:
            current_app.logger.warning(f"Không tìm thấy bản ghi lương chi tiết cho ca {maca} / nv {manv} để hoàn trả.")

        # 4. Commit tất cả
        db.session.commit()
        return jsonify({"msg": f"Đã xóa NV {manv} khỏi ca {maca} (Đã hoàn trả lương)."}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi xóa NV khỏi ca: {e}")
        return jsonify({"msg": "Xóa thất bại"}), 500

@shift_manage_bp.route("/shifts/assign", methods=["POST"])
@roles_required('admin', 'manager')
def assign_staff_to_shift():
    """(Admin/Manager) Gán một nhân viên vào một ca làm (Đã thêm tính lương ngày)."""
    
    data = request.get_json()
    maca, manv = data.get("maca"), data.get("manv")
    
    if not maca or not manv: 
        return jsonify({"msg": "Thiếu mã ca hoặc mã nhân viên"}), 400
    
    shift = CaLam.query.get(maca)
    staff = NhanVien.query.get(manv) 
    
    if not shift or not staff: 
        return jsonify({"msg": "Không tìm thấy ca làm hoặc nhân viên"}), 404
    
    if shift in staff.calam: 
        return jsonify({"msg": f"NV {manv} đã được gán vào ca {maca}."}), 409
    
    try:
        staff.calam.append(shift)
        if not _calculate_and_save_daily_salary(staff, shift):
            raise Exception("Tính lương ngày thất bại, xem log để biết chi tiết.")
        db.session.commit()
        try:
            send_shift_notification_email(staff.email, staff.hoten, shift)
        except Exception as e:
            current_app.logger.error(f"Gán ca thành công, NHƯNG gửi mail thất bại: {e}")
        
        return jsonify({"msg": f"Đã gán thành công NV {manv} vào ca {maca} (Đã tính lương)"}), 200
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi gán NV vào ca: {e}")
        return jsonify({"msg": f"Gán thất bại: {e}"}), 500

@shift_manage_bp.route("/shifts/registrations/<int:reg_id>/approve", methods=["PUT"])
@roles_required('admin', 'manager')
def approve_shift_registration(reg_id):
    """(Admin/Manager) Phê duyệt một yêu cầu đăng ký ca làm (Đã thêm tính lương ngày)."""
    reg = DangKyCaLam.query.get(reg_id)
    if not reg: 
        return jsonify({"msg": "Không tìm thấy yêu cầu đăng ký"}), 404
    if reg.trangthai != 'pending': 
        return jsonify({"msg": "Yêu cầu này đã được xử lý"}), 400
    try:
        staff = NhanVien.query.get(reg.manv)
        shift = CaLam.query.get(reg.maca)
        if not shift or not staff:
             return jsonify({"msg": "Không tìm thấy nhân viên hoặc ca làm liên quan"}), 404
        reg.trangthai = 'approved'
        if shift not in staff.calam:
             staff.calam.append(shift)
        if not _calculate_and_save_daily_salary(staff, shift):
            raise Exception("Tính lương ngày thất bại, xem log để biết chi tiết.")
        db.session.commit()
        try:
            send_shift_notification_email(staff.email, staff.hoten, shift)
        except Exception as e:
            current_app.logger.error(f"Duyệt ca thành công, NHƯNG gửi mail thất bại: {e}")

        return jsonify({"msg": "Phê duyệt thành công (Đã tính lương)."}), 200
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi phê duyệt ĐK ca: {e}")
        return jsonify({"msg": f"Phê duyệt thất bại: {e}"}), 500
    
# API XEM LỊCH CỦA QUẢN LÝ / LỄ TÂN                
@shift_manage_bp.route("/all-schedules", methods=["GET"])
@roles_required('letan','staff', 'admin', 'manager') 
def get_all_schedules():
    """(Lễ tân/Admin/Manager) Xem toàn bộ lịch làm của tất cả nhân viên."""
    start_date_str, end_date_str = request.args.get("start_date"), request.args.get("end_date")
    if not start_date_str or not end_date_str: return jsonify({"msg": "Vui lòng cung cấp start_date và end_date"}), 400
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date(); end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        all_shifts = CaLam.query.filter(CaLam.ngay.between(start_date, end_date)).order_by(CaLam.ngay, CaLam.giobatdau).all()
        
        schedule_by_date = {}
        for shift in all_shifts:
            date_str = shift.ngay.isoformat()
            if date_str not in schedule_by_date: schedule_by_date[date_str] = []
            
            assigned_staff = [{"manv": s.manv, "hoten": s.hoten} for s in shift.nhanvien]
            
            schedule_by_date[date_str].append({
                "maca": shift.maca, 
                "start_time": shift.giobatdau.strftime('%H:%M'), 
                "end_time": shift.gioketthuc.strftime('%H:%M'), 
                "assigned_staff": assigned_staff 
            })
        return jsonify(schedule_by_date), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy toàn bộ lịch làm việc: {e}"); return jsonify({"msg": "Lỗi hệ thống"}), 500

#  API CHO NHÂN VIÊN (ĐĂNG KÝ)               
@shift_manage_bp.route("/shifts/register", methods=["POST"])
@roles_required('letan', 'staff', 'manager', 'admin') 
def register_for_shift():
    """(Mọi nhân viên) Đăng ký vào một hoặc nhiều ca làm trống."""
    staff = g.current_user 
    data = request.get_json(); registrations_to_process = []
    
    if isinstance(data, dict): registrations_to_process.append(data)
    elif isinstance(data, list): registrations_to_process = data
    else: return jsonify({"msg": "Dữ liệu không hợp lệ."}), 400
    
    try:
        created_regs = 0
        for info in registrations_to_process:
            maca = info.get("maca")
            if not maca: raise ValueError("Thiếu mã ca (maca).")
            if not CaLam.query.get(maca): continue
            
            existing = DangKyCaLam.query.filter_by(manv=staff.manv, maca=maca).first()
            assigned = db.session.query(nhanvien_calam).filter_by(manv=staff.manv, maca=maca).first()
            if existing or assigned: continue
            
            new_reg = DangKyCaLam(manv=staff.manv, maca=maca, trangthai='pending'); 
            db.session.add(new_reg); 
            created_regs += 1
            
        db.session.commit()
        return jsonify({"msg": f"Đã gửi thành công {created_regs} yêu cầu đăng ký."}), 201
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi đăng ký ca làm: {e}"); return jsonify({"msg": str(e)}), 500
    

@shift_manage_bp.route("/shifts/registrations/<int:reg_id>/reject", methods=["PUT"])
@roles_required('admin', 'manager')
def reject_shift_registration(reg_id):
    """(Admin/Manager) Từ chối một yêu cầu đăng ký ca làm."""
    
    reg = DangKyCaLam.query.get(reg_id)
    if not reg: 
        return jsonify({"msg": "Không tìm thấy yêu cầu đăng ký"}), 404
    if reg.trangthai != 'pending': 
        return jsonify({"msg": "Yêu cầu này đã được xử lý"}), 400
        
    try:
        reg.trangthai = 'rejected'
        db.session.commit()
        
        # (Bạn có thể thêm logic gửi email thông báo từ chối ở đây)
        
        return jsonify({"msg": "Đã từ chối yêu cầu thành công."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi từ chối ĐK ca: {e}")
        return jsonify({"msg": "Từ chối thất bại"}), 500

@shift_manage_bp.route("/my-schedule-list", methods=["GET"])
@roles_required('letan', 'staff', 'manager', 'admin')
def get_my_schedule_list():
    staff = g.current_user

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if not start_date_str or not end_date_str:
        return jsonify({"success": False, "message": "Thiếu start_date hoặc end_date"}), 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        results = []

        approved_shifts = staff.calam.filter(
            CaLam.ngay.between(start_date, end_date)
        ).all()

        for ca in approved_shifts:
            colleagues = []
            for nv in ca.nhanvien:
                if nv.manv != staff.manv:
                    colleagues.append({
                        "hoten": nv.hoten,
                        "chucvu": nv.chucvu.tencv if nv.chucvu else "N/A"
                    })

            results.append({
                "ngay": ca.ngay.isoformat(),
                "ten_ca": f"Ca #{ca.maca}",
                "giobatdau": ca.giobatdau.strftime('%H:%M'),
                "gioketthuc": ca.gioketthuc.strftime('%H:%M'),
                "trangthai_code": "approved",
                "trangthai_text": "Đã duyệt",
                "colleagues": colleagues
            })

        pending_regs = DangKyCaLam.query.filter(
            DangKyCaLam.manv == staff.manv,
            DangKyCaLam.trangthai == 'pending'
        ).join(CaLam).filter(
            CaLam.ngay.between(start_date, end_date)
        ).all()

        for reg in pending_regs:
            colleagues = []
            for nv in reg.calam.nhanvien:
                colleagues.append({
                    "hoten": nv.hoten,
                    "chucvu": nv.chucvu.tencv if nv.chucvu else "N/A"
                })

            results.append({
                "ngay": reg.calam.ngay.isoformat(),
                "ten_ca": f"Ca #{reg.calam.maca}",
                "giobatdau": reg.calam.giobatdau.strftime('%H:%M'),
                "gioketthuc": reg.calam.gioketthuc.strftime('%H:%M'),
                "trangthai_code": "pending",
                "trangthai_text": "Chờ duyệt",
                "colleagues": colleagues
            })

        results.sort(key=lambda x: x['ngay'])

        return jsonify({"success": True, "schedule": results}), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy lịch của NV {staff.manv}: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500
from flask import Blueprint, request, jsonify, current_app, render_template, make_response
from ..extensions import db
from ..models import Luong, NhanVien, CaLam, nhanvien_calam, BangLuongChiTiet, ChucVu
from ..decorators import roles_required
from sqlalchemy import extract, func, and_
from datetime import datetime
from weasyprint import HTML
from decimal import Decimal

salary_manage_bp = Blueprint("salary_manage", __name__)

@salary_manage_bp.route("/salaries/calculate", methods=["POST"])
@roles_required('admin', 'manager')
def calculate_salaries():
    """ (ĐÃ CẬP NHẬT) Tổng hợp lương, thưởng, và khấu trừ từ Bảng Chi Tiết vào Bảng Lương Tháng. """
    data = request.get_json()
    thang, nam = data.get("thang"), data.get("nam")
    if not thang or not nam: 
        return jsonify({"msg": "Cần cung cấp tháng và năm"}), 400
    
    try:
        all_staff = NhanVien.query.all()
        
        for staff in all_staff:
            luong_thang = Luong.query.filter_by(manv=staff.manv, thang=thang, nam=nam).first()
            if not luong_thang:
                luong_thang = Luong(manv=staff.manv, thang=thang, nam=nam, luongcoban=Decimal('0'), thuong=Decimal('0'), khautru=Decimal('0'), tongluong=Decimal('0'))
                db.session.add(luong_thang)
                db.session.flush() 

            # === SỬA: Tính tổng cả 3 cột ===
            salary_summary = db.session.query(
                func.sum(BangLuongChiTiet.luong_ca),
                func.sum(BangLuongChiTiet.thuong_ca),
                func.sum(BangLuongChiTiet.khautru_ca)
            ).filter(
                BangLuongChiTiet.manv == staff.manv,
                extract('month', BangLuongChiTiet.ngay_lam) == thang,
                extract('year', BangLuongChiTiet.ngay_lam) == nam
            ).first()

            total_base = salary_summary[0] or Decimal('0')
            total_bonus = salary_summary[1] or Decimal('0')
            total_deduction = salary_summary[2] or Decimal('0')

            # Cập nhật bảng lương tháng
            luong_thang.luongcoban = total_base
            luong_thang.thuong = total_bonus
            luong_thang.khautru = total_deduction
            luong_thang.tongluong = (total_base + total_bonus - total_deduction)
            
            # Cập nhật liên kết
            BangLuongChiTiet.query.filter(
                BangLuongChiTiet.manv == staff.manv,
                extract('month', BangLuongChiTiet.ngay_lam) == thang,
                extract('year', BangLuongChiTiet.ngay_lam) == nam,
                BangLuongChiTiet.maluong_thang == None
            ).update({"maluong_thang": luong_thang.maluong})

        db.session.commit()
        return jsonify({"msg": f"Đã tổng hợp lương tháng {thang}/{nam} thành công."}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi tổng hợp lương: {e}")
        return jsonify({"msg": "Tổng hợp lương thất bại"}), 500

@salary_manage_bp.route("/salaries", methods=["GET"])
@roles_required('admin', 'manager')
def get_all_salaries():
    """ (ĐÃ CẬP NHẬT) Gửi thêm thuong_ca và khautru_ca khi lọc theo ngày. """
    try:
        filter_type = request.args.get('filter_type', 'month')
        
        if filter_type == 'day':
            day_str = request.args.get('day')
            if not day_str:
                return jsonify({"msg": "Vui lòng chọn ngày"}), 400
            selected_date = datetime.strptime(day_str, '%Y-%m-%d').date()
            
            daily_salaries = db.session.query(BangLuongChiTiet, NhanVien, ChucVu).join(
                NhanVien, BangLuongChiTiet.manv == NhanVien.manv
            ).join(
                ChucVu, NhanVien.macv == ChucVu.macv
            ).filter(
                BangLuongChiTiet.ngay_lam == selected_date
            ).all()

            result = [{
                "filter_type": "day", 
                "id_chitiet": blct.id, # ID của bảng chi tiết
                "hoten": nv.hoten,
                "ngay_lam": blct.ngay_lam.isoformat(),
                "chucvu": cv.tencv,
                "sogio_lam": str(blct.sogio_lam),
                "dongia_gio": str(blct.dongia_gio),
                "luong_ca": str(blct.luong_ca),
                "thuong_ca": str(blct.thuong_ca),     # <-- THÊM MỚI
                "khautru_ca": str(blct.khautru_ca)  # <-- THÊM MỚI
            } for blct, nv, cv in daily_salaries if nv.role != 'admin']
            
        else:
            # Lọc theo tháng (Giữ nguyên logic)
            month_year_str = request.args.get('month_year') 
            if not month_year_str:
                now = datetime.now()
                thang, nam = now.month, now.year
            else:
                selected_month = datetime.strptime(month_year_str, '%Y-%m')
                thang, nam = selected_month.month, selected_month.year

            salaries = Luong.query.filter_by(thang=thang, nam=nam).all()
            result = [{
                "filter_type": "month",
                "maluong": s.maluong, 
                "manv": s.manv, 
                "hoten": s.nhanvien.hoten if s.nhanvien else 'N/A', 
                "thang": s.thang, 
                "nam": s.nam, 
                "tongluong": str(s.tongluong),
                "luongcoban": str(s.luongcoban),
                "thuong": str(s.thuong),
                "khautru": str(s.khautru)
            } for s in salaries if s.nhanvien and s.nhanvien.role != 'admin']
            
        return jsonify(result), 200
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy LS lương: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

# === API MỚI: ĐIỀU CHỈNH LƯƠNG/THƯỞNG/PHẠT CỦA CA (NGÀY) ===
@salary_manage_bp.route("/salaries/daily/<int:id_chitiet>", methods=["PUT"])
@roles_required('admin', 'manager')
def adjust_daily_salary(id_chitiet):
    """ API mới để sửa thưởng/phạt cho một bản ghi lương chi tiết. """
    
    blct = BangLuongChiTiet.query.get(id_chitiet)
    if not blct:
        return jsonify({"msg": "Không tìm thấy bản ghi lương chi tiết"}), 404
        
    data = request.get_json()
    thuong_ca = data.get("thuong_ca")
    khautru_ca = data.get("khautru_ca")

    try:
        # 1. Cập nhật bản ghi chi tiết
        if thuong_ca is not None:
            blct.thuong_ca = Decimal(thuong_ca)
        if khautru_ca is not None:
            blct.khautru_ca = Decimal(khautru_ca)
        
        # 2. Cập nhật lại bảng lương THÁNG
        luong_thang = Luong.query.get(blct.maluong_thang)
        if luong_thang:
            # Truy vấn lại tổng thưởng/khấu trừ của tháng đó
            summary = db.session.query(
                func.sum(BangLuongChiTiet.thuong_ca),
                func.sum(BangLuongChiTiet.khautru_ca)
            ).filter(
                BangLuongChiTiet.maluong_thang == luong_thang.maluong
            ).first()
            
            luong_thang.thuong = summary[0] or Decimal('0')
            luong_thang.khautru = summary[1] or Decimal('0')
            
            # Tính lại tổng lương tháng
            luong_thang.tongluong = (luong_thang.luongcoban or Decimal('0')) + \
                                    (luong_thang.thuong or Decimal('0')) - \
                                    (luong_thang.khautru or Decimal('0'))
        
        db.session.commit()
        return jsonify({"msg": "Cập nhật lương ca thành công"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi điều chỉnh lương ca {id_chitiet}: {e}")
        return jsonify({"msg": "Cập nhật thất bại"}), 500

# === API CŨ: ĐIỀU CHỈNH LƯƠNG THÁNG (GIỮ NGUYÊN) ===
@salary_manage_bp.route("/salaries/<int:maluong>", methods=["PUT"])
@roles_required('admin', 'manager')
def adjust_monthly_salary(maluong):
    """ Hàm này chỉ điều chỉnh Thưởng/Khấu trừ ở cấp độ Tháng (ghi đè). """
    salary = Luong.query.get(maluong)
    if not salary: return jsonify({"msg":"Không tìm thấy bảng lương"}), 404
    
    data = request.get_json()
    thuong = data.get("thuong")
    khautru = data.get("khautru")
    try:
        # Ghi đè tổng thưởng/khấu trừ của tháng
        if thuong is not None: 
            salary.thuong = Decimal(thuong)
        if khautru is not None: 
            salary.khautru = Decimal(khautru)
        
        salary.tongluong = (salary.luongcoban or Decimal('0')) + (salary.thuong or Decimal('0')) - (salary.khautru or Decimal('0'))
        
        db.session.commit()
        return jsonify({"msg": "Điều chỉnh lương thành công"}), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi điều chỉnh lương: {e}"); return jsonify({"msg": "Điều chỉnh thất bại"}), 500

# === API XUẤT PDF (CẬP NHẬT) ===
@salary_manage_bp.route("/salaries/export-pdf", methods=["GET"])
@roles_required('admin', 'manager')
def export_salaries_pdf():
    try:
        filter_type = request.args.get('filter_type', 'month')
        month_year_str = request.args.get('month_year')
        day_str = request.args.get('day')
        
        data = []
        template_name = 'admin/salary_export_month.html' 
        title = "Báo cáo lương"
        grand_total = Decimal('0')

        if filter_type == 'day':
            selected_date = datetime.strptime(day_str, '%Y-%m-%d').date()
            title = f"Báo cáo lương chi tiết ngày {selected_date.strftime('%d/%m/%Y')}"
            template_name = 'admin/salary_export_day.html'
            
            query = db.session.query(BangLuongChiTiet, NhanVien, ChucVu).join(
                NhanVien, BangLuongChiTiet.manv == NhanVien.manv
            ).join(
                ChucVu, NhanVien.macv == ChucVu.macv
            ).filter(
                BangLuongChiTiet.ngay_lam == selected_date
            ).all()
            
            for blct, nv, cv in query:
                if nv.role != 'admin':
                    # === SỬA: Tính tổng ca ===
                    luong_ca_d = Decimal(blct.luong_ca or '0')
                    thuong_ca_d = Decimal(blct.thuong_ca or '0')
                    khautru_ca_d = Decimal(blct.khautru_ca or '0')
                    tong_ngay = luong_ca_d + thuong_ca_d - khautru_ca_d
                    
                    data.append({
                        "hoten": nv.hoten,
                        "chucvu": cv.tencv,
                        "luong_ca": luong_ca_d,
                        "thuong_ca": thuong_ca_d,
                        "khautru_ca": khautru_ca_d,
                        "tong_ngay": tong_ngay # <-- Cột tổng mới
                    })
                    grand_total += tong_ngay # <-- Tính tổng

        else:
            # Lọc theo tháng (Giữ nguyên)
            if not month_year_str:
                now = datetime.now()
                thang, nam = now.month, now.year
            else:
                selected_month = datetime.strptime(month_year_str, '%Y-%m')
                thang, nam = selected_month.month, selected_month.year
            
            title = f"Báo cáo lương tổng hợp tháng {thang}/{nam}"
            template_name = 'admin/salary_export_month.html'
            
            query = Luong.query.filter_by(thang=thang, nam=nam).all()
            
            for s in query:
                if s.nhanvien and s.nhanvien.role != 'admin':
                    tongluong_decimal = Decimal(s.tongluong or '0')
                    data.append({
                        "hoten": s.nhanvien.hoten if s.nhanvien else 'N/A', 
                        "luongcoban": Decimal(s.luongcoban or '0'),
                        "thuong": Decimal(s.thuong or '0'),
                        "khautru": Decimal(s.khautru or '0'),
                        "tongluong": tongluong_decimal
                    })
                    grand_total += tongluong_decimal 

        html_string = render_template(
            template_name, 
            data=data, 
            title=title, 
            grand_total=grand_total 
        )
        
        pdf = HTML(string=html_string).write_pdf()
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=bao_cao_luong_{filter_type}.pdf'
        return response
        
    except Exception as e:
        current_app.logger.error(f"Lỗi khi xuất PDF lương: {e}")
        return jsonify({"msg": "Xuất PDF thất bại"}), 500
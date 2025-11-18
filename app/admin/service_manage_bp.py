from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import DichVu
from ..decorators import roles_required 
import base64

service_manage_bp = Blueprint("service_manage", __name__)

@service_manage_bp.route("/services", methods=["GET"])
@roles_required('admin', 'manager', 'staff', 'letan')
def get_services_admin():
    """Lấy danh sách dịch vụ cho admin (có thể thấy tất cả, kể cả inactive)"""
    try:
        services = DichVu.query.all()
        result = [{
            "madv": s.madv,
            "tendv": s.tendv,
            "gia": str(s.gia),  
            "thoiluong": s.thoiluong,
            "mota": s.mota,
            "active": s.active,
            "anhdichvu": base64.b64encode(s.anhdichvu).decode('utf-8') if s.anhdichvu else None
        } for s in services]
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy DS dịch vụ: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@service_manage_bp.route("/services", methods=["POST"])
@roles_required('admin', 'manager') 
def create_service():
    try:
        # Sử dụng request.form thay vì request.get_json() vì có ảnh
        tendv = request.form.get("tendv")
        gia = request.form.get("gia")
        thoiluong = request.form.get("thoiluong")
        mota = request.form.get("mota")
        anhdichvu = request.files.get("anhdichvu")

        if not tendv or gia is None:
            return jsonify({"msg": "Thiếu tên dịch vụ hoặc giá"}), 400

        new_service = DichVu(
            tendv=tendv, 
            gia=gia, 
            thoiluong=thoiluong, 
            mota=mota, 
            active=True
        )

        # Xử lý ảnh nếu có
        if anhdichvu:
            anhdichvu_data = anhdichvu.read()
            new_service.anhdichvu = anhdichvu_data

        db.session.add(new_service)
        db.session.commit()
        return jsonify({"msg": "Thêm dịch vụ thành công", "madv": new_service.madv}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi thêm dịch vụ: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@service_manage_bp.route("/services/<int:madv>", methods=["PUT"])
@roles_required('admin', 'manager') 
def update_service(madv):
    service = DichVu.query.get(madv)
    if not service:
        return jsonify({"msg": "Không tìm thấy dịch vụ"}), 404

    try:
        # Sử dụng request.form
        if 'tendv' in request.form:
            service.tendv = request.form.get("tendv")
        if 'gia' in request.form:
            service.gia = request.form.get("gia")
        if 'thoiluong' in request.form:
            service.thoiluong = request.form.get("thoiluong")
        if 'mota' in request.form:
            service.mota = request.form.get("mota")

        if 'active' in request.form:
            active_value = request.form.get("active")
            service.active = active_value.lower() == 'true'

        # Xử lý ảnh nếu có
        anhdichvu = request.files.get("anhdichvu")
        if anhdichvu:
            anhdichvu_data = anhdichvu.read()
            service.anhdichvu = anhdichvu_data

        db.session.commit()
        return jsonify({"msg": "Cập nhật dịch vụ thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi cập nhật dịch vụ: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500
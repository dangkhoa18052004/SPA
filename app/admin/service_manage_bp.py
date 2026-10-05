from flask import Blueprint, request, jsonify, current_app, g
from ..extensions import db
from ..models import DichVu
from ..decorators import roles_required 
import base64
from ..services.upload_service import read_validated_image, InvalidUploadError
from ..services import commission_service

service_manage_bp = Blueprint("service_manage", __name__)

@service_manage_bp.route("/services", methods=["GET"])
@roles_required('admin', 'manager', 'staff', 'letan')
def get_services_admin():
    """Lấy danh sách dịch vụ cho admin (có thể thấy tất cả, kể cả inactive)"""
    try:
        services = DichVu.query.all()
        can_see_commission = getattr(getattr(g, 'current_user', None), 'role', None) in ('admin', 'manager')
        result = [{
            "madv": s.madv,
            "tendv": s.tendv,
            "gia": str(s.gia),  
            "thoiluong": s.thoiluong,
            "mota": s.mota,
            "post_care_instructions": s.post_care_instructions or "",
            "active": s.active,
            "anhdichvu": base64.b64encode(s.anhdichvu).decode('utf-8') if s.anhdichvu else None,
            **({
                "commission_percent": str(s.commission_percent) if s.commission_percent is not None else None,
                "commission_fixed": str(s.commission_fixed) if s.commission_fixed is not None else None,
            } if can_see_commission else {}),
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
        post_care_instructions = request.form.get("post_care_instructions", "")
        anhdichvu = request.files.get("anhdichvu")

        if len(post_care_instructions) > 10000:
            return jsonify({"msg": "Hướng dẫn chăm sóc sau dịch vụ tối đa 10.000 ký tự"}), 400
        try:
            commission_percent, commission_fixed = commission_service.parse_policy(
                request.form.get("commission_percent"), request.form.get("commission_fixed"))
        except ValueError as e:
            return jsonify({"msg": str(e)}), 400

        if not tendv or gia is None:
            return jsonify({"msg": "Thiếu tên dịch vụ hoặc giá"}), 400

        new_service = DichVu(
            tendv=tendv, 
            gia=gia, 
            thoiluong=thoiluong, 
            mota=mota, 
            post_care_instructions=post_care_instructions or None,
            commission_percent=commission_percent,
            commission_fixed=commission_fixed,
            active=True
        )

        # Xử lý ảnh nếu có
        if anhdichvu:
            anhdichvu_data = read_validated_image(anhdichvu)
            new_service.anhdichvu = anhdichvu_data

        db.session.add(new_service)
        db.session.commit()
        return jsonify({"msg": "Thêm dịch vụ thành công", "madv": new_service.madv}), 201
    except InvalidUploadError as e:
        db.session.rollback()
        return jsonify(msg=str(e)), 400
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
        if 'post_care_instructions' in request.form:
            post_care_instructions = request.form.get("post_care_instructions", "")
            if len(post_care_instructions) > 10000:
                return jsonify({"msg": "Hướng dẫn chăm sóc sau dịch vụ tối đa 10.000 ký tự"}), 400
            service.post_care_instructions = post_care_instructions or None

        if 'commission_percent' in request.form or 'commission_fixed' in request.form:
            try:
                service.commission_percent, service.commission_fixed = commission_service.parse_policy(
                    request.form.get("commission_percent", service.commission_percent),
                    request.form.get("commission_fixed", service.commission_fixed))
            except ValueError as e:
                return jsonify({"msg": str(e)}), 400

        if 'active' in request.form:
            active_value = request.form.get("active")
            service.active = active_value.lower() == 'true'

        # Xử lý ảnh nếu có
        anhdichvu = request.files.get("anhdichvu")
        if anhdichvu:
            anhdichvu_data = read_validated_image(anhdichvu)
            service.anhdichvu = anhdichvu_data

        db.session.commit()
        return jsonify({"msg": "Cập nhật dịch vụ thành công"}), 200
    except InvalidUploadError as e:
        db.session.rollback()
        return jsonify(msg=str(e)), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi cập nhật dịch vụ: {e}")
        return jsonify({"msg": "Lỗi hệ thống"}), 500

@service_manage_bp.route("/services/<int:madv>", methods=["DELETE"])
@roles_required('admin', 'manager')
def delete_service(madv):
    """Soft-delete dịch vụ bằng cách chuyển active = False."""
    service = DichVu.query.get(madv)
    if not service:
        return jsonify({"msg": "Không tìm thấy dịch vụ"}), 404

    try:
        service.active = False
        db.session.commit()
        return jsonify({"success": True, "msg": "Xóa dịch vụ thành công"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi xóa dịch vụ {madv}: {e}", exc_info=True)
        return jsonify({"msg": "Lỗi hệ thống khi xóa dịch vụ"}), 500

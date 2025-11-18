from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import ChucVu, NhanVien
from ..decorators import roles_required

role_manage_bp = Blueprint("role_manage", __name__)

@role_manage_bp.route("/roles", methods=["GET"])
@roles_required('admin')
def get_roles():

    try:
        roles = ChucVu.query.all(); result = [{"macv": r.macv, "tencv": r.tencv, "dongiagio": str(r.dongiagio)} for r in roles]
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy DS chức vụ: {e}"); return jsonify({"msg": "Lỗi hệ thống"}), 500

@role_manage_bp.route("/roles", methods=["POST"])
@roles_required('admin')
def create_role():

    data = request.get_json(); tencv, dongiagio = data.get("tencv"), data.get("dongiagio")
    if not tencv or dongiagio is None: return jsonify({"msg": "Thiếu thông tin"}), 400
    if ChucVu.query.filter_by(tencv=tencv).first(): return jsonify({"msg": "Tên chức vụ đã tồn tại"}), 409
    try:
        new_role = ChucVu(tencv=tencv, dongiagio=dongiagio); db.session.add(new_role); db.session.commit()
        return jsonify({"msg": "Tạo chức vụ thành công", "macv": new_role.macv}), 201
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi tạo chức vụ: {e}"); return jsonify({"msg": "Lỗi hệ thống"}), 500

@role_manage_bp.route("/roles/<int:macv>", methods=["PUT"])
@roles_required('admin')
def update_role(macv):

    role = ChucVu.query.get(macv);
    if not role: return jsonify({"msg": "Không tìm thấy chức vụ"}), 404
    data = request.get_json(); role.tencv = data.get("tencv", role.tencv); role.dongiagio = data.get("dongiagio", role.dongiagio)
    try:
        db.session.commit(); return jsonify({"msg": "Cập nhật chức vụ thành công"}), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi cập nhật chức vụ: {e}"); return jsonify({"msg": "Lỗi hệ thống"}), 500

@role_manage_bp.route("/roles/<int:macv>", methods=["DELETE"])
@roles_required('admin')
def delete_role(macv):

    role = ChucVu.query.get(macv)
    if not role: return jsonify({"msg": "Không tìm thấy chức vụ"}), 404
    if NhanVien.query.filter_by(macv=macv).first(): return jsonify({"msg": "Không thể xóa, còn nhân viên giữ chức vụ này."}), 400
    try:
        db.session.delete(role); db.session.commit(); return jsonify({"msg": "Xóa chức vụ thành công"}), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Lỗi khi xóa chức vụ: {e}"); return jsonify({"msg": "Lỗi hệ thống"}), 500
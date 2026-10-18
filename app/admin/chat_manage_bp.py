from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Hoithoai, NhanVien
from ..decorators import roles_required

chat_manage_bp = Blueprint("chat_manage", __name__)


@chat_manage_bp.get('/conversations/assignees')
@roles_required('letan', 'manager', 'admin')
def conversation_assignees():
    return jsonify(items=[dict(manv=s.manv, hoten=s.hoten) for s in
        NhanVien.query.filter_by(role='staff', trangthai=True).order_by(NhanVien.hoten).all()])

@chat_manage_bp.route("/conversations/<int:maht>/assign", methods=["PUT"])
@roles_required('letan', 'manager', 'admin')
def assign_conversation(maht):
    """
    Gán một cuộc hội thoại cho một Nhân viên (Kỹ thuật viên) cụ thể.
    """
    data = request.get_json(silent=True)
    manv_to_assign = data.get('manv') if isinstance(data, dict) else None

    if type(manv_to_assign) is not int or manv_to_assign < 1:
        return jsonify({"msg": "Cần cung cấp 'manv' (ID nhân viên) để gán"}), 400

    conversation = Hoithoai.query.get(maht)
    if not conversation:
        return jsonify({"msg": "Không tìm thấy hội thoại"}), 404
        
    staff = NhanVien.query.get(manv_to_assign)
    if not staff:
        return jsonify({"msg": "Không tìm thấy nhân viên"}), 404
        
    if staff.role != 'staff' or not staff.trangthai:
        return jsonify({"msg": "Chỉ có thể gán cho Kỹ thuật viên (nhanvien)"}), 400

    try:
        conversation.manv = manv_to_assign
        db.session.commit()
        return jsonify({"msg": f"Đã gán hội thoại {maht} cho nhân viên {staff.hoten}"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi gán hội thoại: {e}")
        return jsonify({"msg": "Gán hội thoại thất bại"}), 500

@chat_manage_bp.route("/conversations/<int:maht>/unassign", methods=["PUT"])
@roles_required('letan', 'manager', 'admin') # Chỉ Lễ tân/Quản lý
def unassign_conversation(maht):
    """
    Gỡ nhân viên khỏi hội thoại, đưa về Hộp thư chung (CSKH).
    """
    conversation = Hoithoai.query.get(maht)
    if not conversation:
        return jsonify({"msg": "Không tìm thấy hội thoại"}), 404

    try:
        conversation.manv = None
        db.session.commit()
        return jsonify({"msg": f"Đã gỡ gán hội thoại {maht}, đưa về Hộp thư chung"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi gỡ gán hội thoại: {e}")
        return jsonify({"msg": "Gỡ gán hội thoại thất bại"}), 500

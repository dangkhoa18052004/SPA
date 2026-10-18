from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Hoithoai, KhachHang, NhanVien
from ..services import chat_service
import re

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

def get_current_user_from_jwt():
    """Helper function to get current user from JWT token"""
    identity = get_jwt_identity()
    
    if not isinstance(identity, str) or ':' not in identity or not identity.split(':', 1)[1].isdigit():
        return None, None
    if identity.startswith("customer:"):
        user_id = int(identity.split(":")[1])
        user = KhachHang.query.get(user_id)
        return user, 'customer'
    elif identity.startswith("staff:"):
        user_id = int(identity.split(":")[1])
        user = NhanVien.query.get(user_id)
        return user, 'staff'
    
    return None, None

@chat_bp.route("/conversations", methods=["GET"])
@jwt_required()
def get_my_conversations():
    user, user_type = get_current_user_from_jwt()
    
    if not user:
        return jsonify({"success": False, "message": "Người dùng không tồn tại"}), 404
    
    try:
        conversations = chat_service.get_conversations_for_user(user, user_type)
        return jsonify({
            "success": True,
            "conversations": conversations
        }), 200
    except PermissionError as e:
        return jsonify(success=False, message=str(e)), 403
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy hội thoại: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500


@chat_bp.route("/conversations", methods=["POST"])
@jwt_required()
def start_conversation():
    user, user_type = get_current_user_from_jwt()
    
    if not user or user_type != 'customer' or user.trangthai != 'active':
        return jsonify({"success": False, "message": "Chỉ khách hàng mới có thể tạo cuộc trò chuyện"}), 403
    
    try:
        conversation = Hoithoai.query.filter_by(makh=user.makh).first()
        if not conversation:
            conversation = Hoithoai(makh=user.makh)
            db.session.add(conversation)
            db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Bắt đầu/Tiếp tục cuộc trò chuyện",
            "conversation": {
                "maht": conversation.maht
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi bắt đầu hội thoại: {e}")
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500

@chat_bp.route("/conversations/<int:maht>/messages", methods=["GET"])
@jwt_required()
def get_conversation_messages(maht):
    """Lấy tin nhắn trong một cuộc trò chuyện."""
    user, user_type = get_current_user_from_jwt()
    
    try:
        messages, _ = chat_service.get_messages_for_conversation(maht, user, user_type)
        return jsonify({"success": True, "messages": messages}), 200
    except PermissionError as e:
        return jsonify({"success": False, "message": str(e)}), 403
    except Exception as e:
        current_app.logger.error(f"Lỗi khi lấy tin nhắn: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500

@chat_bp.route("/conversations/<int:maht>/messages", methods=["POST"])
@jwt_required()
def send_message(maht):
    """Gửi tin nhắn mới."""
    user, user_type = get_current_user_from_jwt()
    data = request.get_json(silent=True)
    noidung = data.get('noidung') if isinstance(data, dict) else None
    
    # The existing customer service picker embeds raster photos in SERVICE_CARD/IMG messages.
    # Keep those working while bounding plain text and the total encoded image size.
    rich_image = (isinstance(noidung, str) and len(noidung) <= 4_000_000 and
        re.fullmatch(r'\[(?:SERVICE_CARD:\d+\|[^|\r\n]+\|[\d.]+\|\d+\||IMG:)data:image/(?:jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+\]\s*[\s\S]{0,5000}', noidung.strip()))
    if not isinstance(noidung, str) or not noidung.strip() or len(noidung) > 5000 and not rich_image:
        return jsonify({"success": False, "message": "Tin nhắn cần có nội dung và tối đa 5000 ký tự"}), 400
    noidung = noidung.strip()
    
    try:
        # Kiểm tra quyền và lấy hội thoại
        _, conversation = chat_service.get_messages_for_conversation(maht, user, user_type)
        
        # Gửi tin nhắn và cập nhật hội thoại
        new_message = chat_service.send_message_as_user(conversation, noidung, user, user_type)
        
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Gửi tin nhắn thành công",
            "matn": new_message.matn
        }), 201
    except PermissionError as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 403
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi gửi tin nhắn: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi hệ thống"}), 500

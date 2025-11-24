# app/services/chat_service.py
from ..extensions import db
from ..models import Hoithoai, TinNhan, NhanVien, KhachHang 
from sqlalchemy import desc, or_, func
from datetime import datetime, timezone
import pytz

CSKH_ROLES = ['letan', 'manager', 'admin']
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

def get_conversations_for_user(user, user_type):
    """
    Lấy danh sách hội thoại.
    """
    convs_query = None
    conversations_list = []
    
    if user_type == 'customer':
        convs_query = db.session.query(
            Hoithoai,
            NhanVien.hoten.label("staff_name"),
            NhanVien.anhnhanvien.label("staff_avatar")
        ).outerjoin(
            NhanVien, Hoithoai.manv == NhanVien.manv
        ).filter(
            Hoithoai.makh == user.makh
        )
        
        user_conversations = convs_query.order_by(desc(Hoithoai.tin_nhan_cuoi_thoi_gian)).all()
        
        for conv, staff_name, staff_avatar_file in user_conversations:
            unread_count = db.session.query(func.count(TinNhan.matn)).filter(
                TinNhan.maht == conv.maht,
                TinNhan.nguoigui_manv != None,
                TinNhan.da_doc == False      
            ).scalar()

            last_msg_time = None
            if conv.tin_nhan_cuoi_thoi_gian:
                utc_time = conv.tin_nhan_cuoi_thoi_gian.replace(tzinfo=timezone.utc)
                vietnam_time = utc_time.astimezone(VIETNAM_TZ)
                last_msg_time = vietnam_time.isoformat()

            conversations_list.append({
                "maht": conv.maht,
                "staff_name": staff_name or "Hỗ trợ",
                "staff_avatar": staff_avatar_file,
                "last_message": conv.tin_nhan_cuoi_noi_dung,
                "last_message_time": last_msg_time,
                "unread_count": unread_count
            })
            
    elif user_type == 'staff':
        base_query = db.session.query(
            Hoithoai,
            KhachHang.hoten.label("customer_name"),
            KhachHang.anhdaidien.label("customer_avatar")
        ).outerjoin(
            KhachHang, Hoithoai.makh == KhachHang.makh
        )
        
        if user.role in CSKH_ROLES:
            convs_query = base_query
        elif user.role == 'staff':
            convs_query = base_query.filter(Hoithoai.manv == user.manv)
        else:
            return []
            
        user_conversations = convs_query.order_by(desc(Hoithoai.tin_nhan_cuoi_thoi_gian)).all()

        for conv, customer_name, customer_avatar_file in user_conversations:
            unread_count = db.session.query(func.count(TinNhan.matn)).filter(
                TinNhan.maht == conv.maht,
                TinNhan.nguoigui_makh != None,
                TinNhan.da_doc == False        
            ).scalar()

            last_msg_time = None
            if conv.tin_nhan_cuoi_thoi_gian:
                utc_time = conv.tin_nhan_cuoi_thoi_gian.replace(tzinfo=timezone.utc)
                vietnam_time = utc_time.astimezone(VIETNAM_TZ)
                last_msg_time = vietnam_time.isoformat()

            conversations_list.append({
                "maht": conv.maht,
                "customer_name": customer_name or "Khách vãng lai",
                "customer_avatar": customer_avatar_file,
                "last_message": conv.tin_nhan_cuoi_noi_dung,
                "last_message_time": last_msg_time,
                "unread_count": unread_count
            })
            
    return conversations_list

def get_messages_for_conversation(conversation_id, user, user_type):
    """
    Lấy tin nhắn.
    ✅ FIX: Convert timezone và đánh dấu đã đọc
    """
    conversation = Hoithoai.query.get(conversation_id)
    if not conversation:
        raise PermissionError("Không tìm thấy hội thoại")

    if user_type == 'customer':
        if conversation.makh != user.makh:
            raise PermissionError("Bạn không có quyền xem hội thoại này")
    elif user_type == 'staff':
        if user.role in CSKH_ROLES: 
            pass 
        elif user.role == 'staff':
            if conversation.manv != user.manv:
                raise PermissionError("Bạn không có quyền xem hội thoại này")
        else:
            raise PermissionError("Bạn không có quyền truy cập chức năng chat")
                
    if user_type == 'staff':
        db.session.query(TinNhan).filter(
            TinNhan.maht == conversation_id,
            TinNhan.nguoigui_makh != None,
            TinNhan.da_doc == False       
        ).update({"da_doc": True}, synchronize_session=False)
        
    elif user_type == 'customer':
        db.session.query(TinNhan).filter(
            TinNhan.maht == conversation_id,
            TinNhan.nguoigui_manv != None,
            TinNhan.da_doc == False        
        ).update({"da_doc": True}, synchronize_session=False)
    
    db.session.commit()

    messages_query = TinNhan.query.filter_by(maht=conversation_id).order_by(TinNhan.thoigiangui.asc()).all()
    
    messages = []
    for msg in messages_query:
        utc_time = msg.thoigiangui.replace(tzinfo=timezone.utc)
        vietnam_time = utc_time.astimezone(VIETNAM_TZ)
        
        if user_type == 'staff':
            messages.append({
                "matn": msg.matn, 
                "noidung": msg.noidung, 
                "thoigian": vietnam_time.isoformat(),  
                "is_from_staff": msg.nguoigui_manv is not None
            })
        else:
            messages.append({
                "matn": msg.matn, 
                "noidung": msg.noidung, 
                "thoigiangui": vietnam_time.isoformat(),  
                "is_customer": msg.nguoigui_makh is not None
            })

    return messages, conversation 

def send_message_as_user(conversation, noidung, user, user_type):
    """
    Gửi tin nhắn.
    """
    vietnam_now = datetime.now(VIETNAM_TZ)
    
    new_message = TinNhan(
        maht=conversation.maht, 
        noidung=noidung,
        thoigiangui=vietnam_now, 
        da_doc=False 
    )
    is_customer = False
    
    if user_type == 'customer':
        new_message.nguoigui_makh = user.makh
        is_customer = True
    else:
        new_message.nguoigui_manv = user.manv
        is_customer = False

    db.session.add(new_message)
    
    conversation.tin_nhan_cuoi_noi_dung = noidung[:150] 
    conversation.tin_nhan_cuoi_thoi_gian = vietnam_now  
    conversation.tin_nhan_cuoi_la_khach_gui = is_customer
    
    return new_message
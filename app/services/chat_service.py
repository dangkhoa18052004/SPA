from ..extensions import db
from ..models import Hoithoai, TinNhan, NhanVien, KhachHang 
from sqlalchemy import desc, or_, func

CSKH_ROLES = ['letan', 'manager', 'admin']

def get_conversations_for_user(user, user_type):
    """
    Lấy danh sách hội thoại.
    NÂNG CẤP: Tính toán unread_count dựa trên cờ 'da_doc'.
    """
    convs_query = None
    conversations_list = []
    
    if user_type == 'customer':
        # --- Logic cho Khách hàng ---
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
            # Đếm tin nhắn chưa đọc (do NHÂN VIÊN gửi)
            unread_count = db.session.query(func.count(TinNhan.matn)).filter(
                TinNhan.maht == conv.maht,
                TinNhan.nguoigui_manv != None, # Do nhân viên gửi
                TinNhan.da_doc == False      
            ).scalar()

            conversations_list.append({
                "maht": conv.maht,
                "staff_name": staff_name or "Hỗ trợ",
                "staff_avatar": staff_avatar_file,
                "last_message": conv.tin_nhan_cuoi_noi_dung,
                "last_message_time": conv.tin_nhan_cuoi_thoi_gian.isoformat() if conv.tin_nhan_cuoi_thoi_gian else None,
                "unread_count": unread_count
            })
            
    elif user_type == 'staff':
        # --- Logic cho Nhân viên (Admin/Lễ tân) ---
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
            # Đếm tin nhắn chưa đọc (do KHÁCH HÀNG gửi)
            unread_count = db.session.query(func.count(TinNhan.matn)).filter(
                TinNhan.maht == conv.maht,
                TinNhan.nguoigui_makh != None, # Do khách gửi
                TinNhan.da_doc == False        
            ).scalar()

            conversations_list.append({
                "maht": conv.maht,
                "customer_name": customer_name or "Khách vãng lai",
                "customer_avatar": customer_avatar_file,
                "last_message": conv.tin_nhan_cuoi_noi_dung,
                "last_message_time": conv.tin_nhan_cuoi_thoi_gian.isoformat() if conv.tin_nhan_cuoi_thoi_gian else None,
                "unread_count": unread_count
            })
            
    return conversations_list

def get_messages_for_conversation(conversation_id, user, user_type):
    """
    Lấy tin nhắn.
    NÂNG CẤP: Đánh dấu các tin nhắn đã tải là "da_doc = True".
    """
    conversation = Hoithoai.query.get(conversation_id)
    if not conversation:
        raise PermissionError("Không tìm thấy hội thoại")

    if user_type == 'customer':
        if conversation.makh != user.makh:
            raise PermissionError("Bạn không có quyền xem hội thoại này")
    elif user_type == 'staff':
        if user.role in CSKH_ROLES: pass 
        elif user.role == 'staff':
            if conversation.manv != user.manv:
                raise PermissionError("Bạn không có quyền xem hội thoại này")
        else:
            raise PermissionError("Bạn không có quyền truy cập chức năng chat")
                
    if user_type == 'staff':
        # Admin đang đọc, vậy đánh dấu tin nhắn của KHÁCH là đã đọc
        db.session.query(TinNhan).filter(
            TinNhan.maht == conversation_id,
            TinNhan.nguoigui_makh != None,
            TinNhan.da_doc == False       
        ).update({"da_doc": True}, synchronize_session=False)
        
    elif user_type == 'customer':
        # Khách đang đọc, vậy đánh dấu tin nhắn của NHÂN VIÊN là đã đọc
        db.session.query(TinNhan).filter(
            TinNhan.maht == conversation_id,
            TinNhan.nguoigui_manv != None,
            TinNhan.da_doc == False        
        ).update({"da_doc": True}, synchronize_session=False)
    
    db.session.commit() # Lưu lại trạng thái đã đọc

    messages_query = TinNhan.query.filter_by(maht=conversation_id).order_by(TinNhan.thoigiangui.asc()).all()
    
    messages = []
    if user_type == 'staff':
        messages = [
            {"matn": msg.matn, "noidung": msg.noidung, "thoigian": msg.thoigiangui.isoformat(), 
             "is_from_staff": msg.nguoigui_manv is not None}
            for msg in messages_query
        ]
    else: # user_type == 'customer'
        messages = [
            {"matn": msg.matn, "noidung": msg.noidung, "thoigiangui": msg.thoigiangui.isoformat(), 
             "is_customer": msg.nguoigui_makh is not None}
            for msg in messages_query
        ]

    return messages, conversation 

def send_message_as_user(conversation, noidung, user, user_type):
    """
    Gửi tin nhắn.
    Tin nhắn mới mặc định là da_doc = False.
    """
    new_message = TinNhan(
        maht=conversation.maht, 
        noidung=noidung,
        da_doc=False 
    )
    is_customer = False
    
    if user_type == 'customer':
        new_message.nguoigui_makh = user.makh
        is_customer = True
    else: # user_type == 'staff'
        new_message.nguoigui_manv = user.manv
        is_customer = False
        pass

    db.session.add(new_message)
    
    conversation.tin_nhan_cuoi_noi_dung = noidung[:150] 
    conversation.tin_nhan_cuoi_thoi_gian = new_message.thoigiangui
    conversation.tin_nhan_cuoi_la_khach_gui = is_customer
    
    return new_message
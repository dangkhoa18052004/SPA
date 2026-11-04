from datetime import datetime, timedelta
from app.extensions import db
from app.models import Hoithoai, TinNhan

def test_newest_null_tiebreak_and_list_never_marks_read(app,client,admin_auth_headers,staff_auth_headers):
    with app.app_context():
        now=datetime.utcnow()
        rows=[Hoithoai(makh=app.config['TEST_CUSTOMER_ID'],manv=app.config['TEST_STAFF_ID'] if i<3 else app.config['TEST_STAFF2_ID'],tin_nhan_cuoi_thoi_gian=now if i<2 else None,tin_nhan_cuoi_noi_dung=f'Chat {i}') for i in range(4)]
        db.session.add_all(rows);db.session.flush()
        ids=[r.maht for r in rows]
        for row in rows:
            db.session.add(TinNhan(maht=row.maht,nguoigui_makh=row.makh,noidung='Unread',da_doc=False))
        db.session.commit()
    result=client.get('/api/chat/conversations',headers=admin_auth_headers).json['conversations']
    assert [r['maht'] for r in result]==[ids[1],ids[0],ids[3],ids[2]]
    assert sum(r['unread_count'] for r in result)==4
    visible=client.get('/api/chat/conversations',headers=staff_auth_headers).json['conversations']
    assert {r['maht'] for r in visible}==set(ids[:3])
    assert sum(r['unread_count'] for r in visible)==3
    assert client.get(f'/api/chat/conversations/{ids[3]}/messages',headers=staff_auth_headers).status_code==403
    assert client.get(f'/api/chat/conversations/{ids[1]}/messages',headers=admin_auth_headers).status_code==200
    result=client.get('/api/chat/conversations',headers=admin_auth_headers).json['conversations']
    assert {r['maht']:r['unread_count'] for r in result}=={ids[0]:1,ids[1]:0,ids[2]:1,ids[3]:1}

def test_incoming_message_moves_an_old_thread_first(app,client,admin_auth_headers,customer_auth_headers):
    with app.app_context():
        old,new=[Hoithoai(makh=app.config['TEST_CUSTOMER_ID'],tin_nhan_cuoi_thoi_gian=datetime.utcnow()-timedelta(days=days)) for days in (2,1)]
        db.session.add_all([old,new]);db.session.commit();old_id,new_id=old.maht,new.maht
    assert client.get('/api/chat/conversations',headers=admin_auth_headers).json['conversations'][0]['maht']==new_id
    sent=client.post(f'/api/chat/conversations/{old_id}/messages',headers=customer_auth_headers,json={'noidung':'Mới nhất'})
    assert sent.status_code in (200,201)
    first=client.get('/api/chat/conversations',headers=admin_auth_headers).json['conversations'][0]
    assert first['maht']==old_id and first['last_message']=='Mới nhất' and first['unread_count']==1

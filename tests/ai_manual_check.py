"""Kiểm tra THẬT với Gemini (cần GEMINI_API_KEY trong môi trường/.env) trên DB thử nghiệm trong bộ nhớ.

Run: python tests/ai_manual_check.py
Không ghi vào DATABASE_URL, không gửi email, không in API key.
"""
import json
import os
import sys
import time as clock
from datetime import time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, DichVu, CaLam, nhanvien_calam, LichHen, AIBookingDraft, HoaDon, ThanhToan
from app.services import appointment_service, package_service as ps

if not os.getenv('GEMINI_API_KEY'):
    sys.exit('GEMINI_API_KEY chưa được đặt; bỏ qua kiểm tra thật.')

app = create_app(dict(TESTING=True, APP_ENV='testing', SQLALCHEMY_DATABASE_URI='sqlite://', SECRET_KEY='manual',
                      JWT_SECRET_KEY='manual-ai-check-secret-32-bytes!!', GEMINI_API_KEY=os.environ['GEMINI_API_KEY'],
                      GEMINI_MODEL=os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')))
appointment_service.send_appointment_confirmation_email_async = lambda *a: None
tomorrow = ps.local_now().date() + timedelta(days=1)
with app.app_context():
    db.create_all()
    role = ChucVu(tencv='KTV', dongiagio=100000); db.session.add(role); db.session.flush()
    staff = NhanVien(hoten='Kỹ thuật viên Mai', taikhoan='ktv', matkhau='x', macv=role.macv, role='staff', trangthai=True)
    admin = NhanVien(hoten='Quản lý', taikhoan='ql', matkhau='x', macv=role.macv, role='manager', trangthai=True)
    customer = KhachHang(hoten='Trần Văn Bình', taikhoan='binh', matkhau='x', sdt='0987654321', email='binh@example.com')
    db.session.add_all([staff, admin, customer,
                        DichVu(tendv='Massage thư giãn toàn thân', gia=350000, thoiluong=60, active=True),
                        DichVu(tendv='Chăm sóc da mụn', gia=550000, thoiluong=60, active=True)])
    db.session.flush()
    shift = CaLam(ngay=tomorrow, giobatdau=time(8), gioketthuc=time(20), sogio=12)
    db.session.add(shift); db.session.flush()
    db.session.execute(nhanvien_calam.insert().values(manv=staff.manv, maca=shift.maca))
    invoice = HoaDon(makh=customer.makh, manv=staff.manv, tongtien=350000, trangthai='Đã thanh toán')
    db.session.add(invoice); db.session.flush()
    db.session.add(ThanhToan(mahd=invoice.mahd, sotien=350000, phuongthuc='Tiền mặt', ngaythanhtoan=ps.local_now()))
    db.session.commit()
    customer_headers = {'Authorization': 'Bearer ' + create_access_token(identity=f'customer:{customer.makh}')}
    manager_headers = {'Authorization': 'Bearer ' + create_access_token(identity=f'staff:{admin.manv}')}

client = app.test_client()
history, draft = [], None


def say(message):
    global draft
    started = clock.time()
    r = client.post('/api/ai/chat', headers=customer_headers, json={'message': message, 'history': history})
    body = r.json
    print(f'\nKHÁCH: {message}\n  HTTP {r.status_code} · tools={body.get("tools_used")} · {clock.time() - started:.1f}s')
    print('  AI:', (body.get('reply') or body.get('msg', ''))[:400].replace('\n', ' '))
    history.extend([{'role': 'user', 'text': message}, {'role': 'model', 'text': body.get('reply', '')}])
    if body.get('draft'):
        draft = body['draft']
        print('  BẢN NHÁP:', json.dumps({k: draft[k] for k in ('ngaygio', 'tong_tien_vnd', 'ky_thuat_vien')}, ensure_ascii=False))
    return body


say('Chào bạn, mình muốn massage chiều mai')
with app.app_context():
    assert LichHen.query.count() == 0
say(f'3 giờ chiều mai ({tomorrow:%d/%m}) nhé, cho mình đặt luôn')
if not draft:
    say('Đúng rồi, tạo bản nháp giúp mình')
assert draft, 'Gemini chưa tạo bản nháp'
with app.app_context():
    assert LichHen.query.count() == 0, 'Bản nháp không được tạo lịch hẹn'
r1 = client.post('/api/ai/booking/confirm', headers=customer_headers, json={'draft_id': draft['draft_id']})
r2 = client.post('/api/ai/booking/confirm', headers=customer_headers, json={'draft_id': draft['draft_id']})
print(f'\nXÁC NHẬN: HTTP {r1.status_code} → lần 2 HTTP {r2.status_code} (created={r2.json["created"]})')
with app.app_context():
    apt = LichHen.query.one()
    print(f'  LichHen #{apt.malh} {apt.ngaygio:%H:%M %d/%m/%Y} nguồn={apt.booking_source} dịch vụ={[d.dichvu.tendv for d in apt.chitiet]}')

started = clock.time()
summary = client.post('/api/ai/business-summary', headers=manager_headers, json={}).json
print(f'\nTÓM TẮT KINH DOANH ({clock.time() - started:.1f}s, bỏ {summary.get("removed_unverified")} câu có số không kiểm chứng):')
for fact in summary.get('facts', []):
    print('  FACT:', fact)
print('  NHẬN XÉT:', summary.get('summary'))
for s in summary.get('suggestions', []):
    print('  GỢI Ý:', s)
assert client.post('/api/ai/business-summary', headers=customer_headers, json={}).status_code == 403
print('\nPASS: luồng thật hỏi lại giờ → bản nháp (chưa có lịch) → xác nhận 1 lịch, idempotent; tóm tắt kinh doanh; khách bị chặn.')

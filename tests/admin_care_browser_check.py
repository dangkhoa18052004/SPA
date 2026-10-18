"""Đợt 6 browser journeys on an in-memory database, with AI/email providers stubbed."""
from datetime import datetime
import base64
import io
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db
from app.models import ChucVu, NhanVien, KhachHang, DichVu, LichHen, ChiTietLichHen, DanhGia, DanhGiaDichVu, ReviewReply, Hoithoai, TinNhan
from app.services import loyalty_service as loyalty, email_service, ai_service
from PIL import Image
from admin_browser import Harness

artifacts = ROOT / '.test-tmp' / ('admin-care-browser-' + uuid4().hex[:8])
artifacts.mkdir(parents=True)
app = create_app(dict(TESTING=True, APP_ENV='testing', STAFF_SECURITY_ENABLED=False, SQLALCHEMY_DATABASE_URI='sqlite://',
    SECRET_KEY='browser-test', JWT_SECRET_KEY='admin-care-browser-only-at-least-32-characters',
    BUSINESS_PORTAL_ENABLED=True, ADMIN_CARE_REACT_ENABLED=True, ADMIN_BOOKING_REACT_ENABLED=True, ADMIN_BILLING_REACT_ENABLED=True,
    ADMIN_CATALOG_REACT_ENABLED=True, ADMIN_PEOPLE_REACT_ENABLED=True, EMPLOYEE_PORTAL_ENABLED=False,
    CRM_ENABLED=False, BI_REPORTS_ENABLED=False, OBSERVABILITY_ENABLED=False, AUTH_RATE_LIMIT_ENABLED=False,
    AI_CHAT_JOBS_ENABLED=False, GEMINI_API_KEY='fake-never-sent', SEPAY_POLL_ENABLED=False))
email_service.send_email = lambda *args, **kwargs: True
ai_calls = []
def summary(from_date, to_date):
    ai_calls.append((from_date, to_date))
    if app.config.get('BROWSER_AI_FAIL'):
        raise ai_service.AIUpstreamError('AI kiểm thử tạm thời chưa phản hồi.')
    return dict(success=True, facts=['Số liệu kiểm thử đã đối chiếu.'], summary='Spa đang phục vụ khách theo lịch.',
                suggestions=['Kiểm tra các lịch đang chờ xác nhận.'], removed_unverified=0, from_date=from_date, to_date=to_date)
ai_service.business_summary = summary

with app.app_context():
    db.create_all()
    position = ChucVu(tencv='Kỹ thuật viên', dongiagio=100000)
    db.session.add(position); db.session.flush()
    actors = {r: NhanVien(hoten='Kiểm thử ' + r, taikhoan=r, matkhau='hash', role=r, macv=position.macv, trangthai=True) for r in ['admin', 'manager', 'letan', 'staff']}
    customer = KhachHang(hoten='Khách thử chăm sóc', sdt='0901234567', taikhoan='care_customer', matkhau='hash', trangthai='active')
    service = DichVu(tendv='Massage kiểm thử', gia=300000, thoiluong=60, active=True)
    db.session.add_all([*actors.values(), customer, service]); db.session.flush()
    apt = LichHen(makh=customer.makh, manv=actors['staff'].manv, ngaygio=datetime.now(), trangthai='completed')
    db.session.add(apt); db.session.flush(); db.session.add(ChiTietLichHen(malh=apt.malh, madv=service.madv))
    review = DanhGia(makh=customer.makh, manv=actors['staff'].manv, malh=apt.malh, rating=5, comment='Dịch vụ chu đáo <script>window.bad=1</script>')
    db.session.add(review); db.session.flush(); db.session.add(DanhGiaDichVu(madg=review.madg, madv=service.madv))
    conv = Hoithoai(makh=customer.makh, manv=actors['staff'].manv, tin_nhan_cuoi_noi_dung='Xin tư vấn', tin_nhan_cuoi_thoi_gian=datetime.utcnow())
    db.session.add(conv); db.session.flush(); db.session.add(TinNhan(maht=conv.maht, nguoigui_makh=customer.makh, noidung='Xin tư vấn', da_doc=False))
    image = io.BytesIO(); Image.new('RGB', (8, 8), 'green').save(image, format='PNG')
    photo = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode()
    db.session.add(TinNhan(maht=conv.maht, nguoigui_makh=customer.makh,
        noidung=f'[SERVICE_CARD:{service.madv}|Massage kiểm thử|300000|60|{photo}] Tôi muốn đặt lịch', da_doc=False))
    loyalty.admin_adjust_points(customer.makh, 1000, 'Điểm kiểm thử riêng', actors['admin'].manv, 'fund')
    gift = loyalty.save_reward(dict(name='Khăn spa kiểm thử', reward_type='physical_gift', points_cost=50, validity_days=30))
    redemption = loyalty.redeem_reward(customer.makh, gift.id, 'gift')
    db.session.commit()
    ids = dict(customer=customer.makh, review=review.madg, conversation=conv.maht, redemption=redemption.id)
    tokens = {r: create_access_token(identity=f'staff:{actor.manv}') for r, actor in actors.items()}

app.config['BROWSER_ROLE'] = 'admin'
h = Harness(app, tokens, artifacts); b = h.browser
try:
    b.viewport(1440)
    b.navigate('/admin/loyalty?tab=rewards')
    b.wait("document.body.textContent.includes('Khăn spa kiểm thử')")
    b.button('Thêm quà / voucher')
    b.wait("document.querySelector('.ant-drawer-open input#name')")
    # antd Form labels link to the Select by id.
    b.js("document.querySelector('#reward_type').closest('.ant-select').querySelector('.ant-select-selector').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}))")
    b.wait("document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')")
    b.js("[...document.querySelectorAll('.ant-select-item-option')].find(e=>e.textContent==='Quà tại cửa hàng').click()")
    b.type('.ant-drawer-open input#name', 'Quà mới đợt 6')
    b.type('.ant-drawer-open input#points_cost', '30')
    b.button('Lưu quà', "document.querySelector('.ant-drawer-open')")
    b.wait("!document.querySelector('.ant-drawer-open') && document.body.textContent.includes('Quà mới đợt 6')")
    b.screenshot('rewards-1440')
    b.navigate('/admin/loyalty?tab=config')
    b.wait("document.querySelector('input#earn_points')")
    b.type('input#earn_points', '2')
    b.button('Lưu quy tắc'); b.confirm_modal('Lưu quy tắc')
    b.wait("document.body.textContent.includes('Đã lưu quy tắc')")
    assert h.query(lambda: loyalty.get_config().earn_points) == 2
    b.screenshot('rules-1440')
    b.navigate('/admin/loyalty?tab=customers')
    b.wait("document.body.textContent.includes('Khách thử chăm sóc')")
    b.button('Điều chỉnh điểm')
    b.wait("document.querySelector('.ant-modal input#points')")
    b.type('.ant-modal input#points', '25'); b.type('.ant-modal textarea#reason', 'Bổ sung điểm kiểm thử')
    b.drop_response(f"/api/admin/loyalty/customers/{ids['customer']}/adjust")
    b.button('Lưu điều chỉnh', "document.querySelector('.ant-modal')")
    b.wait("document.body.textContent.includes('Không thể kết nối')")
    b.navigate('/admin/profile')
    b.navigate('/admin/loyalty?tab=customers')
    b.wait("document.body.textContent.includes('Khách thử chăm sóc')")
    b.button('Điều chỉnh điểm')
    b.wait("document.querySelector('.ant-modal input#points')?.value==='25'")
    b.button('Lưu điều chỉnh', "document.querySelector('.ant-modal')")
    b.wait("!document.querySelector('.ant-modal-wrap:not([style*=\"display: none\"])')")
    assert h.query(lambda: loyalty.get_balance(ids['customer'])['available_points']) == 975

    app.config['BROWSER_ROLE'] = 'letan'
    b.navigate('/admin/loyalty?tab=config')
    b.wait("document.body.textContent.includes('Khăn spa kiểm thử')")
    assert not b.js("document.body.textContent.includes('Lưu quy tắc')")
    b.button('Xác nhận giao quà'); b.button('Đã trao quà cho khách', "document.querySelector('.ant-modal')")
    b.wait("document.body.textContent.includes('Đã giao quà')")
    b.screenshot('gift-handover-1440')
    app.config['BROWSER_ROLE'] = 'staff'
    b.navigate('/admin/reviews')
    b.wait("document.body.textContent.includes('Dịch vụ chu đáo')")
    assert not b.js('!!window.bad')
    b.button('Trả lời khách'); b.wait("document.querySelector('.ant-drawer-open textarea#content')")
    b.type('.ant-drawer-open textarea#content', 'Spa cảm ơn bạn đã ghé thăm.')
    b.button('Lưu phản hồi', "document.querySelector('.ant-drawer-open')")
    b.wait("document.body.textContent.includes('Spa cảm ơn bạn đã ghé thăm.') && !document.querySelector('.ant-drawer-open')")
    assert h.query(lambda: ReviewReply.query.count()) == 1
    b.screenshot('review-reply-1440')

    app.config['BROWSER_ROLE'] = 'admin'
    b.navigate(f"/admin/chat?conversation={ids['conversation']}")
    b.wait("document.querySelector('#chat-message-input') && document.body.textContent.includes('Xin tư vấn')")
    b.wait("[...document.querySelectorAll('.care-message img')].some(i=>i.naturalWidth===8)", 'customer service picker photo')
    b.type('#chat-message-input', 'Bản nháp giữ khi chuyển trang')
    b.navigate('/admin/dashboard')
    b.wait("document.body.textContent.includes('Hiệu quả kinh doanh')")
    app.config['BROWSER_AI_FAIL'] = True
    b.button('Tạo tóm tắt cho khoảng đang xem')
    b.wait("document.body.textContent.includes('AI kiểm thử tạm thời')")
    assert len(ai_calls) == 1
    app.config['BROWSER_AI_FAIL'] = False
    b.button('Tạo tóm tắt cho khoảng đang xem')
    b.wait("document.querySelector('[data-testid=business-ai-result]')")
    assert len(ai_calls) == 2
    assert not b.js("[...document.querySelectorAll('a')].some(a=>a.href.includes('ui=legacy'))")
    b.screenshot('dashboard-ai-1440')
    b.navigate(f"/admin/chat?conversation={ids['conversation']}")
    b.wait("document.querySelector('#chat-message-input')?.value==='Bản nháp giữ khi chuyển trang'")
    b.click('.care-chat-thread .ant-collapse-header')
    b.wait("document.querySelector('input[aria-label=\"Nhân viên nhận hội thoại\"]')")
    b.choose('Nhân viên nhận hội thoại', 'Kiểm thử staff')
    b.button('Giao phụ trách')
    b.wait("document.body.textContent.includes('Đã phân người phụ trách')")
    b.click('.care-chat-thread .ant-collapse-header')
    b.drop_response(f"/api/chat/conversations/{ids['conversation']}/messages")
    b.click('[data-testid=chat-send]')
    b.wait("document.querySelector('#chat-message-input')?.value==='' && document.body.textContent.includes('Bản nháp giữ khi chuyển trang')")
    assert h.query(lambda: TinNhan.query.filter_by(noidung='Bản nháp giữ khi chuyển trang').count()) == 1
    b.screenshot('chat-reconciled-1440')

    # Responsive, explicit empty states, and role gates.
    for width in [360, 390, 768, 1024, 1440]:
        b.viewport(width)
        for path in ['/admin/loyalty?tab=redemptions', '/admin/reviews', f"/admin/chat?conversation={ids['conversation']}", '/admin/dashboard']:
            b.navigate(path)
            b.wait("!document.querySelector('.ant-skeleton')")
            b.screenshot(f"care-{path.split('?')[0].split('/')[-1]}-{width}")
            assert not b.js('window.__uiErrors.length'), b.js('window.__uiErrors')
    app.config['BROWSER_ROLE'] = 'letan'
    b.navigate('/admin/reviews', ready="document.body.textContent.includes('không có quyền')")
    app.config['BROWSER_ROLE'] = 'staff'
    b.navigate('/admin/loyalty', ready="document.body.textContent.includes('không có quyền')")
    app.config['BROWSER_ROLE'] = 'manager'
    b.navigate('/admin/loyalty?tab=transactions')
    b.wait("document.body.textContent.includes('Bổ sung điểm kiểm thử')")
    b.navigate('/admin/page-does-not-exist', ready="document.body.textContent.includes('Không tìm thấy trang')")
    b.screenshot('admin-404')
    print('Admin care browser check passed. Screenshots:', artifacts)
finally:
    h.close()

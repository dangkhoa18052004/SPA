# Đợt 6 Chăm sóc khách hàng và hoàn thiện tổng quan

Triển khai ngày 17/10/2026 theo [kế hoạch thống nhất quản trị](../plans/2026-10-16-thong-nhat-giao-dien-admin.md). Điểm thưởng, đánh giá và tin nhắn dùng chung `AdminShell` với các màn Đợt 1–5. Tổng quan mới có thêm số liệu và tóm tắt AI ngay trên trang. Bản Jinja được giữ để đối chiếu trong Đợt 7.

## Các màn đã chuyển

| Màn | Chức năng | Quyền |
| --- | --- | --- |
| `/admin/loyalty` | Tổng quan ví; tìm khách; chi tiết điểm/hạng và lịch sử; cộng/trừ có lý do; cấu hình tích/dùng điểm và ngưỡng hạng; tạo/sửa/ngừng quà hoặc voucher; tra mã và xác nhận giao quà | Admin/quản lý quản trị; lễ tân chỉ tra mã/giao quà |
| `/admin/reviews` | Lọc tên khách, số sao, dịch vụ, nhân viên, tình trạng phản hồi; đọc chi tiết; thêm/sửa/xóa phản hồi chính thức | Admin/quản lý; nhân viên chỉ các đánh giá thuộc mình. Lễ tân không xem |
| `/admin/chat` | Tìm khách/tin, lọc chưa đọc, phân trang; đọc/gửi; giữ bản nháp; phân/gỡ người phụ trách; nội dung dịch vụ có ảnh | Admin/quản lý/lễ tân xem hộp thư; nhân viên chỉ hội thoại được giao |
| `/admin/dashboard` | Thực thu dịch vụ/gói; AOV; lượt giao dịch; lịch/khách mới/tỷ lệ hủy; biểu đồ ngày/tháng và bảng số liệu; dịch vụ được đặt nhiều; trạng thái lịch; quy mô spa/nhân sự; tóm tắt AI | Phần kinh doanh và AI chỉ admin/quản lý. Lễ tân/nhân viên giữ tổng quan công việc theo quyền |
| URL quản trị không tồn tại | Trang lỗi trong khung chung, có đường về tổng quan | HTTP 404; các API vẫn kiểm tra quyền riêng |

## Cách dùng

- Điểm thưởng: chọn **Chăm sóc → Điểm thưởng**, sau đó chọn mục cần làm. Điện thoại dùng ô chọn mục để tên mục luôn đọc được. Lễ tân chỉ thấy **Tra mã và giao quà**. Kiểm tra khách, mã và món quà trước khi xác nhận đã trao.
- Điều chỉnh điểm: tìm khách → **Điều chỉnh điểm** → cộng/trừ, số điểm và lý do → **Lưu điều chỉnh**. Nếu mất phản hồi, dữ liệu và khóa yêu cầu được giữ trong tab, kể cả chuyển trang/tải lại. Mở lại khách để kiểm tra cùng yêu cầu trước khi tạo điều chỉnh khác.
- Quà/voucher: trường giảm tiền, phần trăm và điều kiện đơn chỉ xuất hiện cho loại phù hợp. Quà vật lý không bị buộc nhập các trường voucher bị ẩn. Ngừng cho đổi giữ các lượt đã đổi và lịch sử.
- Đánh giá: chọn bộ lọc → **Trả lời khách** hoặc **Sửa phản hồi**. Đóng khi đang viết có nhắc giữ nội dung. Phản hồi hiển thị công khai; không sửa hay xóa nội dung đánh giá thay khách.
- Tin nhắn: chọn khách → nhập nội dung → **Gửi tin nhắn**. Bản đang viết được giữ riêng theo tài khoản và hội thoại trong `sessionStorage` của tab. Trên điện thoại có nút quay lại danh sách; đổi người phụ trách nằm trong phần mở rộng.
- Tổng quan: chọn khoảng ngày, ngày/tháng, rồi xem số liệu. **Tạo tóm tắt cho khoảng đang xem** chỉ gọi AI khi bấm. Lỗi AI có thông báo riêng; báo cáo tiếp tục dùng được. Thay khoảng ngày không giữ nhầm tóm tắt của kỳ trước.

## Tránh ghi lặp và kiểm tra quyền

Điều chỉnh điểm tái sử dụng idempotency của backend. Khi chưa rõ kết quả, form giữ nguyên dữ liệu và khóa cũ; bấm kiểm tra lại không tạo thêm giao dịch điểm. Xác nhận giao quà dùng service hiện có: lần lặp trả kết quả đã giao, không trừ điểm hoặc giao quà lần nữa.

API chat hiện chưa có khóa gửi tin được lưu trong database. Giao diện giữ danh sách mã tin trước lần gửi, nội dung và người gửi; khi mất phản hồi sẽ đọc lại lịch sử, không tự gửi POST lần nữa. Một tin mới khớp chính xác được nhận diện để khôi phục giao diện. Nếu chưa xác định được, màn hình giữ cảnh báo, cho kiểm tra tiếp và chỉ mở lại soạn tin sau thao tác xác nhận đã xem lịch sử. Cơ chế này không tuyên bố bảo đảm gửi đúng một lần giữa mọi thiết bị/phiên.

Các request đọc chat kiểm tra tài khoản hoạt động và quyền hội thoại trước khi đánh dấu đã đọc. Nhân viên không đọc/trả lời hội thoại của người khác; người bị vô hiệu không tiếp tục dùng JWT cũ để chat. Chỉ admin/quản lý/lễ tân được phân hội thoại; người nhận phải là kỹ thuật viên đang hoạt động. Endpoint danh sách người nhận chỉ trả mã/tên.

Tin nhắn thường tối đa 5.000 ký tự. Thẻ dịch vụ/ảnh raster nhúng từ bộ chọn dịch vụ khách hàng cũ được giữ tương thích, với giới hạn tổng nội dung 4.000.000 ký tự và giới hạn request của ứng dụng. React hiển thị nội dung chữ như văn bản; ảnh chỉ nhận đường tài nguyên nội bộ, HTTPS hoặc base64 JPEG/PNG/WebP/GIF; không nhúng SVG hay giao thức thực thi.

Tin nhắn mới ghi giờ UTC và đổi sang giờ Việt Nam khi hiển thị. Không tự sửa giờ các tin nhắn cũ vì chưa xác minh quy ước ghi của từng bản trước đây.

## Số liệu và AI

Tái sử dụng `/api/analytics/*` và `/api/ai/business-summary`; không thay công thức doanh thu, hoa hồng hoặc lương. Thực thu theo ngày nhận thanh toán; sử dụng buổi liệu trình không tạo thêm doanh thu. Dịch vụ được đặt nhiều đếm lịch đã xác nhận/đang làm/hoàn thành; giao diện giải thích số lượt không phải thực thu.

Khoảng ngày và nhóm biểu đồ lưu trong URL, tối đa 366 ngày. Các số về quy mô spa và nhân viên có ca hôm nay được trình bày riêng, có giải thích ca dự kiến không đồng nghĩa đã chấm vào. Bảng số liệu cung cấp cách đọc thay cho biểu đồ.

AI chỉ nhận các số liệu tổng hợp từ service đang có. Kết quả tách số liệu đã đối chiếu, nhận xét và gợi ý; service tiếp tục loại nội dung có số chưa được xác minh. Client chờ tối đa 30 giây cho yêu cầu tóm tắt, phù hợp ngân sách provider 22 giây của backend. Không tự gọi lại AI khi lỗi, không gọi AI thật trong kiểm thử.

## Bật tại máy và bản dự phòng

Không có migration của Đợt 6. Build và khởi động lại ứng dụng để đọc cấu hình:

```powershell
cd E:\Project\Spa\SPA
npm --prefix frontend run build
venv\Scripts\python.exe run.py --https
```

Nếu ứng dụng đang chạy, dừng bằng Ctrl+C ở cửa sổ đang chạy rồi dùng lệnh trên, sau đó Ctrl+F5 trong trình duyệt. Giữ cách chạy HTTPS đang dùng để chấm công GPS hoạt động. Công cụ không khởi động lại notification worker hoặc gửi thông báo thật trong đợt triển khai này.

```dotenv
BUSINESS_PORTAL_ENABLED=true
ADMIN_BOOKING_REACT_ENABLED=true
ADMIN_BILLING_REACT_ENABLED=true
ADMIN_CATALOG_REACT_ENABLED=true
ADMIN_PEOPLE_REACT_ENABLED=true
ADMIN_CARE_REACT_ENABLED=true
```

Đã bổ sung các cờ Đợt 2–6 vào `.env` local: trước khi triển khai lần này, mã Đợt 2–5 tồn tại nhưng các cờ tương ứng chưa có trong file và cấu hình mới đọc trả false. Các hành trình trình duyệt Đợt 2–5 được chạy lại trước khi bật. Các cấu hình tài khoản, khóa MFA, GPS 500 m/sai số 150 m và ngày chuyển lương được giữ nguyên.

Nguồn và `.env.example` để cờ Đợt 6 mặc định false cho các môi trường chưa cập nhật. Để quay lại cụm chăm sóc cũ, tắt `ADMIN_CARE_REACT_ENABLED` và khởi động lại web theo quy trình vận hành; có thể đối chiếu trực tiếp `?ui=legacy`. Khi cờ bật, menu và dashboard không đặt liên kết buộc người dùng về tổng quan cũ. Các template in/xuất và đường dự phòng vẫn giữ cho Đợt 7.

## Kiểm chứng

Các bài thử dùng database riêng; email, ngân hàng và AI được giả lập. Không tạo giao dịch, điều chỉnh điểm, gửi tin hoặc đăng ký bảo mật trên dữ liệu vận hành để kiểm thử.

- Build TypeScript/Vite production và kiểm thử Vitest.
- Các nhóm pytest về rollout, chat, điểm/quà/hạng/voucher, đánh giá, tổng quan, AI, bảo mật và booking.
- Kiểm thử JavaScript cho AI chat, thanh toán hóa đơn và loyalty.
- Hành trình Chrome Đợt 6: tạo quà vật lý, quy tắc, điều chỉnh điểm mất phản hồi rồi chuyển trang, lễ tân giao quà, nhân viên trả lời đánh giá, bản nháp và ảnh thẻ dịch vụ trong chat, phân người phụ trách, gửi mất phản hồi chỉ có một tin, AI lỗi/thử lại, giới hạn vai trò và trang 404.
- Đối chiếu 360/390/768/1024/1440 px; kiểm tra không tràn ngang/không lỗi JavaScript và xem ảnh thực tế. Đã thu gọn chọn mục điểm thưởng và phần giao người phụ trách sau khi xem ảnh điện thoại.
- Chạy lại các hành trình khung quản trị, đặt lịch, hóa đơn/bán gói, danh mục/liệu trình và nhân sự/lịch làm. Chưa thay thế nghiệm thu Safari/thiết bị thật hoặc Đợt 7.

Kết quả lượt cuối: **142 kiểm thử Python đạt, 1 bỏ qua**; **54 kiểm thử frontend đạt**, **20 kiểm thử JavaScript đạt**, build production đạt. Đây là các nhóm liên quan đã chạy trong Đợt 6, không phải tuyên bố chạy lại toàn bộ bộ kiểm thử dự án, hồi quy PostgreSQL đầy đủ hoặc đã nghiệm thu production. Hành trình Chrome Đợt 6 đạt, lưu 27 ảnh trong thư mục bên dưới.

Ảnh và log local:

- Đợt 6, gồm thẻ dịch vụ có ảnh: `.test-tmp/admin-care-browser-bab4c124`.
- Khung quản trị: `.test-tmp/admin-shell-browser-5d0217df`.
- Đặt lịch: `.test-tmp/admin-booking-browser-c1c3c8df`.
- Hóa đơn/bán gói: `.test-tmp/admin-billing-browser-f07849b3`.
- Danh mục/liệu trình: `.test-tmp/admin-catalog-browser-f2227e8c`.
- Nhân sự/lịch làm: `.test-tmp/admin-people-browser-950730c5`.
- Log kiểm thử: `.test-tmp/admin-care-python.log`, `.test-tmp/admin-care-frontend.log`, `.test-tmp/admin-care-js.log`, `.test-tmp/admin-care-build.log`.

Lệnh có thể chạy lại:

```powershell
npm --prefix frontend test
venv\Scripts\python.exe -m pytest -q tests/test_admin_care.py tests/test_admin_shell.py tests/test_booking_gifts_reviews.py tests/test_loyalty_gift_fulfillment.py tests/test_loyalty_service.py tests/test_loyalty_tiers.py tests/test_loyalty_voucher_percent.py tests/test_ai_booking_agent.py tests/test_phase2_analytics_review.py tests/test_analytics_package_revenue.py tests/test_phase4_ui.py tests/test_phase0_security.py --disable-warnings
venv\Scripts\python.exe tests/admin_care_browser_check.py
```

Workflow chất lượng bổ sung hành trình Đợt 6 và ảnh kết quả. Chưa push/kích hoạt CI từ lần làm này. Đợt 7 tiếp tục nghiệm thu toàn bộ, thiết bị thật, vận hành và dọn mã dự phòng sau khi đủ điều kiện.

# Giai đoạn 5 Đề xuất dịch vụ và chăm sóc khách hàng

Triển khai tiếp mục 9 của `BinSpa_KeHoach_NangCap_GPS_ChamCong_UI_Refactor.docx`: tracking, ranking, dịch vụ liên quan, notification, KPI baseline và feature flag. Tái sử dụng engine đề xuất và notification outbox hiện có; bổ sung phần đo lường, quyền lựa chọn của khách và màn CRM nội bộ.

## Chức năng

| Màn hình | Cách sử dụng |
| --- | --- |
| `/admin/crm` | Admin, quản lý, lễ tân tìm khách theo tên/điện thoại/email; lọc nhóm; xem lịch sử dịch vụ, lịch sắp tới, lựa chọn nhận email và 20 thông báo gần nhất. Nhân viên thường không xem danh sách khách chung. |
| `/admin/crm` → Hiệu quả đề xuất | Chỉ admin/quản lý xem lượt hiển thị, CTR@6, lượt nhấp có đặt/mua trong 7 ngày, coverage dịch vụ và thời gian xử lý API p95. Lọc tối đa 90 ngày. |
| `/profile#communication` | Khách tự bật/tắt nhắc lịch, dặn dò sau dịch vụ, mời đánh giá và cá nhân hóa. Mặc định ba loại email chăm sóc chưa đăng ký. |
| Trang chủ/danh sách/chi tiết/đặt lịch | Giữ engine ranking hiện có, catalog đầy đủ và section dịch vụ/gói liên quan. Trang chủ khôi phục token từ phiên trước khi tải danh sách. Màn đặt lịch React ghi sự kiện chọn dịch vụ bằng API đang có. |

Nhóm khách chỉ dùng lịch đã hoàn thành: đang quay lại trong 30 ngày; chưa quay lại trên 30 đến 60 ngày; trên 60 ngày; chưa hoàn thành dịch vụ nhưng tạo tài khoản trong 30 ngày; chưa từng sử dụng và tài khoản cũ hơn. Lịch sắp tới hiển thị riêng, không giả định khách có lịch sắp tới là cần liên hệ thêm. Không suy diễn tình trạng da hoặc vấn đề sức khỏe từ dữ liệu này.

Các trọng số trong Word là đề xuất để thử nghiệm. Giữ công thức ranking đã được kiểm thử ở `docs/personalized-recommendations.md`, không thay trọng số khi chưa có baseline. Có thể tắt cá nhân hóa để dùng popularity; danh mục, bộ lọc và luồng đặt lịch vẫn hoạt động.

## Đo hiệu quả

- `IntersectionObserver` chỉ ghi khi ít nhất 50% thẻ hiển thị trong 600 ms hoặc khách chủ động nhấp. Chỉ xét tối đa sáu thẻ đầu trong danh sách đang hiển thị; thẻ bị ẩn hoặc nằm ngoài viewport chưa được tính.
- Chỉ ghi cho khách đã đăng nhập, không tạo mã định danh khách ẩn danh, không ghi chuỗi tìm kiếm, địa chỉ IP hoặc fingerprint. Không gửi dữ liệu sang dịch vụ phân tích bên ngoài.
- Server kiểm tra target đang hoạt động, thứ tự 1–6, customer từ JWT; dedupe theo khách/vị trí/target trong bucket 10 phút; giới hạn 120 impression mới/phút/khách.
- Click phải thuộc impression của chính khách, chỉ ghi lần đầu. CTR bằng lượt impression có click chia lượt impression. Không có mẫu thì trả `null` và giao diện ghi chưa có dữ liệu.
- Đặt/mua sau nhấp: impression có click và có sự kiện backend `book_service` cùng dịch vụ hoặc `purchase_package` cùng gói, của cùng khách, trong bảy ngày sau click. Sự kiện frontend không được dùng làm chuyển đổi. Một impression chỉ tính tối đa một lần; đây là attribution mô tả, không chứng minh quan hệ nhân quả và không đồng nghĩa doanh thu/hoàn thành dịch vụ.
- Cohort theo ngày impression, ranh giới ngày Việt Nam. Chuyển đổi có thể tiếp tục cập nhật trong cửa sổ bảy ngày. Không backfill lượt hiển thị cũ hoặc tạo số liệu mẫu trong database thật.
- Coverage: số dịch vụ đang hoạt động được hiển thị chia tổng dịch vụ đang hoạt động. Mẫu timing là thời gian xử lý các API GET đề xuất/catalog thành công; lấy tối đa một mẫu mỗi 10 giây/endpoint/process, báo cáo p95 trên tối đa 5.000 mẫu gần nhất trong khoảng ngày. Không phải đo thời gian tải trang hoặc độ trễ mạng phía khách. Lỗi lưu timing không làm hỏng danh mục.

## Thông báo và quyền riêng tư

Email xác nhận đặt/hủy lịch, OTP và bảo mật tiếp tục theo nghiệp vụ giao dịch. Ba loại email chăm sóc chỉ enqueue khi khách đã bật đúng lựa chọn; worker kiểm tra lại lựa chọn/tài khoản trước khi gửi. Bật nhắc lịch tạo lịch nhắc cho các hẹn tương lai đã xác nhận; không gửi bù dặn dò/đánh giá của buổi cũ. Tắt một loại email dừng các job chưa gửi của loại đó. Email đã gửi hoặc đã được nhà cung cấp nhận không thể thu hồi.

Khách chỉ sửa lựa chọn của mình. Server ghi version và audit các boolean, dùng khóa khách để serialize lần ghi đầu và từ chối phiên bản cũ bằng 409. Nhân viên xem lựa chọn nhưng không thể bật đồng ý thay khách. Khi tắt cá nhân hóa, hệ thống xóa interaction frontend và impression/click của khách; sự kiện backend phục vụ booking/mua và dữ liệu nghiệp vụ vẫn được giữ. Các API tương tác kiểm tra lại sau khóa khách để không ghi mới sau khi lựa chọn đã rút.

Lệnh bảo trì có dry-run, mặc định giữ 90 ngày; chỉ xóa telemetry và interaction frontend cũ, không xóa lịch hẹn, thanh toán, audit đồng ý hoặc sự kiện nghiệp vụ:

```powershell
venv\Scripts\python.exe -m flask --app wsgi:app crm prune-metrics --dry-run
venv\Scripts\python.exe -m flask --app wsgi:app crm prune-metrics
```

Chưa chạy lệnh xóa trên dữ liệu cơ sở. Cần bố trí lệnh này vào lịch bảo trì vận hành; worker hiện có không tự chạy tác vụ xóa telemetry.

## Migration và bật tính năng

Migration `20261015_0020` bổ sung `customer_preference`, `customer_preference_audit`, `recommendation_impression`, `recommendation_timing`; không đổi bảng/giá trị tiền hoặc chấm công.

```powershell
cd E:\Project\Spa\SPA
venv\Scripts\python.exe -m flask --app wsgi:app db upgrade
npm --prefix frontend ci
npm --prefix frontend run build
```

Sau migration, cấu hình:

```dotenv
CRM_ENABLED=true
CUSTOMER_CONSENT_ENABLED=true
PERSONALIZATION_ENABLED=true
RECOMMENDATION_METRICS_ENABLED=true
```

`CRM_ENABLED` bật màn quản trị; `CUSTOMER_CONSENT_ENABLED` duy trì lựa chọn của khách và kiểm tra consent độc lập, kể cả khi cần tắt màn CRM. Giữ cờ consent bật sau khi đã nhận lựa chọn thật. `PERSONALIZATION_ENABLED=false` chuyển sang popularity; `RECOMMENDATION_METRICS_ENABLED=false` dừng ghi impression/timing và ẩn báo cáo. CRM/consent/metrics trong `.env.example` mặc định tắt, giữ tương thích database chưa migrate.

Khởi động lại **cả Flask và notification-worker** sau khi đổi cấu hình. Nếu dùng bộ chạy tại máy này, Ctrl+C ở cửa sổ đang chạy rồi chạy lại `python run.py --https` như trước; lệnh này quản lý cả web và worker. Không chỉ khởi động lại trình duyệt hoặc riêng web khi đổi chính sách thông báo.

Database tại máy đã sao lưu vào `backups/binspa-before-crm-phase5-20261015-073754.dump` (archive đã kiểm tra đọc được), nâng từ 0019 lên 0020. Đối chiếu trước/sau: 23 khách, 82 lịch hẹn, 46 hóa đơn, 31 thanh toán, 4 phiên công, 1 kỳ lương được giữ nguyên. Không tạo lịch/thu tiền hoặc gửi email thật để kiểm thử.

## Kiểm thử và giới hạn

```powershell
venv\Scripts\python.exe -m pytest -q tests/test_crm.py tests/test_recommendations.py tests/test_post_care_email.py
venv\Scripts\python.exe scripts/test_with_postgres.py -- -q --disable-warnings
venv\Scripts\python.exe tests/phase5_browser_check.py
npm --prefix frontend test
node --test tests/*.test.cjs
```

Kiểm thử backend bao gồm opt-in, audit/version, tài khoản inactive, phân quyền, rút lựa chọn, dừng job, worker kiểm tra lại, không gửi bù quá khứ, dedupe, click của khách khác, attribution quá hạn/cùng khách/cùng target, cold-start/kill switch, giữ dữ liệu nghiệp vụ khi dọn telemetry, và migration trên SQLite/PostgreSQL. Database test riêng, không dùng `DATABASE_URL` thật làm database test.

Kết quả ngày 15/10/2026: build production thành công; **676 kiểm thử Python đạt**, chạy trên PostgreSQL tạm riêng và SQLite; **8 kiểm thử frontend đạt**; **40 kiểm thử JavaScript đạt**. Bộ PostgreSQL tạm đã dừng sau khi kiểm thử.

Chrome thực đã chạy toàn bộ hành trình ở 360/390/768/1440 px: tab ẩn chưa được ghi impression; đặt lịch React → ghi impression/click/chọn dịch vụ → sự kiện booking backend; bốn vai trò CRM; drawer lịch sử; báo cáo KPI; khách bật nhắc lịch rồi rút consent/cá nhân hóa, kiểm tra dữ liệu đã dừng/xóa. 27 ảnh tại `.test-tmp/phase5-browser-a3ad8477`. Email provider bị chặn bằng giả lập trong browser test. Hành trình booking/gói/quà tặng/VietQR của giai đoạn 4 cũng đã chạy lại thành công với 41 ảnh tại `.test-tmp/phase4-browser-a6279922`.

Bốn cờ giai đoạn 5 đã được bật trong `.env` của máy này để áp dụng ở lần khởi động tiếp theo. Không khởi động lại worker từ công cụ để tránh kích hoạt gửi email thật trong lúc triển khai; người vận hành cần dừng và chạy lại bộ `run.py --https` như hướng dẫn trên. Workflow CI đã thêm hành trình giai đoạn 5; chưa push hay kích hoạt CI từ phiên làm việc này.

Giai đoạn này đạt baseline và feature flags; đánh giá CTR/conversion thực tế cần khách sử dụng sau khi bật. Chưa chạy thử nghiệm A/B có đối chứng, chưa triển khai marketing tự động/campaign gửi hàng loạt. Phần BI/giám sát và chuẩn bị phát hành đã được triển khai tiếp tại [giai đoạn 6](BI_RELEASE_PHASE6.md); tài liệu đó ghi rõ các mục nghiệm thu còn lại.

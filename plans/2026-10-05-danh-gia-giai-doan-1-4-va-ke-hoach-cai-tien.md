# Bin Spa — Kiểm tra giai đoạn 1–4 và kế hoạch cải tiến

Ngày đánh giá: **05/10/2026**. Tài liệu đối chiếu: `BinSpa_Roadmap.docx` ở thư mục gốc, phiên bản ghi trong tài liệu là **01/10/2026**.

**Kết luận: chưa hoàn thành toàn bộ giai đoạn 1–4 theo roadmap.** Các luồng đặt lịch, đánh giá, tích/đổi điểm, bán gói, sử dụng liệu trình và gửi dặn dò đã có nền tảng tốt và vượt qua phần lớn kiểm thử. Tuy nhiên còn lỗi liên kết doanh thu, khởi tạo database mới, thiếu hoa hồng/hạng thành viên và một số lỗi giao diện ảnh hưởng trực tiếp tới thao tác.

Đây là báo cáo kiểm tra và đề xuất thay đổi; chưa sửa mã ứng dụng. Các đoạn “prompt cho AI Coding Agent” trong Word được dùng để đọc yêu cầu nghiệm thu, không được thực thi như một yêu cầu triển khai mới.

## 1. Phạm vi và giới hạn kiểm thử

- Đọc nội dung Word bằng cách giải nén DOCX và phân tích XML; đối chiếu model, migration, route, service, HTML/CSS/JavaScript và các test hiện có.
- Chạy toàn bộ pytest, toàn bộ test JavaScript hiện có và các script kiểm tra giao diện bằng Chrome/Edge thật ở chế độ ẩn.
- Dùng SQLite thử nghiệm riêng và tài khoản giả; không thay đổi database vận hành, không thu tiền hoặc gửi email thật.
- Quan sát 40 trạng thái giao diện ở kích thước 1440, 768 và 390px: dashboard, lịch hẹn, đánh giá, điểm thưởng, lương, bán gói, danh sách gói, các tab hồ sơ, ba bước đặt lịch và hộp đánh giá.
- Chưa khảo sát người dùng thật. Nhận xét về khả năng thao tác là đánh giá từ giao diện, vị trí điều khiển và các luồng kiểm thử.
- 11 test PostgreSQL bị bỏ qua vì thiếu `TEST_LOYALTY_POSTGRES_URL`; chưa xác nhận khóa đồng thời và migration trên PostgreSQL trong lượt này. Thanh toán/email bên ngoài được mô phỏng; chưa nghiệm thu môi trường production.

## 2. Kết quả kiểm thử thực tế

| Nhóm | Kết quả | Ý nghĩa |
| --- | --- | --- |
| Python: toàn bộ `tests` | **406 passed, 11 skipped, 0 failed, 0 errors**, 829,99 giây | Logic và các regression hiện có đạt trên môi trường thử; test không bao phủ mọi yêu cầu roadmap |
| JavaScript: 5 file `.test.cjs` | **28 passed, 0 failed** | Kiểm tra hành động lịch hẹn, thanh toán, hóa đơn, liệu trình và điểm thưởng |
| `admin_package_booking_browser.py` | Đạt | Lễ tân đặt lịch hỗn hợp dịch vụ/gói/quà, đổi khách xóa lựa chọn cũ, giữ buổi, tải lại, desktop/tablet/mobile |
| `loyalty_customer_browser_check.py` | Đạt | Bộ lọc đổi thưởng, xác nhận/hủy, nhấn lặp, thử lại sau mất phản hồi, ưu đãi/chi tiết/copy, phục hồi tab, bàn phím và 390px |
| `billing_browser_check.py` | Đạt | Hoàn thành lịch, phân quyền KTV, đóng/tải lại thanh toán, tiền mặt, QR mở lại, hóa đơn dịch vụ/gói và PDF A5 một trang; 4 email dặn dò qua provider giả |
| Kiểm tra Chrome bổ sung | Hoàn tất 40 quan sát; không có lỗi JavaScript không được xử lý trong các trạng thái đó | Đặt lịch dùng gói qua nút gửi thật → API hoàn thành → khách gửi đánh giá thành công; phát hiện vấn đề vị trí nút và responsive |
| Script cũ `phase4_ui_check.py` | **Không đạt** | Assertion còn mong payload cũ, thiếu `the_item_id`; không phải bằng chứng chức năng đặt lịch hiện tại bị hỏng |
| `flask db upgrade` trên SQLite rỗng | **Không đạt: `NoSuchTableError: lichhen`** | Migration baseline không tạo bảng; cần khắc phục đường cài mới |
| Kiểm tra liên kết doanh thu bán gói → analytics | **Không đạt về nghiệp vụ tổng doanh thu** | Gói đã thanh toán 1,2 triệu nhưng dashboard/biểu đồ vẫn 0; thêm 300 nghìn dịch vụ chỉ hiện 300 nghìn |

Lần chạy Node đầu bị sandbox chặn tạo tiến trình (`EPERM`); chạy lại ngoài sandbox đạt 28/28. Pytest có 7.714 cảnh báo, chủ yếu API cũ của SQLAlchemy và `datetime.utcnow`; không gây test thất bại trong lượt này.

Kết quả pytest theo nhóm chính: booking core 13; availability 23; bộ lọc ngày 14; analytics/review 10; packages/care 32; email dặn dò 19; notification runtime 11. Các nhóm mở rộng loyalty, hóa đơn, quà tặng, sale channel và regression khác cũng nằm trong tổng 406.

## 3. Đối chiếu hoàn thành với roadmap

| Giai đoạn | Đã có và được kiểm tra | Thiếu hoặc chưa đạt | Đánh giá |
| --- | --- | --- | --- |
| **1 — Booking core và dữ liệu** | Service dùng chung; tính tổng thời lượng; ca làm và overlap; auto assign; chuẩn hóa status backend; hủy trước/sau mốc 4 giờ; soft-delete dịch vụ; migration bổ sung | Cài DB mới chỉ bằng migration thất bại. Bộ lọc admin thiếu `pending` và `in_progress`; nút Reset bị ẩn. Hồ sơ khách chưa dịch `in_progress` sang tiếng Việt | **Cốt lõi đạt các test hiện có; chưa thể chốt hoàn tất** |
| **2 — Analytics và verified review** | API doanh thu dịch vụ theo thanh toán, khách mới theo ngày tạo, thống kê lịch, top dịch vụ; review sở hữu lịch completed, chống trùng, rating hợp lệ; UI đánh giá/phản hồi | Dashboard chưa hiển thị đủ KPI hủy, tỷ lệ hủy, giá trị trung bình, khách mới và top dịch vụ. Doughnut đang là trạng thái lịch, chưa có cơ cấu dịch vụ. Chưa thấy average rating/count được tích hợp vào danh sách nhân viên/lịch KTV. Tổng doanh thu chưa cộng bán gói | **Backend chính có; báo cáo/UI còn thiếu** |
| **3 — Loyalty, commission/payroll** | Wallet và ledger điểm; tích điểm khi thanh toán; reserve/redeem/refund; idempotency; voucher tiền/%; quà vật lý; UI lịch sử/đổi thưởng/ưu đãi | Không có policy ngưỡng hạng, hạng hiện tại/tiến độ lên hạng. Không có `CommissionEntry` hoặc tương đương, mức hoa hồng theo dịch vụ, snapshot chống thay đổi lịch sử, hoặc phần hoa hồng trong tính lương | **Chưa hoàn thành; thiếu một phần nghiệp vụ lớn** |
| **4 — Gói liệu trình và automation** | Mua/thanh toán/cấp thẻ; chủ sở hữu/hạn/số buổi; reserved → consumed/released; quà tặng riêng; không trừ buổi lặp; job lưu DB, reminder 24h/2h cho lịch confirmed, post-care/review-request, retry/claim chống gửi lặp | Doanh thu gói có hàm tổng riêng nhưng chưa nối dashboard/analytics. Lựa chọn dùng gói đặt sau nút xác nhận trên mobile. Script UI cũ lệch API mới. Chưa thử gửi mail/provider và PostgreSQL production thật | **Luồng gói/job cơ bản đạt; tích hợp báo cáo và nghiệm thu còn thiếu** |

`lifetime_earned` trong wallet là một số liệu lịch sử; chưa có logic hạng thành viên nên không thể coi trường đó là đã hoàn thành yêu cầu `tier_progress`.

Hai lỗi đặt đầu tài liệu Word: availability và custom date đã có sửa và test. API kiểm tra lịch có phân biệt reason và frontend báo lỗi API thay vì ghi “Đã bận”. Tuy vậy UI hiện chỉ hiển thị nhân viên có ca/trùng lịch; reason `not_working` không được vẽ thành thẻ “Không có ca làm”. Nếu nghiệm thu đúng từng dòng của Word, cần thống nhất lại cách hiển thị này. Date picker đã có, nhưng thao tác Reset chưa sử dụng được từ màn hình dù hàm và test logic vẫn đạt.

## 4. Các phát hiện có bằng chứng cụ thể

| Mã | Phát hiện và cách tái hiện | Nguồn/bằng chứng | Tác động |
| --- | --- | --- | --- |
| F01 | Mua gói 1.200.000đ bằng API → xác nhận HTTP 200 → `paid_package_revenue = 1200000` nhưng chart, doanh thu hôm nay/tháng = 0. Thêm thanh toán dịch vụ 300.000đ → chart/KPI = 300.000đ, tổng đúng phải là 1.500.000đ | `analytics_service.py` chỉ truy vấn `ThanhToan`; tiền gói nằm ở `GoiDichVuPurchase`. [Kết quả tái hiện](../tests/runtime_phase4_audit/business-results.json) | Báo cáo tổng doanh thu thấp hơn thực thu |
| F02 | Chạy migration DB rỗng dừng ở `20261001_0002` vì thiếu `lichhen` | Baseline `f3b12dbde06b_initial_baseline.py:17` có `upgrade(): pass`. [Log](../tests/runtime_phase4_audit/fresh-migration.txt) | Không cài mới được chỉ bằng `flask db upgrade` |
| F03 | Tổng hợp lương chỉ cộng lương ca, thưởng và khấu trừ; không tìm thấy model/migration/service hoa hồng | `salary_manage_bp.py:14`, `models.py`, toàn bộ migrations/services | Chưa đáp ứng giai đoạn 3.2 |
| F04 | Cấu hình loyalty không có tier thresholds; UI ví chỉ có điểm khả dụng/tổng tích/tổng dùng | `loyalty_models.py:21`, `loyalty_models.py:35`, `loyalty_service.py` | Chưa có hạng/tiến độ theo roadmap |
| F05 | Nhóm nút Lọc/Reset ở admin appointments có `d-none d-lg-flex`; CSS có `d-none !important` nhưng không có `d-lg-flex`. Dropdown chỉ có confirmed/completed/cancelled | `templates/admin/appointments.html`, `css/admin/utilities.css`. Cả 1440/768/390px đều không có nút Reset trong điều khiển hiển thị | Không thể xóa toàn bộ bộ lọc bằng một thao tác; thiếu hai trạng thái |
| F06 | Giờ 08:00 xuất hiện hai lần; lựa chọn giờ là danh sách HTML cố định dù đã có API available-slots | `appointment_create.html:123–124`, `customers/appointments.js`; `results.json` mục `time-options` | Khách chọn giờ không có ca/chỗ rồi phải quay lại |
| F07 | Ở 390px, nút “Xác nhận đặt lịch” bắt đầu tại y≈1206 nhưng select “Sử dụng liệu trình” tại y≈1794. Ở 768px tương ứng y≈847 và y≈1450 | [DOM đo vị trí](../tests/runtime_phase4_audit/results.json), `appointment_create.html` | Khách có gói dễ xác nhận trước khi thấy lựa chọn dùng gói |
| F08 | Bảng lịch admin kéo ngang. Ở 768px nút “Tạo hóa đơn” nằm một phần ngoài màn hình; ở 390px cột thao tác hoàn toàn ngoài khung nhìn ban đầu | [Ảnh 768px](../tests/runtime_phase4_audit/768-admin-appointments.png), [ảnh 390px](../tests/runtime_phase4_audit/390-admin-appointments.png) | Lễ tân khó tìm thao tác cần làm trên tablet/mobile |
| F09 | Dashboard đặt 390px nhưng `innerWidth` đo được 732px; nhóm biểu đồ vẫn bị ép hai cột bởi style inline `2fr 1fr` | `dashboard.html:87`, mục `390-admin-dashboard` trong `results.json` | Layout dashboard mobile chưa đạt; chỉ kiểm tra `scrollWidth <= innerWidth` sẽ bỏ sót |
| F10 | Menu admin đặt Điểm thưởng/Đánh giá/Trang cá nhân trước Dashboard và Lịch hẹn. Menu hồ sơ mobile bắt đầu Điểm thưởng/Đánh giá; Lịch hẹn nằm cuối vùng tab kéo ngang | `admin_layout.js:112`, `customer/profile.html`, [ảnh hồ sơ](../tests/runtime_phase4_audit/390-profile-appointments.png) | Các việc hằng ngày không ở vị trí dễ tìm nhất |
| F11 | Màn hình lương hiển thị cả tháng và ngày dù đang lọc theo tháng; `.d-flex !important` thắng `style.display='none'` | `templates/admin/salaries.html`, `admin/salaries.js`, `admin/utilities.css`; [ảnh](../tests/runtime_phase4_audit/1440-admin-salary.png) | Người dùng không biết bộ lọc nào có hiệu lực |
| F12 | Hồ sơ khách thiếu mapping `in_progress`; danh sách nhân viên/KTV chưa tích hợp rating average/count dù API review có tính | `customers/profile.js:353`, `admin/staff.js`, `admin/staff.html`, `admin/my_schedule.js` | Trạng thái hiện tiếng Anh; chưa dùng được đủ thông tin đánh giá |

Các tọa độ phụ thuộc dữ liệu thử gồm hai KTV và màn hình cao 900px; đây là bằng chứng về thứ tự các phần trong trang, không phải quy định tọa độ cho thiết kế mới.

## 5. Đánh giá giao diện và cách bố trí nút

Giao diện desktop có phân nhóm và khoảng cách tương đối rõ. Wizard ba bước đặt lịch, tóm tắt giá, nhãn còn trống, các nút hành động theo quyền/trạng thái, xác nhận đổi thưởng và hóa đơn có thể tiếp tục sau khi đóng là các phần đang hữu ích. Chưa cần thiết kế lại toàn bộ.

Vấn đề chính là **ưu tiên thao tác**, **thứ tự thông tin trước khi xác nhận** và **bảng rộng trên mobile**. Nên sửa như sau:

| Khu vực | Bố trí đề xuất |
| --- | --- |
| Menu admin | Tổng quan → Lịch hẹn → Hóa đơn → Bán gói → Khách hàng; nhóm Danh mục: Dịch vụ/Gói; nhóm Nhân sự: Nhân viên/Ca/Lương; nhóm Chăm sóc: Điểm thưởng/Đánh giá/Tin nhắn; Trang cá nhân ở cuối |
| Hồ sơ khách | Lịch hẹn → Liệu trình → Điểm thưởng → Hóa đơn → Đánh giá → Tài khoản; đưa chỉnh sửa thông tin/đổi mật khẩu vào Tài khoản. Mobile có tab hiện hành rõ và dấu hiệu có thể kéo ngang |
| Đặt lịch | Chọn dịch vụ → chọn nguồn dùng buổi gói/quà hoặc trả tiền lẻ → ngày/giờ còn chỗ → chọn/tự xếp KTV → tóm tắt cuối → xác nhận. Khách luôn thấy nguồn buổi và số tiền còn phải trả trước nút xác nhận |
| Nút wizard | Desktop: Quay lại bên trái, Tiếp theo/Xác nhận bên phải. Mobile: một CTA chính rộng, có thể sticky trên thanh điều hướng dưới; chừa chỗ cho bàn phím và chat, không che dữ liệu tóm tắt |
| Danh sách lịch admin | Desktop giữ bảng nhưng cột thao tác dễ truy cập. Tablet/mobile chuyển thành card chứa giờ, khách, dịch vụ, trạng thái và một hành động tiếp theo. “Xem chi tiết” phụ; “Hủy/Sửa” trong menu phụ |
| Hành động lịch hẹn | Pending → Xác nhận; confirmed/in_progress → Hoàn thành theo quyền; completed chưa hóa đơn → Tạo hóa đơn; hóa đơn chưa trả → Thanh toán; đã trả → Xem/In hóa đơn. Luồng hiện đã có nhiều quy tắc đúng; chỉ chỉnh mức nhấn mạnh và vị trí |
| Bộ lọc | Ngày + Trạng thái + Tìm kiếm + “Xóa bộ lọc” luôn truy cập được. Custom: Từ ngày/Đến ngày/Lọc nằm cùng nhóm. Hiển thị khoảng ngày đang áp dụng và số kết quả |
| Lương | Chỉ hiện trường tháng hoặc ngày tương ứng chế độ; thêm cột hoa hồng/chi tiết sau khi có nghiệp vụ. Xuất PDF dùng kiểu nút phụ, đỏ dành cho hành động xóa/hủy |
| Dashboard | KPI gọn, chung phạm vi ngày; số thực thu dịch vụ/gói/tổng được ghi rõ. Mobile một cột biểu đồ, không giữ inline grid hai cột |
| Kích thước nút | Đặt mục tiêu vùng chạm ít nhất 44×44px trên mobile; nút icon có tên truy cập được và focus rõ; không dùng màu làm dấu hiệu duy nhất |

Đây là đề xuất UX; chưa có đo thời gian hoàn thành tác vụ hoặc khảo sát người dùng để khẳng định mọi người đều thao tác dễ dàng.

## 6. Bảng kế hoạch thay đổi

P0: cần sửa trước khi chốt số liệu/cài đặt. P1: thiếu nghiệp vụ hoặc cản thao tác chính. P2: cải thiện sự rõ ràng và bảo trì. Ước lượng là ngày công cho một lập trình viên quen repo, chưa phải lịch cam kết.

| Thứ tự | Ưu tiên | Thay đổi cụ thể | Phạm vi chính | Ước lượng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- | --- |
| 1 | **P0** | Nối doanh thu bán gói vào analytics/dashboard; trả số riêng dịch vụ, gói và tổng. Dùng số tiền thực thu sau ưu đãi, ngày thanh toán thống nhất; lượt dùng gói không sinh doanh thu lần hai | `analytics_service`, `package_service`, dashboard API/JS | 1–2 ngày | Gói 1,2 triệu + dịch vụ 300 nghìn → tổng 1,5 triệu; webhook/complete lặp không tăng tổng; cùng bộ lọc ngày cho KPI/chart |
| 2 | **P0** | Có schema baseline đầy đủ cho DB mới, cùng quy trình nhận diện/stamp DB cũ đã tồn tại; kiểm tra nâng cấp giữ dữ liệu | `migrations`, tài liệu cài đặt | 1–2 ngày | Upgrade DB rỗng tới head và DB mẫu cũ đạt; không reset DB; kiểm tra model/schema và rollback phù hợp trên SQLite/PostgreSQL thử |
| 3 | **P1** | Thêm policy hoa hồng theo dịch vụ và `CommissionEntry` snapshot; khi completed ghi đúng một lần; cộng hoa hồng vào payroll và chi tiết/Xuất PDF | Model/migration, service hoa hồng/payroll, appointment complete, UI lương | 3–5 ngày | Complete lặp không nhân đôi; đổi tỷ lệ không sửa lịch sử; lương = lương ca + hoa hồng + thưởng − khấu trừ; có quy tắc base amount cho buổi gói/quà/ưu đãi |
| 4 | **P1** | Thêm ngưỡng hạng, metric tiến độ và UI hạng/tiến độ; xác định ảnh hưởng của refund và điều chỉnh thủ công | Loyalty model/config/service, hồ sơ khách | 1–2 ngày | Đổi điểm không làm mất tiến độ; hoàn tiền theo policy; test các ngưỡng; giữ nguyên đối soát ledger/available/reserved hiện có |
| 5 | **P1** | Hiện nút “Xóa bộ lọc” ở mọi màn hình; đủ 5 trạng thái; dùng chung mapping trạng thái cho hồ sơ/admin | Appointments template/JS/CSS, customer profile | 0,5–1 ngày | Người dùng click Reset thật xóa ngày/trạng thái/tìm kiếm và tải lại bảng/KPI; lọc được pending/in_progress; UI không lộ code tiếng Anh |
| 6 | **P1** | Bỏ giờ trùng; dùng slot khả dụng theo tổng thời lượng và ca. Khi hết chỗ gợi ý ngày/giờ khác, lỗi kiểm tra có nút thử lại; tránh phản hồi ngày cũ ghi đè | Appointment API/service và customer booking JS/template | 1–2 ngày | Chỉ chọn được slot phù hợp; nhiều dịch vụ tính tổng đúng; không nhầm lỗi API với bận; auto assign còn kiểm tra lại server |
| 7 | **P1** | Đưa chọn liệu trình/quà lên trước tóm tắt và xác nhận; hiển thị dịch vụ nào dùng buổi, dịch vụ nào trả lẻ; CTA mobile thuận tay | Customer appointment template, packages JS/CSS | 1–1,5 ngày | Khách có gói thấy lựa chọn trước khi gửi; số buổi và số tiền rõ; không che CTA bởi navbar/chat/keyboard; mixed booking vẫn đúng |
| 8 | **P1** | Sửa dashboard mobile hai cột; card lịch admin trên tablet/mobile hoặc cột thao tác sticky; giảm chiều cao các KPI phụ | Dashboard template/CSS, admin tables/appointments | 1–2 ngày | 390/768px giữ đúng viewport; thao tác chính thấy được không phải kéo bảng ngang; nội dung dài vẫn đọc được |
| 9 | **P2** | Hoàn thiện KPI và biểu đồ cơ cấu/top dịch vụ, phạm vi ngày dùng chung; bổ sung average rating/count cho admin/KTV | Dashboard/review/staff APIs và UI | 1–2 ngày | Hiển thị KPI đúng cùng range, top/service mix dùng API; review xác minh được, average/count đúng và không lộ dữ liệu ngoài quyền |
| 10 | **P2** | Sắp menu theo tần suất dùng và vai trò; hồ sơ đưa Lịch hẹn/Liệu trình lên đầu, gom phần tài khoản | Admin layout JS, customer profile | 0,5–1 ngày | Lễ tân/KTV thấy đúng chức năng; tab mobile hiện hành dễ nhận biết; link trực tiếp và quay lại vẫn giữ tab |
| 11 | **P2** | Sửa ẩn/hiện bộ lọc lương bằng class/hidden nhất quán, bỏ xung đột `.d-flex !important`; nút Xuất PDF là nút phụ | Salaries template/JS, CSS utilities | 0,5 ngày | Chọn tháng chỉ hiện tháng, chọn ngày chỉ hiện ngày; query, tiêu đề và PDF cùng bộ lọc |
| 12 | **P2** | Thống nhất vùng chạm, nhãn icon, thứ bậc nút chính/phụ và dialog xác nhận hành động hủy | CSS components, dialog/UI liên quan | 0,5–1 ngày | Dùng được bằng bàn phím, focus/nhãn rõ; nút mobile đạt mục tiêu 44px; không lẫn nút xuất với nút nguy hiểm |
| 13 | **P1** | Cập nhật script UI cũ theo `the_item_id`; thêm kiểm thử tích hợp doanh thu gói/KPI, migration DB rỗng, Reset bằng click và viewport thực | `tests`, script browser, tài liệu QA | 0,5–1 ngày | Không hạ yêu cầu test để pass; bắt được F01/F02/F05/F09; script cũ kiểm tra đúng nguồn quyền lợi |
| 14 | **P1 trước nghiệm thu** | Cấu hình PostgreSQL test riêng; kiểm tra migration/concurrency; smoke email/provider có chủ đích; test hồi quy giai đoạn 1–4 sau các thay đổi | Test env, notification worker, tài liệu | 1–2 ngày | 11 test đang skip được chạy; full suite và browser smoke đạt; chứng minh worker gửi/ retry đúng ở môi trường cần nghiệm thu |

Nên làm 1–2–5 trước để xử lý lỗi hiện hữu dễ gây hiểu nhầm; sau đó hoàn tất nghiệp vụ 3–4 và luồng booking 6–7; tiếp theo responsive/dashboard/menu 8–12. Các test ở 13 phải được bổ sung cùng từng thay đổi, rồi thực hiện nghiệm thu 14. Các task độc lập có thể xen kẽ; chưa nên coi giai đoạn 1–4 đã xong để chốt hồ sơ hoặc chuyển sang nghiệm thu AI.

## 7. Kịch bản nghiệm thu sau khi sửa

| Vai trò | Luồng cần chạy | Điều kiện đạt |
| --- | --- | --- |
| Khách | Dịch vụ → nguồn buổi/tiền lẻ → ngày/giờ → KTV → xác nhận → lịch của tôi | Số tiền/buổi đúng, lỗi hiện đúng nơi, không bỏ sót lựa chọn dùng gói |
| Khách | Đổi voucher/quà → xem ưu đãi → áp dụng → thanh toán | Điều kiện/hạn rõ; nhấn lặp không trừ điểm hai lần; hạng không giảm do redeem |
| Lễ tân | Tìm khách → đặt hỗn hợp gói/lẻ → xác nhận → thu tiền → in | Thao tác thấy trên 390/768/1440px; tài chính không sinh lặp |
| KTV | Lịch của tôi → thực hiện → hoàn thành → xem đánh giá/lương | Chỉ lịch được phép; buổi gói/hoa hồng/job phát sinh một lần |
| Quản lý | Bán gói + dịch vụ → dashboard cùng range → tổng hợp lương | Tổng thực thu đối chiếu được; mức hoa hồng lịch sử giữ nguyên |
| Vận hành | DB mới + nâng DB cũ → worker → retry lỗi mail | Schema đúng, giữ dữ liệu, job không gửi/trừ lặp |

## 8. Tệp bằng chứng của lượt kiểm tra

- [Kết quả pytest XML](../tests/runtime_phase4_audit/pytest-results.xml).
- [40 quan sát UI và các tọa độ điều khiển](../tests/runtime_phase4_audit/results.json).
- [Tái hiện thiếu doanh thu gói qua API](../tests/runtime_phase4_audit/business-results.json).
- [Log migration database rỗng](../tests/runtime_phase4_audit/fresh-migration.txt).
- Script kiểm tra bổ sung: `tests/runtime_phase4_audit/audit_ui.py`, `audit_business.py`; ảnh tương ứng trong cùng thư mục.
- Ảnh/artefact của Edge: `tests/admin-package-booking-preview.tmp`, `tests/loyalty-customer-browser-49653.tmp`, `tests/billing-preview.tmp`.

Thư mục `tests/runtime_phase4_*` và các artefact `.tmp` đã được `.gitignore` loại khỏi Git. Những link bằng chứng này dùng trên workspace hiện tại; nếu chia sẻ báo cáo cần sao chép kèm các bằng chứng. Mã ứng dụng, migration hiện có và file Word gốc không bị sửa trong lượt đánh giá.

## 9. Kết quả thực hiện bảng kế hoạch (05/10/2026)

| # | Trạng thái | Đã làm | Kiểm chứng |
| --- | --- | --- | --- |
| 1 | Xong | Analytics/dashboard cộng tiền bán gói (`payable_amount`, `status='paid'`, theo `paid_at`) với thanh toán dịch vụ; API trả riêng dịch vụ/gói/tổng; `/api/analytics/summary` và dashboard dùng một khoảng ngày cho KPI và biểu đồ | `test_analytics_package_revenue.py`: 1,2 triệu + 300 nghìn = 1,5 triệu; xác nhận lặp, dùng buổi gói, gói trả bằng điểm không cộng thêm |
| 2 | Xong | Baseline tạo schema gốc khi DB rỗng, no-op khi DB cũ; `scripts/detect_db_revision.py` nhận diện revision để `flask db stamp`; [hướng dẫn](../docs/DATABASE_MIGRATIONS.md) | `test_fresh_migration.py` trên SQLite và PostgreSQL: DB rỗng → head khớp model, DB cũ giữ dữ liệu, downgrade/upgrade lại |
| 3 | Xong | Mức hoa hồng theo dịch vụ (% hoặc cố định), `CommissionEntry` snapshot một lần/lịch-dịch vụ, cột hoa hồng trong lương tháng/ngày/PDF/lương của tôi, chi tiết hoa hồng; [quy tắc base amount](../docs/COMMISSION_AND_TIERS.md) | `test_staff_commission.py` (10 test) |
| 4 | Xong | Ngưỡng hạng cấu hình được, điểm xét hạng tính từ ledger (redeem không trừ, refund điểm tích có trừ, điều chỉnh tay theo cấu hình), thẻ hạng/tiến độ cho khách và admin | `test_loyalty_tiers.py` (11 test) |
| 5 | Xong | Nút "Xóa bộ lọc" luôn hiện, đủ 5 trạng thái, dòng tóm tắt bộ lọc + số kết quả, tìm kiếm giữ khi phân trang; hồ sơ khách dùng nhãn trạng thái từ server | `test_admin_appointment_filters_ui.py`; click chuột thật trong `ui_improvements_browser_check.py` |
| 6 | Xong | Giờ đặt lịch lấy từ `/available-slots` theo tổng thời lượng nhiều dịch vụ, không còn giờ trùng; hết chỗ thì gợi ý ngày/giờ gần nhất; lỗi API có nút Thử lại, không báo nhầm là bận; chặn phản hồi cũ | `test_booking_time_slots.py` |
| 7 | Xong | Chọn liệu trình/quà ở bước 1, tóm tắt ghi "Dùng buổi gói"/"Còn phải trả", tóm tắt ngay trên nút xác nhận; CTA mobile dính đáy, tránh thanh điều hướng và nút chat | Kiểm tra trình duyệt 390/768/1440px |
| 8 | Xong | Dashboard bỏ grid inline, một cột trên mobile; lịch hẹn admin thành thẻ ≤1100px, desktop cho cột chữ xuống dòng; KPI phụ gọn trên mobile | `innerWidth` = độ rộng giả lập ở 390/768/1440px, không nút thao tác nào ngoài khung |
| 9 | Xong | KPI: thực thu tách dịch vụ/gói, giá trị TB/giao dịch, lịch hẹn, lịch hủy + tỷ lệ, khách mới; biểu đồ cơ cấu dịch vụ + top dịch vụ; điểm TB/số đánh giá ở danh sách nhân viên và trang lịch KTV | `test_ui_navigation_and_ratings.py` |
| 10 | Xong | Menu admin theo nhóm và tần suất dùng cho từng vai trò; hồ sơ khách: Lịch hẹn → Liệu trình → Điểm thưởng → Hóa đơn → Đánh giá → Tài khoản, mặc định mở Lịch hẹn, URL giữ tab | Như trên + trình duyệt |
| 11 | Xong | Bộ lọc lương dùng thuộc tính `hidden`, Xuất PDF là nút phụ, có dòng "Đang xem lương ..." | Trình duyệt: chọn tháng chỉ hiện tháng, chọn ngày chỉ hiện ngày |
| 12 | Xong | Focus rõ, vùng chạm 44px trên cảm ứng, nút icon có nhãn; hủy lịch dùng hộp xác nhận nút đỏ (Esc để thoát, focus mặc định "Quay lại") thay cho `prompt` | `test_ui_navigation_and_ratings.py` |
| 13 | Xong | `phase4_ui_check.py` cập nhật `the_item_id`, giờ tải động và id hộp đánh giá; thêm `ui_improvements_browser_check.py` | Cả hai script đạt |
| 14 | Một phần | Tạo database thử nghiệm riêng `binspa_test` trên PostgreSQL cục bộ (không đụng DB vận hành); các test PostgreSQL trước đây bị skip đều chạy | Full suite kèm `TEST_LOYALTY_POSTGRES_URL`: 471 passed, 0 skipped; `loyalty_postgres_check.py` đạt 86/86; chưa gửi email qua provider thật |

Việc còn lại / cần quyết định:
- Smoke gửi email thật qua provider cần hộp thư nhận thử và sự đồng ý gửi ra ngoài.
- `ThanhToan.ngaythanhtoan` một số luồng ghi giờ UTC (`datetime.utcnow`), còn bán gói ghi giờ Việt Nam; analytics đang so theo giá trị lưu. Nên thống nhất múi giờ ghi thanh toán trước khi chốt báo cáo theo ngày.
- `tests/booking_gifts_reviews_browser.py` đã lỗi sẵn ở bước đăng nhập → quay lại trang đặt lịch (lỗi giống hệt trên commit gốc), chưa xử lý trong lượt này.
- Thẻ "Không có ca làm" cho reason `not_working` (mục 3 của báo cáo) chưa đổi cách hiển thị; cần thống nhất nghiệp vụ.

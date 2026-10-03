# Đặt lịch theo URL, tặng dịch vụ và quản lý đánh giá

Ngày kiểm tra: 03/10/2026. Nền source: `ba0b02dbbae11199b0785b34411b3dda77904be9`.

## 1. Nguyên nhân và cách sửa preselection

Trang đặt lịch trước đây tải dịch vụ bất đồng bộ và dùng timer polling để chọn dịch vụ từ URL. Việc chọn phụ thuộc vào thời điểm DOM/API sẵn sàng; liên kết đăng nhập còn làm mất query đặt lịch. Liên kết đặt dịch vụ từ chat dùng `service_id`, khác tham số `service` của booking.

Luồng mới trong `customers/appointments.js`: `DOMContentLoaded → await loadAllServices() → await applyBookingContext() → cập nhật card/tag → await renderBooking() → summary`. Không còn polling preselection. Liên kết đăng nhập giữ query; redirect được giới hạn trong cùng website.

## 2. Chọn liệu trình

Booking lấy chi tiết liệu trình qua API kiểm tra chủ sở hữu. Chỉ hiển thị item đang cung cấp, còn hiệu lực và còn lượt. Một item khả dụng tự chọn dịch vụ và entitlement. Nhiều dịch vụ hiển thị “Dịch vụ khả dụng trong gói của bạn”, với nút chọn từng item; không tự chọn tất cả.

Khi cùng dịch vụ có nhiều nguồn, URL có `item` chọn chính xác nguồn đó. Với `treatment` hoặc `treatment&service`, nếu chỉ có một dịch vụ khả dụng thì tự chọn đúng một item: ưu tiên item gói gốc, tiếp theo gift hết hạn sớm nhất, rồi gift vô thời hạn; cùng hạn thì theo ID. Khách vẫn có thể chọn nguồn khác từ từng nút item. Nhiều dịch vụ vẫn yêu cầu khách chọn dịch vụ cụ thể. Summary trừ phần được bao phủ còn 0đ. Lỗi mạng giữ lựa chọn entitlement và có nút thử lại; backend vẫn xác minh mọi điều kiện khi đặt lịch.

## 3. URL cuối cùng

- `/appointments/create?service=<madv>`
- `/appointments/create?treatment=<mathe>`
- `/appointments/create?treatment=<mathe>&service=<madv>`
- `/appointments/create?treatment=<mathe>&service=<madv>&item=<the_item_id>`

URL cuối được dùng cho nút đặt lịch trên từng dịch vụ gốc hoặc dịch vụ tặng ở profile. Email yêu cầu đánh giá vẫn dùng `/profile?review=<malh>#appointments`; khi đã có đánh giá, liên kết mở đánh giá hiện có.

## 4–5. Migration và model gift

`20261003_0007_treatment_gifts.py` mở rộng `TheLieuTrinhItem`:

| Field | Ý nghĩa |
| --- | --- |
| `source_type` | `package` hoặc `gift`; dữ liệu cũ mặc định `package` |
| `valid_from` | Ngày bắt đầu dùng item |
| `expires_at` | Hạn riêng của item |
| `gifted_by_staff` | FK nhân viên cấp, lấy từ tài khoản xác thực |
| `gift_note` | Ghi chú cấp tặng |
| `created_at` | Thời điểm tạo; item cũ được điền thời điểm migration |

Gỡ UNIQUE `(mathe,madv)` để từng lần tặng cùng dịch vụ vẫn có item và audit riêng. Giữ PK, các FK và `LieuTrinhUsage.the_item_id` hiện có. Gift có `unit_value_snapshot=0`, không tạo giao dịch mua gói/doanh thu mới. Downgrade migration gift sẽ từ chối khi có gift nhằm bảo toàn audit.

## 6. Hiệu lực

`package_service.is_treatment_item_usable()` được dùng cho serializer, reservation và đổi lịch:

- Gói gốc: hạn riêng item nếu có, nếu không kế thừa hạn liệu trình.
- Gift: chỉ dùng hạn riêng; `NULL` nghĩa là vô thời hạn, kể cả gói gốc hết hạn.
- Ngày hết hạn được tính trọn ngày theo giờ Asia/Saigon.
- Liệu trình bị hủy, dịch vụ ngừng cung cấp, ngày trước `valid_from` hoặc sau hạn đều bị từ chối.
- Availability tính từ tổng buổi trừ `consumed` và `reserved`. Trạng thái hiển thị/lọc liệu trình xét cả item tặng còn dùng được; hạn gói gốc vẫn hiển thị riêng.

## 7. Reservation chính xác

```json
{"mathe":12,"the_item_id":41,"madv":8,"quantity":1}
```

Backend đối chiếu đủ chủ sở hữu, liệu trình, item, dịch vụ của lịch hẹn, hiệu lực hiện tại/ngày hẹn và số lượt. Khóa liệu trình trước khi tính/reserve. Ledger giữ chuyển trạng thái `reserved → released` khi hủy hoặc `reserved → consumed` khi hoàn thành; thao tác lặp không tiêu thụ thêm lượt.

Payload cũ vẫn chọn item gốc hợp lệ trước. Nếu chỉ còn một gift hợp lệ, có thể chọn nguồn đó; nhiều gift cùng dịch vụ thì yêu cầu `the_item_id`. Gift được loại khỏi giá hóa đơn như entitlement gói; lịch hỗn hợp chỉ tính dịch vụ chưa được bao phủ. Lịch được bao phủ hoàn toàn không cần tạo hóa đơn dịch vụ mới.

## 8. Migration review

`20261003_0008_review_services_reply.py` giữ `DanhGia` và UNIQUE `malh` hiện có: một đánh giá mỗi lịch hẹn. Thêm `updated_at`, bảng liên kết `DanhGiaDichVu(madg,madv)` và `ReviewReply` với một phản hồi chính thức mỗi đánh giá. Backfill liên kết đánh giá cũ từ dịch vụ thực tế trong `ChiTietLichHen`, giữ ID/nội dung/số sao/thời điểm cũ.

Lịch nhiều dịch vụ được chọn một hoặc nhiều dịch vụ thực tế cho cùng đánh giá. Frontend yêu cầu chọn rõ; API cũ không truyền `service_ids` liên kết các dịch vụ thực tế của lịch để giữ tương thích. Sửa đánh giá chỉ thay sao/nhận xét, không thay lịch, khách, nhân viên hoặc tập dịch vụ.

## 9–11. API đánh giá

| Endpoint | Chức năng |
| --- | --- |
| `POST /api/reviews` | Tạo; lịch đã hoàn thành, đúng chủ, `service_ids` thuộc lịch |
| `GET /api/reviews/my` | Đánh giá của khách, dịch vụ và phản hồi |
| `GET /api/reviews/appointments/<malh>/context` | Dịch vụ được đánh giá và đánh giá hiện có |
| `PUT /api/reviews/<madg>` | Chủ sở hữu sửa sao/nhận xét |
| `DELETE /api/reviews/<madg>` | Chủ sở hữu xóa, cascade liên kết/phản hồi |
| `GET /api/reviews/manage` | Danh sách nội bộ; lọc sao/dịch vụ/nhân viên/đã trả lời/tên, phân trang |
| `POST/PUT/DELETE /api/reviews/<madg>/reply` | Cấp, sửa hoặc xóa phản hồi chính thức |
| `GET /api/services/<madv>/reviews` | Công khai, phân trang, điểm trung bình/tổng/phân bố sao và phản hồi |

Endpoint công khai chỉ lấy review có dịch vụ thực sự trong lịch completed và khớp chủ lịch. Tên khách được che một phần; không trả email, điện thoại, mã khách/lịch/nhân viên. Nội dung được escape khi render. Thống kê truy vấn mới sau edit/delete; response không cache. Email review_request vẫn được xếp lịch sau 2 giờ.

## 12. Các UI/file chính

- Booking và auth: `app/static/js/customers/appointments.js`, `auth-session.js`, `auth.js`, `main.js`; `app/templates/customer/appointment_create.html`; `app/routes/customer_bp.py`.
- Profile/liệu trình: `app/static/js/packages.js`, `customers/profile.js`; `app/templates/customer/profile.html`.
- Gift admin: `app/static/js/admin/packages.js`, `admin/admin_layout.js`, `app/static/css/admin/packages.css` và `modals.css`.
- Review chung: `app/static/js/reviews.js`, `app/static/css/reviews.css`; `app/templates/admin/reviews.html`, `customer/service_detail.html`, `customers/service-detail.js`.
- Backend/model: `app/models.py`, `services/package_service.py`, `services/review_service.py`, `routes/package_bp.py`, `routes/review_bp.py`, `routes/service_bp.py`, `admin/admin_bp.py`, `app/__init__.py`.

Modal native ở top layer, dùng fixed/inset/auto margin, giới hạn kích thước và scroll nội dung; khóa scroll nền khi mở. Gift dùng base modal liệu trình; review dùng CSS scoped riêng. Kiểm tra receipt/payment modal cũ để tránh ảnh hưởng.

## 13. Phân quyền

- Khách đang hoạt động: chỉ liệu trình/lịch/review của mình; sửa/xóa review của mình; không được cấp gift hoặc phản hồi chính thức.
- Admin/manager: xem toàn bộ review và phản hồi; xem liệu trình/cấp gift.
- Staff đang hoạt động: xem liệu trình/cấp gift; chỉ xem/trả lời review của lịch mình thực hiện. Filter nhân viên không mở rộng phạm vi này.
- Lễ tân: quyền bán/thanh toán gói cũ được giữ; không được cấp gift hoặc quản lý review.
- Người chưa đăng nhập: xem đánh giá dịch vụ công khai. Các quyền được kiểm tra tại API, không dựa vào menu/localStorage.

## 14. Kiểm chứng và dữ liệu local

Đã sao lưu PostgreSQL local tại `instance/backups/before-booking-gifts-reviews-20261003-194031.dump`, sau đó upgrade `0006 → 0007 → 0008`. Bản backup nằm ngoài Git. Đối chiếu toàn bộ giá trị cột cũ của item/usage/review và số lượng các bảng lịch/hóa đơn/thanh toán/job: giữ nguyên. Có 4 item gốc, 4 usage, 2 review; backfill được 2 liên kết dịch vụ.

| Nhóm test theo yêu cầu | Kiểm chứng |
| --- | --- |
| 1–3: service/reload/login | Browser click CTA, đăng nhập thật trên DB thử, giữ query, reload vẫn selected |
| 4–6: single/multi/exact treatment | Browser tự chọn một dịch vụ dù có nhiều item cùng madv; ưu tiên gói gốc, rồi gift hết hạn sớm nhất; multi không chọn tất cả; exact item + 0đ |
| 7–11: gift và expiry | API audit/số buổi, unlimited/days/date, biên hết hạn, gói hết hạn nhưng gift còn dùng |
| 12–17: ledger/billing/exact source | API reserved/released/consumed, hết 2 lượt, hóa đơn hỗn hợp, đúng item cùng madv |
| 18–23: verified/public/privacy | API owner/completed/subset; public đúng dịch vụ, tên che, không email/phone/IDs riêng |
| 24–27: owner CRUD | API và browser sửa/xóa; khách khác bị 403; public mất review sau xóa |
| 28–31: quản lý/reply | API admin tất cả/staff chỉ của mình; UI staff reply; phản hồi trên service detail |
| 32: statistics | API điểm trung bình/phân bố cập nhật sau sửa/xóa; UI public lấy dữ liệu mới |

Kết quả: bộ regression đầy đủ **213 passed** tại mốc kiểm tra; sau các kiểm tra biên bổ sung, chạy lại nhóm thay đổi **38 passed** (gồm 2 case expiry mới), rồi bộ feature cuối **29 passed**. **12 test JavaScript passed**; **10 file JS parse thành công**. Browser mới kiểm tra luồng đặt lịch/gift/review, URL sai, lỗi mạng không làm mất lựa chọn miễn phí và 5 viewport 1920/1440/1024/768/390. Browser regression hóa đơn/thanh toán cũng pass: resume/đóng–mở QR, cash, hóa đơn hỗn hợp, in A5, căn giữa/scroll/nút đóng/Escape. Server browser test chạy tuần tự vì fixture SQLite in-memory dùng chung một kết nối. Migration được kiểm tra trên SQLite và PostgreSQL độc lập trước khi áp dụng local. 6 API đọc dữ liệu local sau upgrade đều HTTP 200.

Lệnh tái chạy:

```powershell
python -B -m pytest -p no:cacheprovider -q --disable-warnings
python -B tests/booking_gifts_reviews_browser.py
python -B tests/billing_browser_check.py
node tests/appointment-actions-ui.test.cjs
node tests/invoice-payment-ui.test.cjs
node tests/invoice-receipt-ui.test.cjs
```

Browser dùng DB thử độc lập và mock email. Không tạo gift/review thử hoặc gửi email thật tới khách trong DB local. Ảnh kiểm tra nằm ở `tests/booking-gifts-reviews-preview.tmp/` và `tests/billing-preview.tmp/` (không đưa vào Git).

Khi đưa source lên môi trường khác, chạy `python -m flask --app run.py db upgrade` trước khi restart web/worker; môi trường đó cần backup riêng. Migration chỉ đã được áp dụng vào PostgreSQL local của workspace này.

Đối chiếu yêu cầu gửi lại: đã bổ sung preselection cho một dịch vụ có nhiều nguồn package/gift và chạy lại browser toàn luồng thành công. Browser xác nhận chỉ chọn một usage, giữ tổng 0đ, gift còn dùng khi gói gốc hết hạn, và URL có `item` vẫn chọn đúng item được chỉ định. PostgreSQL local vẫn ở revision `20261003_0008`; không cần migration bổ sung cho thay đổi JavaScript này.

# Nhân viên đặt lịch bằng gói / liệu trình của khách

Admin, manager và lễ tân chọn khách trong **Quản lý lịch hẹn → Thêm lịch hẹn**, rồi chọn **Dịch vụ thông thường** hoặc **Sử dụng gói / liệu trình**. Mặc định là dịch vụ thông thường.

## Thay đổi source

- `app/admin/appointment_manage_bp.py`: truyền package usages và người tạo vào service; endpoint đọc liệu trình theo khách; chi tiết lịch trả nguồn cover và audit.
- `app/services/appointment_service.py`: lưu nguồn đặt lịch và người tạo; tiếp tục reserve và tạo notification jobs trong cùng transaction.
- `app/services/package_service.py`: yêu cầu exact item khi đặt lịch từ admin; kiểm tra source package/gift trong hàm kiểm tra hiệu lực dùng chung. Giữ nguyên ledger và khóa liệu trình.
- `app/routes/package_bp.py`: bổ sung filter `makh` chính xác, giữ `search`, `status` và quyền quản lý hiện tại.
- `app/models.py`: thêm `LichHen.booking_source`, `created_by_staff` và phân biệt FK người tạo với FK KTV thực hiện.
- `app/static/js/admin/appointments.js`, `app/templates/admin/appointments.html`, `app/static/css/admin/appointment-treatments.css`: chọn nguồn/item, dịch vụ mua thêm, số buổi do backend trả, kiểm tra ngày, reset khách, xử lý hết lượt, chi tiết cover và giao diện responsive.
- `migrations/versions/20261004_0010_appointment_booking_audit.py`: migration additive sau head thực tế `20261003_0009`.
- `tests/test_admin_package_booking.py`, `tests/admin-package-booking-ui.test.cjs`, `tests/admin_package_booking_browser.py`: kiểm thử backend, state frontend và Edge DOM.
- `tests/test_loyalty_migration.py`: bổ sung bảng lịch hẹn vào database test tối thiểu và cập nhật kỳ vọng head khi chạy `db upgrade`.

Các thay đổi loyalty/thanh toán có sẵn trong workspace được giữ nguyên. Không sửa migration 0001–0009.

## API và quyền

| Endpoint | Thay đổi / quyền |
| --- | --- |
| `POST /api/admin/appointments` | Nhận `package_usages`; admin/manager/letan đang hoạt động; không cấp quyền tạo lịch cho staff/KTV. |
| `GET /api/admin/appointments/customers/<makh>/treatments` | Endpoint mới chỉ đọc cho admin/manager/letan đang hoạt động. Query backend `TheLieuTrinh.makh == makh`. |
| `GET /api/admin/packages/treatments?makh=<id>` | Filter khách chính xác kết hợp được với search/status. Giữ quyền admin/manager/staff, không thêm letan. |
| `GET /api/admin/appointments/<malh>` | Thêm coverage theo dịch vụ, nguồn đặt lịch và người tạo. Giữ quyền xem lịch hiện tại. |

Frontend tự gọi endpoint chỉ đọc khi chọn khách, không tải danh sách tất cả khách rồi lọc bằng JavaScript. Response được lấy từ `serialize_treatment()` và chỉ giữ các trường phục vụ booking; không trả giá trị kế toán snapshot hay history quản trị. Lễ tân không được cấp quyền tặng dịch vụ, sửa gói hoặc quản lý liệu trình.

## UI và payload

Mỗi liệu trình là một card mở được. Item `package` có badge **Trong gói**, item `gift` có badge **🎁 Spa tặng**, kèm số buổi còn/tổng, consumed, reserved, hạn hiệu lực, người tặng và ghi chú. Các item cùng dịch vụ ở nhiều gói hoặc giữa package/gift vẫn là các lựa chọn riêng. Mỗi dịch vụ trong một lịch chỉ chọn một nguồn.

Chỉ chọn được item `usable == true`, `available_sessions > 0` và còn hiệu lực vào ngày chọn. Frontend dùng trực tiếp `available_sessions` và `effective_expires_at` của backend. Gift có hạn riêng, không bị chặn bởi ngày hết hạn của gói chính.

Ví dụ một lịch gồm Massage dùng liệu trình và Gội đầu thanh toán riêng:

```json
{
  "makh": 15,
  "madv_list": [3, 8],
  "ngaygio": "2026-10-10T10:30",
  "manv": 5,
  "ghichu": "CSKH đặt lịch giúp khách",
  "package_usages": [
    {"mathe": 12, "the_item_id": 41, "madv": 3, "quantity": 1}
  ]
}
```

Khi đổi khách, toàn bộ lựa chọn liệu trình và các dịch vụ được cover bị xóa; dịch vụ thường mua thêm được giữ. Phản hồi load của khách cũ không thể ghi đè dữ liệu khách mới. Khi đổi ngày ngoài hạn, item và dịch vụ liên quan được bỏ chọn kèm cảnh báo. Khi backend trả 400/409 cho booking có package usages, frontend tải lại liệu trình và hiển thị lỗi gốc; không âm thầm chuyển item hết lượt thành dịch vụ tính tiền.

## Reservation, hủy, hoàn thành và hóa đơn

Route chỉ gọi `appointment_service.create_appointment()`. Service gọi `reserve_usages(..., require_item_id=True)` cho nguồn admin, cùng transaction tạo lịch/chi tiết/jobs. Hàm reserve kiểm tra chủ sở hữu, treatment, exact item, dịch vụ trong lịch, quantity, source, số buổi và hiệu lực cả hiện tại lẫn ngày hẹn. `lock_treatment()` giữ nguyên cơ chế khóa chống hai request dùng cùng buổi cuối. Thất bại rollback toàn bộ lịch, usage và jobs.

Usage mới có state **reserved**. Hủy tiếp tục dùng `transition_usages(..., 'released')` để trả đúng buổi. Hoàn thành dùng **consumed**; thao tác hoàn thành lặp không consume thêm. `total_sessions` không bị sửa trong luồng booking.

Invoice tiếp tục chỉ cover dịch vụ có usage **consumed**. Lịch mixed chỉ xuất hóa đơn dịch vụ thường; lịch được package/gift cover toàn bộ không tạo hóa đơn 0đ. Lịch staff đặt vẫn mang `LichHen.makh` của khách nên xuất hiện ở tài khoản khách. Email xác nhận và jobs nhắc lịch 24h/2h giữ nguyên.

## Audit và triển khai

Staff booking lưu `booking_source='admin'`, `created_by_staff=g.current_user.manv`; không tin giá trị audit client gửi. Customer tự đặt lưu `booking_source='customer'`, người tạo staff null. Service hỗ trợ `source='ai'` cho tích hợp sau này.

Migration mới giữ dữ liệu cũ với nguồn **legacy**, người tạo null; không suy đoán người tạo. Đã kiểm tra upgrade/downgrade trên database test và upgrade từ head cũ. Ngày 04/10/2026 đã áp dụng migration `0010` vào PostgreSQL local mà source đang dùng, sau khi xác nhận lỗi API do schema vẫn ở `0009`. Cả 66 lịch hẹn giữ nguyên các trường dữ liệu cũ; API danh sách, thống kê, chi tiết và liệu trình theo khách đều trả 200. Edge tải đúng 66 lịch, trang đầu 10 dòng, thống kê hoạt động và không có lỗi JavaScript. Khi triển khai source sang database khác, chạy:

```powershell
python -m flask --app run db upgrade
```

## Kiểm thử

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q --disable-warnings
node tests/admin-package-booking-ui.test.cjs
python tests/admin_package_booking_browser.py
```

Backend feature: **29 passed**, bao gồm ba role, package/gift, wrong customer/item/service, hết hạn hiện tại/ngày hẹn, hết lượt, rollback, cancel, completion idempotent, mixed/full invoice, self-booking, notification/email và hai request booking đồng thời tranh buổi cuối trên SQLite với kết nối riêng.

Frontend state: **5 passed**, gồm exact item, phân biệt nguồn, escape dữ liệu, reset khách/ngày, phản hồi bất đồng bộ và refresh khi hết lượt.

Edge DOM: **passed** với role lễ tân trên desktop 1280px, tablet 768px và mobile 390px; chọn khách, đổi khách, chọn package/gift, tạo mixed booking, reload, xem nguồn cover/audit, không có lỗi JavaScript. Email trong test được mock; kiểm thử không gửi email thật hay sửa dữ liệu vận hành.

Regression: toàn bộ bộ test cũ chạy xong với **242 passed, 6 skipped**, và một bài migration dùng fixture cũ thiếu bảng `lichhen`. Đã cập nhật fixture/head và chạy lại module migration thành công (**2 passed, 2 skipped**). Kết hợp 29 test feature mới, kết quả cuối theo từng bài test là **272 passed, 6 skipped**, không còn failure. Sáu bài PostgreSQL bị skip vì chưa cấu hình `TEST_LOYALTY_POSTGRES_URL`; concurrency của booking đã được kiểm tra trên SQLite thật với các kết nối riêng.

Các bài JavaScript regression sẵn có cho appointment actions, invoice payment, invoice receipt và loyalty: **15 passed**. Cộng 5 bài booking mới: **20 passed**. Kiểm tra cú pháp Python/JavaScript và `git diff --check` đều pass.

# Bảng đối chiếu URL quản trị — thống nhất giao diện

Lập ngày 16/10/2026 cho Đợt 1 của [kế hoạch thống nhất giao diện quản trị](2026-10-16-thong-nhat-giao-dien-admin.md). Dữ liệu lấy từ `app.url_map`, template Jinja và JavaScript hiện có. Quyền ở cột "Hiện trong menu" chỉ là điều kiện hiển thị liên kết; máy chủ vẫn kiểm tra từng API.

Ký hiệu cột "Giao diện": **React** = đã chạy trong khung quản trị chung `AdminShell`; **Jinja** = trang cũ, menu mở bằng tải lại trang.

## Đã nằm trong khung chung (Đợt 1–6)

| URL | Giao diện | Cờ cấu hình | Hiện trong menu | API chính | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| `/admin/dashboard` | React | `BUSINESS_PORTAL_ENABLED`; nội dung đầy đủ thêm `ADMIN_CARE_REACT_ENABLED` | Mọi vai trò nội bộ; số liệu kinh doanh và AI chỉ admin/quản lý | `/api/dashboard/appointments/*`, `/api/analytics/*`, `/api/ai/status`, `/api/ai/business-summary` | Khoảng ngày và nhóm ngày/tháng trong URL; thực thu, AOV, dịch vụ được đặt nhiều, trạng thái lịch, quy mô spa; tóm tắt AI trong cùng màn. Không còn liên kết mở bản cũ khi bật Đợt 6 |
| `/admin/profile` | React | `BUSINESS_PORTAL_ENABLED` | Menu tài khoản | `/api/profile`, `/api/profile/update`, `/api/profile/upload-avatar`, `/api/profile/change-password` | Tab qua `?tab=password`. `?ui=legacy` mở bản cũ |
| `/admin/login` | React | `BUSINESS_PORTAL_ENABLED` | — | `/api/auth/login/staff` | Mặc định vào `/admin/profile`; khi hết phiên quay về `?next=` (chỉ nhận trang `/admin`, `/employee`) |
| `/admin/crm` | React | `CRM_ENABLED` | Admin, quản lý, lễ tân | `/api/admin/crm/*`, `/api/admin/recommendations/baseline` | Nhóm khách, từ khóa, trang giữ trong URL |
| `/admin/reports` | React | `BI_REPORTS_ENABLED` | Admin, quản lý | `/api/admin/bi/report` | |
| `/admin/security` | React | `STAFF_SECURITY_ENABLED` | Menu tài khoản | `/api/me/security/*` | Hộp xác minh hai bước duy nhất: `StepUpGate` ở gốc |
| `/admin/operations/{dashboard,attendance,adjustments,payroll,branches,audit}` | React | `EMPLOYEE_PORTAL_ENABLED` | Admin, quản lý | `/api/admin/operations/*`, `/api/admin/attendance*`, `/api/admin/payroll-periods*` | Trước đây có khung/menu riêng; nay dùng khung chung. `/admin/operations` = tổng quan công |
| `/admin/appointments` | React | `BUSINESS_PORTAL_ENABLED` + `ADMIN_BOOKING_REACT_ENABLED` | Admin, quản lý, lễ tân (nhân viên mở trực tiếp: chỉ lịch của mình) | `/api/admin/appointments*`, `/api/admin/staff/available`, `/api/admin/invoices/*`, `/api/admin/billing/transactions/service/<id>` | Bộ lọc `range/from/to/status/q/page/makh` và `new=1` trong URL. Đặt nhiều dịch vụ, buổi gói/quà, báo giá, nhân viên rảnh; mất phản hồi → đối soát trước khi gửi lại. Thu tiền mặt/VietQR/điểm/voucher, xem và in phiếu. `?ui=legacy` mở bản cũ |
| `/admin/customers` | React | như trên | Admin, quản lý, lễ tân | `/api/admin/customers/*`, `/api/admin/appointments?makh=`, `/api/admin/appointments/customers/<id>/treatments` | `?view=<makh>` mở hồ sơ. Sửa/khóa chỉ hiện cho admin, quản lý (đúng quyền API); thêm nhanh cho cả lễ tân |
| `/admin/invoices` | React | `BUSINESS_PORTAL_ENABLED` + `ADMIN_BILLING_REACT_ENABLED` | Admin, quản lý, lễ tân | `/api/admin/billing/transactions*`, `/api/admin/invoices/*`, `/api/admin/package-sales/<id>`, `/api/admin/packages/purchases/<id>/*` | Gộp hóa đơn dịch vụ và phiếu bán gói; lọc `type/range/from/to/status/q/page` trong URL; thu tiền đúng loại phiếu; xem và in phiếu (cửa sổ in riêng). `?ui=legacy` mở bản cũ |
| `/admin/package-sales` | React | như trên | Admin, quản lý, lễ tân | `/api/admin/package-sales*`, `/api/packages/payment-options`, `/api/admin/packages/purchases/<id>/*` | Tìm khách (kèm thêm khách vãng lai), chọn gói có xem trước, tiền mặt có tiền thối hoặc VietQR chờ ngân hàng xác nhận, điểm/voucher; mất phản hồi khi tạo phiếu → đối soát, không tạo phiếu thứ hai. Lịch sử lọc `q/status` trong URL |
| `/admin/services` | React | `BUSINESS_PORTAL_ENABLED` + `ADMIN_CATALOG_REACT_ENABLED` | Admin (API cho cả quản lý) | `/api/admin/services*`, `/api/admin/service-categories` | Lọc `status/category/q/page` trong URL; thêm/sửa trong Drawer: ảnh, giá, thời lượng, danh mục, hoa hồng, mô tả, dặn dò sau dịch vụ, trạng thái. `?ui=legacy` mở bản cũ |
| `/admin/packages` | React | như trên | Admin, quản lý (gói + liệu trình); nhân viên (chỉ liệu trình) | `/api/admin/packages`, `/api/admin/packages/treatments*` | Tab `?tab=treatments` (liên kết cũ `#treatments` tự chuyển); `?mathe=` mở chi tiết liệu trình; tặng dịch vụ. Lễ tân không còn thấy liên kết vì API từ chối |
| `/admin/packages/new`, `/admin/packages/<id>`, `/admin/packages/<id>/edit` | React | như trên | Admin, quản lý | `/api/admin/packages`, `/api/admin/packages/<id>` | Liên kết sâu giữ nguyên; tổng giá lẻ/tiết kiệm, chặn trùng dịch vụ, cảnh báo giá gói cao hơn giá lẻ, hỏi lại khi rời trang chưa lưu |
| `/admin/staff` | React | `BUSINESS_PORTAL_ENABLED` + `ADMIN_PEOPLE_REACT_ENABLED` | Admin | `/api/admin/staff/*`, `/api/admin/roles` | Lọc `role/status/q` trong URL; thêm/sửa trong Drawer (ảnh, chức vụ, vai trò, trạng thái); vô hiệu/kích hoạt. Xác minh hai bước giữ nguyên dữ liệu đang nhập. `?ui=legacy` mở bản cũ |
| `/admin/roles` | React | như trên | Admin | `/api/admin/roles*` | Thêm/sửa/xóa chức vụ, đơn giá giờ; hiện số nhân viên mỗi chức vụ, chặn xóa khi còn người giữ |
| `/admin/shifts` | React | như trên | Admin, quản lý | `/api/admin/shifts*`, `/api/admin/staff/list-all` | Lọc `from/to/assignment` trong URL (mặc định 2 tuần), tuần trước/sau; tạo/sửa ca (ca qua đêm được báo), xóa; `?maca=` mở phân/bỏ phân nhân viên |
| `/admin/approve-shifts` | React | như trên | Admin, quản lý | `/api/admin/shifts/registrations/*` | Duyệt/từ chối đăng ký |
| `/admin/my-schedule`, `/admin/register-shift` | React | như trên | Mọi vai trò nội bộ | `/api/admin/my-schedule-list`, `/api/admin/all-schedules`, `/api/admin/shifts/register`, `/api/reviews/staff/<id>` | Lịch tuần `?week=`; ca đã phân/chờ duyệt, đồng nghiệp, đánh giá; đăng ký hiện đúng trạng thái từng ca |
| `/admin/salary` | React (chỉ xem) | như trên | Admin (quản lý khi chưa bật bảng lương GPS) | `/api/admin/salaries` (GET), `/commissions`, `/export-pdf` | Lịch sử lương cũ theo tháng/ngày, hoa hồng, xuất PDF. Server từ chối mọi ghi khi `PAYROLL_V2_ENABLED` nên chỉ còn một luồng tính lương |
| `/employee/*` | React (cổng nhân viên) | `EMPLOYEE_PORTAL_ENABLED` | Nhóm "Công và lương" | `/api/me/*` (ca, chấm công, thu nhập, lịch hẹn) | Giữ điều hướng mobile riêng theo kế hoạch; có liên kết "Về trang quản trị" |
| `/admin/loyalty` | React | `BUSINESS_PORTAL_ENABLED` + `ADMIN_CARE_REACT_ENABLED` | Admin, quản lý; lễ tân chỉ tra mã/giao quà | `/api/admin/loyalty/*` | Sáu mục: tổng quan, điểm khách, giao quà, quà/voucher, lịch sử, quy tắc/hạng. Giữ `?tab=redemptions`, tìm/lọc/trang trong URL. Mất phản hồi điều chỉnh điểm giữ nguyên khóa yêu cầu qua tải lại/chuyển trang trong cùng tab |
| `/admin/reviews` | React | như trên | Admin, quản lý; nhân viên chỉ đánh giá thuộc mình | `/api/reviews/manage`, `/api/reviews/<id>/reply` | Lọc tên khách, sao, dịch vụ, nhân viên, phản hồi; thêm/sửa/xóa phản hồi chính thức; không sửa/xóa đánh giá thay khách |
| `/admin/chat` | React | như trên | Admin, quản lý, lễ tân; nhân viên có mục Tin nhắn của tôi | `/api/chat/conversations*`, `/api/admin/conversations/*` | Tìm/lọc chưa đọc/phân trang; đọc, gửi, giữ bản nháp theo tài khoản/hội thoại; kiểm tra lịch sử khi mất phản hồi; giao/gỡ người phụ trách đúng quyền. Hội thoại giữ bằng `?conversation=` |
| URL quản trị không tồn tại | React với HTTP 404 | như trên | Theo phiên nội bộ | Không gọi API nghiệp vụ riêng | Dùng cùng khung/menu và đường về tổng quan. Các màn chăm sóc kiểm tra vai trò trước khi tải dữ liệu |

## Các đường dự phòng còn giữ đến Đợt 7

| URL | Đợt | Hiện trong menu | API chính | Ghi chú cần giữ khi chuyển |
| --- | --- | --- | --- | --- |
| `/admin/my-salary` | 5 | Khi tắt cổng nhân viên | `/api/profile/my-salary` | Chuyển hướng sang `/employee/income` khi bật bảng lương GPS |
| `/admin/loyalty?ui=legacy`, `/admin/reviews?ui=legacy`, `/admin/chat?ui=legacy` | 7 | Không đặt liên kết dự phòng trong màn mới | API nghiệp vụ hiện có | Dùng để đối chiếu/quay lại khi cần; không xóa trước nghiệm thu |
| `/admin/dashboard?ui=legacy` | 7 | Không đặt liên kết trong tổng quan khi bật Đợt 6 | `/api/ai/business-summary`, `/api/ai/status` | Tổng quan React đã có tóm tắt AI và số liệu bổ sung |

## Thay đổi API ở Đợt 2 (chỉ bổ sung)

- `GET /api/admin/appointments`: thêm trường `makh`, `khachhang_sdt` và tham số lọc `makh`. Trường cũ giữ nguyên; kiểm thử ở `tests/test_admin_shell.py`.
- `GET /api/me/operations`: thêm `features.admin_booking`.

## Thay đổi phía server ở Đợt 3

- Không đổi API. Thêm cờ `ADMIN_BILLING_REACT_ENABLED` và `features.admin_billing` trong `/api/me/operations`; hàm chọn bản React/bản cũ chuyển vào `app/ui_assets.py` (`admin_portal_page`) để `package_bp` dùng chung.

## Thay đổi phía server ở Đợt 4

- Không đổi API. Thêm cờ `ADMIN_CATALOG_REACT_ENABLED` và `features.admin_catalog`.

## Thay đổi phía server ở Đợt 5 (chỉ bổ sung)

- `GET /api/admin/staff/list-all`: thêm `macv`. `GET /api/admin/my-schedule-list`: thêm `maca` (và `reg_id` cho ca chờ duyệt). Trường cũ giữ nguyên; kiểm thử ở `tests/test_admin_shell.py`.
- Cờ `ADMIN_PEOPLE_REACT_ENABLED`, `features.admin_people`.

## Khác biệt có chủ đích so với bản cũ

- "Tuần này"/"Tháng này" lấy cả tuần (thứ Hai–Chủ nhật) và cả tháng theo lịch giờ Việt Nam, để thấy lịch sắp tới trong kỳ; bản cũ dừng ở hôm nay và dùng giờ máy.
- Nút "Lịch hẹn" của khách nay lọc đúng khách (bản cũ chuyển `?makh=` nhưng trang lịch hẹn bỏ qua).
- Lễ tân không còn thấy nút Sửa/Khóa khách vì API vốn từ chối (403).
- Hóa đơn: lọc thêm "Tuần này" và khoảng ngày tùy chọn; tìm kiếm gửi khi nhấn Enter/nút tìm thay vì mỗi lần gõ.
- Bán gói: chọn khách và gói bằng một ô tìm kiếm (thay cho ô tìm + danh sách riêng); có thêm khách vãng lai ngay tại form.
- Dịch vụ: thêm lọc theo danh mục và cột hoa hồng; tìm không dấu. Dịch vụ mới chọn "ngừng" được lưu đúng trạng thái (bản cũ luôn tạo ở trạng thái mở).
- Gói: lưu xong mở trang chi tiết gói thay vì quay về danh sách; giá gói cao hơn tổng giá lẻ phải xác nhận trước khi lưu.
- Menu: lễ tân không còn thấy "Gói dịch vụ" (API vốn từ chối, trang cũ báo lỗi).
- Ca làm: quản lý thấy "Ca làm" và "Duyệt đăng ký ca" (API vốn cho phép; cần cho chấm công theo ca). Mặc định lọc 2 tuần từ đầu tuần này thay vì toàn bộ; cho phép ca qua đêm (server vốn hỗ trợ, bản cũ chặn).
- Đăng ký ca: hiện đúng ca đã đăng ký/đã được phân (bản cũ gọi API thiếu ngày nên luôn trống); ca đã bắt đầu không cho đăng ký.
- "Lịch hẹn của tôi" (khi tắt cổng nhân viên) trỏ về `/admin/appointments` ở chế độ chỉ lịch của mình, tách khỏi "Lịch làm của tôi".
- Lịch sử lương cũ chỉ xem; các nút tính/sửa lương của bản cũ (vốn bị server chặn) không còn.
- Khi bật Đợt 6, nhân viên có mục "Tin nhắn của tôi"; API vốn cho phép xem/trả lời các hội thoại được giao, không mở quyền xem hộp thư chung.
- Tin nhắn mới ghi UTC và hiển thị giờ Việt Nam. Dữ liệu tin nhắn cũ chưa được tự điều chỉnh lại múi giờ.
- Điều chỉnh điểm giữ khóa yêu cầu chưa rõ kết quả qua chuyển trang; chat kiểm tra tin mới đúng người gửi trước khi khôi phục, không tự gửi lại POST.

## Thay đổi phía server ở Đợt 6

- Thêm `ADMIN_CARE_REACT_ENABLED`, `features.admin_care`, phục vụ React cho điểm thưởng/đánh giá/tin nhắn; giữ `?ui=legacy` và dự phòng khi chưa build.
- Chat: thêm `assigned_staff_id`/`assigned_staff_name` vào danh sách, `sender_staff_id` vào tin nhắn trả cho nhân viên; thêm `GET /api/admin/conversations/assignees` chỉ trả mã/tên kỹ thuật viên hoạt động cho admin/quản lý/lễ tân.
- API chat kiểm tra tài khoản hoạt động, quyền chủ hội thoại, nội dung chuỗi không trắng tối đa 5.000 ký tự; không nhận người phụ trách đã vô hiệu.
- URL quản trị không tồn tại dùng khung lỗi React với HTTP 404 khi bật Đợt 6. Không có migration hoặc thay đổi chính sách công/lương.

## Kiểm thử đi kèm

- `tests/test_admin_care.py`: cờ/bản dự phòng/404, quyền chat, tài khoản vô hiệu, định dạng tin, thời gian UTC và phân người phụ trách.
- `frontend/src/admin/care/model.test.ts`: loại quà và trường ẩn, giao quà, ảnh an toàn, đối chiếu tin mới; navigation test có thêm các đường chăm sóc và cờ Đợt 6.
- `tests/admin_care_browser_check.py`: quà/quy tắc/điều chỉnh điểm mất phản hồi qua chuyển trang, lễ tân giao quà, nhân viên phản hồi đánh giá, chat giữ bản nháp/phân người/mất phản hồi, AI lỗi rồi thử lại, bốn vai trò, 360/390/768/1024/1440 px; DB và nhà cung cấp giả lập.

- `frontend/src/admin/navigation.test.ts`: menu theo vai trò/cờ, liên kết nội bộ, đường dẫn phân cấp.
- `frontend/src/session.test.ts`: `next` an toàn, hết phiên về đúng màn, sai mật khẩu hiện tại không bị coi là hết phiên.
- `tests/test_admin_shell.py`: bật/tắt cờ, `?ui=legacy`, chưa build vẫn dùng trang cũ, đăng nhập vẫn vào trang cá nhân.
- `tests/admin_shell_browser_check.py` (chạy tay sau khi build): một React root, điều hướng không tải lại, quay lại, bộ lọc trong URL, 4 vai trò, hồ sơ, hết phiên, đăng xuất, 360/390/768/1024/1440 px.
- `frontend/src/admin/booking/model.test.ts`: khoảng ngày theo giờ spa, tìm không dấu, báo giá trừ buổi gói, buổi gói hết hạn theo ngày, đối soát khi mất phản hồi.
- `tests/admin_booking_browser_check.py` (chạy tay sau khi build): khách vãng lai → đặt lịch; buổi gói + dịch vụ trả thêm; mất phản hồi không tạo trùng; xác nhận → check-in → hoàn thành → hóa đơn → tiền mặt có tiền thối → phiếu; đổi dịch vụ; hủy; quyền lễ tân/quản lý/nhân viên; 360–1440 px.
- `frontend/src/admin/billing/model.test.ts`: đối soát phiếu bán gói khi mất phản hồi.
- `tests/admin_billing_browser_check.py` (chạy tay sau khi build; dùng `tests/admin_browser.py`): bán gói tiền mặt có tiền thối → liệu trình kích hoạt → phiếu; mất phản hồi khi tạo phiếu không tạo trùng; VietQR hoàn tất khi ngân hàng xác nhận (giả lập bằng service của webhook); hóa đơn lọc trong URL; thu hóa đơn dịch vụ và phiếu gói từ danh sách; nhân viên bị chặn; 360–1440 px.
- `frontend/src/admin/catalog/model.test.ts`: trạng thái bán gói, giá lẻ/tiết kiệm, kiểm tra dòng dịch vụ, tiến độ liệu trình, ảnh.
- `tests/admin_catalog_browser_check.py` (chạy tay sau khi build): thêm dịch vụ có ảnh/danh mục, sửa và ngừng dịch vụ, tạo gói (tiết kiệm, chặn trùng), sửa gói qua liên kết sâu, `#treatments`, chi tiết và tặng dịch vụ, quyền nhân viên/lễ tân, 360–1440 px.
- `frontend/src/admin/people/model.test.ts`: tuần theo lịch spa, giờ ca qua đêm, trạng thái đăng ký ca.
- `tests/admin_people_browser_check.py` (chạy tay sau khi build): thêm/sửa/vô hiệu/kích hoạt nhân viên; chức vụ; quản lý tạo ca, phân/bỏ phân, xóa; nhân viên đăng ký → quản lý duyệt → hiện trong lịch tuần; lịch sử lương cũ chỉ xem; quyền; 360–1440 px.

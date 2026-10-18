# Khảo sát giao diện khách hàng — PR0

Ngày: 18/10/2026. Commit bắt đầu: `c189ad9f21e78ba423455c55e9181ef109478749`, trùng mốc kế hoạch.
Working tree ban đầu: `refactorUI_Customer.md` chưa tracked và một file khóa Word `~$nSpa_KeHoach_NangCap_GPS_ChamCong_UI_Refactor.docx` đã bị xóa. Giữ nguyên hai thay đổi này.

## Route inventory

| URL | Template / owner hiện tại | Auth / liên kết cần giữ |
|---|---|---|
| `/` | `customer/index.html`, `customers/main.js` | Guest; `#services`, `#about`, `#contact`; 6 dịch vụ giữ thứ tự API |
| `/services` | `services.html`, `customers/services.js` | Guest; filter/sort toàn bộ catalog, mặc định giữ ranking |
| `/services/<id>` | `service_detail.html`, `service-detail.js`, reviews/recommendations | Guest; `?service=<id>` khi đặt lịch |
| `/packages`, `/packages/<id>` | `packages.html`, `packages.js` | Guest xem, đăng nhập mua; server lọc `customer_sale_enabled` |
| `/appointments/create` | `appointment_create.html` hoặc `booking_react.html` | Cờ `CUSTOMER_BOOKING_REACT_ENABLED`, manifest booking và không `ui=legacy`; `service`, `treatment`, `item` |
| `/auth/login` | `login.html`, auth JS | `redirect` nội bộ, session customer đã có thì redirect |
| `/auth/register` | `register.html` | Session customer đã có thì về `/` |
| `/auth/verify-otp` | `verify_otp.html` | `registration_email` trong session hoặc `otp_email` sessionStorage |
| `/auth/forgot-password`, `/auth/reset-password` | template tương ứng | Giữ email/OTP contract hiện hành |
| `/profile` | `profile.html`, `customers/profile.js` | Route trả HTML; JS restore JWT hoặc về login |

Hash profile: `#appointments` (mặc định), `#invoices`, `#treatments`, `#loyalty`, `#reviews`, `#info`, `#edit`, `#password`, `#communication` khi CRM/consent bật. Giữ query `review=<appointment id>`, `loyalty_view=history|rewards|mine`, `loyalty_status`.

## Phạm vi và tài nguyên dùng chung

- Customer: `app/templates/customer`, `app/static/js/customers`, CSS customer, `frontend/src/customer`, routes customer, resolver assets và Vite.
- `packages.js`: customer package/detail/legacy booking/profile; admin invoices/package-sales. Không xóa hoặc đổi contract globals `PackageCare`.
- `reviews.js`: customer detail/profile và admin reviews. Giữ `ReviewUI`.
- `change-services.js`: customer profile và admin appointments. Giữ quyền do backend quyết định.
- `loyalty-payment.js`: bridge hóa đơn, booking/profile/public layout; giữ `LoyaltyPayment`, không coi đóng QR là hủy/thành công.
- `customers/main.js`: header, translations, catalog home, quick view, chat, music. Không mount React lên các vùng mà script này còn sở hữu.
- Portal admin có entry/CSS riêng (`src/main.tsx`, `style.css`); customer không import chúng.

## Môi trường và baseline trình duyệt

Preview: `python tests/customer_ui_preview.py`, loopback `127.0.0.1:5077`, SQLite in-memory từ fixture test; chỉ dữ liệu giả được ghi rõ là kiểm thử. Email bị vô hiệu hóa, không dùng DB production, SePay polling/AI tắt. Cờ booking bật riêng trong preview; public/account mặc định tắt. Không đọc/in `.env`.

Lệnh: `playwright-cli -s=customer-ui open http://127.0.0.1:5077/ --browser=msedge`, sau đó `run-code --filename=tests/customer-ui-baseline.playwright.js`.
Ảnh baseline local lưu trong `.test-tmp/customer-ui/before-*` (không đưa dữ liệu khách thật vào repo). Kết quả chi tiết sẽ được ghi vào progress sau khi lệnh hoàn tất.

Lỗi baseline quan sát được ngay trên home guest: `/api/auth/restore-session` trả 401 khi không có phiên (đúng luồng guest); `/favicon.ico` 404. Chưa có exception JS ở lần mở đầu. Phải phân biệt hai request này với regression.

## Phát hiện cần xử lý

1. `customer/api.ts` redirect cho mọi 422, trong khi 422 validation không phải luôn là JWT lỗi. Auth bridge cũng retry mọi 422: cần phân loại JSON `msg` của JWT trước retry/redirect.
2. Profile `switchSection` và `initializeProfilePage` cùng gọi tải lịch hẹn; tab hash khởi tạo gọi dữ liệu trước khi restore hoàn tất. Menu dùng `replaceState` làm mất lịch sử Back/Forward của tab.
3. Cards catalog dùng div onclick, dữ liệu text nội suy vào HTML; nên dùng link thực, escape nội dung, giữ một listener recommendation.

## Nội dung cần chủ dự án xác minh (A06)

| Nội dung | Hiện trạng | Quyết định |
|---|---|---|
| CS1 điện thoại | Text `038 782 9152`, tel `02862588687` | Chưa biết số đúng; giữ dữ liệu, không tự chọn |
| CS1/CS2 địa chỉ và giờ mở cửa | Ghi trực tiếp trong home | Giữ cả hai cơ sở; cần chủ dự án xác nhận |
| 4.9/5, 1.200+ reviews, 5.000+ khách, 100% thảo dược/hài lòng | HTML tĩnh, không có nguồn | Không coi là dữ liệu đã chứng thực; bản public mới không quảng bá số liệu chưa có nguồn |
| Testimonial Thanh Thảo / Minh Hoàng / Ngọc Mai | Nội dung HTML tĩnh | Chưa chứng minh là review thật; không dùng làm review đã xác minh |
| Kinh nghiệm trên 5 năm | HTML tĩnh | Chưa có nguồn |
| Ảnh/video | Asset hiện có trong `static/images` | Tái sử dụng, không tạo ảnh dịch vụ/marketing giả |

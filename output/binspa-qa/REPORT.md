# BinSpa — kiểm tra UI trên localhost

Ngày kiểm tra: 18/10/2026 (Asia/Saigon). Địa chỉ duy nhất được mở: `https://127.0.0.1:5000`. Server có sẵn, HTTP 200. Playwright CLI 0.1.22 mở Chrome cài sẵn, dùng engine Chromium, có cửa sổ trình duyệt. Chứng chỉ local được bỏ qua trong cấu hình kiểm thử.

## Lỗi đã sửa và kiểm thử lại

| Lỗi | Nguyên nhân / sửa đổi | Bằng chứng sau sửa |
| --- | --- | --- |
| Chữ menu trang chủ khó đọc trên nền sáng | Navbar dùng nền trắng trong suốt nhưng logo, liên kết và nút dùng màu trắng. Đổi sang màu xanh/chữ tối có sẵn của giao diện; bỏ gạch chân logo để thống nhất desktop/mobile. | `home-header-after.png`; kiểm tra màu thực tế bằng browser thành công. |
| Trang chi tiết dùng thương hiệu “Sà Spa” | Chuỗi cũ trong `service-detail.js`. Đổi tiêu đề tab và mô tả dự phòng sang Bin Spa. | API thật dịch vụ 3: tiêu đề `Spa chân - Bin Spa` ở cả bốn kích thước. Nhánh mô tả dự phòng được sửa trong code nhưng không có dữ liệu trống để thực thi nhánh này. |
| Nút hiện mật khẩu biến mất khi CDN icon không tải | Nút chỉ có Font Awesome, không có kích thước riêng; đo được 0×0 và click timeout. Dùng SVG nội tuyến, vùng bấm 44×44, chừa khoảng trống trong input, bổ sung tên truy cập và trạng thái hiện/ẩn. JS hỗ trợ cả SVG mới lẫn icon cũ ở màn xác thực khác. | `login-390-before.png` / `login-390-after.png`; click hiện, Enter ẩn và `aria-pressed` đạt ở cả bốn kích thước. Kiểm tra kích thước cho phép sai số subpixel 0,1px. |

## File ứng dụng đã sửa

- `app/static/css/customers/style.css`
- `app/static/css/customers/responsive.css`
- `app/static/css/customers/auth.css`
- `app/templates/customer/login.html`
- `app/static/js/customers/auth.js`
- `app/static/js/customers/service-detail.js`

Các thay đổi đã có trước trong repository được giữ nguyên. Không thay đổi schema, cấu hình production hay triển khai.

## Kết quả kiểm thử

| Trang | 1920×1080 | 1366×1080 | 768×1024 | 390×844 |
| --- | --- | --- | --- | --- |
| Trang chủ `/` | Đạt | Đạt | Đạt | Đạt |
| Dịch vụ `/services` | Đạt | Đạt | Đạt | Đạt |
| Chi tiết `/services/3` | Đạt | Đạt | Đạt | Đạt |
| Đặt lịch `/appointments/create` — khách chưa đăng nhập | Đạt | Đạt | Đạt | Đạt |
| Đăng nhập `/auth/login` | Đạt | Đạt | Đạt | Đạt |

- 20/20 trang trả HTTP 200 sau sửa; không có trang tràn ngang theo `scrollWidth` so với `clientWidth`, ảnh nội bộ hỏng hoặc JavaScript exception được ghi nhận.
- Thanh lọc ngang trên mobile có cuộn bên trong; video hero dùng crop. Các phần này không làm trang tràn ngang.
- 26/26 kiểm tra tương tác sau sửa đạt: nút mật khẩu ở bốn kích thước, kiểm tra form trống, lọc nhóm, tìm kiếm không có kết quả, sắp giá, menu mobile và Escape, liên kết đăng nhập, giữ đường dẫn đặt lịch sau đăng nhập, xem nhanh/mở/đóng, màu menu.
- Đăng nhập thành công bằng tài khoản thử nghiệm được cung cấp; chọn sẵn dịch vụ từ URL, chọn giờ trống, chuyển đến bước xem lại và hiển thị nút xác nhận. Kiểm tra màn xem lại ở cả bốn kích thước đạt. Không bấm xác nhận tạo lịch hay thanh toán. Đã đăng xuất khi hoàn tất kiểm tra có tài khoản.
- Đánh giá dịch vụ tải thành công khi chờ API; nút Liên hệ mở chat. Không ghi nhận lỗi API trong luồng chọn giờ/xem lại.
- `node --check` cho hai file JS đã sửa: đạt. `git diff --check` cho sáu file đã sửa: đạt.

## Phần còn lại / giới hạn xác minh

- Chặn mọi request ngoài loopback để tuân thủ yêu cầu chỉ localhost. Google Fonts, Font Awesome CDN, nhạc Pixabay và iframe Google Maps vì vậy không được kiểm tra tải thực tế. Font dự phòng được dùng; các icon CDN khác vẫn không hiện trong phiên này. Không kết luận CDN hoặc production bị lỗi.
- API `/api/auth/restore-session` trả 401 với khách chưa đăng nhập / sau đăng xuất: hành vi xác thực dự kiến, không phải lỗi API nghiệp vụ. Không có HTTP 4xx/5xx khác trong ma trận kiểm tra.
- Chưa kiểm tra thao tác tạo lịch thật, thanh toán thật hoặc mọi dịch vụ trong danh mục. Trang chi tiết được kiểm tra với dịch vụ 3; tính năng đặt lịch được kiểm tra đến màn xem lại để không tạo dữ liệu lịch hẹn.
- Bản sửa dùng chung kích thước nút mật khẩu cũng áp dụng cho các trang đăng ký/đặt lại mật khẩu; hai trang ngoài phạm vi này chưa được kiểm thử browser riêng.

## Artifacts

- `audit-before.log`, `audit-after.json`: ma trận trang và thông tin network/runtime.
- `interactions-before.log`: tái hiện nút mật khẩu không click được.
- `interactions-after.json`: kết quả 26 kiểm tra tương tác.
- `booking-auth-before.log`, `booking-review-before.log`, `auth-after.log`: kiểm tra đặt lịch có tài khoản.
- `*-before.png`, `*-after.png`: screenshots trước/sau, gồm bốn kích thước và màn xem lại lịch.
- `*.js`, `cli.config.json`: kịch bản và cấu hình Playwright CLI dùng lại được, không chứa tài khoản/mật khẩu thử nghiệm.

Các ảnh chụp full-page ban đầu có thể hiển thị vùng đánh giá đang tải; đây là thời điểm chụp sớm, đã được kiểm tra lại với điều kiện chờ API sau đó. Script kiểm tra ảnh sau sửa chỉ chờ decode ảnh đã tải, tránh chờ vô hạn ảnh lazy-load ngoài viewport.

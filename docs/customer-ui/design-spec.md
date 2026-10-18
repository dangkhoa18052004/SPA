# Thiết kế và component matrix

## Bố cục

- Home: header gọn → hero (Đặt lịch chính, Xem dịch vụ phụ) → một danh sách dịch vụ theo backend → giới thiệu/lợi ích → liên hệ CS1 và CS2 → footer. Ẩn số liệu/testimonial chưa có nguồn ở UI mới.
- Catalog: H1 + mô tả → search có label + category + sort → trạng thái kết quả → 3 cột desktop / 2 tablet / 1 mobile; tên xuống dòng, giá và CTA không cắt.
- Detail: breadcrumb → ảnh/thông tin/Đặt lịch → nội dung/reviews → related. Mobile không thêm fixed CTA nếu làm chồng bottom nav/chat.
- Booking: giữ ba bước Dịch vụ → Thời gian → Xác nhận; summary cạnh phải desktop, dưới nội dung mobile. Back giữ lựa chọn; loading/timeout không cho create lại mù.
- Profile: sidebar desktop; điều hướng ngang mobile; tab cũ/hash/query giữ nguyên. Chỉ tab hiện tại tải dữ liệu, profile identity dùng chung.
- Auth: một cột rộng tối đa khoảng 440px; label thật, autocomplete, nút hiện mật khẩu, status/validation rõ; không thêm luật backend.

## Tokens và ownership

Primary `#425F49`, foreground `#2E3C30`, muted `#606E60`, background `#F7F7F2`, secondary `#EDF1E9`, border `#DCE3D8`, surface trắng. Sans hỗ trợ tiếng Việt, body 16px; control ít nhất 44px; radius control 10px/card 16px. Container 1200px; gutters 16/24/32.

| Component | Thực hiện / reuse | State và khả năng truy cập |
|---|---|---|
| Public shell | Jinja + customer entry, reuse route/session | Skip link, active nav, keyboard/ESC, focus visible |
| Cards | Renderer dùng chung customer, giữ data-service-id | Link chi tiết thật, CTA riêng; escape text, placeholder ảnh, width/height, lazy |
| Booking primitives | `customer/ui.tsx` hiện có | Loading/disabled, button type, focus, Input/Card không đổi API |
| Account forms/history | Ant Design 5 trong entry riêng khi đủ parity | ConfigProvider cùng tokens, popup theme, responsive; không trộn control trong form |
| Empty/error/loading | Component React và markup semantic tương ứng | role=status/alert, lỗi có retry; layout ổn định |
| Payment/reviews/packages | Giữ bridge đã kiểm chứng | Server quyết định status/tiền/quyền; modal không có hai owner |

CSS mới chỉ nạp khi flag và manifest khả dụng. Namespace `customer-ui`; không import admin `style.css` hoặc reset Tailwind vào entry public/account. Booking là document riêng nên có thể giữ reset của entry booking. Popup Ant phải có theme qua ConfigProvider cả ngoài root.

## QA

360/390/768/1024/1440px, zoom 200%, Tab/Shift+Tab/Enter/ESC, giảm motion; kiểm tra ảnh lỗi/tên dài, network/console, fallback flag-off/missing-assets/`ui=legacy`, portal admin/employee/manager. Loading/empty/error phải phân biệt, không đánh dấu Xong nếu mới build mà chưa xem browser.

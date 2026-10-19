# E07 — Điểm thưởng, đổi quà và ưu đãi

Ngày kiểm chứng: 19/10/2026. Tiếp theo E06 và chức năng hủy đơn mua gói chờ; phạm vi theo E07 trong `refactorUI_Customer.md`.

## Kết quả

- Đưa điểm khả dụng lên đầu, định dạng số theo tiếng Việt; tổng điểm tích/đã dùng và tiến độ hạng rõ ràng. Giữ số điểm dùng được do server trả, không đưa điểm đang giữ vào wallet customer.
- Thống nhất font, màu chữ/nền, bộ lọc, thẻ quà và lịch sử tăng/giảm điểm. Điều kiện, hạn, thiếu điểm và hết quà hiển thị riêng; nút và trường nhập phù hợp mobile. Nút bị vô hiệu hóa dùng chữ tối trên nền nhạt, giữ nhãn dễ đọc; phép đo chữ bao gồm cả các nút này.
- Voucher/quà có nhóm trạng thái, mã, điều kiện và nút tiếp tục đúng hóa đơn/đơn gói. Chi tiết modal có feedback sao chép tại chỗ; đóng modal trả focus, xác nhận đổi mở ở nút Hủy.
- Wallet và danh sách có trạng thái lỗi/retry riêng. Wallet lỗi vẫn xem được danh sách, chặn đổi mới với thông báo chưa tải được điểm. Không giả định số dư bằng 0.
- Giữ owner JS và luồng idempotency hiện hành: double click không tạo lần đổi thứ hai; retry sau mất phản hồi/tải lại giữ cùng key. Không thay API, quy tắc điểm, schema, dependency hoặc cấu hình máy chủ.

## File thay đổi trong E07

| File | Nội dung |
|---|---|
| `app/static/js/customers/loyalty.js` | Renderer wallet/lịch sử/quà, lỗi độc lập, reload, keyboard, dialog/focus/copy và định dạng điểm |
| `app/static/css/loyalty.css` | Style customer giới hạn `#loyalty-section` và `.loyalty-reward-dialog`; cả legacy/refactor |
| `app/templates/customer/profile.html` | Tiêu đề/mô tả và nút tải lại điểm thưởng |
| `tests/loyalty-ui.test.cjs` | Thêm ca wallet chưa biết không được coi là thiếu điểm hoặc cho đổi |
| `tests/customer-ui-rewards.playwright.js` | Fixture API, style/layout, thao tác, lỗi và retry ở cả hai shell |
| `tests/loyalty_customer_browser_check.py` | Cập nhật định dạng thiếu điểm `4.300` và selector feedback copy trong modal; giữ kiểm chứng nghiệp vụ |
| `docs/customer-ui/progress.md`, `contracts.md`, `qa-results.md`, `rewards-refactor.md` | Tiến độ, ownership và bằng chứng kiểm tra |

Các thay đổi của E06, hủy đơn, typography và `requirements-dev.txt` đã có trước lượt E07 được giữ nguyên.

## Kiểm chứng

| Kiểm tra | Kết quả |
|---|---|
| `node --test tests/*.test.cjs` | 50 PASS |
| `python -m pytest tests/test_loyalty_customer_rewards.py tests/test_loyalty_tiers.py -q --disable-warnings --tb=short` | 17 PASS; 391 warnings |
| Playwright CLI `customer-ui-rewards.playwright.js` | PASS legacy/refactor, 360/390/768/1024/1440px; 30 tổ hợp màn/viewport và 2 dialog |
| `python tests/loyalty_customer_browser_check.py` | PASS, API + SQLite fixture; lost-response/reload, số dư cuối 400, nhóm ưu đãi, thanh toán customer/admin, keyboard/mobile |

Playwright kiểm tra font, màu chữ/nền, không tràn ngang; tương phản nhỏ nhất của chữ được đo là 4,71:1 (dialog 5,39:1), không có uncaught exception hoặc failed request. HTTP 503 là phản hồi lỗi chủ động của fixture. Ảnh và báo cáo nằm ở `.test-tmp/customer-ui-rewards/`: `browser.json`, `refactor-rewards-1440.png`, `legacy-rewards-390.png`, `refactor-mine-390.png`, `node.log`, `pytest.log`, `loyalty-browser.log`. Đã xem ảnh desktop/mobile; số đo tự động không thay thế nghiệm thu accessibility đầy đủ.

Lượt chạy hồi quy đầu phát hiện kỳ vọng test cũ còn số `4300` chưa định dạng và thông báo copy ở trang phía sau modal. Đã cập nhật đúng UI mới và chạy lại thành công, giữ nguyên assertions số dư, số redemption và idempotency.

Chỉ chạy loopback với dữ liệu thử nghiệm; không đổi quà hoặc sửa dữ liệu khách thật. Không bật flag, restart/deploy LAN, chạy ngân hàng thật hoặc nghiệm thu thiết bị thật. Full pytest, Vitest và Vite build không chạy lại trong E07; lượt này chỉ thay static JS/CSS/Jinja cùng test/tài liệu. Bước tinh chỉnh tiếp theo là E08 — Đánh giá.

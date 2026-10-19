# Kiểm tra tiến độ và typography customer — 19/10/2026

## Kết luận

Phần triển khai A–F đã có trong commit `ad68001`; HEAD lúc bắt đầu kiểm tra là `38e100d`. Chưa thể kết luận toàn bộ giao diện mới đã chạy trên `https://192.168.1.160:5000`: booking dùng React mới, trong khi public/auth và profile đã đăng nhập vẫn dùng legacy. Cập nhật này sửa các lỗi CSS tìm thấy và ghi nhận riêng kết quả LAN với preview refactor.

| Nhóm | Mã nguồn / tiến độ | Quan sát trên LAN |
|---|---|---|
| A | Đã có baseline, contracts, design spec, inventory | Thông tin doanh nghiệp CS1 và số liệu marketing vẫn cần chủ dự án xác minh |
| B | Có tokens/theme, entries và fallback | Booking có `customer-booking`; public/account không tải entry mới |
| C | Home, services/detail, packages/detail đã triển khai | Các route kiểm tra đang dùng legacy |
| D | Booking đã triển khai | Đang dùng giao diện mới; đã kiểm tra khách đăng nhập và guest |
| E | Auth, profile và các vùng React đã triển khai | Auth/profile vẫn legacy, gồm 9 tab profile đã truy cập |
| F | Có QA local, tài liệu; thêm kiểm tra typography trong lượt này | Chưa nghiệm thu rollout public/account, thiết bị thật, PostgreSQL và CI hosted |

Không suy ra giá trị flag thực tế chỉ từ HTML. Gate có thể tắt hoặc resolver có thể fallback vì asset; cần kiểm tra cấu hình tiến trình/manifest trên máy chủ trước rollout. Không đọc secrets hoặc sửa cấu hình trong lượt này.

## Phạm vi và cách đo

- Microsoft Edge qua Playwright CLI, chứng chỉ LAN tự ký được bỏ qua riêng trong browser context kiểm thử.
- LAN: 34 tổ hợp route/viewport công khai, 29 tổ hợp profile/booking bằng phiên do người dùng đăng nhập. Các route/tab chính kiểm tra ở 390/1440px; shell/form đại diện thêm 360/768/1024px.
- Công khai: home, services, services/3, packages, packages/2, login/register/forgot-password/verify-otp/reset-password, booking guest.
- Profile: appointments, invoices, treatments, loyalty, reviews, info, edit, password, communication; không lưu thay đổi hoặc tạo giao dịch.
- Preview độc lập `http://127.0.0.1:5080`: fixture SQLite, dữ liệu thử nghiệm, public/account/booking mới; services/1 và packages/1. Không dùng dữ liệu production.
- Kiểm tra computed font family/size/weight/style/line-height, màu chữ/nền, placeholder, tràn ngang và ảnh desktop/mobile. CDP xác nhận font thực sự render là Segoe UI / Segoe UI Bold trên trang detail mới.
- Đo tương phản chữ thường tối thiểu 4,5:1, chữ lớn 3:1; loại disabled và nền ảnh/gradient khỏi kết luận tự động. Bộ đọc màu hỗ trợ `oklab()`/`color(srgb)` qua canvas, không chỉ `rgb()`.
- Dropdown Select, Drawer chi tiết và modal xác nhận hủy lịch được mở trên preview; modal đóng bằng “Giữ lịch”. AI panel trên LAN được mở ở desktop/mobile, không gửi tin nhắn.

## Lỗi quan sát trên bản legacy của LAN

| Vị trí | Giá trị thực tế | Kết quả |
|---|---|---|
| Body public / tiêu đề | Plus Jakarta Sans / Playfair Display | Khác hệ sans thống nhất của refactor |
| Search, sort và filter services | Times New Roman, 14px | Control bị lọt font mặc định serif |
| Body auth | Arial | Chưa dùng font token mới |
| Nút vàng services/packages/profile | Trắng trên `#d4af37` | 2,10:1, không đạt |
| Nút auth | Trắng trên `#c9a961` | 2,25:1, không đạt |
| Link auth | `#8b9d7c` trên trắng | 2,91:1, không đạt |
| Profile email | `#888` trên trắng, 13px | 3,54:1, không đạt |
| Menu profile active | `#c9a961` trên `#f8f8f8` | 2,12:1, không đạt |

Các vấn đề legacy trên public/profile vẫn hiện hữu trên LAN khi gate chưa trả bản mới. Không sửa hàng loạt stylesheet legacy để thay thế việc rollout.

## Sửa và kiểm chứng bản refactor

| Lỗi tìm thấy | Thay đổi | Sau sửa |
|---|---|---|
| Auth link còn màu xanh nhạt; divider còn chữ xám nhạt và nền trắng khác trang | `public.css`: link/hover dùng primary; divider dùng muted/background | Link 6,59:1; muted trên nền trang 5,01:1 |
| Email bị inline `#888` ghi đè CSS | `profile.html`: dùng `var(--customer-muted, #888)` | 5,39:1 trên trắng khi có token; legacy giữ fallback |
| Ant danger button chữ đỏ nhạt 3,27:1 | `theme.ts`: error/danger đậm hơn; placeholder dùng muted | Nút/modal đỏ `#a62b2b`, trắng/đỏ đạt 7,00:1 |
| Booking custom CSS tham chiếu biến `--color-*` không có sau `@theme inline` | `booking.css`: custom rules đọc trực tiếp `--customer-*`; placeholder explicit | Logo/nút/viền/focus dùng đúng token; trắng/xanh 7,08:1 |
| Badge thời lượng phủ ảnh dùng đen bán trong suốt, không bảo đảm tương phản trên ảnh sáng | `public.css`: nền primary đặc, chữ trắng | 7,08:1, không phụ thuộc ảnh |
| AI trigger/message/send còn trắng trên vàng; note nhạt | `ai-chat.css`: dùng customer tokens với fallback legacy | Trigger/send 7,08:1; note 5,39:1 |
| AI panel mobile và input có thể bị cắt bên phải | Panel fixed tự tính chiều rộng; input `min-width:0` | Nút gửi nằm trọn trong viewport 390px |

Typography mục tiêu sau sửa: font hệ thống (Segoe UI trên máy Windows này), body 16px/400/normal, chữ `#2e3c30`, nền trang `#f7f7f2`, card trắng, primary `#425f49`, muted `#606e60`. Tương phản body/nền trang 10,83:1.

Sau build, LAN đã phục vụ CSS booking mới: đo lại cả 5 breakpoint khi dữ liệu dịch vụ đã tải xong, có input/select thực tế; logo/fab xanh `rgb(66,95,73)`, placeholder `rgb(96,110,96)`, không tràn ngang. Public/account vẫn legacy; các sửa thuộc hai nhóm này chỉ được xác minh trên preview.

## Kết quả kiểm tra trong lượt này

| Kiểm tra | Kết quả |
|---|---|
| `npm --prefix frontend run build` | PASS; còn warning chunk Ant >500kB đã ghi nhận trước |
| `npm --prefix frontend test` | 63 PASS / 12 files |
| `python -m pytest tests/test_customer_ui_foundation.py -q --disable-warnings --tb=short` | 9 PASS / 36 warnings |
| Typography preview public | 34 cases; 947 phép đo chữ/nền; không còn issue font serif hoặc contrast nền phẳng |
| Typography preview account/booking | 29 cases; 951 phép đo chữ/nền; không còn issue font serif hoặc contrast nền phẳng |
| LAN public/account | 34 + 29 cases; không có uncaught JS exception hoặc tràn ngang; có các lỗi typography legacy nêu trên |
| LAN booking sau sửa | 5 breakpoint, dữ liệu đã tải; computed styles và ảnh PASS |
| Ant popup + AI panel | Kiểm tra font/màu, ảnh và hình học PASS trong phạm vi đã mô tả |
| `git diff --check` với các file sửa trong lượt này | PASS |

Không chạy lại full pytest 768 tests hoặc Node 49 tests trong lượt audit CSS này; các con số đó trong tài liệu cũ là kết quả lịch sử.

Quan sát mạng: guest `/api/auth/restore-session` trả 401 là baseline; favicon 404 xuất hiện lúc mở phiên mới. Lượt khảo sát đầu có một connection reset package trên LAN và lỗi related recommendation 500 trên fixture; các lượt sau không tái hiện. Một lượt public preview có `net::ERR_NO_BUFFER_SPACE` ở restore-session, nên không coi toàn bộ network của preview là sạch tuyệt đối. Không có uncaught JS exception trong các báo cáo cuối.

Ảnh và JSON chi tiết nằm trong `.test-tmp/customer-ui-2026-10-19/` (ignored). Ảnh LAN profile có thể chứa dữ liệu phiên thử nghiệm nên không đưa vào Git. Báo cáo JSON typography không ghi tên, địa chỉ, hóa đơn hoặc giá trị input.

Script tái kiểm tra: `tests/customer-ui-typography.playwright.js`, chạy bằng `playwright-cli -s=<session> run-code --filename=tests/customer-ui-typography.playwright.js`. Mở `/profile` bằng phiên khách đã đăng nhập để chạy nhóm account; mở một trang public để chạy nhóm public. Tạo thư mục artifact nêu trên trước khi chạy. Script chỉ đọc; không submit form.

## File thay đổi trong lượt này

- `app/static/css/ai-chat.css`
- `app/templates/customer/profile.html`
- `frontend/src/customer/booking.css`
- `frontend/src/customer/public.css`
- `frontend/src/customer/theme.ts`
- `tests/customer-ui-typography.playwright.js`
- `docs/customer-ui/progress.md`
- `docs/customer-ui/qa-results.md`
- `docs/customer-ui/typography-audit-2026-10-19.md`

Giữ nguyên chỉnh sửa `requirements-dev.txt` có sẵn trước lượt làm việc. Không thay schema, cấu hình production, không restart tiến trình LAN, không deploy; chỉ restart preview fixture ở port 5080 để nạp template sửa. Chưa thay đổi flag rollout public/account.

## Bổ sung: Đổi dịch vụ và thanh toán theo ảnh người dùng

Lượt audit trang/tab ở trên chưa bao phủ đầy đủ hai dialog này. Đã tái hiện hai lỗi trên CSS thực tế của LAN bằng dữ liệu giả lập trong browser, không cần truy cập hay thay đổi lịch/hóa đơn thật:

- `change-services.css` thiếu `margin:auto`/inset riêng, trong khi reset `* {margin:0}` của customer ghi đè margin căn giữa của native dialog. Trước sửa: viewport 1440px, dialog rộng 880px nằm tại x=0/y=0. Sau sửa: x=280, cách đều hai bên; dialog ít dịch vụ cũng căn giữa theo chiều dọc. Mobile dùng toàn màn hình, header/footer không bị flex ép co và input không đẩy tràn ngang.
- `loyalty-payment.js` dùng `.btn-secondary` của legacy shell: chữ/viền trắng, nền trong suốt trên panel trắng. Các nút “Dùng tối đa”, “Xem quy đổi”, “Bỏ sử dụng điểm”, “Áp dụng voucher” vì thế khó hoặc không nhìn thấy. `loyalty.css` nay quy định riêng màu nền/chữ/viền cho primary, secondary, outline, hover, disabled và focus trong payment/dialog; dialog có nền trắng và màu chữ rõ ràng. Không đổi phép tính hoặc API thanh toán.
- Nút lưu đổi dịch vụ dùng xanh đậm; label mờ của dialog đổi sang xám đậm. Các control kế thừa font của shell.

File bổ sung trong đợt sửa này: `app/static/css/change-services.css`, `app/static/css/loyalty.css`, `tests/customer-ui-dialogs.playwright.js`, báo cáo này và `qa-results.md`.

Kiểm chứng: 33 trường hợp browser trên 360/390/768/1024/1440px, với legacy CSS của LAN, booking React thực tế và bộ CSS public refactor tải từ build manifest. Trường hợp `refactor-css` chỉ là kiểm tra tích hợp CSS vào dialog; không có nghĩa public/account đã được bật trên máy chủ. Có thử 2/55 dịch vụ, chọn dịch vụ, ESC, footer trong viewport, editor điểm/voucher, preview điểm, hover và QR. Payment API được intercept toàn bộ bằng fixture; không lưu dịch vụ, áp dụng điểm/voucher hay tạo QR thật. Các nút thanh toán đang hoạt động có tương phản tối thiểu 6,19:1; không uncaught JS exception, không tràn ngang. Ảnh sau sửa: `change-after-*.png`, `payment-after-*.png` trong thư mục artifact đã nêu.

`node --test tests/loyalty-ui.test.cjs tests/invoice-payment-ui.test.cjs`: 15 PASS. `git diff --check` hai stylesheet: PASS. Không chạy lại build vì đây là CSS tĩnh được Flask phục vụ trực tiếp; không thay entry Vite. Chưa kiểm tra browser của admin hoặc thiết bị thật trong đợt bổ sung này.

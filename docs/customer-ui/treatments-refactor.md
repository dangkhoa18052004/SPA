# E06 — Hoàn thiện giao diện Liệu trình của tôi

Ngày 19/10/2026; tiếp nối sửa dialog đổi dịch vụ và thanh toán. Đây là phần hoàn thiện giao diện E06 trong `refactorUI_Customer.md`, không phải rollout production.

## Kết quả

- Mỗi liệu trình có tên/mã, trạng thái, ngày mua/kích hoạt và hạn gói gốc. Từng dịch vụ hiển thị riêng lượt còn lại, đang giữ, đã dùng và hạn hiệu lực do server trả về.
- Tách dịch vụ trong gói và dịch vụ tặng. Lượt tặng có thể có thời hạn khác gói gốc; CTA dựa trên `usable`, `available_sessions` và trạng thái hủy. Khi lượt không khả dụng, dùng nhãn “Lượt còn lại” và không hiện nút đặt lịch, tránh làm người dùng hiểu là có thể đặt.
- Đường dẫn đặt lịch giữ `treatment`, `service`, `item`; đã kiểm tra chọn đúng lượt tặng khi chuyển qua booking.
- Gói pending nằm trong vùng riêng với số phải trả từ server và link `/packages?purchase=<purchase-id>`. Lỗi GET pending không xóa liệu trình đã tải; nút thử lại chỉ tải vùng lỗi.
- Lịch sử mở theo yêu cầu, phân biệt lượt trong gói/lượt tặng và trạng thái giữ/dùng/trả. Khi đang tải thì khóa nút; có lỗi và thử lại; mở lại sẽ GET lịch sử mới. ARIA expanded/controls/busy và vùng status/alert đi cùng trạng thái hiển thị.
- Loading, empty và lỗi mạng là các trạng thái khác nhau. Phản hồi từ lần tải cũ không ghi đè lần tải mới hơn.

## Ownership và rollout

Account entry đăng ký `CustomerTreatments`, là renderer nhỏ không nhập Ant Design. `packages.js` tiếp tục làm adapter GET và event, chỉ dùng renderer mới khi bridge hiện diện; không có hai owner của DOM. Các hàm/admin renderer cũ không bị thay thế. CSS nằm trong namespace `.customer-ui` của account bundle.

Giữ gate `CUSTOMER_ACCOUNT_REACT_ENABLED`, kiểm tra manifest đầy đủ và fallback `?ui=legacy`. Không thêm dependency, endpoint, schema hoặc thay đổi giá/lượt/quyền. Không bật cờ, không deploy hoặc restart máy chủ LAN trong lượt này. Bản mới được xác minh trên preview loopback `5080` dùng SQLite fixture, email/provider bị vô hiệu hóa; API liệu trình/purchase/history của browser test được mock. Không phát sinh lịch hoặc giao dịch thật.

## File thay đổi trong lượt E06

| File | Thay đổi |
|---|---|
| `frontend/src/customer/treatments.ts` | Renderer thẻ, quà tặng, lịch sử, pending và các trạng thái |
| `frontend/src/customer/treatments.test.ts` | 6 ca kiểm tra ID/deep link, lượt/quà, quyền đặt, escaping, payable/pending và empty/error |
| `frontend/src/customer-account-main.tsx` | Đăng ký renderer trong account entry |
| `frontend/src/customer/account.css` | Bố cục và màu/font responsive của E06 |
| `app/static/js/packages.js` | Nhánh adapter mới có retry độc lập, history và guard phản hồi cũ; giữ nhánh legacy/admin |
| `app/templates/customer/profile.html` | Header liệu trình sau gate; giữ ID/DOM hooks |
| `tests/customer-ui-treatments.playwright.js` | Smoke và lỗi có kiểm soát, 5 breakpoint, typography và legacy fallback |
| `docs/customer-ui/progress.md`, `qa-results.md`, `contracts.md`, tài liệu này | Tiến độ, kết quả và ownership |

Giữ nguyên các thay đổi có sẵn của các lượt trước, bao gồm `requirements-dev.txt`; không gom chúng thành thay đổi mới của E06.

## Kiểm thử thực hiện

| Lệnh / kiểm tra | Kết quả |
|---|---|
| `npm --prefix frontend run build` | PASS; build đủ entry; còn cảnh báo chunk Ant 540,51kB đã ghi nhận |
| `npm --prefix frontend test` | 69 PASS / 13 files |
| `node --test tests/*.test.cjs` | 49 PASS |
| `python -m pytest tests/test_customer_ui_foundation.py tests/test_phase4_packages_care.py -q --disable-warnings --tb=short -k 'customer_ui or treatment_validation or mixed_booking or pending_purchase_owner or reserve_release_consume or pages_render'` | 22 PASS / 19 deselected; 395 warnings |
| `customer-ui-treatments.playwright.js` | PASS: 6 nhóm hành vi, gồm các ca lỗi 503 được mock chủ động; errors/failed requests rỗng |
| Account smoke hiện có | PASS: lazy tab, Back/Forward, invoice Drawer/ESC, lưu profile fixture, sai mật khẩu không restore lại, review context; dùng bản sao ignored đổi port 5078 → 5080 |
| Viewport và font/màu | 360/390/768/1024/1440px PASS; 105 phần tử chữ mỗi viewport, tối thiểu 4,71:1; không tràn ngang |
| `git diff --check` các file E06 | PASS |

Ảnh và log trong `.test-tmp/customer-ui-treatments/` (ignored): `after-390.png`, `after-1440.png`, `browser-final.json`, `account-smoke.json`, `build-final.log`, `vitest-final.log`, `node.log`, `pytest.log`.

Chưa kiểm tra native zoom/keyboard thiết bị thật, PostgreSQL, hosted CI hay rollout LAN. Không dùng kết quả fixture để khẳng định dữ liệu khách thật hoặc quy trình thanh toán ngân hàng đã được nghiệm thu.

Phần tiếp theo theo thứ tự tài liệu: E07 — điểm thưởng, đổi quà và voucher, tiếp tục giữ idempotency và owner hiện hành.

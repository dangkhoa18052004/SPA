# E09 và F — Hoàn thiện customer UI

Checkpoint local ngày 19/10/2026, HEAD đối chiếu `38e100d`. Thực hiện theo E09 và F01–F06 trong `refactorUI_Customer.md`. Các sửa E06–E08/hủy purchase/typography và thay đổi có sẵn của người dùng được giữ nguyên.

## E09 — Thông báo và quyền riêng tư

- Tách email chăm sóc và cá nhân hóa thành hai nhóm rõ ràng; giải thích email giao dịch, tác động khi tắt cá nhân hóa; đồng bộ font, chữ/nền, focus và controls mobile với hồ sơ customer.
- Chỉ tải khi mở tab; giữ bốn lựa chọn và version do server trả, không tự opt-in hoặc tự lưu. Không thay mặc định nghiệp vụ trên server.
- Khóa cả hai fieldset khi loading/saving/chưa có version. Sửa lỗi tải lại thất bại còn giữ version cũ và cho phép lưu lại. Từ nay lỗi GET giữ form khóa tới khi GET hợp lệ.
- PUT một lần khi bấm lặp; gửi đủ boolean và đúng version. 409 hoặc lỗi lưu chưa rõ kết quả yêu cầu tải lại trước khi ghi tiếp; 400/422 giữ draft để sửa. Không tự retry mutation. Request có timeout 20 giây và lỗi kết nối/phản hồi sai định dạng có thông báo.
- Flag tắt thì ẩn tab/form và không tải assets. Không thay API, schema hoặc cấu hình production.

`customer-ui-preferences-final.playwright.js`: PASS legacy/refactor, lazy load, keyboard, không tự opt-in, submit lặp chỉ một PUT, lưu/reload, draft khi 400, 409 khóa ghi, GET lỗi vẫn khóa, PUT 503 chưa rõ kết quả, response sai version, version mới sau reload, bật/tắt cá nhân hóa và flag-off. 24 lượt đo chữ/layout ở 5 viewport; tương phản chữ tối thiểu 4,71:1, không tràn ngang; exceptions=[], failed requests=[]. Đã xem ảnh desktop/mobile.

## F — Các hạng mục hoàn thiện

| Mục | Thực hiện / bằng chứng | Giới hạn nghiệm thu |
|---|---|---|
| F01 | Sửa chat mất refresh sau khi Back/Forward khôi phục document: persisted pageshow khởi động đúng một interval khi có phiên; pagehide/logout dừng vòng. Đã kiểm tra init lặp, pagehide/pageshow giả lập và thiếu token. Chat mở/ESC/focus, không autoplay và input ở viewport cao 600px đạt | Lifecycle event test là giả lập; bàn phím iOS/Android thật còn cần nghiệm thu |
| F02 | Responsive 360/390/768/1024/1440px; các suite public/account/auth/treatments/rewards/reviews/preferences, dialogs và keyboard/focus; thêm compact 720×480 và root text resize 200% | Root text resize/viewport giả lập không thay thế native browser zoom 200%; thiết bị thật chưa kiểm chứng |
| F03 | Build đủ portal/booking/customer/account thành công, manifest output riêng giống build preview. Public metadata/canonical/detail, không tải portal JS vào public; lazy account/preferences giữ đúng ownership. Có đo LCP/CLS loopback | Warning shared Ant chunk >500kB; số đo local dưới tải regression không phải field data hoặc cam kết tốc độ |
| F04 | Build/Vitest/Node, 11 browser suites, 11 smoke API/DB và full pytest đã chốt ở bảng dưới | 24 test skip chưa nghiệm thu; chưa chạy hosted GitHub CI |
| F05 | Kiểm kê template consumers của packages/reviews/change-services/payment: admin và legacy vẫn dùng, giữ các file này; không thêm owner/listener cho cùng root hoặc dependency | Không xóa file dùng chung để giảm số lượng asset một cách hình thức |
| F06 | Cập nhật progress, contracts, QA, changed-files, rollout/rollback và báo cáo này; build review xuất riêng ngoài assets đang phục vụ LAN | Chưa commit các bổ sung, tạo PR, đổi flags, restart/deploy hoặc nghiệm thu rollout |

## Gate local

| Kiểm tra | Kết quả |
|---|---|
| Build TypeScript/Vite, output `.test-tmp/customer-ui-final/portal` | PASS; manifest giống build hiện có; còn warning shared chunk |
| Vitest | 69 PASS / 13 files |
| Node `tests/*.test.cjs` | 50 PASS |
| Syntax check `communication-preferences.js`, `customers/main.js` | PASS |
| 11 browser suites: foundation/public/account/auth-preferences/hardening/transactions/avatar/treatments/rewards/reviews/performance | PASS; bản sao chỉ đổi port sang 5080, giữ assertions |
| E09 preferences-final | PASS; 24 lượt đo + state/API fixtures |
| final-hardening | PASS; chat lifecycle/compact viewport/metadata/text resize |
| 11 smoke có API/DB: 8 suite theo workflow + loyalty/reviews/admin-booking | PASS |
| `python -m pytest tests -q --ignore-glob=*.tmp --disable-warnings --tb=short` | 779 PASS, 24 SKIP, không FAIL; 12.719 warnings; 1717,79s |
| Typography toàn giao diện | 34 public + 29 account cases, issues=[], errors=[], failed=[] |
| Dialogs đổi dịch vụ/thanh toán | 33 cases PASS; API fixture, không giao dịch thật |
| Hủy mua gói chờ | PASS cả legacy/refactor ở 5 viewport; chỉ tạo/hủy đơn SQLite preview |

Log, JSON và ảnh: `.test-tmp/customer-ui-final/`, gồm `pytest-full.log`, `build.log`, `build-parity.json`, `vitest.log`, `node.log`, `browser-summary.json`, `smoke-summary.json`, `preferences.json`, `final-hardening.json`, `typography-public.json`, `typography-account.json`, `dialogs.json`, `purchase-cancel.json`. API provider/email/AI được fixture mock; giao dịch chỉ nằm ở DB kiểm thử. Các suite kiểm tra lỗi chủ động trả 400/403/409/503, guest restore có 401 đúng dự kiến; không coi các response này là lỗi ngoài dự kiến.

24 skip không được tính là pass. Nhóm điều kiện trong source gồm PostgreSQL (`TEST_LOYALTY_POSTGRES_URL` chưa cấu hình) và ca cần lịch hẹn trong cùng ngày; môi trường này không có lệnh PostgreSQL/Docker sẵn để chạy nhóm PostgreSQL. Không thay marker/assertions để che thiếu môi trường. Hosted workflow vẫn cần PostgreSQL chuyên dụng như `quality.yml`. Các warning được ghi trong log, không đổi dependencies của người dùng trong lượt này.

So sánh lab một mẫu tại loopback, Edge, cache sẵn có, chạy cùng hồi quy:

| UI | Width | LCP ms | CLS |
|---|---:|---:|---:|
| Legacy | 390 | 312 | 0,00277 |
| Refactor | 390 | 416 | 0,00041 |
| Legacy | 1440 | 296 | 0,03850 |
| Refactor | 1440 | 628 | 0,02245 |

Các mẫu lab đều dưới mục tiêu tham khảo LCP 2,5s và CLS 0,1 của kế hoạch. Layout shift thấp hơn trong lượt đo; LCP cần đo trên staging/network đại diện và không dùng mẫu này để khẳng định refactor nhanh hơn. Giữ cảnh báo Ant chunk trong build log.

## File của lượt E09/F

- `app/static/js/customers/communication-preferences.js`: state/version/error/timeout và khóa form.
- `app/static/css/communication-preferences.css`: tokens, controls, contrast, responsive/focus.
- `app/templates/customer/profile.html`: hai nhóm preferences và giải thích email giao dịch.
- `app/static/js/customers/main.js`: khôi phục vòng chat sau Back/Forward cache.
- `tests/customer-ui-preferences-final.playwright.js`, `tests/customer-ui-final-hardening.playwright.js`.
- `docs/customer-ui/e09-final-hardening.md`, `progress.md`, `qa-results.md`, `contracts.md`, `changed-files.md`, `release-checklist.md`.

`git diff --check` cho file E09/F đạt. Kiểm tra toàn working tree còn cảnh báo blank line EOF đã có sẵn trong `requirements-dev.txt`; không sửa file ngoài phạm vi này.

## Trước nghiệm thu toàn bộ trên máy chủ

HTTP chỉ đọc trên LAN ngày 19/10: `/`, `/services`, `/packages`, `/auth/login`, `/profile` chưa có bundle public/account mới; booking có bundle mới. Không đổi cờ để xử lý trạng thái này trong lượt E09/F. Chỉ preview loopback chứng minh phần refactor mới; chưa coi LAN đã rollout.

Các phần cần môi trường/người nghiệm thu: native zoom 200%, bàn phím iOS/Android thật; PostgreSQL chuyên dụng/hosted CI nếu test bị skip; nội dung doanh nghiệp/marketing theo A06; kiểm tra flags/assets và staging/rollout được chủ dự án duyệt. Xem `release-checklist.md` để bàn giao release đầy đủ và rollback theo nhóm, giữ dữ liệu giao dịch.

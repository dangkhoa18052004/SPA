# Kết quả kiểm tra local — 18/10/2026

## Gate và smoke tests

| Kiểm tra | Kết quả |
|---|---|
| `npm --prefix frontend run build` | PASS, TypeScript và toàn bộ Vite entries portal/booking/customer/account |
| `npm --prefix frontend test` | 63 PASS / 12 files |
| `node --test tests/*.test.cjs` | 49 PASS |
| Full pytest, `tests -q --ignore-glob='*.tmp' --disable-warnings --tb=short` | 768 PASS, 24 SKIP; 959.44s; log `.test-tmp/customer-ui/pytest-full.txt` |
| Foundation/assets/navigation bổ sung sau chỉnh gate | 15 PASS; log `pytest-foundation-final.txt` |
| `operations_browser_check.py`, `phase4_browser_check.py`, `phase5_browser_check.py`, `booking_catalog_browser_check.py` | PASS |
| `phase6_browser_check.py`, `ai_chat_navigation_browser_check.py`, `staff_security_browser_check.py`, `admin_care_browser_check.py` | PASS; phase6 lần đầu WebSocket timeout, chạy lại PASS cả 390/768/1440px, log `phase6-browser-rerun.txt` |
| `loyalty_customer_browser_check.py` | PASS: wallet, filters, confirm/cancel, double click, lost-response retry, URL restore, payment points, keyboard/mobile |

24 skip không được coi là pass. Các test có điều kiện bao gồm PostgreSQL khi thiếu test server và điều kiện lịch hẹn trong ngày. Chưa chạy hosted GitHub CI hay staging.

## Playwright CLI cho giao diện mới

- Baseline: 14 ảnh guest/profile customer ở 390/1440px, `.test-tmp/customer-ui/before-*`.
- Foundation: 5 viewport không overflow, không kéo CSS admin, `ui=legacy` hoạt động; exceptions=[], failed requests=[].
- Public: 4 route × 5 viewport; search/sort/refresh/reset, deep link service → booking PASS; exceptions=[], lỗi HTTP mới ngoài guest restore=[].
- Account: lazy active-tab data, hash Back/Forward, profile save một request, sai mật khẩu giữ phiên, invoice drawer/ESC, review context, desktop table/mobile cards PASS.
- Avatar: upload logo JPEG vào thư mục test PASS, header/profile đồng bộ sau success; mock rejection giữ ảnh cũ. Tệp dịch vụ 1.32MB vượt giới hạn test 1MB được backend từ chối đúng, sau đó dùng tệp logo nhỏ hợp lệ để kiểm tra success.
- Transactions: double click chỉ tạo **1 POST**; server tạo xong rồi response bị mất → reload → reconcile đúng lịch; không retry create. Mở/đóng QR fixture giữ invoice ở trạng thái chưa thanh toán.
- Lỗi mở thanh toán từ lịch hẹn được đưa vào Alert có thể thử lại; kiểm tra bằng invoice API trả 503, không có unhandled promise.
- Auth/preferences: 5 màn × 5 viewport, paste OTP 6 số, repeat registration chỉ 1 request; preferences gửi version, conflict yêu cầu reload; tab preferences không tải heavy account controls. Các tab liệu trình/loyalty/reviews/info/communication không overflow.
- Hardening PASS: skip link/menu/ESC và Drawer trả focus; không autoplay nhạc; chat trong thanh navigation; ảnh lỗi/tên dài/null price/escape API; empty/error/retry; root text resize 200%. Exceptions=[]. Bằng chứng tại `hardening-result.txt` và ảnh `final-*`.

Kích thước: 360/390/768/1024/1440px. Dữ liệu chỉ từ fixture SQLite, provider/QR lỗi mạng được mock, không thanh toán hoặc gửi thông báo thật. Guest restore-session 401 và favicon legacy 404 đã có ở baseline. Lỗi 400/401/409/503 cố ý gây ra trong test không phải regression.

## Hiệu năng / bundle

LCP/CLS đo một lần trên Edge, loopback cùng máy, cache hiện hữu, không network shaping; không phải field data hay chứng nhận Lighthouse. Script: `customer-ui-performance.playwright.js`, log `performance-result.txt`.

| UI | Width | LCP ms | CLS |
|---|---:|---:|---:|
| Legacy | 390 | 144 | 0.00202 |
| Mới | 390 | 132 | 0.00041 |
| Legacy | 1440 | 164 | 0.04290 |
| Mới | 1440 | 124 | 0.02278 |

Booking entry baseline: JS 58.71kB, CSS 16.72kB. Sau refactor: khoảng JS 58.28kB + API shared 1.47kB; CSS 19.04kB (token, accessibility và các utility dùng chung). Public entry khoảng 3.3kB JS / 10.6kB CSS, không import root portal. Account entry khoảng 1.34kB; heavy Ant/history/forms ở lazy panel khoảng 10.8kB cùng React/Ant chunks. Tab liệu trình/preferences không tải panel này. Build vẫn cảnh báo shared Ant chunk khoảng 540kB raw / 170kB gzip; không che cảnh báo hoặc nâng dependency để né.

## Giới hạn nghiệm thu

- Chưa kiểm tra PostgreSQL bị skip, ngân hàng thật, hosted CI hoặc staging.
- Root text resize 200% là phép thử CSS; **không thay thế native browser zoom 200%**. Chưa kiểm tra bàn phím trên thiết bị iOS/Android thật.
- Nội dung CS1/CS2 và marketing xem checklist A06 trong `baseline.md`; không tự sửa theo phỏng đoán.
- Legacy được giữ để rollback và phục vụ admin/shared consumers. Không tuyên bố mọi vùng đã chuyển sang React: liệu trình, loyalty, review và preferences giữ JS hiện hành, shell/token và ownership đã được thống nhất.

## Kiểm tra lại ngày 19/10/2026

Xem [báo cáo typography và trạng thái LAN](typography-audit-2026-10-19.md): build PASS, Vitest 63 PASS, foundation pytest 9 PASS; 34 public + 29 account cases trên preview refactor và khảo sát tương ứng trên LAN. Booking đã dùng giao diện mới; public/auth/profile LAN vẫn legacy. Kết quả các mục phía trên là lịch sử ngày 18/10, không phải toàn bộ được chạy lại trong lượt này.

Bổ sung theo ảnh người dùng: sửa căn giữa native dialog Đổi dịch vụ và nút trắng trên trắng trong thanh toán. `customer-ui-dialogs.playwright.js`: 33 trường hợp PASS ở 5 breakpoint với legacy/booking/public refactor CSS, API thanh toán dùng browser fixtures; Node loyalty/invoice-payment 15 PASS. Chi tiết nguyên nhân, phạm vi và ảnh trong báo cáo typography ở trên.

## Hoàn thiện E06 — Liệu trình, ngày 19/10/2026

Build PASS (còn cảnh báo Ant chunk >500kB); Vitest 69 PASS; Node 49 PASS; pytest foundation và các ca booking/lượt liệu trình chọn lọc 22 PASS / 19 deselected. Browser `customer-ui-treatments.playwright.js` PASS: tải theo tab, loading/empty/error/retry, gói chờ thanh toán độc lập, history chống click lặp, phản hồi cũ, deep link lượt tặng và fallback legacy. Browser account hiện có chạy lại bằng bản sao đổi port sang preview 5080: PASS. Không có uncaught exception hoặc failed request ngoài các HTTP 503 được fixture chủ động trả để kiểm tra lỗi.

360/390/768/1024/1440px không tràn ngang; kiểm tra 105 phần tử chữ mỗi kích thước, tương phản tối thiểu 4,71:1, dùng font hệ thống chung. Chi tiết và file thay đổi: [treatments-refactor.md](treatments-refactor.md). Chỉ kiểm tra preview với dữ liệu thử nghiệm; không chạy lại full pytest/hosted CI hoặc bật rollout LAN trong lượt này.

## Hủy mua gói chờ thanh toán — 19/10/2026

Thêm API và nút hủy cho cả legacy/refactor theo yêu cầu người dùng. Build PASS, Vitest 69 PASS, Node 49 PASS; pytest hủy purchase 10 PASS, 71 ca hồi quy loyalty payment/sale channels PASS. Lượt gộp có một lỗi thiết lập fixture paid; đã sửa test và chạy lại nhóm hủy thành công, không thay assertions nghiệp vụ. Browser cancellation và E06 regression PASS ở 5 breakpoint, không uncaught exception/failed request; có chủ động mock 503 để kiểm tra retry. Chỉ tạo/hủy đơn ở SQLite preview; LAN chỉ kiểm tra OPTIONS không thay đổi dữ liệu. Xem [purchase-cancellation.md](purchase-cancellation.md) cho file thay đổi, quyền, hoàn ưu đãi và phạm vi kiểm chứng.

## Hoàn thiện E07 — Điểm thưởng, đổi quà và ưu đãi, ngày 19/10/2026

Node 50 PASS; pytest customer rewards/tier 17 PASS (391 warnings). `customer-ui-rewards.playwright.js` PASS ở legacy và refactor: 3 màn × 5 viewport = 30 tổ hợp, thêm 2 lượt đo dialog; font thống nhất, tương phản chữ đo được tối thiểu 4,71:1, không tràn ngang. Kiểm tra tải theo tab, filters/pagination/empty, lỗi wallet và danh sách độc lập, retry, keyboard, focus, copy feedback trong modal, các nhóm voucher/quà và lost-response cùng key; exceptions=[], failed requests=[]. Có HTTP 503 chủ động từ fixture để kiểm tra retry.

`loyalty_customer_browser_check.py` chạy lại PASS với API và SQLite thật trong fixture: confirm/cancel, double click, lost-response sau reload chỉ trừ điểm một lần, số dư cuối 400, URL/filter restore, customer payment/admin và mobile. Cập nhật kỳ vọng test theo định dạng `4.300` và vị trí thông báo copy trong dialog, giữ nguyên assertions số điểm/giao dịch. Chi tiết, file và ảnh: [rewards-refactor.md](rewards-refactor.md). Không chạy lại full pytest, Vite build hoặc Vitest trong lượt E07 vì không thay frontend bundle; chưa xác minh rollout LAN/ngân hàng/thiết bị thật.

## Hoàn thiện E08 — Đánh giá, ngày 19/10/2026

`test_booking_gifts_reviews.py`, `test_phase2_analytics_review.py`, `test_ui_navigation_and_ratings.py`: 44 PASS (857 warnings); Node 50 PASS và `node --check app/static/js/reviews.js` PASS. `booking_gifts_reviews_browser.py` chạy lại PASS trên Edge với API/SQLite fixture: tạo/sửa/xem/xóa, chỉ dịch vụ được chọn, phản hồi admin/staff, thống kê public, HTML an toàn, lựa chọn gói/quà và modal mobile. Test cũ được cập nhật để chờ context tải xong, dùng hộp xác nhận xóa mới và kiểm tra màu nút Đóng theo token xanh mới; giữ assertions nghiệp vụ.

`customer-ui-reviews.playwright.js`: PASS cả legacy/refactor; 50 tổ hợp = danh sách/editor/tạo mới nhiều dịch vụ/xác nhận xóa/public × 5 viewport (360/390/768/1024/1440px) × 2 shell. Font thống nhất, tương phản chữ đo tối thiểu 4,71:1, dialog ở giữa, không overflow; kiểm tra lazy load, empty/loading/retry, response cũ, quyền context, lỗi giữ draft, chặn gửi/xóa lặp, keyboard/focus và public cập nhật ngay sau sửa. Ca PUT treo 20 giây timeout đúng, giữ draft và mở lại controls, không gửi lại. Exceptions=[], failed requests ngoài abort chủ động=[]; HTTP 400/403/503 chủ động để kiểm tra lỗi. Xem [reviews-refactor.md](reviews-refactor.md) cho file/ảnh/phạm vi. Không chạy lại full pytest, Vite build hoặc Vitest trong E08 (không thay bundle frontend); chưa rollout LAN hoặc nghiệm thu thiết bị thật.

## Gate E09/F — 19/10/2026

Build TypeScript/Vite PASS, xuất riêng vào `.test-tmp/customer-ui-final/portal` để không thay asset LAN đang phục vụ. Đối chiếu SHA-256 62 file/manifest với build preview: không khác biệt. Vitest 69 PASS / 13 files; Node 50 PASS; syntax check hai script E09/F PASS. Vẫn có warning shared Ant chunk >500kB; không đổi dependency để né warning.

- E09: 24 lượt đo ở 5 viewport trên legacy/refactor PASS, tương phản chữ tối thiểu 4,71:1, không tràn ngang. Lazy load, flag-off không có tab/assets, không tự opt-in, single PUT, version 0→1 và reload đúng; lỗi 400 giữ draft, 409/503 khóa ghi đến GET mới, GET lỗi/sai version không mở form bằng version cũ.
- 11 suite Playwright hiện có chạy lại PASS: foundation/public/account/auth-preferences/hardening/transactions/avatar/treatments/rewards/reviews/performance. Bản sao test chỉ đổi port 5078/5079 thành 5080, giữ assertions.
- Typography rộng: 34 public + 29 account cases, issues=[], errors=[], failed=[]. Dialog đổi dịch vụ/thanh toán: 33 cases PASS. Hủy purchase: cả legacy/refactor ở 5 viewport PASS, chỉ có đơn SQLite preview.
- F01/F02/F03 bổ sung PASS: init chat lặp vẫn một interval, pagehide dừng, persisted pageshow khởi động lại một vòng khi còn phiên và không khởi động khi thiếu token; compact chat 360/390×600 không che input, ESC trả focus; metadata/canonical/public không tải portal; preferences 720×480 và root text resize 200% không overflow. Lifecycle events và viewport là giả lập.
- 11 browser smoke có API/DB PASS: 8 suite theo quality workflow cùng loyalty, booking/gifts/reviews và admin-booking. Mail/AI/provider mock, không tạo giao dịch thật.
- Full pytest lượt E09/F: **779 PASS, 24 SKIP, không FAIL**, 12.719 warnings, 1717,79s. Lệnh `python -m pytest tests -q --ignore-glob=*.tmp --disable-warnings --tb=short`; log `pytest-full.log`. Không coi 24 skip là pass; có nhóm PostgreSQL thiếu môi trường và điều kiện lịch hẹn cùng ngày. Các kết quả full pytest ở đầu tài liệu là lịch sử, không thay thế lượt này.

Chỉ đọc HTTP trên LAN: public/auth/profile vẫn chưa có entry refactor mới, booking có. Không bật flag, restart hoặc deploy. Native browser zoom 200%, bàn phím iOS/Android thật, PostgreSQL thiếu môi trường và hosted CI chưa được nghiệm thu; không coi skip là pass. Kết quả performance, file thay đổi, log/ảnh và các điều kiện rollout: [e09-final-hardening.md](e09-final-hardening.md), [release-checklist.md](release-checklist.md).

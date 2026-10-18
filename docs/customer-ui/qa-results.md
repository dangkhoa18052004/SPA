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

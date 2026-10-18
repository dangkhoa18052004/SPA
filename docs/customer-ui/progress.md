# Tiến độ refactor customer UI

Nguồn yêu cầu: `refactorUI_Customer.md`. Bắt đầu tại `c189ad9f21e78ba423455c55e9181ef109478749`, ngày 18/10/2026. Các đợt chỉ là checkpoint local; chưa commit/deploy hay bật flag production.

| Task ID | Trạng thái | File / bằng chứng | Vấn đề còn lại | Tiếp theo |
|---|---|---|---|---|
| A01–A02 | Xong | `baseline.md`: commit, working tree, routes, hashes, consumers | Không | A03 |
| A03 | Xong | 14 ảnh baseline 390/1440px tại `.test-tmp/customer-ui/before-*`; guest và profile customer test | 401 guest restore và favicon 404 là baseline | A05 |
| A04 | Xong | `contracts.md`, đối chiếu route/JS hiện tại | Endpoint chi tiết chỉ mở rộng types khi triển khai màn tương ứng | B05 |
| A05 | Xong | `design-spec.md`, desktop/mobile và state matrix; đã xem ảnh baseline | Không | B01 |
| A06 | Xong phần kiểm kê | `baseline.md`: content checklist | Chủ dự án xác minh CS1, giờ/địa chỉ và nguồn số liệu; không chặn foundation | C01 |
| B01–B06 | Xong nền tảng public/booking | `tokens.css`, `theme.ts`, `ui.tsx`, `customer-main.ts`, `public.css`, gate/resolver/layout, API/auth bridge; build PASS; Vitest 60 PASS; Node auth 3 PASS; pytest foundation/admin shell/phase4/assets 21 PASS; Playwright foundation 5 viewport, errors=[], failed=[] | Account entry/Ant forms thuộc E; theme adapter đã typecheck, popup cần verify khi dùng ở E | C01–C05 |
| C01–C02 | Xong local | `index.html`, `catalog.ts`, `public.css`, main/services/recommendations renderer: hero CTA, cards semantic, escape API text, null/zero price, fallback ảnh | Thông tin doanh nghiệp theo A06 chưa được xác minh | QA staging |
| C03–C05 | Xong local | `services.js`, `services.html`, `service-detail.js`: filter/search/sort/URL, metadata, deep link, giữ một capture listener tracking; Node catalog/recommendation 12 PASS; pytest liên quan 113 PASS; Playwright public 20 tổ hợp viewport/route PASS, errors=[], failures=[] | Chưa đo tracking bằng dữ liệu khách thật; chỉ test accounts | QA staging |
| C06 | Xong giao diện, giữ nghiệp vụ | CSS package cards cùng token; giữ nguyên `packages.js`, sale channels và purchase resume; package/API tests và phase4 browser PASS | Không bật QR hoặc cash channel mới | Không cần sửa backend |
| D01–D04 | Xong local | Booking giữ model/stepper/entitlements/pending marker; tokens chung, resource abort, tự xóa staff không còn khả dụng; pytest booking/payment/package 108 PASS; browser catalog PASS ở 390/768/1440 | Không phát sinh giao dịch thật | QA staging |
| D04 kiểm thử lỗi mạng | Xong | `customer-ui-transactions.playwright.js`: server tạo lịch rồi mất response; double click chỉ POST 1 lần; reload và reconcile ra đúng lịch, không POST lại | Không | — |
| D05–D07 | Xong local | `loyalty-payment.js`: copy số TK/nội dung, trạng thái chờ xác nhận, restore focus; giữ polling/resume/điểm/voucher; đóng QR không đổi invoice sang paid; phase4 và loyalty browser PASS | QR/provider chỉ dùng fixture/mock; chưa kiểm tra ngân hàng thật | QA staging được cho phép |
| E01 | Xong local | `_auth_assets.html`, 5 auth templates, `auth.js`, OTP paste trong customer entry; 5 màn × 5 viewport PASS; repeat submit chỉ 1 request đăng ký | Giữ form native nhất quán; Ant dùng ở form profile, không trộn hai họ control trong một form | QA staging |
| E02–E03 | Xong local | `customer-account-main.tsx`, lazy `account-panels.tsx`, profile template/JS, `account.css`: hash/Back/Forward, active-tab loading, form Ant; avatar upload thật vào thư mục test đồng bộ header sau success, rejection giữ ảnh cũ; business 401 không logout/retry | Chỉ dùng tệp và tài khoản test local | QA staging |
| E04–E05 | Xong local | Table desktop/card mobile, filter status, Drawer chi tiết; cancel/change/review qua bridge hiện hữu, payment chỉ invoice chờ; browser account 5 viewport PASS | Backend vẫn quyết định quyền và số tiền | — |
| E06–E08 | Xong bằng migration từng vùng | Liệu trình, loyalty và review tiếp tục một owner JS hiện hành, dùng shell/token mới; không viết lại idempotency/entitlement; review bỏ eager fetch ẩn; tất cả tab responsive PASS; loyalty browser PASS double click/lost-response/URL | Không chuyển các vùng này sang React chỉ để thay DOM | Giữ legacy consumers |
| E09 | Xong local | Preferences lazy theo tab; giữ version, 409 hiện tải lại và khóa submit tới khi reload; test flag on/off và mock conflict PASS | Không tự opt-in | — |
| F01 | Xong local | Chat interval không tạo lặp, dừng pagehide/logout, bỏ pending marker khi logout; nhạc mới không autoplay; chat mobile tích hợp vùng navigation | Bàn phím thiết bị thật còn cần nghiệm thu | F02 |
| F02 | Đã QA tự động; còn nghiệm thu thiết bị | 360/390/768/1024/1440px, ảnh lỗi/tên dài, native dialogs/ESC, keyboard và root text resize | Native browser zoom 200% và bàn phím iOS/Android thật chưa được kiểm chứng; xem `qa-results.md` | QA staging/device |
| F03 | Xong phần local | Entry public không import portal; account controls lazy; metadata detail từ server; đo LCP/CLS local trước/sau và kích thước entry trong `qa-results.md` | Có warning Ant shared chunk >500kB; không coi số đo loopback là field data | Theo dõi staging |
| F04 | Đã chạy gate local | Build PASS; Vitest 63 PASS; Node 49 PASS; full pytest 768 PASS / 24 SKIP; bổ sung foundation/assets/navigation 15 PASS; 8 smoke suites CI và loyalty browser PASS (phase6 chạy lại sau timeout) | Chưa xác minh các test PostgreSQL bị skip và điều kiện giờ hẹn; chưa chạy GitHub CI trên branch | Gate staging trước rollout |
| F05 | Xong kiểm kê/cleanup an toàn | Không xóa shared packages/reviews/change-services/payment vì còn admin/legacy consumers; bỏ component mới chưa dùng, giữ một owner cho mỗi root | CSS/JS legacy được giữ cho fallback có chủ đích | Không xóa thêm |
| F06 | Xong tài liệu bàn giao | `release-checklist.md`, `qa-results.md`, `changed-files.md`; mặc định flag mới false, có rollback và preview local | Chưa commit, tạo PR, thay config production hoặc deploy | Review diff và QA staging |

Các nhóm trên là checkpoint thực hiện local PR0–PR6, không phải bảy PR đã được tạo trên GitHub. Không tuyên bố hoàn thành nghiệm thu production khi còn các mục kiểm chứng bổ sung đã ghi.

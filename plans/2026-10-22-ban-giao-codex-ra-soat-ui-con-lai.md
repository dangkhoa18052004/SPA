# Bàn giao cho Codex: phần còn lại của rà soát giao diện

Ngày: **22/10/2026**, giờ Asia/Saigon. Workspace: `E:\Project\Spa\SPA`.

Tài liệu này nối tiếp `plans/2026-10-21-ban-giao-claude-kiem-tra-ui-va-tang-dich-vu.md` (gọi tắt là **plan 21/10**). Plan 21/10 vẫn là nguồn chính cho nguyên tắc, ma trận trang (mục 6), hành trình J01–J10 (mục 7), mẫu ghi lỗi (mục 10) và điều kiện hoàn thành (mục 11). Ở đây chỉ ghi những gì đã thay đổi, việc còn lại và các bẫy đã gặp.

## 1. Quy tắc bắt buộc

- Đọc `AGENTS.md`. Tìm symbol/path trước khi mở file, không quét cả repo.
- **Working tree có rất nhiều thay đổi có từ trước.** Không `git reset`, `git checkout .`, `git clean`, không stage/commit toàn bộ. Không coi cả `git diff` là thay đổi của nhiệm vụ này.
- Không đổi schema/migration, cấu hình production, không deploy, không commit nếu chưa được duyệt.
- Mọi thao tác ghi chỉ chạy trên fixture SQLite cổng **5091**. Không chạy test có ghi dữ liệu trên cổng **5000** (app local đang dùng); không dừng process cổng 5000.
- Không in token, mật khẩu, nội dung `.env`. Không bật provider thanh toán/email/AI thật.
- Báo cáo phân biệt: đã viết code / đã mở trang / đã kiểm thử nghiệp vụ / đã nghiệm thu.

## 2. Trạng thái hiện tại

Bằng chứng: `output/ui-review-2026-10-21/REPORT.md` và `output/ui-review-2026-10-22/REPORT.md` (log, ảnh cùng thư mục).

| ID | Trạng thái | Ghi chú |
|---|---|---|
| P0-00 → P0-03 | **Xong** | Quà tặng G01–G18 đều có E2E. G16 (đa tab) là giới hạn đã ghi nhận, không phải pass |
| P1-01 | Xong phía UI | API lịch sử bán gói vẫn `limit(200)`; phân trang API là việc riêng |
| P1-02 | **Xong admin + nhân viên** | Nhân viên: `/employee/appointments?view=<malh>` |
| P1-03 | **Xong** | Chưa kiểm OTP/reset thành công, chuyển hướng sau đăng nhập đúng |
| P1-04 | **Chờ chủ spa** | `/terms`, `/privacy` trả 404; không tự viết nội dung pháp lý |
| P1-05 | Một phần | Đã quét: admin, guest, customer, staff, manager, letan, legacy admin, legacy staff. Thiếu: legacy guest/customer, trang 403/404/ID không tồn tại, các flag tắt |
| P1-06 | Chưa | Chỉ mới sửa vài lỗi gặp tình cờ (UI-007, UI-008, UI-009, GIFT-003) |
| P1-07 | Một phần | J03 xong; J04 có phần ledger qua G14. Còn J01, J02, J05–J10 |
| P1-08 | Chưa | Báo cáo tổng cuối |
| P2-01..03 | Chưa | Đề xuất, cần quyết định nghiệp vụ |

### Các sửa trong 21–22/10 (để không làm lại hoặc vô tình hoàn tác)

| ID | File | Nội dung |
|---|---|---|
| UI-001..004 | `app/static/js/admin/package-sales.js` | Link tặng trên dòng phiếu paid ở UI legacy; phiếu vẫn mở khi API phụ lỗi |
| GIFT-001/002 | `frontend/src/admin/catalog/Packages.tsx`, `app/static/js/admin/packages.js` | Xóa `gift=1` sau khi đóng; legacy không bật lại nút sau lỗi 5xx |
| GIFT-003 | `Packages.tsx` (`TreatmentDrawer`) | Form tặng chỉ hiện sau `afterOpenChange`; `keyboard={!gifting}`; trả focus về drawer qua `panelRef`. Escape đóng đúng một lớp |
| GIFT-004 | `app/services/package_service.py` (`gift_service`) | Khách `trangthai != 'active'` → 400. **Chờ chủ spa xác nhận quy tắc** |
| UI-005..008 | `profile.js`, `register_shifts.js`, `roles.html`, `my_schedule.html` | Lỗi JS và tràn ngang ở legacy |
| UI-009 | `app/static/css/customers/catalog.css` (+ `v=1.2` trong `layout.html`) | Nút "Chi tiết" mất chữ khi hover/chạm (rule ID khóa màu chữ) |
| UI-010 | `app/routes/operations_bp.py`, `frontend/src/Appointments.tsx`, `frontend/src/BusinessDashboard.tsx` | `/api/me/appointments?id=` (vẫn giới hạn theo `manv` người đăng nhập); `?view=` mở drawer |
| UI-011 | `app/static/js/customers/auth-session.js` (+ `v=1.2` ở `layout.html`, `booking_react.html`, `login.html`) | Khách chưa đăng nhập chỉ gọi `restore-session` một lần mỗi trang |

Test/fixture đã thêm hoặc sửa: `tests/master_ui_preview.py`, `tests/ui-review-{pages,gifts,gifts-extra,controls,auth}.playwright.js`, `tests/ui-review-scan-runner.js`, `tests/test_booking_gifts_reviews.py`, `tests/test_employee_appointments.py`, `tests/customer-auth-session.test.cjs`. Bundle build nằm trong `app/static/portal/`.

## 3. Việc còn lại, theo thứ tự

### Lượt D1 — P1-05: hoàn thiện ma trận trang

1. Quét legacy cho guest và customer: `node tests/ui-review-scan-runner.js guest 1 <out.json>`, tương tự `customer 1`. Trước đó đọc `tests/ui-review-pages.playwright.js` để biết danh sách URL theo role và nhánh legacy.
2. Thêm ma trận **lỗi và quyền** (plan 21/10 mục 6, dòng "Lỗi và quyền"): route không tồn tại; ID không tồn tại cho `/services/<id>`, `/packages/<id>`, `/admin/packages/<id>`, drawer `?view=`; session hết hạn; role không được phép (letan vào trang tài chính, staff vào trang admin, customer vào `/admin/*`). Kỳ vọng: 403/404 có nút quay lại, không lộ dữ liệu, không lặp redirect.
3. Đã biết: letan mở `/admin/packages?ui=legacy` bị `alert()` chặn (server cũng trả 403). Có thể thay alert bằng trang thông báo; ghi đề xuất nếu không sửa.
4. Đối chiếu route thật bằng `/__qa/pages` của fixture. `/health/*`, file xác minh Google và `/api/*` nằm ngoài ma trận UI.
5. Ghi ma trận với các cột riêng: mở được / nội dung đúng / nút-biểu mẫu / mobile / role-API / legacy-flag / bằng chứng. Không dùng một ô "pass" chung.

### Lượt D2 — P1-06: duyệt trực quan

- Xem ảnh thật, không chỉ dựa `scrollWidth`. Ưu tiên luồng quan trọng ở 360/390/768/1024/1440: đặt lịch khách, hồ sơ khách, bán gói, lịch hẹn admin, cổng nhân viên.
- Kiểm: text dài, dữ liệu trống/lớn, nút disabled có lý do, focus nhìn thấy được, focus trả về sau khi đóng modal/drawer, bottom nav không che nội dung, modal không che CTA, tương phản ≥ 4.5:1 (đo bằng `getComputedStyle`, cách làm xem `output/ui-review-2026-10-22/REPORT.md` mục 7).
- **Mẫu lỗi đã gặp nên dò tiếp:** rule dạng `#id .btn-x { color: … }` ghi đè hover chung, làm chữ trùng màu nền khi hover. Lần rà gần nhất không còn chỗ nào, nhưng CSS mới có thể thêm lại.
- Quan sát chưa xử lý: trong form tặng, sau khi server trả lỗi, dropdown "Dịch vụ tặng" mở lại và che nhãn "Số buổi" (`output/ui-review-2026-10-22/g07-inactive-service-alert.png`). Chưa xác định do test hay người dùng cũng gặp.
- Sửa nhỏ, theo token/CSS hiện có, tránh override toàn cục. Mỗi lỗi cần ảnh before/after và kiểm lại tương tác gây lỗi.

### Lượt D3 — P1-07: hành trình liên màn hình

Còn J01, J02, J04 (phần UI: khách hủy trong `/profile#appointments`, nội bộ hoàn thành trong `/admin/appointments`), J05–J10, theo bảng ở plan 21/10 mục 7. Gợi ý:
- J02 (khách mua gói): VietQR giả dùng `--payments` + `POST /__qa/state {"vietqr_paid": <purchase_id>}`. Chặn ảnh `img.vietqr.io` trong test.
- J07 (đăng ký ca → duyệt → chấm công): GPS giả lập bằng `context.setGeolocation`; đọc `tests/operations_browser_check.py` trước khi chạy.
- J08 (chat): fixture có 17 hội thoại, `/__qa/customer-token/<conversation_id>` cấp token khách.
- J10: dùng `page.route` trả 502 sau khi server đã commit (mẫu trong `tests/ui-review-gifts.playwright.js`, ca G10). Luôn `unroute` trong `finally`.

### Lượt E — P1-08: báo cáo cuối

- Tạo `output/ui-review-<ngày>/REPORT.md`; chỉ chạy lại các suite bị ảnh hưởng (danh sách ở mục 5).
- Liệt kê chính xác file của nhiệm vụ (mục 2 ở trên + phần mới), không gộp dirty tree.
- Điền checklist plan 21/10 mục 11, đánh dấu rõ mục nào còn mở.

### Backlog cần quyết định (không tự làm)

| Mục | Cần gì |
|---|---|
| P1-04 | Chủ spa cung cấp nội dung hoặc URL Điều khoản/Chính sách. Không bỏ checkbox đồng ý để test qua |
| GIFT-004 | Chủ spa xác nhận "không tặng cho khách đang khóa" |
| G16 idempotency đa tab | Thiết kế backend riêng; nếu cần cột/bảng → dừng xin duyệt |
| P1-01 API >200 phiếu | Phân trang API tương thích; không bỏ `limit` để tải vô hạn |
| P2-01..03 | Plan 21/10 mục 3 và 5 |

## 4. Môi trường và các bẫy đã gặp

Khởi động fixture (chạy nền, log vào thư mục output trong ngày):

```powershell
npm --prefix frontend run build
python tests/master_ui_preview.py --port 5091 --all-ui            # thêm --payments khi cần VietQR giả
curl http://127.0.0.1:5091/__qa/ping                              # phải thấy environment=isolated-sqlite
```

Đăng nhập trong test: `GET /__qa/login/<admin|manager|staff|letan|customer|guest>` trả `access_token`; lưu vào `localStorage.admin_token` (nội bộ, kèm `admin_role`) hoặc `access_token` (khách). Mẫu xem đầu `tests/ui-review-gifts.playwright.js`.

`POST /__qa/state` (chỉ có trong fixture, nhận JSON): `{"treatment":id,"status":"cancelled|expired","expired":true}`, `{"item":id}` (cho quà hết hạn hôm qua), `{"service":madv,"active":false}`, `{"customer":makh,"trangthai":"blocked"}`, `{"vietqr_paid":purchase_id}`. Không đưa endpoint `/__qa/*` vào app chính.

Bẫy:
1. **Backend không tự reload.** Sửa Python xong phải dừng và chạy lại fixture. Dừng bằng PID đang nghe cổng 5091: `Get-NetTCPConnection -LocalPort 5091 -State Listen`. Dữ liệu fixture mất khi dừng, đó là bình thường.
2. **Build frontend khi phiên trình duyệt đang mở** làm trang tải chunk cũ (404) và hiện "Trang chưa tải được". Sau mỗi lần build, mở session `playwright-cli` mới (`-s=<tên mới>`).
3. `waitForLoadState('networkidle')` không bao giờ xong trên trang khách (có polling). Dùng selector cụ thể hoặc `waitForTimeout` ngắn.
4. Ở 390px, tên tài khoản admin trong header bị ẩn: dùng `waitFor({state:'attached'})`.
5. Danh sách "lịch hôm nay" của nhân viên nằm ở `/admin/dashboard` (role staff), **không** ở `/employee`.
6. Ant Design Select: lọc trước, rồi chọn trong popup thuộc đúng combobox (`aria-controls`). Không dùng `force` (helper `popup()`/`pick()` trong `ui-review-gifts-extra`).
7. Mỗi lần chạy test quà tạo phiếu/liệu trình mới; không đoán ID (`mathe=1`). Lấy ID từ response.
8. Đăng ký thiếu "Tên tài khoản" (`taikhoan`) bị trình duyệt chặn trước khi gửi, không phải lỗi app.
9. `admin_booking_browser_check.py` từng fail một lần ở bước đổi dịch vụ (`after total`), lần sau pass. Nếu gặp lại, điều tra như lỗi chập chờn, đừng bỏ qua.
10. Sau khi Escape đóng form tặng, focus về `.ant-drawer`. Test nhấn Escape cần đợi focus vào modal (đã viết sẵn trong G18).

## 5. Bộ hồi quy theo vùng thay đổi

| Nếu sửa | Chạy |
|---|---|
| Bất kỳ frontend | `npm --prefix frontend test`, `npm --prefix frontend run build` |
| Quà/gói/bán gói | `python -m pytest tests/test_booking_gifts_reviews.py tests/test_package_sale_channels.py -q`; `playwright-cli … run-code --filename=tests/ui-review-gifts.playwright.js` và `ui-review-gifts-extra.playwright.js` (cần `--payments`); `python tests/admin_catalog_browser_check.py`, `admin_billing_browser_check.py` |
| Lịch hẹn/tổng quan/nhân viên | `python -m pytest tests/test_employee_appointments.py -q`; `python tests/admin_booking_browser_check.py`; `ui-review-controls.playwright.js` |
| Script/phiên khách | `node --test tests/*.test.cjs`; `ui-review-auth.playwright.js` |
| Legacy admin/staff | `node tests/ui-review-scan-runner.js <role> 1 <out.json>`; `node --check <file.js>` |

Kết quả gần nhất (22/10): pytest 101 passed (employee + gifts + package channels); node 53/53; frontend 71/71; build OK; các E2E ở trên đều pass.

Chưa chạy trong hai ngày qua (đọc phần thiết lập trước khi chạy, không chạy bằng wildcard): `tests/operations_browser_check.py`, `tests/staff_security_browser_check.py`, `tests/admin_shell_browser_check.py`, `tests/customer-ui-*.playwright.js`, `tests/master-*.playwright.js`.

Không kiểm được trong môi trường này: Safari/iOS/Android thật, bàn phím ảo, GPS thật, in trên máy in thật, email/OTP và thanh toán provider thật.

## 6. Prompt ngắn cho Codex

> Đọc `AGENTS.md`, `plans/2026-10-21-ban-giao-claude-kiem-tra-ui-va-tang-dich-vu.md` và `plans/2026-10-22-ban-giao-codex-ra-soat-ui-con-lai.md`. P0, P1-01, P1-02, P1-03 đã xong; không làm lại, không hoàn tác các sửa ở mục 2. Làm tiếp theo thứ tự: P1-05 → P1-06 → P1-07 → P1-08. Chỉ dùng fixture SQLite cổng 5091 cho thao tác ghi; không đụng cổng 5000. Không đổi schema, cấu hình production, không deploy, không commit. P1-04, GIFT-004, G16 cần chủ spa/duyệt: ghi rõ là còn mở và tiếp tục các việc độc lập. Mỗi lỗi ghi theo mẫu ở plan 21/10 mục 10, có test và ảnh before/after; báo cáo vào `output/ui-review-<ngày>/REPORT.md`, phân biệt đã sửa có kiểm thử với chưa kiểm thử.

## 7. Cập nhật 23/10/2026 (kết quả thật, chi tiết ở `output/ui-review-2026-10-23/REPORT.md`)

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| P1-05 | **Xong** | 47 route thật; 6 vai trò × hiện đại/legacy × 390/1440 (460 lượt mở); ma trận lỗi/quyền 69 ca. Sửa UI-012 (đăng nhập nhân viên legacy tràn/không cuộn), UI-014 (cổng quyền legacy), UI-018/019 (link CSS chết, API cấm gọi thừa), UI-020 (trang 404 tiếng Việt), UI-021 (nút "Về tổng quan" ở 403) |
| P1-06 | **Xong phần kiểm được** | 5 độ rộng × 18 trang; bàn phím/Escape/focus 11 overlay; viewport thấp 390×420; tên truy cập thật. Sửa UI-015 (a11y), UI-017 (footer đặt lịch bị thanh tóm tắt che), UI-022 (tương phản Tag). Dropdown quà mở lại: không tái hiện (6 lượt). Thiết bị thật/bàn phím ảo thật: chưa |
| P1-07 | **Xong J01–J10** | Mới qua UI: J01, J02, J04, J06, J08, J09, J10 + xác thực (OTP/reset/redirect/nhân viên). J03/J05/J07 bằng bộ có sẵn chạy lại |
| P1-01 >200 | **Xong (tương thích)** | `before_id`/`has_more`/`next_before_id`; nút "Tải thêm" React; thông báo legacy |
| `admin_booking_browser_check` chập chờn | **Xong** | Harness bấm khi modal đang zoom → trúng mask. `click()` chờ phần tử đứng yên; 8/8 pass |
| P1-08 | Xong | Báo cáo 23/10 |
| P1-04, GIFT-004, G16, quyền API `customers/list` cho staff | **Còn mở** | Cần chủ spa / thiết kế backend; xem mục 6 báo cáo 23/10 |

Bẫy mới:
- `app/config.py` nạp `.env` → fixture có khóa Resend thật. `master_ui_preview.py` nay gỡ khóa và thay `send_email` ở mọi module bằng hộp thư `/__qa/outbox`. Harness khác dùng `create_app` vẫn nạp `.env`.
- Mật khẩu fixture: `customer_test`/`admin_test`/`staff_test`/`qa_manager`/`qa_letan` = `password`.
- `/__qa/expired-token/<role>` cấp token đã hết hạn; `POST /__qa/state {"expire_codes": email}` làm hết hạn OTP/mã đặt lại.
- Runner chung: `node tests/ui-review-run.js <kịch bản> <thư mục output> [tham số]` (context sạch, chặn ảnh VietQR).
- Badge "Tin nhắn" giới hạn 99+ với fixture (hội thoại 100 tin chưa đọc): đối chiếu chưa đọc theo từng hội thoại.

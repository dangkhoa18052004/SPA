# Bàn giao cho Claude Code: rà soát giao diện và khôi phục tặng dịch vụ khi mua gói

Ngày cập nhật: **21/10/2026**, múi giờ Asia/Saigon. Workspace: `E:\Project\Spa\SPA`.

**Trạng thái: đang làm dở, chưa nghiệm thu toàn bộ.** Người dùng yêu cầu bàn giao trạng thái và kế hoạch tiếp tục. Không coi tài liệu này là xác nhận mọi trang, nút bấm hay nghiệp vụ đã hoạt động đúng.

## 1. Yêu cầu cần hoàn thành

1. Kiểm tra toàn bộ các trang khách hàng, admin/quản lý/lễ tân và nhân viên: bố cục, chữ, nút, điều hướng, biểu mẫu, trạng thái dữ liệu và luồng nghiệp vụ.
2. Khôi phục đường vào dễ tìm cho việc **khách mua một gói/combo, nhân viên tặng thêm một dịch vụ với số buổi tùy chọn**. Khách phải thấy quà trong liệu trình và sử dụng đúng lượt tặng khi đặt lịch.
3. Sửa các lỗi đã xác minh bằng thay đổi nhỏ, tái sử dụng UI/API hiện có. Ghi nhận rõ các đề xuất UX chưa được triển khai.
4. Bàn giao bằng chứng: file thay đổi, lệnh kiểm thử, kết quả, ảnh trước/sau và các giới hạn còn lại.

### Nguyên tắc làm tiếp

- Đọc `AGENTS.md` tại root. Tìm symbol/path trước khi đọc, không quét hoặc viết lại cả repo nếu không cần.
- **Working tree đã có rất nhiều thay đổi từ trước phiên này.** Không `git reset`, `git checkout .`, `git clean`, không stage/commit toàn bộ. Không coi toàn bộ `git diff` là thay đổi của nhiệm vụ UI hiện tại.
- Không thay schema, cấu hình production hoặc deploy khi chưa có chấp thuận riêng. Nhiệm vụ này không cần migration để dùng lại tính năng tặng đang có.
- Không kiểm thử tạo phiếu, thu tiền, tặng dịch vụ, chấm công hoặc gửi tin trên dữ liệu thật. Dùng fixture riêng.
- Ưu tiên Playwright CLI theo `.agents/skills/playwright-cli/SKILL.md`; những browser harness có sẵn có thể dùng để hồi quy.
- Không in token, mật khẩu thật hoặc nội dung `.env`. Không bật nhà cung cấp thanh toán/email/AI thật cho test.
- Phân biệt rõ **đã viết code**, **đã mở trang**, **đã kiểm thử nghiệp vụ** và **đã nghiệm thu**.

## 2. Trạng thái thực tế đã làm

### 2.1 Thay đổi mới trong phiên này

| Hạng mục | File/symbol chính | Đã làm | Mức xác minh hiện tại |
|---|---|---|---|
| Nút tặng sau thanh toán | `frontend/src/admin/billing/PackagePayment.tsx` — `PackagePayment`, prop `onGift` | Thêm “Tặng thêm dịch vụ” trong kết quả thanh toán thành công nếu có `mathe` và callback được cấp | Build và bộ billing browser hiện có qua; test E2E mới chưa chạy đến cuối |
| Tặng từ phiếu bán gói | `frontend/src/admin/billing/PackageSales.tsx` — `Sales`, `actions` | Nút trên phiếu `paid`; dùng lại `TreatmentDrawer`; có hướng dẫn buổi tặng không tăng giá gói | Mã đã viết, trang đã mở; chưa nghiệm thu toàn bộ luồng mới |
| Tặng từ danh sách liệu trình | `frontend/src/admin/catalog/Packages.tsx` — `TreatmentList`, `TreatmentDrawer` | Nút trực tiếp, query `mathe`/`gift=1`, prop `startGift`, kiểm tra `can_gift` khi mở form | Bộ catalog browser hiện có qua, gồm tặng dịch vụ bằng luồng cũ trong drawer |
| Chống gửi lặp trong form quà | Cùng file — `GiftForm` | Khóa submit bằng `useRef`; lỗi mạng/5xx chuyển sang “Kiểm tra liệu trình”, không tự POST lại | Đã viết; test mất phản hồi/bấm hai lần mới chưa hoàn tất. Không phải idempotency backend |
| Lối vào từ tài khoản nhân viên | `frontend/src/Employee.tsx` — `Account` | Link “Liệu trình / tặng dịch vụ” cho admin/manager/staff khi bật `admin_catalog` | Đã quét trang; chưa chứng minh toàn bộ luồng staff → tặng → khách sử dụng |
| Phân trang bán gói mobile | `frontend/src/admin/billing/PackageSales.tsx` | Thay `rows.slice(0, 30)` bằng trang 10 phiếu; desktop/mobile dùng chung trang; reset khi đổi lọc | Build/billing browser qua; test riêng dữ liệu >30 phiếu chưa chạy |
| Mở đúng lịch từ tổng quan | `frontend/src/BusinessDashboard.tsx`, `frontend/src/admin/booking/Appointments.tsx` | Link `?view=<malh>`; mở drawer theo query; đóng drawer xóa query | Đã viết, booking browser hồi quy qua; chưa chạy test riêng click tổng quan → đúng khách |
| Hiện/ẩn mật khẩu đăng ký | `app/templates/customer/register.html` | Thêm tên truy cập, `aria-controls`, `aria-pressed`, cập nhật nhãn nút xác nhận mật khẩu | Đã viết sau lượt quét guest; test kiểm tra nút mới chưa chạy |
| Khôi phục lối tặng trên UI cũ | `app/static/js/admin/package-sales.js`, `app/static/js/admin/packages.js` | Thêm helper link từ phiếu và hỗ trợ query mở liệu trình/form | **Chưa xong: có lỗi nhãn tiếng Việt và thiếu gắn link vào dòng lịch sử. Xem P0-01** |

**Không viết mới backend quà tặng.** Backend và một form tặng đã tồn tại từ trước; công việc hiện tại chủ yếu là làm cho người dùng tìm thấy và đi đến chức năng đó đúng chỗ.

### 2.2 Các file kiểm thử và môi trường đã bổ sung

| File | Vai trò | Trạng thái |
|---|---|---|
| `tests/master_ui_preview.py` | Fixture SQLite tạm có sẵn; phiên này thêm `--all-ui`, `/__qa/pages`, khóa request để hạn chế xung đột SQLite dùng chung kết nối | Đã dùng. File này đã là untracked từ trước; không nhận toàn bộ nội dung là mới |
| `tests/ui-review-pages.playwright.js` | Quét trang theo vai trò, viewport, lỗi JS/network, overflow, ảnh hỏng; chụp ảnh | Đã chạy admin, guest, customer, staff; nhánh manager/letan/legacy đã thêm nhưng chưa chạy |
| `tests/ui-review-gifts.playwright.js` | Kịch bản mới mua gói → thu tiền → tặng → staff → khách đặt lượt tặng; mô phỏng mất phản hồi | **Chưa pass**. Lượt cuối dừng tại chọn gói trong Ant Design Select |
| `tests/ui-review-controls.playwright.js` | Test nút mật khẩu, >30 phiếu, legacy gift link, appointment deep link | **Đã viết, chưa chạy**; còn giả định dữ liệu cần chỉnh trước khi dùng |
| `output/ui-review-2026-10-20/` | Log, JSON, ảnh từ phiên kiểm tra | Kho bằng chứng, không phải source nghiệp vụ. Giữ tên thư mục cũ để không làm mất liên kết |

### 2.3 Kiểm thử đã có kết quả

| Lệnh/bộ kiểm tra | Kết quả đã thấy | Bằng chứng |
|---|---|---|
| `npm --prefix frontend run build` | Thành công; có cảnh báo bundle lớn hơn 500 kB | `output/ui-review-2026-10-20/build.log` |
| `npm --prefix frontend test` | **71 tests, 13 files passed** | `frontend-tests.log` cùng thư mục |
| `python -m pytest tests/test_booking_gifts_reviews.py tests/test_package_sale_channels.py -q` | **86 passed**, có cảnh báo/deprecation, không phải 86 test UI | `gift-api-tests.log` |
| `python tests/admin_catalog_browser_check.py` | Passed | `catalog-browser.log`; ảnh trong `.test-tmp/admin-catalog-browser-eabb7702/` |
| `python tests/admin_billing_browser_check.py` | Passed | `billing-browser.log`; `.test-tmp/admin-billing-browser-96f91106/` |
| `python tests/admin_booking_browser_check.py` | Passed | `booking-browser.log`; `.test-tmp/admin-booking-browser-1a785883/` |
| `python tests/admin_people_browser_check.py` | Passed | `people-browser.log`; `.test-tmp/admin-people-browser-c489f2ca/` |
| `python tests/admin_care_browser_check.py` | Passed | `care-browser.log`; `.test-tmp/admin-care-browser-0ecc612d/` |

Không cộng số lần rerun, số ảnh hoặc số trang vào số tests backend/frontend. Bộ hồi quy pass không đồng nghĩa các nhánh mới của quà tặng đã được kiểm thử đầy đủ.

### 2.4 Phạm vi quét trang đã hoàn thành

| Vai trò | Số đường dẫn/trạng thái URL | Viewport | Số lượt | Kết quả cuối |
|---|---:|---|---:|---|
| Admin | 31 | 390 và 1440 px | 62 | JSON cuối không có JS exception, overflow toàn trang, ảnh hỏng hoặc HTTP lỗi được ghi nhận |
| Khách chưa đăng nhập | 12 | 390 và 1440 px | 24 | Không JS exception/overflow; còn request khôi phục phiên trả 401 khi chưa đăng nhập, cần phân loại riêng |
| Khách đã đăng nhập | 15 | 390 và 1440 px | 30 | JSON cuối không có các lỗi nêu trên |
| Nhân viên | 10 | 390 và 1440 px | 20 | JSON cuối không có các lỗi nêu trên |
| **Tổng** | **68 cặp vai trò/URL, có URL trùng giữa vai trò** | | **136 lượt** | **Đây là quét mở trang, không phải 136 luồng nghiệp vụ đã nghiệm thu** |

Bằng chứng: `admin-scan.json`, `guest-scan.json`, `customer-scan.json`, `staff-scan.json` trong thư mục output trên. Có 145 file PNG tại thời điểm bàn giao, bao gồm ảnh chẩn đoán và test dở; không được ghi “145 ảnh đều pass”. Chỉ một phần ảnh đã được xem trực tiếp, chưa duyệt thủ công toàn bộ 145 ảnh.

Một số lỗi 500/404/503 ban đầu trong fixture không còn xuất hiện ở lượt quét cuối sau khi tuần tự hóa request SQLite. Không kết luận đã sửa production cho các lỗi này.

## 3. Việc chưa xong và bảng ưu tiên thực hiện

Quy ước: **P0** phải giải quyết trước khi tuyên bố tính năng quà tặng hoàn tất; **P1** cần hoàn thành để nghiệm thu yêu cầu rà soát giao diện; **P2** nâng cấp UX/tối ưu sau khi luồng chính ổn định. Ước lượng là số phiên làm việc tập trung, không phải cam kết thời gian.

| ID | Ưu tiên / trạng thái | Việc cần làm | Phụ thuộc | Sản phẩm bàn giao / tiêu chí chính | Ước lượng |
|---|---|---|---|---|---|
| P0-00 | P0 / chưa làm khi tiếp nhận | Chụp trạng thái working tree, chuẩn bị fixture/test sạch, xác minh build từ source hiện tại | Không | Không mất thay đổi có sẵn; fixture cô lập, chạy đúng source | 1 phiên |
| P0-01 | P0 / lỗi đã thấy trong source | Hoàn thiện legacy gift: sửa chữ, gắn nút vào dòng phiếu, kiểm tra phiếu/in và lỗi tải phụ | P0-00 | Cả dòng phiếu đã trả tiền và chi tiết phiếu đều có đường tặng hợp lệ | 1 phiên |
| P0-02 | P0 / test đang fail | Điều tra Ant Design Select và ổn định test E2E quà tặng | P0-00 | Chọn gói/dịch vụ bằng chuột, bàn phím, tìm kiếm đều dùng được; test không force-click để che lỗi | 1–2 phiên |
| P0-03 | P0 / đã viết code, chưa nghiệm thu | Hoàn thiện và kiểm thử xuyên suốt quà tặng, đúng khách/phiếu/lượt, quyền, mất phản hồi | P0-01, P0-02 | Test tạo quà + khách đặt lịch + ledger pass; không tính thêm tiền, không trừ nhầm lượt gói | 2 phiên |
| P1-01 | P1 / test mới chưa chạy | Chứng minh phân trang >30 phiếu, bộ lọc, resize desktop/mobile; đánh giá giới hạn 200 từ API | P0-00 | Không mất phiếu trong tập kết quả; có phương án rõ cho lịch sử >200 | 1 phiên |
| P1-02 | P1 / mới sửa phía admin | Kiểm tra deep link lịch hẹn và bổ sung phía nhân viên nếu cần | P0-00 | Bấm đúng khách mở đúng lịch; reload/back/close giữ điều hướng hợp lý | 1 phiên |
| P1-03 | P1 / có code, thiếu verification | Kiểm tra đăng ký/đăng nhập, nút mật khẩu, lỗi form, khôi phục phiên | P0-00 | Nhãn và trạng thái nút đúng; lỗi form dễ hiểu; không lặp request ngoài ý muốn | 1 phiên |
| P1-04 | P1 / đường dẫn thiếu trong route inventory | Xử lý `/terms`, `/privacy` và rà liên kết nội bộ lỗi | Nội dung chủ spa đối với chính sách | Không còn link dẫn 404 được quảng bá là chính sách; không tự bịa điều khoản pháp lý | Tùy nội dung |
| P1-05 | P1 / mới quét một phần | Hoàn thành ma trận tất cả trang, manager/lễ tân, giao diện cũ và các feature flag hợp lệ | P0-00 | Mọi route giao diện có trạng thái và bằng chứng, không chỉ trang đang bật React | 2–3 phiên |
| P1-06 | P1 / chưa rà đủ | Duyệt ảnh, typography, nút, menu, responsive, bàn phím, focus và tương phản | P1-05 | Lỗi xác minh có before/after; modal và nút quan trọng dùng được ở 360 px | 2 phiên |
| P1-07 | P1 / có regression từng module | Kiểm tra đủ trạng thái và luồng liên màn hình của khách/admin/nhân viên | P0-03, P1-05 | Các hành trình trong mục 7 có kết quả cụ thể; ngoại lệ được ghi rõ | 2–3 phiên |
| P1-08 | P1 / chưa thực hiện | Chuẩn hóa báo cáo cuối và hồi quy sau các sửa mới | Các mục P0/P1 liên quan | Danh sách file chính xác, log cuối, ảnh và giới hạn; chưa deploy tự động | 1 phiên |
| P2-01 | P2 / đề xuất chưa triển khai | Mặc định lịch hôm nay, lọc nhanh, menu/icon và thuật ngữ nhất quán | P1-02, P1-06 | Giảm số thao tác, không làm hỏng tìm lịch quá khứ hoặc deep link khách | 1–2 phiên |
| P2-02 | P2 / đề xuất chưa triển khai | Cho khách xem/chọn trước đăng nhập, xem xét quà nhiều dòng hoặc chọn quà trước thu tiền | Cần chốt yêu cầu mở rộng | Không tự thay quy tắc kích hoạt liệu trình/thu tiền hoặc tạo quà trước khi trả tiền | Tách nhiệm vụ |
| P2-03 | P2 / cảnh báo đã thấy | Đánh giá bundle và hiệu năng danh sách lớn | Sau lỗi chức năng | Đo trước/sau, không thêm thư viện/chia lại cả app chỉ để xóa warning | 1 phiên |

## 4. Hướng dẫn thực hiện chi tiết các mục P0

### P0-00 — Tiếp nhận workspace và dựng môi trường

1. Chạy `git status --short`; lưu riêng danh sách trước khi sửa. Đọc diff của **9 file ứng dụng** tại mục 2.1, không khôi phục chúng về HEAD.
2. Đọc các test mới, không mặc định chúng đúng. Những script `master-*` có sẵn có thể hardcode port 5088/5087 hoặc fixture khác; không chạy nhầm vào 5000.
3. Kiểm tra cổng 5091. **Lần kiểm tra gần nhất khi bàn giao không còn server lắng nghe cổng này.** Phải khởi động lại; fixture mất dữ liệu khi dừng là bình thường.
4. Dựng lại frontend; chạy fixture riêng theo mục 9. Không bật `--payments` trừ khi test cần, và vẫn chỉ dùng thông tin ngân hàng giả.
5. Fixture dùng SQLite `sqlite://`, chia sẻ một connection. Khóa request đã thêm để hạn chế lỗi khi nhiều API cùng tải. Xem lại thứ tự `teardown_request`/`db.session.remove` trước khi chạy nhiều browser đồng thời; không đưa khóa toàn cục này sang production.
6. Thu thập `/__qa/pages` để đối chiếu route thật. Các endpoint `/__qa/*` chỉ thuộc fixture; không đưa vào app chính.
7. Tạo thư mục output mới nếu chạy ngày khác. Không ghi đè log lỗi cũ trước khi trích nguyên nhân vào báo cáo.

Nghiệm thu: build thành công; `/__qa/ping` trả `environment=isolated-sqlite`; không có provider thật; test không cần đọc thông tin đăng nhập thật.

### P0-01 — Sửa phần legacy đang dang dở

**Phát hiện đã xác minh khi bàn giao:**

- `app/static/js/admin/package-sales.js:8` có nhãn **`T?ng th?m d?ch v?`** trong `giftLink`. Đây là chuỗi hỏng thật trong file, không chỉ cách PowerShell hiển thị.
- `giftLink(p)` hiện mới được gọi trong `receipt()`. **Chưa được gắn vào `history()`**, nên test tìm link tại dòng lịch sử sẽ không tìm thấy.
- `receipt()` đang chờ thêm API `/api/admin/package-sales/<id>` trước khi mở phiếu. Cần tránh để lỗi của request phục vụ nút quà làm mất khả năng xem/in phiếu vốn đã tải thành công.

Các bước:

| Bước | Thao tác | Điều kiện đạt |
|---|---|---|
| 1 | Sửa bằng công cụ ghi UTF-8 an toàn, ví dụ `apply_patch`; tránh pipe PowerShell→Python chứa tiếng Việt nếu chưa đặt encoding | Đọc lại file thấy đúng “Tặng thêm dịch vụ” |
| 2 | Gắn helper vào cột thao tác của `history()` cho phiếu `paid` có `mathe` và role hợp lệ | Pending/failed/cancelled không có nút; paid có link đúng `mathe` |
| 3 | Kiểm tra helper trong `receipt()`; request thêm thất bại chỉ làm thiếu hành động phụ, không làm biến mất phiếu | Xem/in vẫn dùng được nếu endpoint phụ lỗi |
| 4 | Kiểm tra print không in nút tương tác thừa; tái sử dụng `no-print` nếu phù hợp | Phiếu in sạch, số tiền không đổi |
| 5 | Kiểm tra `admin/packages.js` nhận `tab=treatments&mathe=...&gift=1`; backend `can_gift` quyết định mở form | Link vào đúng khách/gói; id không tồn tại có thông báo; role bị cấm không mở được form |
| 6 | Chạy UI cũ thật bằng `?ui=legacy`, không chỉ mở React từ link legacy rồi kết luận cả legacy pass | Ảnh desktop/mobile cho lịch sử, phiếu, form tặng; thao tác hủy không ghi dữ liệu |

Không dựa vào `localStorage.admin_role` làm quyền thật; đây chỉ là điều kiện hiển thị. Backend tiếp tục kiểm quyền.

### P0-02 — Điều tra test Select thất bại

Log cuối: `output/ui-review-2026-10-20/gift-flow.log`. Kịch bản dừng tại:

```javascript
page.locator('.ant-select-item-option').filter({ hasText: 'Gói kiểm thử 01' }).click()
```

Thông báo: phần tử tồn tại nhưng ở ngoài viewport/không ổn định rồi timeout. Lượt trước cũng có hiện tượng tương tự ở dịch vụ tặng. **Chưa xác định đây là lỗi component/CSS hay cách chọn phần tử trong test.**

1. Tạo browser context/session sạch; xác minh form/option đang thấy và chụp ảnh trước khi click.
2. Tái hiện bằng thao tác bình thường: mở Select, chọn dòng đầu, tìm theo tên, dùng ArrowDown/Enter; thử 360, 390, 768, 1024, 1440 px.
3. Kiểm tra option virtualization, chiều cao item so với style thực tế, popup container, z-index, overlay, scroll và focus. Chỉ sửa app nếu tái hiện được lỗi người dùng.
4. Nếu vấn đề chỉ là test, tìm kiếm trước bằng combobox được đặt tên, đợi kết quả đúng rồi chọn trong popup đang mở. Test hiện đã tìm khách bằng SĐT và tìm dịch vụ 02/03; **chưa lọc Select gói trước khi chọn**.
5. Không dùng `force: true`, DOM `.click()` hoặc kéo timeout thật dài để che lỗi chọn bình thường. DOM double-click trong test chỉ dành cho ca cố ý kiểm tra chống gửi lặp.
6. Wait theo trạng thái UI; không kết luận overflow ngay giữa animation resize/modal. Lượt đầu từng báo 360px overflow tức thời, đo lại sau animation là `scrollWidth === innerWidth`; ảnh không chứng minh tràn ngang thực tế.

Nghiệm thu: lựa chọn bằng chuột và bàn phím hoạt động; test đi qua chọn gói/dịch vụ ổn định; nếu sửa app có ảnh/video repro và test hồi quy.

### P0-03 — Nghiệm thu nghiệp vụ tặng dịch vụ

#### Luồng được triển khai hiện tại

`Chọn khách → chọn gói → tạo phiếu → thanh toán thành công → Tặng thêm dịch vụ → chọn dịch vụ/số buổi/thời hạn/ghi chú → xác nhận → khách xem liệu trình → đặt bằng lượt tặng`.

- Chỉ thêm quà sau khi có liệu trình đã kích hoạt. Đây là cách tận dụng mô hình hiện có, không phải tính năng chọn quà trong giỏ trước thanh toán.
- Một form tặng một dịch vụ với nhiều buổi; có thể tặng thêm dịch vụ khác bằng thao tác tiếp theo. Chưa có bảng nhiều dòng quà trong một lần lưu.
- Staff dùng trang liệu trình, không được tự mở quyền bán gói. Admin/manager có cả lối từ bán gói.

#### Hợp đồng API và dữ liệu cần giữ

| Nội dung | Điểm vào hiện có |
|---|---|
| Chi tiết liệu trình và quyền tặng | `GET /api/admin/packages/treatments/<mathe>` → `treatment`, `can_gift`, `services` |
| Thêm quà | `POST /api/admin/packages/treatments/<mathe>/gifts` |
| Body | `makh`, `madv`, `quantity`, `gift_note`; tùy chọn **một trong** `validity_days` hoặc `expires_at` |
| Kết quả | HTTP 201, `item_id`, `treatment` |
| Xử lý nghiệp vụ | `app/services/package_service.py` → `gift_service` |
| Kiểm quyền/API | `app/routes/package_bp.py` → `admin_treatment_detail`, `grant_treatment_gift`, `treatment_staff_required` |
| Hiển thị khách | `frontend/src/customer/treatments.ts`, `app/static/js/packages.js`, `/profile#treatments` |
| Đặt lượt quà chính xác | `/appointments/create?treatment=<mathe>&service=<madv>&item=<gift_item_id>`; `frontend/src/customer/Booking.tsx`, `booking-model.ts` |

Giữ `source_type='gift'`, `gifted_by_staff`, ngày tạo, ghi chú, số buổi, thời hạn, giá trị lượt quà bằng 0. Không sửa `items` của gói danh mục để làm quà cho tất cả khách khác.

#### Ma trận ca bắt buộc

| Mã | Ca kiểm tra | Kỳ vọng |
|---|---|---|
| G01 | Mua gói bằng tiền mặt rồi tặng dịch vụ khác 2 buổi | Đúng khách, đúng `mathe`; giá phiếu và tổng thực thu không tăng |
| G02 | Phiếu pending/failed/cancelled | Không cho tặng từ phiếu chưa kích hoạt |
| G03 | Dịch vụ tặng trùng dịch vụ đã có trong gói | Tách item quà, không tăng hoặc trừ nhầm item trả tiền |
| G04 | Tặng thêm hai dịch vụ bằng hai lần hợp lệ | Hai item đúng nội dung; không mất quà trước |
| G05 | Thiếu dịch vụ; 0, số âm, số lẻ, quá giới hạn; ghi chú quá dài | Validation rõ ở UI; API không ghi dữ liệu sai |
| G06 | Vô thời hạn / số ngày / ngày hết hạn / ngày quá khứ | Chỉ gửi field ứng với chế độ đang chọn; ngày VN nhất quán |
| G07 | Khách bị khóa, dịch vụ ngừng, liệu trình bị hủy, sai `makh` | API từ chối đúng, thông báo UI đọc được |
| G08 | Admin/manager/staff hợp lệ; customer/letan không có quyền | Quyền server được giữ; không chỉ ẩn nút |
| G09 | Bấm xác nhận liên tiếp khi request đang chờ | Một POST, một quà trong ca này |
| G10 | Server commit nhưng response bị mất/502 | Không tự POST lại; người dùng được kiểm tra liệu trình đã cập nhật |
| G11 | Lỗi trước commit; lỗi refresh; đóng/mở hoặc reload sau lỗi không rõ | Không tuyên bố thành công khi chưa biết; không dẫn đến tặng lặp âm thầm |
| G12 | Khách mở `/profile#treatments` | Thấy dịch vụ, số lượt khả dụng, thời hạn; phân biệt quà với lượt mua |
| G13 | Khách bấm “Đặt lịch bằng lượt tặng” và hoàn thành đặt | Đúng `the_item_id`; tiền phần quà bằng 0; giữ đúng 1 lượt |
| G14 | Hủy lịch đã giữ lượt; hoàn thành lịch; quà hết lượt/hết hạn | Hoàn/tiêu đúng lượt; không cho dùng vượt khả dụng |
| G15 | Gói gốc hết hạn nhưng quà có hạn độc lập còn hiệu lực | Giữ đúng hành vi backend hiện có; không khóa quà chỉ vì gói gốc hết hạn |
| G16 | Hai tab/nhân viên thao tác đồng thời | Ghi rõ giới hạn; không gọi khóa UI là bảo đảm exactly-once của backend |
| G17 | Sau VietQR được xác nhận bằng mock fixture | Nút tặng xuất hiện cùng quy tắc paid; không chuyển khoản thật |
| G18 | Mobile, Escape, đóng drawer/modal, quay lại và đổi liệu trình | Không hiện nhầm tên khách hoặc dùng dữ liệu drawer trước |

Test mới hiện chưa đạt G01→G13 xuyên suốt. Các tests API đã pass chỉ xác minh các ca thực sự có trong bộ đó, không tự đánh dấu toàn bảng này là pass.

Nếu muốn bảo đảm idempotency qua reload/đa tab cần thiết kế riêng; ưu tiên giải pháp phù hợp mô hình hiện có. Nếu giải pháp cần bảng/cột mới, dừng phần migration để xin duyệt; vẫn hoàn thành các việc UI độc lập.

## 5. Hướng dẫn các sửa UI còn thiếu

| ID | Chi tiết triển khai và kiểm tra | File cần xem trước |
|---|---|---|
| P1-01 | Seed ít nhất 34 phiếu ở fixture; kiểm tra trang 1/4, chuyển viewport vẫn cùng trang, lọc khi ở trang cuối reset đúng, không có trang trắng sau đổi tập dữ liệu. `ui-review-controls` hiện giả định đúng 34 phiếu: đổi thành tổng động hoặc reset fixture trước chạy. API hiện có `limit(200)` nên phân trang client không giải quyết lịch sử hơn 200; ghi nhận và nếu cần bổ sung phân trang API tương thích, không bỏ limit để tải vô hạn | `PackageSales.tsx`; `app/routes/package_bp.py` tại lịch sử bán gói; `tests/ui-review-controls.playwright.js` |
| P1-02 | Seed lịch hôm nay cho 2 khách/2 nhân viên, click từng dòng trên tổng quan. Kiểm tra `?view=`, reload, back/forward, đóng. Hiện `detailHref` cố ý vẫn trả danh sách khi `staff && employeePortal`: **phía nhân viên chưa được sửa deep link**. Nếu bổ sung, API phải vẫn giới hạn lịch của chính nhân viên | `BusinessDashboard.tsx`, admin `Appointments.tsx`, `frontend/src/Appointments.tsx`, `app/routes/operations_bp.py`, `router.ts` |
| P1-03 | Test cả 2 nút hiện mật khẩu, label thay đổi, input type, keyboard Enter/Space. Kiểm tra lỗi đăng ký không làm mất input, khôi phục phiên guest không lặp vô ích, logout back không lộ tài khoản cũ. Không tự gửi OTP/email thật | `register.html`, `login.html`, `app/static/js/customers/auth.js`, `frontend/src/session.ts` |
| P1-04 | `/terms` và `/privacy` được link từ đăng ký nhưng không có trong route inventory. Xác minh HTTP trên fixture và tìm nội dung đã được chủ spa duyệt trong repo. Nếu chưa có, báo chủ spa cung cấp nội dung hoặc đường dẫn; không viết bừa chính sách, không bỏ checkbox đồng ý để làm test qua. Các liên kết khác kiểm tra fragment/target trước khi coi là lỗi | `app/templates/customer/register.html`, `app/routes/customer_bp.py`, các template layout/footer |
| P1-06 | Duyệt ảnh thật, không chỉ `scrollWidth`; kiểm tra text dài, dữ liệu trống/lớn, nút disabled có lý do, keyboard, focus return, modal không che CTA, bottom nav không che nội dung, bảng cuộn nằm trong vùng cho phép. Scanner `unnamedButtons` chỉ là gợi ý vì icon có thể có accessible name ở phần tử con | CSS/token hiện có, các component liên quan lỗi cụ thể; tránh global override rộng |
| P2-01 | Chỉ đổi mặc định lịch sang hôm nay sau khi xử lý giá trị “Toàn bộ”: `useQuery` xóa value rỗng, nên cần sentinel/logic rõ để người dùng vẫn chọn toàn bộ được. Giữ deep link `makh/q/view`, lịch quá khứ. Thống nhất “Khách đã đến / Đang phục vụ / Hoàn thành”, xem lại T/V/N/C trong menu thu gọn. Đây là đề xuất, chưa triển khai | `admin/booking/Appointments.tsx`, `booking/model.ts`, `admin/navigation.ts`, `AdminShell.tsx`, `Employee.tsx` |

## 6. Ma trận trang phải hoàn thành khi rà toàn bộ project

Đánh dấu riêng: **mở được**, **nội dung đúng**, **nút/biểu mẫu**, **mobile**, **role/API**, **legacy/flag**, **bằng chứng**. Không dùng một ô “pass” chung cho cả nhóm.

| Nhóm | URL/trạng thái phải có | Tương tác trọng tâm | Trạng thái bàn giao |
|---|---|---|---|
| Công khai | `/`, `/services`, `/services/<id>`, `/packages`, `/packages/<id>` | Menu desktop/mobile, tìm kiếm, lọc, phân trang, chi tiết, CTA đặt/mua, ảnh lỗi, ID không tồn tại | Đã quét các URL mẫu; chưa kiểm mọi nút/ID/empty |
| Xác thực khách | `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/verify-otp`, `/auth/reset-password` | Validation, hiện mật khẩu, redirect sau login, OTP/reset hợp lệ/hết hạn trong fixture | Đã mở trang; chưa nghiệm thu đủ states; policy links thiếu |
| Đặt lịch khách | `/appointments/create` và query service/treatment/item | 3 bước, lọc dịch vụ, lịch trống, chọn giờ/staff, quay lại giữ dữ liệu, dùng gói/quà, mất phản hồi, xác nhận | Backend quà/booking test có pass; E2E quà mới chưa xong |
| Hồ sơ khách | `/profile#info`, `#appointments`, `#treatments`, `#invoices`, `#loyalty`, `#reviews`, `#communication`, `#edit`, `#password` | Chuyển tab, cập nhật, thanh toán/hủy, đánh giá, điểm/quà, thông báo; refresh/hash/back | Đã quét 9 hash; cần chứng minh active section đúng, không chỉ URL đổi |
| Đăng nhập nội bộ | `/admin/login` | Login hợp lệ/sai/khóa, điều hướng vai trò, logout | Đã mở; regression hiện có không bao trùm mọi trạng thái |
| Tổng quan | `/admin/dashboard` | KPI có dữ liệu, lọc, số liệu, mở lịch cụ thể, CTA theo role, lỗi từng nguồn API | Admin đã quét; chưa manager/letan riêng; deep link mới cần test |
| Lịch và khách | `/admin/appointments`, `/admin/customers` + drawer/modal | Tạo/sửa/hủy, tiếp nhận/hoàn thành, đổi dịch vụ, tìm khách, khách vãng lai, lịch sử, xác nhận hành động | Booking browser passed; kiểm riêng thay đổi mới |
| Thu tiền và bán gói | `/admin/invoices`, `/admin/package-sales` + receipt/payment | Tiền mặt, VietQR giả, điểm/voucher, phiếu pending/paid, in, quà thêm, lọc/phân trang | Billing passed; luồng quà/phân trang mới thiếu bằng chứng riêng |
| Danh mục | `/admin/services`, `/admin/packages`, `/admin/packages/new`, `/<id>`, `/<id>/edit`, tab treatments | Tạo/sửa/ngừng, form lỗi, upload mẫu, chi tiết, tặng và hạn dùng | Catalog passed; legacy gift chưa hoàn tất |
| Nhân sự | `/admin/staff`, `/admin/roles`, `/admin/shifts`, `/admin/approve-shifts`, `/admin/my-schedule`, `/admin/register-shift`, `/admin/salary`, `/admin/my-salary` | Form, phân quyền, đăng ký/duyệt ca, lọc lương và nội dung khi thiếu ca | People browser passed; matrix role/legacy chưa đủ |
| Chăm sóc | `/admin/loyalty`, `/admin/reviews`, `/admin/chat`, `/admin/crm` và từng tab | Đổi/trao quà vật lý, voucher, tin nhắn/unread, phân công, trả lời đánh giá, CRM | Care browser passed. **Quà điểm thưởng không phải lượt dịch vụ tặng khi mua combo** |
| Báo cáo | `/admin/reports` | Khoảng ngày, lỗi date, dữ liệu trống, tải/xuất nếu có, quyền tài chính | Mới quét admin; cần test chức năng |
| Công/lương vận hành | `/admin/operations`, `/dashboard`, `/attendance`, `/adjustments`, `/payroll`, `/branches`, `/audit` dưới prefix operations | Alias, lọc/duyệt, lock/payroll, vị trí, audit, form và quyền | 6 màn con đã quét admin; chưa chạy operations browser trong phiên này |
| Tài khoản/bảo mật | `/admin/profile`, `/admin/security` | Đổi mật khẩu, step-up/MFA/session trong fixture, trạng thái thiếu config | Đã quét; chưa chạy đầy đủ security browser trong phiên này |
| Nhân viên | `/employee`, `/employee/attendance`, `/appointments`, `/schedule`, `/history`, `/income`, `/account` | Chấm công/GPS giả lập, yêu cầu sửa công, lịch cá nhân, thu nhập, menu mobile, link liệu trình, logout | 6 màn con đã quét; chưa test mọi hành động/máy thật |
| Lỗi và quyền | Route không tồn tại; ID không tồn tại; session hết hạn; role không được phép | 403/404 hữu ích, nút quay lại, không lộ dữ liệu hay loop redirect | Chưa có ma trận đầy đủ |
| Phiên bản cũ | Các URL hỗ trợ `?ui=legacy`; các module flag off dùng template cũ | Chức năng tương đương, link giữa hai UI, không tải double handler | Nhánh scanner đã viết, **chưa chạy quét đầy đủ** |

`/health/*`, file xác minh Google và API không phải trang giao diện; ghi là ngoài ma trận UI, không tính thiếu trang. Route động phải lấy ít nhất một ID tồn tại và một ID không tồn tại.

## 7. Hành trình liên màn hình phải có bằng chứng

| Mã | Vai trò / hành trình | Kiểm chứng dữ liệu cuối |
|---|---|---|
| J01 | Guest xem dịch vụ → đăng nhập → đặt lịch → hồ sơ | Đúng dịch vụ/giờ/khách; một lịch tạo ra; trạng thái hiển thị đúng |
| J02 | Khách mua gói → thanh toán giả → liệu trình | Kích hoạt một lần, số buổi và thời hạn đúng; chưa trả tiền không có lượt khả dụng |
| J03 | Nội bộ bán gói → tặng 2 buổi → khách đặt bằng quà | Đúng item quà, giữ 1 lượt, không tăng tiền, không giảm lượt trả tiền |
| J04 | Khách hủy lịch dùng quà → đặt lại → nội bộ hoàn thành | Hoàn lượt khi hủy, tiêu lượt khi hoàn thành, không tiêu hai lần |
| J05 | Lễ tân tìm/thêm khách → tạo lịch → khách đến → dịch vụ → thu tiền | Các nút phù hợp trạng thái, không cho thao tác lặp/không hợp lệ |
| J06 | Nhân viên nhận lịch → mở đúng khách → xem liệu trình → tặng theo quyền | Không xem/sửa lịch riêng của người khác ngoài chính sách hiện có |
| J07 | Nhân viên đăng ký ca → quản lý duyệt → lịch/chấm công/thu nhập | Đồng bộ sau reload; thông báo thiếu ca/quyền/GPS rõ |
| J08 | Khách chat → nội bộ trả lời/đánh dấu đọc → đổi tài khoản/logout | Đúng hội thoại; badge đồng bộ, không lẫn tin giữa người dùng |
| J09 | Khách nhận điểm/voucher → thanh toán → lịch sử | Voucher/quà vật lý/lượt tặng không bị nhập nhằng, số tiền minh bạch |
| J10 | Lỗi mạng ở submit → kiểm tra lại → tiếp tục | Không mất dữ liệu nhập không cần thiết; không tạo lặp giao dịch/lịch/quà |

Các tương tác gửi tin, thanh toán, trao quà chỉ ở fixture với provider bị tắt/mock. Không gửi thử cho khách thật.

## 8. Sửa và dùng các test mới đúng cách

### `ui-review-pages.playwright.js`

- Base hardcode 5091; role/legacy đọc từ URL browser **trước khi chạy**. Phải `goto .../__qa/ping?role=...&legacy=1` đúng lần chạy.
- Có handler `pageerror` được gắn mỗi lần chạy; dùng session/context mới hoặc tháo listener sau test để không tích lũy qua nhiều run.
- Hiện đợi 450ms sau load: nên bổ sung ready selector/API cụ thể cho trang nhiều dữ liệu để không chụp khi skeleton còn hiện.
- Chuyển hash có thể trả `page.goto()` response `null`; code đã xử lý `response?.status() ?? 200`. Đây là giá trị thay thế của scanner, không phải HTTP 200 thực tế cho một document request mới.
- `overflowing` có thể liệt kê phần tử nằm trong vùng cuộn có chủ ý; chỉ kết luận lỗi sau xem ảnh và điều kiện scroll container.
- `unnamedButtons` chỉ dò text/attribute của button; kiểm accessible name thật trước khi sửa.
- Mở `/profile#edit` hoặc `#password` phải xác nhận section thực sự hiện; URL/hash không phải bằng chứng form đã được render.
- Rà thêm các liên kết nội bộ và 403/404; script hiện chưa click tự động mọi anchor/button.

### `ui-review-gifts.playwright.js`

- Đang fail tại Select gói; làm P0-02 trước.
- Không lấy `.find(p => p.status === 'paid')` làm bằng chứng phiếu vừa tạo khi có nhiều phiếu. Bắt response create hoặc lưu ID mới, rồi theo đúng ID đó qua thanh toán/quà.
- Nếu rerun giữa chừng, fixture có thể còn phiếu/quà đã tạo; reset fixture hoặc tạo khách/gói riêng mỗi run. Không đoán `mathe=1`.
- Slot ngày +3 đang dựa ngày browser; lấy ngày/slot thật từ fixture/API, tránh sai do qua nửa đêm hoặc timezone.
- Route giả lập mất response phải dùng `try/finally` để `unroute`; test fail không được để mock ảnh hưởng run sau.
- Double-click đếm POST phải kiểm cả dữ liệu backend, không chỉ số request.
- Không ghi “staff tặng thành công” nếu chỉ mới mở rồi hủy modal như script hiện tại; bổ sung một lần staff thật sự tạo quà trong fixture.

### `ui-review-controls.playwright.js`

- Chưa chạy lần nào. Không coi file tồn tại là bằng chứng pass.
- Test legacy history link sẽ fail cho đến khi P0-01 gắn `giftLink` vào `history()`.
- Test deep link phụ thuộc đã có appointment từ test quà; nên seed độc lập hoặc ghi dependency rõ.
- Test pagination đang seed đến 34 và mong trang 4 có 4 dòng: dùng fixture sạch hoặc tính theo tổng thực tế.
- Kiểm tên nút đóng drawer theo DOM/accessible name locale thực tế; không cố định “Close” nếu app hiển thị nhãn khác.
- Kết quả `/terms`, `/privacy` cần có HTTP evidence; phần này mới viết, chưa chạy.

## 9. Lệnh khởi động và kiểm thử tham khảo

Chạy tại root `E:\Project\Spa\SPA`. Khi chạy PowerShell, truyền URL có `&` trong dấu nháy. Không ghép chuỗi shell từ dữ liệu người dùng.

```powershell
git status --short
npm --prefix frontend run build
python tests/master_ui_preview.py --port 5091 --all-ui
```

Giữ server trong terminal riêng. Nếu dùng `Start-Process`, chỉ khởi động helper nền với `-WindowStyle Hidden`; log đến thư mục output đã tạo. Không dừng process cổng 5000; đó là app local đang dùng.

```powershell
playwright-cli -s=claude-ui open 'http://127.0.0.1:5091/__qa/ping?role=admin'
playwright-cli -s=claude-ui run-code --filename=tests/ui-review-pages.playwright.js
playwright-cli -s=claude-ui console error
playwright-cli -s=claude-ui requests
```

Lặp với guest/customer/staff/manager/letan; dùng session mới khi cần độc lập và lưu log riêng. Legacy:

```powershell
playwright-cli -s=claude-legacy open 'http://127.0.0.1:5091/__qa/ping?role=admin&legacy=1'
playwright-cli -s=claude-legacy run-code --filename=tests/ui-review-pages.playwright.js
```

Sau khi sửa test theo mục 8:

```powershell
playwright-cli -s=claude-gifts open 'http://127.0.0.1:5091/__qa/ping'
playwright-cli -s=claude-gifts run-code --filename=tests/ui-review-gifts.playwright.js
playwright-cli -s=claude-gifts run-code --filename=tests/ui-review-controls.playwright.js
```

Hồi quy phù hợp với thay đổi:

```powershell
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest tests/test_booking_gifts_reviews.py tests/test_package_sale_channels.py -q
python tests/admin_catalog_browser_check.py
python tests/admin_billing_browser_check.py
python tests/admin_booking_browser_check.py
python tests/admin_people_browser_check.py
python tests/admin_care_browser_check.py
```

Các suite còn lại cần đọc phần thiết lập trước khi chạy: `tests/admin_shell_browser_check.py`, `tests/operations_browser_check.py`, `tests/staff_security_browser_check.py`, `tests/customer-ui-*.playwright.js`, `tests/master-booking.playwright.js`, `tests/master-customer-flow.playwright.js`. Không chạy tất cả bằng wildcard rồi bỏ qua lỗi port/fixture.

Nếu chỉ xem app local HTTPS cổng 5000:

```powershell
playwright-cli -s=local-readonly open https://127.0.0.1:5000/ --config=output/binspa-qa/cli.config.json
```

Cấu hình trên đã có `ignoreHTTPSErrors: true` cho chứng chỉ tự ký local. Đây không phải sửa production và không phải lý do tắt kiểm tra TLS cho app thật. Không chạy bộ test có mutation trên cổng 5000.

## 10. Thứ tự làm và cách ghi kết quả

1. **Lượt A:** P0-00 → P0-01 → P0-02. Sửa các phần dang dở và lỗi test đã thấy trước khi làm đẹp giao diện.
2. **Lượt B:** P0-03. Đóng luồng quà từ bán gói tới sử dụng/hoàn lượt; chốt ma trận quyền hiện có.
3. **Lượt C:** P1-01/02/03 và P1-04. Xác minh các sửa đã viết; xử lý liên kết hỏng. Nội dung policy chờ chủ spa không cản các việc độc lập khác.
4. **Lượt D:** P1-05/06/07. Hoàn thành coverage trang/role/legacy và duyệt visual, chức năng liên màn hình.
5. **Lượt E:** P1-08. Tổng hợp báo cáo và chỉ chạy lại các test bị ảnh hưởng/thực sự cần thiết; không rerun vô hạn các suite không liên quan.
6. P2 đưa vào backlog riêng nếu không đủ phạm vi hoặc cần quyết định nghiệp vụ. Không ghi chúng đã triển khai.

Mỗi lỗi lưu một dòng theo mẫu:

| ID | Role + URL + viewport | Dữ liệu/điều kiện | Cách tái hiện | Mong đợi / thực tế | Root cause | File sửa | Test và kết quả | Ảnh trước/sau | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| Ví dụ UI-001 | admin, package-sales legacy, 390 | Phiếu paid có liệu trình | Mở lịch sử bán gói | Có link tặng / hiện chưa có | Helper chưa gắn vào dòng | `package-sales.js` | Tên test + log | Path PNG | TODO |

Không ghi lỗi đã sửa chỉ vì ảnh after đẹp; phải kiểm lại tương tác gây lỗi và dữ liệu liên quan. Không ghi fail của fixture thành lỗi ứng dụng nếu chưa xác định.

## 11. Điều kiện được tuyên bố hoàn thành

- [ ] Không còn nhãn hỏng hoặc thiếu lối vào quà trên các UI được hỗ trợ.
- [ ] Toàn bộ P0 có bằng chứng pass; test E2E mới không còn timeout ở Select.
- [ ] Quyền admin/manager/staff/letan/customer được kiểm ở cả UI và API; không tự mở rộng quyền.
- [ ] Khách thực sự đặt/giữ/hoàn/tiêu đúng lượt tặng; giá gói và doanh thu không bị thay đổi bởi quà.
- [ ] Test mất phản hồi không tạo lặp trong phạm vi đã cam kết; giới hạn idempotency ghi rõ.
- [ ] Phân trang mobile và deep link có test riêng, không chỉ dựa bộ hồi quy cũ.
- [ ] Mọi route giao diện trong ma trận có trạng thái cụ thể, bao gồm manager/letan và legacy hợp lệ.
- [ ] 360/390/768/1024/1440 px được kiểm cho luồng quan trọng; các trang còn lại có ít nhất desktop/mobile và review ảnh.
- [ ] Không có lỗi JS/network chức năng chưa phân loại; 401 guest, provider bị tắt và trang thiếu cấu hình được giải thích đúng.
- [ ] Liên kết policy có nội dung được duyệt hoặc còn mở được ghi công khai, không lặng lẽ bỏ qua.
- [ ] Báo cáo riêng phần không kiểm được: Safari/iOS/Android thật, bàn phím ảo, GPS thật, in thiết bị thật, email/OTP và thanh toán provider thật.
- [ ] Có danh sách file chỉ thuộc thay đổi mới, kết quả test cuối và ảnh trước/sau; không gộp toàn bộ dirty working tree của người dùng.
- [ ] Không migration, sửa production hoặc deploy ngoài phạm vi được duyệt.

## 12. Prompt ngắn giao cho Claude Code

> Đọc `AGENTS.md` và `plans/2026-10-21-ban-giao-claude-kiem-tra-ui-va-tang-dich-vu.md`. Tiếp tục từ working tree hiện tại, bảo toàn mọi thay đổi có sẵn. Hoàn thành các P0 rồi P1 theo thứ tự trong tài liệu. Chú ý: luồng tặng mới chưa nghiệm thu, legacy có nhãn hỏng và thiếu gắn nút lịch sử, test Select đang timeout; không coi các phần đó là đã xong. Dùng fixture SQLite riêng để kiểm thử mọi thao tác ghi. Không thay schema, cấu hình production hoặc deploy. Với chính sách pháp lý chưa có nội dung, ghi rõ phần cần chủ spa cung cấp nhưng tiếp tục các việc độc lập. Sau mỗi nhóm việc cập nhật bảng trạng thái, test, ảnh và file thay đổi; chỉ kết luận hoàn tất khi có bằng chứng đúng phạm vi.

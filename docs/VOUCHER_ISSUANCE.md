# Voucher chào mừng và tặng thủ công

## Quy tắc hiện hành — xác nhận ngày 24/10/2026

Người dùng tự tạo voucher và quyết định mức giảm, đơn tối thiểu, phạm vi, số lượng và hạn dùng. Không tự tạo mẫu, đổi giá trị hoặc bật/tắt chương trình thật trong lần hoàn thiện này.

- **Hoạt động (`active`) chỉ kiểm soát đổi điểm.** Mẫu tắt hoạt động không xuất hiện trong catalog khách và không đổi bằng điểm được; vẫn tự cấp welcome, nhân viên vẫn tặng được, voucher đã nhận vẫn dùng được theo snapshot/hạn dùng/tồn kho.
- **Dành cho khách hàng mới** nằm ngay trong form tạo/sửa voucher trên React và legacy. Chọn và lưu sẽ cấu hình tự tặng sau OTP, trong cùng transaction với mẫu. Có một mẫu welcome tại một thời điểm; chọn mẫu khác thay chương trình hiện hành, không thu hồi voucher đã cấp. Sửa lại cùng mẫu không dời mốc đăng ký ban đầu. Mẫu welcome cần có hạn dùng.
- Nhân viên có quyền được tặng mọi mẫu voucher giảm tiền/phần trăm còn tồn, bao gồm mẫu welcome và mẫu không hoạt động. Cột `allow_manual_gift` được giữ tương thích schema cũ; không còn là điều kiện chặn tặng. Quà hiện vật không nằm trong luồng tặng voucher.
- Mẫu welcome đang được chương trình chọn không xuất hiện để khách tự đổi điểm. Để dừng tự tặng, bỏ chọn **Dành cho khách hàng mới** rồi lưu hoặc tắt **chương trình**; tắt **hoạt động của mẫu** không dừng tự tặng.
- **Khách hàng → Tặng voucher** có ngay trên từng dòng/thẻ khách và trong **Hồ sơ → Voucher tặng**. Khách pending/bị khóa không nhận quà thủ công. Nếu không có mẫu phù hợp, hiện hướng dẫn và chặn gửi form trống.

Các quy tắc này thay thế điều kiện active/allow_manual_gift và yêu cầu không tặng thủ công mẫu welcome của bản thiết kế 23/10. Không cần migration/schema mới để áp dụng thay đổi này.

## Kết quả hoàn thiện ngày 24/10/2026

- Sửa test nhãn giao diện cũ, thêm hồi quy mẫu inactive nhận welcome, tặng tay và thanh toán; kiểm tra lưu lựa chọn khách mới atomic, rollback khi thiếu hạn dùng và giữ nguyên cutoff khi sửa mẫu.
- Backend: **154 passed, 0 skipped**, chạy toàn bộ `test_loyalty_*.py` trên SQLite và PostgreSQL 17 riêng tại loopback. PostgreSQL test dùng cluster mới, không kết nối database ứng dụng. Sau chỉnh logger, chạy lại bốn test observability: **4 passed**.
- Frontend: **71 passed**, build thành công; Node UI/auth-session và browser được lưu trong `output/voucher-completion-2026-10-24/`. Browser hồi quy 11 nhóm và 3 nhóm bổ sung: form khách mới React/legacy, mẫu inactive nhận OTP, nút tặng ngay danh sách, apply/release, lễ tân mobile và hướng dẫn khi trống. Không lỗi JavaScript hoặc request ngoài lỗi mạng được cố ý mô phỏng ở bài retry.
- Đọc trạng thái môi trường đang chạy: schema voucher `20261023_0025`, welcome đã bật, hai mẫu voucher còn tồn; trang khách và API mẫu trả 200, bundle khách đang phục vụ có nút tặng mới. Đây là kiểm tra chỉ đọc; không thay mẫu, tài khoản hay voucher thật.
- Script legacy đã đổi version để tránh dùng cache cũ. Các thay đổi khác có sẵn trong workspace được giữ nguyên; không deploy hoặc chạy migration mới.

## Theo dõi vận hành

Tìm dòng **`voucher_event {JSON}`** trong log ứng dụng. Logger con `app.voucher` ghi INFO độc lập với cờ observability tổng, dùng chung handler của ứng dụng. JSON chỉ có loại sự kiện, nguồn, thao tác, mã lý do, ID voucher/mẫu, mã request, HTTP status hoặc tên loại lỗi; không ghi token, OTP, email/SĐT, lý do nội bộ, lời nhắn, payload hay câu SQL.

| `event` | Ý nghĩa |
| --- | --- |
| `issued` | Voucher đã được commit; phân theo `source=points_redemption/welcome/staff_gift` |
| `replayed` | Thử lại cùng thao tác đã commit, không cấp thêm |
| `skipped` | Welcome không cấp: `disabled`, `outside_program`, `not_new_registration`, `already_received`, `out_of_stock`, `invalid_template`, `inactive_customer` |
| `rejected` | Từ chối yêu cầu; ví dụ `out_of_stock`, `idempotency_conflict`, `validation_error` |
| `failed` | Lỗi hệ thống/DB, chỉ ghi tên loại lỗi; activation rollback |
| `used`, `cancelled` | Voucher đã thanh toán/thu hồi và commit |

Đếm các sự kiện theo nguồn/lý do để theo dõi phát hành, replay, hết kho và dùng thành công. Sự kiện thành công chỉ xuất sau outer commit; rollback xóa buffer để không báo cấp/dùng giả. Log không thay thế lịch sử DB và cần được lưu theo chính sách log của môi trường triển khai.

## Biên bản triển khai ngày 23/10/2026

Triển khai ngày 23/10/2026 theo kế hoạch bàn giao và thiết kế schema đã được người dùng duyệt. Sau phê duyệt bổ sung "Cho phép sao lưu và chạy migration", đã sao lưu và migrate PostgreSQL đang phục vụ `192.168.1.160:5000` từ `20261021_0024` lên `20261023_0025`. Không deploy hoặc bật chương trình chào mừng.

## Khắc phục lỗi tải danh sách sau triển khai

Trang Tra mã và giao quà lỗi vì mã nguồn mới truy vấn các cột phát hành chưa có trong database `20261021_0024`. Sau khi người dùng cho phép, đã:

- Chạy bốn file migration/concurrency trên database PostgreSQL kiểm thử mới, độc lập, chứa dữ liệu tổng hợp: **24 passed (12 PostgreSQL + 12 SQLite)**. Database kiểm thử đã được xóa; không dùng database ứng dụng để chạy test.
- Tạo backup đầy đủ định dạng custom và kiểm tra đọc được catalog bằng pg_restore: `backups/voucher-before-20261023_0025-20261023-120000.dump` (18.400.774 bytes). Thư mục backups đã được git-ignore; không đưa backup dữ liệu thật vào tài liệu/public artifacts.
- Chạy đúng migration `20261023_0025` với lock timeout 10 giây và statement timeout 120 giây. Migration hoàn tất.
- Đối chiếu toàn bộ cột cũ theo thứ tự ID và SHA-256 trên năm bảng reward, redemption, wallet, point transaction, loyalty config: dữ liệu trước/sau giống nhau. Giữ 3 mẫu và 3 lượt đổi quà; không phát hành voucher mới.
- Gọi lại API trên tiến trình ứng dụng HTTPS đang chạy: redemptions **200 / 3 lượt**, rewards **200 / 3 mẫu**, gift-templates **200 / 0 mẫu được bật tặng**, welcome-config **200 / enabled=false**. Không cần khởi động lại ứng dụng.

Log/biên bản không chứa token hoặc dữ liệu khách: `output/voucher-issuance-2026-10-23/postgres-tests.log`, `live-migration.log`, `live-migration-verification.json`, `live-api-verification.json`.

## Vận hành

1. Sau khi được phép rollout database thật, backup và chạy migration mới `20261023_0025` (nối `20261021_0024`). Không sửa migration cũ. Mẫu cũ được giữ `allow_points_redemption=true`, `allow_manual_gift=false`; không backfill khách cũ vào chương trình.
2. Admin/quản lý vào **Điểm thưởng → Quà và voucher**, tạo mẫu giảm tiền hoặc phần trăm. Nhập mức giảm, trần, đơn tối thiểu, phạm vi, tồn, hạn dùng theo ý muốn. Bỏ **Cho đổi bằng điểm** để cho phép điểm đổi bằng 0. Mọi voucher còn tồn đều tặng được; không phụ thuộc cờ hoạt động.
3. Bật **Dành cho khách hàng mới** trong form mẫu rồi lưu để tự cấp welcome. Có thể chỉnh thời gian/bật tắt riêng ở **Quy tắc và hạng → Voucher chào mừng** (legacy có tab riêng). Mẫu có hạn dùng, không cần đang hoạt động. Database lưu UTC; giao diện nhập giờ Việt Nam, API nhận ISO 8601 kèm múi giờ.
4. Admin/quản lý/lễ tân bấm **Tặng voucher** ở dòng/thẻ khách hoặc mở **Hồ sơ → Voucher tặng**. Kiểm tra đúng người nhận và lịch sử, chọn mẫu, nhập lý do nội bộ, lời nhắn tùy chọn rồi xác nhận. Khách phải đang active.
5. Nếu mất phản hồi, dùng **Thử lại cùng yêu cầu**. Form giữ payload và key trong sessionStorage theo actor/khách, kể cả đóng/mở lại. Không tạo yêu cầu mới chỉ vì phản hồi chậm. Một thao tác mới có chủ đích được phép tặng thêm.
6. Admin/quản lý được thu hồi voucher tặng còn hạn, đang available, với lý do bắt buộc. Không hoàn tồn; không hoàn điểm vì chưa trừ điểm. Voucher reserved/used không thu hồi được.
7. Khi dừng welcome, tắt chương trình hoặc bỏ chọn **Dành cho khách hàng mới**. Tắt hoạt động của mẫu chỉ ngừng đổi điểm. Voucher đã cấp giữ nguyên snapshot/hạn dùng và tiếp tục dùng trong bộ chọn thanh toán hiện có.

Welcome chỉ cấp khi tài khoản **tự đăng ký mới** từ mốc chương trình, sau đó chuyển pending → active bằng OTP thành công. Dấu `customer_otp_registration` chỉ ghi tại `auth_bp.register()` khi tạo tài khoản mới; không ghi lại khi gửi lại OTP hoặc cập nhật tài khoản pending. Hai đường tạo khách nội bộ trong `app/admin/staff_manage_bp.py` (tạo đầy đủ/thêm nhanh) không ghi dấu này. Khách cũ/import/nhân viên tạo không được cấp tự động, kể cả gửi lại OTP. Mỗi makh nhận welcome tối đa một lần suốt đời, kể cả đổi mẫu/bật lại/thu hồi quà cũ.

Chương trình tắt/chưa bắt đầu/kết thúc/mẫu không hợp lệ/hết kho: kích hoạt vẫn thành công và trả lý do skip. Lỗi DB: rollback cả kích hoạt, tồn và voucher; OTP chưa bị tiêu thụ và có thể thử lại. Không tự cấp bù lúc đăng nhập, reset mật khẩu hoặc thanh toán.

## API và quyền

| API | Quyền | Nội dung |
| --- | --- | --- |
| GET `/api/admin/loyalty/gift-templates` | admin/manager/letan | Voucher tiền/phần trăm còn tồn, kể cả inactive/welcome, phân trang/search |
| POST `/api/admin/loyalty/customers/{makh}/voucher-gifts` | admin/manager/letan | Header `Idempotency-Key` bắt buộc; JSON `reward_id`, `reason`, `customer_message` tùy chọn. 201 khi cấp, 200 replay cùng payload, 409 khác payload/hết kho |
| GET cùng URL | admin/manager/letan | Lịch sử phân trang; `issuance_source`, nhóm `status` như loyalty hiện có, `issued_by_staff` |
| POST `/api/admin/loyalty/voucher-gifts/{id}/cancel` | admin/manager | JSON `reason`; 409 nếu trạng thái/hạn không hợp lệ |
| GET/PUT `/api/admin/loyalty/welcome-config` | admin/manager | `enabled`, `reward_id`, `starts_at`, `ends_at`; không tự bật mặc định |
| GET `/api/loyalty/my-rewards` | chính khách | Thêm `issuance_source`, `issued_at`, `customer_message`; không trả lý do nội bộ/actor/payload chống trùng |
| POST `/api/admin/loyalty/rewards`, PUT `…/rewards/{id}` | admin/manager | Thêm boolean `for_new_customers`; lưu mẫu và lựa chọn welcome cùng transaction |

Không nhận mức giảm/hạn/actor/makh trong body tặng. Không gửi email/Zalo/SMS, không gửi hàng loạt, không hạn mức nhân viên/ngày. Kênh thông báo và hạn mức là phạm vi sau. Định nghĩa người mới theo mỗi tài khoản, không cam kết mỗi người thật.

## Dữ liệu và giao dịch

- `LoyaltyReward` thêm hai cờ cho đổi điểm/tặng thủ công; không tạo ví voucher khác.
- `LoyaltyRewardRedemption` thêm nguồn, actor, lý do/lời nhắn, payload chuẩn hóa, once-key và audit thu hồi. Constraint bắt buộc đổi điểm >0; welcome/staff_gift =0, staff_gift có actor/lý do, welcome có khóa unique riêng.
- Phát hành dùng chung `loyalty_service.lock_reward()/issue_reward()` cho tồn, mã và snapshot. Service không commit. Quà không tạo/sửa wallet hoặc ledger.
- Manual khóa actor qua cập nhật cột không phải key, sau đó khách rồi mẫu. Cùng actor/key được tuần tự hóa kể cả payload đổi người nhận. Khóa khách/mẫu tương thích thứ tự redeem. Welcome dùng compare-and-set pending/OTP + khóa khách và unique lifetime key ở DB. Thu hồi khóa cùng dòng voucher như apply.
- Bản đầu không hoàn tồn khi thu hồi. Không sửa hành vi hoàn/hủy giao dịch đã thanh toán hay mở lại voucher used.
- Downgrade từ chối rõ ràng nếu có voucher tặng hoặc mẫu 0 điểm; không xóa dữ liệu để ép rollback. Cách dừng thông thường là tắt phát hành, giữ schema và voucher đã cấp.

## Các file triển khai

- Model/schema: `app/loyalty_models.py`, import trong `app/models.py`, `migrations/versions/20261023_0025_voucher_issuance.py`.
- Service/API: `app/services/voucher_issuance_service.py`, `app/services/loyalty_service.py`, `app/admin/loyalty_manage_bp.py`, `app/routes/loyalty_bp.py`, `app/routes/auth_bp.py`.
- Observability: `app/services/voucher_observability.py`, `tests/test_loyalty_voucher_observability.py`; UI bổ sung: `tests/voucher-admin-actions.playwright.js`.
- React: `frontend/src/admin/care/VoucherGifts.tsx`, `WelcomeVoucher.tsx`, `Loyalty.tsx`, `model.ts`, `frontend/src/admin/booking/Customers.tsx`. Khung hồ sơ co theo viewport; form quà cuộn trong modal trên mobile.
- Legacy/khách: `app/static/js/admin/voucher-gifts.js`, `customers.js`, `loyalty.js`, `app/templates/admin/customers.html`, `loyalty.html`, `app/templates/customer/verify_otp.html`, `app/static/js/customers/loyalty.js`, `auth.js`.
- Kiểm thử: `tests/test_loyalty_voucher_issuance.py`, `test_loyalty_issuance_concurrency.py`, `test_loyalty_issuance_migration.py`, bổ sung `tests/loyalty-ui.test.cjs`, fixture `tests/voucher_issuance_preview.py`, kịch bản `tests/voucher-issuance.playwright.js`, `tests/voucher-template-editors.playwright.js`.

Những file vốn đã có thay đổi chưa commit được giữ nguyên; chỉ bổ sung phần liên quan. Không tự commit/deploy.

## Kiểm thử

- Toàn bộ hồi quy loyalty qua pytest discovery `tests -k loyalty`: **133 passed, 14 skipped**; trước lần bổ sung test tắt chương trình với mẫu đã dừng.
- Các test phát hành/concurrency/migration sau chỉnh sửa cuối: **23 passed, 5 skipped** (SQLite).
- Lần triển khai đầu PostgreSQL bị skip vì chưa có URL test. Trong lần khắc phục lỗi database nêu trên, đã tạo database kiểm thử riêng trên PostgreSQL 17 và chạy bốn file `test_loyalty_issuance_concurrency.py`, `test_loyalty_issuance_migration.py`, `test_loyalty_migration.py`, `test_loyalty_concurrency.py`: **24 passed, không skip (12 PostgreSQL + 12 SQLite)**. URL test chỉ tồn tại trong môi trường subprocess; database tạm đã được xóa sau kiểm thử.
- `npm run test`: **71 passed**; `npm run build`: đạt (còn cảnh báo chunk lớn của bộ UI hiện có).
- Node UI/auth-session: **18 passed**; có kiểm tra nhãn nguồn, không hiển thị trừ 0 điểm, escape lời nhắn, không lộ lý do nội bộ.
- Playwright CLI/Chrome: **11 nhóm hành trình đạt** (8 nhóm trong `browser-tests.log`, 3 nhóm trong `template-browser-tests.log`). React/legacy tặng tiền/phần trăm, mất phản hồi và mở lại/retry cùng key, thu hồi, phân trang/bộ lọc, quyền lễ tân, mẫu chỉ tặng 0 điểm trên cả hai UI, cấu hình welcome, đăng ký/OTP thật trong fixture và xem quà trong tài khoản, voucher tặng trong bộ chọn thanh toán cũ và apply/release. Escape đóng dialog tặng legacy và giữ hồ sơ khách bên dưới. Không lỗi page JavaScript hoặc request lỗi ngoài tình huống mất phản hồi được chủ động giả lập. Legacy còn một cảnh báo deprecation từ thư viện hiện có.
- Đã xem ảnh desktop 1440px, mobile 390px/360px. Sửa khung hồ sơ bị cắt trái khi viewport nhỏ và giới hạn vùng cuộn modal tặng quà; kiểm tra bounding box thực tế vừa viewport. Thêm aria-hidden cho biểu tượng trang OTP để tên nút Xác thực không bị đọc kèm glyph trang trí.
- Ảnh/log: `output/voucher-issuance-2026-10-23/`, gồm `react-gift-desktop.png`, `react-history-360.png`, `react-gift-mobile.png`, `legacy-gift-mobile.png`, `customer-welcome-mobile.png`, `welcome-config-desktop.png`, `otp-welcome.png`, `gift-payment-picker.png` và ảnh hai form tạo mẫu. Kịch bản dùng database riêng, email bị chặn, không thanh toán thật.

Chạy lại giao diện trên fixture riêng:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python tests/voucher_issuance_preview.py
# Terminal khác, fixture phải mới để các assertion số lượng bắt đầu từ 0:
playwright-cli -s=voucher-issuance open http://127.0.0.1:59147/__qa/ping --browser=chrome
playwright-cli -s=voucher-issuance run-code --filename=tests/voucher-issuance.playwright.js
playwright-cli -s=voucher-issuance run-code --filename=tests/voucher-template-editors.playwright.js
```

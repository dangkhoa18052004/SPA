# Giai đoạn 3A — Loyalty & Rewards

Ngày kiểm chứng: 04/10/2026. Thay đổi được thực hiện trong workspace BIN SPA; chưa commit hoặc triển khai lên Render.

## Báo cáo 18 mục

| # | Hạng mục | Kết quả triển khai |
|---|---|---|
| 1 | Source bắt đầu | `f0649da54e369fd81d08cf2cbc5936cd2042e1a5`, đúng source tham chiếu. |
| 2 | Migration | `20261003_0009_loyalty_rewards.py`, revision `20261003_0009`, nối sau head `20261003_0008`. Tạo sáu bảng Loyalty, seed config, thêm ba cột giảm giá/thực trả trên hóa đơn và purchase. Backfill giảm giá bằng 0, payable bằng giá gốc. Giữ nguyên 0007/0008. |
| 3 | Models mới | `LoyaltyWallet`, `LoyaltyConfig`, `LoyaltyPointTransaction`, `LoyaltyRedemptionReservation`, `LoyaltyReward`, `LoyaltyRewardRedemption` trong `app/loyalty_models.py`, được export qua `app.models`. |
| 4 | Config | Admin/Manager chỉnh đơn vị tích điểm, số điểm, giá trị điểm, mức tối thiểu, phần trăm tối đa và bốn cờ earn/redeem cho dịch vụ/gói. Backend quyết định quy đổi; JS đọc kết quả preview. |
| 5 | Wallet | Mỗi khách tối đa một ví, tạo lazy. Có available/reserved/lifetime/version; check constraint ngăn số dư âm. Khóa hàng khách trước khi tạo ví để chống hai request cùng tạo. |
| 6 | Ledger | Signed integer, sáu loại giao dịch, nguồn và reference, staff/lý do/metadata, idempotency unique. Không có API sửa/xóa lịch sử. Helper reversal thêm dòng `refund` đối ứng. |
| 7 | Reservation | `reserved → consumed/released`, một active reservation mỗi target. Giữ điểm trước payment; đóng modal/reload không release. Có nút bỏ sử dụng trước paid. Đã paid không đổi ưu đãi. |
| 8 | Cash | Kiểm tiền nhận theo payable, lưu `ThanhToan.sotien` bằng payable và cash_received riêng; tiền thừa = nhận − payable. Claim payment, consume, earn và commit cùng transaction. |
| 9 | VietQR | QR dùng payable cho dịch vụ và gói. Sinh QR không earn. Payable 0 dùng nút thanh toán bằng điểm, không QR 0đ; payment dịch vụ ghi phương thức `Điểm thưởng`, số tiền 0. |
| 10 | SePay/idempotency | Giữ webhook event/provider transaction unique, khóa payment target, kiểm tiền vào và số tiền. Unique earn/redeem theo invoice/package; duplicate webhook và double cash không ghi thêm điểm. Package callback lỗi dùng savepoint để không commit settlement dở dang. |
| 11 | Package | Giữ `amount` gốc, thêm discount/payable. Pending không earn hoặc activate; paid consume/earn rồi activate treatment như cũ trong một transaction. Session/gift không tích thêm; mixed gift chỉ tích phần invoice trả tiền. |
| 12 | Rewards | Catalog voucher tiền/quà vật lý, tồn kho nullable, hiệu lực nullable, active. Đổi quà khóa ví và stock, trừ điểm/ghi ledger/tạo redemption atomic, snapshot và mã riêng. Voucher reserve/used cho invoice hoặc package; physical gift có bàn giao và staff audit. |
| 13 | Customer UI | Tab Điểm thưởng tại `/profile`: số dư khả dụng/đang giữ/tổng tích/tổng dùng, lịch sử phân trang, catalog, ưu đãi của tôi. Thiếu điểm/hết stock khóa nút đổi. Payment dịch vụ/gói có preview, dùng tối đa, bỏ điểm và chọn voucher. Identity lấy từ JWT. |
| 14 | Admin UI | Menu `/admin/loyalty`, sáu tab tổng quan/quy tắc/khách hàng/lịch sử/quà/lịch sử đổi. Tìm tên/SĐT/email, chi tiết ví, điều chỉnh bắt buộc lý do và staff, CRUD catalog, bàn giao. Staff thanh toán theo quyền hiện có; config/adjust chỉ Admin/Manager. |
| 15 | Billing/receipt | Giữ `tongtien`, purchase `amount` và serialized `total_amount` gốc. Thêm original/reward/loyalty/payable/points_used/points_earned; thống kê doanh thu cộng payable. Receipt dịch vụ/gói hiển thị discount, điểm dùng/tích, thực trả và tiền thừa; ẩn dòng giảm giá 0. In A5 đã kiểm chứng. |
| 16 | Concurrency | Thứ tự khóa target → customer/wallet → reward. UPDATE hàng tồn tại để khóa cả khi ví chưa có; `FOR UPDATE` đọc ví/webhook target. Partial unique một reservation/voucher active trên target; DB unique cho mọi ledger key và redemption key. Kiểm race thật trên SQLite và PostgreSQL. |
| 17 | Tests mới | 34 ca Python Loyalty, 3 ca Node Loyalty và browser Loyalty. Service, API/payment, concurrent workers, migration/backfill và Flask CLI upgrade; bao gồm rollback, config, snapshot, expiry, reversal, ownership, staff audit, full points, cash/QR/packages/rewards và session/gift. |
| 18 | Full regression | 249/249 Python passed, 0 failed/errors/skipped, 451,877 giây; gồm 215 regression cũ và 34 Loyalty mới. 15/15 Node passed. Browser Loyalty/Billing/Gift/Review passed. Gift/Review/notification và các luồng billing hiện có được chạy cùng suite. |

## Quy tắc và transaction

Default ban đầu: `100000đ = 10 điểm`, `1 điểm = 1000đ`, tối thiểu 10 điểm, tối đa 50% sau voucher. Cả bốn cờ earn/redeem dịch vụ/gói mặc định bật. `points_expiry_months = NULL`; GĐ3A không có scheduler hết hạn điểm.

Earn = `floor(payable / earn_amount_unit) × earn_points`. Với default: 350.000đ tích 30 điểm, 400.000đ tích 40 điểm; 0đ không tích điểm. Tiền dùng Decimal/Numeric; chart chuyển sang kiểu JSON số sau khi tổng hợp Decimal.

Thứ tự giảm: giá gốc → voucher → điểm → payable. Giới hạn phần trăm điểm tính trên phần còn lại sau voucher. Khi voucher mới làm reservation hiện tại vượt cap, backend từ chối và rollback; người dùng giảm/bỏ điểm rồi áp voucher. Reservation đã lưu giữ giá trị giảm để tiếp tục payment khi config đổi.

Invariant của ví:

```text
available_points + reserved_points = SUM(ledger.points_delta)
```

Reserve chỉ chuyển available sang reserved, chưa ghi dòng trừ ledger. Xác nhận paid mới consume reservation, ghi redeem và earn. Toàn bộ thay đổi số dư ở `loyalty_service.py`; service không tự commit. Route/provider sở hữu transaction payment và rollback đồng bộ khi lỗi.

Earn/redeem hóa đơn có key `loyalty:earn:invoice:<mahd>` và `loyalty:redeem:invoice:<mahd>`; purchase dùng `...:package:<id>`. Đổi quà và adjustment yêu cầu `Idempotency-Key` hoặc `idempotency_key`; retry cùng key trả giao dịch cũ, đổi payload sang quà/điểm khác bị từ chối.

`reverse_loyalty_for_payment(kind, id)` khôi phục điểm đã redeem trước, rồi thu hồi earned bằng ledger refund; gọi lặp không đảo thêm lần nữa. Caller phải commit/rollback cùng nghiệp vụ hoàn tiền. Nếu không đủ điểm khả dụng để thu hồi earned, helper từ chối để không phát sinh ví âm. Không bổ sung refund UI trong GĐ3A.

Endpoint customer `pay-online` giả lập trước đây trả 410 vì số tiền customer tự gửi không xác nhận chuyển khoản. UI dùng VietQR/SePay hoặc thanh toán tại quầy. Provider MoMo đã có trong source cũng dùng payable và cùng finalize helper để mọi điểm xác nhận payment thống nhất; không thêm phương thức thanh toán mới.

## API chính

- Customer: `GET /api/loyalty/me`, `/me/transactions`, `/rewards`, `/my-rewards`; `POST /api/loyalty/rewards/<id>/redeem`.
- Payment target: `GET/POST/DELETE <base>/loyalty`, `POST <base>/loyalty/preview`, `POST/DELETE <base>/reward`, `POST <base>/pay-points`.
- Bases: `/api/admin/invoices/<id>`, `/api/payment/invoices/<id>`, `/api/admin/packages/purchases/<id>`, `/api/packages/purchases/<id>`.
- Admin: `/api/admin/loyalty/{overview,config,customers,transactions,rewards,redemptions}`, chi tiết khách/adjust, reward CRUD và redemption fulfill.

Preview không INSERT ví/config/reservation/ledger. Thanh toán đọc lại target dưới khóa và kiểm ownership/trạng thái; không tin makh, giá gốc hoặc discount client gửi.

## Kiểm thử

| Nhóm | Kết quả |
|---|---|
| Python full suite, với PostgreSQL cô lập cho concurrency/migration | **249 passed, 0 failed, 0 errors, 0 skipped**, 451,877 giây. |
| Concurrency + migration SQLite/PostgreSQL riêng | 12 passed, 0 failed, 0 skipped. |
| API Loyalty, gồm session/gift/mixed | 14 passed. |
| Migration CLI + notification + date-filter sau sửa test isolation | 27 passed; 2 PostgreSQL cases skipped ở lần SQLite này và được chạy trong full PostgreSQL suite. |
| Node UI | 15 passed: 12 regression hiện có và 3 Loyalty mới. |
| Edge browser Loyalty | PASS: admin config/adjust, voucher+points preview/apply, invoice/package resume, QR/cash/payable, receipt, customer wallet/rewards, mobile. |
| Edge billing regression | PASS: appointment completion/payment resume, cash, package coverage, staff completion, post-care mock; năm viewport; receipt dịch vụ/gói vừa một trang A5. |
| Edge Gift/Review regression | PASS: gift selection/booking, review CRUD/reply/public reviews; năm viewport. |

Lệnh kiểm chứng tái lập:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest tests -q --disable-warnings
python tests/loyalty_postgres_check.py --full
node tests/loyalty-ui.test.cjs
python tests/loyalty_browser_check.py
python tests/billing_browser_check.py
python tests/booking_gifts_reviews_browser.py
```

PostgreSQL helper yêu cầu PostgreSQL binaries (hoặc `POSTGRES_BIN`), khởi tạo cluster tạm chỉ bind localhost, chọn port ngẫu nhiên và dừng trong finally. Concurrency/migration cũng hỗ trợ `TEST_LOYALTY_POSTGRES_URL` dành riêng cho test; tạo/drop schema riêng. Helper không dùng `DATABASE_URL` của ứng dụng. Browser dùng SQLite fixture và email/payment mock; không gửi thông báo hay giao dịch thật. Artifact/log/screenshot được giữ trong các thư mục `tests/*.tmp` đã gitignore.

Kết quả cuối: `tests/loyalty-postgres-32001df672814243bd27bdf8a4b9dea0.tmp/results.xml`. Cluster PostgreSQL tạm đã dừng. Screenshot Loyalty cuối trong `tests/loyalty-browser-50919.tmp`; billing trong `tests/billing-preview.tmp`; Gift/Review trong `tests/booking-gifts-reviews-preview.tmp`. Alembic heads xác nhận duy nhất `20261003_0009`; kiểm tra cú pháp Python và `git diff --check` pass. Suite còn warning deprecation từ các API/dependency hiện có.

Lần full regression trước phát hiện một fixture ngày cũ đặt cố định 05/10/2026 bị trùng ngày mai khi chạy qua nửa đêm 04/10; đã đổi ngày ranh giới sang `today + 3 days` và lấy range từ fixture. Test migration CLI mới cũng được cô lập logging để Alembic `fileConfig` không tắt logger của các test notification chạy sau. Hai sửa chữa này chỉ ở test; không thay nghiệp vụ appointment hoặc notification.

## Migration khi triển khai

Đã thử `flask db upgrade` từ 0008 lên 0009 trên SQLite và PostgreSQL test; migration giữ dữ liệu cũ và backfill đúng. Production/Render chưa chạy migration, không reset database và không cần secret mới.

Trong quy trình deploy hiện có, chạy:

```text
flask --app run.py db upgrade
```

Không thay Gift source_type, migration 0007/0008 hoặc notification worker. Phạm vi kết thúc ở GĐ3A, không có payroll, commission, GPS, chuyển điểm hoặc rút điểm ra tiền.

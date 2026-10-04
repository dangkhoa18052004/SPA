# Tách bán gói trên website và tại quầy

Gói còn hoạt động có thể mở bán riêng trên website hoặc tại quầy. Tắt bán web không ngăn nhân viên bán tại quầy; các cấu hình bán chỉ kiểm soát giao dịch mua mới.

## Model và migration

- Giữ `GoiDichVu.active`.
- Thêm `customer_sale_enabled` và `staff_sale_enabled`: boolean, NOT NULL, mặc định `true` cho gói mới.
- Migration mới: `20261004_0011_package_sale_channels.py`, nối sau Alembic head thực tế `20261004_0010`.
- Backfill cả hai cờ bằng `active`: gói active tiếp tục bán ở hai kênh; gói inactive giữ cả hai kênh đóng.
- Upgrade chỉ ADD COLUMN và UPDATE hai cột mới. Không sửa migration cũ, không tạo lại bảng, không xóa purchase/treatment/gift/usage.
- `serialize_package()` trả cả ba cờ. API tạo/sửa chỉ nhận boolean JSON, từ chối chuỗi, số 0/1 và null. Khi sửa mà bỏ qua các cờ, giữ cấu hình đã lưu.

| Hoạt động | Website | Tại quầy | Nhãn quản lý |
| --- | --- | --- | --- |
| Có | Có | Có | Web + Tại quầy |
| Có | Không | Có | Chỉ bán tại quầy |
| Có | Có | Không | Chỉ bán online |
| Có | Không | Không | Ngừng bán |
| Không | Bất kỳ | Bất kỳ | Ngừng hoạt động |

## Backend và phân quyền

`create_purchase(package_id, customer_id, method, *, sale_channel='customer')` chỉ nhận `customer` hoặc `staff`. Hàm giữ row lock, kiểm tra `active`, cờ của kênh tương ứng và dịch vụ còn hoạt động trước khi tạo purchase.

| Endpoint | Điều kiện / quyền |
| --- | --- |
| `GET /api/packages` | `active=true AND customer_sale_enabled=true` |
| `/packages/<id>`, `GET /api/packages/<id>` | Cùng điều kiện customer; gói ẩn trả 404 |
| `POST /api/packages/<id>/purchase` | Customer identity; route cố định `sale_channel='customer'` |
| `GET /api/admin/package-sales/packages` | `package_sales_required`; `active=true AND staff_sale_enabled=true` |
| `POST /api/admin/package-sales` | Route cố định `sale_channel='staff'`; giữ `created_by_staff` |
| Tạo/sửa package | Giữ quyền admin/manager hiện tại |

Customer gửi `sale_channel='staff'` hoặc `created_by_staff` vẫn không vượt được kiểm tra kênh customer. Staff sales giữ quyền admin/manager/letan và yêu cầu tài khoản còn hoạt động; customer và KTV không được bán, lễ tân không được đổi cấu hình gói.

Danh sách tại quầy hỗ trợ tìm theo tên, mã số hoặc `#<mã>`, không lọc theo cờ website.

## Giao diện

Form tạo/sửa có ba lựa chọn rõ ràng: cho phép bán trên website, cho phép nhân viên bán tại quầy, gói đang hoạt động. Mặc định mở hai kênh khi tạo; sửa tải lại đúng giá trị đã lưu. Phần giải thích nêu rõ lưu trữ gói không hủy quyền sử dụng liệu trình đã mua.

Danh sách và trang chi tiết quản lý có badge theo năm trạng thái và bộ lọc tương ứng. Badge xuống dòng trên màn hình nhỏ. Màn hình bán gói tải endpoint staff riêng, có tìm kiếm theo tên/mã, và hiển thị badge “Chỉ bán tại quầy” trong lựa chọn và bản xem trước.

## Thanh toán và liệu trình cũ

Giữ nguyên logic cash, VietQR, xác nhận thanh toán, activation, loyalty và notification. Purchase vẫn snapshot tên, giá, dịch vụ, số buổi, giá trị mỗi buổi và thời hạn. Việc thay đổi hoặc lưu trữ gói sau khi tạo purchase không đổi snapshot; xác nhận thanh toán vẫn kích hoạt theo snapshot.

Không thêm kiểm tra sales flags hoặc `package.active` vào `is_treatment_item_usable()`, gift, booking, reserve/release/consume. Liệu trình cũ vẫn hiển thị, đặt lịch, dùng buổi còn lại và nhận dịch vụ tặng khi gói tắt một/hai kênh hoặc ngừng hoạt động. `DichVu.active=false` vẫn chặn bán và được xử lý theo logic usability hiện có.

## Kiểm thử

- `tests/test_package_sale_channels.py`: tám tổ hợp trạng thái; listing/detail/purchase; giả mạo kênh; tìm tại quầy; quyền; validation JSON/multipart; mặc định và lưu lại cấu hình; cash/VietQR sau lưu trữ; snapshot; liệu trình/gift đặt lịch, release và consume.
- `tests/test_package_sale_channels_migration.py`: dữ liệu active/inactive, mặc định và NOT NULL, bảo toàn purchase/treatment/gift/usage, CLI upgrade từ head cũ và lặp upgrade; PostgreSQL SQL additive và một Alembic head.
- Hai kiểm thử migration cũ được cập nhật để hỗ trợ head mới: fixture loyalty bổ sung bảng package legacy; kiểm thử booking xác nhận revision cũ vẫn thuộc lịch sử migration.
- `tests/package_sale_channels_browser.py`: Chromium thật, database test trong bộ nhớ, lưu/reload form, badge quản lý/chi tiết/mobile 390px, gói ẩn khỏi customer, tìm và xem trước tại quầy, cash và webhook VietQR giả lập kích hoạt liệu trình; không phát sinh JavaScript error.
- Ảnh giao diện: `tests/runtime_phase4_sale_channels/` (artifact local, bỏ qua trong Git).

Chạy Python regression:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider --disable-warnings tests
```

Kiểm thử PostgreSQL tùy chọn dùng `TEST_LOYALTY_POSTGRES_URL` và tạo schema tạm riêng, không dùng bảng ứng dụng hiện có. Đã chạy migration trên cả SQLite và PostgreSQL local.

Kết quả xác minh ngày 04/10/2026:

- Full Python regression: 341 pass; một assertion cũ yêu cầu `0010` vẫn là head thất bại. Assertion đã được sửa để kiểm tra revision nằm trong lịch sử migration và rerun thành công cùng năm kiểm thử trang/static asset (6 pass). Vì full run bắt đầu trước khi sửa assertion, báo cáo của lần chạy đó vẫn ghi 1 failed; toàn bộ 342 trường hợp của mã cuối đã được xác minh qua full run và rerun.
- 57 kiểm thử API/business mới pass; migration mới và regression migration loyalty trên cả SQLite/PostgreSQL: 9 pass.
- JavaScript regression: 20 pass.
- Chromium desktop và mobile 390px: pass, bao gồm lưu/reload flags và cash/VietQR activation.
- `node --check` cho ba file JavaScript thay đổi và `git diff --check`: pass.

Chạy toàn bộ JavaScript regression trong một tiến trình (không cần spawn subprocess Node trong sandbox):

```powershell
node -e "for (const file of require('node:fs').readdirSync('tests').filter(f => f.endsWith('.test.cjs'))) require('./tests/' + file)"
```

Chạy kiểm thử trình duyệt:

```powershell
python tests/package_sale_channels_browser.py
```

## Áp dụng migration

```sh
flask --app wsgi db upgrade
```

Database PostgreSQL local đã nâng từ `20261004_0010` lên `20261004_0011`. Trước/sau nâng cấp giữ nguyên: 5 package, 5 purchase, 5 treatment, 6 treatment item, 8 usage; backfill cả hai cờ khớp `active` ở mọi gói cũ. Chưa chạy upgrade trên Neon production.

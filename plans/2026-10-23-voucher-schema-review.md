# Thiết kế cụ thể để duyệt: voucher chào mừng và tặng thủ công

## Bổ sung nghiệp vụ đã xác nhận ngày 24/10/2026

Đã hoàn thiện trên schema voucher hiện có, không thêm/sửa migration:

- `active=false` chỉ tắt đổi điểm. Welcome và tặng thủ công vẫn cấp được, voucher nhận rồi vẫn dùng được theo snapshot/hạn/trạng thái.
- Form tạo/sửa voucher có **Dành cho khách hàng mới** (`for_new_customers` trên API admin). Lựa chọn này cập nhật singleton welcome và mẫu cùng transaction, chỉ một mẫu tại một thời điểm, không dời mốc khi sửa cùng mẫu và không cấp lại cho người đã nhận.
- Tất cả voucher tiền/phần trăm còn tồn đều có thể tặng bởi admin/manager/lễ tân, kể cả mẫu welcome/inactive. `allow_manual_gift` giữ trong schema để tương thích nhưng không chặn phát hành thủ công.
- Không tự kích hoạt mẫu hoặc thay giá trị quà khi bật welcome. Giá trị, đơn tối thiểu, phạm vi và hạn dùng do người dùng tự tạo theo ý muốn.
- Bổ sung log vận hành sau commit và nút tặng ở danh sách/hồ sơ React + legacy. Hồi quy SQLite/PostgreSQL riêng **154 passed, không skip**; kết quả chi tiết tại [docs/VOUCHER_ISSUANCE.md](../docs/VOUCHER_ISSUANCE.md).

Phần bên dưới là thiết kế và biên bản ngày 23/10; quy tắc ngày 24/10 này được ưu tiên khi có khác biệt. Môi trường đang chạy đã được đọc lại: welcome hiện bật; không thay đổi database/cấu hình thật trong lần hoàn thiện này.

Ngày: 23/10/2026. Người dùng đã duyệt thiết kế và các mặc định trong phiên làm việc. Phạm vi duyệt: mã model, migration mới và chạy migration trên database kiểm thử riêng; không bao gồm database thật, production hoặc deploy. Kết quả triển khai/kiểm thử: `docs/VOUCHER_ISSUANCE.md`.

Phê duyệt bổ sung cùng ngày, khi xử lý lỗi trang Tra mã và giao quà: người dùng xác nhận "Cho phép sao lưu và chạy migration" trên PostgreSQL đang phục vụ `192.168.1.160:5000`. Đã backup đầy đủ, migrate lên `20261023_0025`, xác minh dữ liệu cũ giữ nguyên và các API tải danh sách trả 200. Welcome vẫn tắt; không deploy.

## Schema

- Alembic revision mới `20261023_0025`, nối head hiện tại `20261021_0024`; không sửa migration cũ.
- `loyalty_reward`: thêm `allow_points_redemption` boolean NOT NULL default true và `allow_manual_gift` boolean NOT NULL default false. Constraint giữ nguyên các điều kiện cũ, thay điều kiện điểm bằng `points_cost >= 0 AND (NOT allow_points_redemption OR points_cost > 0)`. Chỉ voucher được phép tặng thủ công.
- `loyalty_reward_redemption`: thêm `issuance_source` NOT NULL default `points_redemption`; `issued_by_staff` FK nhanvien; `gift_reason` text; `customer_message` string(1000); `welcome_once_key` string(80) UNIQUE nullable; `issuance_payload_json` JSON nullable để so payload chống trùng; `cancelled_by_staff` FK nhanvien, `cancelled_at` datetime, `cancel_reason` text. Index lịch sử `(makh, issuance_source, redeemed_at)`. Giữ unique code, idempotency và index reserved hiện có.
- Constraint nguồn: points_redemption phải points_spent > 0; welcome/staff_gift phải points_spent = 0. staff_gift bắt buộc actor và lý do; welcome bắt buộc once-key, nguồn khác once-key NULL. Voucher quà vẫn dùng snapshot và vòng đời thanh toán cũ.
- Bảng `welcome_voucher_config`: singleton id=1, enabled boolean default false, reward_id FK loyalty_reward nullable, starts_at/ends_at UTC datetime nullable, updated_by_staff FK nhanvien nullable, updated_at UTC. Check khoảng thời gian; nếu bật cần reward và starts_at. Service kiểm tra mẫu active, loại voucher và validity_days > 0.
- Bảng `customer_otp_registration`: makh PK/FK khachhang, registered_at UTC NOT NULL. Chỉ tạo khi tự đăng ký tài khoản mới; không backfill. Cần bảng này vì các đường tạo khách nội bộ/import không có dấu nguồn đăng ký; chỉ dựa vào ngaytao và pending không phân biệt được. Hook OTP yêu cầu cả dấu này và ngaytao từ mốc chương trình.
- Downgrade kiểm tra trước, từ chối nếu có voucher quà hoặc mẫu 0 điểm; không xóa dữ liệu nghiệp vụ để ép downgrade. SQLite dùng batch_alter_table, PostgreSQL dùng constraint/FK tương thích.

## Quy tắc triển khai đề nghị

- Welcome khi tự đăng ký và kích hoạt OTP lần đầu; một lần suốt đời makh. Đổi mẫu/bật lại không cấp lại. Chương trình tắt mặc định, chưa tạo mẫu hoặc hardcode giá trị ưu đãi.
- Admin/manager/letan được tặng; admin/manager được cấu hình và thu hồi. Không mở quyền cho staff.
- Chỉ cấp vào tài khoản, không email/Zalo/SMS, không cấp bù khách cũ, không hạn mức nhân viên trong bản đầu.
- Manual cần header Idempotency-Key và payload chuẩn hóa, lấy actor từ phiên. Khóa actor để tuần tự retry cùng key, khóa khách rồi mẫu để dùng chung tồn với đổi điểm. Welcome khóa khách và unique once-key tại DB. Thu hồi khóa voucher như apply; không hoàn tồn.
- Service không commit; OTP activation và phát hành cùng transaction. Skip nghiệp vụ vẫn kích hoạt; lỗi DB rollback cả hai.
- Các thay đổi chưa commit đang có được giữ nguyên. Kiểm thử chỉ SQLite/PostgreSQL riêng, PostgreSQL tùy có TEST_LOYALTY_POSTGRES_URL.

## Quyết định còn mở

Giá trị quà, đơn tối thiểu, phạm vi và hạn dùng thực tế được quản lý nhập sau nghiệm thu. Không bật production trong công việc này.

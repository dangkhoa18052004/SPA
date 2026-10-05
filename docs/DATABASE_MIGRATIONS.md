# Cài database mới và nâng cấp database cũ

## Database mới (rỗng)

```bash
flask db upgrade
python create_admin.py
```

Revision gốc `f3b12dbde06b` tạo các bảng nền (khách hàng, nhân viên, dịch vụ, lịch hẹn,
hóa đơn, thanh toán, ca làm, lương, chat). Các migration sau thêm phần còn lại tới head.
Không dùng `db.create_all()` cho database thật: nó bỏ qua bảng `alembic_version`, khiến
lần `flask db upgrade` kế tiếp cố tạo lại bảng đã có.

## Database đã có Alembic (`alembic_version` tồn tại)

Sao lưu, rồi chạy `flask db upgrade`. Baseline không chạy DDL khi các bảng gốc đã tồn tại.

## Database cũ chưa có `alembic_version`

Ví dụ database khôi phục từ `CSDL.sql` hoặc tạo bằng `db.create_all()`.

1. Sao lưu database.
2. Nhận diện revision (chỉ đọc schema):

   ```bash
   python scripts/detect_db_revision.py --url "$DATABASE_URL"
   ```

3. Chạy đúng các lệnh script in ra, thường là:

   ```bash
   flask db stamp <revision>
   flask db upgrade
   ```

Script so dấu hiệu của từng migration (bảng/cột mà migration đó thêm) theo thứ tự và dừng ở
dấu hiệu đầu tiên còn thiếu. Nếu kết quả là "Không nhận diện được", dừng lại và kiểm tra tay.
Khi thêm migration mới, bổ sung dấu hiệu tương ứng vào `MARKERS` trong script.

## Rollback

`flask db downgrade <revision>` hoạt động cho các migration bổ sung. Downgrade về trước
baseline không xóa bảng gốc để tránh mất dữ liệu vận hành; muốn dựng lại database thử nghiệm
thì xóa database đó rồi `flask db upgrade`.

## Kiểm thử

- `pytest tests/test_fresh_migration.py`: database rỗng → head khớp model; database cũ được
  nhận diện, stamp và nâng cấp giữ dữ liệu; downgrade/upgrade lại.
- Đặt `TEST_LOYALTY_POSTGRES_URL` (tài khoản có quyền `CREATE DATABASE`) để chạy thêm trên
  PostgreSQL thử nghiệm.

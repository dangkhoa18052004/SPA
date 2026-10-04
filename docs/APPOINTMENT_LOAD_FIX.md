# Sửa trang quản lý lịch hẹn không tải dữ liệu — 04/10/2026

Database PostgreSQL local đang ở `20261003_0009`, trong khi model `LichHen` đã có `booking_source` và `created_by_staff` của migration `20261004_0010`. Hai cột chưa tồn tại khiến truy vấn ORM của API lịch hẹn trả 500; frontend hiển thị “Không thể tải danh sách lịch hẹn”.

Đã áp dụng migration có sẵn bằng `python -m flask --app run db upgrade`, nâng `0009 → 0010`. Migration chỉ thêm hai cột audit và foreign key người tạo; không reset database, seed dữ liệu hoặc thay logic đặt lịch.

Đã lấy số lượng và SHA-256 của các trường lịch hẹn cũ theo thứ tự `malh` trước/sau: **66 lịch hẹn**, dữ liệu cũ khớp hoàn toàn. Các lịch cũ có nguồn `legacy`, `created_by_staff` null.

Kết quả xác minh trên database cấu hình thực tế:

| Kiểm tra | Kết quả |
| --- | --- |
| GET `/api/admin/appointments` | Trước 500, sau 200 |
| GET `/api/admin/appointments/statistics` | 200 |
| GET `/api/admin/appointments/<malh>` | 200 |
| GET `/api/admin/appointments/customers/<makh>/treatments` | 200 |
| Edge: trang quản lý lịch hẹn | Tải 66 lịch, trang đầu 10 dòng, thống kê đúng |
| Edge: lỗi JavaScript | 0 |
| Test migration | 3 passed, 2 PostgreSQL tests skipped vì chưa cấu hình URL test |

Kiểm tra browser chỉ đọc database local, không đặt/hủy lịch, không gửi email hay tạo giao dịch. Database ở deployment khác chưa được truy cập trong lần sửa này; deployment đó cần áp dụng cùng migration nếu schema vẫn ở `0009`.

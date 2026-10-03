# Kết quả debug email post-care ngày 03/10/2026

Source kiểm tra: commit `ba0b02d` và các thay đổi hiện tại trong workspace.
Thời gian trong bảng là UTC theo DB; giờ Việt Nam = UTC + 7.

## Bằng chứng trước sửa

DB PostgreSQL thật có 6 post-care job sent và 1 pending. Job `id=15`,
`malh=63`, `type=post_care`, `status=pending`,
`scheduled_at=2026-10-03 11:05:26.068526`, `attempts=0`, `max_attempts=3`,
`sent_at=null`, `last_error=''`, `unique_key=appointment:63:postcare`.
Job đã đến hạn. Kiểm tra process Windows cho thấy web đang chạy nhưng không có
process `notification-worker`. `RESEND_API_KEY` có cấu hình (không in giá trị).

Nguyên nhân được xác nhận ở local: web tạo job đúng nhưng không có worker lấy job.
`python run.py` không chạy worker; repo chưa có launcher web + worker hoặc
Render worker configuration. Chưa truy cập được runtime Render để kết luận về
process production.

## Test trên DB thật và Resend thật

Dùng inbox do người dùng cung cấp (`d***@gmail.com`), tạo lịch được đánh dấu
`[EMAIL SMOKE TEST]` là #64. API confirm và complete đều trả HTTP 200 trước sửa.
Lịch completed, chưa tạo hóa đơn, có đúng một post-care job.

| Field | Sau complete, trước worker | Sau worker |
|---|---|---|
| id | 17 | 17 |
| malh | 64 | 64 |
| type | post_care | post_care |
| status | pending | sent |
| scheduled_at | 2026-10-03 11:19:46.332640 | Giữ nguyên |
| attempts | 0 | 1 |
| max_attempts | 3 | 3 |
| sent_at | null | 2026-10-03 11:27:34.300445 |
| last_error | null | null |
| unique_key | appointment:64:postcare | Giữ nguyên |

Chạy launcher thật trên cổng 5011: `python run_dev.py --appointment-id 64`.
Worker startup báo key configured=yes, claim job → processing → gửi Resend → sent.
Provider trả id `01a10184-fbc6-7ae5-bf9a-f074ca5a54db`, kết quả
`sent=1 failed=0 cancelled=0`. Người dùng đã xác nhận nhận được email
`Bin Spa - Dặn dò sau buổi chăm sóc` trong hộp thư thật.

Complete lặp thêm hai lần đều HTTP 200, count post-care vẫn 1. Restart worker
riêng cho lịch #64, qua nhiều chu kỳ vẫn `attempts=1`, `status=sent`, cùng sent_at;
không gửi lại. Flask reloader có reload web nhưng chỉ một worker được tạo.
Ctrl+C dừng worker và các process web/reloader do launcher tạo; các process web
đã chạy trước đó không bị dừng. Worker thử được dừng sau kiểm thử.

Không xử lý job #63 hoặc các review job của lịch khác trong lần gửi thử.
Lịch thử #64 giữ lại để đối chiếu; không tạo hóa đơn hoặc thu tiền.

## Thay đổi

- `run_dev.py`: supervisor chạy web và worker thành process riêng; kiểm tra key,
  dừng cả hai khi Ctrl+C hoặc một process kết thúc; filter lịch thử tùy chọn.
- `render.yaml`: web và Background Worker riêng, chung environment group,
  giữ database hiện tại. Worker chỉ cài dependencies, không migrate/reset DB.
- `app/services/notification_service.py`: startup kiểm tra key, log processing/
  sent/failure có mã lịch và recipient được che, filter kiểm thử, bỏ qua email blank.
- `app/services/email_service.py`: đọc API key hiện tại của process, trả provider id
  cho worker nhưng giữ bool mặc định, lưu lỗi HTTP/provider có che secret.
- `app/services/appointment_service.py`: bỏ helper completed-email bằng thread
  không có caller. Giữ helper xác nhận đặt lịch đang được sử dụng.
- `README.md`, `docs/NOTIFICATION_WORKER.md`: cách chạy và cấu hình vận hành.
- Test runtime, transport, transaction rollback, no-email, retry và launcher.

Giữ transaction complete + consume + enqueue, idempotency key, retry policy,
review +2 giờ, payment/package flow và cột thanh toán đang được ẩn.

## Vận hành

Kiểm thử: 70 test notification/care/appointment liên quan và 3 test launcher pass;
hồi quy toàn bộ cuối cùng **186 passed**, không có test thất bại. Bao gồm Resend
HTTP 403 → last_error/retry → sent, email null/blank, invoice chưa tạo/chưa trả,
package consume một lần, rollback transaction khi enqueue lỗi, worker thiếu key
và không gửi lại job sent sau restart. Lỗi provider được mô phỏng trong test;
test gửi mail và nhận inbox #64 dùng Resend thật như ghi ở trên.

Local: dùng `python run_dev.py` thay cho chạy riêng `python run.py`.
Render: áp dụng cấu hình Background Worker theo `docs/NOTIFICATION_WORKER.md`.
Blueprint đã thêm vào repo; chưa deploy hoặc xác minh Dashboard Render.
Vì vậy kết quả đã chứng minh luồng local gửi email thật; không khẳng định
worker production đang chạy.

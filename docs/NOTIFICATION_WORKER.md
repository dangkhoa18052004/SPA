# Email tự động sau hoàn thành lịch hẹn

Luồng duy nhất: endpoint `/api/admin/appointments/<malh>/complete` →
`update_appointment_status()` → consume lượt gói và enqueue post-care trong cùng
transaction → worker gửi Resend sau commit. Hóa đơn/thanh toán không kích hoạt email.

## Local Windows

Kích hoạt venv, cấu hình `.env`, rồi chạy từ thư mục dự án:

```powershell
python run.py
```

`python run.py` tự gọi launcher, chạy `python run.py --web-only` và
`python -m flask --app wsgi:app notification-worker --interval 15` thành hai process
riêng. Worker không được khởi động trong `create_app()` hoặc Flask reloader.
Ctrl+C dừng cả web và worker; một process thoát thì launcher dừng process còn lại.
Không cần mở terminal hoặc gõ lệnh gửi mail riêng sau mỗi lần hoàn thành lịch hẹn.
`python run_dev.py` vẫn là launcher tương đương, có thêm tùy chọn giới hạn lịch thử.
Không chạy launcher thứ hai nếu web đã chiếm cổng. Nếu đã chạy web riêng:

```powershell
python -m flask --app wsgi:app notification-worker --interval 15
```

Worker in `RESEND_API_KEY configured: yes/no` và dừng rõ ràng nếu thiếu key.
Không in giá trị secret. Post-care gửi khi đến hạn trong chu kỳ kế tiếp;
backlog và thời gian phản hồi Resend có thể làm tăng thời gian chờ.

## Render

`render.yaml` khai báo web và Background Worker độc lập, dùng chung environment
group `bin-spa-production`. Tạo group này bằng **các giá trị hiện có của web**:
`DATABASE_URL`, `RESEND_API_KEY`, `SECRET_KEY`, `JWT_SECRET_KEY`, `SEPAY_API_KEY`,
và toàn bộ cấu hình production liên quan (VietQR, callback URLs, upload, admin ban đầu).
Không tạo database mới; không sinh lại secret đang dùng. Sender
`noreply@binspa.id.vn` phải được xác minh trong Resend.

Nếu web hiện tại được quản lý thủ công, giữ web hiện tại và tạo riêng Background
Worker từ cùng repo/branch, build `pip install -r requirements.txt`, start:

```text
python -m flask --app wsgi:app notification-worker --interval 15
```

Link cùng environment group vào cả hai. Chỉ dùng Blueprint để quản lý web khi đã
đối chiếu tên service trong YAML với web hiện tại; tránh tạo thêm web ngoài ý muốn.
Worker không chạy `build.sh`, migrate hoặc `create_admin.py`. Build script của web
không thay thế worker. File cấu hình trong repo chưa chứng minh service Render đang chạy;
cần kiểm tra Dashboard/Logs sau deploy.

Tài liệu chính thức: [Background Workers](https://render.com/docs/background-workers),
[Blueprint Specification](https://render.com/docs/blueprint-spec),
[Environment Variables](https://render.com/docs/configure-environment-variables).

## Kiểm tra email thật

1. Dùng khách có email do người kiểm thử kiểm soát. Tạo lịch thử được đánh dấu rõ,
   xác nhận rồi hoàn thành qua endpoint hiện có.
2. Query `notificationjob` theo `malh` để ghi lại `id`, `type`, `status`,
   `scheduled_at`, `attempts`, `max_attempts`, `sent_at`, `last_error`, `unique_key`.
3. Để chỉ xử lý lịch thử và giữ nguyên các job khác:

```powershell
python -m flask --app wsgi:app notification-worker --interval 15 --appointment-id 64
```

Hoặc chạy cả web/worker: `python run_dev.py --appointment-id 64` (thay 64 bằng
mã lịch thử). **Bỏ `--appointment-id` khi chạy vận hành** để xử lý mọi lịch hẹn,
reminder và review. Lệnh one-shot `process-notification-jobs` vẫn được giữ.

4. Quan sát `pending → processing → sent`, `attempts=1`, `sent_at` có giá trị.
   Log phải có type, mã lịch, người nhận được che và provider id. Gọi complete lại
   hoặc restart worker không tạo/gửi thêm post-care job đã sent.
5. Xác nhận inbox/spam có subject `Bin Spa - Dặn dò sau buổi chăm sóc`.
   Provider nhận email và job `sent` chưa chứng minh email đã xuất hiện trong inbox.

Job dùng khóa `appointment:<malh>:postcare` khi gửi Resend. Lỗi provider được lưu
trong `last_error`; retry sau 5 × attempts phút, tối đa `max_attempts`. Không reset
sent/failed job để gửi lại một cách tùy tiện. Khách thiếu/blank email vẫn hoàn thành
lịch, không enqueue email. Review request giữ lịch sau 2 giờ.

## Tự hủy lịch khi khách không đến

Mỗi chu kỳ, `notification-worker` (được `python run.py` khởi động cùng web) tự hủy lịch **chờ xác nhận/đã xác nhận**
đã quá giờ hẹn `NO_SHOW_GRACE_MINUTES` phút (mặc định 30, đặt trong `.env`). Khi hủy:
- trả lại các buổi gói/quà đang giữ cho lịch, hủy email nhắc lịch còn chờ;
- ghi chú "[Tự động hủy ...]" vào lịch;
- xếp email `appointment_no_show` vào outbox (báo khách lịch đã hủy, mời đặt lịch mới), worker gửi và retry như email khác.

Lịch đã chuyển "Đang thực hiện" (khách đã đến) không bị hủy. Chạy một lần thủ công: `flask --app wsgi:app auto-cancel-no-shows`.
Khách tự hủy hoặc đổi dịch vụ được tới trước giờ hẹn; nhân viên đổi dịch vụ theo yêu cầu khách ở trang Lịch hẹn (nút "Đổi dịch vụ").

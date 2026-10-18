# Trả lời AI tiếp tục khi khách chuyển trang

Khung chat hiện có chế độ xử lý nền: gửi câu hỏi nhận mã yêu cầu ngay, worker AI xử lý độc lập với trang web, trang mới lấy lại kết quả bằng mã đó. Áp dụng cả trang khách Jinja và `/appointments/create` React. Việc chuyển trang/tải lại không gọi Gemini lại cho cùng một mã.

## Hành vi khách hàng

- Giữ câu hỏi đang chờ, lịch sử và trạng thái mở khung chat khi chuyển trang trong cùng tab.
- Trang mới tiếp tục đợi và hiển thị câu trả lời. Nếu khung chat đang đóng khi có kết quả, nút mở đổi thành “AI đã trả lời”. Khi mở/khôi phục, cuộn đến nội dung mới nhất.
- Mất phản hồi xác nhận đã nhận câu hỏi: gửi lại **cùng UUID**, không tạo tác vụ AI thứ hai. Nếu việc xử lý đã thất bại, nút Thử lại tạo câu hỏi mới có mã mới.
- Bản nháp, trạng thái bỏ bản nháp và xác nhận đặt lịch được giữ qua trang. Chuyển trang không tự xác nhận booking; API xác nhận cũ tiếp tục kiểm tra quyền và idempotency.
- Lịch sử tách theo tài khoản/phiên khách. Đổi tài khoản không thấy câu trả lời của tài khoản trước. Khách chưa đăng nhập được xác định bằng nonce trong Flask session ký; không dùng fingerprint/IP làm chủ sở hữu.

Chế độ mới áp dụng cho câu hỏi gửi sau khi tải bản JS mới. Yêu cầu đồng bộ đã gửi từ bản cũ chưa có mã tác vụ thì không thể khôi phục sau khi trình duyệt hủy kết nối. Cần Ctrl+F5 một lần sau cập nhật.

## Thành phần kỹ thuật

`AIChatJob` lưu UUID, khóa chủ sở hữu HMAC, loại/id tài khoản, hash để kiểm tra retry, payload đã giới hạn/che PII và kết quả/trạng thái. Không lưu JWT, cookie hoặc headers. Nội dung/historic text gửi vào hàng đợi được giới hạn 1.000 ký tự/mục và 10 mục gần nhất; tên tài khoản, email, số điện thoại theo bộ scrub hiện có được che trước khi lưu/gửi provider. Không tuyên bố bộ scrub nhận diện được mọi dữ liệu cá nhân tùy ý.

Kết quả trên máy chủ hết hạn sau **2 giờ**; worker dọn các row hết hạn mỗi khoảng 10 phút khi hoạt động. Lịch sử đã nhận ở trình duyệt nằm trong `sessionStorage` của tab. Bản nháp booking vẫn có hạn 30 phút của nghiệp vụ cũ; việc giữ chat không gia hạn giá/giờ hoặc tự tạo lịch.

| API/lệnh | Chức năng |
| --- | --- |
| `GET /api/ai/status` | Khi bật cờ, trả `chat_jobs` và scope hội thoại dạng opaque cho trình duyệt. |
| `POST /api/ai/chat/jobs` | Enqueue và trả 202, hoặc trả kết quả đã có khi retry cùng mã/nội dung; trùng mã khác nội dung trả 409. |
| `GET /api/ai/chat/jobs/<uuid>` | Chỉ chủ sở hữu đọc được trạng thái/kết quả; người khác nhận 404. Hết hạn trả 410. |
| `flask --app wsgi:app ai chat-worker` | Worker riêng cho AI, không gọi notification worker hoặc gửi email. |
| `flask --app wsgi:app ai chat-worker --once` | Xử lý tối đa một câu hỏi, dùng cho kiểm tra có kiểm soát. |
| `flask --app wsgi:app ai prune-chat-jobs --dry-run` | Xem số row đã hết hạn; bỏ `--dry-run` mới xóa. |

Claim tác vụ bằng UPDATE atomic, PostgreSQL có `SKIP LOCKED`; worker đồng thời không gọi AI hai lần cho một row. Worker kiểm tra lại tài khoản/quyền trước khi gọi service. Luồng AI cũ chỉ tạo draft; khách vẫn phải xác nhận booking. Nếu worker bị dừng khi xử lý, sau 5 phút tác vụ được đánh dấu gián đoạn, không tự gọi lại provider để tránh lặp tác dụng phụ/chi phí. Khách được thử lại bằng thao tác rõ ràng. Tác vụ chưa bắt đầu nằm trong DB để worker đọc sau khi hoạt động lại. Không bảo đảm phản hồi khi máy chủ/provider ngừng hoạt động; lỗi được giữ thành trạng thái để khách biết.

Giới hạn POST dùng cơ chế authentication rate bucket hiện có: 20 lần/phút/IP khi bật rate limit. GET polling chỉ đọc, mỗi giây trong lúc đang chờ; mất kết nối thử lại chậm hơn với cùng mã. Mỗi chủ sở hữu được kiểm tra tối đa 3 tác vụ đang chờ/xử lý. Payload được lưu trước khi gọi provider và kết quả được commit trước khi trả cho trang mới; không dựa vào `keepalive` để giữ request Gemini sống. `keepalive` chỉ hỗ trợ gửi enqueue, UUID mới là cơ chế phục hồi khi mất phản hồi.

## Migration và chạy

Migration `20261015_0022` chỉ thêm `ai_chat_job` và chỉ mục; không sửa lịch, thanh toán, công/lương. Sau migration bật:

```dotenv
AI_CHAT_JOBS_ENABLED=true
```

```powershell
venv\Scripts\python.exe -m flask --app wsgi:app db upgrade
python run.py --https
```

`run.py`/`run_dev.py` hiện quản lý **web + notification worker + AI chat worker**; reloader của web không sinh thêm worker. Ctrl+C ở supervisor dừng các tiến trình con. Nếu chạy Gunicorn hoặc dịch vụ tách riêng, cần một process `flask --app wsgi:app ai chat-worker` cùng database/cấu hình; không chạy worker này trong từng Gunicorn web worker. Chưa thay đổi dịch vụ cloud hoặc triển khai lên Render trong phiên này.

Cờ nguồn và `.env.example` mặc định false để ứng dụng chưa migrate tiếp tục dùng `/api/ai/chat` đồng bộ. Bản async là bổ sung, không đổi hợp đồng endpoint cũ. Trước rollback/downgrade, ngừng enqueue và xử lý/giải quyết tác vụ đang có, rồi dừng worker; downgrade về 0021 xóa bảng hàng đợi và kết quả tạm. Không xóa bản nháp/lịch hẹn đã được tạo bởi các service nghiệp vụ.

## Đã áp dụng và kiểm thử

Đã backup `backups/binspa-before-ai-chat-jobs-20261015-150846.dump`, thử khôi phục vào PostgreSQL tạm và migrate bản khôi phục, sau đó nâng DB đang dùng lên 0022. Số dòng dữ liệu nghiệp vụ và tổng thanh toán/lương giữ nguyên. Đã bật cờ, web trả `chat_jobs=true`, readiness 200 và heartbeat AI worker còn mới. Không gửi câu hỏi giả đến Gemini trên DB thật để thử tính năng.

Với bộ chạy local đang mở từ trước khi sửa supervisor, đã gắn thêm riêng AI worker và theo dõi vòng đời supervisor hiện tại; nó tự dừng khi supervisor cũ dừng. Không khởi động lại notification worker. Ở lần chạy `run.py` tiếp theo, supervisor mới tự quản lý đủ ba tiến trình. Log bootstrap local ở `.test-tmp/ai-chat-worker.log`; đó là dữ liệu vận hành local đã được Git bỏ qua.

Đạt **74 kiểm thử Python liên quan** trên SQLite và PostgreSQL tạm, gồm migration, IDOR, che PII, worker lỗi/expire, idempotency và hai worker/request đồng thời; thêm **5 kiểm thử supervisor** và **45 kiểm thử JS**. Chrome thực kiểm tra 360/1440 px: đang đợi → chuyển Trang chủ/Dịch vụ/Đặt lịch React → nhận kết quả → reload; mất phản hồi enqueue; khôi phục draft và xác nhận; đổi tài khoản không lộ hội thoại. AI/email được giả lập, DB thử riêng. Ảnh tại `.test-tmp/ai-chat-navigation-a6f56b09`; có workflow CI cho hành trình này. PostgreSQL thử nghiệm/restore đã được dừng sau chạy.

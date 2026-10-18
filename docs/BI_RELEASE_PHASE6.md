# Báo cáo BI và chuẩn bị vận hành giai đoạn 6

Triển khai tiếp BI-01 và phần QA/security/observability của giai đoạn 6 trong `BinSpa_KeHoach_NangCap_GPS_ChamCong_UI_Refactor.docx`. Bản này bổ sung báo cáo, giám sát, giới hạn đăng nhập và công cụ thử khôi phục. **Chưa đánh dấu hoàn tất toàn bộ giai đoạn 6 hoặc nghiệm thu production**; các việc còn lại được ghi cuối tài liệu.

## Màn hình và quyền

Mở **Báo cáo & vận hành** trong menu nội bộ hoặc `/admin/reports`. Admin/quản lý chọn khoảng ngày tối đa 366 ngày, cơ sở công/lương và xuất CSV tổng hợp. Mỗi lần xuất có audit người xuất, khoảng ngày, cơ sở, phạm vi và mã yêu cầu. CSV không chứa thông tin liên hệ khách hoặc tọa độ GPS. Nhân viên/lễ tân không được gọi API báo cáo.

Tab **Giám sát hệ thống** chỉ dành cho admin, gồm HTTP p95/4xx/5xx, tín hiệu worker, thông báo chờ quá lâu/thất bại, trạng thái webhook và nhóm kết quả GPS. Màn giám sát chỉ đọc; không gửi lại email, duyệt công hoặc gọi ngân hàng.

Phân cơ sở được xử lý theo dữ liệu thực có:

- Chế độ một địa điểm cố định: số liệu kinh doanh thuộc spa ở địa điểm đó; công/lương theo cơ sở cố định.
- Chế độ nhiều cơ sở: công và bảng lương được lọc bằng quyền quản lý cơ sở trong DB. Lịch hẹn, hóa đơn và bán gói cũ chưa có snapshot cơ sở đáng tin cậy; không suy ngược từ cơ sở hiện tại của nhân viên.
- Vì vậy, chỉ admin xem báo cáo kinh doanh toàn spa khi không chọn cơ sở. Quản lý nhiều cơ sở hoặc bộ lọc chọn riêng một cơ sở sẽ chỉ có phần công/lương; giao diện giải thích phần chưa có dữ liệu phân cơ sở.

## Định nghĩa số liệu

| Chỉ số | Nguồn và quy tắc |
| --- | --- |
| Thực thu | Thanh toán dịch vụ dương theo `ngaythanhtoan` cộng gói `paid` có `payable_amount > 0` theo `paid_at`; giữ quy tắc analytics hiện có. Hóa đơn chưa thu và sử dụng buổi gói không được tính lại. Đây là thực thu hiện có, không tự mô tả là lợi nhuận hoặc thuần sau hoàn tiền. |
| Lịch hẹn | Theo ngày giờ hẹn Việt Nam, thống kê riêng từng trạng thái. |
| Khách quay lại | Khách có lịch hoàn thành trong kỳ và ít nhất một lịch hoàn thành trước kỳ, chia số khách hoàn thành trong kỳ; đếm khách duy nhất. |
| Retention kỳ trước | Khách hoàn thành trong kỳ liền trước có cùng số ngày và hoàn thành tiếp trong kỳ đang xem, chia tổng khách kỳ trước. Không có mẫu trả `null`, không giả tỷ lệ 0%. |
| Không đến | Chỉ lịch bị luồng tự hủy ghi nhận vào `appointment_outcome` từ khi bật BI. Hủy trước đây hoặc hủy thủ công không tự coi là no-show; hiển thị số lịch hủy chưa được phân loại. Không suy từ ghi chú có thể được nhập bằng tay. |
| Công | Theo `work_date` là ngày bắt đầu ca Việt Nam; chỉ cộng phút đã `APPROVED`/`LOCKED`. Tăng ca tách riêng, không tự trừ tiền do đi muộn. |
| Lương đã khóa | Chỉ các kỳ `LOCKED` nằm trọn khoảng ngày và thuộc cơ sở được cấp quyền. Kỳ chỉ giao một phần khoảng ngày được loại và thông báo, không chia lại snapshot. |
| Hoa hồng | Phát sinh là commission entry còn hiệu lực theo ngày hưởng. Hoa hồng trong lương đã khóa là số trong snapshot bảng lương; hai số này không cộng với nhau. |

Ngày báo cáo hiển thị theo Việt Nam. Sự kiện công/webhook lưu UTC được đổi ranh giới ngày khi lọc; dữ liệu lịch/thanh toán cũ tiếp tục dùng quy ước giờ Việt Nam của các service hiện có.

## Giám sát và bảo mật bổ sung

`/health/live` kiểm tra tiến trình web. `/health/ready` kiểm tra kết nối DB, revision bằng migration head và các bundle/CSS bắt buộc của tính năng đang bật; trả 503 nếu chưa sẵn sàng. Hai probe không trả cấu hình, hostname DB hoặc lỗi SQL, không gọi AI/email/bank.

HTTP được ghi log JSON với `request_id`, route mẫu, phương thức, mã HTTP và thời gian xử lý; không ghi body/query/cookie/token/IP/tọa độ trong log HTTP này. Response có `X-Request-ID` để đối chiếu. Mẫu hiển thị là tối đa 5.000 yêu cầu trong 30 phút **của tiến trình web đang trả lời**, mất khi khởi động lại; không được hiểu là số liệu toàn bộ Gunicorn worker hoặc hệ thống giám sát tập trung. Thu thập log cần cấu hình ở môi trường triển khai.

Worker ghi heartbeat sau mỗi vòng xử lý. Không có tín hiệu là `unknown`; quá 120 giây là `stale`; vòng có lỗi hoặc gửi thất bại là `degraded`. Worker cũ cần khởi động lại sau khi bật cờ. Không dùng heartbeat để khẳng định email đã đến hộp thư khách. Job chờ quá 5 phút hoặc xử lý quá 10 phút được đếm riêng.

Giới hạn chung qua DB, dùng upsert atomic áp dụng được trên nhiều tiến trình:

- Đăng nhập khách/nhân viên: 30 lần/15 phút/IP cho từng endpoint.
- Xác minh OTP/đặt lại mật khẩu: 10 lần/10 phút/IP; đăng ký/quên mật khẩu/gửi lại OTP: 3 lần/10 phút/IP.
- Chat AI: 20 lần/phút/IP. Trả 429 cùng `Retry-After`; kho giới hạn lỗi thì các endpoint này trả 503.

Khóa IP được HMAC bằng secret của ứng dụng, không lưu IP thô. Đây là fixed window, có thể có burst tại ranh giới và không thay thế chống tấn công phân tán. Mặc định không tin `X-Forwarded-For`; `TRUSTED_PROXY_HOPS` chỉ đặt bằng số proxy tin cậy thực tế (0 khi chạy trực tiếp). Không đặt tùy tiện để tránh giả IP/giao thức. Production bật cookie `Secure`; các API có `no-store`, `nosniff`, referrer/geolocation policy, chống nhúng khác origin; HTTPS production có HSTS. Endpoint khôi phục/đăng xuất dùng session từ chối POST khác origin/cross-site; nghiệp vụ JWT vẫn yêu cầu Authorization và quyền từ DB.

Dọn bucket hết hạn hơn một ngày bằng lệnh bảo trì, chưa tự gắn cron hoặc chạy xóa trên DB đang dùng:

```powershell
venv\Scripts\python.exe -m flask --app wsgi:app release prune-auth-limits --dry-run
venv\Scripts\python.exe -m flask --app wsgi:app release prune-auth-limits
```

## Sửa lỗi kết nối trợ lý AI ở máy phát triển

`Failed to fetch` là trình duyệt không nhận được response; riêng ảnh không đủ để phân biệt mất mạng, máy chủ đang reload hoặc lỗi TLS. Đã kiểm tra endpoint AI còn phản hồi và có cấu hình. Bộ chạy local trước đây dùng `ssl_context='adhoc'`, đổi chứng chỉ sau mỗi lần reload. Đã đổi sang cặp chứng chỉ/key dùng lại trong `instance/dev-localhost.*`, thư mục đã được gitignore; fingerprint được đối chiếu không đổi qua các lần reload sau sửa. Chứng chỉ vẫn là tự ký dành cho local, không dùng thay TLS production. Lần đổi chứng chỉ đầu có thể cần tải lại trang và xử lý cảnh báo chứng chỉ trong trình duyệt.

Khung chat hiện giải thích lỗi bằng tiếng Việt, giữ câu hỏi để gửi lại, có nút Thử lại/trang Đặt lịch, không tự gửi lại xác nhận booking. Thử lại chat không nhân đôi tin nhắn. Timer 45 giây bao gồm đọc JSON; HTML/JSON lỗi không trở thành câu trả lời rỗng thành công. Backend chia ngân sách 22 giây cho các lần gọi Gemini/retry trong một request, dùng socket timeout theo phần còn lại và trả lỗi JSON khi hết ngân sách. Không tuyên bố ngân sách này thay thế timeout của proxy/worker hoặc ràng buộc mọi hành vi DNS/mạng.

`python run.py --https` giữ nguyên cách chạy hiện có. Nếu dùng venv, cài `requirements-dev.txt` để có cryptography cho HTTPS local. File JS được tăng phiên bản cache; Ctrl+F5 để nhận bản mới. Chưa dùng dữ liệu/tin nhắn thật để gọi Gemini kiểm thử trong phiên này; bài thử provider và mạng đều giả lập.

## Migration và triển khai tại máy

Migration `20261015_0021` bổ sung bốn bảng: `auth_rate_bucket`, `report_export_audit`, `worker_heartbeat`, `appointment_outcome`. Không chỉnh sửa các bảng nghiệp vụ cũ hoặc snapshot lương.

```powershell
venv\Scripts\python.exe -m flask --app wsgi:app db upgrade
npm --prefix frontend ci
npm --prefix frontend run build
venv\Scripts\python.exe -m flask --app wsgi:app release check
```

Cờ trong `.env` sau migration/build:

```dotenv
BI_REPORTS_ENABLED=true
OBSERVABILITY_ENABLED=true
AUTH_RATE_LIMIT_ENABLED=true
TRUSTED_PROXY_HOPS=0
```

Ba cờ nguồn và `.env.example` mặc định false. Có thể tắt màn BI/giám sát mà không xóa bảng; giữ rate limit nếu cần bảo vệ đăng nhập. Khởi động lại web và notification-worker để cả hai đọc cấu hình/mã mới. Bộ `run.py --https` quản lý hai tiến trình; Ctrl+C ở terminal rồi chạy lại lệnh cũ. Công cụ triển khai không tự khởi động lại worker đang hoạt động vì thao tác đó có thể kích hoạt gửi thư thật đang chờ.

Ba cờ đã được bật tại máy này; web đang chạy trả 200 cho readiness, trang báo cáo và trạng thái AI. Đã kiểm tra API BI/giám sát bằng quyền admin trên dữ liệu thật chỉ đọc. GPS vẫn giữ bán kính 500 m/sai số 150 m. Worker hiện báo `unknown` vì tiến trình cũ chưa nạp heartbeat; cần khởi động lại bộ chạy như trên. Đã cài dependency HTTPS local còn thiếu vào venv và kiểm tra tạo cặp cert/key thật hợp lệ, dùng lại qua lần tải lại module.

DB tại máy đã sao lưu vào `backups/binspa-before-bi-phase6-20261015-144026.dump`, kiểm tra archive đọc được và **khôi phục thật vào PostgreSQL tạm riêng**, chạy migrate trên bản khôi phục và đối chiếu dữ liệu. Sau đó nâng DB đang dùng lên 0021. Trước/sau giữ nguyên: 23 khách, 84 lịch, 47 hóa đơn, 32 thanh toán, 9 lượt mua gói, 7 commission entry, 4 phiên công, 1 kỳ lương, 4 dòng lương; tổng thanh toán và tổng lương khóa không đổi. Không tạo giao dịch tài chính, duyệt công hay gửi email thật để thử chức năng.

Công cụ thử restore không kết nối DB nghiệp vụ đang chạy, tự tạo/dừng cụm PostgreSQL trên loopback; archive có dữ liệu thật chỉ nằm trong thư mục local đã được bỏ qua bởi Git:

```powershell
venv\Scripts\python.exe scripts/verify_backup_restore.py backups/binspa-before-bi-phase6-20261015-144026.dump
```

Nếu cần rollback, ưu tiên tắt cờ và dùng bản ứng dụng tương thích schema 0021. Downgrade chỉ trên bản sao/staging trước; 0021→0020 xóa bốn bảng mới và mất audit/telemetry/no-show đã ghi, không chạy tùy tiện trên DB có dữ liệu cần giữ. Khôi phục archive cũ vào DB khác để đối chiếu, không ghi đè vận hành khi chưa xác định giao dịch phát sinh sau backup.

## Kiểm thử và nghiệm thu còn lại

Đã đạt: build production, **699 kiểm thử Python** trên PostgreSQL tạm riêng và SQLite (gồm concurrency/migration), **10 kiểm thử frontend**, **44 kiểm thử JS**. Sau điều chỉnh cuối đã chạy lại các test BI/AI/chăm sóc/HTTPS và hành trình Chrome. Chrome giai đoạn 6 kiểm tra admin/quản lý/lễ tân/nhân viên, scope số liệu, xuất CSV có audit, giám sát chỉ admin, chat mất mạng→thử lại giữ lịch sử ở 360/390/768/1440 px; 36 ảnh tại `.test-tmp/phase6-browser-a95dc812`. Chưa chạy Safari/iPhone thật. Bộ PostgreSQL test và restore drill đã dừng sau khi hoàn tất.

CI được bổ sung hành trình giai đoạn 6 và kiểm tra danh mục đặt lịch mới; chưa push hoặc kích hoạt CI từ phiên này.

Trước khi ký phát hành toàn bộ theo Word vẫn còn:

- SEC-01 đã được triển khai tiếp bằng [xác thực hai bước cho thao tác nhạy cảm](STAFF_SECURITY_PHASE6.md). Cần tự thiết lập ứng dụng cho các tài khoản quản trị/quản lý và kiểm chứng bằng thiết bị thật trước nghiệm thu; không tự đăng ký thay người dùng.
- Staging với bản sao dữ liệu được kiểm soát, kiểm tra nhà cung cấp theo quy trình, HTTPS/proxy thật và theo dõi log tập trung. Chưa triển khai staging/production hoặc thực hiện canary trong phiên này.
- Kiểm thử GPS tại cửa hàng trên điện thoại thật; đối soát công/lương 1–2 kỳ với người phụ trách, quy tắc lương/thuế/bảo hiểm đã được cơ sở duyệt.
- Kiểm tra truy cập bằng bàn phím/độ tương phản và Safari/Android trên thiết bị thật, lưu bằng chứng kiểm thử vận hành; chỉ sau đó ký xác nhận triển khai.

Lệnh kiểm tra kỹ thuật trước staging/production (không gửi thư/gọi bank/AI) là `flask --app wsgi:app release check --production`; kết quả PASS kỹ thuật không thay chữ ký nghiệm thu nghiệp vụ.

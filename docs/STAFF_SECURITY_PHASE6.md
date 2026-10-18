# Xác thực hai bước cho thao tác nhạy cảm

Triển khai tiếp SEC-01 của `BinSpa_KeHoach_NangCap_GPS_ChamCong_UI_Refactor.docx`, giai đoạn 6. Bản này bổ sung xác minh bằng ứng dụng Authenticator trước thao tác nhạy cảm. Không đánh dấu hoàn tất toàn bộ Word hoặc nghiệm thu production.

## Sử dụng

1. Đăng nhập tài khoản nội bộ như hiện tại, mở **Bảo mật tài khoản** trong menu hoặc `/admin/security`.
2. Nhập mật khẩu hiện tại, chọn **Thiết lập ứng dụng**. Trong ứng dụng Authenticator trên điện thoại, thêm tài khoản bằng QR hoặc khóa nhập tay.
3. Nhập mã 6 số rồi **Xác nhận và bật**. Thiết lập chỉ hoàn tất sau khi mã đúng; QR/khóa chờ xác nhận hết hạn sau 10 phút.
4. Lưu **10 mã dự phòng** được hiển thị một lần, đánh dấu đã lưu rồi đóng. Mỗi mã chỉ dùng một lần. Có nút tải tệp văn bản; tệp do người dùng chủ động tải và cần giữ riêng tư.
5. Khi thao tác cần xác minh, nhập mã ứng dụng mới hoặc mã dự phòng. Hiệu lực 10 phút cho đúng JWT hiện tại; không mở rộng quyền nhân viên hay phạm vi cơ sở.

Các màn React mở hộp xác minh và giữ form đang nhập. Khi chưa thiết lập, có thể mở Bảo mật trong tab mới, hoàn tất rồi quay lại chọn **Đã thiết lập, tiếp tục**. Máy chủ từ chối trước khi ghi nghiệp vụ; chỉ sau xác minh thành công mới gửi lại đúng thao tác một lần. Hủy xác minh không ghi thay đổi. Mất mạng hoặc kết quả gửi không rõ không tự gửi lại thao tác. Nếu đổi tài khoản/JWT trong lúc chờ, yêu cầu cũ bị hủy và cần tải lại trang.

Các màn Jinja còn lại có liên kết Bảo mật trong menu. Nếu API yêu cầu xác minh, mở liên kết đó ở tab mới, xác minh rồi thực hiện lại thao tác trên form cũ. Chưa thay toàn bộ các màn Jinja thành React trong hạng mục này.

Đăng nhập, đặt lịch khách hàng, xem lịch cá nhân và chấm công GPS tiếp tục luồng hiện tại. Đây là xác thực tăng cường cho thao tác nhạy cảm, chưa phải yêu cầu mã thứ hai ở mọi lần đăng nhập.

## Phạm vi bảo vệ

| Nhóm | Thao tác yêu cầu xác minh |
| --- | --- |
| Công | Duyệt/từ chối phiên công, tạo công ngoại lệ, quyết định yêu cầu chỉnh công, khóa kỳ công |
| Lương GPS | Tạo snapshot lương, đối soát, điều chỉnh dòng lương, duyệt, chốt và xuất CSV lương |
| Lương cũ | Tính/điều chỉnh lương và xuất PDF, nếu luồng cũ vẫn được phép dùng |
| GPS/cơ sở | Tạo cơ sở kèm chính sách, đổi chính sách GPS/lương cơ sở, cấp quyền quản lý cơ sở |
| Nhân sự/quyền | Tạo, sửa, vô hiệu hóa nhân viên; tạo/sửa/xóa chức vụ và đơn giá giờ |

RBAC từ database vẫn chạy trước lớp xác minh; quản lý đã xác minh không được đổi chính sách dành riêng admin hoặc truy cập cơ sở khác. Khi bật cờ bảo mật, người có quyền thực hiện các thao tác trên phải tự thiết lập ứng dụng trước. Không tự đăng ký thiết bị hoặc tạo mã thật thay người dùng.

## Dữ liệu và kiểm soát

- TOTP theo RFC 6238, SHA-1, 6 số, chu kỳ 30 giây; chấp nhận sai lệch một chu kỳ mỗi phía. Counter đã dùng không được dùng lại, kể cả hai kết nối đồng thời. Nếu vừa dùng mã, chờ ứng dụng đổi mã mới.
- Khóa ứng dụng và khóa chờ thiết lập được mã hóa Fernet bằng `STAFF_MFA_ENCRYPTION_KEY`. Không gửi khóa cho dịch vụ tạo QR bên ngoài; Ant Design dựng QR trong trình duyệt.
- Mã dự phòng chứa 64 bit ngẫu nhiên, chỉ lưu HMAC gắn nhân viên; tiêu thụ bằng UPDATE có điều kiện chưa dùng. Bộ mã mới thay thế toàn bộ mã cũ.
- Hiệu lực xác minh lưu tại server, gắn hash JWT JTI, nhân viên, phiên bản cấu hình MFA và dấu vết mật khẩu/vai trò/trạng thái hiện tại. Không trả thêm bearer token có quyền cao hơn cho trình duyệt.
- Đổi mật khẩu/vai trò làm hiệu lực cũ không còn hợp lệ. API đổi mật khẩu, đổi quyền và khóa tài khoản cũng xóa các xác minh cũ để việc đổi lại quyền/mở lại tài khoản không khôi phục xác minh trước đó. Tắt MFA xóa khóa, mã dự phòng và các phiên xác minh của người đó; thao tác nhạy cảm tiếp theo yêu cầu thiết lập lại. Đăng xuất kèm JWT thu hồi xác minh cho JWT đó; nút **Kết thúc xác minh** thu hồi ngay.
- Bắt buộc mật khẩu hiện tại cùng mã chưa dùng để tắt MFA hoặc thay bộ mã dự phòng. Không có API cho admin đọc/reset khóa của người khác. Mất cả ứng dụng và mã dự phòng cần quy trình xác minh danh tính, khôi phục do người phụ trách kiểm soát; không cung cấp đường bỏ qua qua web.
- Giới hạn riêng qua DB: tối đa 10 yêu cầu chứng minh/thiết lập mỗi tài khoản và 30 mỗi IP trong 5 phút. Có `Retry-After`; vẫn áp dụng dù tắt cờ rate limit đăng nhập chung. Đây là cửa sổ cố định, không thay lớp chống tấn công phân tán.
- API trả `no-store`, từ chối thao tác cross-site; audit ghi actor/action/request ID/thời điểm, không chứa mật khẩu, OTP, khóa, mã dự phòng, JWT hay tọa độ.

## Cài đặt và vận hành

Migration `20261015_0023` chỉ thêm `staff_mfa`, `staff_recovery_code`, `staff_step_up`, `staff_security_audit`; không sửa bảng nhân viên, công, lương hoặc thanh toán. `cryptography` đã đưa vào dependency runtime.

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m flask --app wsgi:app db upgrade
npm --prefix frontend run build
```

Cấu hình nguồn và `.env.example` mặc định tắt. Tạo khóa bằng `Fernet.generate_key()` một lần và lưu trực tiếp trong cấu hình bí mật, không in vào log/commit:

```dotenv
STAFF_SECURITY_ENABLED=true
STAFF_MFA_ENCRYPTION_KEY=<khóa Fernet đã tạo và lưu an toàn>
```

Ứng dụng từ chối khởi động khi bật cờ mà khóa không hợp lệ. Các instance phải dùng cùng khóa mã hóa, `SECRET_KEY`, giờ hệ thống chính xác. Sao lưu khóa riêng với database; không thay/xóa khóa sau khi có người đăng ký mà chưa có kế hoạch chuyển mã hóa và thử khôi phục. Dữ liệu mã hóa không thể khôi phục chỉ bằng database nếu mất khóa. Đổi `SECRET_KEY` cũng làm mất hiệu lực hash mã dự phòng hiện có và xác minh; cần quy trình chuyển đổi có kiểm soát.

Chạy lại bộ phát triển bằng `python run.py --https`, rồi Ctrl+F5. Bộ chạy quản lý web, notification worker và AI chat worker. Không tự chạy lại notification worker từ công cụ triển khai để tránh phát thư thật đang chờ. Lệnh bảo trì chỉ xóa hiệu lực và khóa thiết lập đã hết hạn, không xóa khóa đang bật hay audit:

```powershell
venv\Scripts\python.exe -m flask --app wsgi:app staff-security prune --dry-run
venv\Scripts\python.exe -m flask --app wsgi:app staff-security prune
```

Rollback ưu tiên tắt cờ và dùng code tương thích schema. Hạ 0023 về 0022 xóa cấu hình MFA, mã dự phòng và audit bảo mật; chỉ thử trên bản sao, không dùng như cách sửa lỗi thông thường. Cờ tắt bỏ yêu cầu xác minh cho các thao tác được bảo vệ, do đó chỉ người quản trị môi trường vận hành được thay đổi.

Readiness kiểm tra schema/bundle; `release check --production` nay yêu cầu bật bảo vệ thao tác nhạy cảm, nhưng PASS kỹ thuật không thay nghiệm thu con người hoặc việc các tài khoản quản trị đã đăng ký MFA.

## Sửa việc tải giao diện hai lần

Kiểm tra Chrome phát hiện chunk chia sẻ import lại entry không có query, trong khi template nạp entry có `?v=...`. Hai URL được coi là hai module, dẫn đến hai React root và hai hộp xác minh. Build nay dùng entry có hash nội dung; template lấy đúng file từ manifest, không thêm query. Cổng công/lương cũng dùng bộ phân giải asset chung. Luồng hủy, nhập sai, xác minh và ghi đúng một lần đã được kiểm tra trên bản build này.

## Kiểm chứng tại máy

Đã sao lưu `backups/binspa-before-staff-security-20261015-221301.dump` (14.254.836 byte), kiểm tra archive đọc được, khôi phục thật vào PostgreSQL riêng và nâng bản khôi phục lên 0023. Kết quả `.test-tmp/restore-drill-ae46d8e8af/result.json` xác nhận dữ liệu nghiệp vụ giữ nguyên; server thử đã dừng. Sau đó mới nâng DB đang dùng lên 0023, đối chiếu trước/sau giữ nguyên 23 khách, 84 lịch, 47 hóa đơn, 32 thanh toán, 9 giao dịch gói, 7 commission entry, 4 phiên công, 1 kỳ lương, 4 dòng lương; thực thu dịch vụ 15.090.000đ và tổng lương đã khóa 0 không đổi.

Cờ bảo mật đã bật tại máy, khóa tạo trong `.env` bị Git bỏ qua; công cụ không đăng ký MFA thay người dùng. Flask test client trên cấu hình/DB thật chỉ đọc xác nhận readiness, trang/API bảo mật, trạng thái AI trả 200; export nhạy cảm chưa thiết lập trả 403 trước khi xuất. Đã kiểm tra lại qua web server local sau khi ứng dụng chạy: readiness, trang/API bảo mật và trạng thái AI đều trả 200, AI worker có heartbeat mới. Cấu hình Authenticator hiện có của admin được giữ nguyên.

Build production, 16 kiểm thử frontend và 45 kiểm thử JS đạt. Lượt hồi quy toàn bộ đạt **758 kiểm thử Python** trên PostgreSQL riêng/SQLite, ghi tại `.test-tmp/postgres-654f8302ad1c4c7283916c76c4442189/pytest.log`; PostgreSQL thử đã dừng sau khi hoàn tất. Phạm vi gồm migration upgrade/downgrade và hai yêu cầu OTP/mã dự phòng đồng thời chỉ một yêu cầu được chấp nhận. Chuỗi chấm công → duyệt → khóa kỳ → tạo lương vẫn giữ đúng phạm vi cơ sở. Sau bổ sung thu hồi xác minh khi đổi quyền/khóa/mở lại tài khoản, 17 kiểm thử liên quan đạt; kiểm tra thêm việc cách ly cờ cấu hình và giao diện cũng đạt.

Chrome kiểm tra QR/khóa nhập tay, 10 mã dự phòng, hủy giữ form, mã sai không ghi, mã đúng tạo đúng một policy ở 360/390/768/1440 px. 15 ảnh tại `.test-tmp/staff-security-browser-1d6a4f86`. Hành trình AI tiếp tục qua đổi trang/tải lại và khôi phục bản nháp đạt tại `.test-tmp/ai-chat-navigation-fc56087a`; hành trình BI/role/CSV/chat thử lại đạt tại `.test-tmp/phase6-browser-564fef30`. Dashboard theo vai trò, gói/quà tặng, đối soát mất phản hồi và thanh toán VietQR giả lập cũng đạt tại `.test-tmp/phase4-browser-95f4e7a4`. Toàn bộ dữ liệu browser là giả lập trong DB riêng, không gọi bank, AI thật hoặc SMTP.

Chưa có nghiệm thu staging/production, thiết bị Authenticator thật, Safari/iPhone, GPS thực địa và đối soát lương 1–2 kỳ; chưa đồng bộ toàn bộ màn quản trị cũ. Các mục này vẫn còn trong kế hoạch.

Nguồn kỹ thuật: [RFC 6238](https://www.rfc-editor.org/rfc/rfc6238), [OWASP Multifactor Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html), [Fernet](https://cryptography.io/en/latest/fernet/).

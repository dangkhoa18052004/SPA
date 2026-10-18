# Chấm công GPS và bảng lương Bin Spa

Bản nâng cấp bổ sung cổng nhân viên React/TypeScript, bảng công có phê duyệt và bảng lương có bản chốt, nối với Flask và các ca đang có. Chế độ một địa điểm theo yêu cầu chủ spa dùng tọa độ cố định và không cần phân cơ sở hoặc gán nhân viên trước khi chấm công. Đăng nhập vẫn mở `/admin/profile` và giữ menu nghiệp vụ cũ; chấm công là một mục trong menu. Sao lưu và nâng cấp schema trước khi bật trên một môi trường khác. Không theo dõi vị trí nền.

## Luồng chấm công đơn giản

- Nhân viên đang hoạt động mở **Chấm công GPS**, chọn một ca đang mở và chấm vào/ra. Mọi ca chưa gắn cơ sở tự dùng tọa độ Bin Spa dưới đây; không sửa quan hệ phân ca cũ và không cần thao tác gán riêng. Các ca tại một cơ sở khác không được đưa vào danh sách của chế độ này.
- Mỗi nhân viên chỉ có một phiên đang chấm vào. Cần chấm ra trước khi chọn ca khác.
- Khi GPS lỗi, không cấp quyền vị trí hoặc không chấm được, nhấn **Không chấm được? Gửi yêu cầu quản lý**, nhập giờ thực tế và lý do. Yêu cầu chấm vào không bắt nhập giờ ra.
- Quản lý/admin mở **Công & lương → Yêu cầu chấm công** để chấp nhận hoặc từ chối. Duyệt giờ vào tạo phiên OPEN; nhân viên tiếp tục chấm ra bằng GPS hoặc gửi yêu cầu chấm ra. Không ghi sự kiện GPS thành công giả cho yêu cầu thủ công.
- Bảng **Bảng công** hiển thị giờ vào/ra. Các đề nghị sửa cả ca vẫn có ở lịch sử. Không tự duyệt công của mình.
- `/admin/operations/branches` chỉ hiển thị địa điểm cố định; không có bước phân nhân viên, cấp cơ sở hoặc gắn ca.

Trong chế độ chọn ca tự do, khóa kỳ chỉ yêu cầu xử lý các phiên công và yêu cầu đã phát sinh, không ép các lượt phân ca cũ chưa chấm thành công bắt buộc. Màn kỳ công hiển thị số phiên chờ duyệt/chưa chấm ra và có nút mở đúng khoảng ngày cần duyệt.

Thu nhập hiển thị riêng giờ thực tế đã chấm ra, giờ chờ duyệt, công được trả đã duyệt và lương công tạm tính theo tháng. Chấm ra không tự duyệt lương. Lương tạm tính chưa gồm hoa hồng/phụ cấp/khấu trừ; phiếu chính thức chỉ hiện sau khi chốt.

## Chính sách khởi tạo theo thông tin chủ spa

| Thông số | Giá trị khởi tạo |
| --- | --- |
| Vĩ độ / kinh độ | 10.78686228650495 / 106.5794979291708 |
| Bán kính được chấm | 500 m |
| Sai số GPS tối đa | 150 m, kiểm tra độc lập với bán kính |
| Vị trí cũ tối đa | 30 giây; không dùng giờ thiết bị làm giờ công |
| Mở chấm vào | 30 phút trước ca đến trước khi ca kết thúc |
| Hạn chấm ra | 120 phút sau ca |
| Nghỉ không lương | 0 phút; quản lý xác nhận riêng khi duyệt |
| Giữ tọa độ nhân viên | 90 ngày theo phiên bản chính sách |
| Duyệt tự động / phạt GPS | Không |

Tọa độ được chủ spa cung cấp ngày 14/10/2026. Các cửa sổ giờ, thời hạn lưu và cách tính công là cấu hình đề xuất có thể thay đổi. Bán kính không cộng thêm sai số để cho qua tự động. GPS trong nhà có thể không đủ chính xác; nhân viên được thử lại hoặc gửi ngoại lệ. Không coi GPS là bằng chứng duy nhất kết luận gian lận.

## Cách tính lương được triển khai

Mô hình khởi tạo dùng đơn giá giờ ở **Chức vụ** (`ChucVu.dongiagio`) để nối với nghiệp vụ cũ. Có thể tạo chức vụ theo bậc kỹ thuật viên để áp dụng đơn giá khác nhau. Không gán mức lương mới cho dữ liệu hiện tại.

1. Quản lý tạo ca; nhân viên chọn ca và chấm vào/ra tại địa điểm cố định. Luồng bảng lương mới dựa trên công đã duyệt, không tự trả chỉ vì chọn ca.
2. Backend tính phút thực tế, phút vào muộn và ra sớm. Các số này giúp đối chiếu; chưa phải phút công được trả.
3. Quản lý xác nhận phút công thường, phút tăng ca, nghỉ không lương và phần ban đêm. Form gợi ý đủ giờ ca đã phân, thay vì tự giảm công vì GPS vào muộn. Quản lý phải đối chiếu và ghi lý do. Công được trả có thể khác phút GPS theo chính sách đã công bố.
4. Lương công = phút công thường / 60 × đơn giá giờ đã chụp × hệ số ca đã chụp. Hoa hồng dịch vụ/gói dùng cơ chế snapshot hiện có, giữ ưu tiên thưởng cố định trước phần trăm.
5. Tổng trước thuế/bảo hiểm = lương công + tăng ca + hoa hồng + phụ cấp/thưởng − khoản khấu trừ được duyệt. Không tự tạo phạt tiền, khấu trừ do GPS hoặc tự tính tăng ca từ thời gian chấm ra trễ.

Mẫu đối chiếu, không phải mức áp dụng: 22 ca × 8 giờ × 30.000đ = 5.280.000đ; 2 giờ tăng ca ngày thường = 90.000đ; hoa hồng 1.200.000đ; phụ cấp 300.000đ; khoản khấu trừ có căn cứ 150.000đ; tổng trước thuế/bảo hiểm = **6.720.000đ**.

### Tăng ca và ban đêm

Quản lý phân loại ngày theo lịch nghỉ của nhân viên; hệ thống không coi mọi Chủ nhật là ngày nghỉ hoặc tự suy ra ngày lễ. Tăng ca được duyệt áp dụng hệ số 1,5 ngày thường; 2 ngày nghỉ hằng tuần; 3 ngày lễ. Phút công thường ban đêm có phần cộng 0,3 đơn giá giờ. Phút tăng ca ban đêm tách khỏi tăng ca ban ngày và có phần cộng thêm theo loại ngày. Các hệ số được chụp vào kỳ lương.

Các mức thành phần căn cứ Điều 98 trong [Bộ luật Lao động bản hợp nhất tháng 02/2026](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/02/18-vbhn-vpqh.pdf), cùng hướng dẫn tại [Nghị định 145/2020/NĐ-CP](https://vbpl.vn/botuphap/Pages/vbpq-toanvan.aspx?ItemID=152668&Keyword=). Khi duyệt tăng ca đêm, xác nhận có tăng ca ban ngày trong cùng ngày, kể cả ca khác, để xác định phần tiền cộng thêm. Việc xác định giờ nghỉ được hưởng lương, lương ngày lễ ngoài khoản làm thêm, đơn giá hợp đồng, thuế, bảo hiểm và các khoản khấu trừ vẫn cần người phụ trách nhân sự xác nhận. Phiếu hiện tại ghi rõ tổng **trước thuế/bảo hiểm**, chưa thực hiện tính các nghĩa vụ đó.

### Chốt và điều chỉnh

- Công: OPEN → SUBMITTED → APPROVED hoặc REJECTED. Chỉ công đã duyệt trở thành LOCKED khi khóa kỳ. Không khóa ngày chưa kết thúc, ca còn thiếu công hoặc yêu cầu điều chỉnh chưa xử lý.
- Quên chấm/GPS lỗi: nhân viên gửi giờ thực tế và lý do. Quản lý chấp nhận tạo revision, vẫn giữ event GPS gốc; công quay lại SUBMITTED để duyệt phút được trả riêng. Với ca chưa có công, quản lý được ghi ngoại lệ giờ thực tế hoặc xác nhận vắng mặt có lý do.
- Lương: DRAFT → APPROVED → LOCKED. Người tạo bản nháp cần người khác duyệt; không tự duyệt công/điều chỉnh lương của mình. Cần cấp quyền quản lý cơ sở cho người kiểm tra; nếu kỳ có lương của người kiểm tra, chọn người khác.
- Sau khóa, dữ liệu giá dịch vụ, đơn giá chức vụ hoặc trạng thái lịch hẹn không làm đổi phiếu đã phát. Hoa hồng đã được chốt nhưng bị hủy sau đó tạo delta âm ở kỳ tiếp theo, khôi phục lại thì tạo delta tương ứng; không xóa khoản cũ hoặc trả trùng.
- Mỗi hoa hồng có một claim ban đầu trên toàn hệ thống. Nhân viên thuộc nhiều cơ sở mà hoa hồng chưa có phân bổ sẽ làm dừng tạo lương để đối soát, không tự chọn một cơ sở.
- `PAYROLL_V2_CUTOVER_DATE` phải là ngày bắt đầu phần **chưa trả** bằng hệ thống cũ. Không lập lại kỳ đã trả ở luồng lương cũ. Việc chuyển giữa một kỳ cần đối soát riêng; ưu tiên chuyển từ đầu tháng kế tiếp.

## Giao diện và API

| Địa chỉ | Sử dụng |
| --- | --- |
| `/employee/attendance` | Ca hôm nay, chấm công một lần, thông báo GPS |
| `/employee/appointments` | Lịch hẹn của nhân viên đang đăng nhập, gồm lịch sử, bộ lọc ngày/trạng thái và chi tiết khách/dịch vụ |
| `/employee/schedule` | Các ca có thể chọn trong chế độ một địa điểm |
| `/employee/history` | Lịch sử công, sự kiện chấm và yêu cầu chỉnh công |
| `/employee/income` | Giờ thực tế/chờ duyệt/được trả, hoa hồng, phiếu lương GPS và lịch sử lương trước ngày chuyển; in/lưu PDF bằng trình duyệt |
| `/employee/account` | Cơ sở, hướng dẫn quyền vị trí, hồ sơ, đăng xuất |
| `/admin/operations` | Tổng quan công và việc chờ xử lý |
| `/admin/operations/attendance` | Duyệt công và xử lý ca thiếu công |
| `/admin/operations/adjustments` | Duyệt yêu cầu chấm vào, chấm ra và chỉnh công |
| `/admin/operations/payroll` | Kỳ công, tạo/duyệt/khóa lương, phụ cấp, khấu trừ, xuất CSV mở bằng Excel |
| `/admin/operations/branches` | Xem địa điểm cố định; chế độ nhiều cơ sở mới có phân cơ sở và gắn ca |
| `/admin/operations/audit` | Người thực hiện, lý do, dữ liệu trước/sau |

React dùng Ant Design cho khu vực nội bộ, design tokens chung và tải module theo khu vực. Mobile dùng card và điều hướng dưới cho nhân viên, menu Drawer cho quản lý. Các trang khách hàng/Jinja còn giữ nguyên theo lộ trình chuyển dần.

Mục **Lịch hẹn của tôi** có trong menu tài khoản nhân viên và thanh điều hướng cổng nhân viên. API `/api/me/appointments` luôn lọc `lichhen.manv` bằng nhân viên trong JWT, không nhận mã nhân viên từ bộ lọc. Trả lịch quá khứ/sắp tới của chính người đó, tên/điện thoại khách, dịch vụ, thời lượng, trạng thái và ghi chú khách. Lịch chưa gán nhân viên hoặc gán người khác không xuất hiện. Màn này chỉ xem, không đổi trạng thái lịch hẹn.

Phát triển frontend: chạy Flask trên cổng 5000, chạy `npm --prefix frontend run dev`, mở URL Vite và đăng nhập qua `/admin/login`. Vite chuyển tiếp API và các trang/asset Jinja cần thiết về Flask; build production xuất vào `app/static/portal` để Flask phục vụ cùng origin.

API chính: `/api/me/shifts/today`, `/api/attendance/check-in`, `/api/attendance/check-out`, `/api/me/attendance`, `/api/me/attendance-events`, `/api/me/attendance-adjustments`, `/api/me/commissions`, `/api/me/payslips`; quản lý dùng `/api/admin/attendance`, `/attendance/missing`, `/attendance/exceptions`, `/attendance-adjustments`, `/attendance-periods`, `/payroll-periods`, `/payroll-lines`, `/branches`, `/operations/audit`. Endpoint duyệt và điều chỉnh kiểm tra quyền cơ sở tại backend và phiên bản dữ liệu.

Request chấm công cần `shift_assignment_id` (mã `maca` hiện tại), `latitude`, `longitude`, `accuracy`, `location_timestamp` có múi giờ và `idempotency_key`. Danh tính nhân viên lấy từ JWT, không nhận từ payload. Hai request giống nhau cùng key trả cùng quyết định; đổi nội dung phải dùng key mới. Khi mạng mất sau khi server nhận, frontend gửi lại **nguyên payload và key**, không hiện thành công trước phản hồi server.

## Schema và bảo toàn dữ liệu

Migration `20261014_0018`, sau `20261007_0017`, bổ sung `calam.branch_id` nullable cùng các bảng cơ sở, policy, event/session/adjustment, kỳ công, kỳ/line/adjustment lương, claim/delta hoa hồng và audit. Không tạo bảng phân ca thứ hai: quan hệ `nhanvien_calam` vẫn là nguồn phân ca. Không chuyển ca cũ sang cơ sở một cách ngầm định và không tính lại bảng lương cũ.

Migration `20261014_0019` thêm loại yêu cầu `correction` / `check-in` / `check-out` và cho phép giờ ra đề nghị để trống khi yêu cầu chấm vào. Yêu cầu cũ giữ loại `correction`. Chế độ một địa điểm không dùng phân ca làm điều kiện chấm công.

UTC được lưu cho dữ liệu mới, giao diện hiển thị giờ Việt Nam. Timestamp hoa hồng cũ là giờ địa phương nên bộ tổng hợp vẫn dùng biên ngày địa phương cho chúng. Ca qua nửa đêm thuộc ngày bắt đầu ca. Tiền dùng Decimal/NUMERIC; lương được làm tròn đến đồng theo từng phiên.

Nhánh dữ liệu tranh chấp có transaction và khóa hàng; SQLite dùng UPDATE để khóa ghi, PostgreSQL dùng khóa hàng tương ứng. Unique constraints ngăn phiên hoặc key trùng. Phiên công và kỳ lương có version; màn duyệt cũ trả 409 để tải lại. Ca đã có event/session/adjustment hoặc thuộc kỳ khóa không được sửa, xóa hay gỡ nhân viên qua API ca cũ.

## Áp dụng trên môi trường thử nghiệm rồi vận hành

Yêu cầu Node 22.20+ và Python 3.12 với các dependency của repo. `build.sh` đã có bước build frontend trước migration.

```powershell
# Dùng bản sao dữ liệu đã ẩn thông tin; DATABASE_URL trỏ tới môi trường thử nghiệm.
npm --prefix frontend ci
npm --prefix frontend run build
venv\Scripts\python.exe -m flask --app wsgi:app db upgrade

# Khởi tạo địa điểm cố định và policy GPS; lệnh trả mã cơ sở để điền bên dưới.
venv\Scripts\python.exe -m flask --app wsgi:app operations-init-branch --admin-id <ma_admin> --simple
```

Sau khi migration thành công, cấu hình môi trường và khởi động lại ứng dụng:

```dotenv
EMPLOYEE_PORTAL_ENABLED=true
ATTENDANCE_ENABLED=true
ATTENDANCE_SIMPLE_MODE=true
ATTENDANCE_BRANCH_ID=<ma_co_so_lenh_khoi_tao_tra_ve>
PAYROLL_V2_ENABLED=false
PAYROLL_V2_CUTOVER_DATE=
```

Không cần phân cơ sở hoặc gắn ca khi `ATTENDANCE_SIMPLE_MODE=true`. Nhân viên dùng ca đang có; ca mới nhận địa điểm cố định tự động. Quản lý được duyệt yêu cầu tại địa điểm chung theo vai trò hiện tại. Tọa độ, bán kính và sai số cố định theo thông tin chủ spa. Nếu cần vận hành nhiều cơ sở sau này, tắt chế độ đơn giản rồi cấu hình phân cơ sở/quyền quản lý riêng trước khi áp dụng.

Chạy bảng công/lương mẫu song song để đối chiếu. Khi quyết định chuyển, điền ngày bắt đầu kỳ chưa trả vào `PAYROLL_V2_CUTOVER_DATE`, bật `PAYROLL_V2_ENABLED=true`. API sửa lương cũ được chặn khi bảng lương mới bật. Các trang Jinja kinh doanh tiếp tục hoạt động.

Lập lịch hàng ngày cho lệnh xóa tọa độ hết hạn:

```powershell
venv\Scripts\python.exe -m flask --app wsgi:app attendance-purge-gps --dry-run
venv\Scripts\python.exe -m flask --app wsgi:app attendance-purge-gps
```

Lệnh giữ nguyên thời gian công, khoảng cách, quyết định và nhật ký; xóa latitude/longitude nhân viên đã quá hạn. Không ghi tọa độ nhân viên vào log thông thường. API mới có request ID, `no-store`, `nosniff` và quyền GPS giới hạn cùng origin. Chấm công thực tế cần HTTPS và quyền định vị, chỉ lấy vị trí khi thao tác.

### Sao lưu và rollback

Sao lưu PostgreSQL bằng `pg_dump` trước khi áp dụng và kiểm tra phục hồi trên database test. Nếu UI có lỗi, tắt `EMPLOYEE_PORTAL_ENABLED` để quay lại menu và trang cũ. Nếu chấm công có lỗi, tắt `ATTENDANCE_ENABLED`, nhận yêu cầu ngoại lệ và đối chiếu thủ công. Không dùng hạ cấp schema để xử lý một lỗi UI.

`flask db downgrade 20261007_0017` xóa các bảng công/lương **mới** và cột cơ sở, nên chỉ dùng trên bản sao để kiểm tra rollback hoặc sau khi đã sao lưu/xuất dữ liệu mới. Không hạ cấp một kỳ lương đã vận hành. Bản chốt lương mới không bị sửa khi tắt flag; không tái trả cùng kỳ qua bảng lương cũ.

## Kiểm chứng

```powershell
venv\Scripts\python.exe -m pytest -q
venv\Scripts\python.exe scripts/test_with_postgres.py -- -q
npm --prefix frontend test
node --test tests/*.test.cjs
venv\Scripts\python.exe tests/operations_browser_check.py
```

Helper PostgreSQL tạo cụm riêng chỉ nghe localhost, không sử dụng `DATABASE_URL`, rồi tắt cụm sau test. `.github/workflows/quality.yml` cung cấp PostgreSQL 17, Python/JS tests, frontend build và hành trình Chrome. Chạy CI từ GitHub chưa được xác nhận trong phiên làm việc local này.

Chrome test dùng database riêng, GPS giả lập và phản hồi mạng bị mất có chủ đích để kiểm tra retry. Kiểm tra các kích thước 360/390/768/1440, cổng nhân viên/quản lý, duyệt công và xem phiếu lương. Đây chưa thay thế khảo sát GPS trong nhà trên điện thoại thật, kiểm tra iOS Safari/Android Chrome thực tế và đối soát lương 1–2 kỳ.

## Phần còn lại của lộ trình trong tài liệu Word

Đã triển khai nền tảng và luồng mới cho GPS, duyệt công, lương/hoa hồng snapshot, employee React, manager/admin operations, migration/rollback tests và cấu hình CI. Booking/payment/gói/loyalty/recommendation hiện hữu được giữ và chạy hồi quy cùng các phần mới.

Dashboard kinh doanh theo vai trò và cụm đặt lịch khách hàng đã được nâng cấp ở [giai đoạn 4 UI](UI_PHASE4.md), có cờ chuyển giao diện và đường dẫn đối chiếu trang cũ. Chưa chuyển toàn bộ trang quản trị/khách hàng sang React; chưa bổ sung CRM/BI nâng cao, 2FA, quản lý thuế/bảo hiểm, tích lũy phép hoặc chính sách đổi ca. Không đánh dấu hoàn tất toàn bộ kế hoạch bằng việc dựng cổng công/lương và hai cụm giao diện này. Phát hành production, backup/restore trên dữ liệu thật, khảo sát GPS và người phụ trách ký xác nhận quy chế lương cần thực hiện tại môi trường vận hành.

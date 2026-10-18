# Kế hoạch thống nhất giao diện quản trị Bin Spa

Ngày lập 16/10/2026, cập nhật 17/10/2026. Trạng thái: Đợt 1–5 đã triển khai ngày 16/10/2026; Đợt 6 đã triển khai ngày 17/10/2026 (xem [bảng đối chiếu URL](2026-10-16-bang-doi-chieu-admin.md) và [kết quả Đợt 6](../docs/ADMIN_CARE_PHASE6.md)). Đợt 2 bật bằng `ADMIN_BOOKING_REACT_ENABLED`, Đợt 3 bằng `ADMIN_BILLING_REACT_ENABLED`, Đợt 4 bằng `ADMIN_CATALOG_REACT_ENABLED`, Đợt 5 bằng `ADMIN_PEOPLE_REACT_ENABLED`, Đợt 6 bằng `ADMIN_CARE_REACT_ENABLED`. Đợt 7 chưa thực hiện nghiệm thu toàn bộ.

## Mục tiêu

Toàn bộ khu vực quản trị dùng giao diện React TypeScript và Ant Design hiện có: cùng thanh menu, tiêu đề, màu sắc, bảng dữ liệu, biểu mẫu và cách thông báo kết quả. Người dùng đi từ tổng quan sang lịch hẹn, nhân sự, công/lương hoặc hồ sơ mà vẫn ở trong cùng một khung giao diện.

Thực hiện theo mục UX-02 và 5.4–5.5 của kế hoạch Word. Tái sử dụng API và service nghiệp vụ; mọi thay đổi API cần thiết để hỗ trợ màn mới được bổ sung có kiểm thử tương thích. Các quy tắc thanh toán, lượt liệu trình, công/lương và phân quyền tiếp tục được kiểm tra tại máy chủ.

## Hiện trạng đã đối chiếu mã nguồn

| Nhóm | Hiện trạng |
| --- | --- |
| Tổng quan, CRM, báo cáo, bảo mật | React, cùng khung `AdminShell` |
| Công/lương, yêu cầu công, địa điểm, nhật ký | React, cùng khung `AdminShell` |
| Lịch hẹn, khách hàng, hóa đơn, bán gói | React, đã chuyển Đợt 2–3 |
| Dịch vụ, gói, chi tiết/tạo/sửa gói, liệu trình khách | React, đã chuyển Đợt 4 |
| Nhân viên, chức vụ, ca, duyệt đăng ký ca | React, đã chuyển Đợt 5 |
| Điểm thưởng, đánh giá, tin nhắn | React, đã chuyển Đợt 6; giữ bản Jinja để dự phòng có kiểm soát |
| Hồ sơ, đổi mật khẩu, đăng nhập, lịch cá nhân, đăng ký ca | React, đã chuyển Đợt 1 và 5 |
| Lương cá nhân | Đã chuyển hướng sang thu nhập khi bật bảng lương GPS; còn đường dự phòng cũ |
| Phân tích AI trên dashboard | Tạo và xem tóm tắt ngay trên React; không còn liên kết dashboard cũ khi bật Đợt 6 |

Các nhóm màn đã được chuyển tăng dần. Đợt 7 sẽ đối chiếu đầy đủ quyền, liên kết sâu, thiết bị và điều kiện vận hành trước khi dọn các template/JS dự phòng.

## Thiết kế và điều hướng đích

- Khung quản trị chung có sidebar thu gọn được, topbar tên/vai trò, đường dẫn phân cấp và vùng nội dung. Mobile dùng Drawer, bảng có cách xem phù hợp màn nhỏ.
- Dùng hệ màu xanh hiện tại của React, font, khoảng cách và trạng thái nút thống nhất. Ant Design là bộ thành phần chính cho khu vực nội bộ.
- Một cấu hình menu dùng chung, lọc theo quyền và tính năng đang bật. Admin, quản lý và lễ tân cùng hệ thiết kế, mỗi vai trò thấy đúng tác vụ được cấp.
- Nhóm menu: Tổng quan; Vận hành; Nhân sự; Công và lương; Danh mục; Chăm sóc; Báo cáo; Hệ thống. Hồ sơ, bảo mật và đăng xuất nằm ở khu vực tài khoản.
- Công/lương trở thành nhóm trong menu quản trị chung. Các trang nhân viên chuyên dụng tiếp tục dùng điều hướng mobile phù hợp tác vụ; liên kết từ quản trị có tên và đường quay lại rõ ràng.
- Bảng dùng cùng bộ tìm kiếm, bộ lọc, phân trang và xóa bộ lọc. Trang có trạng thái tải, trống, lỗi và thử lại. Form thêm/sửa ưu tiên Drawer; xác nhận ngắn dùng Modal.

## Thứ tự triển khai

### Đợt 1 Nền giao diện và tài khoản

1. Lập bảng đối chiếu từng URL, thao tác, API, quyền và liên kết sâu; đánh dấu chức năng còn thiếu ở bản React.
2. Tách khung quản trị chung và cấu hình menu khỏi `BusinessDashboard.tsx`/`main.tsx`; chuyển tổng quan, CRM, báo cáo, bảo mật và các màn công/lương vào khung đó.
3. Chuẩn hóa client API, xử lý phiên hết hạn, thông báo lỗi, tải dữ liệu và cổng xác minh hai bước. Giữ một nơi hiển thị hộp xác minh.
4. Chuẩn bị điều hướng React cho khu vực admin; Flask vẫn phục vụ URL khi mở trực tiếp hoặc tải lại. Giữ bộ lọc/phân trang trong URL để nút quay lại hoạt động đúng.
5. Chuyển hồ sơ, ảnh đại diện, đổi mật khẩu và trang đăng nhập sang cùng thiết kế. Giữ hướng vào trang cá nhân sau đăng nhập như yêu cầu đã thống nhất.

Điều kiện xong: các trang React hiện có và tài khoản dùng cùng khung/menu; tải lại, quay lại, đăng xuất, hết phiên và xác minh hai bước hoạt động đúng; không tạo hai React root hoặc hai hộp thoại.

### Đợt 2 Lịch hẹn và khách hàng

1. Chuyển `/admin/appointments`: danh sách, tìm kiếm, bộ lọc ngày/trạng thái, phân trang, thống kê cùng phạm vi lọc và xem chi tiết.
2. Chuyển tạo/sửa lịch, kiểm tra giờ và nhân viên trống, phân nhân viên, khách đến, xác nhận, hủy, hoàn thành; hiển thị các thao tác theo đúng trạng thái.
3. Giữ đặt nhiều dịch vụ, dùng đúng lượt gói/quà tặng, báo giá và kết quả khi dữ liệu vừa thay đổi. Xử lý đối soát khi gửi xong nhưng mất phản hồi.
4. Chuyển `/admin/customers`: tìm, tạo nhanh, thêm/sửa, trạng thái khách và hồ sơ có lịch sử dịch vụ, lịch hẹn, liệu trình theo quyền thực tế.

Điều kiện xong: lễ tân/quản lý xử lý được một hành trình khách hoàn chỉnh trên giao diện mới; tránh đặt trùng và lộ hồ sơ ngoài quyền.

### Đợt 3 Hóa đơn và bán gói

1. Chuyển `/admin/invoices`: danh sách dịch vụ/gói, bộ lọc, chi tiết, số phải trả, số đã thu, giảm giá/điểm/voucher và in chứng từ.
2. Chuyển `/admin/package-sales`: tìm khách, chọn gói, tạo giao dịch, thu tiền mặt/tiền thừa, QR và theo dõi trạng thái.
3. Tái sử dụng luồng thanh toán/đối soát hiện có; tải lại hoặc mất kết nối không tạo giao dịch, kích hoạt liệu trình hoặc ghi doanh thu lặp.

Điều kiện xong: nghiệp vụ hóa đơn và bán gói tương đương bản cũ; thử thanh toán bằng dữ liệu/provider giả lập trước, việc đối soát thật theo quy trình vận hành.

### Đợt 4 Danh mục và liệu trình

1. Chuyển dịch vụ: danh sách, tìm/lọc, ảnh, nhóm dịch vụ, thời lượng, giá, trạng thái và nội dung chăm sóc sau dịch vụ.
2. Chuyển danh sách/tạo/sửa/chi tiết gói: ảnh, thành phần, số buổi, giá và hạn sử dụng.
3. Chuyển quản lý liệu trình khách: lượt khả dụng/đang giữ/đã dùng, quà tặng và lịch sử sử dụng. Tách rõ cấu hình gói bán với quyền sử dụng của từng khách.
4. Giữ liên kết như `/admin/packages/<id>/edit` và `#treatments` hoạt động đúng.

Điều kiện xong: thêm/sửa danh mục và quản lý lượt liệu trình đầy đủ; upload ảnh, nội dung dài và lỗi nhập liệu hiển thị tốt trên mobile.

### Đợt 5 Nhân sự và lịch làm

1. Chuyển nhân viên và chức vụ: thông tin, ảnh, quyền, trạng thái và đơn giá; tích hợp xác minh hai bước cho thao tác được bảo vệ.
2. Chuyển ca làm và duyệt đăng ký ca: tìm/lọc theo ngày, danh sách/lịch, tạo/sửa ca, quyết định duyệt/từ chối và lịch cá nhân.
3. Đối chiếu các trang lịch làm/đăng ký ca cá nhân còn nằm dưới `/admin`; dùng chung màn hoặc chuyển hướng sang trang nhân viên khi đã đủ chức năng.
4. Gom điều hướng công, yêu cầu công, kỳ công và bảng lương; trình bày lý do chưa thể khóa kỳ cùng đường dẫn xử lý.
5. Bảng lương GPS là luồng chính theo mốc 01/10/2026 đã thống nhất. Dữ liệu lương trước mốc được xem qua lịch sử phù hợp; tránh tạo thêm hai luồng nhập/tính lương cùng kỳ.

Điều kiện xong: quyền thực tế ở API được giữ nguyên, phiên xác minh không tăng quyền hoặc đổi phạm vi cơ sở, snapshot lương đã khóa vẫn ổn định.

### Đợt 6 Chăm sóc và hoàn thiện tổng quan

Đã triển khai 17/10/2026. Các API nghiệp vụ hiện có được giữ lại; màn chăm sóc dùng `ADMIN_CARE_REACT_ENABLED`. Kiểm thử bằng dữ liệu và nhà cung cấp giả lập; xem bằng chứng và giới hạn ở tài liệu kết quả.

1. Chuyển điểm thưởng, hạng thành viên, quà/voucher, đổi quà và giao dịch điểm theo đủ quyền hiện có.
2. Chuyển đánh giá khách và tin nhắn: danh sách, chi tiết, tìm kiếm, trạng thái đọc và luồng gửi đang có. Thử bằng tài khoản/dữ liệu giả lập, không gửi tin cho khách thật từ công cụ kiểm thử.
3. Hoàn thiện tổng quan: các KPI/biểu đồ còn thiếu, số liệu chi tiết và tóm tắt kinh doanh AI; đưa các tính năng hiện còn mở qua dashboard cũ sang màn mới.
4. Chuẩn hóa các trang không có quyền, không tìm thấy, lỗi và các liên kết điều hướng còn sót.

Điều kiện xong: menu quản trị mặc định không còn đưa người dùng về giao diện cũ để hoàn thành một nghiệp vụ.

### Đợt 7 Nghiệm thu và chuyển hoàn toàn

1. Đối chiếu toàn bộ bảng URL/chức năng/quyền với bản cũ, kể cả các trang tạo/sửa/chi tiết, cửa sổ in và các liên kết có query/hash.
2. Kiểm thử API, luồng giao diện và hồi quy PostgreSQL/SQLite. Thử vai trò admin, quản lý, lễ tân, nhân viên; quyền ở máy chủ là căn cứ cuối cùng.
3. Kiểm tra 360/390/768/1024/1440 px, bàn phím, focus, biểu mẫu, bảng rộng, Drawer/Modal, phiên hết hạn, mất mạng và request đồng thời.
4. Kiểm tra các hành trình: lịch hẹn → dùng liệu trình/thu tiền → hoàn thành; ca → chấm công → duyệt → chốt lương; thay quyền → xác minh lại; tin nhắn → chuyển trang → quay lại.
5. Bật theo từng nhóm màn bằng cờ cấu hình. Trong thời gian chuyển đổi, có đường quay lại được kiểm soát để xử lý lỗi; menu sử dụng thông thường ưu tiên bản mới.
6. Sau khi đủ chức năng, kiểm thử đạt và vận hành ổn định, gỡ liên kết mở bản cũ, ngừng render các trang cũ đã thay thế, rồi dọn CSS/JS/template hết sử dụng. Giữ các mẫu in/xuất còn được nghiệp vụ sử dụng.

Điều kiện xong: toàn bộ đường quản trị trong sử dụng thông thường dùng cùng giao diện mới; không còn tác vụ buộc mở trang cũ; có tài liệu vận hành và cách quay lại bản phát hành trước khi cần.

## Quy tắc triển khai và nghiệm thu từng đợt

- Mỗi đợt có danh sách màn/chức năng cụ thể, ảnh desktop/mobile, các kiểm thử liên quan và ghi chú phần chưa chuyển. Chỉ chuyển mặc định khi đã đủ nghiệp vụ của nhóm đó.
- Thêm/sửa form có kiểm tra dữ liệu, chống gửi lặp và xử lý thay đổi chưa lưu. Xác minh hai bước giữ dữ liệu đang nhập; hủy xác minh không ghi nghiệp vụ.
- Dữ liệu và API đang vận hành được bảo toàn. Nếu cần thay hợp đồng API/schema, bổ sung kế hoạch tương thích/migration riêng trước khi áp dụng; không gắn việc đổi giao diện với tự sửa chính sách công/lương.
- Kiểm thử giao dịch trên DB riêng và provider giả lập. Sao lưu trước các thay đổi dữ liệu hoặc migration cần thiết.
- Cổng khách hàng, AI đang trả lời và cổng nhân viên có hành trình hồi quy riêng để phát hiện ảnh hưởng từ asset/auth dùng chung.

## Bước triển khai tiếp theo

Tiếp theo là Đợt 7: nghiệm thu xuyên suốt các nhóm đã chuyển; kiểm tra liên kết, quyền, mạng chập chờn, bàn phím và thiết bị thật. Chỉ dọn giao diện dự phòng sau khi nhóm màn tương ứng đạt nghiệm thu. Việc hoàn thành Đợt 6 không thay thế nghiệm thu production, GPS thực địa hoặc đối soát lương thực tế trong kế hoạch Word.

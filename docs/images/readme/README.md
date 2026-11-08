# Bộ ảnh giao diện Bin Spa

Ảnh chụp ngày **08/11/2026** từ ứng dụng đang chạy ở bản phát triển, không phải mockup. Bộ ảnh phục vụ README và giới thiệu đồ án.

## Môi trường và dữ liệu

- Chạy trên loopback với **SQLite riêng trong bộ nhớ**; không kết nối hay thay đổi database spa đang sử dụng.
- Tên người, tài khoản, số điện thoại, lịch hẹn và doanh thu là **dữ liệu minh họa do công cụ chụp tạo**. Email dùng miền `example.com`; không lấy thông tin cá nhân từ database thật.
- Dùng ảnh và thành phần có sẵn của dự án. Không phát sinh giao dịch ngân hàng, gửi email hoặc gọi AI bên ngoài để tạo bộ ảnh.
- Ảnh phản ánh bản phát triển có cải tiến mới về ưu đãi dịch vụ và đối chiếu chấm công. Nhánh `main` có thể chưa bao gồm toàn bộ thay đổi đó; cập nhật tài liệu/ảnh không đồng nghĩa phát hành tính năng hoặc nghiệm thu toàn hệ thống.
- PNG chụp trực tiếp bằng Playwright CLI. Màn hình desktop **1440 px**, mobile **390 px**. Bấm ảnh trong README để mở bản đầy đủ.

## Danh mục

| Ảnh | Nội dung |
| --- | --- |
| [01-customer-home.png](01-customer-home.png) | Trang chủ và trải nghiệm khách hàng. |
| [02-service-catalog.png](02-service-catalog.png) | Danh mục, tìm kiếm và giá dịch vụ. |
| [03-customer-booking.png](03-customer-booking.png) | Chọn dịch vụ và tóm tắt lịch hẹn. |
| [04-admin-dashboard.png](04-admin-dashboard.png) | Tổng quan công việc và lịch phục vụ. |
| [05-admin-appointments.png](05-admin-appointments.png) | Quản lý lịch hẹn, nhân viên và trạng thái. |
| [06-service-discounts.png](06-service-discounts.png) | Mức giảm, đối tượng và giới hạn thời gian. |
| [07-attendance-requests.png](07-attendance-requests.png) | Giờ đề nghị, giờ thực tế và ca được xếp. |
| [08-attendance-review.png](08-attendance-review.png) | Bảng công và trạng thái duyệt. |
| [09-mobile-booking.png](09-mobile-booking.png) | Đặt lịch trên điện thoại. |
| [10-mobile-attendance.png](10-mobile-attendance.png) | Yêu cầu chấm công trên điện thoại. |

Khi thay ảnh, chụp lại từ dữ liệu demo riêng, đợi tải xong dữ liệu/phông chữ/ảnh và kiểm tra console, request thất bại, bố cục, trạng thái tải cùng thông tin xuất hiện trong ảnh trước khi commit.

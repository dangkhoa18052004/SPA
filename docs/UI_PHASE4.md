# Giai đoạn 4 — Dashboard theo vai trò và đặt lịch khách hàng

Triển khai tiếp mục 9 của `BinSpa_KeHoach_NangCap_GPS_ChamCong_UI_Refactor.docx` sau cổng công/lương.

## Màn hình đã triển khai

| Đường dẫn | Nội dung |
| --- | --- |
| `/admin/dashboard` | React + Ant Design, lấy vai trò hiện tại từ API, menu công việc, lịch hôm nay, tìm kiếm/lọc/xóa bộ lọc, thẻ lịch cho màn hình dưới 1100 px. |
| Admin / quản lý | Lịch chung, thực thu dịch vụ + bán gói theo khoảng ngày, biểu đồ và bảng số liệu chi tiết, liên kết duyệt công/lương. |
| Lễ tân | Lịch chung và thao tác nghiệp vụ tại quầy. Không gọi các API thực thu. |
| Nhân viên | Lịch của chính nhân viên; không gọi lịch chung hoặc báo cáo doanh thu. Liên kết lịch khách, chấm công, thu nhập, liệu trình, đánh giá và hồ sơ. |
| `/appointments/create` | React + thành phần shadcn/ui được quản lý trong repository, Tailwind riêng: dịch vụ/gói/quà tặng → ngày, giờ trống, nhân viên → ghi chú, kiểm tra và xác nhận. |

Nghiệp vụ tiếp tục dùng API/service hiện có. Giá gửi lên máy chủ không lấy từ tổng tiền do trình duyệt tính. Gói/quà tặng được giữ buổi chính xác bằng `the_item_id`; phần dịch vụ trả tiền mới tạo hóa đơn trả trước. Sau đặt lịch, VietQR dùng hộp thanh toán hiện tại để giữ luồng áp điểm/voucher, cập nhật QR và xác nhận thanh toán. Hóa đơn chưa trả không tính vào thực thu.

Giờ/ngày của dashboard thống nhất theo Việt Nam kể cả khi server chạy UTC. Quyền API vẫn kiểm tra tài khoản và vai trò từ database, không tin vai trò lưu trên trình duyệt.

## Tình huống ngoại lệ

- Liên kết `service`, `treatment`, `item` được giữ khi chuyển đăng nhập. Liên kết cả liệu trình có danh sách dịch vụ khả dụng; không tự đổi một quà tặng hết hạn sang lượt gói trả tiền.
- Chọn lại dịch vụ/ngày/giờ sẽ xóa lựa chọn thời gian hoặc nhân viên cũ. Giờ và nhân viên được kiểm tra lại trước màn xác nhận; máy chủ kiểm tra lại khi đặt.
- Giữ nguyên lựa chọn lượt gói khi thay đổi ngày sang ngoài hạn sử dụng và yêu cầu người dùng chọn lại; không âm thầm tính giá bán lẻ.
- Không cho gửi hai lần hoặc sửa thông tin trong lúc gửi. Nếu mất phản hồi, lưu dấu lần gửi trong `sessionStorage`, kể cả sau khi tải lại. Nút kiểm tra đối chiếu lịch mới của chính khách với danh sách trước lần gửi; không tự gửi lại POST. Chưa đối soát được thì hướng khách đến lịch của mình hoặc liên hệ spa.
- Lỗi tải danh mục/giờ/nhân viên có trạng thái và nút thử lại. Khách chưa đăng nhập có nút đăng nhập kèm địa chỉ quay lại.
- Danh mục đặt lịch dùng thẻ có ảnh, tên, giá và thời lượng, **6 dịch vụ/trang**; ảnh thiếu hoặc lỗi dùng ảnh mặc định. Nút Trước/Sau đưa về đầu danh sách. Đổi trang, tìm kiếm hoặc lọc nhóm vẫn giữ dịch vụ và lượt liệu trình đã chọn; đổi bộ lọc đưa về trang đầu.
- Chỉ hiện giờ được API xác nhận còn trống và chưa qua theo giờ Việt Nam. Kiểm tra đồng hồ mỗi 30 giây và khi quay lại tab: giờ vừa qua bị ẩn, lựa chọn hết hạn được xóa. Ngày hết chỗ có thông báo và gợi ý ngày khác nếu có; vẫn kiểm tra lại giờ/nhân viên trước xác nhận và trên máy chủ khi đặt.

## Build, bật và quay lại giao diện cũ

```powershell
cd E:\Project\Spa\SPA
npm --prefix frontend ci
npm --prefix frontend run build
```

Hai entry Vite riêng: `src/main.tsx` (Ant Design), `src/booking-main.tsx` (khách hàng). CSS Tailwind không được tải vào màn hình quản trị/công lương. Manifest được kiểm tra trước khi render; thiếu bản build sẽ sử dụng trang Jinja hiện có.

Trong `.env`:

```dotenv
BUSINESS_PORTAL_ENABLED=true
CUSTOMER_BOOKING_REACT_ENABLED=true
```

Khởi động lại Flask để đọc cấu hình mới. Không cần migrate database cho giai đoạn này. Các cờ nguồn và `.env.example` mặc định `false`; bản cài đặt tại máy này được bật sau kiểm thử. Để quay lại, đặt cờ tương ứng thành `false` và khởi động lại. Có thể mở ngay `/admin/dashboard?ui=legacy` hoặc `/appointments/create?ui=legacy` để đối chiếu giao diện cũ; giữ thêm các tham số gói/dịch vụ trong URL nếu cần.

Các màn quản lý lịch/hóa đơn/bán gói/danh mục, hồ sơ khách và báo cáo AI hiện có vẫn được liên kết từ giao diện mới. Không xóa trang cũ trước khi có đánh giá vận hành theo kế hoạch.

## Kiểm thử

```powershell
npm --prefix frontend test
venv\Scripts\python.exe -m pytest -q tests/test_phase4_ui.py tests/test_booking_time_slots.py tests/test_booking_gifts_reviews.py tests/test_prepay_booking.py tests/test_phase2_analytics_review.py tests/test_analytics_package_revenue.py
venv\Scripts\python.exe tests/phase4_browser_check.py
venv\Scripts\python.exe tests/booking_catalog_browser_check.py
```

Chrome thực chạy ẩn trên SQLite riêng, mail giả lập, webhook thanh toán giả lập. Kiểm tra bốn vai trò ở 360/390/768/1440 px, không tràn ngang/không lỗi JavaScript, tìm/xóa bộ lọc, số thực thu gồm gói/dịch vụ, liên kết quà tặng, đặt gói + quà tặng, mất phản hồi rồi tải lại và đối soát, hóa đơn VietQR chưa trả → đã trả, đăng nhập quay về liên kết đúng. Ảnh lưu ở `.test-tmp/phase4-browser-*`. Không đặt lịch hoặc ghi thanh toán vào dữ liệu cơ sở đang vận hành.

Kết quả tại máy phát triển ngày 15/10/2026: build production thành công; **660 kiểm thử Python đạt** trên PostgreSQL tạm riêng và SQLite, **8 kiểm thử frontend đạt**; hành trình Chrome giai đoạn 4 đạt, gồm kiểm tra hộp thanh toán ở bốn kích thước màn hình và 41 ảnh. Bộ kiểm thử PostgreSQL tạm đã dừng server sau khi chạy xong.

Workflow CI đã thêm build, kiểm thử frontend và hành trình Chrome cho giai đoạn này. CI trên máy chủ chưa được kích hoạt bằng push trong phiên này.

Cập nhật danh mục/giờ đặt lịch ngày 15/10/2026: build đạt, **10 kiểm thử frontend đạt**. Chrome kiểm tra 13 dịch vụ chia 3 trang, giữ lựa chọn qua trang/bộ lọc, ảnh lỗi, giờ đã qua/kín lịch, giờ hết hạn khi đang mở trang và ngày không còn chỗ ở 360/390/768/1440 px; thiết bị thử đặt múi giờ Mỹ để kiểm tra giờ Việt Nam. Hành trình gói/quà tặng, đối soát mất phản hồi và thanh toán VietQR cũng đã chạy lại thành công.

## Các giai đoạn tiếp theo

Phần này hoàn thành dashboard và cụm đặt lịch của giai đoạn 4. Giai đoạn 5 được triển khai tiếp tại [Đề xuất dịch vụ và CRM](RECOMMENDATION_CRM_PHASE5.md). Còn giai đoạn 6 (BI, hardening, phát hành), cùng việc chuyển các cụm Jinja còn lại khi đã đạt tương đương nghiệp vụ và được thử ở môi trường vận hành; chưa đánh dấu hoàn thành toàn bộ tài liệu.

Tài liệu kỹ thuật áp dụng: [shadcn/ui Button](https://ui.shadcn.com/docs/components/radix/button), [Tailwind với Vite](https://tailwindcss.com/docs/installation/using-vite).

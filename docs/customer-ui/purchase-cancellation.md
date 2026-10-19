# Hủy yêu cầu mua gói chưa thanh toán — 19/10/2026

Theo yêu cầu người dùng, bổ sung lựa chọn bỏ các đơn không muốn mua nữa trong “Liệu trình của tôi”. Trước đây danh sách chỉ có “Tiếp tục thanh toán”; chưa có API khách hàng hủy purchase.

## Hành vi

- Mỗi đơn `pending` có “Tiếp tục thanh toán” và “Hủy mua gói”, ở cả legacy đang hiển thị trong ảnh người dùng và renderer refactor sau account gate.
- Hủy mở native dialog, ghi rõ tên gói, xử lý điểm/voucher đang giữ và lưu ý đối soát nếu đã chuyển tiền. Mặc định focus “Giữ lại”; chọn giữ lại/ESC không gửi API. Khi đang gửi, khóa thao tác lặp.
- Chỉ sau server xác nhận mới tải lại danh sách và báo thành công. Đơn đã hủy không xuất hiện lại khi reload; hủy một đơn không hủy các đơn còn lại hoặc liệu trình đã kích hoạt.
- Lỗi hiển thị ngay trong dialog, có thể thử lại. Nếu trạng thái đã thay đổi do thanh toán hoàn tất, server từ chối hủy và UI tải lại danh sách chờ.
- Mở lại URL purchase đã hủy chỉ hiển thị trạng thái kết thúc; không dựng QR/điểm/voucher hoặc đề nghị thanh toán tiếp. Polling cũng chuyển sang trạng thái kết thúc khi server báo đã hủy.

## Backend

`POST /api/packages/purchases/<id>/cancel` yêu cầu khách đăng nhập và sở hữu đơn. Dùng target-row lock hiện có của loyalty, cùng cơ chế khóa với xác nhận thanh toán. `pending` được trả điểm/voucher đang giữ trước khi chuyển `cancelled`; mọi thao tác chung một transaction. Lỗi giữa chừng rollback toàn bộ. Lặp lại đơn `cancelled` thành công mà không hoàn điểm lần hai. Đơn paid/failed bị từ chối; sai chủ hoặc ID không tồn tại trả 404.

Giữ bản ghi giao dịch ở trạng thái `cancelled` để đối soát; không hard-delete dữ liệu thanh toán. Voucher hết hạn trở về `expired`, voucher còn hạn trở về `available`; không hoàn lại điểm đã chi để đổi voucher vì voucher vẫn thuộc khách. Không sửa schema hoặc thêm migration: trạng thái cancelled đã có sẵn.

## File thay đổi của yêu cầu này

- `app/services/package_service.py`: hàm hủy dùng target lock và trả ưu đãi.
- `app/routes/package_bp.py`: route hủy có quyền sở hữu.
- `app/static/js/packages.js`: confirmation, pending legacy/refactor, retry và guard purchase đã kết thúc.
- `app/static/css/packages.css`: các action và dialog, màu chữ rõ, control tối thiểu 44px.
- `app/templates/customer/profile.html`: vùng thông báo kết quả.
- `frontend/src/customer/treatments.ts`, `treatments.test.ts`: nút hủy cho renderer mới; chỉ pending có action.
- `tests/test_package_purchase_cancel.py`, `tests/customer-purchase-cancel.playwright.js`: kiểm tra backend/browser.
- `docs/customer-ui/contracts.md`, `progress.md`, `qa-results.md`, tài liệu này: hợp đồng và bằng chứng.

Giữ nguyên các thay đổi chưa commit của những lượt trước, bao gồm `requirements-dev.txt`.

## Kiểm chứng

- Build PASS; Vitest 69 PASS; Node 49 PASS.
- Backend: 71 ca hồi quy loyalty payment/sale channels PASS; nhóm hủy riêng 10 PASS: quyền guest/staff/sai chủ/ID không tồn tại, hủy bền vững và lặp lại, trả điểm/voucher còn hạn/hết hạn, bảo vệ đơn paid, thanh toán đến sau hủy không kích hoạt liệu trình và rollback khi trả voucher lỗi. Kết quả chạy cuối xem `pytest-cancel-final.log`.
- Lượt chạy gộp đầu có một ca fixture paid thiết lập sai; đã sửa test để thanh toán đúng purchase đang kiểm tra và chạy lại toàn bộ nhóm hủy. Không thay assertion hoặc logic ứng dụng để bỏ qua trạng thái paid.
- Browser chạy fixture thực ở loopback, tạo/hủy purchase trong SQLite thử nghiệm: cả legacy/refactor, 360/390/768/1024/1440px. PASS giữ lại không POST, bấm lặp chỉ POST một lần, hủy bền vững sau reload, giữ đơn khác, lỗi 503/thử lại và URL đã hủy không còn thanh toán. Không uncaught JS exception hoặc failed request.
- Browser E06 chạy lại PASS; 106 phần tử chữ/viewport, tương phản tối thiểu 4,71:1; không tràn ngang.
- Trên LAN chỉ gửi OPTIONS, xác nhận route trả 200 với `Allow: OPTIONS, POST`. Không gửi lệnh hủy hoặc thay đổi đơn thật. Không restart máy chủ/deploy/thay flag trong lượt này; OPTIONS không thay thế kiểm chứng giao dịch thật.

Log/ảnh ignored ở `.test-tmp/customer-purchase-cancel/`: `browser.json`, `confirm-legacy-390.png`, `confirm-refactor-1440.png`, `pytest-final.log`, `pytest-cancel-final.log`, `treatments-regression.json`, `build.log`, `vitest.log`, `node.log`. Chưa chạy lại full pytest, CI hosted hoặc kiểm tra cạnh tranh transaction trên PostgreSQL.

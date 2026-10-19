# E08 — Đánh giá của khách hàng

Hoàn thiện và kiểm chứng ngày 19/10/2026, theo E08 trong `refactorUI_Customer.md`.

## Hành vi sau thay đổi

- Danh sách có số lượng, tải lại, loading, trạng thái rỗng kèm liên kết tới lịch hẹn, lỗi và thử lại. Hiển thị dịch vụ, số sao, nhận xét và phản hồi từ spa bằng font/màu chung; nội dung API được escape.
- Form tạo/sửa có lựa chọn dịch vụ đã sử dụng, nhóm sao dùng bàn phím, hướng dẫn nhận xét không bắt buộc, giới hạn/bộ đếm 5.000 ký tự. Không chọn dịch vụ thì hiển thị lỗi trước khi gửi; backend vẫn xác minh quyền, trạng thái lịch và dịch vụ.
- Khi đang gửi, khóa control và chặn submit lặp; không đóng dialog bằng ESC/backdrop trong lúc chờ kết quả. Mỗi yêu cầu có giới hạn 20 giây, hết thời gian trả lại điều khiển và yêu cầu tải lại để kiểm tra kết quả. Lỗi giữ lựa chọn/nhận xét để sửa và thử lại; phản hồi không hợp lệ/mất kết nối có thông báo dễ hiểu. Không tự động gửi lại POST/PUT/DELETE.
- Xóa dùng dialog có nút Giữ đánh giá được focus trước, nút xóa phân biệt bằng màu; chặn click lặp, lỗi tại chỗ và retry. Đóng dialog trả focus về nút mở nếu còn, hoặc tab đang chọn nếu danh sách đã được thay.
- Sau tạo/sửa/xóa thành công, tải lại danh sách/summary hiện diện trên trang, thông báo kết quả và phát `reviews-updated` để lịch hẹn cập nhật. Bỏ response danh sách cũ; context trả về muộn không mở lại dialog đã đóng.
- Giữ `ReviewUI` và một owner JS cho mỗi vùng. Style mới áp dụng customer legacy/refactor và vùng đánh giá công khai; giao diện phản hồi admin giữ style riêng. Không đổi API, quyền, schema, dependency hoặc cấu hình máy chủ.

## File thay đổi trong E08

| File | Nội dung |
|---|---|
| `app/static/js/reviews.js` | Trạng thái list/context/mutation, xác nhận xóa, editor/counter, keyboard/focus và tải lại public |
| `app/static/css/reviews.css` | Style customer scoped, font/màu/contrast, responsive và focus |
| `app/templates/customer/profile.html` | Header, tải lại, số lượng, thông báo và list Đánh giá |
| `tests/customer-ui-reviews.playwright.js` | Fixture tương tác/lỗi/race, style/layout và cập nhật public trên cả hai shell |
| `tests/booking_gifts_reviews_browser.py` | Chờ editor/detail sau context loading; xác nhận xóa mới; màu nút Đóng theo token customer; giữ kiểm chứng API/DB |
| `docs/customer-ui/progress.md`, `contracts.md`, `qa-results.md`, `reviews-refactor.md` | Checkpoint, ownership, kết quả và giới hạn |

Các thay đổi của các giai đoạn trước và `requirements-dev.txt` đã có sẵn được giữ nguyên.

## Kết quả kiểm tra

| Lệnh / suite | Kết quả |
|---|---|
| `python -m pytest tests/test_booking_gifts_reviews.py tests/test_phase2_analytics_review.py tests/test_ui_navigation_and_ratings.py -q --disable-warnings --tb=short` | 44 PASS; 857 warnings |
| `node --test tests/*.test.cjs` | 50 PASS |
| `node --check app/static/js/reviews.js` | PASS |
| Playwright CLI `tests/customer-ui-reviews.playwright.js` | PASS; 50 tổ hợp style/layout trên legacy/refactor và 5 viewport |
| `python tests/booking_gifts_reviews_browser.py` | PASS trên Edge với API/SQLite fixture; CRUD, liên kết dịch vụ, phản hồi staff/admin, public statistics, HTML an toàn, gói/quà và mobile |

Playwright chủ động trả lỗi 400/403/503 và giữ response chậm để kiểm tra retry, giữ draft và stale response. Tạo mới chỉ gửi 1 POST dù submit hai lần; sửa lỗi giữ draft rồi retry; xóa lỗi không thay danh sách rồi retry đúng một DELETE. Giữ một PUT không trả phản hồi suốt 20 giây để xác minh timeout: đúng 1 request, bản nháp còn nguyên, form và nút đóng hoạt động lại. Sau sửa từ trang dịch vụ, số sao/nhận xét/summary public cập nhật ngay mà không reload trang. Không có uncaught exception hoặc network failure ngoài request bị chủ động abort khi timeout; HTTP 400/403/503 là phản hồi lỗi chủ động của fixture.

50 tổ hợp gồm list, editor sửa, editor tạo với nhiều dịch vụ, xác nhận xóa, và vùng public tại 360/390/768/1024/1440px trên 2 shell. Font và màu chữ/nền được đo; tối thiểu 4,71:1 ở chữ đã kiểm tra, không tràn ngang, dialog căn giữa. Đã xem ảnh desktop/mobile. Đây không phải chứng nhận accessibility đầy đủ hoặc kiểm tra bàn phím/zoom trên thiết bị thật.

Bằng chứng tại `.test-tmp/customer-ui-reviews/`: `browser.json`, `pytest.log`, `node.log`, `regression-browser.log`, `refactor-list-1440.png`, `refactor-editor-390.png`, `refactor-create-390.png` và các ảnh tương ứng của legacy/viewport khác. Hồi quy cũ ban đầu còn kỳ vọng nút Đóng màu đen; đã cập nhật theo token xanh mới và chạy lại thành công, không nới kiểm tra CRUD/số sao/quyền.

Chỉ tạo/sửa/xóa dữ liệu thử nghiệm ở loopback; không thao tác đánh giá khách thật trên LAN. Không deploy, bật flag hoặc restart máy chủ. Full pytest, Vitest và Vite build không chạy lại trong E08 vì không thay source bundle frontend. Phần tinh chỉnh tiếp theo theo kế hoạch là E09 — Thông báo và quyền riêng tư.

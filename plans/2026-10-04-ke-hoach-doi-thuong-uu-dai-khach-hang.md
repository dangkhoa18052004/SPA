# Kế hoạch phát triển Đổi thưởng và Ưu đãi của tôi

- Dự án: Bin Spa.
- Ngày lập: 04/10/2026, múi giờ Asia/Saigon.
- Trạng thái: Đã triển khai phiên bản đầu ngày 04/10/2026 — xem mục 11.
- Cơ sở: đối chiếu mã nguồn Loyalty, trang hồ sơ khách hàng, màn hình thanh toán và bộ kiểm thử hiện tại.

## 1. Yêu cầu và phạm vi

| Mã | Yêu cầu của người dùng | Kết quả cần đạt |
| --- | --- | --- |
| YC01 | Phát triển chức năng **Đổi thưởng** | Khách hiểu quyền lợi, số điểm cần đổi, điều kiện; xác nhận trước khi đổi; nhận kết quả rõ ràng và được bảo vệ khỏi đổi/trừ điểm trùng. |
| YC02 | Phát triển chức năng **Ưu đãi của tôi** | Khách dễ tìm ưu đãi đã đổi, biết trạng thái/hạn sử dụng và cách dùng voucher hoặc nhận quà. |
| YC03 | Loại bỏ **Điểm đang giữ** khỏi giao diện khách hàng | Không hiển thị ô, nhãn hay số điểm đang giữ ở hồ sơ, đổi thưởng, ưu đãi và thanh toán của khách hàng. |
| YC04 | Lập bảng kế hoạch, lưu trong `plans` | Tài liệu này nêu hiện trạng, đầu việc, thứ tự triển khai, tệp liên quan và tiêu chí nghiệm thu. |

Các chi tiết UX bên dưới là phương án đề xuất để cụ thể hóa YC01–YC03. Yêu cầu hiện tại là lập kế hoạch; chưa đổi giao diện, API, database hoặc chính sách điểm thưởng.

**Phương án cho phiên bản đầu:** tiếp tục dùng khu vực Điểm thưởng tại `/profile#loyalty`, nâng cấp hai tab Đổi thưởng và Ưu đãi của tôi; giữ hai loại quà hiện có là voucher giảm số tiền cố định và quà nhận tại cửa hàng.

## 2. Hiện trạng đã kiểm tra

| Hạng mục | Đã có trong source | Khoảng cần phát triển |
| --- | --- | --- |
| Ví điểm khách hàng | `available_points`, `reserved_points`, tổng đã tích, tổng đã dùng; giao diện hiện bốn chỉ số. | Bỏ chỉ số điểm đang giữ khỏi giao diện khách; điều chỉnh bố cục còn ba chỉ số. |
| Danh mục đổi thưởng | API phân trang quà active; hiển thị tên, mô tả, điểm đổi, giá trị, thời hạn; khóa nút khi thiếu điểm/hết quà. | Bổ sung tìm kiếm/lọc, xem chi tiết, xác nhận trước khi đổi và trạng thái tải/lỗi rõ ràng. |
| Xử lý đổi thưởng | Kiểm tra điểm/tồn kho, khóa dữ liệu, trừ điểm, lưu snapshot, giảm tồn kho và chống trùng bằng idempotency key. | Hoàn thiện trải nghiệm gửi lại khi mất mạng/reload; cập nhật ví, catalog và ưu đãi sau thao tác. |
| Ưu đãi của tôi | Danh sách phân trang gồm mã, tên, trạng thái, hạn dùng; voucher và quà vật lý có hướng dẫn chung. | Bổ sung lọc trạng thái/loại, chi tiết ưu đãi, sao chép mã và hướng dẫn theo trạng thái. |
| Thanh toán | Voucher và điểm dùng được với hóa đơn dịch vụ/giao dịch mua gói; có áp dụng/bỏ ưu đãi. Component hiện hiển thị số điểm đang giữ cho cả khách và nhân viên. | Tách phần trình bày theo ngữ cảnh customer/admin; khách không còn thấy điểm đang giữ nhưng vẫn thấy điểm áp dụng cho giao dịch và tiền được giảm. |
| Nhận quà | Nhân viên có API xác nhận bàn giao quà, ghi người bàn giao và thời điểm. | Hiển thị rõ hướng dẫn nhận quà, trạng thái đã nhận và thời điểm trên phía khách. |
| Hết hạn | Serializer suy ra `expired` cho ưu đãi `available` đã quá hạn; trạng thái lưu trong DB có thể vẫn là `available`. | Bộ lọc và tổng số kết quả phải dùng trạng thái hiệu lực thống nhất trước khi phân trang. |

## 3. Quy tắc về việc bỏ Điểm đang giữ

| Nội dung | Quy tắc triển khai |
| --- | --- |
| Trang Điểm thưởng | Hiển thị **Điểm khả dụng**, **Tổng điểm đã tích**, **Tổng điểm đã dùng**. Loại bỏ card “Điểm đang giữ”. |
| Thanh toán của khách | Chỉ hiển thị số điểm khả dụng và thông tin áp dụng cho giao dịch, ví dụ “Dùng 100 điểm · Giảm 100.000đ”. Không hiển thị số dư điểm đang giữ. |
| Nguồn số dư | Dùng `available_points` do backend trả về. Không cộng `reserved_points` vào số điểm khách có thể dùng. |
| Ví dụ nghiệm thu | Ví có 300 điểm khả dụng và 100 điểm đang giữ: khách thấy **300 điểm khả dụng**, không thấy chỉ số 100 điểm đang giữ và không thể chi tiêu 400 điểm. |
| Logic nội bộ | Giữ `reserved_points` và cơ chế reserve/release/consume để chống dùng một số điểm cho nhiều giao dịch. Đóng modal/reload không tự hoàn điểm; thao tác bỏ điểm và xử lý giao dịch tiếp tục theo nghiệp vụ hiện tại. |
| API | Chưa cần xóa field khỏi API chỉ để ẩn UI. Giữ tương thích với component và phía quản trị; nếu tách serializer customer thì phải rà soát đầy đủ consumer trước. |
| Quản trị/nhân viên | Giữ thông tin điểm đang giữ để đối soát. Component dùng chung phân biệt customer/admin theo ngữ cảnh màn hình; phân quyền dữ liệu vẫn do backend kiểm tra. |
| Trạng thái voucher | Voucher đang gắn với thanh toán có nhãn **Đang áp dụng**. Đây là trạng thái ưu đãi, không phải chỉ số điểm đang giữ. |
| Phạm vi chữ “Đang giữ” | Không sửa “buổi đang giữ” của liệu trình/lịch hẹn: đó là dữ liệu buổi dịch vụ, nằm ngoài yêu cầu ẩn điểm. |

## 4. Bảng kế hoạch triển khai

Ưu tiên **P0**: bắt buộc để đáp ứng yêu cầu và bảo toàn nghiệp vụ. **P1**: nâng cấp trải nghiệm đề xuất cho phiên bản đầu. Chỉ nghiệm thu cả phiên bản sau khi các hạng mục đã chọn và kiểm thử tương ứng hoàn tất.

| STT | Giai đoạn / ưu tiên | Đầu việc | Cách thực hiện dự kiến | Phụ thuộc | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- | --- |
| 1 | Khảo sát / P0 | Chốt phạm vi và màn hình ảnh hưởng | Lập danh sách điểm xuất hiện của số dư, catalog, ưu đãi, thanh toán hóa đơn và gói; ghi nhận behavior hiện có. | — | Có checklist riêng cho customer và admin; phân biệt điểm với buổi liệu trình. |
| 2 | Ví điểm / P0 | Bỏ card Điểm đang giữ | Sửa render ví khách theo danh sách ba chỉ số được phép hiển thị; chỉnh bố cục responsive. | 1 | Khách không thấy card/nhãn/số điểm đang giữ; số điểm khả dụng không bị cộng thêm. |
| 3 | Thanh toán / P0 | Ẩn điểm đang giữ trong component dùng chung | Render phần số dư theo ngữ cảnh customer/admin; giữ tóm tắt điểm áp dụng, voucher và số tiền phải trả. | 1–2 | Hóa đơn dịch vụ và mua gói ở phía khách đều không lộ chỉ số đang giữ; admin vẫn đối soát được. |
| 4 | Đổi thưởng / P1 | Nâng cấp danh mục | Card quà rõ tên, loại, giá trị, điểm cần đổi, thời hạn, trạng thái còn/hết quà; tìm theo tên, lọc voucher/quà và đủ điểm. Lọc ở backend trước phân trang. | 1 | Không bỏ sót kết quả ở trang khác; thiếu điểm hiển thị “Cần thêm X điểm”; hết quà không đổi được. |
| 5 | Đổi thưởng / P0 | Xem chi tiết và xác nhận đổi | Dialog hiển thị quyền lợi, điểm cần dùng, điểm khả dụng dự kiến còn lại, hạn dùng, cách dùng/nhận quà; hai nút Hủy và Xác nhận đổi. | 2, 4 | Mở/đóng dialog không trừ điểm; khách chỉ đổi sau xác nhận rõ ràng. |
| 6 | Đổi thưởng / P0 | Hoàn thiện gửi yêu cầu và chống trùng | Tái sử dụng endpoint redeem và khóa giao dịch hiện có; giữ cùng idempotency key khi retry một thao tác chưa rõ kết quả, kể cả khôi phục sau reload. Backend luôn kiểm tra lại điểm, tồn kho và trạng thái quà. | 5 | Double-click/retry không tạo hai ưu đãi hay trừ điểm hai lần; đổi lần mới có chủ ý dùng key mới. |
| 7 | Đổi thưởng / P0 | Xử lý kết quả thành công/thất bại | Thành công cập nhật ví và tồn kho, chuyển tới ưu đãi vừa đổi; lỗi thiếu điểm/hết quà/ngừng đổi/mất mạng có thông báo và cách thử lại. | 6 | Không báo thành công trước phản hồi backend; không hiển thị số dư cũ sau khi đổi thành công. |
| 8 | Ưu đãi của tôi / P1 | Danh sách và bộ lọc | Tab mặc định ưu đãi có thể dùng; lọc theo trạng thái và loại; phân trang; thêm trạng thái rỗng phù hợp từng bộ lọc. | 1 | Đúng tổng số và số trang; trạng thái hết hạn theo thời gian backend, hiển thị ngày giờ Việt Nam. |
| 9 | Ưu đãi của tôi / P1 | Chi tiết, mã và hành động | Hiển thị snapshot quyền lợi, điểm đã đổi, mã, ngày đổi, hạn dùng và thời điểm dùng/nhận; cho sao chép mã; hướng dẫn áp dụng tại thanh toán hoặc nhận quà tại spa. | 8 | Sửa quà trong catalog không đổi quyền lợi đã đổi; sao chép có thông báo; mã không bị mô tả sai là coupon có thể nhập ở nơi chưa hỗ trợ. |
| 10 | Ưu đãi và thanh toán / P0 | Đồng bộ trạng thái xuyên suốt | Áp dụng voucher → Đang áp dụng; bỏ voucher → khả dụng/hết hạn; thanh toán → Đã sử dụng; bàn giao → Đã nhận quà. Refresh dữ liệu khi trở lại tab. | 3, 8–9 | Một voucher không áp dụng đồng thời hai giao dịch; refresh không đưa ưu đãi đã dùng về khả dụng. |
| 11 | API / P0 | Bổ sung khả năng đọc và lọc cần thiết | Mở rộng query params đã validate; thống nhất tính trạng thái hiệu lực. Chỉ thêm API chi tiết nếu dữ liệu danh sách không đủ; mọi truy vấn ưu đãi của tôi gắn với identity đăng nhập. | 4, 8–10 | Customer không đọc/dùng ưu đãi của người khác bằng cách đổi ID hoặc gửi `makh`; bộ lọc không chỉ hoạt động trên trang đang tải. |
| 12 | Giao diện / P1 | Hoàn thiện trải nghiệm | Tab đang chọn rõ ràng; ghi nhớ view qua URL theo cơ chế profile hiện tại; loading/error/empty state, chống phản hồi cũ ghi đè, nút disabled khi xử lý; kiểm tra mobile, bàn phím, focus và thông báo đọc được. | 2–11 | Reload trở về đúng tab; không nhân đôi request/thao tác; dùng được ở viewport 390px và desktop. |
| 13 | Kiểm thử / P0 | API, nghiệp vụ, UI và regression | Bổ sung các ca ở mục 8; chạy lại loyalty/payment/concurrency và regression liên quan package, booking, gift, billing. | 2–12 | Các ca nghiệm thu pass; số dư/tồn kho không âm, không double-spend, không làm sai payable. |
| 14 | Bàn giao / P0 | Tài liệu và phát hành | Ghi thay đổi, ảnh desktop/mobile, kết quả test và hướng dẫn vận hành. Rà soát cache asset; nếu có thay đổi schema thì thêm migration mới và kiểm tra head thực tế. | 13 | Có kết quả kiểm thử tái lập; dữ liệu ưu đãi cũ hiển thị đúng; tài liệu phát hành phản ánh đúng thay đổi. |

**Thứ tự thực hiện:** khảo sát → ẩn Điểm đang giữ → đổi thưởng → ưu đãi của tôi và API hỗ trợ → đồng bộ thanh toán → kiểm thử → bàn giao. API cần cho từng màn hình được làm cùng màn hình đó, không chờ đến cuối mới xử lý.

## 5. Luồng trải nghiệm đề xuất

### Đổi thưởng

1. Khách mở Đổi thưởng và xem số điểm khả dụng.
2. Tìm/lọc quà, xem điểm cần đổi và thông tin quyền lợi.
3. Chọn Đổi ngay → mở dialog xác nhận.
4. Xác nhận → backend kiểm tra điều kiện và tạo giao dịch đổi một lần.
5. Thành công → cập nhật điểm, chuyển sang Ưu đãi của tôi và đánh dấu ưu đãi vừa nhận.
6. Nếu dữ liệu đã thay đổi hoặc request chưa rõ kết quả → thông báo cụ thể, tải lại dữ liệu và retry an toàn.

### Ưu đãi của tôi

| Trạng thái backend | Nhãn khách thấy | Hành động đề xuất |
| --- | --- | --- |
| `available`, voucher còn hạn | Có thể sử dụng | Xem chi tiết, sao chép mã, hướng dẫn chọn voucher khi thanh toán. |
| `available`, quà vật lý còn hạn | Chờ nhận quà | Xem mã và hướng dẫn mang mã tới Bin Spa; khách không tự xác nhận đã nhận. |
| `reserved` | Đang áp dụng | Hiển thị giao dịch đang áp dụng; cho tiếp tục thanh toán nếu có luồng tương ứng và người dùng có quyền. Không cho áp dụng lần nữa vào giao dịch khác. |
| `used` | Đã sử dụng | Xem ngày dùng và giao dịch liên quan, không có nút áp dụng. |
| `fulfilled` | Đã nhận quà | Xem ngày nhận, không có nút nhận lần nữa. |
| `expired` hoặc available đã quá hạn | Đã hết hạn | Xem chi tiết/lịch sử; không có nút dùng/nhận. |
| `cancelled` | Đã hủy | Xem trạng thái/lịch sử; không tự hoàn điểm từ frontend. |

Đề xuất nhóm lọc: **Có thể sử dụng**, **Chờ nhận quà**, **Đang áp dụng**, **Đã sử dụng / Đã nhận**, **Hết hạn / Đã hủy**, **Tất cả**. `reserved` quá hạn tiếp tục theo chính sách giao dịch hiện tại; không tự chuyển trạng thái hoặc hoàn điểm chỉ do khách mở trang.

## 6. API và dữ liệu

| Thành phần | Hướng sử dụng / mở rộng |
| --- | --- |
| `GET /api/loyalty/me` | Tái sử dụng số dư chính xác. UI customer chỉ chọn ba chỉ số cần hiển thị. |
| `GET /api/loyalty/rewards` | Đề xuất thêm `search`, `reward_type`, `affordable_only`; giữ `page`, `per_page`; validate và lọc trước paginate. |
| `POST /api/loyalty/rewards/<id>/redeem` | Giữ cơ chế idempotency và kiểm tra server hiện tại; cải thiện cách frontend xác nhận/retry và cập nhật dữ liệu. |
| `GET /api/loyalty/my-rewards` | Đề xuất thêm nhóm trạng thái, loại ưu đãi và tìm theo tên/mã; trả trạng thái hiệu lực nhất quán với kết quả lọc và tổng số. |
| API chi tiết ưu đãi | Chỉ bổ sung nếu cần tải độc lập theo ID. Bắt buộc kiểm tra ownership; không nhận `makh` từ client làm căn cứ cấp quyền. |
| Các endpoint `.../loyalty`, `.../reward`, `.../pay-points` hiện có | Tiếp tục dùng cho preview/áp dụng/bỏ điểm-voucher và thanh toán. Frontend không tự tính giá trị giảm thay cho kết quả backend. |
| `POST /api/admin/loyalty/redemptions/<id>/fulfill` | Giữ luồng nhân viên xác nhận bàn giao và ghi audit. |
| Model/database | Phiên bản đầu ưu tiên dữ liệu hiện có; chưa cần migration để ẩn chỉ số, thêm dialog, lọc hoặc đổi bố cục. Giữ ledger, reservation, snapshot và dữ liệu ưu đãi đã đổi. |

Lưu ý triển khai: filter `expired` không chỉ dùng `WHERE status='expired'`, vì source hiện suy ra hết hạn khi serialize. Cần một định nghĩa trạng thái hiệu lực dùng chung cho filter/count/serialize. Catalog ngừng cho đổi không tự hủy các ưu đãi hợp lệ đã phát hành.

## 7. Tệp dự kiến liên quan

| Tệp | Vai trò dự kiến |
| --- | --- |
| `app/templates/customer/profile.html` | Khu vực điểm, tab và vùng dialog/chi tiết ưu đãi. |
| `app/static/js/customers/loyalty.js` | Render ba chỉ số, catalog, xác nhận đổi, lọc ưu đãi, trạng thái tải và retry. |
| `app/static/js/loyalty-payment.js` | Ẩn reserved balance theo ngữ cảnh khách; đồng bộ voucher và số tiền thanh toán. |
| `app/static/js/customers/profile.js` | Điều hướng/khôi phục tab nếu cần tích hợp URL; tránh tải trùng. |
| `app/static/css/loyalty.css` | Bố cục ví ba chỉ số, card quà/voucher, badge, dialog và responsive; tránh tác động sai giao diện admin dùng chung CSS. |
| `app/routes/loyalty_bp.py` | Query params, lọc/phân trang và API chi tiết nếu cần. |
| `app/services/loyalty_service.py` | Helper trạng thái hiệu lực/điều kiện dùng; giữ giao dịch nguyên tử và quy tắc tiền/điểm. |
| `app/loyalty_models.py` | Chỉ chỉnh nếu phạm vi dữ liệu mới thực sự được bổ sung; không xóa `reserved_points`. |
| `app/admin/loyalty_manage_bp.py`, `app/static/js/admin/loyalty.js` | Đối chiếu quyền bàn giao và nghiệp vụ dùng chung; không thiết kế lại admin trong phiên bản này. |
| `tests/test_loyalty_service.py`, `tests/test_loyalty_payments.py`, `tests/test_loyalty_concurrency.py` | Nghiệp vụ, quyền truy cập, tiền/điểm, retry và giao dịch đồng thời. |
| `tests/loyalty-ui.test.cjs`, `tests/loyalty_browser_check.py` và test mới phù hợp | Luồng khách, component dùng chung, trạng thái hết hạn và trải nghiệm mobile. |

## 8. Bảng kiểm thử và tiêu chí nghiệm thu

| Mã | Tình huống | Kết quả bắt buộc |
| --- | --- | --- |
| T01 | Khách mở hồ sơ/Đổi thưởng/Ưu đãi/thanh toán hóa đơn/thanh toán gói | Không thấy nhãn hoặc giá trị điểm đang giữ, kể cả dialog và giao diện mobile. |
| T02 | Ví có điểm đang dùng cho giao dịch khác | Chỉ `available_points` được dùng để đổi/dùng tiếp; không cộng điểm đang giữ vào số khả dụng. |
| T03 | Nhân viên mở màn hình thanh toán/quản lý điểm | Vẫn xem được điểm đang giữ; không bị thay đổi bởi component customer. |
| T04 | Khách mở rồi hủy dialog xác nhận đổi | Điểm và tồn kho giữ nguyên, không tạo redemption. |
| T05 | Đủ điểm, quà còn hàng và active | Đổi thành công đúng một lần, trừ đúng điểm, giảm đúng tồn kho, ưu đãi mới xuất hiện. |
| T06 | Thiếu điểm/hết quà/quà ngừng đổi sau khi mở trang | Backend từ chối; UI báo đúng lý do và cập nhật dữ liệu. |
| T07 | Double-click, mất mạng, retry hoặc reload giữa yêu cầu | Cùng thao tác không trừ điểm/phát quà trùng; thao tác mới hợp lệ vẫn đổi được. |
| T08 | Hai khách đổi phần quà cuối hoặc một khách dùng điểm đồng thời | Không âm tồn kho/số dư và không chi tiêu trùng điểm. |
| T09 | Tìm/lọc danh mục hoặc ưu đãi có nhiều trang | Kết quả, tổng số, số trang và bộ lọc thống nhất trên toàn bộ dữ liệu. |
| T10 | Có ưu đãi available đã quá hạn trong DB | Nằm đúng nhóm hết hạn; không được áp dụng/nhận quà; ngày giờ hiển thị theo Việt Nam. |
| T11 | Admin sửa tên/giá trị/thời hạn hoặc ngừng catalog sau khi khách đổi | Ưu đãi đã đổi vẫn hiển thị quyền lợi từ snapshot, đúng hạn và trạng thái riêng. |
| T12 | Khách sửa ID/`makh` để xem hoặc dùng ưu đãi người khác | Bị backend từ chối; không lộ dữ liệu và không đổi giao dịch của người khác. |
| T13 | Áp dụng/bỏ voucher, thanh toán cash/VietQR/điểm | Payable và trạng thái đúng; không dùng voucher hai giao dịch; đã thanh toán không sửa ưu đãi. |
| T14 | Khách đóng thanh toán rồi mở lại | Giữ đúng giao dịch và ưu đãi đang áp dụng; không tự release chỉ vì đóng dialog. |
| T15 | Quà vật lý: nhận, nhận lại, hết hạn, thao tác từ customer | Chỉ nhân viên có quyền bàn giao; không bàn giao trùng/quà hết hạn; customer không tự xác nhận. |
| T16 | Clipboard lỗi, API lỗi, session hết hạn, response trả chậm | Thông báo rõ; cho thao tác phù hợp; không render kết quả cũ đè view mới. |
| T17 | Mobile 390px, desktop và dùng bàn phím | Không tràn card/dialog; tab/focus/nút và thông báo hoạt động đầy đủ. |
| T18 | Regression hệ thống | Loyalty, package purchase, cash/VietQR, billing, booking, treatment, gift và notification liên quan pass. |

**Điều kiện hoàn thành phiên bản:** YC01–YC03 được đáp ứng; các test tương ứng pass; kiểm tra browser thật cho luồng đổi → xem ưu đãi → dùng/nhận; không mất dữ liệu hoặc thay đổi sai quyền lợi cũ; có báo cáo kết quả kiểm thử và ảnh giao diện.

## 9. Đề xuất mở rộng sau phiên bản đầu

Các mục này chưa nằm trong phạm vi mặc định; chỉ đưa vào giai đoạn tiếp theo khi có chính sách cụ thể:

| Mở rộng | Nội dung cần xác định trước |
| --- | --- |
| Ảnh quà/voucher, banner chiến dịch | Nguồn ảnh, kích thước, upload và nơi lưu trữ; migration nếu thêm field. |
| Voucher phần trăm, giới hạn dịch vụ/gói, giá trị đơn tối thiểu | Quy tắc cộng dồn, giới hạn giảm và snapshot điều kiện cho ưu đãi đã đổi. |
| Ưu đãi sinh nhật hoặc cấp trực tiếp từ spa | Điều kiện được nhận, lịch phát, chống phát trùng và cách phân biệt với quà đổi bằng điểm. |
| Hủy đổi/hoàn điểm hoặc xử lý ưu đãi hết hạn | Ai được thao tác, điều kiện hoàn, hoàn tồn kho, audit và ảnh hưởng ledger. Không tự áp dụng chính sách mới. |
| Dùng voucher trực tiếp từ Ưu đãi của tôi | Cách chọn đúng hóa đơn/giao dịch gói chưa thanh toán, xử lý giao dịch không tương thích và điều hướng. Phiên bản đầu giữ chọn voucher tại màn hình thanh toán hiện có. |
| Nhắc ưu đãi sắp hết hạn | Kênh thông báo, lịch gửi và chống gửi trùng; xử lý quyền nhận thông báo. |

## 10. Bàn giao của bước lập kế hoạch

Tài liệu đã lưu trong `plans`. Bước hiện tại chỉ tạo kế hoạch và cập nhật mục lục thư mục; chưa triển khai các hạng mục tính năng, chưa đổi số dư/ưu đãi và chưa chạy migration.

## 11. Kết quả triển khai phiên bản đầu (04/10/2026)

| Hạng mục | Đã thực hiện |
| --- | --- |
| YC03 – Ẩn Điểm đang giữ | Ví khách còn 3 chỉ số. `loyalty-payment.js` chỉ hiện “Đang giữ” khi base là `/api/admin/...`; khách chỉ thấy điểm khả dụng. `reserved_points` và cơ chế reserve/release/consume giữ nguyên. |
| YC01 – Đổi thưởng | Tìm theo tên, lọc loại, “Chỉ quà đủ điểm” (lọc ở backend trước phân trang); card hiện quyền lợi/điểm/hiệu lực/tồn; dialog xác nhận (Hủy không trừ điểm); idempotency key lưu `sessionStorage`, chỉ giữ lại khi kết quả chưa rõ (mất mạng/5xx/409) để thử lại an toàn, kể cả sau reload. Thành công → chuyển sang Ưu đãi của tôi, làm nổi bật ưu đãi mới. |
| YC02 – Ưu đãi của tôi | Nhóm trạng thái Có thể sử dụng / Chờ nhận quà / Đang áp dụng / Đã sử dụng–Đã nhận / Hết hạn–Đã hủy / Tất cả; lọc loại, tìm tên/mã; chi tiết theo snapshot; sao chép mã; hướng dẫn theo trạng thái; “Tiếp tục thanh toán” cho ưu đãi đang áp dụng. |
| API | `GET /api/loyalty/rewards`: `search`, `reward_type`, `affordable_only`. `GET /api/loyalty/my-rewards`: `status`, `reward_type`, `search`. Trạng thái hiệu lực dùng chung `redemption_status`/`filter_redemptions` cho lọc, tổng số và serialize. Không thêm API chi tiết, không migration. |
| Giao diện | Tab có `role=tab`, phím mũi tên; ghi nhớ view qua `?loyalty_view=&loyalty_status=`; loading/lỗi/rỗng; tải lại khi quay lại tab; cache-bust `v=2.0`. CSS mới được giới hạn trong `#loyalty-section`, không ảnh hưởng admin. |
| Kiểm thử | `tests/test_loyalty_customer_rewards.py` (mới), test lọc đa backend trong `test_loyalty_concurrency.py`, 3 test node mới, `tests/loyalty_customer_browser_check.py` (Edge thật, desktop + 390px). Kết quả: pytest 340 passed/9 skipped; node 23/23; PostgreSQL 14/14; cả hai browser check PASS. |
| Ngoài phạm vi | API chi tiết theo ID, dùng voucher trực tiếp từ Ưu đãi của tôi và các mở rộng ở mục 9. Lưu ý: tìm kiếm không phân biệt hoa/thường với ký tự có dấu chỉ đầy đủ trên PostgreSQL (SQLite chỉ gộp chữ ASCII). |

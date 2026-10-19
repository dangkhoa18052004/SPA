# Hợp đồng và quyền sở hữu DOM

Đối chiếu trực tiếp các route và script tại commit trong baseline. Các ví dụ chỉ ghi shape, không ghi token hoặc thông tin người dùng thật. Không thay schema hoặc API trong migration.

| Method / endpoint | Request và response cần giữ | Quyền / lỗi |
|---|---|---|
| POST `/api/auth/login/customer` | `{taikhoan|email|sdt, matkhau}` → `{success, access_token, user, redirect_url}` | 400 thiếu input, 401 sai mật khẩu, 403 khóa, 404 không có tài khoản |
| POST `/api/auth/restore-session` | Session cookie → `{success, access_token}` | 401 khi guest; bridge retry tối đa một lần |
| POST `/api/auth/logout` | Xóa session; client xóa token/cache | Không ghi token ra console |
| POST `/api/auth/register`, `/verify-otp`, `/resend-otp`, `/forgot-password`, `/reset-password` | Giữ tên trường của `customers/auth.js` | Không suy đoán thêm password policy hoặc resend countdown |
| GET `/api/services` | `category`, `search`, `sort` tùy chọn → `{success, services, total}`; service `{madv,tendv,mota,gia,thoiluong,anhdichvu,category_slug,category_name}` | Guest hoặc JWT optional; 403 inactive; 503 DB. Private/no-store |
| GET `/api/services/<id>` | `{success,service}` | 404 không tồn tại/inactive |
| GET `/api/services/<id>/reviews` | `page`, `per_page` (max 50), server summary/reviews | 400 pagination; chỉ public reviews |
| GET `/api/recommendations[/related/<id>]` | Server ranking, items/reason | Giữ thứ tự default; lỗi related không chặn catalog |
| POST `/api/recommendations/events` | `{action,madv}` (`click_service`, `select_service`, view hiện hành) | CustomerAuth; capture listener toàn document, dedupe 10 phút; không thêm listener trùng |
| GET `/api/appointments/available-slots` | `date`, `madv_list` CSV (hoặc `madv`), `manv`, `suggest=1` → `{success,date,duration_minutes,day_status,slots,suggestions?}` | 400 thiếu/sai ngày; 500 lỗi server |
| POST `/api/appointments/available-staff` | `{ngaygio,madv_list}` → `{success,staff:[{manv,hoten,available,message,chucvu}]}` | Guest/JWT optional; 400 validation |
| POST `/api/appointments/create` | `{madv_list,ngaygio,manv,ghichu,package_usages,payment_option}` → `{success,appointment}` (201) | Customer; 400 invalid, 409 slot, 503 QR unavailable. Giữ marker trước POST và reconcile sau timeout |
| GET `/api/appointments/my-appointments` | `{success,appointments}`; services/invoice/quyền server | Customer, 401 không có identity |
| PUT hoặc POST `/api/appointments/<id>/cancel`; PUT `/<id>/services` | Response server làm nguồn status/tiền/lượt | 403/404/409/400; không tự sửa thành công trước response |
| GET `/api/profile` | `{success,user:{makh,hoten,sdt,diachi,email,taikhoan,anhdaidien}}` | JWT, 404 user không tồn tại |
| PUT `/api/profile/update` | `{hoten,sdt,diachi,email}` → `{success,message}` | JWT; reload sau success |
| POST `/api/profile/upload-avatar` | FormData `file` → `{success,filename,message}` | JWT; 400/413/500; không đặt JSON Content-Type cho multipart |
| PUT `/api/profile/change-password` | `{matkhau_cu,matkhau_moi}` | JWT; không log hoặc cache password |
| GET `/api/payment/invoices[/<id>]` | List/detail **không luôn có wrapper success**; detail `{mahd,ngaylap,tongtien,trangthai,chitiet,...payment_summary}` | JWT, ownership; 404/500 |
| POST `/api/payment/invoices/<id>/generate-qr` | QR/payment details server; không coi là paid | 400 paid/cancelled/zero due, 404 ownership, 500 QR |
| GET `/api/packages[/<id>]` | `{success,packages|package}` | Guest; chỉ active và customer_sale_enabled |
| GET `/api/packages/payment-options` | `vietqr_available` và cash gate hiện hành | Không tự mở sale channel |
| POST `/api/packages/<id>/purchase` | payment_method hợp lệ → `{success,purchase}` (201) | Customer; 503 QR unavailable |
| GET `/api/packages/my-purchases`, `/purchases/<id>[/status]` | `{success,purchases|purchase}` | Customer ownership; 404; purchase ID khác invoice ID |
| POST `/api/packages/purchases/<id>/cancel` | Không cần body → `{success,purchase,message}`, status `cancelled` | Chỉ chủ đơn và trạng thái pending; lặp lại cancelled trả thành công; 404 sai chủ/không tồn tại, 400 đã thanh toán/thất bại. Trả điểm/voucher đang giữ cùng transaction; không xóa bản ghi hoặc liệu trình đã mua |
| GET `/api/packages/my-treatments[/<id>]` | `{success,treatments|treatment}`, detail có history | Customer ownership; lượt/hạn/quà theo server |
| GET `/api/loyalty/me`, `/me/transactions`, `/rewards`, `/my-rewards` | wallet `available_points`, config/tier; paged `items,page,per_page,total,pages` | Customer; giữ filters `search,reward_type,affordable_only,status,usable_for` |
| POST `/api/loyalty/rewards/<id>/redeem` | `Idempotency-Key` hoặc body `idempotency_key` ≤80 ký tự, cùng key khi retry | 201 redemption; 400 validation; 409 conflict |
| GET `/api/reviews/my`, `/appointments/<id>/context`; POST `/api/reviews`; PUT/DELETE `/<id>` | `malh,rating` và fields editor hiện hành | Customer, ownership; 400/403/404/409; refresh sau success |
| GET/PUT `/api/me/communication-preferences` | Consent fields và version | CRM/consent flag, 409 dữ liệu vừa thay đổi; không tự opt-in |
| GET/POST `/api/chat/conversations[/<id>/messages]` | Giữ conversation/unread/service picker | Chỉ hội thoại có quyền; dừng polling/clear khi logout |

## DOM và bridge

- `window.CustomerTreatments` chỉ đăng ký bởi account entry khi gate mới khả dụng. Bridge cung cấp markup cho list/history/pending/loading/error; `PackageCare.loadTreatments()` tiếp tục sở hữu GET và event trong `myTreatments`/`myPackagePurchases`. Không mount React vào các root này. Thiếu bridge hoặc `?ui=legacy` dùng renderer cũ; admin không gọi nhánh mới. Các query booking `treatment`, `service`, `item` và purchase resume ID được giữ nguyên.

- `servicesGrid`: home thuộc main.js; `/services` thuộc services.js; không mount hai owner. `relatedRecommendations` thuộc recommendations.js.
- `root` trên booking React thuộc React; không tải script legacy appointment/packages để điều khiển cùng subtree.
- Profile: `*-section`, `.menu-link[data-section]`, `editProfileForm`, `changePasswordForm`, `avatarInput`, `appointmentsList`, invoice hooks giữ nguyên cho scripts hiện tại; account shell mới phải chuyển quyền sở hữu menu một cách tường minh.
- `PackageCare`, `ReviewUI`, `LoyaltyPayment`, `CustomerAuth`, `CustomerLoyalty` là contract bridge. Không xóa shared scripts chỉ vì customer chuyển sang entry mới.
- E07: `customers/loyalty.js` tiếp tục sở hữu dữ liệu, sự kiện và DOM điểm thưởng ở cả legacy/refactor; không mount React vào các root loyalty. Wallet và danh sách tải song song, lỗi độc lập; wallet chưa tải được không được coi là 0 điểm và chặn lượt đổi mới. Retry yêu cầu chưa rõ kết quả giữ nguyên idempotency key trong sessionStorage; server vẫn quyết định số dư/quyền/điều kiện đổi. CSS mới giới hạn trong `#loyalty-section` và `.loyalty-reward-dialog`, không áp dụng wallet customer cho admin.
- E08: `reviews.js` tiếp tục là owner duy nhất của `myReviews`, `[data-service-reviews]` và `spaReviewDialog`; giữ `ReviewUI.openAppointmentReview`, `loadMy`, `appointmentActions` cùng sự kiện `reviews-updated`. Context API xác minh lịch hoàn thành/ownership; tạo mới gửi service_ids được chọn, sửa chỉ gửi rating/comment. Chặn submit/xóa lặp trong lúc chờ, lỗi giữ bản nháp và cho thử lại; request timeout sau 20 giây yêu cầu tải lại để kiểm tra kết quả, không retry mutation tự động hoặc giả định thành công khi mất mạng. Sau response thành công tải lại danh sách/summary đang có trên trang và phát sự kiện cập nhật lịch hẹn. Response danh sách/context cũ không được ghi đè dữ liệu mới hoặc mở lại dialog đã đóng. Style customer giới hạn `#reviews-section`, `.customer-review-dialog`, `[data-service-reviews]`; admin vẫn dùng renderer/phản hồi hiện hành.
- E09: `communication-preferences.js` là owner duy nhất của form `communicationPreferences`; chỉ GET khi tab được mở, không tự PUT hoặc tự đổi các giá trị server trả. Hai fieldset cùng khóa khi loading/saving hoặc chưa có version hợp lệ. PUT giữ đủ bốn boolean và version; 409 hoặc kết quả lưu chưa rõ yêu cầu GET mới trước khi ghi tiếp. 400/422 giữ draft để khách sửa; lỗi GET sau đó không được mở lại form bằng version cũ. Flag tắt thì template không có tab/form/assets. Giữ mặc định nghiệp vụ hiện hành của server; không thay opt-in từ UI.
- F01: chat legacy customer giữ một vòng refresh; pagehide dừng vòng, pageshow từ Back/Forward cache chỉ khởi động lại khi còn access token. `setupChatRefresh` tiếp tục clear interval cũ trước khi tạo vòng mới; logout dừng và xóa dữ liệu phiên theo luồng hiện hành.
- Auth errors: JWT invalid dùng `{msg: ...}`; business validation thường `{success:false,message:...}`. Không coi mọi 422 là logout, không retry mutation do lỗi validation.

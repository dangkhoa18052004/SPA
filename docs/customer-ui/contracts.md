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
| GET `/api/packages/my-treatments[/<id>]` | `{success,treatments|treatment}`, detail có history | Customer ownership; lượt/hạn/quà theo server |
| GET `/api/loyalty/me`, `/me/transactions`, `/rewards`, `/my-rewards` | wallet `available_points`, config/tier; paged `items,page,per_page,total,pages` | Customer; giữ filters `search,reward_type,affordable_only,status,usable_for` |
| POST `/api/loyalty/rewards/<id>/redeem` | `Idempotency-Key` hoặc body `idempotency_key` ≤80 ký tự, cùng key khi retry | 201 redemption; 400 validation; 409 conflict |
| GET `/api/reviews/my`, `/appointments/<id>/context`; POST `/api/reviews`; PUT/DELETE `/<id>` | `malh,rating` và fields editor hiện hành | Customer, ownership; 400/403/404/409; refresh sau success |
| GET/PUT `/api/me/communication-preferences` | Consent fields và version | CRM/consent flag, 409 dữ liệu vừa thay đổi; không tự opt-in |
| GET/POST `/api/chat/conversations[/<id>/messages]` | Giữ conversation/unread/service picker | Chỉ hội thoại có quyền; dừng polling/clear khi logout |

## DOM và bridge

- `servicesGrid`: home thuộc main.js; `/services` thuộc services.js; không mount hai owner. `relatedRecommendations` thuộc recommendations.js.
- `root` trên booking React thuộc React; không tải script legacy appointment/packages để điều khiển cùng subtree.
- Profile: `*-section`, `.menu-link[data-section]`, `editProfileForm`, `changePasswordForm`, `avatarInput`, `appointmentsList`, invoice hooks giữ nguyên cho scripts hiện tại; account shell mới phải chuyển quyền sở hữu menu một cách tường minh.
- `PackageCare`, `ReviewUI`, `LoyaltyPayment`, `CustomerAuth`, `CustomerLoyalty` là contract bridge. Không xóa shared scripts chỉ vì customer chuyển sang entry mới.
- Auth errors: JWT invalid dùng `{msg: ...}`; business validation thường `{success:false,message:...}`. Không coi mọi 422 là logout, không retry mutation do lỗi validation.

# Bàn giao Claude: voucher người mới và nhân viên tặng voucher

## Cập nhật đã chốt và hoàn thiện ngày 24/10/2026

Người dùng xác nhận lại nghiệp vụ: tự tạo voucher theo ý muốn, có lựa chọn **Dành cho khách hàng mới** ngay trong form mẫu; **tắt hoạt động chỉ ngừng khách đổi bằng điểm**, không ngừng welcome, tặng thủ công hoặc dùng voucher đã nhận. Nhân viên có quyền có thể tặng cả mẫu inactive/welcome còn tồn; không yêu cầu `allow_manual_gift`. Các điều kiện active/allow_manual_gift và giới hạn không tặng tay mẫu welcome ở thiết kế lịch sử dưới đây đã được thay thế.

Đã bổ sung nút **Tặng voucher** ngay danh sách khách và giữ trong hồ sơ trên cả React/legacy; đổi version script legacy tránh cache cũ. Form tạo/sửa mẫu lưu boolean `for_new_customers` và cấu hình welcome cùng transaction. Một mẫu welcome tại một thời điểm, lifetime once-key giữ nguyên. Mức giảm/đơn tối thiểu/phạm vi/hạn dùng do người dùng tự nhập; không cần chờ chốt một giá trị cố định và không tự đổi chương trình đang chạy.

V02–V06 đã có triển khai; V07 kiểm tra mới **154 passed, không skip** trên SQLite/PostgreSQL riêng, frontend **71 passed/build đạt**, browser hồi quy + luồng inactive/nút danh sách React/legacy/mobile đạt. V08 cập nhật vận hành và log `voucher_event` chỉ báo thành công sau commit, có replay/skip/hết kho/lỗi/used/cancelled; test rollback và riêng tư đạt. Chi tiết, bằng chứng và quy tắc hiện hành: [docs/VOUCHER_ISSUANCE.md](../docs/VOUCHER_ISSUANCE.md), `output/voucher-completion-2026-10-24/`.

Kiểm tra chỉ đọc môi trường đang chạy: welcome đã bật, hai mẫu voucher còn tồn, trang khách/API trả 200 và bundle phục vụ có nút tặng. Không chạy migration mới, không đổi giá trị mẫu hoặc cấu hình thật, không deploy. Phần còn lại của tài liệu giữ nội dung bàn giao ban đầu để truy vết; ưu tiên quy tắc ngày 24/10 nêu trên.

Ngày lập: 23/10/2026. Cập nhật: đã triển khai mã nguồn và, sau phê duyệt bổ sung của người dùng, đã backup/migrate PostgreSQL đang phục vụ `192.168.1.160:5000` lên `20261023_0025`. Dữ liệu cũ giữ nguyên; welcome vẫn tắt; không deploy. Xem kết quả và hướng dẫn vận hành tại [docs/VOUCHER_ISSUANCE.md](../docs/VOUCHER_ISSUANCE.md). Các mục dưới đây giữ lại nội dung thiết kế/bàn giao ban đầu.

## 1. Mục tiêu và phạm vi

1. Khách hàng mới đủ điều kiện được tự động nhận đúng 1 voucher chào mừng, không mất điểm.
2. Nhân viên được cấp quyền có thể chọn khách hàng và tặng voucher từ mẫu đã được quản lý cho phép, không cần xin duyệt từng lần.
3. Voucher được cấp trực tiếp vào “Ưu đãi của tôi”, sử dụng trên luồng thanh toán đang có và có lịch sử truy vết.

Trong phiên bản đầu, “gửi voucher” nghĩa là cấp voucher vào tài khoản khách. Email/Zalo/SMS là kênh thông báo riêng, không nằm trong phạm vi mặc định. Không làm gửi hàng loạt, chuyển voucher giữa khách, tự nhập mức giảm tùy ý, hoặc hệ thống chiến dịch marketing tổng quát.

## 2. Hiện trạng đã kiểm tra trong mã nguồn

| Thành phần | Hiện trạng | Hướng tận dụng |
| --- | --- | --- |
| `app/loyalty_models.py` | Có `LoyaltyReward`, `LoyaltyRewardRedemption`; constraint bắt buộc `points_cost > 0`, `points_spent > 0` | Mở rộng nguồn phát hành và constraint; không giả lập trừ/cộng điểm |
| `app/services/loyalty_service.py` | Có đổi thưởng, snapshot, mã riêng, tồn kho, hạn dùng, voucher tiền/phần trăm, điều kiện đơn tối thiểu và phạm vi | Tách phần phát hành dùng chung; giữ nghiệp vụ đổi điểm |
| Cùng service | Có giữ voucher khi áp dụng, bỏ áp dụng, kiểm tra chủ sở hữu, hoàn tất thanh toán | Voucher tặng dùng chung vòng đời này |
| `app/routes/auth_bp.py` | Đăng ký tạo khách `pending`; `verify_otp()` chuyển sang `active` rồi commit | Điểm tích hợp đề xuất: kích hoạt lần đầu thành công |
| `app/routes/loyalty_bp.py` | Có `/api/loyalty/my-rewards`, catalog, đổi thưởng, áp dụng thanh toán | Mở rộng serializer/bộ lọc, không tạo ví voucher thứ hai |
| `frontend/src/admin/booking/Customers.tsx` | Giao diện quản lý khách React | Đặt thao tác “Tặng voucher” tại chi tiết khách |
| `frontend/src/admin/care/Loyalty.tsx` | Giao diện loyalty quản trị React | Quản lý mẫu được phép tặng và cấu hình chào mừng |
| `app/static/js/customers/loyalty.js`, `app/templates/customer/profile.html` | Có “Ưu đãi của tôi” | Bổ sung nhãn nguồn nhận, nội dung tặng |
| `app/static/js/admin/customers.js`, `app/static/js/admin/loyalty.js` | Có giao diện legacy song song | Kiểm tra route đang hỗ trợ và giữ tính nhất quán |
| `app/decorators.py` | Phân quyền theo role; admin có quyền đặc biệt | Kiểm tra phía server và giao diện theo quyền thực tế |
| `app/services/notification_service.py` | Hàng đợi hiện gắn với nghiệp vụ lịch hẹn | Không mặc định dùng được ngay cho voucher; cần đánh giá riêng nếu thêm email |

Repository đang có nhiều thay đổi chưa commit. Claude phải đọc trạng thái hiện tại, giữ nguyên công việc đang làm và chỉ sửa phần liên quan. Các API/model mới dưới đây là thiết kế đề xuất, không phải chức năng đã tồn tại.

## 3. Quy tắc nghiệp vụ đề xuất

### 3.1. Voucher người mới

| Nội dung | Quy tắc đề xuất cho bản đầu |
| --- | --- |
| Định nghĩa người mới | Tài khoản được tạo từ thời điểm chương trình bắt đầu, lần đầu chuyển từ `pending` sang `active` bằng OTP khi chương trình đang chạy |
| Thời điểm tặng | Sau kiểm tra OTP thành công, cùng giao dịch ghi nhận kích hoạt và phát hành |
| Số lượng | 1 voucher chào mừng trong suốt vòng đời mỗi `makh`; đổi mẫu hoặc bật lại chương trình không cấp lại |
| Không đủ điều kiện | Khách cũ, chưa xác thực, bị khóa; đăng nhập lại, gửi lại OTP, đổi mật khẩu không phát hành |
| Cấu hình | Bật/tắt, mẫu voucher, thời điểm bắt đầu/kết thúc; chỉ admin/quản lý có quyền cấu hình |
| Ví dụ để bàn bạc | Giảm 50.000đ, đơn từ 300.000đ, hạn 30 ngày, áp dụng hóa đơn dịch vụ. Đây là ví dụ, không tự bật trên production |
| Thay đổi cấu hình | Chỉ ảnh hưởng lần phát hành sau; voucher đã cấp giữ snapshot và hạn cũ |
| Tồn kho | Mẫu chào mừng mặc định không giới hạn; nếu cấu hình tồn hữu hạn thì hết kho không được chặn kích hoạt |
| Chương trình tắt/hết hạn/hết kho | Kích hoạt vẫn thành công, trả trạng thái không cấp kèm lý do; không tự cấp bù khi đăng nhập |
| Lỗi DB không dự kiến | Rollback toàn giao dịch, không báo kích hoạt thành công khi chưa commit; OTP có thể thử lại theo cơ chế hiện có |
| Khách do nhân viên tạo/import | Chưa tự nhận trong bản đầu; nếu dự án có thêm luồng này phải thống kê và chốt tiêu chí xác thực trước khi nối hook |

Giới hạn “mỗi tài khoản” không đồng nghĩa “mỗi người thật”. Tận dụng kiểm tra trùng định danh và giới hạn OTP hiện có; không cam kết chặn một người tạo nhiều tài khoản. Không đưa số điện thoại vào khóa chống trùng nếu chưa xác thực quyền sở hữu.

### 3.2. Nhân viên chủ động tặng

1. Mở chi tiết khách → “Tặng voucher”.
2. Chọn mẫu đang hoạt động và được phép tặng thủ công.
3. Xem tên khách/định danh đã che bớt, mức giảm, đơn tối thiểu, phạm vi, hạn dùng, tồn còn lại.
4. Nhập lý do nội bộ bắt buộc; lời nhắn cho khách là tùy chọn, tách riêng hai trường.
5. Xác nhận tặng → backend phát hành → hiện mã và voucher trong lịch sử khách.

| Nội dung | Quy tắc |
| --- | --- |
| Quyền tặng | Đề xuất cho `admin`, `manager`, `letan`; nhân viên kỹ thuật role `staff` chỉ được tặng nếu mở quyền phù hợp. Cần đối chiếu mô hình quyền thực tế |
| Quyền sửa giá trị voucher | Chỉ quản lý mẫu; người tặng không truyền mức giảm/hạn dùng tùy ý |
| Người nhận | Khách đang active; chặn khách pending/bị khóa/không tồn tại |
| Mỗi thao tác | 1 khách, 1 voucher; không tặng hàng loạt |
| Tặng nhiều lần | Được phép qua các thao tác mới có chủ đích; hiện lịch sử gần đây để tránh nhầm. Retry cùng thao tác không tạo thêm |
| Điểm | `points_spent = 0`; số dư và lịch sử điểm không đổi |
| Tồn kho | Trừ tồn đúng 1 nếu mẫu có tồn hữu hạn; chung tồn với đổi điểm khi dùng cùng mẫu |
| Lịch sử | Lưu người tặng từ phiên đăng nhập, khách, mẫu/snapshot, lý do, lời nhắn, thời điểm, mã, nguồn, trạng thái |
| Thu hồi | Admin/quản lý có thể hủy voucher tặng đang `available`, chưa hết hạn, với lý do bắt buộc; không hủy voucher đang giữ/đã dùng |
| Hoàn tồn khi thu hồi | Đề xuất không hoàn tồn để tránh phát hành vượt định mức lịch sử; không hoàn điểm vì không trừ điểm |

Nếu cần hạn mức nhân viên/ngày, ngân sách tháng hoặc quy trình duyệt ngoại lệ, đưa vào đợt sau; bản đầu kiểm soát bằng quyền và mẫu cho phép tặng.

### 3.3. Quy tắc sử dụng giữ nguyên

- Mỗi voucher thuộc một khách, dùng một lần, không đổi thành tiền và không chuyển nhượng.
- Dùng chung kiểm tra `minimum_spend`, `apply_to`, hạn dùng, trạng thái và chủ sở hữu hiện có.
- Mỗi giao dịch giữ tối đa một voucher; cách kết hợp với điểm giữ nguyên theo logic hiện tại.
- Áp dụng thành công chuyển `available → reserved`; hoàn tất thanh toán chuyển `reserved → used`.
- Bỏ áp dụng/hủy giao dịch chưa thanh toán phải giải phóng về `available` hoặc `expired` theo hạn.
- Đối chiếu luồng hoàn/hủy thanh toán đã trả tiền trước khi sửa; không tự mở lại voucher `used`.
- Hiển thị giờ Việt Nam; dữ liệu thời gian giữ chuẩn UTC hiện có, tránh đổi quy ước toàn dự án.

## 4. Thiết kế dữ liệu đề xuất

### 4.1. Mở rộng `LoyaltyReward`

- `allow_points_redemption`: boolean, default true để giữ catalog cũ.
- `allow_manual_gift`: boolean, default false.
- Mẫu chào mừng được tham chiếu bởi cấu hình; chỉ chấp nhận `voucher_amount` hoặc `voucher_percent`.
- Cho phép `points_cost = 0` nếu không cho đổi bằng điểm. Nếu `allow_points_redemption = true` thì vẫn bắt buộc `points_cost > 0`.
- Catalog khách chỉ trả mẫu được phép đổi điểm. Backend redeem cũng kiểm tra cờ; ẩn trên UI chưa đủ.
- Giữ các constraint về phần trăm, mức trần, tiền, tồn, hạn và phạm vi.

### 4.2. Mở rộng `LoyaltyRewardRedemption`

| Trường | Ý nghĩa |
| --- | --- |
| `issuance_source` | `points_redemption`, `welcome`, `staff_gift`; backfill dữ liệu cũ là `points_redemption` |
| `issued_by_staff` | FK nhân viên, bắt buộc với `staff_gift`; lấy từ server |
| `gift_reason` | Lý do nội bộ, không xuất trong API khách |
| `customer_message` | Lời nhắn khách được xem; giới hạn độ dài và render dưới dạng text |
| `welcome_once_key` | NULL với nguồn khác; với welcome là khóa ổn định theo `makh`, UNIQUE ở DB, không bao gồm phiên bản chương trình |
| `cancelled_by_staff`, `cancelled_at`, `cancel_reason` | Dấu vết thu hồi |

Constraint phải phân biệt: `points_redemption` có `points_spent > 0`; `welcome`/`staff_gift` có `points_spent = 0`. Giữ FK, unique mã, idempotency và index giữ voucher trên giao dịch. Không chỉ nới thành `points_spent >= 0` rồi bỏ kiểm tra nguồn.

Tiếp tục dùng `reward_snapshot_json` chụp đầy đủ điều kiện khi cấp và `redeemed_at` làm thời điểm cấp trong bản đầu; serializer có thể đặt tên hiển thị `issued_at` để tránh hiểu là đổi điểm. Không đổi tên cột cũ không cần thiết.

### 4.3. Cấu hình chào mừng

Đề xuất một bản ghi cấu hình riêng, ví dụ `WelcomeVoucherConfig`: `enabled`, `reward_id`, `starts_at`, `ends_at`, `updated_by_staff`, `updated_at`. Kiểm tra khoảng thời gian hợp lệ, mẫu hoạt động, đúng loại và có hạn dùng. Bản đầu chỉ có một chương trình chào mừng; khóa nhận một lần vẫn tồn tại khi đổi cấu hình.

### 4.4. Migration

- Đọc Alembic head thực tế trước khi chọn revision, không sửa migration đã chạy.
- Thêm cột với default tương thích → backfill → cập nhật constraint/index; kiểm thử SQLite và PostgreSQL nếu cả hai đang được hỗ trợ.
- Kiểm tra bản ghi cũ vẫn hiển thị, đổi điểm, giữ voucher và thanh toán được.
- Downgrade phải từ chối rõ ràng nếu có bản ghi tặng 0 điểm không tương thích schema cũ; không xóa voucher để ép rollback.
- Theo `AGENTS.md`, thay đổi schema cần phê duyệt. Tài liệu này chỉ là đề xuất để duyệt; chưa chạy migration hoặc đổi database.

## 5. Backend và API đề xuất

Tạo service phát hành tập trung, ví dụ `app/services/voucher_issuance_service.py`, dùng chung phần snapshot/mã/tồn kho với loyalty. Không gọi `redeem_reward()` rồi hoàn lại điểm. Route chịu trách nhiệm commit; service không tự commit giữa chừng.

| API đề xuất | Quyền | Hành vi |
| --- | --- | --- |
| `GET /api/admin/loyalty/gift-templates` | Người có quyền tặng | Danh sách mẫu hợp lệ, phân trang |
| `POST /api/admin/loyalty/customers/{makh}/voucher-gifts` | Người có quyền tặng | Body: `reward_id`, `reason`, `customer_message`; bắt buộc `Idempotency-Key` |
| `GET /api/admin/loyalty/customers/{makh}/voucher-gifts` | Quyền xem khách/lịch sử | Lịch sử phân trang, lọc nguồn/trạng thái/người tặng |
| `POST /api/admin/loyalty/voucher-gifts/{id}/cancel` | Admin/quản lý | Thu hồi có lý do, kiểm tra trạng thái dưới khóa |
| `GET/PUT /api/admin/loyalty/welcome-config` | Admin/quản lý | Đọc/cập nhật cấu hình, validate toàn bộ |
| `GET /api/loyalty/my-rewards` hiện có | Khách | Bổ sung nguồn cấp và lời nhắn; chỉ trả voucher thuộc khách |

Đối chiếu blueprint/prefix/response hiện có trước khi chốt URL. Dùng lỗi nhất quán với dự án: 400 dữ liệu sai/không đủ điều kiện, 401 chưa đăng nhập, 403 thiếu quyền, 404 không tồn tại, 409 xung đột idempotency/tồn/trạng thái. Tạo mới trả 201; replay hợp lệ trả 200 với cùng voucher.

### Chống trùng và đồng thời

- Manual: key gắn người thực hiện và thao tác; lưu/so sánh toàn bộ payload chuẩn hóa, gồm khách, mẫu, lý do, lời nhắn. Cùng key khác payload trả 409.
- UI sinh key một lần khi xác nhận; mất mạng/retry giữ nguyên key. Chỉ tạo key mới khi bắt đầu tặng mới.
- Welcome: unique ổn định theo khách ở DB là rào chắn cuối, không chỉ `SELECT` kiểm tra trước khi insert.
- Khóa/conditional update tồn kho, phát hành, snapshot và audit nằm cùng transaction; không cho tồn âm hoặc trừ tồn khi replay.
- Thống nhất thứ tự khóa với redeem/apply hiện có để giảm deadlock; kiểm thử hai nguồn dùng chung mẫu.
- Khi unique conflict phải rollback/savepoint phù hợp rồi đọc kết quả đã commit; không tiếp tục dùng session lỗi.
- Thu hồi và áp dụng đồng thời: chỉ một thao tác thắng; không để voucher bị hủy vẫn giảm tiền hóa đơn.
- OTP: chỉ response đã commit mới báo cấp thành công. Request lặp sau kích hoạt không được cấp thêm, kể cả response trước bị mất.

## 6. Giao diện cần làm

| Màn hình | Thay đổi | Tiêu chí |
| --- | --- | --- |
| Chi tiết khách | Nút “Tặng voucher”; modal chọn mẫu, xem điều kiện, lý do/lời nhắn và xác nhận | Nhìn rõ đúng người nhận; chặn bấm lặp; lỗi giữ dữ liệu nhập |
| Chi tiết khách | Danh sách voucher nhận, nguồn, người cấp, thời gian, trạng thái; thu hồi theo quyền | Có phân trang/empty/loading/error; không chỉ hiện voucher còn dùng được |
| Quản lý loyalty | Cờ cho đổi điểm/cho tặng thủ công, form cấu hình chào mừng | Không ép mẫu chỉ dùng tặng phải có điểm đổi; kiểm tra cả client và server |
| Ưu đãi của tôi | Nhãn “Quà chào mừng”, “Được spa tặng”, “Đổi bằng điểm” | Không hiện “Đã trừ 0 điểm”; không lộ lý do nội bộ/tên tài khoản nhân viên |
| Xác thực OTP | Thông báo có quà nếu backend xác nhận đã cấp | Không thông báo quà nếu chương trình tắt/hết kho; không thay đổi điều hướng đăng nhập hiện có |
| Thanh toán | Voucher được tặng xuất hiện trong bộ chọn hiện tại | Tính tiền và xử lý hạn/trạng thái thống nhất với voucher đổi điểm |

Kiểm thử desktop 1440px và mobile 390px/360px, thao tác bàn phím, focus modal, nhãn trường, toast lỗi/thành công; kiểm tra console và request lỗi. Nếu cả React và legacy còn được phục vụ, cập nhật tương ứng hoặc ghi rõ phạm vi hỗ trợ đã thống nhất.

## 7. Bảng công việc để bàn giao

Ước lượng là ngày công tham khảo cho triển khai và kiểm thử, không phải cam kết lịch; tổng khoảng 7–11 ngày công, chưa tính kênh gửi ngoài ứng dụng.

| Mã | Công việc | Phụ thuộc | Đầu ra/điều kiện hoàn thành | Ước lượng |
| --- | --- | --- | --- | --- |
| V01 | Chốt tiêu chí người mới, giá trị quà, quyền tặng và phạm vi | Không | Ghi quyết định vào mục 9; rà soát mọi đường tạo/kích hoạt khách | 0,5 |
| V02 | Thiết kế model, constraint, migration, tương thích dữ liệu cũ | V01 | Schema đề xuất được duyệt; migration thử trên DB test sạch và có dữ liệu cũ | 1 |
| V03 | Service phát hành chung, idempotency, tồn, snapshot, audit | V02 | Test 0 điểm, replay, cạnh tranh tồn và rollback đạt | 1–1,5 |
| V04 | API nhân viên tặng, lịch sử, thu hồi và phân quyền | V03 | API test quyền và đồng thời đạt; không tin dữ liệu người tặng từ client | 0,5–1 |
| V05 | Cấu hình và hook OTP cho voucher chào mừng | V03 | Khách hợp lệ nhận 1 lần; tắt/hết kho không chặn kích hoạt | 1–1,5 |
| V06 | UI khách hàng/quản trị, form mẫu và chương trình | V04, V05 | Thao tác tặng thực tế hoàn chỉnh; React/legacy trong phạm vi hoạt động | 1–2 |
| V07 | Hồi quy thanh toán, concurrency, migration, E2E | V06 | Checklist mục 8 đạt; báo rõ lỗi tồn tại từ trước | 1–1,5 |
| V08 | Tài liệu vận hành, nghiệm thu và hướng dẫn bật/tắt | V07 | Demo, bằng chứng kiểm thử, hướng dẫn rollout/rollback | 0,5 |

Có thể chia commit theo V02, V03–V04, V05, V06, V07–V08. Mỗi commit tập trung đúng phạm vi; không gom thay đổi có sẵn của người khác.

## 8. Ma trận kiểm thử và nghiệm thu

| Nhóm | Tình huống bắt buộc | Kết quả mong đợi |
| --- | --- | --- |
| Welcome | Đăng ký chưa OTP; OTP sai/hết hạn | Không nhận voucher |
| Welcome | OTP hợp lệ cho khách mới | Active và có đúng 1 voucher, 0 điểm bị trừ |
| Welcome | Gửi lại OTP, đăng nhập lại, reset mật khẩu, kích hoạt/retry đồng thời | Không có voucher chào mừng thứ hai |
| Welcome | Khách cũ; tài khoản tạo trước mốc; chương trình tắt/chưa bắt đầu/hết hạn | Không tự tặng hồi tố |
| Welcome | Hết kho/mẫu ngừng hoạt động; lỗi DB giữa phát hành | Business skip vẫn kích hoạt; lỗi DB rollback sạch, không thành công giả |
| Welcome | Đổi mẫu, tắt/bật chương trình | Khách đã nhận không nhận thêm |
| Manual | Nhân viên hợp lệ tặng mẫu tiền và mẫu phần trăm | Khách thấy voucher ngay, số dư/lịch sử điểm không thay đổi |
| Manual | Nhân viên không quyền, bị khóa, khách gọi API | Bị từ chối ở backend |
| Manual | Giả actor/mức giảm/hạn/khách trong payload | Không vượt quyền hoặc sửa điều kiện mẫu |
| Manual | Double click, timeout rồi retry, cùng key khác payload | Cùng thao tác chỉ 1 voucher; khác payload trả 409 |
| Stock | Hai yêu cầu tranh tồn cuối; đổi điểm và tặng cùng mẫu | Tối đa 1 yêu cầu lấy tồn cuối; không âm tồn |
| Snapshot | Sửa mẫu sau khi cấp | Voucher cũ giữ nguyên quyền lợi và hạn |
| Payment | Khác chủ, hết hạn, sai phạm vi, dưới đơn tối thiểu | Không áp dụng được |
| Payment | Một voucher trên hai hóa đơn đồng thời | Chỉ một giao dịch giữ được |
| Payment | Apply, release, hủy giao dịch, thanh toán, webhook lặp | Trạng thái và tiền đúng, không dùng hai lần |
| Payment | Phần trăm có trần, tiền giảm vượt tổng, kết hợp điểm | Dùng Decimal/rounding cũ; số phải trả không âm |
| Cancel | Thu hồi khả dụng; thu hồi đang giữ/đã dùng; thu hồi tranh apply | Chỉ thu hồi hợp lệ; không giảm tiền bằng voucher bị hủy |
| Privacy | Khách gọi my-rewards và đổi ID | Không lộ voucher khách khác, lý do nội bộ, metadata nhân viên |
| Migration | DB cũ có voucher đang giữ/đã dùng, upgrade, rollback không tương thích | Không mất dữ liệu; downgrade được chặn rõ ràng khi cần |
| UI | Mobile/desktop, mất mạng, danh sách trống, thiếu quyền, legacy | Hiển thị đúng, không toast thành công giả, không lỗi console mới |

Bộ hồi quy cần ưu tiên: `tests/test_loyalty_service.py`, `test_loyalty_customer_rewards.py`, `test_loyalty_voucher_apply.py`, `test_loyalty_voucher_terms.py`, `test_loyalty_voucher_percent.py`, `test_loyalty_voucher_finalize.py`, `test_loyalty_payments.py`, `test_loyalty_concurrency.py`, `test_loyalty_migration.py` và browser checks tương ứng. Thêm test riêng cho welcome/manual/thu hồi, không chỉ sửa expected để tests qua.

Lệnh tham khảo từ root SPA: `python -m pytest tests/test_loyalty_*.py` (nếu shell không expand glob, truyền danh sách file hoặc dùng pytest discovery với `-k loyalty`); trong `frontend`: `npm run test`, `npm run build`. Xác định fixture/env test của repository trước khi chạy, tuyệt đối không trỏ test vào DB thật. Chạy bài concurrency trên PostgreSQL test nếu đây là DB triển khai; SQLite pass chưa chứng minh được khóa PostgreSQL đúng.

## 9. Các quyết định chủ sản phẩm cần chốt

| Quyết định | Mặc định đề xuất | Khi chọn khác |
| --- | --- | --- |
| “Khách mới” là đăng ký hay lần đầu trả tiền? | Kích hoạt OTP lần đầu, tài khoản tạo từ mốc chương trình | Nếu là lần đầu mua: chuyển hook sang payment finalization, định nghĩa giao dịch hợp lệ và xử lý webhook lặp |
| Mức ưu đãi | Chưa chốt; ví dụ 50.000đ/đơn 300.000đ/30 ngày | Nhập cấu hình sau khi duyệt; không hardcode |
| Ai được tự tặng? | Admin, manager, lễ tân | Nếu mọi kỹ thuật viên: cần mở quyền API và điểm vào UI phù hợp, không mặc định mở toàn trang khách |
| “Gửi” có bao gồm email/Zalo/SMS? | Cấp vào tài khoản | Nếu có: thêm outbox/job, consent, retry, lịch sử gửi; gửi lỗi không được cấp voucher lại |
| Khách cũ có được nhận? | Không tự cấp welcome; vẫn có thể nhận quà nhân viên | Nếu cần cấp bù: công việc riêng có dry-run, thống kê và chống trùng |
| Có hạn mức nhân viên? | Chưa có hạn mức theo ngày; kiểm soát bằng quyền/mẫu/tồn | Nếu cần, bổ sung budget/limit atomic và test cạnh tranh |

Đây là những giả định để duyệt kế hoạch, không phải các quyết định đã được chủ sản phẩm xác nhận.

## 10. Rollout và tài liệu bàn giao sau triển khai

1. Kiểm thử trên database riêng; lưu kết quả hồi quy và demo hai hành trình hoàn chỉnh.
2. Duyệt schema/migration theo AGENTS; backup và migration production chỉ thực hiện khi được cho phép.
3. Cấu hình mặc định welcome tắt, mẫu cũ không cho tặng thủ công. Chỉ bật mẫu/quyền/chương trình sau nghiệm thu.
4. Theo dõi số cấp theo nguồn, replay, lỗi phát hành, hết kho và voucher dùng thành công; log không chứa OTP/token/định danh đầy đủ.
5. Khi cần dừng: tắt phát hành mới; voucher đã cấp vẫn hiển thị và sử dụng theo điều kiện. Không xóa dữ liệu hoặc tự rollback schema có voucher 0 điểm.
6. Bàn giao danh sách file sửa, migration, API, quyền, các test đã chạy/kết quả, lỗi còn lại, ảnh UI và hướng dẫn cấu hình. Không tuyên bố đã kiểm thử khi chỉ mới đọc mã.

## 11. Prompt để gửi Claude

> Hãy đọc AGENTS.md và plans/2026-10-23-ban-giao-claude-voucher-nguoi-moi-va-tang-voucher.md trong repository SPA. Triển khai hai chức năng: tự tặng 1 voucher cho khách mới đủ điều kiện và cho nhân viên được phân quyền tặng voucher trực tiếp vào tài khoản khách. Tận dụng LoyaltyReward/LoyaltyRewardRedemption và luồng thanh toán hiện tại, không trừ điểm cho voucher tặng, không tạo hệ thống voucher song song. Trước khi triển khai, đối chiếu mục 9 với quyết định nghiệp vụ của tôi; đánh dấu rõ điều chưa được chốt. Tôn trọng yêu cầu phê duyệt schema trong AGENTS.md, chuẩn bị thiết kế cụ thể để duyệt, không chạy migration production/deploy khi chưa được phép. Giữ nguyên thay đổi chưa commit của người khác. Làm theo V01–V08, kiểm thử chống cấp trùng, cạnh tranh tồn, phân quyền, snapshot, OTP và thanh toán. Khi bàn giao, báo file thay đổi, test thực sự đã chạy, kết quả và phần chưa hoàn tất; không tự bật chương trình trên production.

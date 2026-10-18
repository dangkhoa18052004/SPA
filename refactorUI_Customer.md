# BIN SPA — KẾ HOẠCH REFACTOR GIAO DIỆN KHÁCH HÀNG

Ngày lập: 18/10/2026. Đối tượng sử dụng: chủ dự án và coding agent.

Repository: https://github.com/dangkhoa18052004/SPA

Mốc khảo sát: `main`, cây mã nguồn `c189ad9f21e78ba423455c55e9181ef109478749`. Agent phải ghi lại commit đang làm trước khi triển khai và đối chiếu thay đổi mới hơn. Đây là kế hoạch dựa trên đọc mã nguồn liên quan; chưa chạy website, chưa kiểm chứng trực quan trên trình duyệt, chưa sửa hoặc deploy repo. Các tiêu chí dưới đây là mục tiêu nghiệm thu, không phải kết quả đã đạt.

## 1. Mục tiêu và quyết định triển khai

Refactor toàn bộ trải nghiệm khách hàng theo hướng tối giản, rõ thao tác, thuận tiện trên điện thoại và nhất quán giữa trang giới thiệu, dịch vụ, đặt lịch, tài khoản, thanh toán. Giữ nhận diện Bin Spa bằng màu xanh trầm, nền sáng và ảnh dịch vụ thật.

| Quyết định | Phương án thực hiện | Lý do / giới hạn |
|---|---|---|
| Phạm vi | Giao diện công khai và tài khoản khách hàng | Không refactor nghiệp vụ nhân viên, quản lý, admin; vẫn kiểm tra hồi quy nếu sửa tài nguyên dùng chung |
| Ant Design | Ưu tiên cho form tài khoản, bảng/lịch sử trên desktop, tabs, pagination, trạng thái, xác nhận thao tác và các màn giao dịch cần cấu trúc rõ | Dùng phiên bản đã khóa trong lockfile; không nâng cấp major chỉ để thay giao diện |
| shadcn | Ưu tiên phong cách và component tùy biến cho header, thẻ dịch vụ/gói, bố cục public, booking đang có, vùng chọn dịch vụ | Mở rộng bộ component hiện hữu; không mặc định coi `ui.tsx` hiện tại là đã cài đầy đủ shadcn/ui |
| Kết hợp hai hướng | Một bộ token dùng chung; mỗi màn chọn một họ control chính; các vùng khác nhau vẫn đồng bộ màu, font, chiều cao | Không dùng hai bộ Button/Input khác nhau xen kẽ trong cùng một form; không thêm thư viện thứ ba chỉ để làm modal/toast |
| Kiến trúc | Flask giữ URL và backend; React mở rộng từng nhóm màn; Jinja giữ nội dung public quan trọng và fallback | Không chuyển toàn bộ thành SPA trong một lần; không tự thêm Next.js hoặc dịch vụ backend mới |
| Booking | Tái sử dụng React booking đã có, cải tiến giao diện từng phần | Giữ tính toán lượt gói, kiểm tra slot, chống gửi lặp và đối soát sau timeout |
| API | Giữ endpoint, payload, quyền truy cập và quy tắc giao dịch hiện có | Nếu thiếu dữ liệu cho UI, ghi rõ khoảng trống và đề xuất riêng; không bịa endpoint |
| CSS | Tách namespace và entry khách hàng; dùng chung token nhưng không import CSS admin vào public | Tailwind reset, Ant Design portal và CSS legacy phải được kiểm tra phạm vi ảnh hưởng |
| Phát hành | Chuyển từng nhóm qua feature flag có fallback | Cờ mới là đề xuất; chưa tồn tại cho đến khi agent triển khai. Không tự bật trên production |

Tài liệu tham chiếu: https://ant.design/docs/react/customize-theme/ và https://ui.shadcn.com/docs . Tài liệu Ant Design hiện có nội dung phiên bản mới hơn repo; chỉ dùng API tương thích Ant Design 5 đang khóa. Không copy tính năng riêng v6 vào dự án v5.

## 2. Hiện trạng đã xác minh từ mã nguồn

| Khu vực | File hiện có | Nhận xét có căn cứ / hệ quả cho kế hoạch |
|---|---|---|
| Hạ tầng frontend | `frontend/package.json`, `frontend/vite.config.ts` | Có React 18, TypeScript, Vite, Ant Design khai báo `^5.27.0`, Tailwind, Radix Slot, CVA; lockfile mới là nguồn phiên bản cài thực tế |
| Build nhiều entry | `frontend/vite.config.ts` | Đang có `portal` và `booking`; output chung `app/static/portal`, có manifest và `emptyOutDir: true`; build mới phải giữ cả các entry cũ |
| Resolve asset | `app/ui_assets.py` | `portal_assets(source)` đọc manifest và CSS imports; thiếu entry/asset thì trả `None` để fallback |
| Trang public | `app/templates/customer/layout.html`, `index.html`, `services.html`, `service_detail.html`, `packages.html` | Jinja kết hợp JavaScript; header/footer, chat, nhạc, bottom nav, quick view và script dùng chung nằm ở layout |
| Đặt lịch | `frontend/src/booking-main.tsx`, `customer/Booking.tsx`, `booking-model.ts`, `api.ts`, `ui.tsx`, `booking.css` | Đã có React booking và component Button/Card/Input; giữ logic hiện tại, tránh viết lại từ đầu |
| Chuyển đổi booking | `app/routes/customer_bp.py` | `CUSTOMER_BOOKING_REACT_ENABLED`, `?ui=legacy`, kiểm tra asset trước khi render `booking_react.html` |
| Tài khoản | `app/templates/customer/profile.html`, `app/static/js/customers/profile.js` | Nhiều phân hệ trong một trang: hồ sơ, lịch hẹn, hóa đơn, liệu trình, đánh giá, điểm thưởng, tùy chọn thông báo |
| Phiên đăng nhập | `app/static/js/customers/auth-session.js`, `frontend/src/customer/api.ts` | `CustomerAuth` phục hồi token từ session, retry và redirect; React còn phụ thuộc bridge trên `window` |
| Cá nhân hóa | `app/routes/service_bp.py`, `recommendation_bp.py`, `app/static/js/customers/recommendations.js` | Dịch vụ có logic xếp hạng; có endpoint ghi event và gợi ý liên quan. UI phải giữ thứ tự backend khi chọn mặc định |
| Thanh toán | `app/static/js/loyalty-payment.js`, `packages.js`, `customers/profile.js` | Có nhiều điểm vào hóa đơn / VietQR / mua gói; cần kiểm kê trước khi thay DOM và tách component |
| Nội dung trang chủ | `app/templates/customer/index.html` | Có video hero, dịch vụ, lý do chọn, testimonial, giới thiệu, liên hệ; một số con số và testimonial được ghi trực tiếp trong HTML, chưa xác minh nguồn |
| Liên hệ CS1 | Cùng file `index.html` | Hiển thị `038 782 9152` nhưng `href="tel:02862588687"`; cần chủ dự án xác định số đúng, rồi đồng bộ text và href |
| Hồi quy | `tests/`, `frontend/src/customer/booking-model.test.ts`, `.github/workflows/quality.yml` | Có sẵn nhiều test booking, payment, loyalty, recommendation và assets; CI build frontend, chạy Vitest và pytest |

### 2.1 Những điều agent phải kiểm chứng ở giai đoạn 0

- Cờ nào đang bật trong môi trường local/test, route nào đang phục vụ React/legacy; không đọc hoặc in secrets.
- Luồng click từ dịch vụ/gói sang booking sử dụng query parameter nào; bảo toàn deep link hiện hành.
- Tên hash của mọi tab profile và query của loyalty; giữ cả bookmark cũ.
- Component nào của legacy còn được admin sử dụng, đặc biệt `packages.js`, `reviews.js`, `loyalty-payment.js` và `change-services.js`.
- Cấu trúc response thực tế, mã lỗi, quyền xem và trạng thái của từng API trước khi viết TypeScript types.
- Hiển thị thực tế trên local bằng Playwright CLI; không kết luận lỗi pixel chỉ từ việc đọc CSS.
- Nguồn xác nhận số điện thoại, giờ hoạt động, địa chỉ, đánh giá, con số khách hàng. Giữ CS1/CS2; không gộp/xóa cơ sở để đơn giản UI.

## 3. Phạm vi màn hình và bố cục đích

| Màn / URL hiện có | Bố cục đề xuất | Thành phần / hành vi phải giữ |
|---|---|---|
| Trang chủ `/` | Header gọn → hero có một CTA chính “Đặt lịch”, CTA phụ “Xem dịch vụ” → danh sách dịch vụ → giới thiệu/lợi ích → đánh giá có nguồn → liên hệ CS1/CS2 → footer | Danh sách dịch vụ là một section, có thứ tự ưu tiên từ backend; tránh thêm ba block cá nhân hóa trùng nhau. Vị trí dịch vụ mặc định ngay dưới hero; nếu giữ nhiều banner, đặt sau cụm banner cuối |
| Dịch vụ `/services` | Tiêu đề + ô tìm kiếm + bộ lọc + sort → grid → phân trang hoặc cơ chế tải hiện hành | Giá, thời lượng, ảnh, mô tả ngắn, CTA; tìm/lọc trên tập dữ liệu đầy đủ trước khi phân trang |
| Chi tiết `/services/<id>` | Breadcrumb → ảnh + thông tin + CTA → nội dung dịch vụ → đánh giá → dịch vụ/gói liên quan | “Có thể bạn cũng quan tâm” ở dưới; giữ dữ liệu review và recommendation; mobile CTA không che nội dung |
| Gói `/packages`, `/packages/<id>` | Thẻ gói rõ giá, số buổi, dịch vụ, thời hạn, chênh lệch với mua lẻ; chi tiết/checkout theo route hiện có | Quyền mua, điều kiện sale channel, đăng nhập, VietQR, pending purchase, không biến gói bán tại quầy thành gói mua online |
| Đặt lịch `/appointments/create` | Luồng bước: dịch vụ/lượt gói → ngày giờ/nhân viên → kiểm tra/xác nhận; desktop có tóm tắt, mobile có thanh thao tác | Giữ step semantics hiện có nếu khác đề xuất; tự động kiểm tra lại slot và nhân viên; trạng thái pending sau timeout |
| Đăng nhập `/auth/login` | Form gọn, nhãn rõ, show/hide password, lỗi tại trường và thông báo chung | `redirect` hợp lệ, session/token bridge, không redirect ngoài site |
| Đăng ký `/auth/register` | Form một cột, hướng dẫn mật khẩu lấy từ quy tắc backend, trạng thái submit | Không thêm điều kiện validation tự suy đoán; không gửi đăng ký hai lần |
| OTP `/auth/verify-otp` | Input thuận tiện dán mã, countdown nếu backend hỗ trợ, gửi lại và thông báo lỗi | Hạn dùng, resend limit, email/sessionStorage và luồng hiện hành |
| Quên/đặt lại mật khẩu | Cùng hệ form với đăng nhập | Giữ endpoint và token/OTP contract; không ghi dữ liệu nhạy cảm vào log |
| Hồ sơ `/profile` | Desktop sidebar, mobile tab/selector; phần nội dung tải theo tab | Họ tên, avatar, thông tin cá nhân, đổi mật khẩu, hash deep link |
| Lịch hẹn trong profile | Filter trạng thái → card mobile / table desktop → drawer chi tiết | Hủy, đổi dịch vụ, tiếp tục thanh toán, đánh giá chỉ hiện theo quyền/trạng thái thực tế |
| Hóa đơn trong profile | Danh sách + trạng thái + chi tiết tiền + CTA thanh toán phù hợp | Phân biệt chờ thanh toán, đang kiểm tra, đã thanh toán; server là nguồn xác nhận |
| Liệu trình trong profile | Card gói, số lượt còn, hạn dùng, lịch sử sử dụng, CTA đặt tiếp | Phân biệt lượt gói và quà; không tự trừ lượt sau click nếu server chưa xác nhận |
| Điểm thưởng / voucher | Số dư, giao dịch, quà có thể đổi, quà của tôi; giữ bộ lọc/query | Giữ idempotency khi đổi quà, điều kiện voucher và số điểm dùng được |
| Đánh giá của tôi | List/card; form đánh giá; xác nhận xóa | Quyền đánh giá theo lịch hẹn, sửa/xóa theo backend, refresh dữ liệu sau thao tác |
| Thông báo & quyền riêng tư | Nhóm tùy chọn dễ hiểu, trạng thái lưu và lỗi xung đột | Chỉ hiển thị khi cờ CRM/consent cho phép; giữ version khi cập nhật |
| Chat và tiện ích nổi | Một lối mở chat rõ, panel thích nghi mobile; nhạc là tùy chọn nhỏ | Giữ hội thoại, tin chưa đọc, chọn dịch vụ; không tự gửi tin/đăng ký nhận tin khi chỉ mở panel |

## 4. Đặc tả design system

Các giá trị dưới đây là đề xuất thiết kế, không phải dữ liệu doanh nghiệp. Bảng màu kế thừa gần với React booking hiện tại để giảm khác biệt khi chuyển đổi.

| Thuộc tính | Giá trị / nguyên tắc | Kiểm tra bắt buộc |
|---|---|---|
| Primary | `#425F49`; chữ trên primary `#FFFFFF` | Đo contrast thực tế cả normal/hover/disabled |
| Nền / surface | Nền `#F7F7F2`; card `#FFFFFF`; secondary `#EDF1E9` | Card phân biệt rõ mà không cần bóng đổ nặng |
| Text / muted / border | `#2E3C30` / `#606E60` / `#DCE3D8` | Nội dung nhỏ phải đủ tương phản; không dùng muted cho thông tin giá quan trọng |
| Typography | Ưu tiên một font sans hỗ trợ tiếng Việt; body 16px, phụ 14px, label 14–16px, H1 desktop 36–44px/mobile 28–32px | Không vỡ dấu tiếng Việt, không dùng chữ hoa cho toàn bộ menu/form |
| Spacing | 4, 8, 12, 16, 24, 32, 48, 64px | Dùng token; không thêm hàng loạt padding gần giống nhau |
| Radius | Input/button 8–10px; card 12–16px | Đồng bộ cả hai hệ component; hạn chế pill ngoài badge/chip |
| Layout | Container tối đa khoảng 1200px; lề 16px mobile, 24px tablet, 32px desktop | Không overflow ngang ở 360px; đoạn văn có chiều rộng đọc phù hợp |
| Control | Vùng chạm tối thiểu 44×44px cho hành động chính trên điện thoại | Nút icon có accessible name; icon không thay toàn bộ nhãn |
| Grid dịch vụ | Desktop 3 cột, tablet 2 cột; mobile 1 cột hoặc 2 cột khi nội dung vẫn đủ rõ | Không cắt giá/CTA; tên dài xuống dòng đúng |
| Ảnh | Tỉ lệ nhất quán 4:3 hoặc 16:9 theo component; có width/height và placeholder | Không đổi ảnh thật thành ảnh không liên quan; lazy load ảnh ngoài màn đầu |
| Trạng thái | Default, hover, focus, active, loading, disabled, empty, error, success | Disabled không chỉ đổi màu; lỗi có cách xử lý tiếp theo |
| Motion | 150–200ms cho tương tác nhỏ; tôn trọng reduced motion | Video có poster/fallback; nhạc không tự phát |
| Overlay | Z-index theo lớp header < thanh CTA < drawer/modal < thông báo | Không có hai backdrop; ESC đóng, focus trap và trả focus về trigger |
| Ngôn ngữ | Tiếng Việt đầy đủ trước; nếu giữ VI/EN phải kiểm kê chuỗi hiện hành | Không để “Loading...” hoặc chuỗi dịch dở dang trong luồng chính |

### 4.1 Bảng phân công component

| Nhóm | Triển khai ưu tiên | Quy tắc tái sử dụng |
|---|---|---|
| CustomerHeader, Footer, MobileNav | Custom theo phong cách shadcn, cùng token | Jinja macro cho public; React shell cho account/booking, cùng dữ liệu nav và kiểm tra parity |
| ServiceCard, PackageCard, PriceSummary | Component React custom / markup Jinja tương ứng | Các trường hiển thị cùng semantics; không copy logic tính tiền giữa các trang |
| Booking Button/Input/Card | Mở rộng `customer/ui.tsx` | Giữ API sử dụng hiện hành và thêm state/accessibility cần thiết |
| Account forms, validation | Ant Design Form/Input/Upload | Đọc lỗi backend; upload avatar xử lý cả file lớn/sai loại |
| Lịch sử và dữ liệu dạng bảng | Ant Design Table/Pagination trên desktop; card cùng dữ liệu trên mobile | Không dựng table khác nguồn dữ liệu; không tải hai lần cho hai breakpoint |
| Account tabs/empty/loading/tag | Ant Design | Theme theo token khách hàng; status có chữ ngoài màu |
| Modal/Drawer/Toast | Ant Design ở màn Ant; primitive hiện có hoặc shadcn tương thích ở màn custom khi thật sự cần | Một màn một cơ chế overlay; không cài cả bộ chỉ để có một hộp thoại |
| Thanh toán chuyển tiếp | Adapter cho `window.LoyaltyPayment` trước, React hóa sau khi có parity | Không giữ hai polling loop cùng theo dõi một hóa đơn |
| Auth/recommendations | Adapter TypeScript quanh bridge hiện có | Không nhân bản localStorage/session restore hoặc cơ chế ghi event |

## 5. Kiến trúc migration và file đích

Các file ghi “mới” dưới đây là đề xuất tạo, không phải file đã tồn tại.

| Khu vực | File hiện có cần đọc / sửa | File mới đề xuất | Ranh giới |
|---|---|---|---|
| Token và theme | `frontend/src/customer/booking.css`, `ui.tsx`, `app/static/css/customers/style.css` | `frontend/src/customer/theme.ts`, `tokens.css`; CSS token public được build/đồng bộ có quy trình | Một nguồn giá trị; tránh chỉnh thủ công hai bảng token rồi lệch |
| Customer entry | `frontend/vite.config.ts`, `app/ui_assets.py`, `customer_bp.py` | `frontend/src/customer-main.tsx`, `app/templates/customer/react_shell.html` | Giữ portal và booking entry; resolve đúng manifest key và CSS imports |
| Shared UI | `frontend/src/customer/ui.tsx` | `customer/components/ServiceCard.tsx`, `AsyncState.tsx`, `StatusBadge.tsx`, `CustomerShell.tsx` | Tách component khi có tái sử dụng hoặc logic đủ phức tạp; không phân mảnh mọi dòng JSX |
| Public rendering | `layout.html`, `index.html`, `services.html`, `service_detail.html`, `packages.html` | Jinja partial/macro trong `app/templates/customer/components/` khi cần | Server giữ title/meta và nội dung công khai quan trọng; React chỉ quản lý vùng đã mount |
| Profile | `profile.html`, `customers/profile.js`, `reviews.js`, `packages.js`, `customers/loyalty.js` | `customer/account/Profile.tsx`, `Appointments.tsx`, `Invoices.tsx`, `Treatments.tsx`, `Rewards.tsx`, `Reviews.tsx`, `Preferences.tsx` | Phân chia theo tab; lazy load hoặc tải dữ liệu khi tab được mở |
| API và model | `customer/api.ts`, `booking-model.ts`, legacy JS tương ứng | `customer/types.ts`, adapter theo nhóm khi cần | Không dùng API staff/admin cho khách hàng; không cast `any` để bỏ qua response mismatch |
| Booking | `Booking.tsx`, `booking-main.tsx`, `booking_react.html` | Tách component nhỏ nếu cần nhưng giữ model | Không rewrite state machine trong PR chỉ thay style |
| Auth | `auth-session.js`, `customers/auth.js`, template `auth/*` thực tế nằm trực tiếp trong `customer/` | Component form hoặc Jinja macro dùng chung | Giữ route `/auth/*`, API `/api/auth/*`; không đổi cơ chế bảo mật trong refactor UI |
| Kiểm thử | Test hiện hữu; `.agents/skills/playwright-cli/SKILL.md` khi dùng CLI | Test browser tập trung vào hành trình, test contract/asset cho entry mới | Không viết test chỉ kiểm tra class CSS cho mọi component |

### 5.1 Quy tắc chuyển đổi bắt buộc

1. Một vùng DOM chỉ có một chủ sở hữu: React hoặc legacy JS. Gỡ listener/script của vùng đã chuyển hoặc giới hạn mount target, không để cả hai cùng render.
2. Jinja public được phép giữ lại: mục tiêu là giao diện thống nhất và dễ bảo trì, không phải đổi tất cả file sang TSX.
3. Mỗi nhóm màn mới có gate tương tự booking; cờ đề xuất: `CUSTOMER_ACCOUNT_REACT_ENABLED`, `CUSTOMER_PUBLIC_UI_ENABLED`. Tên cuối cùng phải phù hợp cấu hình dự án.
4. Nếu manifest thiếu, cờ tắt hoặc `ui=legacy`, trang vẫn phục vụ bản cũ. Không redirect vòng giữa mới/cũ.
5. Không import `frontend/src/style.css` hoặc CSS admin hàng loạt vào customer entry. Kiểm tra cả CSS được kéo theo từ common chunk.
6. Với Ant popup render qua portal, kiểm tra nơi gắn popup, token và z-index; namespace root một mình không đảm bảo popup nhận style.
7. Build đầy đủ vì `emptyOutDir` có thể xóa output cũ. Không build riêng customer rồi bỏ mất portal nhân viên/admin.
8. Không đổi schema, cấu hình production hoặc deploy trong nhiệm vụ này. `AGENTS.md` yêu cầu được duyệt cho các việc đó.

## 6. Backlog chi tiết cho agent

Quy ước: P0 = nền tảng hoặc rủi ro giao dịch, P1 = chức năng chính, P2 = hoàn thiện. Mỗi dòng là đơn vị có thể giao agent; khi một dòng quá lớn, chia tiếp theo màn nhưng giữ nguyên tiêu chí. Trạng thái ban đầu của mọi task: **Chưa thực hiện**.

### Giai đoạn A — Khảo sát và chốt hợp đồng giao diện

| ID | Ưu tiên / phụ thuộc | Việc cần làm | File / đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| A01 | P0 / không | Đọc AGENTS, ghi commit, kiểm tra working tree, xác định scope customer | `docs/customer-ui/baseline.md` mới | Không ghi đè thay đổi người dùng; có danh sách file thuộc scope và shared dependencies |
| A02 | P0 / A01 | Lập route inventory: URL, template/entry, auth, flag, query/hash | `customer_bp.py`, `package_bp.py`; bảng route | Mọi route ở mục 3 có đối chiếu; route chưa rõ được ghi câu hỏi, không tự tạo |
| A03 | P0 / A02 | Chạy local bằng cấu hình test; chụp baseline các màn chính desktop/mobile | `docs/customer-ui/baseline.md`; ảnh QA nội bộ | Có trạng thái guest/customer, console và failed requests; lỗi có sẵn tách khỏi lỗi mới |
| A04 | P0 / A02 | Kiểm kê API/payload/status và globals/DOM hooks | JS customer, route liên quan; `contracts.md` mới | Ghi method, endpoint, auth, response mẫu đã ẩn dữ liệu, errors, DOM selector consumers |
| A05 | P1 / A03 | Chốt wireframe và component matrix cho home/services/detail/booking/profile | `design-spec.md` mới | Có desktop/mobile, thứ tự nội dung, CTA chính, loading/empty/error; không thiết kế thêm nghiệp vụ |
| A06 | P1 / A04 | Kiểm kê số liệu marketing, CS1/CS2, số điện thoại, giờ mở cửa, ảnh | Bảng content checklist | Những thông tin chưa xác minh được đánh dấu; không tự đổi địa chỉ/số điện thoại theo phỏng đoán |

### Giai đoạn B — Nền tảng UI và migration an toàn

| ID | Ưu tiên / phụ thuộc | Việc cần làm | File / đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| B01 | P0 / A05 | Xây token màu/font/spacing/radius và Ant theme cùng giá trị | `tokens.css`, `theme.ts`, CSS public | Trang mẫu hai hệ có cùng typography và control height; không dùng theme v6 |
| B02 | P0 / B01 | Chuẩn hóa Button/Input/Card hiện hữu; thêm empty/error/loading theo nhu cầu | `customer/ui.tsx`, component mới | Focus rõ, disabled đúng, loading không làm nhảy layout; booking hiện tại vẫn chạy |
| B03 | P0 / A04 | Xây customer shell/entry và gate theo nhóm; giữ legacy fallback | Vite, `ui_assets.py`, route/template | Tất cả entry build thành công; mở URL trực tiếp và refresh được; thiếu asset có fallback |
| B04 | P0 / B03 | Giới hạn CSS reset, kiểm tra popup/overlay, loại xung đột body/global selector | CSS customer và imports | Customer mới không thay đổi giao diện portal; modal đúng font/theme; không hai backdrop |
| B05 | P0 / A04 | Chuẩn hóa adapter API, auth restore, error mapping và cleanup request | `customer/api.ts`, `auth-session.js` | 401/422 liên quan xác thực vẫn xử lý đúng; lỗi validation không bị quy hết thành logout; retry không lặp vô hạn |
| B06 | P1 / B02+B03 | Header/footer/mobile nav cùng cấu trúc, active state, menu keyboard | `layout.html`, CustomerShell | Link cũ giữ nguyên; logo/menu/profile có accessible name; thanh đáy không che CTA |

### Giai đoạn C — Khám phá dịch vụ

| ID | Ưu tiên / phụ thuộc | Việc cần làm | File / đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| C01 | P1 / B06+A06 | Refactor home; giảm độ rối, chuẩn hóa hero và dịch vụ | `index.html`, `customers/main.js`, CSS | CTA rõ; một danh sách dịch vụ ưu tiên; ảnh/video không gây dịch chuyển layout lớn; không thêm số liệu giả |
| C02 | P1 / B02+A04 | Chuẩn hóa thẻ dịch vụ, giá/thời lượng/ảnh/CTA | ServiceCard hoặc Jinja macro, renderer cũ | Tên dài, giá 0/null theo contract, ảnh lỗi đều xử lý; không lồng button trong anchor |
| C03 | P1 / C02 | Refactor danh sách, search/filter/sort và state URL khi phù hợp | `services.html`, `customers/services.js` | Lọc kết hợp đúng; xóa filter khôi phục danh sách; sort mặc định giữ ranking backend |
| C04 | P1 / C02 | Refactor chi tiết, review summary, related items và mobile CTA | `service_detail.html`, `service-detail.js`, `reviews.js` | Đúng ID; dữ liệu không tồn tại có thông báo; CTA truyền đúng lựa chọn sang booking |
| C05 | P0 / C01+C03+C04 | Kiểm tra event tracking sau chuyển DOM/React | `recommendations.js`, adapter, tests | Một thao tác người dùng không bị ghi lặp do listener/StrictMode; gợi ý lỗi không chặn xem/đặt dịch vụ |
| C06 | P1 / C02+A04 | Refactor danh sách/chi tiết gói và thông tin điều kiện | `packages.html`, `packages.js`, route package | Phân biệt giá gói và giá lẻ; thời hạn/số buổi rõ; tuân thủ sale channels; pending purchase mở lại được |

### Giai đoạn D — Đặt lịch và thanh toán

| ID | Ưu tiên / phụ thuộc | Việc cần làm | File / đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| D01 | P0 / B02+B05+C02 | Đồng bộ giao diện booking, stepper, summary, mobile actions | `Booking.tsx`, `booking.css`, template | Lùi bước giữ lựa chọn hợp lệ; giá/thời lượng đúng; không viết lại model nếu không cần |
| D02 | P0 / D01 | Rà slot/staff khi đổi dịch vụ, ngày, tổng thời lượng | Booking, booking-model | Slot hết chỗ được bỏ chọn; không đặt giờ quá khứ; đổi ngày không giữ staff/slot không còn hợp lệ |
| D03 | P0 / D01 | Làm rõ dùng lượt liệu trình/quà và tiền bổ sung | Booking, booking-model | Chọn sai/hết hạn/không đủ lượt báo rõ; dùng toàn bộ lượt hợp lệ không ép trả thêm |
| D04 | P0 / D02+D03 | Cải thiện submit/loading/success và pending reconciliation | Booking | Double click không tạo hai yêu cầu chủ động; timeout sau gửi không retry create mù; pending gắn đúng khách hàng |
| D05 | P0 / A04+B04 | Chuẩn hóa vùng VietQR/hóa đơn/voucher/điểm bằng adapter trước | `loyalty-payment.js`, payment component | Số tiền lấy từ server; chờ xác nhận khác thành công; không tự mark paid; copy mã/số tài khoản có feedback |
| D06 | P0 / D05+C06 | Đồng bộ mua gói và tiếp tục thanh toán sau refresh | `packages.js`, profile invoice entry | Đóng/mở QR không tạo giao dịch mới; khôi phục purchase/invoice đúng người; polling có cleanup và giới hạn |
| D07 | P0 / D04+D06 | Chạy hồi quy kết hợp booking/prepay/voucher/gói và UI | Test booking, payments, packages hiện có | Kết quả test rõ; luồng lỗi có thể phục hồi; không sửa expected test để hợp thức hóa lỗi tiền/lượt |

### Giai đoạn E — Xác thực và tài khoản

| ID | Ưu tiên / phụ thuộc | Việc cần làm | File / đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| E01 | P1 / B02+B05 | Refactor login/register/OTP/forgot/reset | Template customer auth + `customers/auth.js` | Form bàn phím dùng được; paste OTP; redirect hợp lệ; lỗi sai mật khẩu/OTP/hết hạn rõ |
| E02 | P0 / B03+B05 | Tạo account shell, tab routing theo hash cũ và lazy data loading | `profile.html`, account shell | `/profile#appointments`, `#treatments` mở đúng; Back/Forward hoạt động; không tải toàn bộ phân hệ khi vào trang |
| E03 | P1 / E02 | Form hồ sơ, avatar, đổi mật khẩu | Profile component, API profile | Lưu thành công mới cập nhật thông tin; lỗi upload/validation hiển thị; avatar header đồng bộ |
| E04 | P0 / E02+D04 | Lịch hẹn: list, filters, detail, cancel/change services/review CTA | Appointments component, profile JS | Chỉ thao tác được khi backend cho phép; cancel có xác nhận; đổi dịch vụ cập nhật lại tiền/thời gian theo response |
| E05 | P0 / E02+D05 | Hóa đơn: lịch sử, chi tiết, thanh toán tiếp | Invoices component | Tổng trước/sau ưu đãi rõ; không cộng/trừ ưu đãi hai lần; trạng thái refresh sau thanh toán |
| E06 | P1 / E02+D03 | Liệu trình: lượt/hạn/lịch sử/đặt tiếp | Treatments component, packages adapter | Deep link booking giữ liệu trình đã chọn; quà và lượt gói không nhập nhằng |
| E07 | P0 / E02+D05 | Điểm thưởng, đổi quà, voucher của tôi | Rewards component, `customers/loyalty.js` | Giữ idempotency key cùng lần thử; không đổi quà lặp khi mạng chậm; trạng thái hết điểm/hết quà rõ |
| E08 | P1 / E02 | Đánh giá: danh sách, editor, sửa/xóa và trạng thái cập nhật | Reviews component, `reviews.js` | Chỉ đánh giá dịch vụ/lịch hợp lệ; lỗi có thể sửa lại; public và “của tôi” cập nhật sau thành công |
| E09 | P1 / E02 | Tùy chọn thông báo/quyền riêng tư | Preferences component | Flag tắt thì ẩn; version được gửi đúng; xung đột yêu cầu tải lại dữ liệu, không ghi đè im lặng |

### Giai đoạn F — Hoàn thiện và bàn giao

| ID | Ưu tiên / phụ thuộc | Việc cần làm | File / đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| F01 | P1 / B06+E02 | Đồng bộ chat, unread, service picker, tiện ích nổi | `main.js`, layout và script chat liên quan | Không tự tạo nhiều interval; logout hủy dữ liệu/loop phiên cũ; mobile keyboard không che input |
| F02 | P1 / C+E | Responsive 360/390/768/1024/1440px, zoom 200%, keyboard | CSS/component liên quan | Không overflow; focus hiện; modal vừa màn hình; bottom nav/CTA/chat không chồng |
| F03 | P1 / C+D+E | SEO/hiệu năng: metadata, ảnh, chunk, video, lazy tab | Template, Vite imports, assets | Public title/description/canonical đúng; không mất nội dung công khai chính; không kéo portal admin vào bundle public |
| F04 | P0 / D07+F02 | Test hồi quy chức năng, assets, auth, flags, full CI theo repo | Vitest/pytest/browser test và báo cáo | Chỉ ra pass/fail/blocked; không tuyên bố đạt khi thiếu DB hoặc browser |
| F05 | P1 / F04 | Dọn CSS/JS không còn dùng sau kiểm kê consumers | Asset inventory + diff cleanup | Không xóa file dùng chung admin/legacy; fallback vẫn chạy; không để hai listener cho một action |
| F06 | P0 / F04+F05 | Tài liệu rollout/rollback và PR/diff bàn giao | `release-checklist.md`, `progress.md` mới | Ghi rõ flags, entry assets, kiểm tra staging, rollback; chưa deploy nếu chưa có phê duyệt |

## 7. Hợp đồng API cần bảo toàn

Bảng này chỉ liệt kê endpoint đã thấy trong mã nguồn. Agent đọc route trước khi triển khai để ghi đầy đủ method, fields và mã lỗi; không suy ra quyền từ việc nút đang hiển thị.

| Nhóm | Endpoint / bridge đã thấy | Bất biến nghiệp vụ |
|---|---|---|
| Auth | `/api/auth/login/customer`, `/register`, `/verify-otp`, `/forgot-password`, `/reset-password`, `/resend-otp`, `/restore-session`, `/logout` (các đường dẫn rút gọn cùng prefix `/api/auth`) | Dùng CustomerAuth hiện hành; giữ safe redirect, restore và logout; không đổi cơ chế token trong PR UI |
| Catalog | `/api/services`, `/api/services/<id>`, `/api/services/<id>/reviews` | Danh sách và chi tiết đúng ID; giá/khả dụng/ranking lấy từ server |
| Recommendation | `/api/recommendations`, `/api/recommendations/events`, `/api/recommendations/related/<id>` | Giữ event name/payload và thứ tự; guest có fallback; explicit sort của người dùng phải có tác dụng |
| Booking | `/api/appointments/available-slots`, `/available-staff`, `/create`, `/my-appointments` cùng prefix `/api/appointments` | Tổng dịch vụ, ngày giờ, nhân viên, `package_usages`, `payment_option` không thay contract |
| Sửa lịch | `/api/appointments/<id>/cancel`, `/api/appointments/<id>/services` | Không tự chuyển trạng thái ở client; phản ánh response backend |
| Hồ sơ | `/api/profile`, `/api/profile/update`, `/api/profile/upload-avatar`, `/api/profile/change-password` | Quyền theo phiên; dữ liệu cá nhân không xuất vào fixture/log công khai |
| Hóa đơn | `/api/payment/invoices`, `/api/payment/invoices/<id>`, `/api/payment/invoices/<id>/generate-qr`; `window.LoyaltyPayment` | Chỉ server xác nhận thanh toán; đóng UI không đồng nghĩa hủy hóa đơn |
| Gói | `/api/packages`, `/<id>`, `/<id>/purchase`, `/payment-options`, `/my-purchases`, `/purchases/<id>`, `/purchases/<id>/status` cùng prefix `/api/packages` | Không tự mở phương thức tiền mặt nếu cờ không cho phép; invoice và purchase là hai loại ID khác nhau |
| Liệu trình | `/api/packages/my-treatments`, `/api/packages/my-treatments/<id>` | Giữ hiệu lực/hạn/lượt/quà và lịch sử theo backend |
| Loyalty | `/api/loyalty/me`, `/me/transactions`, `/rewards`, `/my-rewards`, `/rewards/<id>/redeem` cùng prefix `/api/loyalty` | Đổi quà dùng idempotency; không lấy tổng điểm thay cho available points |
| Reviews | `/api/reviews/my`, `/api/reviews`, `/api/reviews/<id>`, `/api/reviews/appointments/<id>/context` | Giữ điều kiện và quyền sửa/xóa; render text an toàn |
| Preferences | `/api/me/communication-preferences` | Giữ version và config gate; không tự opt-in |
| Chat | `/api/chat/conversations`, `/api/chat/conversations/<id>/messages` | Chỉ xem/gửi trong hội thoại được phép; kiểm tra cleanup polling |

## 8. Ma trận kiểm thử hành trình

Test các hành vi rủi ro; không tạo hàng trăm test chỉ so sánh tên class. Dùng tài khoản/dữ liệu test và môi trường local, không phát sinh thanh toán thật hoặc gửi thông báo thật.

| Mã | Tình huống | Kết quả mong đợi | Phương pháp |
|---|---|---|---|
| T01 | Guest vào home, tìm dịch vụ, mở chi tiết | Nội dung/ảnh/giá đúng; không ép đăng nhập khi chỉ xem | Browser |
| T02 | Không có dịch vụ hoặc request lỗi | Empty/error phân biệt, có thử lại, không spinner vô hạn | Browser với fixture/mock |
| T03 | Customer quay lại xem dịch vụ, đổi sort/filter | Ranking mặc định giữ; explicit sort và filter hoạt động đúng | API + browser |
| T04 | Click/view một dịch vụ sau mount lại | Không tăng event gấp đôi vì handler/StrictMode | Network inspection |
| T05 | Login từ CTA booking rồi quay lại | Giữ URL/lựa chọn hợp lệ, không redirect ngoài site | Browser |
| T06 | Token hết hạn, restore thành công/thất bại | Retry có giới hạn hoặc về login; không loop; không lộ dữ liệu phiên trước | Test adapter + browser |
| T07 | Chọn nhiều dịch vụ, đổi ngày, chọn staff | Slot theo tổng thời lượng; lựa chọn không hợp lệ bị xóa | Booking tests + browser |
| T08 | Slot vừa bị người khác đặt | Báo hết chỗ và cho chọn lại, không hiện success giả | Integration + browser |
| T09 | Submit hai lần / mạng timeout sau create | Không tạo lại mù; pending có đối soát và lối xem lịch | Test booking + network mock |
| T10 | Dùng lượt gói và quà; gói hết hạn | Tổng tiền/lượt đúng, báo điều kiện không hợp lệ | Package/booking tests |
| T11 | Đặt lịch trả tại spa / VietQR không khả dụng | Chỉ phương án backend cho phép được chọn | Browser + prepay tests |
| T12 | VietQR pending → paid | Hiển thị chờ rồi cập nhật từ server; polling dừng phù hợp | Payment tests + browser |
| T13 | Đóng QR rồi refresh/mở lại | Đúng invoice/purchase cũ, không tạo mới | Browser + invoice resume test |
| T14 | Voucher không đủ điều kiện/hết hạn/được áp dụng | Thông báo rõ, số tiền lấy từ response; không trừ hai lần | Loyalty voucher tests |
| T15 | Đổi quà double click/retry | Một lần đổi tương ứng idempotency key, số dư đúng | Loyalty tests |
| T16 | Hủy/đổi dịch vụ lịch hợp lệ và không hợp lệ | UI phản ánh quyền/trạng thái; backend từ chối vẫn hiện lỗi đúng | Appointment tests |
| T17 | Sửa avatar/profile/password sai dữ liệu | Validation rõ, không mất dữ liệu nhập không nhạy cảm | Browser + API tests |
| T18 | Đánh giá/sửa/xóa đánh giá | Chỉ tài nguyên của mình; danh sách refresh | Review tests + browser |
| T19 | Preferences version cũ / flag tắt | Báo xung đột; tính năng ẩn khi không bật | API + browser |
| T20 | Logout, đăng nhập khách khác | Không hiển thị pending booking, hóa đơn, chat hay cache của người trước | Browser |
| T21 | Mobile bàn phím mở, chat + bottom nav + CTA | Không che input/nút, scroll và focus đúng | Browser mobile |
| T22 | Cờ tắt, thiếu manifest entry, `ui=legacy` | Bản legacy phục vụ được, URL giữ nguyên | Route/asset tests |
| T23 | Build customer và mở admin/employee/manager | Không thiếu JS/CSS entry, không nhiễm theme/reset | Build + smoke browser |
| T24 | Deep link profile, services, packages; refresh/Back | Không trang trắng hoặc mất tab/ID | Browser |
| T25 | Ảnh lỗi, tên dài, màn 360px, zoom 200% | Không overflow, CTA đọc được, fallback ảnh đúng | Visual QA |
| T26 | Keyboard Tab/Shift+Tab/Enter/ESC | Thứ tự focus hợp lý; modal trap/restore focus; menu dùng được | Manual browser |

### 8.1 Lệnh kiểm tra đã đối chiếu với CI

```bash
npm --prefix frontend ci --no-fund
npm --prefix frontend run build
npm --prefix frontend test
python -m pytest -q --disable-warnings
```

Chuẩn bị Python dependencies, test DB và environment theo README/CI trước khi chạy pytest. Không dùng DB production. Trong lúc làm từng PR, ưu tiên nhóm test liên quan; trước bàn giao chạy gate CI đầy đủ theo repo. Nếu không chạy được, ghi lệnh, lý do và phần chưa xác minh.

Các file test đáng ưu tiên: `tests/test_customer_static_assets.py`, `test_ui_navigation_and_ratings.py`, `test_recommendations.py`, `test_booking_time_slots.py`, `test_booking_gifts_reviews.py`, `test_prepay_booking.py`, `test_invoice_resume.py`, `test_package_login_required.py`, `test_package_sale_channels.py`, nhóm `test_loyalty_*.py`, `frontend/src/customer/booking-model.test.ts`. Đây là danh sách chọn lọc, không thay thế việc đọc dependency của diff.

### 8.2 Tiêu chí hiệu năng và khả năng truy cập

- Mục tiêu thiết kế: contrast chữ thông thường tối thiểu 4.5:1, chữ lớn 3:1; focus rõ; giảm motion theo cài đặt hệ thống.
- Đo baseline và bản mới cùng máy/network/viewport; lưu điều kiện đo. Mục tiêu tham khảo LCP ≤2.5s, CLS ≤0.1; không coi phép đo local là chứng nhận dữ liệu người dùng thật.
- Không bắt mọi chỉ số Lighthouse đạt 100. Nếu video hero làm chậm, dùng poster và tải có điều kiện; ảnh dưới fold lazy load.
- So sánh bundle mỗi entry: public/customer không import toàn bộ portal. Ghi kích thước trước/sau và giải thích tăng nếu có.
- Kiểm tra console errors và failed requests; phân biệt lỗi do third-party có sẵn với regression do refactor.

## 9. Chia PR, ước lượng và checkpoint

Ước lượng là thời gian người phát triển thực hiện và kiểm tra, không phải cam kết thời gian agent. Các khoảng có thể chồng lấp nhưng không được bỏ dependency.

| PR / đợt | Task chính | Khoảng công tham khảo | Điều kiện chuyển đợt |
|---|---|---|---|
| PR0 — khảo sát | A01–A06 | 1–2 ngày | Baseline, contract và wireframe đủ rõ |
| PR1 — nền tảng | B01–B06 | 2–3 ngày | Entry/theme/fallback hoạt động, booking cũ không hỏng |
| PR2 — public | C01–C05 | 2–4 ngày | Home/list/detail và ranking đạt QA |
| PR3 — gói/booking/payment | C06, D01–D07 | 3–5 ngày | Giao dịch và lỗi timeout có bằng chứng test |
| PR4 — auth/profile | E01–E06 | 3–5 ngày | Deep link, lịch hẹn, hóa đơn, liệu trình ổn |
| PR5 — loyalty/reviews/preferences | E07–E09, F01 | 2–3 ngày | Không mất quyền/trạng thái/idempotency |
| PR6 — hardening | F02–F06 | 2–3 ngày | CI và QA có kết quả, tài liệu rollout/rollback đầy đủ |

Tổng tham khảo: 15–25 ngày công cho migration đầy đủ, tùy chất lượng baseline và mức chuyển React. Nếu cần bản sớm, hoàn thành PR0–PR2 để thay giao diện khám phá; giữ booking/profile hiện hữu cho đến khi test đủ. Không làm tất cả trong một PR rất lớn.

Mỗi checkpoint cập nhật `docs/customer-ui/progress.md`:

| Task ID | Trạng thái | File thay đổi | Bằng chứng kiểm tra | Vấn đề còn lại | Bước tiếp theo |
|---|---|---|---|---|---|
| Ví dụ B03 | Chưa làm / Đang làm / Xong / Bị chặn | Đường dẫn cụ thể | Lệnh + kết quả hoặc ảnh QA local | Mô tả cụ thể, không chỉ “cần test” | Task ID tiếp theo |

## 10. Rủi ro và cách xử lý

| Rủi ro | Dấu hiệu | Cách kiểm soát |
|---|---|---|
| React và legacy cùng sở hữu DOM | Ghi event/gửi request hai lần, nội dung nhấp nháy | Một mount target một owner; kiểm kê event listener; cleanup sau unmount |
| Hai hệ UI không đồng nhất | Nút/input/modal lệch font/radius/màu | Token chung, một họ control mỗi form, kiểm tra popup ngoài root |
| Gãy session | Login thành công nhưng header/booking vẫn guest | Tái dùng CustomerAuth; kiểm tra session restore và đồng bộ header |
| Tạo lịch/giao dịch lặp | Retry sau timeout tạo bản ghi mới | Giữ pending marker và reconciliation; không coi UI disable là idempotency toàn hệ thống |
| Tính tiền sai | Voucher/điểm/lượt gói cộng trừ nhiều nơi | Backend là nguồn số tiền cuối; reuse model/adapter và test giao dịch |
| Xóa nhầm tài nguyên shared | Admin/legacy mất CSS/JS sau cleanup | Lập consumers map; test các màn dùng chung trước khi xóa |
| Build mất entry cũ | Booking chạy nhưng portal trắng | Build multi-entry đầy đủ, kiểm tra manifest và asset |
| Mất SEO hoặc deep link | Refresh 404, title chung, hash không mở tab | Flask giữ route; metadata/public HTML; smoke refresh và bookmark |
| Hồi quy recommendation | UI tự sort alphabet sau khi backend rank | Default order giữ nguyên, explicit sort mới override; test guest/customer |
| Nội dung doanh nghiệp sai | Số điện thoại text khác tel, số liệu thiếu nguồn | Ghi checklist cần xác minh, không tự bịa thông tin mới |

## 11. Definition of Done và rollback

Một task chỉ được đánh dấu Xong khi:

1. Có file thay đổi cụ thể, không có refactor ngoài scope.
2. Chức năng đúng ở trạng thái success/loading/empty/error phù hợp.
3. Đã kiểm tra mobile và desktop với dữ liệu test; lỗi chưa test được ghi rõ.
4. Không tạo lỗi console/request mới thuộc thay đổi; không rò dữ liệu khách hàng qua log hoặc cache phiên khác.
5. Test nghiệp vụ liên quan pass; không xóa assertion tiền/lượt/quyền để làm test xanh.
6. Route/query/hash/API và fallback giữ đúng hợp đồng.
7. Có checkpoint và mô tả cách kiểm tra lại.

Trước rollout: build từ commit đã kiểm tra, lưu artifact tương ứng, test staging với cờ từng nhóm; xác định ai bật cờ và ai theo dõi. Không thay cấu hình production hoặc deploy khi chưa được duyệt theo AGENTS.md.

Rollback: tắt cờ UI của nhóm vừa chuyển trong môi trường được phép hoặc quay về release/asset đã xác minh; kiểm tra manifest/legacy. Không rollback dữ liệu giao dịch chỉ vì rollback giao diện. Vì kế hoạch không thay schema, rollback UI không yêu cầu migration database.

## 12. Prompt giao agent thực hiện

Copy nguyên khối dưới đây cùng file kế hoạch vào agent có checkout repo:

```text
Bạn là coding agent refactor giao diện KHÁCH HÀNG của Bin Spa.
Repository: dangkhoa18052004/SPA.
Đọc BinSpa_KeHoach_Refactor_UI_KhachHang_Agent.md và AGENTS.md trước khi làm.

MỤC TIÊU
- Giao diện tối giản, mobile-first, nhất quán, dễ đặt lịch và quản lý tài khoản.
- Ưu tiên Ant Design cho form/account/history và UI nghiệp vụ; dùng phong cách
  shadcn/component hiện có cho public cards/layout và booking.
- Dùng token chung. Một form chỉ dùng một họ control chính.
- Tận dụng React booking, CustomerAuth, LoyaltyPayment và API hiện có.

PHẠM VI VÀ RÀNG BUỘC
- Chỉ customer/public. Không refactor admin/staff/manager ngoài compatibility tối thiểu.
- Không đổi schema DB, business rules, API contract, production config hoặc deploy.
- Không thêm framework mới hoặc nâng major dependencies chỉ để đổi giao diện.
- Giữ URL/query/hash, auth/session, ranking và events recommendation.
- Giữ CS1/CS2. Thông tin doanh nghiệp chưa xác minh phải ghi vấn đề riêng.
- Không tạo dữ liệu marketing, đánh giá, con số hoặc thông tin dịch vụ giả.
- Không gửi email/tin nhắn hoặc thanh toán thật khi test.

CÁCH THỰC HIỆN
1. Xác định commit và working tree; đọc đúng file liên quan, không scan/dump toàn repo.
2. Hoàn thành A01-A06: route inventory, baseline browser, API contract, shared scripts,
   wireframe và nội dung chưa xác minh. Tạo docs/customer-ui/progress.md.
3. Làm theo thứ tự PR0-PR6 và dependency từng task. Sau mỗi đợt, verify rồi checkpoint.
4. Mở rộng customer entry qua Vite manifest nhưng giữ portal/booking entries.
5. Migration từng nhóm; cờ mới mặc định an toàn và có legacy fallback.
6. Mỗi DOM subtree chỉ có một owner. Dọn listener/polling khi chuyển hoặc unmount.
7. Giữ pending reconciliation của Booking.tsx; không retry create mù sau timeout.
8. Số tiền, trạng thái paid, quyền thao tác, lượt gói và điểm thưởng lấy từ backend.
9. Dùng Playwright CLI theo hướng dẫn repo để kiểm tra local. Xem console/network,
   ảnh trước-sau các màn chính; kiểm tra 360/390/768/1024/1440px và keyboard.
10. Chạy test liên quan mỗi PR; trước bàn giao chạy frontend build, Vitest, pytest
    theo CI. Nếu thiếu môi trường, ghi chính xác phần bị chặn, không tuyên bố pass.
11. Chỉ xóa legacy assets sau khi chứng minh không còn consumer và fallback vẫn đúng.

TIÊU CHÍ BẮT BUỘC
- Xem dịch vụ → đặt lịch → xác nhận → thanh toán/tiếp tục thanh toán hoạt động.
- Không đặt trùng do double click/retry; không cộng trừ tiền hoặc lượt sai.
- Profile: hồ sơ, lịch hẹn, hóa đơn, liệu trình, điểm thưởng, đánh giá, preferences đủ parity.
- Không mất cá nhân hóa, không nhân đôi tracking, không nhiễm CSS sang portal.
- Cờ tắt/thiếu asset/ui=legacy vẫn phục vụ giao diện cũ.

BÁO CÁO MỖI CHECKPOINT
- Task đã hoàn thành và file thay đổi.
- Quyết định thiết kế/kiến trúc có ảnh hưởng.
- Lệnh/test đã chạy, kết quả, màn đã xem bằng browser.
- Hạng mục chưa kiểm chứng và blocker thật.
- Task tiếp theo; không yêu cầu xác nhận lại cho các chỉnh sửa local thông thường
  đã thuộc phạm vi. Nếu cần schema/production/deploy thì dừng đúng phần đó và
  nêu quy định AGENTS.md cùng đề xuất cụ thể để chủ dự án quyết định.

Bắt đầu khảo sát và triển khai PR0 rồi PR1, tiếp tục các đợt sau theo kế hoạch
trong phạm vi được giao. Không dừng ở việc chỉ viết lại kế hoạch này.
```

## 13. Nguồn mã tham chiếu

- [Frontend dependencies](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/frontend/package.json)
- [Build entries](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/frontend/vite.config.ts)
- [Customer routes và booking fallback](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/app/routes/customer_bp.py)
- [Customer layout](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/app/templates/customer/layout.html)
- [Trang chủ](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/app/templates/customer/index.html)
- [React booking](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/frontend/src/customer/Booking.tsx)
- [API bridge](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/frontend/src/customer/api.ts)
- [Profile](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/app/templates/customer/profile.html)
- [Hướng dẫn agent của repo](https://github.com/dangkhoa18052004/SPA/blob/c189ad9f21e78ba423455c55e9181ef109478749/AGENTS.md)

Các file đích mới, flag mới, thời gian và thiết kế trong tài liệu là đề xuất triển khai; không được hiểu là tính năng đã tồn tại hoặc kết quả đã được kiểm thử.

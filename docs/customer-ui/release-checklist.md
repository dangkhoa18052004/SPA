# Rollout và rollback

## Trạng thái

Phần nền tảng đã commit tại `ad68001`; HEAD đối chiếu ngày 19/10/2026 là `38e100d`. Các bổ sung E06–E09 và sửa lỗi theo phản hồi hiện nằm trong working tree, chưa commit hoặc tạo PR trong lượt này. Không đổi cấu hình production hoặc deploy. Các cờ customer mới mặc định **false**. API hủy purchase bổ sung theo yêu cầu người dùng được ghi riêng trong `purchase-cancellation.md`; E09/F không đổi API hay schema.

Kiểm tra HTTP chỉ đọc trên LAN ngày 19/10: `/`, `/services`, `/packages`, `/auth/login`, `/profile` chưa có entry public/account mới; `/appointments/create` có entry booking. Đây là trạng thái asset được quan sát, không suy ra chính xác nguyên nhân cấu hình. Chưa bật rollout các nhóm còn legacy.

| Cờ | Phạm vi | Entry |
|---|---|---|
| `CUSTOMER_PUBLIC_UI_ENABLED` | Home, services/detail, packages và CSS/auth enhancement | `src/customer-main.ts` |
| `CUSTOMER_ACCOUNT_REACT_ENABLED` | Shell profile, forms và history panels; các vùng liệu trình/loyalty/review/preferences giữ owner hiện hành | `src/customer-account-main.tsx` + lazy `customer/account-panels.tsx` |
| `CUSTOMER_BOOKING_REACT_ENABLED` (đã có) | Booking React hiện hành | `src/booking-main.tsx` |

Public và account độc lập. Profile thiếu account asset sẽ dùng **toàn bộ form legacy**, không render hai owner. `?ui=legacy` luôn ưu tiên và giữ URL/query/hash. Manifest customer kiểm tra cả imported JS, CSS và lazy chunks; thiếu asset sẽ fallback. Nếu mất chunk sau khi HTML đã tải, account có link mở legacy giữ nguyên tab/query.

## Xem và kiểm tra local

```powershell
npm --prefix frontend run build
python tests/customer_ui_preview.py --new-ui --preferences --port 5079
playwright-cli -s=customer-ui open http://127.0.0.1:5079/ --browser=msedge
```

Preview chỉ bind loopback, dùng SQLite in-memory và dữ liệu test; `/__preview/session?customer=1` tạo phiên test, `/__preview/session` về guest. Hai route này **chỉ tồn tại trong preview script**, không được đăng ký bởi ứng dụng thật. Email và provider polling bị vô hiệu hóa. Không sử dụng preview làm production server.

Các script `tests/customer-ui-*.playwright.js` chạy qua `playwright-cli ... run-code --filename=...`. Public/account/transaction scripts dùng port 5078 với preview `--new-ui`; auth/preferences/hardening dùng 5079 với `--new-ui --preferences`; baseline/performance cần legacy preview port 5077.

Các suite bổ sung treatments/rewards/reviews/preferences-final/final-hardening và purchase cancellation dùng preview `--new-ui --preferences --port 5080`. Lượt kiểm tra cuối dùng bản sao ignored của các script cũ để đổi 5078/5079 thành 5080; giữ nguyên assertions, tên file nguồn và log trong `.test-tmp/customer-ui-final`. Cần legacy preview 5077 cho flag-off và so sánh hiệu năng.

Build nghiệm thu có thể xuất riêng để tránh thay asset mà các phiên LAN đang dùng:

```powershell
npm --prefix frontend run build -- --outDir E:/Project/Spa/SPA/.test-tmp/customer-ui-final/portal
```

Lượt E09/F đã đối chiếu manifest output riêng với `app/static/portal/.vite/manifest.json`: giống hệt; preview vẫn dùng đúng build tương ứng. Các sửa E09/F là static JS/CSS/Jinja. Không dùng thư mục test làm release; khi triển khai được duyệt phải bàn giao trọn bộ output/manifest đúng revision.

```powershell
npm --prefix frontend test
node --test tests/*.test.cjs
python -m pytest tests -q --ignore-glob='*.tmp' --disable-warnings --tb=short
```

Lệnh pytest local giới hạn `tests` và bỏ browser-profile `.tmp` cũ để tránh collection quét artifact. Lệnh CI gốc vẫn là `python -m pytest -q --disable-warnings`. Không thay assertions tiền/lượt/quyền để làm xanh tests. Kết quả và phần chưa xác minh xem `qa-results.md`.

## Trước rollout staging

1. Review diff theo checkpoint: foundation → public → booking/payment → account → loyalty/preferences/hardening. Khi tách PR, mỗi PR phải build đầy đủ, giữ các entry cũ.
2. Build đúng revision đã review; lưu manifest cùng **toàn bộ** output `app/static/portal`. `emptyOutDir` xóa asset cũ, vì vậy chuẩn bị output ngoài release đang phục vụ rồi chuyển release đồng bộ. Giữ asset cũ cho phiên đang mở theo quy trình hosting để lazy imports không bị đứt; không build riêng customer rồi bỏ portal/booking.
3. Test PostgreSQL chuyên dụng như CI qua `TEST_LOYALTY_POSTGRES_URL`; không dùng DB production. Kiểm tra các test thời gian bị skip với fixture phù hợp.
4. Kiểm tra native zoom 200%, iOS/Android keyboard, focus, chat/navigation/CTA và upload avatar. Đo lại hiệu năng trên staging/network đại diện.
5. Xác minh CS1 text/tel, cả hai địa chỉ/giờ mở cửa, nguồn ảnh và nguồn các thông tin marketing trước khi công bố. Không tự bật lại số liệu/testimonial chưa xác thực.
6. Chỉ người được chủ dự án cho phép mới thay config/deploy theo `AGENTS.md`. Bật từng nhóm; theo dõi lỗi JS/API, auth restore, booking pending, payment status và asset 404.

## Rollback

- Tắt đúng cờ nhóm vừa chuyển trong môi trường đã được cho phép, hoặc phục hồi release cùng manifest/assets đã kiểm chứng. `ui=legacy` là lối kiểm tra khẩn cấp ở từng URL.
- Kiểm tra lại `/`, `/services`, `/packages`, `/profile#appointments`, `/appointments/create?ui=legacy` và portal admin/employee/manager.
- Không xóa/rollback dữ liệu lịch hẹn, hóa đơn, gói, loyalty hoặc phiên giao dịch chỉ vì rollback UI.
- Không cần migration DB cho rollout/rollback này.

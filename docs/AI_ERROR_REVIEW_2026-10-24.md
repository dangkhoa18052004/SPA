# Kiểm tra lỗi gợi ý soi da, chat và tóm tắt kinh doanh — 24/10/2026

## Đã sao lưu và migrate database thật sau phê duyệt

Ngày 24/10/2026, người dùng xác nhận **“cho phép sao lưu database và chạy migration”**. Đã thực hiện trên database đang phục vụ `192.168.1.160:5000`:

- Backup đầy đủ định dạng custom: `backups/skin-map-before-20261024_0026-20261024-105709.dump`, **18.446.058 bytes**. Xác minh archive có dữ liệu các bảng ứng dụng và đọc/giải nén toàn bộ bằng `pg_restore` thành công. Backup nằm trong thư mục được git-ignore, không đưa vào tài liệu công khai hay commit.
- Chạy đúng Alembic migration **`20261023_0025 → 20261024_0026`**, với lock timeout 10 giây và statement timeout 120 giây. Không sửa migration cũ, không deploy hoặc thay cấu hình production.
- Đối chiếu số dòng và SHA-256 toàn bộ dữ liệu theo khóa chính của **11 bảng**: dịch vụ, nhân viên, khách hàng, kết quả soi da, 5 bảng loyalty, hóa đơn và thanh toán. Kết quả trước/sau giống nhau.
- Bảng `skin_service_map`, index, hai FK và constraint được tạo thành công. **0 ánh xạ được thêm**, không tự chọn hoặc duyệt dịch vụ.
- API `/api/admin/skin-service-map` trên ứng dụng đang chạy trả **200**, `schema_ready=true`, `source=empty`, 55 dịch vụ đang hoạt động, 5 nhóm loại mụn; trang `/admin/skin-service-map` trả **200**. Không cần khởi động lại ứng dụng.
- Biên bản không chứa token hay dữ liệu khách: `output/ai-errors-2026-10-24/live-migration.log`, `live-migration-verification.json`, `live-mapping-api-verification.json`.

Để có gợi ý dịch vụ thực tế, quản lý cần chọn dịch vụ cho từng loại mụn và **Lưu và duyệt**, theo hướng dẫn cuối tài liệu.

## Nguyên nhân đã xác minh trước migration

1. Database đang chạy ở `20261023_0025`, chưa có bảng `skin_service_map` của migration `20261024_0026`. Code gợi ý mới truy vấn bảng chưa tồn tại nên lỗi server; trang khách không nhận JSON hợp lệ và hiện câu chung “Chưa lấy được gợi ý dịch vụ lúc này”. `SKIN_SERVICE_MAP` trong cấu hình hiện cũng rỗng, nên chưa có dịch vụ được quản lý duyệt cho từng loại mụn.
2. Hàm gọi Gemini dùng chung hardcode hướng dẫn “dùng trang Đặt lịch”. Cả chat và business summary đi qua hàm này, nên business summary hiện sai ngữ cảnh khi hết deadline 22 giây.
3. Model chính có thể dùng hết deadline trước khi các model dự phòng được thử. Một job chat gần nhất lưu FAILED/504. Probe ngắn: model chính và alias dự phòng bị ReadTimeout; model lite còn trả 200. Không có bằng chứng key bị thiếu hoặc vô hiệu.

## Đã sửa trong mã nguồn

- `app/services/ai_service.py`: thông báo provider trung tính, chia budget cho các fallback thay vì thử lại primary trước; đặt deadline hữu hạn cho cả lời gọi từ gợi ý; dùng lại model đã thành công cho các vòng tool trong cùng request và bỏ model vừa lỗi.
- `app/services/ai_chat_jobs.py`: tách trạng thái provider của từng job để model/lỗi từ job trước không rò sang job sau.
- `app/routes/ai_bp.py`: timeout/lỗi business summary nói về tóm tắt kinh doanh và số liệu báo cáo, không chỉ sang Đặt lịch.
- `app/services/skin_recommendation_service.py`: kiểm tra tồn tại bảng trước khi đọc; khi chưa migrate chỉ dùng map môi trường đã cấu hình rõ ràng. Nếu không có map thì trả trạng thái chưa có dịch vụ phù hợp, không tự suy đoán hay tự duyệt dịch vụ.
- `app/services/skin_service_map_service.py`, `app/admin/skin_service_map_bp.py`, `app/static/js/admin/skin-service-map.js`, `app/templates/admin/skin_service_map.html`: trả `schema_ready`, giải thích chưa cập nhật cấu hình, chặn lưu khi bảng chưa sẵn sàng, đổi version script tránh cache cũ.
- Test bổ sung: `tests/test_ai_resilience.py`, `tests/test_ai_chat_jobs.py`, `tests/test_skin_service_map.py`; cập nhật test fallback tại `tests/test_ai_booking_agent.py`. Fixture/browser: `tests/ai_errors_preview.py`, `tests/ai-errors.playwright.js`.

## Kết quả kiểm tra

- Bộ AI booking/summary, job, soi da và map trước chỉnh sửa cuối: **102 passed**. Sau chỉnh trạng thái provider cuối cùng: **12 passed** cho fallback, deadline, context, worker isolation, thiếu bảng và migration.
- Migration `0026` được upgrade/downgrade trên SQLite/PostgreSQL 17 riêng: **3 passed**, giữ bảng dịch vụ/nhân viên có sẵn. Không chạy migration database ứng dụng.
- Node chat UI: **5 passed**; JS syntax và diff check đạt.
- Playwright: **3 luồng đạt**: lỗi summary đúng ngữ cảnh, map chưa sẵn sàng chặn lưu có giải thích, gợi ý soi da thiếu map hiển thị trạng thái trống; không page error/request failure. Dữ liệu và ảnh đều tổng hợp trên SQLite riêng.
- Probe Gemini qua hàm sửa: chuyển được sang lite sau khoảng 16 giây; lời gọi tiếp theo cùng context dùng lại lite và xong khoảng 2,4 giây. Không gửi ảnh hay dữ liệu khách.
- Gọi lại API trên môi trường đang chạy: `/api/ai/business-summary` cho ngày 24/10 trả **200**, có 4 facts và nhận xét AI, khoảng **5,25 giây**. `/api/admin/skin-service-map` trả **200**, `schema_ready=false`, `source=empty`. Đây là đọc/tóm tắt số liệu, không thay database hay cấu hình.
- Bằng chứng: `output/ai-errors-2026-10-24/` gồm log test, browser, probe provider, kiểm tra API và ảnh giao diện.

## Thao tác quản lý sau migration

Phần backup/migration đã được người dùng cho phép và đã hoàn tất như biên bản đầu tài liệu. Migration chỉ thêm bảng ánh xạ và index/FK, không điền hoặc tự duyệt dịch vụ, không đổi model/key/cấu hình production, không deploy.

Sau khi bảng sẵn sàng, quản lý vào **Dịch vụ theo loại mụn**, tự chọn hoặc nhờ Gemini đề xuất rồi kiểm tra và **Lưu và duyệt**. Có bảng mà chưa duyệt map vẫn chưa có ứng viên để gợi ý; hệ thống tiếp tục hiển thị thông báo chưa có dịch vụ được chọn sẵn.

## Bổ sung trang quản trị React

Trước chỉnh sửa, chức năng chỉ có trang cũ, chưa có menu và màn hình trong giao diện mới. Đã bổ sung **Chăm sóc → Dịch vụ theo loại mụn** cho admin/quản lý tại `/admin/skin-service-map`, điều hướng trong cùng giao diện React. Khi tắt nhóm giao diện mới hoặc dùng `?ui=legacy`, trang cũ vẫn dùng được.

- `frontend/src/admin/care/SkinServiceMap.tsx`: chọn/tìm dịch vụ theo 5 nhóm, đề xuất Gemini chỉ tạo bản nháp, hiển thị phần thêm/bỏ và lý do, xác nhận trước khi lưu duyệt, giữ lựa chọn khi API lỗi. Hiển thị người/thời gian duyệt và chặn thao tác khi dữ liệu chưa sẵn sàng.
- Menu/route: `frontend/src/admin/navigation.ts`, `frontend/src/main.tsx`, `app/admin/admin_bp.py`; bố cục thích ứng trong `frontend/src/admin/care/care.css`.
- Kiểm tra: **72 test frontend đạt**, build thành công; **36 test backend đạt, 1 bỏ qua** (test PostgreSQL tùy chọn cần URL riêng). Playwright đạt 4 nhóm luồng: menu/đề xuất/chỉnh sửa/lưu/tải lại; lỗi API giữ bản nháp; mobile 390/360px và duyệt rỗng; quyền admin/quản lý và chặn lễ tân. Không lỗi JavaScript hoặc request thất bại ngoài lỗi HTTP 502/503 chủ động giả lập.
- Log và ảnh: `output/skin-map-react-2026-10-24/`. Test trình duyệt dùng SQLite và dữ liệu tổng hợp riêng; không lưu hoặc duyệt ánh xạ trên database thật.
- Kiểm tra chỉ đọc trên ứng dụng đang chạy: trang trả **200**, dùng shell React thay cho editor cũ; bundle mới trả **200**, manifest có chunk `SkinServiceMap.tsx`. Biên bản: `live-page-verification.json`.

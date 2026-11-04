# Soi da bằng AI (phát hiện và phân loại mụn)

Khách hàng tự chụp hoặc tải ảnh khuôn mặt tại `/skin-analysis`. Website chuyển ảnh sang **dịch vụ AI cục bộ** (repo `E:\Project\BinSpa_AI`, `api/server.py`), lưu kết quả và ảnh **khi khách đã đồng ý**, rồi vẽ vị trí nốt mụn lên ảnh.

## Chạy trên máy

1. **Chạy dịch vụ AI** (cần GPU; chờ đến khi in dòng "BinSpa AI service on ..." là model đã nạp xong):
   ```powershell
   cd E:\Project\BinSpa_AI
   .\venv\Scripts\python.exe api\server.py --port 8008
   ```
   Kiểm tra: mở `http://127.0.0.1:8008/health`.

2. **Bật chức năng trên website:** thêm vào `.env` của website.
   ```
   SKIN_ANALYSIS_ENABLED=true
   AI_SKIN_URL=http://127.0.0.1:8008
   # Tùy chọn: khóa dùng chung, phải trùng với biến BINSPA_AI_KEY của dịch vụ AI
   # AI_SKIN_KEY=...
   # AI_SKIN_TIMEOUT=60
   ```

3. **Tạo bảng:** chạy `flask db upgrade`. Lệnh này áp dụng migration `20261021_0024_skin_analysis` và chỉ thêm bảng `skin_analysis`, không sửa bảng cũ.

4. Chạy website như bình thường, đăng nhập bằng tài khoản khách hàng rồi mở `/skin-analysis`.

Khi `SKIN_ANALYSIS_ENABLED` tắt (mặc định), trang và API trả 404. Nếu dịch vụ AI chưa chạy, khách sẽ thấy thông báo "Dịch vụ phân tích da đang tạm ngừng" (503), không có lỗi hệ thống.

## API (chỉ dành cho khách đã đăng nhập, `Cache-Control: private, no-store`)

| Method | Đường dẫn | Mô tả |
|---|---|---|
| POST | `/api/me/skin-analyses` | multipart: `image` và `consent=<CONSENT_VERSION>`. Ảnh bị yêu cầu chụp lại (`retake_photo`) không được lưu |
| GET | `/api/me/skin-analyses` | 20 lần phân tích gần nhất |
| GET | `/api/me/skin-analyses/<id>` | Chi tiết: vị trí, loại mụn, số lượng |
| GET | `/api/me/skin-analyses/<id>/image` | Ảnh, chỉ chủ tài khoản xem được |
| GET | `/skin-analysis/<id>` | Trang chi tiết; dữ liệu và ảnh vẫn lấy qua API kiểm tra chủ tài khoản |
| DELETE | `/api/me/skin-analyses/<id>` | Xóa kết quả và file ảnh (kèm gợi ý đã lưu tạm) |
| POST | `/api/me/skin-analyses/<id>/recommendations` | JSON `{"consent": "<RECOMMENDATION CONSENT_VERSION>"}`. Dịch vụ gợi ý cho lần phân tích này (xem mục bên dưới). 404 khi `SKIN_RECOMMENDATIONS_ENABLED` tắt |

Trạng thái kết quả:
- `ok`: có loại mụn cho các nốt AI chắc chắn.
- `location_only`: ảnh khác ảnh huấn luyện hoặc quá ít nốt, nên chỉ hiển thị vị trí.
- `retake_photo`: ảnh mờ, tối, mặt nhỏ…, kèm lý do bằng tiếng Việt.
- `demo`: dịch vụ AI chạy với `--demo`. Mọi nốt có top-1 hợp lệ đều có loại mụn, nốt chưa chắc được đánh dấu `low_confidence`. Trang kết quả hiển thị tối đa 8 điểm có điểm số cao nhất, không hiện banner thử nghiệm; trong lịch sử vẫn có nhãn "Thử nghiệm". Trạng thái và cờ tin cậy của API được giữ nguyên.

### Điểm "đủ tin cậy" và kết quả nổi bật

Mỗi điểm trong `lesions` có `id` theo thứ tự prediction gốc của AI (không đổi khi sắp xếp/lọc; số trên ảnh là `id`), `bbox` (null nếu tọa độ lỗi: vẫn liệt kê, không vẽ), `type/label/probability`, `low_confidence`, `reliable`, `alternatives`.

- `reliable = true` chỉ khi kết quả là `ok`, AI gắn `type_status = "confident"` (xác suất top-1 đã hiệu chỉnh ≥ ngưỡng của dịch vụ AI) và loại/xác suất hợp lệ (loại thuộc 5 loại đã biết, xác suất hữu hạn trong [0, 1]). Thiếu `type_status` thì coi là chưa chắc. Top-1 lỗi không bao giờ được thay bằng top-2.
- `highlights`: tối đa 3 loại có điểm `reliable`, xếp theo độ tin cậy cao nhất trong nhóm, rồi số điểm, rồi mã loại. `max_probability` là của điểm rõ nhất, không phải độ tin cậy chung của cả loại.
- Website không tự đặt ngưỡng 80%/90% và không hạ ngưỡng của dịch vụ AI. `highlights` trong API vẫn chỉ gồm nhóm đủ tin cậy. Giao diện dùng tối đa 8 điểm có điểm số cao nhất (`TOP_POINTS` trong `skin-analysis-view.js`), không yêu cầu điểm thuộc `highlights` và không đổi cờ `reliable` hay phần trăm thực tế.
- `detection_confidence` của detector không được hiển thị hay trộn vào xếp hạng độ tin cậy phân loại.

Trang kết quả: bên phải ảnh là tối đa 8 điểm sắp theo độ tin cậy giảm dần, kèm loại và phần trăm. Có ít hơn 8 điểm thì hiện đúng số điểm thực tế; điểm chưa có phần trăm ghi "Chưa có", không tạo thêm điểm hoặc điểm số. Chọn một thẻ để đối chiếu vị trí trên ảnh; khung nét đứt nghĩa là độ tin cậy thấp hoặc chưa xác định loại. "Xem chi tiết toàn bộ N điểm" mở trang `/skin-analysis/<id>` với mọi dòng ngay từ đầu, sắp cao → thấp, điểm chưa có độ tin cậy ở cuối. Trang chi tiết tải lại trực tiếp được, có nút quay về đúng kết quả nổi bật, checkbox hiện mọi vị trí và chọn từng dòng trên ảnh. Thông báo chụp lại ảnh, lỗi truy cập và câu tham khảo chuyên môn vẫn được giữ.

Theo yêu cầu ngày 24/10/2026, bỏ banner "Chế độ thử nghiệm", phần giải thích model huấn luyện trên ảnh chuyên dụng và thông báo trống "Chưa đủ độ tin cậy để xác định loại…". Câu giới thiệu dịch vụ khi `demo` giữ nội dung: "Dựa trên loại mụn AI phân loại ở chế độ thử nghiệm, chỉ để tham khảo. Hãy đặt lịch để chuyên viên tư vấn chính xác." (bỏ tiền tố "Gợi ý thử nghiệm:").

## Gợi ý dịch vụ bằng Gemini (tắt mặc định)

```
SKIN_RECOMMENDATIONS_ENABLED=true
# Map dự phòng khi bảng skin_service_map rỗng (madv trong bảng dichvu).
SKIN_SERVICE_MAP={"papule": [3, 5], "pustule": [5], "closed_comedo": [7], "open_comedo": [7]}
# Dùng chung GEMINI_API_KEY / GEMINI_MODEL / GEMINI_TIMEOUT / GEMINI_FALLBACK_MODELS của trợ lý AI.
```

Luồng (`app/services/skin_recommendation_service.py`): kiểm tra chủ sở hữu → đọc kết quả đã lưu → bằng chứng = mọi điểm `reliable` theo loại (kết quả `demo`: mọi điểm có loại top-1) → ứng viên = dịch vụ `active` có trong map đã duyệt cho các loại đó → hỏi đồng ý → Gemini chọn tối đa 3 và viết lý do → server kiểm tra → thẻ dịch vụ.

### Đề xuất và duyệt map dịch vụ

Chạy `flask db upgrade` để áp dụng migration mới `20261024_0026_skin_service_map.py` (revision `20261024_0026`, sau `20261023_0025`). Migration này chỉ thêm bảng `skin_service_map`, gồm cặp loại/dịch vụ duy nhất, người duyệt và thời điểm duyệt UTC; xóa dịch vụ sẽ xóa các cặp liên quan, xóa nhân viên thì giữ cặp và bỏ người duyệt.

Admin hoặc manager mở `/admin/skin-service-map` từ menu **Chăm sóc → Dịch vụ theo loại mụn** ở giao diện React (trang cũ nằm trong Danh mục):

1. **Nhờ Gemini đề xuất**: tạo bản nháp cho đủ 5 loại, tối đa 5 dịch vụ mỗi loại, hiển thị lý do và đánh dấu thêm/bỏ so với map đang dùng. Không ghi DB.
2. Xem và tick/bỏ tick để sửa. **Lưu và duyệt** yêu cầu xác nhận số lượng từng loại, tối đa 10 dịch vụ active mỗi loại. Toàn bộ map được thay trong một transaction; lỗi ghi sẽ rollback và giữ map cũ.
3. Tải lại trang để xem nguồn, người và thời điểm duyệt. Có ít nhất một dòng trong DB thì **chỉ dùng map DB**, bỏ qua `.env` hoàn toàn. Bảng rỗng thì dùng `SKIN_SERVICE_MAP`; lưu rỗng là hợp lệ và **quay về `.env`**, không có nghĩa là tắt mọi gợi ý nếu `.env` vẫn có map.

Khi đề xuất cho quản lý, Gemini chỉ nhận 5 mã/tên loại mụn và **mọi dịch vụ active** với ID, tên, mô tả tối đa 400 ký tự và tên danh mục active (hoặc null). Không gửi giá, ảnh, dữ liệu khách/nhân viên, token hay đường dẫn. JSON được lọc theo đúng các ID active đã gửi, gộp loại trùng, bỏ ID lạ/trùng và thay lý do không an toàn bằng câu trung tính. Kết quả cả 5 loại rỗng vẫn hợp lệ; không có dịch vụ active thì không gọi Gemini.

API admin/manager: `GET /api/admin/skin-service-map`, `POST /api/admin/skin-service-map/proposal`, `PUT /api/admin/skin-service-map` với body `{"map": {"papule": [3, 5]}}`. Đề xuất giới hạn một request đang chạy/nhân viên (409), 5 lần gọi/10 phút/nhân viên (429), trong bộ nhớ **từng worker**. Thiếu cấu hình Gemini trả 503, lỗi Gemini/JSON trả 502; không tự lưu đề xuất.

Luồng khách vẫn chỉ gửi những ứng viên đã được map và active; không gửi toàn bộ danh mục. Khi các ứng viên hoặc `allowed_type_codes` thay đổi, hash phiên bản hiện có khiến cache khách không dùng lại kết quả cũ; không thêm cơ chế cache mới.

Nếu dòng `SKIN_SERVICE_MAP` mẫu trong `.env` hiện có là JSON không hợp lệ, hãy xóa hoặc để trống (hoặc thay bằng JSON hợp lệ khi cần map dự phòng). Thay đổi này không tự sửa `.env`.

- Trạng thái trả về: `ok`, `consent_required`, `insufficient_evidence` (`location_only`, hoặc không có điểm đủ tin cậy / điểm có loại). Kết quả `demo` có thêm `demo: true`, Gemini nhận `mode: "demo"` và trang hiện câu tham khảo nêu trên; `no_matching_services` khi không có dịch vụ được duyệt hoặc Gemini không chọn dịch vụ nào. Lỗi Gemini: 502/503 với thông báo riêng và nút "Thử lại"; kết quả soi da không bị ảnh hưởng, không thay bằng danh sách bán chạy.

### Kiểm tra giao diện kết quả ngày 24/10/2026

- `node --test tests/skin-analysis-view.test.cjs`: **5 passed** (xếp hạng, không đổi cờ/điểm số, ít điểm, thiếu điểm số, đầy đủ danh sách, escape HTML).
- `python -m pytest tests/test_skin_analysis.py -q --disable-warnings --tb=short`: **32 passed**, gồm quyền chủ tài khoản và trang chi tiết không nhúng dữ liệu riêng tư.
- `tests/skin-results.playwright.js` trên SQLite/ảnh tổng hợp riêng: 3 nhóm luồng đạt; upload thật qua form, kết quả demo, đủ 128 dòng chi tiết, tải lại/quay về, mobile 390/360px không tràn ngang, ít/không điểm, thiếu điểm số, chụp lại và lỗi không tìm thấy. Không page error/request failure; HTTP 404 là tình huống cố ý giả lập.
- Bằng chứng: `output/skin-results-2026-10-24/`. Không thay schema, cấu hình AI hay dữ liệu khách thật.

### Giữ gợi ý dịch vụ khi quay lại từ trang chi tiết

Lỗi cũ: chuyển sang trang chi tiết rồi mở lại trang kết quả làm biến `recConsent` khởi tạo lại thành `false`; phần dịch vụ đã có bị thay bằng bước đồng ý. Nút Back cũng có thể mở lại URL chưa chứa ID phân tích hoặc ảnh blob đã bị thu hồi.

- `app/static/js/customers/skin-analysis.js`: nhớ bản hiển thị gợi ý gần nhất trong `sessionStorage` tối đa 30 phút, gắn đúng chủ tài khoản, ID phân tích và phiên bản thông báo đồng ý. Không lưu ảnh/token; chỉ khôi phục sau khi API xác minh quyền xem kết quả. Bản nhớ chỉ khôi phục các thẻ dịch vụ, không khôi phục sự đồng ý gửi thêm dữ liệu. Xóa bản nhớ khi xóa phân tích.
- URL kết quả giữ `?analysis=<id>`; Back/Forward mở lại đúng phân tích. Khi trình duyệt phục hồi một document từ cache, kiểm tra quyền xem lại trước khi hiển thị kết quả và giữ ảnh blob dùng được.
- `app/templates/customer/skin_analysis.html`: tăng version script lên `3.1` để tránh cache mã cũ.
- `tests/skin-results.playwright.js`: thêm kiểm tra nút quay lại, Back/Forward, tải lại và phục hồi document đều giữ nguyên gợi ý, **không thêm request gợi ý**. Kiểm tra bản nhớ khác tài khoản/phân tích, hết hạn, sai phiên bản, và API từ chối truy cập không được khôi phục. Tổng **5 nhóm luồng trình duyệt đạt**, không page error/request failure; console chỉ có 404 cố ý giả lập. Kiểm tra JS syntax/diff đạt; 5 test hàm hiển thị vẫn đạt.
- Bằng chứng bổ sung: `output/skin-results-2026-10-24/browser-return.log`, `recommendations-after-return.png`. Kiểm tra bằng dữ liệu SQLite/ảnh tổng hợp riêng.
- Gửi sang Gemini: mã/tên loại, số điểm đủ tin cậy, độ tin cậy cao nhất mỗi loại, và tên/mô tả/danh mục/loại được phép của dịch vụ ứng viên. **Không gửi** ảnh, bbox, tên, SĐT, email, token, đường dẫn ảnh, giá.
- Kiểm tra output: JSON đúng dạng; chỉ ID trong danh sách ứng viên, bỏ trùng; `matched_type_codes` phải thuộc loại được duyệt của dịch vụ đó và có bằng chứng; lý do/tóm tắt có câu chẩn đoán, thuốc, hứa chữa khỏi, giá/ưu đãi, link hoặc ký tự HTML thì thay bằng câu trung tính. Giá, thời lượng, link (`/services/<madv>`, `/appointments/create?service=<madv>`) luôn lấy từ database.
- Đồng ý: khách bấm "Đồng ý và xem gợi ý" trên trang; request gửi `consent` = `CONSENT_VERSION` của `skin_recommendation_service.py`. Từ chối vẫn xem kết quả soi da. Lựa chọn chỉ nhớ trong lần mở trang đó và **không lưu vào database** (lưu bền cần thêm cột/bảng, phải duyệt riêng). Đổi nội dung thông báo thì tăng phiên bản này.
- Chống trùng/chi phí: một request đang chạy cho mỗi lần phân tích (409), tối đa 10 lần gọi Gemini / 10 phút / khách (429), cache 30 phút theo lần phân tích + phiên bản danh mục ứng viên + phiên bản prompt; xóa lần phân tích thì xóa cache. Các giới hạn này nằm trong bộ nhớ **từng tiến trình**: chạy nhiều worker thì mỗi worker có giới hạn và cache riêng.
- Trước khi bật cho khách thật: spa cần duyệt map dịch vụ (DB, hoặc `SKIN_SERVICE_MAP` dự phòng) và nội dung thông báo gửi dữ liệu tới Google Gemini.

## Chế độ thử nghiệm (chưa có ảnh khách hàng để huấn luyện lại)

Chạy dịch vụ AI với `--demo` thay cho lệnh ở bước 1:
```powershell
cd E:\Project\BinSpa_AI
.\venv\Scripts\python.exe api\server.py --port 8008 --demo
```
Website không cần cấu hình thêm. Trên ảnh khác nguồn huấn luyện, loại mụn chỉ đúng khoảng 21–28%, nên chế độ này chỉ dùng để demo, không dùng để tư vấn khách thật.

## Dữ liệu và quyền riêng tư

- **Không phân tích, không lưu** nếu khách chưa tick đồng ý. Phiên bản điều khoản đồng ý (`CONSENT_VERSION` trong `app/services/skin_analysis_service.py`) được lưu cùng mỗi lần phân tích. Khi đổi nội dung điều khoản thì tăng phiên bản này.
- Ảnh lưu ở `uploads/skin/<makh>/` (đã nằm trong `.gitignore`), không có đường dẫn công khai, chỉ chủ tài khoản tải được qua API.
- Ảnh được xoay đúng chiều theo EXIF, rồi mã hóa lại thành JPEG. Chính file JPEG này vừa được gửi sang AI vừa được lưu, nên tọa độ các khung khớp với ảnh đã lưu.
- Dịch vụ AI không lưu ảnh.

## Giới hạn hiện tại của model

Model học trên ảnh chụp da liễu chuẩn hóa (VISIA). **Với selfie điện thoại, phần lớn kết quả chỉ ở mức `location_only`**, tức là có vị trí mụn nhưng chưa có loại mụn. Đây là giới hạn đã đo được của model, không phải lỗi website. Chi tiết: `E:\Project\BinSpa_AI\reports\input_gate_summary.md` và `reports/phase2_calibration_summary.md`. Kết quả chỉ mang tính tham khảo chăm sóc da, không phải chẩn đoán.

## Kiểm thử

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_skin_service_map.py tests/test_skin_analysis.py tests/test_recommendations.py -q
node --test tests/skin-analysis-view.test.cjs
```

Các test giả lập dịch vụ AI và Gemini, nên không cần GPU hay khóa API.

Kiểm tra trang duyệt map với SQLite tạm và Gemini giả (chỉ bind loopback):

```powershell
.\venv\Scripts\python.exe tests\skin_service_map_preview.py --port 5079
# Ở terminal khác:
playwright-cli -s=skin-map open http://127.0.0.1:5079/__preview/login
playwright-cli -s=skin-map run-code --filename tests/skin-service-map.playwright.js
playwright-cli -s=skin-map eval 'localStorage.skin_map_qa'
```

Kịch bản kiểm tra đề xuất không tự lưu, sửa checkbox, xác nhận số lượng, duyệt rồi reload, lưu rỗng quay về `.env`, escape dữ liệu HTML, giao diện desktop/mobile và lỗi console/request. Ảnh chụp lưu trong `.playwright-cli/skin-map-desktop.png` và `skin-map-mobile.png`. Route đăng nhập preview không được đăng ký trong ứng dụng thật.

Xem giao diện với dữ liệu giả (SQLite tạm, AI và Gemini giả, ảnh tổng hợp):
```powershell
.\venv\Scripts\python.exe tests\skin_analysis_preview.py --port 5078
# Mở http://127.0.0.1:5078/__preview/session?customer=1
# Đổi kịch bản: /__preview/mode?ai=ok|many|location_only|demo|empty|retake&gemini=ok|fail|none
```

# Kế hoạch Skin Analysis: giao diện khách hàng và Gemini gợi ý dịch vụ

Ngày: 23/10/2026. Trạng thái: **đã triển khai SK-01 → SK-13 (23/10/2026), kiểm bằng test và preview dữ liệu giả**. Gợi ý Gemini tắt mặc định (`SKIN_RECOMMENDATIONS_ENABLED`), chờ spa duyệt `SKIN_SERVICE_MAP` và nội dung thông báo gửi dữ liệu. Chi tiết vận hành: `docs/SKIN_ANALYSIS_AI.md`.

## 1. Mục tiêu và phạm vi

Khách chụp/tải ảnh → nhận kết quả gọn, dễ hiểu → xem vài loại mụn có độ tin cậy cao nhất → bấm “Xem chi tiết” để xem toàn bộ điểm theo độ tin cậy giảm dần → xem dịch vụ phù hợp do Gemini gợi ý dựa trên chính kết quả đó → xem dịch vụ hoặc đặt lịch.

Tái sử dụng giao diện khách hàng, token màu và API hiện có. Giữ trang `/skin-analysis`, không tạo một ứng dụng React riêng chỉ cho trang này. Không sửa mô hình AI, hạ ngưỡng phân loại hoặc đổi schema để làm giao diện trông có nhiều kết quả hơn.

## 2. Hiện trạng đã kiểm tra trong source

| Thành phần | Hiện có | Khoảng thiếu |
|---|---|---|
| `app/templates/customer/skin_analysis.html` | Tải ảnh, consent, kết quả, ảnh đánh dấu, bảng từng nốt, lịch sử | Mọi thông tin dồn ra ngay; thiếu tóm tắt ưu tiên và khu vực dịch vụ |
| `app/static/js/customers/skin-analysis.js` | `drawBoxes`, `renderSummary`, `renderTable`, mở/xóa lịch sử | Vẽ toàn bộ điểm; bảng chưa sắp theo độ tin cậy; chưa thu gọn |
| `app/static/css/customers/skin-analysis.css` | CSS riêng cho trang | Cần bố cục tối giản, mobile và trạng thái tương tác |
| `app/services/skin_analysis_service.py` | Chuẩn hóa ảnh, gọi AI, lưu kết quả, serialize quyền riêng tư | Cần contract cho thứ hạng/ID điểm và dữ liệu đưa sang Gemini |
| `app/routes/skin_bp.py` | Trang, tạo, lịch sử, chi tiết, ảnh riêng tư, xóa | Chưa có endpoint gợi ý dịch vụ cho một analysis |
| `app/skin_models.py` | Lưu JSON kết quả gốc, ảnh, chủ sở hữu, consent | Tận dụng dữ liệu hiện có; chưa cần migration |
| `app/services/ai_service.py`, `recommendation_service.py` | Hạ tầng AI và gợi ý/danh mục hiện có | Cần kiểm tra điểm tái sử dụng để tránh thêm Gemini client/prompt trùng lặp |
| `tests/test_skin_analysis.py`, `docs/SKIN_ANALYSIS_AI.md` | Test API và tài liệu | Bổ sung ca UI, sắp xếp, gợi ý, quyền và lỗi provider |

Theo `docs/SKIN_ANALYSIS_AI.md`, selfie có thể chỉ đạt `location_only`; chế độ `demo` không dùng để tư vấn khách thật. `lesions()` hiện trả `type/probability = null` cho nhiều điểm chưa đủ điều kiện công bố loại. Không coi null là xác suất 0 hoặc tự lấy loại bị ẩn để đưa lên UI.

## 3. Thiết kế trải nghiệm đề xuất

### Bố cục

```text
Soi da bằng AI
Một câu hướng dẫn ngắn

[ Chọn/chụp ảnh ] → [ Xem trước ảnh ] → [ Phân tích ]

Kết quả nổi bật                         [ Phân tích ảnh khác ]
[ Ảnh: các điểm nổi bật ] [ Tối đa 3 loại đủ tin cậy ]
                         [ Tên loại · số điểm đủ tin cậy ]
                         [ Độ tin cậy cao nhất trong nhóm ]
Đang hiển thị X / N điểm. Các điểm khác được thu gọn.
[ Xem chi tiết N điểm ↓ ]

Dịch vụ gợi ý cho bạn
Lý do gợi ý ngắn, dựa trên kết quả lần phân tích này
[ Dịch vụ 1 · giá · thời lượng · lý do · Xem dịch vụ ]
[ Dịch vụ 2 ... ]       [ Dịch vụ 3 ... ]

Lịch sử phân tích [ Xem lịch sử ↓ ]
```

Desktop: ảnh và tóm tắt hai cột; dịch vụ bên dưới. Mobile: một cột, tóm tắt ngắn rồi ảnh, nút chi tiết rộng dễ bấm. Lịch sử thu gọn mặc định để ưu tiên lần hiện tại. Dùng nền sáng, chữ đậm vừa, xanh thương hiệu, ít đường viền/bóng; màu trạng thái phải có nhãn chữ đi kèm. Dùng token/font hiện có, không thêm thư viện UI.

### Nội dung khách nhìn thấy

- Tiêu đề: “Kết quả nổi bật”. Dòng giải thích: “Ưu tiên các điểm AI có độ tin cậy cao. Bạn có thể mở chi tiết để xem tất cả.”
- Nút đóng/mở: “Xem chi tiết N điểm” / “Thu gọn chi tiết”.
- Phần mở rộng: “Sắp xếp theo độ tin cậy cao → thấp”; điểm chưa có mức đánh giá nằm cuối.
- Gợi ý: “Dịch vụ gợi ý cho bạn”; lý do 1–2 câu, không trình bày prompt, JSON hoặc tên model trong luồng chính.
- Một lưu ý ngắn: “Kết quả AI mang tính tham khảo, không thay thế đánh giá chuyên môn.”
- Xác suất phải được gọi là “Độ tin cậy của AI”, không phải mức độ nặng, tỷ lệ diện tích da hoặc khả năng chữa khỏi.

## 4. Quy tắc kết quả nổi bật và chi tiết

Các con số dưới đây là mặc định thiết kế có thể cấu hình, không phải ngưỡng y khoa:

| Quy tắc | Cách thực hiện |
|---|---|
| Điểm đủ tin cậy | Chỉ điểm thuộc kết quả `ok`, có loại hợp lệ, xác suất hữu hạn trong [0,1], được model đánh dấu confident. Không chỉ dựa vào top-1 tương đối |
| Ngưỡng | Tôn trọng ngưỡng đã hiệu chỉnh của dịch vụ AI. Không tự đặt 80%/90% cho mọi loại hoặc hạ ngưỡng để đủ 3 thẻ |
| Loại nổi bật | Nhóm các điểm đủ điều kiện theo loại; xếp loại bằng xác suất cao nhất trong nhóm; tối đa 3 loại. Nếu bằng nhau: số điểm đủ điều kiện giảm dần, sau đó mã loại ổn định |
| Nhãn trên thẻ loại | Tên + “X điểm đủ tin cậy” + “Độ tin cậy cao nhất: Y%”. Không gọi max là độ tin cậy chung của cả loại |
| Ảnh mặc định | Chỉ đánh dấu tối đa 5 điểm cao nhất thuộc các loại nổi bật; hiển thị rõ X/N. Bấm thẻ loại có thể lọc ảnh theo loại đó, có nút bỏ lọc |
| Chi tiết | Giữ toàn bộ điểm model trả về; sort xác suất công bố hợp lệ giảm dần, không có xác suất đặt cuối; tie dùng ID/thứ tự gốc |
| ID điểm | Gán ID ổn định theo prediction gốc trong một analysis, không đánh số lại theo vị trí sort. Số trên ảnh phải khớp danh sách sau lọc/sắp xếp |
| Hiển thị yếu/không xác định | Đủ điều kiện công bố loại nhưng thấp: nhãn “Độ tin cậy thấp”. Loại đã bị backend ẩn: giữ “Chưa xác định loại”, điểm tin cậy “Chưa có”, không đoán |
| Nhiều điểm | Danh sách mobile dạng thẻ gọn; desktop dạng bảng. Phân trang 20 điểm hoặc “Xem thêm”, tổng đúng và không âm thầm bỏ điểm |
| Ảnh khi mở chi tiết | Cho bật “Hiện tất cả điểm”; chọn một hàng sẽ làm nổi bật điểm tương ứng. Ẩn chi tiết trở về chế độ nổi bật, không mất dữ liệu |
| Không có kết quả đủ tin cậy | Thông báo “Chưa đủ độ tin cậy để xác định loại”; vẫn xem được vị trí được phép hiển thị. Không ép có top 3 |
| Không phát hiện điểm | “Chưa phát hiện điểm trong ảnh này”; không kết luận khách không có mụn hoặc da hoàn toàn khỏe |

Nếu cần hiển thị điểm tin cậy phát hiện vị trí khi xác suất phân loại bị ẩn, phải xác minh AI thật sự trả trường đó. Tách rõ detection confidence và classification confidence; không trộn hai đại lượng trong cùng bảng xếp hạng. Nếu backend không công bố được xác suất phân loại thì xếp nhóm ấy cuối, không sửa dữ liệu để giả vờ sắp được toàn bộ bằng số.

## 5. Luồng Gemini đề xuất

### Luồng dữ liệu

`analysis_id → kiểm tra đăng nhập/chủ sở hữu → đọc kết quả lưu tại server → chọn bằng chứng đủ tin cậy → chọn danh mục dịch vụ đang hoạt động, đủ điều kiện → Gemini chọn/xếp hạng và giải thích → server kiểm tra output → render thẻ dịch vụ → trang chi tiết/đặt lịch`.

Gemini dùng dữ liệu của lần phân tích vừa chọn, không dựa vào lịch sử cũ thay thế hoặc tự phân tích lại khuôn mặt. Gợi ý dùng toàn bộ điểm **đủ tin cậy**, không chỉ 5 điểm đang vẽ; không dùng điểm yếu bị ẩn để tạo lời khẳng định.

| Thành phần | Đặc tả đề xuất |
|---|---|
| Endpoint mới | `POST /api/me/skin-analyses/<analysis_id>/recommendations`; route khách đã đăng nhập, kiểm quyền tương tự detail |
| Request | Không nhận loại mụn, số điểm, giá hay tên dịch vụ do browser gửi làm nguồn tin cậy; server đọc analysis/candidate catalog |
| Dữ liệu sang Gemini | Mã loại được cho phép, số điểm đủ tin cậy, thống kê confidence có nghĩa rõ ràng, trạng thái analysis; danh sách ID dịch vụ + mô tả thật + thông tin phù hợp đã được duyệt |
| Không gửi mặc định | Ảnh mặt, bbox, tên khách, SĐT, email, token, đường dẫn ảnh. Chỉ gửi thông tin dẫn xuất tối thiểu cần cho gợi ý |
| Consent | Consent hiện tại chỉ nói lưu ảnh/kết quả. Cần cập nhật thông báo/đồng ý phù hợp việc gửi kết quả dẫn xuất tới Gemini; khách từ chối vẫn xem kết quả quét bình thường. Nếu đổi điều khoản đang dùng, tăng version theo cơ chế hiện có |
| Dịch vụ hợp lệ | Chỉ lấy dịch vụ active/công khai/được phép đặt. Không suy ra phù hợp chỉ vì tên chứa “mụn”; nếu thiếu metadata, dùng bảng ánh xạ cấu hình do spa duyệt, không tự bịa chỉ định |
| Candidate filter | Lọc phù hợp bằng dữ liệu đã duyệt trước; Gemini chủ yếu chọn tối đa 3 dịch vụ và viết lý do. Không giao toàn bộ quyết định tính phù hợp cho model |
| Output có cấu trúc | `recommendations: [{service_id, matched_type_codes, reason}], summary`; danh sách ID/type phải nằm trong input cho phép |
| Kiểm tra output | JSON/schema, độ dài, ID lạ, ID trùng, loại không có bằng chứng, dịch vụ đã ngừng, nội dung không phù hợp. Reject/lọc an toàn; không hiển thị HTML model sinh ra |
| Giá/thời lượng/link | Lấy lại từ database qua serializer hiện có. Không lấy giá, ưu đãi hoặc URL do Gemini sáng tác |
| Ngôn ngữ | “Có thể tham khảo…”, lý do gắn với kết quả. Không chẩn đoán, kê thuốc, cam kết trị khỏi hoặc tự nêu mức độ bệnh |
| Không đủ dữ liệu | Trả trạng thái `insufficient_evidence` hoặc `no_matching_services`; có CTA tư vấn, không cố bán dịch vụ không phù hợp |
| Provider lỗi/tắt | Kết quả quét vẫn hiển thị; block gợi ý có lỗi riêng và “Thử lại”. Không âm thầm thay bằng danh sách bán chạy rồi nói là gợi ý theo da |
| Lịch sử | Khi đổi analysis, hủy/ignore request cũ; response phải có `analysis_id` để không trộn gợi ý giữa ảnh A/B |
| Chi phí/trùng request | Một request đang chạy cho mỗi khách/analysis; timeout hữu hạn; rate limit; cache có thời hạn theo analysis + phiên bản candidate catalog/prompt. Không giữ request mở vô hạn |
| Lưu gợi ý | MVP có thể cache ngắn hạn hoặc tính lại theo yêu cầu, không cần bảng mới. Chỉ đề xuất migration nếu thật sự cần lưu lịch sử gợi ý bền vững |

`demo`, `location_only`, `retake_photo` không được dùng như phân loại chắc chắn để gợi ý dịch vụ điều trị. Demo phải có nhãn thử nghiệm rõ ràng, không dùng banner thành công như kết quả sản phẩm thật. Với location-only có thể mời tư vấn, không tự đặt tên loại mụn qua Gemini.

## 6. Bảng triển khai chi tiết

| ID | Ưu tiên | Công việc / file dự kiến | Phụ thuộc | Tiêu chí hoàn thành |
|---|---|---|---|---|
| SK-01 | P0 | Xác minh contract AI thật, ngưỡng/type_status, dữ liệu cũ; `skin_analysis_service.py`, `test_skin_analysis.py`, docs AI | Không | Có fixture ok/mixed/location_only/demo/retake/empty; biết rõ ý nghĩa các xác suất |
| SK-02 | P0 | Chuẩn hóa DTO điểm: ID ổn định, confidence hợp lệ, tổng số phát hiện/đủ tin cậy; giữ tương thích lịch sử | SK-01 | Không đưa loại bị ẩn thành chắc chắn; null/NaN/ngoài miền được xử lý; total nhất quán |
| SK-03 | P0 | Bố cục tối giản, trạng thái upload/loading/kết quả; template + CSS hiện có | SK-01 | Mobile một cột; CTA rõ; không tràn; ảnh không méo; lỗi không xóa ảnh đã chọn |
| SK-04 | P0 | Top 3 loại, top 5 điểm, sort và nhãn X/N; JS hiện có hoặc helper thuần tách nhỏ | SK-02,03 | Số lượng ít hơn giới hạn vẫn đúng; không ép loại yếu lên top; ảnh và thẻ đồng bộ |
| SK-05 | P0 | Accordion chi tiết, sort cao→thấp, nhóm chưa xác định cuối, phân trang và highlight điểm | SK-04 | Xem được mọi điểm, ID ổn định; keyboard/aria-expanded/aria-controls; đóng mở không mất vị trí |
| SK-06 | P0 | Kiểm hạ tầng Gemini/catalog hiện có, thống nhất ánh xạ dịch vụ đủ điều kiện với spa | SK-01 | Có candidate list thực, không bịa dịch vụ hay tính phù hợp; thiếu ánh xạ có fallback rõ |
| SK-07 | P0 | Endpoint gợi ý, serializer/schema, timeout, rate limit và bảo vệ quyền; tái sử dụng Gemini client nếu phù hợp | SK-02,06 | Chỉ chủ analysis gọi được; không gửi ảnh/PII; output được kiểm ID/nội dung; không đổi giá |
| SK-08 | P0 | Thông báo/consent gửi kết quả dẫn xuất, cập nhật version nếu cần | SK-07 | Khách hiểu dữ liệu nào gửi; từ chối Gemini vẫn dùng quét; không gọi Gemini trước đồng ý cần thiết |
| SK-09 | P0 | Thẻ gợi ý tối đa 3, lý do, giá/thời lượng, xem dịch vụ/đặt lịch đúng dịch vụ | SK-07,08 | Gợi ý đúng analysis; không gắn dịch vụ không tồn tại; không tự tạo booking khi chỉ xem |
| SK-10 | P1 | Lối vào Skin Analysis từ menu khách, danh mục và hồ sơ; lịch sử chọn/xóa | SK-03 | Tôn trọng feature flag và đăng nhập; giữ đúng redirect; tránh nhồi thêm bottom-nav làm chật |
| SK-11 | P1 | Cache/chống request trùng, xử lý đổi ảnh/đổi lịch sử/xóa/logout; giải phóng blob URL | SK-07,09 | Response chậm A không ghi đè B; xóa ảnh đồng thời xóa dữ liệu cache liên quan |
| SK-12 | P1 | Test API/helper/browser, visual QA desktop/mobile và dữ liệu lớn | SK-04..11 | Ma trận mục 7 đạt; ảnh trước/sau; không provider thật hoặc ảnh khách thật |
| SK-13 | P1 | Cập nhật tài liệu, báo cáo nghiệm thu và danh sách giới hạn | SK-12 | Có file đổi/lệnh/log/ảnh; phân biệt mô phỏng với inference thật; không tuyên bố đã nâng độ chính xác model |

Thứ tự: SK-01/02 → SK-03/04/05 → SK-06/07/08 → SK-09/10/11 → SK-12/13. Không chờ nội dung mapping để bỏ dở UI độc lập; dùng fixture ghi rõ chỉ dành test trong thời gian đó.

## 7. Ma trận kiểm thử nghiệm thu

| Nhóm | Ca bắt buộc | Kỳ vọng |
|---|---|---|
| Top kết quả | 0/1/2/3/>3 loại; confidence bằng nhau; một loại nhiều điểm; một điểm xác suất cao nhưng model không confident | Top đúng quy tắc, không nâng confidence giả; tie ổn định |
| Dữ liệu bất thường | null, thiếu trường, NaN, xác suất âm/>1, bbox lỗi, label lạ, analysis cũ | UI không crash; dữ liệu bất hợp lệ bị loại/đánh dấu; không render HTML không tin cậy |
| Chi tiết | >100 điểm; sort; paginate; chọn hàng/điểm; đóng mở; resize | Không mất điểm, không đổi ID; overlay khớp ảnh EXIF đã xử lý |
| Trạng thái AI | ok, location_only, demo, retake_photo, không phát hiện, timeout | Copy phù hợp; không có gợi ý điều trị từ dữ liệu không đủ điều kiện |
| Gợi ý | Danh mục trống; không dịch vụ phù hợp; Gemini ID lạ/trùng/giá bịa/JSON lỗi/nội dung vượt phạm vi | Chỉ hiện dịch vụ hợp lệ từ DB, có fallback; không crash toàn kết quả |
| Race | Bấm phân tích/gợi ý hai lần, đổi A→B khi request A còn chờ, xóa trước response, logout | Không trộn ảnh/kết quả/gợi ý, không gửi request thừa, không lộ dữ liệu cũ |
| Quyền | Khách A truy cập analysis/ảnh/gợi ý của B; nội bộ không có quyền mặc định; chưa đăng nhập | API giữ chính sách riêng tư hiện có; không log ảnh/token |
| Consent | Không đồng ý lưu; không đồng ý Gemini; consent cũ; lịch sử đã có | Không suy diễn đồng ý gửi sang bên thứ ba; vẫn xem dữ liệu được phép |
| Chuyển đổi | Xem dịch vụ → đặt lịch → back về kết quả; dịch vụ bị ngừng sau khi gợi ý | ID đúng, giá mới từ server; không đặt dịch vụ đã ngừng |
| Giao diện | 360/390/768/1024/1440px, text dài, 200% zoom, keyboard, focus, screen reader labels | Không tràn toàn trang; nút không bị che; xem chi tiết dễ tìm; thông tin không chỉ dựa màu |

Các test backend dùng mock AI/Gemini; test browser dùng fixture SQLite riêng, không ghi trên app thật cổng 5000. Chạy `python -m pytest tests/test_skin_analysis.py -q` và bổ sung suite gợi ý; Node test cho helper sort/group; Playwright CLI cho hành trình. Chỉ build frontend nếu thay đổi module thuộc pipeline đó; template/JS legacy cần kiểm đúng asset được trang tải.

## 8. Dữ liệu cần chủ spa cung cấp và giới hạn

- Cần mapping dịch vụ nào có thể được gợi ý cho từng nhóm kết quả, cùng điều kiện không phù hợp nếu có. Gemini không được tự biến mô tả marketing thành chỉ định.
- Cần xác nhận nội dung thông báo xử lý dữ liệu dẫn xuất bởi Gemini trước khi bật cho khách thật.
- Không cần xin lại các lựa chọn UI thông thường: mặc định top 3 loại, tối đa 5 điểm trên ảnh, chi tiết thu gọn, 3 dịch vụ là thiết kế đề xuất để triển khai.
- Độ chính xác model và calibration là việc riêng; UI mới không giải quyết hạn chế selfie/location_only. Không tính demo thành nghiệm thu độ chính xác thực tế.
- Nếu cần thay schema/cấu hình production/deploy thì chuẩn bị thay đổi cụ thể để xin duyệt theo AGENTS.md. Kế hoạch này không cấp quyền thực hiện các bước đó.

## 9. Prompt giao triển khai

> Đọc AGENTS.md và plans/2026-10-23-skin-analysis-giao-dien-va-goi-y-dich-vu.md. Triển khai SK-01 đến SK-13 theo thứ tự phụ thuộc, bảo toàn các thay đổi có sẵn trong working tree. Ưu tiên giao diện khách tối giản, top loại/điểm đủ tin cậy, chi tiết đầy đủ sắp giảm dần và Gemini gợi ý từ kết quả đã lưu cùng danh mục thật. Không hạ ngưỡng model, không biến dữ liệu location_only/demo thành chẩn đoán, không tự sáng tác dịch vụ/giá/tính phù hợp. Dùng fixture/mock cho thao tác ghi và provider; không đổi schema, cấu hình production hoặc deploy khi chưa duyệt. Những dữ liệu mapping/consent thiếu thì ghi rõ, tiếp tục phần độc lập. Báo cáo trạng thái từng SK, file đổi, test, ảnh và giới hạn; không đánh dấu hoàn tất khi chưa kiểm luồng ảnh → kết quả → chi tiết → gợi ý → đặt lịch.

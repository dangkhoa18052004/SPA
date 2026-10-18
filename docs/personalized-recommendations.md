# Personalized Recommendation — sửa theo ngữ cảnh (2026-10-07)

Phần bổ sung đo lường impression/click, feature flag, lựa chọn cá nhân hóa của khách và CRM được ghi tại [Giai đoạn 5](RECOMMENDATION_CRM_PHASE5.md). Công thức ranking dưới đây được giữ nguyên.

## Kết quả

`/services` chỉ còn header, bộ lọc/tìm kiếm/sắp xếp và một grid dịch vụ.
Đã xóa toàn bộ section `#recommendations`, hai tiêu đề “Dịch vụ dành cho bạn” /
“Gói phù hợp với bạn”, CSS và script package không còn cần ở trang danh sách.
Không có danh sách đề xuất riêng, giới hạn top-N hoặc điểm số trên trang này.

Thứ tự mặc định của toàn bộ dịch vụ hoạt động được cá nhân hóa cho khách có lịch sử.
Khách chưa có tín hiệu và khách chưa đăng nhập dùng popularity. Mỗi dịch vụ xuất hiện
một lần; các dịch vụ có điểm thấp vẫn nằm trong danh sách.

Trang `/services/<id>` có đúng một section cuối trang “Có thể bạn cũng quan tâm”.
Một grid trộn tối đa 3 dịch vụ và 2 gói, có badge “Dịch vụ” / “Gói”.
Đã bỏ cách chọn dịch vụ liên quan ngẫu nhiên và renderer cũ của trang chi tiết.

## Các file sửa trong lần refactor

| File | Thay đổi |
| --- | --- |
| `app/services/recommendation_service.py` | Ranking toàn bộ candidate; popularity fallback/tiebreaker; ranking theo dịch vụ đang xem; lọc gói mua được; serializer giữ score ở backend. |
| `app/routes/service_bp.py` | GET catalog nhận JWT tùy chọn, lọc candidate trước khi rank, manual sort, metadata category, cache riêng; detail loại dịch vụ inactive. |
| `app/routes/recommendation_bp.py` | Thêm GET related theo service ID, giữ API tracking và API generic tương thích. |
| `app/static/js/customers/services.js` | CustomerAuth.fetch, giữ thứ tự backend, kết hợp filter/search/sort trong một luồng; giữ manual sort qua mọi thay đổi bộ lọc. |
| `app/static/js/customers/recommendations.js` | Chỉ render section related ở detail, một grid chung với badge, giữ tracking. |
| `app/static/js/customers/service-detail.js` | Xóa loadRelatedServices/displayRelatedServices ngẫu nhiên, giữ view_service tracking. |
| `app/static/js/customers/main.js` | Loader preview 6 dịch vụ chỉ chạy ở trang chủ, tránh ghi đè catalog. |
| `app/templates/customer/services.html` | Xóa hai section cũ, bỏ package assets, tăng version script. |
| `app/templates/customer/service_detail.html` | Một section mixed related, tải package renderer và CSS. |
| `app/templates/customer/layout.html` | Tăng version script chung để tránh dùng cache cũ. |
| `app/static/css/related-recommendations.css` | File mới: badge, grid responsive và chiều cao ảnh card chung. |
| `tests/test_recommendations.py` | Mở rộng kiểm thử catalog, filter/search/manual sort, context, inactive/unbuyable, template. |
| `tests/recommendations-ui.test.cjs` | Kiểm thử mixed grid/badge/escaping/exclude current/error và tracking. |
| `tests/services-catalog-ui.test.cjs` | File mới: mặc định đủ catalog, category/search, manual sort bền vững và tránh preview overwrite. |
| `tests/test_customer_static_assets.py` | Thêm trang detail vào kiểm tra tài nguyên CSS/JS được Flask phục vụ. |
| `docs/personalized-recommendations.md` | Báo cáo này. |

Schema, migration, business-event hooks và giao diện admin category từ lần triển khai
trước được tái sử dụng. Lần refactor này không cần migration mới.

## Ranking ở danh sách

`rank_services_for_customer(customer_id, candidate_services)` dùng engine `Ranking`
hiện có, trả tất cả candidate hoạt động, loại ID trùng và sắp xếp deterministic.
API chỉ lấy customer ID từ JWT; query string không thể chọn hồ sơ khách khác.

Giữ CustomerBehavior, lịch hẹn/hoàn thành, hóa đơn đã thanh toán, paid package snapshot,
treatment ledger, rating đã xác thực, category FK và time decay. Backend audit events
không cộng lại tín hiệu đã có trong bảng nghiệp vụ. Frontend event được dedupe 10 phút,
cap đóng góp 3 lần/action/target/ngày và giới hạn 60 event mới/phút.

```text
decay(age_days) = 2 ^ (-max(age_days, 0) / 30)
N(x) = x / (abs(x) + 5)
personal_score = .40 N(category_interest)
               + .30 N(booking_affinity)
               + .15 N(behavior_interest)
               + .15 N(rating_affinity)
order = personal_score DESC, popularity DESC, service_id ASC
```

Popularity chỉ phá hòa khi có tín hiệu cá nhân; không được cộng vào personal_score.
Không có tín hiệu thì popularity là thứ tự fallback, giữ công thức booking/completion
và rating Bayesian hiện có. Rating 1/2 sao làm giảm affinity; lịch sử cũ giảm theo decay.

API lọc active/category/search để tạo candidate trước khi gọi ranking. Manual sort giá/tên
bỏ qua ranking cá nhân. Giao diện tải catalog theo thứ tự backend bằng CustomerAuth.fetch,
lọc candidate tại client rồi áp dụng lựa chọn sort hiện tại. Score của mỗi dịch vụ độc lập
với tập candidate, nên lấy thứ tự backend trên tập đã lọc cho cùng kết quả như rank lại
riêng tập đó. Đổi category/search không reset manual sort; chọn default khôi phục thứ tự
cá nhân hóa. Thứ tự gốc được lưu riêng, không bị sort tại client làm mất.

Category đã gán dùng FK/slug, kể cả khi tên dịch vụ chứa từ khóa gây nhầm.
Filter “Chăm sóc da” gom facial/acne, “Điều trị cơ thể” dùng body-care.
Giao diện giữ keyword filter cũ cho dịch vụ chưa có category nhằm bảo toàn thao tác hiện có;
engine không suy ra category từ tên. Category-based affinity cần admin gán category.

## Ranking ở chi tiết

`get_related_recommendations(customer_id, current_service_id, service_limit=3, package_limit=2)`
tạo một Ranking và dùng dịch vụ hiện tại làm context chính:

1. Dịch vụ: loại chính nó và inactive; ưu tiên cùng category, rồi độ gần giá/thời lượng,
   tiếp theo personal_score, popularity và ID để kết quả ổn định.
2. Gói: chỉ lấy active, customer_sale_enabled, có item hợp lệ và tất cả dịch vụ active;
   gói chứa chính dịch vụ hiện tại đứng trước gói cùng category. Sau đó xét tỷ lệ buổi
   cùng nhóm, customer affinity/owned-package penalty, popularity và ID.
3. Trộn card trong một danh sách: gói chứa dịch vụ hiện tại đứng trước; dịch vụ/gói
   cùng category trước các fallback. Giới hạn riêng từng loại, không trùng ID trong loại.

Nếu category chưa được gán, dịch vụ dùng similarity giá/thời lượng; gói vẫn nhận diện
dịch vụ hiện tại trực tiếp qua item ID. Nếu VietQR không khả dụng và customer cash bị tắt,
không đề xuất gói. Dịch vụ context inactive/không tồn tại trả 404. Lỗi API ẩn section related.
Không có score số, category interest map hoặc dữ liệu khách khác trong response/HTML.

## API

| API | Hành vi |
| --- | --- |
| `GET /api/services` | Response cũ `success/services/total`; toàn bộ dịch vụ được rank mặc định. Thêm category_id/category_slug/category_name cho mỗi dịch vụ, không thêm score. |
| `GET /api/services?category=massage&search=da&sort=price-asc` | Category/search kết hợp; default là cá nhân hóa, price-asc/price-desc/name-asc/name-desc ghi đè. `%` và `_` trong search là ký tự literal. |
| `GET /api/services/<id>` | Giữ service response, thêm category metadata và trả 404 cho inactive. |
| `GET /api/recommendations/related/<id>` | API mới: `{success: true, items: [...]}`; mỗi item có type service/package và dữ liệu card tương ứng. |
| `GET /api/recommendations` | Giữ tương thích backend; giao diện `/services` không gọi/render API này nữa. |
| `POST /api/recommendations/events` | Giữ authenticated tracking, chỉ nhận action và madv/magoi. |

Catalog cá nhân hóa và related dùng `Cache-Control: private, no-store` / `Vary: Authorization, Cookie`.
JWT tùy chọn cho GET; tài khoản customer inactive trả 403; POST yêu cầu customer active.
Không có Gemini, thư viện ML mới hoặc gọi API bên ngoài khi scoring.

## Kiểm thử lần refactor

- Recommendation/backend: **51 passed**, 0 failed, 54.06 giây.
- Hồi quy customer static assets, phase4, booking/gifts/reviews và AI booking:
  **51 passed**, 0 failed, 21.18 giây. Detail được bổ sung vào kiểm tra static assets và chạy lại riêng.
- Toàn bộ 7 file JavaScript test: **40 passed**, 0 failed, gồm 12 test recommendation/catalog UI.
- `git diff --check`: passed.
- Smoke test ứng dụng đang chạy tại localhost:5000: catalog 200, đủ **36** dịch vụ;
  related 200 với 5 item mixed; HTML catalog không có hai tiêu đề cũ.
- Cả 7 tình huống bắt buộc đã có automated coverage: A/B khác nhóm; anonymous;
  filter chỉ matching category và rank nội bộ; search da chỉ matching; price ascending;
  related exclude current/cùng nhóm/matching package; inactive/không mua được bị loại.
- Chưa chạy kiểm tra hình ảnh trong trình duyệt thật cho lần refactor này. Node VM kiểm tra
  logic rendering/filtering; Flask tests và live smoke kiểm tra response, HTML và tài nguyên.
- Không chạy lại toàn bộ Python suite trong lần refactor. Kết quả trước refactor không
  được tính vào các số pass ở trên. Có các deprecation warning datetime/SQLAlchemy hiện có.

Lệnh chạy lại trong sandbox, không cần subprocess runner của Node:

```powershell
venv\Scripts\python.exe -B -m pytest tests/test_recommendations.py -q -p no:cacheprovider
venv\Scripts\python.exe -B -m pytest tests/test_customer_static_assets.py tests/test_phase4_regression_fix.py tests/test_booking_gifts_reviews.py tests/test_ai_booking_agent.py -q -p no:cacheprovider --disable-warnings
Get-ChildItem tests/*.test.cjs | ForEach-Object { node $_.FullName }
git diff --check
```

## Kiểm tra thủ công

1. Trong admin, gán ít nhất hai dịch vụ Massage và hai dịch vụ acne/facial đúng category;
   có một gói chứa dịch vụ định xem và một gói chứa dịch vụ cùng nhóm.
2. Khách A có lịch sử Massage, khách B có lịch sử da mụn: mở `/services` bằng hai tài khoản,
   so sánh thứ tự mặc định. Cả hai vẫn thấy đủ catalog, không có hai section đề xuất riêng.
   Mở cửa sổ chưa đăng nhập: danh sách hoạt động với fallback popularity.
3. Chọn Massage: chỉ thấy dịch vụ matching, vẫn theo thứ tự mặc định trong nhóm.
   Tìm `da`: chỉ thấy tên/mô tả matching; kết hợp với category để kiểm tra giao của hai bộ lọc.
4. Chọn Giá thấp đến cao hoặc Tên A-Z, đổi category rồi sửa/xóa search: sort đã chọn
   tiếp tục được áp dụng. Chuyển lại mặc định: phục hồi thứ tự cá nhân hóa.
5. Mở chi tiết Massage bằng khách vốn quan tâm da mụn: cuối trang có một section chung,
   không có chính dịch vụ đang xem; dịch vụ cùng nhóm và gói chứa nó được ưu tiên,
   card có badge Dịch vụ/Gói và link đặt lịch/xem gói đúng. Kiểm tra trên desktop/mobile.
6. Tắt dịch vụ hoặc gói/customer-sale: chúng biến mất; gói có dịch vụ inactive cũng bị loại.
   Trong Network kiểm tra JSON không chứa score; anonymous không ghi behavior thành công.

## Database hiện tại

Migration gốc `20261007_0017` tạo category, CustomerBehavior và history indexes,
không backfill category từ tên. Local PostgreSQL đã được nâng lên 0017 ở lần sửa lỗi
trước; 36 dịch vụ được bảo toàn. Lần refactor này không thay đổi dữ liệu ứng dụng đang chạy.
Nếu triển khai ở database khác, chạy Flask-Migrate upgrade và gán category qua admin.

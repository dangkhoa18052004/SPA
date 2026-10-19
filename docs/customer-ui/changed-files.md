# File thay đổi

Danh sách theo checkpoint của đợt customer UI; phần nền tảng đã commit, các bổ sung gần nhất còn ở working tree. Build output, ảnh QA và log nằm trong các thư mục ignored. Không sửa thay đổi sẵn có của người dùng trong `requirements-dev.txt`.

## Bổ sung sau checkpoint nền tảng

- E06: [treatments-refactor.md](treatments-refactor.md).
- Hủy mua gói chờ: [purchase-cancellation.md](purchase-cancellation.md).
- E07: [rewards-refactor.md](rewards-refactor.md).
- E08: [reviews-refactor.md](reviews-refactor.md).
- E09/F: [e09-final-hardening.md](e09-final-hardening.md). File mới: `tests/customer-ui-preferences-final.playwright.js`, `tests/customer-ui-final-hardening.playwright.js`; sửa `communication-preferences.js`, `communication-preferences.css`, `profile.html`, `customers/main.js` và tài liệu. Không thêm dependency hoặc xóa asset dùng chung.

## Danh sách nền tảng

- [app/config.py](../../app/config.py)
- [app/routes/customer_bp.py](../../app/routes/customer_bp.py)
- [app/static/js/customers/auth-session.js](../../app/static/js/customers/auth-session.js)
- [app/static/js/customers/auth.js](../../app/static/js/customers/auth.js)
- [app/static/js/customers/communication-preferences.js](../../app/static/js/customers/communication-preferences.js)
- [app/static/js/customers/main.js](../../app/static/js/customers/main.js)
- [app/static/js/customers/profile.js](../../app/static/js/customers/profile.js)
- [app/static/js/customers/recommendations.js](../../app/static/js/customers/recommendations.js)
- [app/static/js/customers/service-detail.js](../../app/static/js/customers/service-detail.js)
- [app/static/js/customers/services.js](../../app/static/js/customers/services.js)
- [app/static/js/loyalty-payment.js](../../app/static/js/loyalty-payment.js)
- [app/static/js/reviews.js](../../app/static/js/reviews.js)
- [app/templates/customer/_auth_assets.html](../../app/templates/customer/_auth_assets.html)
- [app/templates/customer/booking_react.html](../../app/templates/customer/booking_react.html)
- [app/templates/customer/forgot_password.html](../../app/templates/customer/forgot_password.html)
- [app/templates/customer/index.html](../../app/templates/customer/index.html)
- [app/templates/customer/layout.html](../../app/templates/customer/layout.html)
- [app/templates/customer/login.html](../../app/templates/customer/login.html)
- [app/templates/customer/profile.html](../../app/templates/customer/profile.html)
- [app/templates/customer/register.html](../../app/templates/customer/register.html)
- [app/templates/customer/reset_password.html](../../app/templates/customer/reset_password.html)
- [app/templates/customer/service_detail.html](../../app/templates/customer/service_detail.html)
- [app/templates/customer/services.html](../../app/templates/customer/services.html)
- [app/templates/customer/verify_otp.html](../../app/templates/customer/verify_otp.html)
- [app/ui_assets.py](../../app/ui_assets.py)
- [docs/customer-ui/baseline.md](../../docs/customer-ui/baseline.md)
- [docs/customer-ui/changed-files.md](../../docs/customer-ui/changed-files.md)
- [docs/customer-ui/contracts.md](../../docs/customer-ui/contracts.md)
- [docs/customer-ui/design-spec.md](../../docs/customer-ui/design-spec.md)
- [docs/customer-ui/progress.md](../../docs/customer-ui/progress.md)
- [docs/customer-ui/qa-results.md](../../docs/customer-ui/qa-results.md)
- [docs/customer-ui/release-checklist.md](../../docs/customer-ui/release-checklist.md)
- [frontend/src/customer-account-main.tsx](../../frontend/src/customer-account-main.tsx)
- [frontend/src/customer-main.ts](../../frontend/src/customer-main.ts)
- [frontend/src/customer/Booking.tsx](../../frontend/src/customer/Booking.tsx)
- [frontend/src/customer/account-panels.tsx](../../frontend/src/customer/account-panels.tsx)
- [frontend/src/customer/account.css](../../frontend/src/customer/account.css)
- [frontend/src/customer/api.test.ts](../../frontend/src/customer/api.test.ts)
- [frontend/src/customer/api.ts](../../frontend/src/customer/api.ts)
- [frontend/src/customer/booking.css](../../frontend/src/customer/booking.css)
- [frontend/src/customer/catalog.test.ts](../../frontend/src/customer/catalog.test.ts)
- [frontend/src/customer/catalog.ts](../../frontend/src/customer/catalog.ts)
- [frontend/src/customer/public.css](../../frontend/src/customer/public.css)
- [frontend/src/customer/theme.ts](../../frontend/src/customer/theme.ts)
- [frontend/src/customer/tokens.css](../../frontend/src/customer/tokens.css)
- [frontend/src/customer/ui.tsx](../../frontend/src/customer/ui.tsx)
- [frontend/vite.config.ts](../../frontend/vite.config.ts)
- [tests/conftest.py](../../tests/conftest.py)
- [tests/customer-auth-session.test.cjs](../../tests/customer-auth-session.test.cjs)
- [tests/customer-ui-account.playwright.js](../../tests/customer-ui-account.playwright.js)
- [tests/customer-ui-auth-preferences.playwright.js](../../tests/customer-ui-auth-preferences.playwright.js)
- [tests/customer-ui-avatar.playwright.js](../../tests/customer-ui-avatar.playwright.js)
- [tests/customer-ui-baseline.playwright.js](../../tests/customer-ui-baseline.playwright.js)
- [tests/customer-ui-foundation.playwright.js](../../tests/customer-ui-foundation.playwright.js)
- [tests/customer-ui-hardening.playwright.js](../../tests/customer-ui-hardening.playwright.js)
- [tests/customer-ui-performance.playwright.js](../../tests/customer-ui-performance.playwright.js)
- [tests/customer-ui-public.playwright.js](../../tests/customer-ui-public.playwright.js)
- [tests/customer-ui-transactions.playwright.js](../../tests/customer-ui-transactions.playwright.js)
- [tests/customer_ui_preview.py](../../tests/customer_ui_preview.py)
- [tests/test_customer_ui_foundation.py](../../tests/test_customer_ui_foundation.py)

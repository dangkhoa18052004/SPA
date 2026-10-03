# Phase 4 completion - packages, payment and counter sales

Status: implementation and local tests ready; real bank configuration is still missing.
No database reset/drop/seed or payroll/attendance/commission changes.
TheLieuTrinh is a treatment entitlement record, never an electronic card issued to customers.

## 1. Payment architecture

GoiDichVuPurchase remains the package sale transaction, separate from appointment HoaDon.
Customer and counter sales call the same package service. VietQR generation and SePay verification
reuse the existing invoice payment services/webhook. pending -> paid -> activate once; purchase_id
is unique on TheLieuTrinh. The purchase snapshot freezes items, price, validity and package cover.

## 2. Why VietQR previously reported missing configuration

Local Config inspection found VIETQR_BANK_ID, VIETQR_ACCOUNT_NO, VIETQR_ACCOUNT_NAME all absent.
SEPAY_API_KEY is present. The .env only has the SePay key among bank-related settings; there are
no alternate bank environment names to reuse. Invoice and package both call the same helper,
so this is missing bank configuration, not a second package payment system or a localhost QR bug.
No credential values were printed or committed. Bank/account details have been requested from the user.

## 3. Environment/configuration

Existing variables, no rename/new secret:

```dotenv
VIETQR_BANK_ID=<bank BIN or supported bank code>
VIETQR_ACCOUNT_NO=<Bin Spa receiving account>
VIETQR_ACCOUNT_NAME=<receiving account holder>
SEPAY_API_KEY=<existing webhook authentication key>
```

Put actual values in the local untracked .env and in deployment environment variables; restart
Flask to load changed environment. /api/packages/payment-options reports a boolean only.
When bank details are absent the UI disables VietQR and defaults to counter cash; requests for
unavailable VietQR return 503 JSON without creating an orphan purchase. Pending purchase/history
queries remain JSON even if bank configuration subsequently disappears.
QR QuickLink parameters are URL-encoded (including account names containing '&'). See
[official VietQR QuickLink documentation](https://www.vietqr.io/intro/).

## 4. Customer VietQR flow

Choose package -> authenticated purchase API -> pending purchase with DB price -> PKG{id} QR.
Modal shows expected amount, bank account, transfer reference and pending status. The owner's
status endpoint is polled every 5 seconds, bounded to 60 polls (5 minutes); paid stops polling
and displays activation success. A manual recheck and pending-purchase resume remain available.
Only the authenticated bank webhook changes a VietQR purchase to paid.

## 5. Counter cash flow

Admin/manager/letan search active customers by name/phone, select an active package and create
pending purchase. Enter cash tender; UI calculates change. Backend locks purchase, verifies tender
is at least the stored expected amount, records cash_received/confirmed_by_staff, marks paid and
activates once. Revenue uses purchase.amount, never the larger cash tender. Repeat confirmation
preserves the first audit/tender/activation. Staff role and inactive operators are rejected.

## 6. Counter VietQR flow

Same counter form creates pending purchase with created_by_staff. Show QR, wait for authenticated
SePay webhook, poll admin status and refresh paid history. Cash confirmation rejects VietQR sales;
there is no transfer override or development payment simulator.

## 7. Admin sale UI

/admin/package-sales is available to admin/manager/letan; technical staff cannot use its APIs.
Menu added for those three roles. Package settings remain admin/manager only. The page has customer
search, package preview, method selection, tender/change, filterable history and detail/receipt actions.
History currently shows up to 200 newest transactions; customer search returns up to 30 matches.

## 8. Package sale receipt

PG{id padded to six digits} is the display receipt code; PKG{id} is the bank reference.
Receipt includes customer/phone, snapshotted package/items, amount, validity, method/status,
creation/payment times and operator. In-website dialog uses window.print() plus scoped print CSS.
This is an internal sale receipt, not a VAT/legal invoice. Chrome exports a test PDF to
 tests/runtime_phase4_ui/package-receipt.pdf and checks a single-item receipt has no blank pages.

## 9. Migration

New migration: 20261002_0005_package_sales.py, down_revision 20261002_0004.
Adds GoiDichVu.anhgoi (binary), nullable validity_months, nullable TheLieuTrinh.expires_at,
and purchase created_by_staff/confirmed_by_staff (staff FKs) plus cash_received.
Updates positive-month check to permit NULL and reject zero. PostgreSQL upgrade was applied
locally; current/head are 20261002_0005. Phase 4 Alembic metadata comparison returned no differences.
37 existing services and their 37 stored images remain. Migration uses additive/alter DDL without
replacing live data. Downgrade refuses to fabricate expiry for unlimited records.

```powershell
python -m flask --app wsgi:app db upgrade
python -m flask --app wsgi:app db current
```

## 10. Images

Reuse DichVu's DB binary storage and base64 serialization. New package cover fallback order:
package image -> first service image -> static default-package.svg. Treatment cover uses purchase
snapshot, with compatibility fallback for purchases from before this extension.
Shared read_validated_image verifies extension/MIME/content, limits upload to 5 MB and 20 MP,
normalizes to JPEG up to 1600px, and never executes filenames or writes uploaded paths.
Admin package create/edit accepts JSON or multipart (data JSON + anhgoi), saving fields/image in
one transaction. Edit without a new file retains old image. The dedicated image PUT also exists.
Service UI already had create/edit upload/preview; its backend now validates using the same helper
while preserving existing stored images and edits without image.

## 11. Unlimited validity

NULL months means unlimited, never zero. Admin checkbox disables/requires month input correctly.
Purchase snapshot with NULL activates expires_at=NULL; dated packages keep calendar-month expiry.
All reserve/reschedule/serialization and booking UI checks guard nullable expiry. Active state and
available sessions still apply; reserve/release/consume ledger semantics are retained.
Existing finite entitlements are unchanged when package catalog validity is edited.
Expiry remains inclusive of the expiry calendar day, matching the existing booking policy.

## 12. UI changes/files

Customer listing: 3 desktop cards, 2 tablet, 1 mobile, covers, positive-only savings, concise service
counts, payment choice and purchase CTA. Detail uses cover/info columns, stacking on mobile.
Treatment cards show cover/status/dates, used/reserved/available counts and progress/history.
Admin warns when package price exceeds snapshotted retail total, without blocking save.

Modified: app/models.py, app/services/package_service.py, app/routes/package_bp.py,
app/services/vietqr_service.py, app/services/upload_service.py, app/admin/service_manage_bp.py,
app/static/js/packages.js, app/static/css/packages.css, app/static/js/admin/admin_layout.js,
app/templates/admin/packages.html, app/templates/customer/packages.html, tests/phase4_ui_check.py.
New: migrations/versions/20261002_0005_package_sales.py,
app/templates/admin/package_sales.html, app/static/js/admin/package-sales.js,
app/static/images/default-package.svg, tests/test_package_completion.py, this report.

## 13. Revenue / ledger

Paid package amount is counted once via paid_package_revenue(). Counter cash change/tender is not
additional revenue. Redemption does not create new ThanhToan or charge covered services again.
Analytics retains the existing integration point for adding package revenue to charts later.
Available = purchased sessions - consumed - reserved; release does not count against availability.
Existing unit-value snapshots remain available for future commission; no commission work was added.

## 14. API additions/changes

| Method | URL | Access |
| --- | --- | --- |
| GET | /api/packages/payment-options | Public availability boolean |
| POST/PUT | /api/admin/packages[/<id>] | Admin/manager; JSON or multipart image |
| PUT | /api/admin/packages/<id>/image | Admin/manager; multipart anhgoi |
| GET | /api/packages/purchases/<id>/status | Owner customer; alias of existing purchase GET |
| GET | /api/admin/package-sales/customers?search=... | Admin/manager/letan |
| GET/POST | /api/admin/package-sales | Admin/manager/letan history/create |
| GET | /api/admin/package-sales/<id>[/status] | Admin/manager/letan receipt/status |
| POST | /api/admin/packages/purchases/<id>/confirm-payment | Admin/manager/letan cash only |

Counter POST body: {makh,magoi,payment_method}. It ignores supplied amount/status.
Cash body: {cash_received}; legacy exact {amount} confirmation remains compatible.
Existing package/customer/ledger/post-care routes remain available.

## 15. Webhook

POST /api/payment/webhook/sepay continues authenticating through SEPAY_API_KEY and the existing
PaymentWebhookEvent audit. HD references use the original invoice path; PKG references use the
package path. Incoming exact-amount transfer -> paid -> one treatment and one set of items.
Duplicate events/confirmation remain idempotent. No alternate webhook system or manual QR-paid API.
For local auto-confirm, configure a public HTTPS tunnel/test server webhook URL ending in
/api/payment/webhook/sepay. 127.0.0.1 cannot be reached by SePay externally. See
[official SePay local development guidance](https://developer.sepay.vn/en/sepay-webhooks).

## 16. Automated tests

Baseline: 108 passed, 0 failed. After extension: 123 passed, 0 failed (15 added cases).
Existing SQLAlchemy/datetime warnings remain (1247 reported). New cases include image fallback,
replace/preserve/spoofed/oversized files, atomic create+image, service image create/edit, 8-month
and unlimited activation/reserve, invalid zero validity, negative savings, cash tender/change/audit,
authorization, QR amount/reference/encoding, duplicate webhook and status polling APIs.

```powershell
python -m pytest -q -p no:cacheprovider --disable-warnings
python tests/phase4_ui_check.py
```

Chrome on isolated DB: five widths (1920/1440/1024/768/390), grid columns, covers loaded, no JS
errors, no control overflow; package create upload/unlimited checkbox; receptionist cash/change/
receipt print; counter VietQR webhook/poll success; original reserve/release/consume/history/review.
Mock payment events and mocked emails only, no real transactions/messages.

## 17. Manual checklist

- /admin/packages: upload/preview, edit retaining/replacing cover; first-service/default fallback;
  toggle unlimited, finite months required; price > retail warning. Invalid/spoofed/oversized images reject.
- /admin/services: existing upload/preview still works; edit text retains old cover.
- /packages and detail: check 3/2/1 cards, real covers, positive savings only and payment modal.
- /profile#treatments: dates, unlimited label, progress/counts/history, empty purchase CTA.
- Booking: finite-expired rejects; unlimited accepts while active/available; cancel releases;
  completed consumes once; regular booking remains normal.
- /admin/package-sales as letan: customer name/phone search, package preview, short tender blocked,
  valid tender/change, paid receipt/history, print; KTV/customer cannot confirm.
- VietQR: fill real bank config, restart server, validate generated QR account/amount/reference,
  configure authenticated public webhook, use provider test mode; paid updates both customer/admin,
  duplicate transfer does not create more records. Existing HD webhook/payment still works.

## 18. Remaining operations / risks

The actual receiving bank/account/name have not been provided, so real customer/counter VietQR
cannot yet be verified locally; the UI correctly disables it. User must supply those three values.
SePay key remains configured and secret; no key should be sent in chat or committed.
Production needs the same migration and HTTPS webhook configuration; no real payment was initiated.
Images are DB binary/base64, including purchase cover snapshots, so DB/JSON sizes grow with images;
normalization bounds new uploads. History/search have the limits described above.
Package analytics charts still require the documented revenue integration if desired later.
Automated care worker deployment/settings are unchanged from Phase 4.

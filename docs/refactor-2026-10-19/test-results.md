# Test results — 20/10/2026

Repository `E:\Project\Spa\SPA`; Edge/Chromium Playwright CLI on Windows. No hosted CI or production mutation. Full logs: [output](../../output/refactor-2026-10-19/). Tests ran during each implementation gate before continuing.

## Final checks

| Command / environment | Actual result | Evidence |
|---|---|---|
| `python scripts/test_with_postgres.py -- -q --tb=short --disable-warnings` | **830 passed, 0 failed, 0 skipped**, 818.15s. Disposable PostgreSQL, includes migrations and concurrency. Cluster stopped by wrapper. | [full log](../../output/refactor-2026-10-19/final-pytest-postgres.log) |
| Focused pytest: `tests/test_public_catalog.py tests/test_recommendations.py -q --tb=short --disable-warnings` | **73 passed** after final bounded-image loading optimization/additional test. | [API delta](../../output/refactor-2026-10-19/final-api-performance-pytest.log) |
| Static/UI asset/backend focused checks after cache-version/template correction | **45 passed**. | [asset checks](../../output/refactor-2026-10-19/final-ui-assets-pytest.log) |
| `python -m pytest tests/test_customer_static_assets.py tests/test_customer_ui_foundation.py tests/test_public_catalog.py -q --tb=short --disable-warnings` | **32 passed** after synchronizing shared asset versions across all template consumers. | [final cache checks](../../output/refactor-2026-10-19/final-cache-assets-pytest.log) |
| `npm run build` in `frontend` (`tsc --noEmit && vite build`) | **PASS**, final rerun includes gift unknown-response fix. Existing shared chunk >500 kB warning. | [build](../../output/refactor-2026-10-19/final-build.log) |
| `npm test -- --run` in `frontend` | **71 passed**, 13 files, final rerun. | [Vitest](../../output/refactor-2026-10-19/final-vitest.log) |
| `node --test tests/services-catalog-ui.test.cjs tests/loyalty-ui.test.cjs` | **52 passed**, 0 failed/skipped. | [Node](../../output/refactor-2026-10-19/final-node.log) |
| Isolated PostgreSQL concurrency gate | **24 passed**. Included again in full suite. | [concurrency](../../output/refactor-2026-10-19/postgres-concurrency.log) |
| `python scripts/verify_catalog_contract_readonly.py` | **PASS** against configured DB with enforced READ ONLY: 55 services, 6 public categories, page 1 has 9, total_pages 7. No PII/secrets printed. | [read-only API](../../output/refactor-2026-10-19/configured-db-readonly-api.log) |

The 830-test full run preceded the final image-query optimization and static template/cache correction. Those deltas passed the 73/45 focused checks above; the whole suite was not rerun afterward. The final gift UI catch-path change passed build/Vitest and its dedicated Playwright lost-response test. Do not add these overlapping counts together as distinct tests.

## Phase gates

| Phase | Backend / unit | Browser verification |
|---|---|---|
| PR0 | Baseline 779 passed / 24 skipped, build/typecheck | Original before screenshots: 25 public combinations plus 12 authenticated/runtime combinations. |
| PR1 | 74 backend, 69 Vitest | Real local API 25 items→9/9/7, exact categories. |
| PR2 | 75 backend, 8 Node | Legacy/enhanced ×360/390/768/1024/1440; one-result grid, categories, filters/URL/order. |
| PR3 | 100 backend | Both UI versions ×5 widths; package cardinality 0/1/9/10/25/100, pagination/URL/detail. |
| PR4 | 60 backend, 69 Vitest | One summary/selector, focus return, six-card paging, treatment amount, double-click/lost-response booking one POST. |
| PR5 | 58 passed/1 skipped at phase gate, 52 Node, 69 Vitest | Long voucher at five widths, preview no writes, same dialog node through point/voucher apply/remove; lost-response one mutation. |
| PR6 | 58 passed/1 skipped +12 inbox tests, 52 Node | 17 threads, unread116→16, 99+, page2→newest top, no hidden/unopened message GET, selection/draft kept, one send; AI/live chat legacy/enhanced ×5; legacy inbox ×5. |
| PR7 | 19 backend, 70 Vitest | Both versions ×5; voucher no handover, cancel=0 POST, double-confirm=1 POST, repeat idempotent. |
| PR8 | 65 passed/2 skipped, 70 Vitest | 120 checks: four roles ×6 employee routes ×5 widths; real login API, direct own profile/return, desktop/mobile logout. Actual MFA enrollment/step-up regression also passed. |
| PR9 | Final gates above resolve environment skips with PostgreSQL | Integrated customer booking/treatment/points/voucher/QR/purchase recovery; network/error/empty states, layout, legacy regressions, gift unknown-response recovery. |

Earlier skips were PostgreSQL/environment dependent, not removed assertions. Full PostgreSQL final run has zero skips. Existing browser selectors changed only where the real control changed (`Trao quà`, voucher radios, DOM dataset mock); business assertions were retained.

## Browser reproduction and logs

Start only disposable QA data, never the configured application DB:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -u tests/master_ui_preview.py
# Separate terminal; loopback only, Edge installed locally:
playwright-cli.cmd -s=binspa-master open http://127.0.0.1:5088 --browser=msedge
playwright-cli.cmd -s=binspa-master run-code --filename=tests/master-catalog.playwright.js
```

Use a fresh QA process between mutation suites if fixture state has been consumed. QA entry points are defined only by the test runner, never registered by the application factory in production. `--payments --port 5089` uses an obvious offline test bank account and disabled external providers; the browser intercepts the QR image. Do not use generated QR for payment.

| Script / existing regression | Result and log |
|---|---|
| `master-catalog.playwright.js`, `master-packages.playwright.js`, `master-payment.playwright.js` | PASS [catalog](../../output/refactor-2026-10-19/final-catalog-browser.log), [packages](../../output/refactor-2026-10-19/final-packages-browser.log), [payment](../../output/refactor-2026-10-19/final-payment-browser.log). |
| `master-booking.playwright.js` | PASS [summary/source/recovery](../../output/refactor-2026-10-19/pr4-browser.log). |
| `master-chat.playwright.js`, `master-legacy-inbox.playwright.js` | PASS [chat](../../output/refactor-2026-10-19/pr6-browser.log), [legacy](../../output/refactor-2026-10-19/pr6-browser-legacy.log). |
| `master-gifts.playwright.js` | PASS [gift desk/confirm](../../output/refactor-2026-10-19/pr7-browser.log). |
| `master-gift-recovery.playwright.js` | PASS: committed POST response lost, subsequent GET503, no stale confirm/rePOST, successful GET retry shows fulfilled. [log](../../output/refactor-2026-10-19/pr9-gift-recovery.log). |
| `master-staff.playwright.js` | PASS [120 route/role/viewport checks](../../output/refactor-2026-10-19/pr9-staff-browser.log). |
| `master-customer-flow.playwright.js` at 390/1440 | PASS: package entitlement +service20, appointment prepay, 30%voucher+100points, server payable and QR103000, close stays unpaid; unknown package POST creates once then auto-recovers/resumes. [log](../../output/refactor-2026-10-19/pr9-customer-flow.log). |
| `master-purchase-recovery.playwright.js` | PASS: unknown purchase/no create, reconciliation GET503 and reload preserve marker; total POST=1. [log](../../output/refactor-2026-10-19/pr9-purchase-recovery.log). |
| `master-hardening.playwright.js` | PASS: 10 layout combinations, filter drawer/URL/ranges, API503/retry/empty, package error/retry, 200% text resize. [log](../../output/refactor-2026-10-19/pr9-hardening-browser.log). |
| `master-final-visual.playwright.js` | PASS: home/detail legacy/enhanced at390/1440,6 home cards/real categories, confirmed hotline, price contrast>=4.5:1, no page errors/overflow, local payload metrics. [log](../../output/refactor-2026-10-19/pr9-final-visual.log). |
| `staff_security_browser_check.py` | PASS real MFA at360/390/768/1440. Harness cleanup now closes its Chrome gracefully then bounds own-process wait. [log](../../output/refactor-2026-10-19/pr9-security-browser.log). |
| `booking_catalog_browser_check.py` | PASS390/768/1440. [log](../../output/refactor-2026-10-19/pr9-booking-regression.log). |
| `phase4_browser_check.py` | PASS package/gift, lost-response, guest deep links and synthetic VietQR. [log](../../output/refactor-2026-10-19/pr9-transactions-regression.log). |
| `loyalty_customer_browser_check.py`, `loyalty_browser_check.py`, `admin_care_browser_check.py` | PASS [customer](../../output/refactor-2026-10-19/pr9-loyalty-customer-browser.log), [admin legacy](../../output/refactor-2026-10-19/pr9-loyalty-admin-browser.log), [admin care](../../output/refactor-2026-10-19/pr9-admin-care-browser.log). |

## Coverage boundaries

API tests cover 0/1/9/10/25/100/500 services; browser package/cardinality tests cover 0/1/9/10/25/100. Filters/sorting execute before paging, one result keeps one desktop column. Security includes3599/3600/3601 seconds, earlier JWT expiry/revoke, role permissions; gift/purchase/loyalty concurrency uses real isolated PostgreSQL transactions.

Console/page errors and critical requests are asserted by browser suites; intentional injected401/400/403/409/503/abort cases are expected. No assertion was disabled to obtain PASS. The application configured DB was accessed only under READ ONLY guards. Physical mobile keyboard, native zoom200%, hosted CI/staging and bank settlement remain release/manual checks. Local Playwright viewport and text resize cannot establish those results.

Native zoom capability was explicitly probed using browser shortcuts; this headless session kept DPR/viewport unchanged, so it is not counted as native zoom coverage. [Probe log](../../output/refactor-2026-10-19/native-zoom-capability.log).

# Master plan implementation — local workspace

No push, merge, deploy, production flag change or schema migration. Source plan left untouched. All mutation QA uses isolated SQLite/browser fixtures.

| Phase | Status | Implementation / evidence |
|---|---|---|
| PR0 | PASS local audit | HEAD/runtime/flags, read-only configured database counts, 25 public baseline combinations plus 12 authenticated/catalog baseline combinations. Both lists reproduced 25 unpaged cards. |
| PR1 | PASS | Public `/api/services/categories`; exact slug matching, neutral absent/inactive category metadata; validated price/duration ranges; opt-in page/per_page (9 default, cap 100), slicing after ranking. 74 backend + 69 Vitest, browser real API 9/9/7. |
| PR2 | PASS | Dynamic home/service categories; home filters full ranked data; service search debounce/abort/stale guard, ranges, URL pushState/Back, empty/error/retry, 3/2/1 fixed columns; detail uses DB category. 75 backend + 8 Node; browser legacy/refactor × 5 widths. |
| PR3 | PASS local | PKG-01..03: compact package listing, full detail/per-session breakdown retained; full-data search then stable sort then 9-per-page; URL history, bounded grid. Browser 10 layouts and 0/1/9/10/25/100-card cases. Purchase mutex plus customer/package sessionStorage snapshot recover unknown POST outcomes through GET across reload without blind retry. |
| PR4 | PASS local | BOOK-01..03: existing source selector moved into one summary; sticky desktop, compact bar/native drawer mobile, same state/controls. Existing 6-service paging and three-step server policy preserved. Five widths, focus return, entitlement/subtotal and lost-response one-POST recovery verified. |
| PR5 | PASS local | PAY-01..05: voucher radio cards wrap long labels/terms; point preview validation/loading/error/aria-live; apply/remove updates same dialog node/focus/scroll. Invalidate stale QR, GET reconciliation before mutation retry, sticky header/footer and internal scroll. Five widths and real isolated server totals verified. |
| PR6 | PASS local | CHAT-01..05: shared green/cream/dark tokens, distinct AI/human labels, mutually exclusive panels. Stable newest-first sort before paging; thread/menu 99+ badges, shared list-only polling, visibility/stale guards, selected/draft retained. Backend batched unread/name queries; existing RBAC/read semantics retained. Both UI versions at five widths. |
| PR7 | PASS local | GIFT-01..04: compact gift desk, physical/voucher type labels, voucher payment guidance/terms. Trao quà only for available unexpired physical gifts; confirm customer/code/expiry, send mutex, reload status after unknown outcome. Existing endpoint, RBAC, audit and DB idempotency preserved. Cancel/double click/repeat and concurrency verified. |
| PR8 | PASS local | SEC-01..04: step-up 600→3600 seconds, still capped by JWT expiry; no login/session/enrollment TTL change. Direct staff profile/navbar/logout desktop and mobile; existing profile with return link. Offline logout and BFCache revalidation. 120 role/route/viewport checks plus actual API login/logout and real MFA regression. |
| PR9 | PASS local; release gates separate | QA-01..03: full isolated PostgreSQL 830/830, follow-up backend checks, build/typecheck/Vitest/Node, end-to-end Playwright and browser regressions; artifact index, changed files, manual/release/rollback documentation. Hosted CI/staging/deploy have not run. |

## Compatibility decisions

- `/api/services` without pagination keeps all matches and old response fields; categories add a public read-only endpoint. Exact slug replaces former UI aliases intentionally; consumers audited: booking/home request full lists, catalog now sends persisted slug. No API field removed.
- Null/unavailable category metadata becomes null; service remains in All, with neutral UI label. No inferred category or data rewrite.
- Range errors/nonfinite numbers/reversed ranges/pagination errors return 400; out-of-range API pages return empty, UI normalizes to last page. Empty catalog has total_pages=0. Ranking remains before slice; only paged services are serialized.
- Packages API/purchase/QR contracts unchanged. Client filters all active/customer-sale-enabled records before slicing. Full detail/admin renderer retained.
- Paginated candidates defer image blobs; one bounded query fetches images for the selected page. No N+1 image reads or image field contract change.
- Unknown purchase outcomes retain a customer/package sessionStorage marker across reload. Only GET reconciliation runs until the result is resolved; no automatic POST retry or new schema/ledger.
- Chat badges request only conversation lists, never messages for unopened threads. Existing GET-messages mark-read behavior and visibility permissions remain. Polling remains the established transport.
- Physical gift fulfillment keeps admin/manager/letan permissions and existing server idempotency/audit. Voucher has no counter handover mutation. Failed handover response discards the stale confirmation and reloads server state before another action.
- Only server step-up duration changes. JWT/session expiry, OTP setup 10-minute deadline, generation/JTI/auth-digest revocation and role checks remain unchanged.
- Previous catalog Node tests assumed client-only filtering and the removed acne/facial grouping. Replaced with request/range/URL/race/error tests for the new contract; backend and browser tests verify actual filtering/order and the exact DB category requirement.

See `test-results.md` for final commands/results and `release-checklist.md` for deployment prerequisites/rollback.

## Verified content and boundaries

The owner confirmed CS1 hotline **0387829152** in this session; visible “038 782 9152” now links to `tel:0387829152`. Unverified hardcoded marketing statistics/testimonials were removed without inventing replacements. Fake catalog/payment data exists only in isolated test fixtures.

No critical application defect remains known in the tested local scope. Shared Ant Design chunk >500 kB remains a build warning. Hosted CI/staging, physical iOS/Android keyboard, native browser 200% zoom and actual banking settlement have not been verified; emulated viewports, 200% text resize and server/QR amounts were verified. QR display/closing never marks a transaction paid.

PR0–PR9 label local implementation groups, not published GitHub pull requests. The original untracked master plan and other user work are preserved. No new dependencies, schema migration, production flag/configuration changes, push or deploy.

See [changed files](changed-files.md), [visual evidence](visual-evidence.md) and [release/manual QA/rollback](release-checklist.md).

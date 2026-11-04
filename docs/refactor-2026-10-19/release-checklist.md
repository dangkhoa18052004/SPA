# Manual QA, release gates and rollback

All PR0–PR9 implementation/local gates are complete. No deploy/push/production flag/config change/schema migration has been performed. This document describes future authorized release work, not approval to execute it.

## Before release

- Review the workspace diff and [changed files](changed-files.md); keep the original user master plan and any later unrelated changes. Create reviewable commits/PRs only when requested.
- Run hosted CI and an authorized preview/staging smoke with PostgreSQL. The disposable local PostgreSQL suite passed830/830; this does not claim hosted staging has run.
- Build **all entries** using `cd frontend; npm ci; npm run build` in deployment CI. Existing lockfile/dependencies suffice. Publish assets and manifest together; verify the resolver finds the complete manifest and cache versions. Do not publish source without matching built assets.
- No new schema migration or environment variable is required. Do not run migrations against production as part of this UI change. Keep existing production data/ledger/stock intact.
- Owner approval is required for deploy and any production configuration/flag change. Configured local public/account flags are OFF, booking/employee/admin groups ON; both legacy and enabled React paths were patched and tested. Do not enable flags just to expose this work. Check actual target environment booleans/manifest without printing secrets.
- Retain the existing database backup procedure before an authorized release; verify restoration procedures with the operator. This work does not need a data rewrite or backup restore to roll back code.
- CS1 hotline0387829152 is confirmed by owner and text/href agree. Other unverified statistics/testimonials were removed, not replaced with invented data.
- Verify physical iOS/Android virtual keyboard, actual browser200% zoom, screen reader flow and real-provider staging integration. Existing chunk-size warning remains; review separately if the performance budget requires splitting the shared Ant bundle.

## Manual customer smoke

1. Open `/`, `/services`, `/services/<real id>` and `/packages` as guest and customer in the target runtime. Categories must match active populated DB categories. Search then category/ranges/sort use AND, changed filters reset page1; Reload/Back preserve query. At360/390/768/1024/1440 check0/1/9/10+ results,9 per page, no stretched lone card/overflow, keyboard focus and loading/error/retry.
2. Home shows up to6 ranked services after applying a real category. Detail keeps booking/deep links and full content. Package cards are concise; package detail retains all items, sessions, unit values/validity/terms. Disabled sale/provider cannot initiate a purchase.
3. Guest→login→resume package; inspect a pending purchase and close/reopen without cancellation. Under throttled/lost response, verify GET reconciliation and one create request. An unresolved purchase marker deliberately blocks blind repeat until state can be checked.
4. `/appointments/create?service=<id>`: select services, change catalog page (still6/page), open summary, select a valid treatment source and back to cash. Verify one selector per service, subtotal, next/back/date/slot, source persistence and three-step submit. Desktop sticky and mobile drawer must leave navigation reachable. Double-click submit creates one appointment; loss of response checks existing appointment instead of rePOST.
5. On invoice/package payment, select a long voucher and preview points. Preview changes no ledger; invalid/over-max input explains the error. Apply/remove updates totals in the same open dialog, keeps focus, clears stale QR. Exercise expired/incompatible voucher and network failures. Compare payable amount to server and QR, verify closing never marks paid. Use a designated staging payment flow only with owner authorization.
6. Open AI/live chat separately: correct labels/palette, draft/retry, links/service cards/images and long text; only one panel open, no mobile-nav overlap, dark theme/focus/ESC/text resize.

## Manual staff/admin smoke

1. Login as each authorized role (staff/letan/manager/admin). From attendance/appointments/schedule/history/income/account, header `Trang cá nhân` opens the existing own profile (desktop1 click, mobile menu+item), return works. Staff must not gain admin/loyalty permissions. Check legacy fallback and current flags.
2. Inbox: leave one thread unread and send it a customer message while on page2; after polling it moves to top and count updates. Opening one thread only clears that thread; badges total match server,99+ over99. Check background tab, rapid route/back, selected thread/draft, slow/out-of-order responses and reconnect without duplicate timers/sends.
3. Gift desk as admin/manager/letan: search/filter/reset, inspect available/expired/fulfilled physical gifts and available/reserved/used vouchers. Only valid available physical gift has `Trao quà`; cancel writes nothing. Verify customer/code/expiry before confirming. Double click/lost response/two counters must preserve one fulfillment audit; failed reconciliation hides stale action. Voucher says use at payment and has no handover button. Staff/unauthorized must get403.
4. Security: enroll/verify OTP as applicable; status shows at most60min and not past JWT.exp. At59m59 verified;60m/60m1 expired. Logout/revoke/password/role/MFA changes still invalidate. Setup enrollment deadline remains10min. Login/session expiry remains unchanged.
5. Logout from header desktop/mobile. Verify server logout call and local cleanup; offline failure still clears tokens. Back/refresh/BFCache must not restore a usable protected session.

## Rollback

Use a reviewed code/asset rollback through the normal release process. Baseline is `61b8a54407e8db527bd85ab6d7430ab9ecaa3a04`; do not run `git reset --hard`, `git clean` or overwrite the user master plan/unrelated work.

1. Save this task diff and any unrelated working changes separately. Restore only the reviewed files in [changed-files.md] from the approved preceding release (or revert this task's later commits). Remove only newly added task source files if reverting the complete implementation. Do not delete database files/rows/ledger or test/user artifacts indiscriminately.
2. Rebuild all frontend entries from the selected release and ship matching manifest/assets together; restore legacy asset versions/templates with their code. Clear only application asset caches via existing deployment procedure.
3. If a React-only issue needs a temporary fallback, use existing per-surface feature flags only after owner approval; fallback legacy was also changed here, so a flag alone is not a complete code rollback. Never alter login TTL/security policies as a workaround.
4. To roll back the duration change specifically, revert `ELEVATION_SECONDS` and its UI wording to the prior release, keeping JWT/session TTL and revocation unchanged. Existing already-issued grants require the operator's normal revocation policy if immediate expiration is required; do not silently rewrite database grants.
5. Recheck public API legacy full-list callers, booking, pending payment resumption, unread counts, fulfillment status and login/logout against server. Successful transactions during the release remain business records; do not reverse them as part of UI rollback.

No unresolved business/schema decision blocks the local implementation. Production release and remaining hosted/device/provider checks are deliberately outside this session's authorization.

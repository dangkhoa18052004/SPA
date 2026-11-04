# PR0 baseline — 20/10/2026

HEAD: `61b8a54407e8db527bd85ab6d7430ab9ecaa3a04`, matches master plan. Initial working tree: only untracked `plans/plan_19_10_2026.md`; preserved. No other uncommitted work.

## Architecture and runtime

Flask/SQLAlchemy/PostgreSQL; React 18/TypeScript/Vite/Ant Design 5 alongside Jinja/vanilla JS. Public/account enhancement requires flag **and complete manifest**. Booking has its own React entry. Shared packages/loyalty scripts remain owners of transactions in both interfaces.

Local configured flags (boolean values only inspected): public/account OFF; customer booking ON; employee/business portals ON; admin booking/billing/catalog/people/care ON; staff security ON. These values have not been changed. `/`, `/services`, `/services/<id>`, `/packages`, `/packages/<id>` therefore normally render legacy; `/appointments/create` React; `/profile#treatments` legacy; employee and enabled admin groups React if assets are present. `?ui=legacy` preserves fallback.

Isolated preview `http://127.0.0.1:5087`: existing SQLite fixture, public/account/booking ON, external mail/banking/AI disabled. No configured DB writes. Playwright CLI Edge: 5 routes × 360/390/768/1024/1440px, 25 screenshots, no horizontal overflow, page errors=[], failed requests=[]. Expected guest session-restore HTTP 401 remains. Screenshots: `output/refactor-2026-10-19/visual-before-after/before-*`. Build/typecheck PASS. Full baseline pytest log: `output/refactor-2026-10-19/pr0-pytest.log` (result tracked in test-results).

## Database audit

`python scripts/audit_catalog_readonly.py` used SQL SELECT in a PostgreSQL READ ONLY transaction. Only non-PII category fields/counts printed. 55 active services, 7 active categories, 0 null/invalid FKs, 0 missing images, 0 duplicate slugs.

| DB category slug | Active services |
|---|---:|
| body-care | 9 |
| facial | 15 |
| acne | 11 |
| massage | 11 |
| nail | 4 |
| relaxation | 0 |
| hair | 5 |

Public categories must include the six active categories with active services. Names/IDs/slugs come from API, never this audit table. Null categories appear in All with neutral label; inactive category metadata is not published.

## Confirmed defects / existing functions

- Service API has `facial -> facial/acne`, `body -> body-care` aliases, no pagination/range filters. Client additionally guesses categories from keywords; both need removal.
- Home chips hardcoded and filter only the six already-rendered cards. Service list loads all results. Package list renders all packages with full item breakdown.
- New public CSS already provides 3/2/1 grid, but local configured legacy remains active. Changes must work in both paths; no production flag changes.
- Booking already pages by 6 and has one summary; source selector is after catalog. Move existing control rather than duplicate state.
- Payment, pending reconciliation, loyalty preview/apply, AI jobs, chat polling/unread, gift fulfill endpoint, admin account/logout already exist. Preserve contracts and ownership.
- Step-up TTL is 600 seconds, independently capped by JWT expiry. Login/session duration must remain unchanged.

## Impacted modules

PR1 service routes/serializer/contracts/tests; PR2 home/services templates, shared renderer and CSS; PR3 shared package listing only; PR4 Booking/booking CSS; PR5 loyalty-payment and invoice refresh bridge; PR6 AI/live-chat CSS, chat list/poll/unread shell; PR7 existing redemption UI/model; PR8 step-up constant and employee header; PR9 consolidated tests/docs. No schema change planned.

## Closing verification

Owner confirmed CS1 hotline0387829152; text/href now agree. Actual configured DB API was verified after implementation inside enforced READ ONLY transactions:55 active services,6 public categories, first page9, total_pages7. Local full isolated PostgreSQL suite passed830/830, with follow-up checks documented separately. No configured DB mutation, schema/config/flag change, push or deploy occurred.

Original before captures are supplemented with explicitly labeled retrospective HEAD asset replays on the same fixture for booking/payment/chat/inbox/gifts/navbar. See [visual evidence](visual-evidence.md) and [test results](test-results.md); no retrospective replay is presented as an initial PR0 screenshot.

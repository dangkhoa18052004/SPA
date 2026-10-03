# Phase 4 regression fix - 2026-10-02

1. Database revision before: 20261001_0003.
2. Database revision after: 20261002_0004 (single head).
3. Existing migration migrations/versions/20261002_0004_packages_and_care.py had not been applied. It already included the required column and all seven tables.
4. No new migration was generated; no duplicate migration was needed.
5. Applied nullable TEXT dichvu.post_care_instructions plus goidichvu, goidichvuitem, goidichvupurchase, thelieutrinh, thelieutrinhitem, lieutrinhusage, notificationjob, including constraints/indexes. Alembic compare_metadata filtered to Phase 4 tables and the new service column returned no differences, including type comparison. Direct queries on all seven models succeeded.
6. The missing column was caused by deploying model changes without advancing the PostgreSQL schema. No field was removed from the model.
7. GET /api/services: before 500 application/json, after 200 application/json. Response keys services/success/total. UI service cards render again on homepage and services page; booking service selection loads.
8. GET /api/packages: before 500 text/html, after 200 application/json with {"packages":[],"success":true}. Endpoint packages.packages; no duplicate prefix. Empty package list is valid.
9. Authenticated GET /api/packages/my-treatments: before 500 text/html, after 200 application/json with {"success":true,"treatments":[]}. Endpoint packages.my_treatments. This is the actual endpoint used by PackageCare.loadTreatments(), which profile.js invokes. Empty state now says the customer has no treatment records.
10. Package and treatment API errors previously returned HTML.
11. The HTML was Flask's HTTP 500 database exception/debug page, not a 404 or login redirect. Missing authentication now returns 401 JSON {success:false,message:...}, without Location. Existing CustomerAuth fetch/restore-session flow is reused; package code no longer reads its own localStorage token fallback.
12. Changed app/static/js/packages.js (Content-Type validation, malformed JSON handling, auth reuse, empty-state wording), app/routes/package_bp.py (scoped missing-auth JSON), added tests/test_phase4_regression_fix.py and this report. No UI redesign, package business logic, payroll or attendance changes.
13. No migration file was changed. Commands executed: python -m flask --app wsgi:app db current; db heads; db history; db upgrade; db current. The additive upgrade was authorized by the user's migration-fix request.
14. New automated tests cover empty package/treatment lists, 401 JSON without redirect, empty active services, HTML error responses and malformed JSON handled by the actual JavaScript through Node. Static regression test remains passing. Node syntax and git diff --check pass.
15. Full suite: 108 passed, 0 failed, 1050 warnings. Chrome on the live PostgreSQL-backed local server passed homepage, services, profile treatments, booking and packages; no captured JS errors, stylesheet rules and logo loaded. Separate isolated full Phase 4 UI check passed 1920/1440/1024/768/390 px, purchase/cash confirmation/reserve/release/consume/history/review. It never sent real payments or emails.

## Data preservation

Before and after: 37 dichvu records. All old nonbinary fields compare equal by primary-key ordering; all 37 service images remain present. The original bytea snapshot used Python memoryview string representations (which contain process addresses), so it is not a byte-for-byte image comparison. The applied migration performs only additive DDL and contains no service UPDATE/DELETE or table recreation. No database reset/drop, seed, or replacement of live data occurred.

## Verification commands

```powershell
python -m flask --app wsgi:app db current
python -m flask --app wsgi:app db heads
python -m pytest -q -p no:cacheprovider --disable-warnings
python tests/phase4_ui_check.py
```

On the live database there are currently no packages or treatments: the empty UI states are expected. Populated package/treatment rendering and the full purchase lifecycle were verified on the isolated test database, not by seeding the live database. Other deployments must apply the same migration against their configured DB before using Phase 4 code.

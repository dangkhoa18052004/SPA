# Visual QA — desktop/mobile

Artifacts: [visual-before-after](../../output/refactor-2026-10-19/visual-before-after/). Original PR0 captures precede implementation. Additional `before-head-*` captures are **retrospective browser replays of original HEAD assets**, against the same isolated fixture as their matched after capture; they are not mislabeled original PR0 captures. No production data or UI was substituted.

The original HEAD frontend was built under `.test-tmp/master-head-61b8a54` with the existing dependencies, not into the active output. Browser routes fulfilled those original assets only for replay. Scripts/logs describe this explicitly. Random gift codes and live unread data are identical within the matched replay sequence. Public original captures and final captures use disposable catalog fixtures; no production names/pictures were invented.

## Key comparisons

| Screen | Before | After |
|---|---|---|
| Home mobile390, legacy final | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-390--.png) | [current](../../output/refactor-2026-10-19/visual-before-after/after-home-legacy-390.png) |
| Home desktop1440 | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-1440--.png) | [current enhanced](../../output/refactor-2026-10-19/visual-before-after/after-home-new-1440.png) |
| Services desktop1440 | [PR0 full list](../../output/refactor-2026-10-19/visual-before-after/before-1440--services.png) | [nine per page](../../output/refactor-2026-10-19/visual-before-after/after-services-new-1440.png) |
| Services mobile390 | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-390--services.png) | [current legacy](../../output/refactor-2026-10-19/visual-before-after/after-services-legacy-390.png) |
| One service desktop1440 | [baseline list](../../output/refactor-2026-10-19/visual-before-after/before-1440--services.png) | [one bounded column](../../output/refactor-2026-10-19/visual-before-after/after-services-single-new-1440.png) |
| Detail desktop1440 | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-1440--services-1.png) | [current](../../output/refactor-2026-10-19/visual-before-after/after-service-detail-new-1440.png) |
| Packages desktop1440 | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-1440--packages.png) | [compact nine](../../output/refactor-2026-10-19/visual-before-after/after-packages-new-1440.png) |
| Packages mobile390 | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-390--packages.png) | [current legacy](../../output/refactor-2026-10-19/visual-before-after/after-packages-legacy-390.png) |
| Booking mobile390, same fixture/HEAD replay | [source below catalog](../../output/refactor-2026-10-19/visual-before-after/before-head-booking-source-390.png) | [source in summary drawer](../../output/refactor-2026-10-19/visual-before-after/after-matched-booking-source-390.png) |
| Booking desktop1440 | [PR0](../../output/refactor-2026-10-19/visual-before-after/before-runtime-1440--appointments-create.png) | [sticky summary](../../output/refactor-2026-10-19/visual-before-after/after-booking-1440.png) |
| Payment mobile390, HEAD replay long voucher | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-payment-390.png) | [wrapped radio cards](../../output/refactor-2026-10-19/visual-before-after/after-payment-390.png) |
| Payment desktop1440 | [HEAD replay](../../output/refactor-2026-10-19/visual-before-after/before-head-payment-1440.png) | [current](../../output/refactor-2026-10-19/visual-before-after/after-payment-1440.png) |
| AI mobile390 | [HEAD CSS replay](../../output/refactor-2026-10-19/visual-before-after/before-head-ai-chat-390.png) | [current legacy](../../output/refactor-2026-10-19/visual-before-after/after-ai-chat-legacy-390.png) |
| Human chat desktop1440 | [HEAD CSS replay](../../output/refactor-2026-10-19/visual-before-after/before-head-live-chat-1440.png) | [current legacy](../../output/refactor-2026-10-19/visual-before-after/after-live-chat-legacy-1440.png) |
| Inbox mobile390, same fixture/HEAD React replay | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-react-inbox-390.png) | [after](../../output/refactor-2026-10-19/visual-before-after/after-matched-inbox-390.png) |
| Inbox desktop1440, same fixture | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-react-inbox-1440.png) | [after](../../output/refactor-2026-10-19/visual-before-after/after-matched-inbox-1440.png) |
| Gift desk mobile390, same fixture | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-react-gifts-390.png) | [after](../../output/refactor-2026-10-19/visual-before-after/after-matched-gifts-390.png) |
| Gift desk desktop1440, same fixture | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-react-gifts-1440.png) | [after](../../output/refactor-2026-10-19/visual-before-after/after-matched-gifts-1440.png) |
| Staff navbar mobile390, same fixture | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-react-staff-navbar-390.png) | [after](../../output/refactor-2026-10-19/visual-before-after/after-matched-staff-navbar-390.png) |
| Staff navbar desktop1440, same fixture | [before](../../output/refactor-2026-10-19/visual-before-after/before-head-react-staff-navbar-1440.png) | [after](../../output/refactor-2026-10-19/visual-before-after/after-matched-staff-navbar-1440.png) |

Additional `after-*` screenshots cover360/390/768/1024/1440, both public/legacy chat and gift variants, four own-profile roles, gift confirmation and customer QR flow. Open [staff profile](../../output/refactor-2026-10-19/visual-before-after/after-profile-staff-390.png) and [gift confirmation](../../output/refactor-2026-10-19/visual-before-after/after-gift-confirm-new-390.png).

## Motion, DOM and local metrics

- [Booking before/after video](../../output/refactor-2026-10-19/booking-before-after.webm): HEAD replay then current mobile, same fixture; source selector scroll/drawer and change/restore without POST. [Assertions](../../output/refactor-2026-10-19/pr9-booking-visual.log).
- Payment DOM assertions reproduced original HEAD replacing the dialog node after point apply, then current code preserving exactly the same node and no close event through point/voucher apply/remove. [HEAD reproduction](../../output/refactor-2026-10-19/pr9-head-baseline-replay.log), [current verification](../../output/refactor-2026-10-19/final-payment-browser.log). Screenshots alone cannot establish absence of flicker.
- Current catalog renders9 cards instead of25 for the same25-item local fixture. Compatible unpaged payload7825 UTF-8 bytes versus paged2882 bytes (about63% less) in the local sample. Timing is a single local sample, not a performance claim; see [metrics](../../output/refactor-2026-10-19/pr9-final-visual.log). The backend test additionally verifies one bounded image query for the page rather than reading all candidate blobs.
- Legacy service price contrast on white is checked at>=4.5:1 in final visual script. Focus/ESC/return, native modal behavior, long text/no overflow, five viewports and200% text resizing were checked. Full screen-reader certification, native200% zoom and physical mobile keyboard remain manual release gates.

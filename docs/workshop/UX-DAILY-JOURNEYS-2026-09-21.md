# Dashboard and library daily loop — 21 September 2026

Child of #793, itself a child of #790. Tracker: #772.

## User stories

- **#773:** Pull from library is disabled with an adjacent explanation when a
  recipe takes no reference. Existing Find reference recipes remains the explicit
  escape route. Eligible recipes open a loading dialog immediately. A failed/busy
  library refresh cannot display stale cached cards as a successful read. Closing,
  changing recipes or reopening invalidates old picker responses. Attachment,
  source-role ownership and Generate remain in their existing handlers.
- **#774:** A failed/uncertain standalone job on Overview opens that exact saved
  record, not an unrelated Create view. The read-only native dialog shows its ID,
  status, failure guidance, known prompt IDs and recorded controls. It marks its
  snapshot time and offers no retry/cancel action. All record text is escaped.
- **#777:** Overview offers Explore creative bundles directly. Both launchers use
  one existing explorer, review/apply gate and event handler. Browsing or closing
  restores focus and leaves the current work alone.
- **#780:** An empty output gallery explains Generate, import via Asset library,
  and Continue with this. Its import link navigates rather than generating.

## Validation

`python tests/workshop_daily_journeys.py` runs exact production scripts or explicit
legacy-function seams over synthetic native Chromium DOMs. Six new methods and
six inherited entry-point methods pass. The new cases were red before these
changes (missing launchers/inspection/guidance, delayed dialog and ambiguous read
outcome), then green. Cancellation/late replies, cached failure, escaped record
text, native focus return and both viewport widths are covered.

`python tests/workshop_daily_application.py --output .runtime/workshop-daily`
runs the full Studio at 1440px and 390px against the existing synthetic HTTP fixture.
It checks the same entry points, failure-record identity, preserved drafts,
unsupported-source explanation, library loading/failure, actual import navigation,
page errors and zero writes except time estimates. It records screenshots and
checks.json in the normal Workshop UI artifact. It must run in hosted CI here:
local Chromium blocks loopback navigation, which was not bypassed.

No runtime, model, provider, licensing, real generation or art acceptance is claimed.
#539 and all HUMAN_TODO creative/owner acceptance remain open. A concurrent library
refresh returns an explicit non-success; the picker asks the user to reopen rather
than pretending cached data is freshly loaded or starting an automatic retry.

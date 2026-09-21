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

`python tests/workshop_daily_journeys.py` runs production scripts or explicit
legacy-function seams over synthetic native Chromium DOMs. Eight daily methods
and six inherited entry-point methods pass on the integrated source. Reads and
selected-recipe changes are deferred explicitly to test cancellation, replacement,
duplicate-open suppression and preservation of newer keyboard focus.

The retained daily branch initially passed twelve methods. Continuation added
nonempty bundle search and cancellation-focus assertions: both viewport variants
left the bundle dialog open after Escape, and closing a loading library picker
lost its opener. All three assertions failed before the correction and now pass.
The bundle handles Escape before the browser's search-field clear action. The
library opener stays focusable while the native modal supplies interaction
isolation; it exposes busy state without disabling native focus return. Opening
an already-open picker cannot issue another read.

`python tests/workshop_daily_application.py --output .runtime/workshop-daily`
runs the full Studio at 1440px and 390px against the existing synthetic HTTP fixture.
It checks launcher/record identity, preserved drafts, unsupported-source
explanation, library loading/failure, actual import navigation, page errors and
zero writes except time estimates. It records screenshots and checks.json in the
Workshop UI artifact. Local Chromium refuses loopback navigation with
`ERR_BLOCKED_BY_ADMINISTRATOR`; no bypass or local HTTP-browser pass is claimed.
Hosted final-head results are recorded in the PR rather than inferred from the
renderer fixture. The fixture's bundle catalogue is empty; card exploration and
apply safeguards remain covered separately by the existing bundle browser suite.

## Reconciliation

The uploaded archive and readonly GitHub snapshot were reconstructed by exact
Git blob, mode, commit and tree identity. The original daily tree
`db046d436b36eb7b4d4c5618f8ae1e347d647dba` was preserved, then reconciled with the
updated #790/#793 stack over main `7b504b902efbb48a0dc1def6a54cedba96b762d9`.
GitHub's merge candidate and the local three-way integration independently
produced `424698c203879258a79c65ec2e65241a8ef81e48` before the focus corrections.
Newer main's model-intel and local-media fallback changes are preserved.

#790 at `c8f90f12b7009d82802844d9344992dcef9b4b09` and #793 at
`57d3ed313e7d3fc3bb06b295fb0b5e21a261c383` each passed all eleven hosted workflows.
The earlier #790 Windows mixed-batch timeout and I2V hash-field error are retained
in its history, not hidden by relaxing assertions or replacing tests. The
integrated head includes main's independent Windows descriptor-identity fix.
The separate lifetime-observability programme is not changed by this UX stack.

No runtime, model, provider, licensing, real generation or art acceptance is claimed.
#539 and all HUMAN_TODO creative/owner acceptance remain open. A concurrent library
refresh returns an explicit non-success; the picker asks the user to reopen rather
than pretending cached data is freshly loaded or starting an automatic retry.

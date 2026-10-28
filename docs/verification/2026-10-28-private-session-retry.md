# Private-session retry qualification — 28 October 2026

## Preserved source

Resumed PR #1677 at `c0ecbcbbc1c8015ae35ca5a1e7fec5a4e3194c48`, tree
`0d66e708084967b1a47e181762f6b5bb2dd713df`, after an interrupted session.
The recovered tracked archive was checked against its Git manifest and tree;
`.gitattributes` CRLF export conversions were accounted for without changing
canonical blobs. Main remains `4e753e3e9c1f5f1ac2cb2ed918e5ae6469edd74d`.

That published source has a successful Check studio run `40695334696` and
three failing browser workflows. Historical receipts are not final-head approval.

## Causal corrections

- **Make migration fixture:** assigning `Storage.prototype.setItem` as a bare
  evaluate expression returns the function. Playwright invokes function-valued
  expressions, causing an unbound native call. The same mistake affected the
  selective scene-storage fault installer. Explicit callback bodies now return
  no function; no storage-loss assertion is removed.
- **Restyle fixture:** restoring `onclick` returned the handler and invoked it
  with a null event. Restore inside a callback body without dispatching a click.
  The actual late-copy completion and stale-feedback assertions remain intact.
- **Desktop layout:** retained native evidence measured a 90.1875px privacy bar
  and 1742px document, exceeding the existing 1700px Workshop limit. Allow the
  live status to share the desktop row and reduce redundant editor top spacing.
  Session, per-creation override, all scope buttons, status and help stay visible.
  The document-height and first-viewport checks are unchanged.

Reference for evaluate semantics:
https://playwright.dev/python/docs/api/class-page#page-evaluate

## Executed checks before publication

| Check | Result |
| --- | --- |
| Actual callback-expression regressions | All three failed before the fix; 3/3 pass after |
| Exact-markup privacy layout | Both desktop status cases failed before; 2 tests pass after, including keyboard/help and widths 1440/1100/900/390/320 |
| Privacy Python contracts | 106 pass |
| Make migration and follow-up Node contracts | 27 pass |
| Repository validator | 94 graphs/bindings, 189 pinned assets, 164 LoRA names pass |

The layout driver renders shipped markup and CSS, not mocked geometry. It does
not substitute for the composed application, HTTP/storage or platform gates.
Local native HTTP navigation remains blocked (`ERR_BLOCKED_BY_ADMINISTRATOR`),
so full native Make, Restyle and Workshop qualification must run in hosted CI.
The new layout and callback checks are wired into both privacy platforms.

## Unchanged limits

No GPU/model generation, runtime installation, workstation restart, owner media
or creative/licensing acceptance. Archive, completed-run privacy migration and
broader agent organization remain independent follow-ups (#1678 / #123).
PR #1677 remains draft until the corrected exact-head checks pass.

## Native layout follow-through

The first retry passed the entire Linux privacy chain (including all seven Make
transition cases), but Workshop still measured 1707px. The toolbar reduction
was effective; editor padding was not. The shipped hidden hero is a sibling
between the privacy bar and main, so an adjacent-sibling selector missed main.
The focused layout fixture had omitted that sibling. It now retains the actual
intervening markup from index.html and reproduces 30px versus 16px padding before
the correction. A general-sibling selector applies the intended padding; both
status cases and keyboard/overflow checks pass without relaxing any threshold.

## Downstream native fixture corrections

On `a5284a3`, the complete Workshop application test now passes at **1693px**;
Restyle passes both platforms, and all Linux privacy journeys pass. The next
Workshop smoke step assumed Make reopened an untouched look gallery. It now
waits for recovery, explicitly chooses Anime character and opens Change look
when a look is already selected. No recovery bytes or model-link assertions
are removed. The earlier finder journey and this Models journey share saved
Make preferences; navigation alone must not erase them.

All 24 Windows private-recovery behavior checks passed, but the fixture's final
error gate counted `ConnectionAbortedError` (WinError 10053) during a cancelled
read-only estimate response as a handler defect. Match the creation driver's
existing disconnect classification; retain the event in `client_disconnects`.
Two actual-handler tests reproduce this missing classification and verify that
ValueError, RuntimeError, other OSError and TimeoutError still fail the gate.
Native smoke and both privacy platforms remain required on the final head.

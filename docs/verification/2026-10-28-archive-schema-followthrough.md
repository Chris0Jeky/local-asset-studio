# Archive integration follow-through — 28 October 2026

## First published source

PR #1681 head `f0d475026793418f605d80e0f0b6103389317fca`, tree
`c12a159229492327e66defcefaf5dd307d88349e`, passed exact-source Linux native
Archive qualification (24 checks), actual SDK/stdio tests and focused contracts
in run 40788141960. These are implementation evidence, not final-head approval.

Broader PR CI identified two integration assumptions; neither is waived.

## New cropped figures start active

Windows runtime job 123167120133 failed the deliberate schema-drift guard:
`archived_at` was not in the reviewed list of fields left to Workspace defaults.
The same assertion failed locally. The decision is explicit: a newly created
figure crop starts with NULL Archive state, even when its source is archived.
Derivation is new active work; it must not unarchive the parent or inherit the
parent's independent organization decision.

The strict schema equality remains. Its reviewed default list now includes
`archived_at`. A new production-Workspace integration test archives a sheet,
creates a crop, and verifies active child paging, archived parent paging,
unchanged parent metadata/original bytes, direct lineage and no generation.
All 14 addressable-figure tests pass locally after reproducing the guard failure.
No figure storage or crop implementation needed changing.

## Observe the complete Library before asserting it is empty

Asset detail job 123167119945 passed the 48 basic detail, 19 reload, 32 metadata
and 25 Workspace checks, then failed LIB-39's whole-Library empty assertion.
It selected All sources but left the new Archive filter at Active. A bounded
active-only empty page cannot establish that no archived assets exist.

The same LIB-39 failure reproduced in the explicitly limited inert driver.
The fixture now selects Active & archived using the actual control before
waiting for its query and observing the synthetic empty state. It restores the
ordinary active view before the unrelated selection/review journeys. Its existing
Make/import wording, primary action, file-chooser and subsequent selection
assertions are unchanged. The application continues to distinguish a filtered
empty view from a whole-Library empty state; no runtime behavior was relaxed.
All 43 Library checks pass in the inert driver after the correction; that remains
explicitly limited transport/storage evidence, not hosted native qualification.

Fresh exact-head full-suite, native Library and Linux/Windows Archive/runtime
qualification remain required. No model runs, owner media, workstation changes
or human creative/licensing acceptance are established by these corrections.

## Independent Archive/Trash wording in the recovery inspector

Both native lifecycle jobs in run 40788365638 reached LIFE-03 and rejected the
old `Active now` label. The inspector deliberately says `Not in Trash now` so
that an archived asset is not misleadingly described as active work. The old
assertion failed in the inert driver too. The fixture now creates an archived
live target and an archived trashed target through the real Workspace owner,
then verifies their exact per-ID headings separately from missing and unarchived
states. The ordinary active page correctly has nine rows; all twelve retained
IDs remain accounted for in read-only inspection. All 20 inert checks pass,
including every existing no-write, export, keyboard, late-response, foreign-scope
and historical-receipt assertion. Native platform gates remain required.

## Local full-suite disposition

The initial tree completed 6,348 tests in 1,049.699 seconds with 54 explicit
skips, one known figure-schema failure and one multiprocessing readiness error
in `test_backend_state` (the `reserve` subprocess did not signal within five
seconds). The identical readiness test passed standalone in 1.961 seconds.
Its runtime owner and fixture are unchanged by Archive; this is not proof of a
specific timeout cause. No timeout was increased or exception ignored. The
complete initial run is failed evidence; hosted final-head full-suite approval
is still required. The lifetime shutdown reported no retained non-daemon thread
or active child process.

## Strict read timestamp consistency

Self-review found that bounded HTTP/SDK summaries accepted a negative Archive
timestamp while the recovery inspector and editor refused it. Both actual
read-owner and strict-client regressions reproduced the inconsistency with -1.
The two read boundaries now require a nonnegative finite Archive timestamp,
retaining zero as archived and omission as the legacy active summary. No general
created-at or Trash timestamp contract changes. The original negative fixtures
now pass, as do all 238 asset tests locally.

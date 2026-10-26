# Refused exact retries retain recovery

Refs #393 and #204. Child of #720; no server metadata protocol changes.

An HTTP refusal describes one attempt, not whether an earlier attempt committed
before losing its reply. The existing detail/library handlers cleared pending
commands on generic 4xx responses, destroying the identity needed to inspect the
original result. Missing-target conflicts also removed exact target evidence.

The corrected paths retain the original request ID, body, expected revisions,
complete target set, selection and newer editable text. A missing target is not
silently dropped. The existing bounded journal and optional shelf remain owners;
there is no extra recovery store or automatic replay.

Use **Check save status** or **Check update status** to inspect the original
receipt. A confirmed historical receipt still does not prove today's lifecycle.
An unknown receipt remains unknown. To send different intent, inspect/export
first, then explicitly discard local recovery (close the detail editor first).
Discard does not cancel or undo server work. This conservative policy also keeps
validation refusals pending until that deliberate choice.

The original slice did not add durable refusal annotations or redesign valid
single-asset revision-conflict comparison/rebase. That existing path is unchanged when there
are no missing targets. The follow-up below qualifies annotation identity;
complete lifecycle focus paths, browser-menu zoom and screen-reader testing
remain #393 work.
#394 selected-File staging and #395 setup history remain separate.

## Retained explanation — 26 October follow-up

The detail and Library recovery panels now keep the last refused attempt's
explanation beside the exact pending command. Typing, reopening, reloading and
export/import through the optional shelf retain it. The explanation describes
one POST attempt; it does not establish whether an earlier attempt committed.
The label **Last recorded refusal** remains accurate if a later exact retry loses
its reply or returns HTTP 5xx, leaving that newer attempt unconfirmed.
An explicit status check remains a GET and does not replace that explanation
when the result is unknown or the read fails.

The optional `last_refusal` field belongs to the existing journal payload, outside
the immutable operation. It records a bounded literal message, HTTP status,
optional server code, request/Workspace identities and local observation time.
Only the current POST handler can add it to the same retained command. Stale
requests, observed Workspace changes, explicit foreign identities and GET
failures cannot create it. A failure to persist the explanation is reported
without implying that the attempted request was never sent.

Confirmation, verified conflict comparison or explicit session discard removes
the annotation from the current journal and panels. Historical shelf snapshots
remain inspectable until explicitly discarded, matching existing shelf behavior.
A different command cannot inherit the old explanation.

New code accepts earlier records without this field. Older open tabs use strict
shelf codecs and can refuse a shelf containing the new field; their retained raw
bytes are preserved. Reload those tabs onto the current application before
continuing device checkpoints. Unknown annotation versions or invalid fields
are refused without silently dropping the evidence.

The [retention qualification](../verification/2026-10-26-recovery-refusal-retention.md)
records the causal tests, executed native journey and remaining accessibility
acceptance. No screen-reader session or browser-menu interaction is claimed.

## Proof

### Original retention correction

The original run of
`python -m unittest discover -s tests -p test_asset_recovery_refusal.py -v`
executed 20 actual-editor cases: nine 4xx status classes for each journal slot,
plus missing-target preservation. All 20 failed on the unchanged #720 modules and
passed after the correction. Reload plus GET-only receipt recovery was included.

The original `python tests/asset_recovery_refusal_browser.py` ran 12 native browser
assertions against actual HTTP handlers and temporary SQLite: committed response loss, a
subsequent pre-commit 403, unchanged exact body/targets, explicit GET recovery,
newer typing/selection, original-file hash and JavaScript errors. The 390px
screenshots are synthetic. `--inert` substitutes storage/transport and is not
native-origin proof. The dedicated read-only workflow checks out the exact head
on Ubuntu and Windows. No private media, model or HUMAN_TODO decision is included.

### Retained-explanation follow-up

The refusal wrapper also executes `tests/asset_recovery_annotation.cjs` for strict
journal/shelf validation and exact-body annotation updates. The native browser
fixture now executes 32 assertions across detail and Library: held refusals,
newer focus and typing, a later lost reply with historical refusal wording,
reopening/reload, native checkpoints, export into a fresh tab after clearing
storage, inspect-first import, restoration, one explicit GET
confirmation, and separate current-versus-historical cleanup. The original
complete-command, selection and original-media protections remain asserted.
`--inert` executes a smaller 22-assertion component/transport flow and does not
establish native persistence, reload or shelf round-trips.

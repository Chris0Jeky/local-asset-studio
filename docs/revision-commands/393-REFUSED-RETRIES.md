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

This slice does not add durable refusal annotations or redesign valid single-asset
revision-conflict comparison/rebase. That existing path is unchanged when there
are no missing targets. Full error-envelope identity qualification, all lifecycle
focus paths, browser-menu zoom and screen-reader testing remain #393 work.
#394 selected-File staging and #395 setup history remain separate.

## Proof

`python -m unittest discover -s tests -p test_asset_recovery_refusal.py -v`
executes 20 actual-editor cases: nine 4xx status classes for each journal slot,
plus missing-target preservation. All 20 fail on the unchanged #720 modules and
pass after the correction. Reload plus GET-only receipt recovery is included.

`python tests/asset_recovery_refusal_browser.py` runs 12 native browser assertions
against actual HTTP handlers and temporary SQLite: committed response loss, a
subsequent pre-commit 403, unchanged exact body/targets, explicit GET recovery,
newer typing/selection, original-file hash and JavaScript errors. The 390px
screenshots are synthetic. `--inert` substitutes storage/transport and is not
native-origin proof. The dedicated read-only workflow checks out the exact head
on Ubuntu and Windows. No private media, model or HUMAN_TODO decision is included.

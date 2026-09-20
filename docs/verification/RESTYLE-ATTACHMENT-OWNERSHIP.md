# Restyle attachment ownership

The Create state owner keeps attachment intent separate from lineage. A board role holds
its `parent_asset` on the reference record. A distinct continuation source holds its
`lastReference` claim in `parentByInput`. Clearing or replacing a role releases only the
role's claim; it must not release the still-attached named source.

## Deferred attachments

`references.js` owns a transient token for each reference record. Both local uploads and
library copies acquire it before staging bytes. A response can apply only while its token,
record identity and reference epoch still match. A newer request for the same slot wins
regardless of completion order. Resetting, clearing or reordering invalidates older intent.
Editing wording or controls is not a reference-attachment transition and does not cancel
an otherwise current board copy. Independent slots may complete independently.

Tokens never appear in drafts, server requests, `parentAssets`, or the readiness projection.
The existing `referencePending` count remains the readiness signal. Every completed or
failed attachment releases its own pending count; a reset owns resetting the old epoch.
No attachment path submits generation.

The one-slot second-picture chooser retains the native `File` and its choice while a
handoff is being reviewed. Refusing to open, failing to read source context, or cancelling
the modal leaves that choice recoverable. Successful Prepare applies a new continuation,
which clears the previous choice through the existing preset transition. Switching the
handoff task deliberately discards the carried role and still announces that decision.

## Reproduce without models

```sh
node --test tests/reference_attachment_races.cjs tests/workbench_handoff_guards.cjs
python -m unittest discover -s tests -p 'test_*handoff*.py'
python -m unittest discover -s tests -p 'test_reference_attachment_races.py'
python tests/restyle_ownership_browser.py --out .runtime/restyle-ownership
```

The browser command uses the actual Create shell with synthetic APIs. Where native
navigation is policy-blocked, add `--inert` to use explicit test storage and API transport.
That mode does **not** validate native origin/storage, media serving, or model execution.
It does exercise real DOM File inputs, modal/cancel behavior and the production handlers.
The JSON report and screenshot are local `.runtime` evidence, not generated artwork.

The browser check also distinguishes two dialog cases: calling `showModal()` again on an
already-modal dialog is accepted; calling it on a dialog opened modelessly throws
`InvalidStateError`. The latter is surfaced without consuming the second picture.

## Issue scope

This slice addresses the remaining attachment behavior in #606 (items 2–4) and the related
same-slot upload/copy race. The saved-setup named-input fix from #588 remains intact and
is exercised by the existing frontend handoff and continuation parent-claim contracts.
It does not qualify models, change Restyle routes, make boards optional, or settle the
owner's aesthetic choices in #343, #351 and #357. #610's shared readiness projection
remains authoritative; this is not another reference-readiness model.

## Availability observations

A pending saved-reference check is an observation, not permission to change a newer
attachment. It captures each record's identity, filename, content hash and current
attachment intent. A newer check supersedes earlier checks on that record. Both successful
and failed responses apply only to observations still current in the same reference epoch.
No observation tokens are persisted or added to the readiness projection.

An obsolete failure must not mark a newly uploaded or copied image missing. Conversely,
a current missing-file result, hash mismatch or failed check still blocks readiness for
that filled record. Empty optional positions do not become missing files on transport
failure. The check releases its own pending count without interfering with a later reset.
These cases run through the real reference owner and the shared readiness projection in
`tests/reference_restore_observations.cjs` (also discovered by the Python suite).

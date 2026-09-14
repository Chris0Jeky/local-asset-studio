# Bind the live Krita dependency set to protected preparation

Maintenance for #225. The correction concerns upstream provenance, not the
native pixel adapter's existing source/result and unsaved-document checks.

## Cause and architecture

Previously a request included a freshly discovered list of dependencies, but
nothing in its pinned native plan fixed which entries had to be present.
Removing the request list after changing an upstream file therefore bypassed
that file's freshness check. A valid hash for each *listed* entry did not prove
that the list was complete.

Move the existing transitive artifact traversal to
`scripts/character_krita_dependencies.py`. Protected `_expected` preparation
now records the canonical `live_dependencies` manifest in `native-plan.json`.
The request builder recomputes the protected plan and requires exact equality,
then copies the bound manifest through the existing local-data interface. It
does not recollect the closure a second time after that comparison.

The stdlib-only native adapter validates at most 256 exact absolute local
path/SHA-256 records, rejects malformed/duplicate records, and canonicalizes
order. Before any live intent, document change or proposed layer, import
requires the complete request set to equal the prepared set and verifies the
current bytes of every bound entry. Sorting does not adopt filesystem aliases
or make request labels executable. Existing path, document-revision, buffer,
no-repeat and comparison checks remain in place.

This is integrity against an edited *request*. Local package files remain
cooperative trusted inputs; someone who can rewrite both the package and its
claimed hash is not authenticated by hashing. Nor does a check lease the
filesystem against later mutation. No new lock, journal, queue, schema migration
or native execution mechanism is introduced.

## Compatibility and operator recovery

Legacy file-based native packages remain readable and revalidatable: execute
recomputes their original shape without retroactively granting live authority.
A package lacking `live_dependencies` is **not accepted for live import**. Do
not edit old package bytes or delete retained intents to retrofit or replay it.

Use the existing commands in [the session runbook](../character-consistency/KRITA-DOCUMENT-SESSION.md)
to prepare a new native package in a new output directory from the still-valid
protected plan/current document/bundle/result, then create a new request for
that package. Changed dependencies require their normal upstream review and
preparation; this fix does not authorize regenerating candidates. A changed or
reopened live document still needs the existing fresh capture/session process.

Installing the new extension remains explicit. Its content-derived package
name changes when the adapter changes; no installed user files are patched by
this repository change. The fixed mechanics/proof fixtures declare an empty
manifest only because they have no protected-edit upstream closure. Real
protected preparation records the full closure.

## Tests

Initial corrected regression run against unchanged code: 11 methods,
**10 failing assertions/subtests**; valid-control cases already passed. The
first fixture attempt accidentally exported imported TestCase classes and
produced a missing-key error; its log is retained, but not used as the causal
regression count.

Final new suite has **14 methods**: removal, substitution, rebound hashes,
extras/duplicates, malformed/oversized manifests, builder refusal, current-byte
verification, stable ordering, valid pixels, full real protected closure,
default argument behavior, legacy reading and legacy file-execute validation.
The execute test stops at a mocked install boundary; it does not launch Krita.
All **44 existing/new Krita contract tests pass** locally. The existing Windows
character-edit lane now runs this group as well, with integration source paths
included in its triggers.

```sh
python -m unittest discover -s tests -p 'test_character_krita*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

## Reconciliation and verification environment

Final independent-branch full suite: **1,707 run, 1,691 passed, 16 skipped, zero failures/errors**, 115.546 s. Repository validation passed **66 graphs/bindings, 121 pins and 86 LoRA names**.

Inspected main `3d3135a17811d2e4846ada05aae35e06f60d92f4` / tree
`b34502d889ba5ffc356eb74b2ec15de8a498fd76`. The reconstructed tracked
source matched that tree before editing. Existing open reference-byte,
snapshot-publication, HTTP-framing, library/shortlist and mixed-batch/schema
work was inspected; this slice does not replace those implementations.

Unchanged baseline: **1,693 tests, 16 skipped, no failures/errors**, 114.044 s.
Local environment: Linux, Python 3.13.5, Node 22.16.0, Pillow 12.3.0.
Existing Pillow deprecation and exit-time socket warnings and deliberate
fault-injection diagnostics remain visible. Skipped cases are unverified,
not counted as executed passes. Hosted CI is a separate gate; final-head
results are recorded in the PR rather than presumed from a workflow file.

## Evidence and rollback boundaries

No native Krita application, menu, installation or owner document was exercised
here. Existing native proof records are historical evidence for their exact
recorded code, not acceptance of this changed adapter. Broader #71/#65 native
and creative acceptance remains open. No model/runtime/configuration change,
HUMAN_TODO decision or art/rights approval occurred.

Reverting restores the previous manifest behavior. New plan files should not
be rewritten for an older adapter; preserve them and use version-matched code
or the established new-package workflow.

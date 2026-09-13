# Readiness review corrections

PR #168, 13 September 2026. Supplements [the requirement contract](../MODEL-REQUIREMENTS.md)
with review and captured-browser findings; this is not workstation/model execution.

## Invalid occupied destinations

Review of initial commit `919fa51` correctly identified that `present: false` merged
an absent path with an existing empty file or directory. Passing that false value
into source eligibility could offer Install for a target the installer would only
attempt to verify, not replace.

The read-only file observation now also returns `occupied`: true for an observed
entry, false for an absent entry, and null for unresolved/inaccessible locations.
When `occupied` is true but `present` is false, the dependency projection suppresses
Install and instructs the operator to inspect the existing entry before choosing
a replacement. Nothing is removed, moved, repaired, downloaded or adopted.
An ordinary nonempty file remains present (not content-verified), and a genuinely
absent sourced safetensors target retains its normal installation eligibility.
The same per-observation cache carries both fields; no extra scan/hash is added.

Four tests in `test_preset_model_occupied.py` exercise actual empty files, directories
with retained children, absent targets and explicit fixture changes across fresh
observations. They pass locally together with the original 23 new tests and the two
HTTP cases below: **29 new ordinary tests** in this PR. Final hosted results are
recorded on the PR by head.

## Per-preset exception review

The second review suggested that catching ValueError no longer catches StudioError.
That claim is refuted by the actual declaration in `app/server.py`:
`class StudioError(ValueError): pass`. No production exception change is necessary.
Two added real-Handler HTTP regressions in `test_preset_model_health_errors.py` delete
or invalidate one actual catalog graph after Studio construction. Both prove
`graph_for` raises StudioError, `/api/health` still returns HTTP 200 with the broken
preset's diagnostic, and an unrelated healthy preset remains unblocked. Both tests
pass on the existing catch, with no queued job or model request. The finding is
answered with that evidence rather than redundant production code.

## Visually separate explanations

Hosted Chromium initially passed functional desktop/390px checks, but inspection of
the actual screenshots exposed adjacent inline small-text elements reading as one
concatenated sentence. `dependencyMarkup` now inserts a line break before its
installation explanation. The browser regression additionally compares actual DOM
bounds to require the second explanation to start below the first on both widths.
Local Node contracts and compilation passed; the final hosted screenshot artifact
is the visual proof, not a local-browser claim (local navigation is blocked).

The first Windows failure was a test-only default-codepage read of the UTF-8 catalog;
all three repository fixture reads now specify UTF-8. Production checks were not
relaxed. The review corrections do not alter source permissions, format support,
backend switching, submission ownership, human decisions or any installed model.

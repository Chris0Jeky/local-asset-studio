# Wan readiness from effective controls — maintenance pass 2

## Scope and reconciliation

Fixes #181. Based on inspected main
`61a8c4e16b8e64b8bdea5a121bec71f2b0758cb8`, tree
`c7e1c8e0857661ce614ba7dd635a4de2beb90062`. Existing Wan admission in
`app/wan_capacity.py` already blocked unproven ordinary-decoder shapes before
job creation; this change does not relax that guard or certify a new shape.

## Reproduced mismatch

The browser used a selected mode's static `execution_block` string. Consequently,
the default 81-frame T2V graph could display Generate enabled, a Balanced I2V
setup could stay enabled after enlarging it, and a Quality setup could remain
held after reducing it to the already-admissible dimensions/frame count.
Programmatic variants, named recipes and saved setups also needed readiness
recomputed after applying their controls, rather than waiting for a health poll.

## One server-owned envelope, a read-only projection

`wan_capacity.projection(preset, graph)` reuses the guard's dependency traversal.
It emits only `Wan22ImageToVideoLatent` ancestors of an ordinary `VAEDecode`, with
exact node IDs, relevant primary/companion bindings and integer graph literals.
It ignores disconnected nodes. Noninteger literals project as unknown so JSON
cannot silently make Python's invalid `1.0` latent batch become JavaScript's
valid integer `1`. The source graph is never modified.

The existing admission envelope is named once and shared by the guard and its
catalogue projection: **768 maximum side, 393,216 maximum pixels, 33 frames,
latent batch size 1**. These are current conservative policy limits, not a
universal performance or memory guarantee. Rotating width/height to match a
reference leaves this symmetric side/area predicate unchanged.

`Studio.catalog()` attaches the versioned data while already reading each
registered graph. No additional graph read, schema fetch, worker, cache, API or
state store is added. The browser overlays the current exact control bindings,
using existing mode/graph defaults when a field is empty, then evaluates that
projection. Unsupported/malformed projections show a readiness-unavailable hold.
Older responses without this projection retain their existing authored mode
holds; no checkpoint/family name is used to guess a decoder.

The UI's serial output count is not the graph's latent batch size. A three-seed
serial audition is therefore not rejected merely because its output count is
three. Runtime, schema, model, reference, continuation and worker gates remain
in effect alongside the capacity result.

## User-visible behavior

Typing, committed edits, named recipes, variants and saved setups recompute the
Generate state immediately. The mode explanation reflects the current shape,
not a stale mode-level hold. The existing workbench blocker surface consumes
the same function. Nothing submits during browsing or applying controls.

| Current setup | Capacity result |
| --- | --- |
| T2V default or 81-frame variant | Held |
| T2V Short motion study, 33 frames | Admissible, other readiness gates still apply |
| I2V Quick / Balanced within the existing envelope | Admissible |
| Balanced changed to 81 frames, a side over 768, or area over 393,216 | Held |
| Quality reduced to 512×768, 33 frames | Admissible |
| Empty field under a long Quality mode | Falls back to the long mode and is held |
| Unknown shape, invalid latent batch or unsupported projection | Held |

Tiled decode is outside this ordinary-decoder contract; absence of this hold
must not be described as tiled-decode certification or improved art quality.
The server rechecks actual prepared graph inputs before dispatch regardless of
what the UI shows.

## Verification

Four new unittest methods verify the actual `Studio.catalog` projection,
companion bindings/dependency closure/nonmutation, integer-only JSON behavior,
and actual shipped JavaScript handlers. The Node group runs 15 scenarios,
including ten real graph/control cases compared with Python's authoritative
guard, plus immediate edit/variant/recipe/saved-setup and malformed-data checks.
These scenarios are contained within one unittest method, not additional tests
in the full-suite count.

New tests failed on unchanged main. Subsequent targeted red/green checks proved
the saved-setup refresh and malformed/type-erasure cases before their fixes.
Existing server admission regressions remain in `tests/test_wan_capacity.py`.

```sh
python -m unittest discover -s tests -p 'test_wan*.py' -v
python -m unittest discover -s tests -p test_frontend_handoffs.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
python tests/wan_capacity_browser.py --out .runtime/wan-capacity-browser
```

Final local full suite: **1,493 tests, 15 skipped, zero failures/errors**, 91.901
seconds (Linux, Python 3.13.5, Node 22.16.0). The focused Wan suites run 11 tests.
Untouched main: 1,489 tests, 15 skipped, no failures. Existing Pillow deprecation
and exit-time socket warnings remain visible.

The existing synthetic browser fixture now derives capacity data with the same
production projector. Its native driver covers 1440px and 390px, keyboard mode
changes, manual overrides, T2V variants and programmatic setup/recipe imports.
It records exact source hashes, screenshots, page exceptions and forbidden
mutation checks. The existing Preset model readiness workflow runs the contract
suites on Linux/Windows and the browser driver on Linux; no extra persistent
service is introduced.

Local Chromium launched, but navigation was blocked by the sandbox's
`ERR_BLOCKED_BY_ADMINISTRATOR` policy. No policy bypass or local native-browser
pass is claimed. Hosted native receipts are a separate gate; consult the PR's
final verification comment. No inference, workstation GPU, real source upload,
model download or subjective acceptance was performed.

## Rollback

Revert the projection and UI consumption together to restore the old mode-level
readiness display. Server admission retains the same envelope. There is no data
migration, changed generation default, stored-state rewrite or runtime restart.

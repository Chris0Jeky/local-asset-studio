# Repair Studio implementation plan

> For agentic workers: implement one reviewable slice at a time using the available executing-plans or subagent-driven-development workflow. Read the linked specification and live repo instructions first. No live inference is implied by these tasks.

**Goal:** obtain accepted repaired assets through explicit scope, native/shared execution and measured bounded strategies.

**Architecture:** extend current Workspace, character-edit bridge, Production, Review Desk and native adapters. Use the offline v0 checker as a design fixture, not an executable plan or replacement service.

**Tech stack:** Python 3.12+, existing Pillow/stdlib/SQLite services, existing plain JavaScript UI and qualified local ComfyUI/native applications.

**Spec:** [ARCHITECTURE.md](ARCHITECTURE.md), [CONTRACTS.md](CONTRACTS.md), [RELIABILITY.md](RELIABILITY.md).

## Global constraints

Keep one writer per checkout, loopback-only service, explicit Start, retained prompt/request IDs, no unknown replay, and no installed package/model/runtime modification. Preserve HUMAN_TODO and existing campaign identities. Use current repo proving commands. New artifacts have new paths; no source overwrite. Ready-for-review PRs; partial broader issues use references, not closing keywords.

The named functions below are proposed interfaces for their implementation slices, not functions already shipped by this planning PR. Keep them stateless where described. Reinspect live source before editing, especially the concurrent changes in RECONCILIATION. Do not bind to stale line numbers.

## Programme map

| Milestone | Deliverable | Issues / prerequisites |
|---|---|---|
| R0 | Architecture, declaration checker and failure matrix | This PR, #243; no inference |
| R1 | One accepted scoped repair through existing owner | #244 → #245 → #248 + #251; #257 throughout |
| R2 | Clutter, matte and reviewed geometry routes | #246 and later #248 adapters |
| R3 | Generic sheets and coupled subject contacts | #249; layout part of #244/#256 |
| R4 | Bounded strategy changes and full agent parity | #250; expanded #251; reuse #65/#66/#123/#178 |
| R5 | Qualified finishing/export and effort evidence | #256/#257; existing #23/#24/#72 |

No calendar dates are committed. Each milestone must show its user outcome, not merely merged infrastructure. Segmentation, another model and autonomous critique are not prerequisites for the first useful hand repair.

## Task 1 — Explicit normalization and exact panel intake (#244)

Files: extend `scripts/character_media.py`; add `tests/test_repair_intake.py`; update existing character-media docs and fixtures. Reuse existing Workspace publication and reference capture rather than adding a store. Coordinate #234/#235 before touching shared byte/publication seams.

Interface: proposed `normalize_repair_png(encoded: bytes) -> tuple[bytes, dict]` returns a new PNG plus a normalization receipt; `extract` continues consuming a reviewed manifest of normalized-source boxes. The initial helper can support bounded single-frame RGB/RGBA PNG and explicit EXIF/tRNS normalization; other formats use a separately declared intake adapter.

- [ ] Write actual-byte tests for all eight EXIF orientations, RGB+tRNS, ordinary RGBA, hidden RGB, unsupported bit depth/profile, corrupt/oversized input and no source mutation.
- [ ] Run `python -m unittest discover -s tests -p 'test_repair_intake.py' -v` and record missing-feature failures.
- [ ] Implement bounded decode and explicit source/derivative facts. Do not reopen a mutable path for geometry after hashing another read.
- [ ] Extend reviewed panel manifests with stable instance/layout roles while retaining current exact crop behavior. Test arbitrary panel counts/aspects and crossing artwork; no automatic segmentation.
- [ ] Run intake plus existing character-media tests and full suite/validator; open a PR with exact synthetic output receipts.

Example first regression, using a real Pillow buffer rather than a fake decoder:

```python
from io import BytesIO
from PIL import Image
from scripts.character_media import normalize_repair_png

buf = BytesIO()
image = Image.new('RGB', (13, 7))
exif = image.getexif()
exif[274] = 6
image.save(buf, format='PNG', exif=exif)
original = buf.getvalue()
normalized, receipt = normalize_repair_png(original)
assert receipt['source_size'] == [13, 7]
assert receipt['normalized_size'] == [7, 13]
assert original == buf.getvalue()
with Image.open(BytesIO(normalized)) as decoded:
    assert decoded.size == (7, 13)
    assert decoded.getexif().get(274, 1) == 1
```

## Task 2 — Effective write and transform contract (#245)

Files: `scripts/character_edit_pixels.py`, current edit-plan/bridge preparation modules, new `tests/test_repair_pixel_transforms.py`. Preserve the existing no-resample contract/version and transparency tests.

Interface: add an explicit transform version to prepared bundles; use the v0 mathematical convention only when the real resampler/native adapter proves it. `prepare` emits source/work masks and transform evidence; existing `apply` consumes a source-bound candidate and revalidates them. Do not silently let v0 design proposals enter this path.

- [ ] Create real checkerboard/alpha fixtures and a deliberately misframed candidate; test all pixels rather than screenshot similarity.
- [ ] Implement explicit scale/padding/filter receipts, effective support after feathering and canonical-to-native mask conversion.
- [ ] Reconstruct expected prepared pixels during apply, then compare exact source retention. Reject mask/protection overlap, writable padding and candidate shape/profile changes.
- [ ] Test odd sizes and fraction rounding, four corners and pixel centres, edge support, stale source, changed transform and no-op. Run `test_character_edit*.py` plus the new transform module and full checks.
- [ ] Publish the synthetic proof and one authorized real repair only when a live allowance exists; otherwise record mechanical-only completion.

Executable geometry regression already supplied by this PR:

```python
from scripts.repair_proposal import transform
r = transform([100, 100], {'box': [3, 5, 10, 14], 'scale': [3, 2],
    'padding': [2, 1, 3, 1], 'alignment': 1})
assert r['resized_size'] == [11, 14]
assert r['work_size'] == [16, 16]
assert r['resampling_performed'] is False
```

This checks declared arithmetic only; the new media tests must prove the actual pixel path.

## Task 3 — One qualified candidate route (#248)

Files: `scripts/character_edit_bridge_plan.py`, `scripts/character_edit_bridge_io.py`, `scripts/character_edit_bridge.py`; registered catalog/graph files only for a deliberate new variant; `tests/test_repair_adapter.py` and current bridge tests.

Interface: current Prepare → Stage → Start → Status/Collect → Compose, with versioned geometry/mask capability. Begin with existing Qwen or matched-style route; do not require every model family. Continue using one context composition slot and supported reference slots exactly as authored.

- [ ] Add failing native-template tests for wrong slot order, unsupported mask/alpha/profile, incompatible patch, auto-crop mismatch, stale graph and off-grid output.
- [ ] Bind the prepared contract to one exact existing model/template and current resource preflight. Unsupported stays blocked rather than silently converted.
- [ ] Exercise actual Handler/Production/Workspace transport with only neural output substituted. Prove one Start, retained identity on lost reply and no writes on preparation.
- [ ] Run bridge/pixel/recovery suites and live schema validation only against an already selected runtime when authorized.
- [ ] Record one truly useful private hand repair with source/candidate/composite and all failed attempts; no generation occurs merely to mark a catalog flag green.

Acceptance assertion for a controlled full-context overwrite candidate: the existing compositor's changed pixels are contained in the effective write mask, the source face is byte-identical and the candidate remains unreviewed until actual inspection. A passing overwrite fixture alone does not complete R1.

## Task 4 — Thin guided journey and shared commands (#251)

Files: existing `app/server.py`/Review Desk/Production routing, `app/static/app.js` or a focused new `app/static/repair.js` module following current loading conventions, existing SDK/MCP command adapters; `tests/test_repair_journey.py` and actual-browser driver in the existing suitable lane.

Interface: one revisioned repair document projected through inspect/propose/preview/request/observe/collect/compare/accept/revert semantics in UX-AND-AGENTS. Use current service error/idempotency conventions; the names are not a new API implemented here.

- [ ] Reproduce a source/mask change during pending preview and a lost Start response in the actual shell.
- [ ] Add source/target/scope preview and exact route explanation, then reuse existing explicit Production Start and review controls.
- [ ] Bind native selection/import to the existing revision guard. Missing native support presents a manual handoff, not fake success.
- [ ] Verify zero generation on navigation, useful focus/keyboard behavior, 390px and 200% zoom, restored draft and retained unknown command.
- [ ] Compare UI and headless effective-input identities; publish the real one-subject journey before expanding automation.

## Task 5 — Selection, matting and ambiguity (#246)

Files: extend actor/reference artifacts and native selection projection; introduce a narrow adapter module only where needed, with `tests/test_repair_selection.py`. Reuse helper scheduling #35 and critique owner #66.

- [ ] Start with reviewed manual selection/visibility fixtures. Test identical instances, prop overlap, edge fragments and hair alpha.
- [ ] Qualify one optional point/box segmentation adapter with exact pins, then evaluate whether it reduces human effort. Do not install all candidates.
- [ ] Add fractional matting only for failed binary-edge cases; retain foreground colour/alpha and shadow distinctions.
- [ ] Require an explicit reconstruction branch for unseen completion and occluder removal. Show a specific clarification crop.
- [ ] Record actual selection effort and misses/spill independently from anatomical repair; run native/adapter checks plus full tests.

## Task 6 — Repeated instances and joint contact (#249)

Files: `scripts/character_edit.py`, bridge plan/pixel modules and current scene/layout contracts; `tests/test_repair_contacts.py`.

- [ ] Add failing two-instance/same-canon and hand-prop contact cases before changing contracts.
- [ ] Version instance/reference/contact records; reject swapped or truncated refs. Preserve local occlusion exceptions instead of forcing an invalid global layer order.
- [ ] Use effective-mask overlap and semantic dependencies to choose independent or coupled work. Treat overlapping patches as ordered new revisions or one shared candidate.
- [ ] Test disjoint composition order, overlap refusal, all contact participants and region coverage, and independent costume invalidation.
- [ ] Compare joint/sequential candidates under a separately authorized campaign, recording actual stage counts and contact review. Do not alter #72's design.

## Task 7 — Bounded strategy policy (#250)

Files: a small pure `app/repair_policy.py` is appropriate if existing policy code has no suitable home; extend `app/production.py` for per-case allocation within its current root. Tests: `tests/test_repair_policy.py` and existing Production transaction/recovery tests.

Proposed pure interface: `next_repair_action(observations: dict, capability_snapshot: dict, remaining: dict) -> dict` returns a proposal, pause or manual action, never performs IO or reserves a job.

- [ ] Test no-op, hidden anatomy, two same-class failures, unsupported geometry, zero credit and uncertain submission.
- [ ] Implement the deterministic transition policy with a recorded changed hypothesis; retain actual model/canon/scope diffs.
- [ ] Extend existing campaign transactions for per-case repair limits. Test simultaneous clients and restart with failures/unknown work consuming the same allowance.
- [ ] Add explicit finite analysis-call/time accounting and fresh #178 resource preflight. No background helper on reads.
- [ ] Evaluate total effort against current/manual baseline before enabling unattended progression. Human approval is never returned by the pure policy.

## Task 8 — Finishing and generic composition (#256)

Files: `scripts/character_media.py`, existing finishing/native export modules, explicitly registered upscale variants if needed; `tests/test_repair_finishing.py`.

- [ ] Write layout-only tests with mixed panel shapes/counts and typography layers; assert zero candidate requests.
- [ ] Replace the demonstration-only layout restriction with a versioned generic layout path while preserving legacy composition.
- [ ] Add accepted-master versus remaster derivative links and explicit pixel/filter/alpha/colour policies. Keep the original master intact.
- [ ] Test tile seams, thin lines, alpha halos, order and exact source placement; inspect final-size output and reopen supported native exports.
- [ ] Record draft/accepted/export-tested states separately; use #23/#24 for actual target compatibility.

## Task 9 — Qualification and closeout (#257)

Files: existing test lanes plus task-specific cases above; local private experiment records under existing ignored locations; redacted `experiments/curated/` evidence only when appropriate.

- [ ] Bind every R-* requirement to an actual fixture and evidence level before enabling its route.
- [ ] Freeze the approved pilot/holdout and budgets; separate paired degradation from natural defects.
- [ ] Execute only authorized cases; keep all failed/unknown/rejected outcomes and true prompt IDs.
- [ ] Report per-class accepted tasks, false acceptance, abstention, cost and cleanup effort; apply the predeclared release gate.
- [ ] Run `python -m unittest discover -s tests` and `python scripts/validate-repo.py`; retain logs and review unresolved claims. Check actual PR head/merge candidate, not a previous green run.
- [ ] Leave incomplete broader issues open and record remaining acceptance. No test result ticks HUMAN_TODO.

## Review boundaries

Each task ends in a reviewable PR with exact changed files, red/green or other causal evidence, focused checks, full checks when relevant, support limits and issue disposition. Read code and native contracts before installing optional dependencies. Stop expanding architecture when the next uncertainty can be answered by one bounded vertical-slice experiment.

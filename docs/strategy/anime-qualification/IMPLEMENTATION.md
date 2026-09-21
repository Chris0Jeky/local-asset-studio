# Integration delivery plan

**Goal:** turn the 15 September report into improvements to the existing accepted-asset loop, beginning with source-scope honesty rather than another model catalogue.

**Architecture:** keep the current Python service, ComfyUI graphs, Workspace, model library, Prompt Lab, resource observer and Experiment Lab. A source record describes the evidence behind advice; a resource pin describes the bytes that advice targets. Neither is execution or acceptance.

**Technology:** existing Python, JSON, unittest and browser modules; no new production dependency. Specification: [architecture](ARCHITECTURE.md), [qualification](QUALIFICATION.md), [knowledge crosswalk](EXTRACTION.md).

## Global constraints

Use #552 under #313/#14, not a new epic. Preserve HUMAN_TODO decisions, existing allowances, protected pixels and ambiguous-submit recovery. Keep general anime work independent of the parked #403 stack. No install, runtime restart, driver update, inference, source-art publication or model promotion is part of these software changes. Each implementation is independently reviewable and may stop after its demonstrated improvement.

## Slice 0: publish and reconcile the research

Files: this directory; `docs/strategy/README.md`; `docs/SETTINGS-KNOWLEDGE.md`.

- [x] Publish page-addressed claims, current divergences, source verification and the accepted-pack reading path.
- [x] Correct the stale statement that no Anima LoRAs are installed without overwriting historical results or changing a recipe.
- [x] Route each remaining requirement to an existing issue and name its smallest evidence-producing change.
- [x] Check relative links, recorded repository identities and source/profile distinctions.

This slice can be reviewed without accepting any proposed runtime, frontend or model change. Its review does not close #313 or imply that #552's implementation programme is finished.

## Slice 1: source scope in existing resource guidance

Files: `studio_workflow/guidance.py`; `tests/test_guidance_source_scope.py`; existing guidance documentation under `docs/bundle-studio/`.

Consumes: `guidance.validate_claim(value)` and `guidance.explain(preset, template, controls, kb, manifest, today=None)`.
Produces: an optional `source.scope` declaration in the existing KB claim and a normalized `source_scope` plus visible reason in the existing explanation. No second source store or endpoint.

- [x] Write a failing real-evaluator test: a legacy claim whose hashes match must report `source_scope == 'unrecorded'`, not exact-version qualification.
- [x] Add cases for `family`, `exact_version`, `local_workflow`, invalid/malformed scope, mutable or absent revision, source/hash mismatch, expired source, conflicting advice, detached return values and changed-context identity.
- [x] Extend the existing validator, accepting the optional scope only. Missing scope remains unrecorded; exact-version and local-workflow declarations require a content/commit pin or an explicit provider-version identity, not `main` or a retrieval date.
- [x] Append the scope explanation to existing `reasons` so the current UI renders it as text. Preserve resource applicability, conflict evaluation and all no-write/no-generation behaviour.
- [x] Exercise the actual CLI and existing HTTP/client contracts. Run focused tests, repository validation and the strict full-suite lifetime gate.
- [x] Publish the tested diff, record its head/checks and request review. Do not backfill old claims with invented source attestations.

Example acceptance:

```python
p, graph, manifest, kb = fixture()
report = guidance.explain(p, graph, {}, kb, manifest)
assert report['claims'][0]['source_scope'] == 'unrecorded'
assert report['claims'][0]['applicability'] == 'applies'
assert report['generation_submitted'] is False
```

The second assertion deliberately means *catalog pins match*, not *the source verified this version*. Scope is a declared evidence category, not automatic source authentication. Existing UI, CLI and HTTP share this evaluator.

## Subsequent slices, existing owners and acceptance

| Order / owner | Smallest useful change and files to inspect | Verification before widening |
| --- | --- | --- |
| 2 / #34, #144, #37 | Separate Aesthetic 1.1, Base 1.0, Turbo 1.1 and Base + turbo-LoRA configurations in `presets/settings-kb.json`, `research/prompt-studio/profiles.json`, `studio_prompt/compiler.py`, `app/settings_planner.py`. Preserve old saved profile revisions. | Exact positive/negative grammar; Aesthetic score-token diagnostic; wrong-base refusal; no universal Animagine grammar for Pony/Noob/WAI; conditional accelerated schedules do not enter unaccelerated grids; no changed prompt/controls without review. |
| 3 / #302, #77, #303, #307 | Extend existing `app/job_resources.py` receipts with attested model/configuration and deliberately established cold/warm/switch/cleanup state. Read `app/host_memory.py` and `docs/performance/` first. | Unknown remains null; manifest pins are not loaded-file attestation; changed listener invalidates observation; observer failure cannot relabel jobs; exact Qwen Q4+Lightning smoke on the operator's machine, then stop or continue under the separately authorized cap. |
| 4 / #21, #232, #35, #38 | Reconcile `studio_prompt/schema.py`, existing Reference Intelligence and setup handoff: costume/outfit vocabulary, source transforms, native slot projection and explicit take/ignore ownership. | Saved-brief compatibility; no silent role rename; four analyzed images cannot become four supported generator slots; wrong order/crop/source bytes and stale revisions refuse; no helper execution on import. |
| 5 / #444, #445, #446 | Finish source-bound pose import/overlay/Workspace persistence on the current Combine editor; inspect `docs/pose-control/` and current PRs before editing. Use the existing 48-cell planner for its own scope. | Confidence and unknown joints survive; original detector result retained; graph contract distinguishes RGB/depth/skeleton; no detector rerun on an already-rendered guide; role binding does not certify neural success. |
| 6 / #10, #37, #72, #257 | Bind the selected T01-T08 cases to existing finite campaigns and review outputs. Implement the explicit cell design in [QUALIFICATION.md](QUALIFICATION.md), not a new runner/database. | Deterministic cell IDs, no hidden batch members/warmups/repairs, rejected and uncertain outcomes retained, no cross-architecture seed-equivalence claim, hard constraints separate from independent visual review. |
| 7 / #243, #245, #248, #251 | Complete one masked repair through registered adapters and existing compositor. Start with the current measured route, then a matched Animagine comparator only when needed. | Final effective write support, alpha/hidden RGB, odd dimensions, protection overlap, candidate alignment, changed source/mask, no-op intended-change failure; real owner acceptance remains separate. |
| 8 / #65, #66, #72, #313 | Freeze an owner-selected canon, repeat the four-asset pack and reuse an accepted artifact. Preserve the pose-then-face route as a baseline. | Per-subject identity, expression/pose variation, protected derivative and lineage; owner time, rejected outcomes and two-pass cost included; no implicit canon from a generated favourite. |
| Conditional / #9, #14, #144 | Only after a measured gap: exact OmniGen2 offload, Illustrious, training or adapter candidate. Use existing acquisition and library paths; completed resume-download issue #356 is retained infrastructure, not newly seeded work. | Source and terms review, byte identity, base/control compatibility, isolated runtime preflight; decline acquisition when it does not answer the gap. |
| Parallel but independent / #118, #123, #539 | Task-aware guidance and a thin agent read/plan surface over the same commands. Coordinate open adaptive UX #549/#551/#556 without taking their proposed frontend stack as settled. | Browser 390px/keyboard and actual handler tests; source count and current readiness, not mockup capabilities; zero generation for inspect/preview; measure time and effort, not screenshot attractiveness. |

## Merge and maintenance rules

Review documentation first, then source-scope software independently. Follow with one selected blocker, not all rows at once. Recheck `main`, issue state, PR files and HUMAN_TODO before every implementation: this table is an ownership map, not a durable open-PR inventory. Use `Refs`, not issue-closing keywords, for partial slices. Retain rejected experiments and supersession links.

A slice is ready only with a stated failing scenario, changed production behaviour, focused regressions, applicable full/hosted gates and honest unverified boundaries. A documentation PR needs link/source checks; a passing software suite never supplies GPU or artistic evidence. Record failures before any test-environment repair, and distinguish a rerun from a new head.

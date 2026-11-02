# Agentic evidence lab: verification and implementation boundary

Date: 2 November 2026. Test environment: isolated Linux container, Python 3.13.5,
Pillow 12.3.0. This is not the owner's Windows/AMD workstation.

## Source and change identity

The supplied main archive identifies `9fa5083a88bebb6b678c880e37abe5745885ba18`.
Live LAS main was inspected at `84b66fba0da1b70be895caf8ec3831cb0a9055bd`.
The production articulated adapter and its tests were synchronized to that newer
Blender compatibility fix before feature verification. The new PR is based on the
live main tree, preserving its other documentation and unrelated work.

## Executed checks

| Check | Result | Scope |
|---|---|---|
| Research intake tests | 10 passed | Exact preservation, citation derivation, tampering, no evidence promotion |
| DCC evidence tests | 17 passed | Topology/pixels, missing views, camera mismatch, paths, hashes, pinned intent |
| Blender probe tests | 12 passed | Python API-shaped fixtures only; no Blender process |
| Programme/CLI tests | 6 passed | Validated catalogue, exclusive output, immutable intent, bounded status |
| Seeded study tests | 2 passed | Repeatable owned synthetic fixtures and diagnostic outcomes |
| Existing frontier tests | 30 passed | Existing atlas/planner unaffected |
| Existing articulated tests | 10 passed | Live-main adapter contract and Blender compatibility regressions |

Total: **87 focused tests passed**, including **47 new tests**. Test-first missing
feature and subsequent review-regression failures were retained before the passing
runs. A self-review caught and fixed mutable intent aliasing, false archive evidence
promotion and missing probe collection budgets. This was not an independent review.

The real offline `seeded-study` command also ran and retained its image/scene bundles,
implementation hashes, environment and JSON comparisons. All eight expected outcomes
were observed: unchanged control within declared tolerance; pixel, connectivity,
weight and omitted-part changes different; missing hold-out incomplete; changed
camera contract incomparable; tampered file refused. This is synthetic evidence of
comparison mechanics, not native geometry, render quality or critic calibration.

Both complete supplied research exports were imported and their archives reverified.
Original JSON bytes and original Markdown remain intact; readable Markdown and source
indexes are separately derived. Unresolved private-source citation tokens remain
visible. Archives are private; no complete report or character asset is published in LAS.

## Full-suite limitation

`python -m unittest discover -s tests -v` was attempted with a 600-second execution
cap. The final-code attempt exited **124 (timeout)** while executing
`test_spoken_brief_runtime.SpokenBriefTests.test_explicit_client_rejection_can_be_fixed_and_retried_without_uncertainty`.
The retained verbose log contained no completed `FAIL`/`ERROR` result before the cap,
but this does **not** establish a green full suite. An earlier intermediate-tree
attempt also reached the same time cap; neither is omitted or called a pass.
A longer full-suite run and hosted checks remain required before merge.

Focused logs, full-suite logs/exit codes, the synthetic study and source-integrity
receipts are included in the delivery artifacts rather than generated into the public
source tree. Repository validation and diff hygiene are run separately at publication;
the PR description records their actual outcome. No native or hosted result is inferred.

## Not implemented or verified here

The read-only Blender probe source exists, but its native execution on 4.5.13 or
5.4 Alpha `67c9bdddb88b` is pending. No HIP/HIP RT/EEVEE/Vulkan benchmark was run.
No ComfyUI generation, model inference, driver change, installation, private asset
transfer, camera/microphone activation or artwork modification occurred.

Controlled native rendering, full capture-contract production, target-aware GLB
identity mapping, texture-byte comparison, evaluated deformation/temporal checks,
native resource admission and app/MCP tool integration are **the next planned slice**,
not completed by the offline CLI. Budget fields in experiment plans are declarations,
not a live scheduler. The comparison never promotes a baseline or artistic acceptance.

Read [the next native parity plan](superpowers/plans/2026-11-02-dcc-native-parity.md)
before executing native work. Keep existing HUMAN_TODO decisions open; this pass does
not resolve art acceptance, target-engine availability or source distribution terms.

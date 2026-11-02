# Agentic evidence lab: verification and implementation boundary

Date: 2 November 2026. Test environment: isolated Linux container, Python 3.13.5,
Pillow 12.3.0. This is not the owner's Windows/AMD workstation.

## Source and change identity

The supplied main archive identifies `9fa5083a88bebb6b678c880e37abe5745885ba18`.
Live LAS main was inspected at `84b66fba0da1b70be895caf8ec3831cb0a9055bd`.
The production articulated adapter and its tests were synchronized to that newer
Blender compatibility fix before feature verification. The new PR is based on the
live main tree, preserving its other documentation and unrelated work.

## Original implementation checks (`af3306ca`)

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

## Independent review corrections

Review of PR #1911 at `af3306ca20ef1773731bd73d0cb942c60f393c1b` reproduced two
false matches while all 47 original new tests passed. The exact source tree was
`b3d3e6120db5e90b43b4dcd5f6451758ee460b89`. The PR head and discussion were
refreshed before implementing this follow-up; the reviewed source was unchanged.

1. An API-shaped RGB node changed its authored output from red to green, but
   the material records remained identical and `compare_scenes` reported
   `equal: true` with no changes. Material snapshots now record exposed output
   socket defaults as well as inputs, using the existing bounded, finite-value
   serializer. RGB and Value nodes are covered. No shader evaluation, animation
   authoring or broader node-state serialization was added.
2. Valid 16-bit RGB and RGBA PNGs with red samples 32768 and 33023 were both
   exposed by Pillow as 8-bit RGB/RGBA. Correctly hashed evidence bundles then
   reported `within_declared_tolerance` at zero tolerance. Comparison now checks
   the encoded sample depth before opening pixels. A bounded chunk-framing walk
   requires one leading 13-byte IHDR and refuses repeated headers, including an
   8-bit header followed by a 16-bit header. It neither decompresses chunks nor
   allocates their declared lengths. Existing byte, resolution, frame and pixel
   bounds remain in force. Unsupported evidence is refused; files are not
   converted or rewritten.

The test-first run of the two affected files ran 34 methods and reproduced
**15 failures across the five new methods**: missing output-value observations,
missing output-value budget refusal, truecolour depth reduction, leading/repeated
IHDR acceptance, and forbidden pixel decoding before refusal. The same 34 methods
passed after the fixes. Supported 8-bit RGB/RGBA controls still detect one-unit
sample changes; source bytes remain unchanged on refusal. Output defaults retain
the existing scalar-budget and non-finite-value checks.

The final focused set passed **92 tests with no skips or failures** on Linux,
Python 3.12.14 and Pillow 13.0.0: the five new modules now contain 52 tests, plus
30 frontier tests and both articulated modules' 10 tests. The source probe remains
stdlib-only; no Blender process or live engine was started. Repository validation
also passed with site packages disabled (`python -S scripts/validate-repo.py`):
98 graphs/bindings, 194 pinned assets, 167 LoRA names and 4,753 tracked paths.

These corrections do not qualify native Blender/Windows/AMD behavior or supply
the missing full-suite result below. They do not reverify private report archives
that are outside the public PR. Fresh hosted checks and integration against the
current base remain required before merge; owner artistic and distribution
decisions remain open.

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

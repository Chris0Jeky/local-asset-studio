# Coverage and verification — Volume VII

## Final delivery counts

| Material | New in this volume | Reused from prior volumes |
| --- | ---: | ---: |
| Completed instructional studies | 48 of 48 | 0 |
| Pending studies in this volume's queue | 0 | — |
| Generated reference sheets accepted for instructional use after agent review | 48 | 0 |
| Editable authored SVG diagrams | 48 | 0 |
| PNG rasterizations of those diagrams | 48 | 0 |
| Actual Blender render images | 74 | 0 |
| Selectable native cases | 43 | — |
| Neutral supporting cages | 1 new extended pose cage | 3 prior cages |

The PDF contains **126 landscape pages**. Full-resolution masters, all lesson/source records and verification receipts are in the complete archive. The three SVGs in this directory are byte-identical selections from the full 48-diagram set.

The accepted reference sheets contain **202 reviewed panels**; the diagrams contain **164 authored panels**. The lessons specify **240 causal Blender actions**. A multipanel sheet is one image. Diagram PNGs are derived rasterizations of the SVG originals, and embedded thumbnails, PDF previews and review screenshots are derivatives rather than additional original illustrations.

The generation log records **64 requests, 60 successful image returns, 48 accepted sheets, 12 retired returns and four rejected attempts with no image**. Retired returns and rejection reasons remain in the archive. Acceptance here means agent review for the documented teaching task; it does not imply owner art acceptance.

The accepted reference categories are **42 body concepts, five nonhuman material coupons and one articulated joint demonstrator**. Body-reference requests for **D18, D21, D25 and D26** were rejected and substituted; exact regional constructions and native examples remain. The full atlas report records the individual substitutions and their teaching limits.

The final reader passed **111 browser checks** and the comparison desk passed **90**. Their exact checks and artifact hashes are recorded separately from visual review. The PDF passed **1,048 automated checks with zero errors**, and all **126 pages** were visually reviewed. The source register contains **32 primary anatomical or official software sources**.

## What the native lab proves

The lab was built and rendered in Blender 5.4.0 Alpha, commit `50d477803fa8`. It contains ten scenes, 19 five-bone armatures and 43 editable case objects. The file retains 146 shape-key blocks including Basis, of which 103 are non-Basis blocks; these totals include duplicated per-case editing sets and are not counts of unrelated anatomical forms.

The independent saved-file reopen checks all 43 source surfaces for one connected component, manifold edges, consistent winding, degenerate faces, loose vertices and nonadjacent triangle intersections. All pass. Evaluated source coordinates agree with the export within **1.6861 × 10⁻⁷ U**. It also checks cameras, normalized weights, the embedded/external helper, independent knee control, pelvis/hip counterrotation and contact proxy endpoints.

All 74 final PNGs pass chunk, CRC, decoded-scanline and Blender-decoding checks. All were visually inspected; selected medial roots, contact fields and profile corrections received enlarged review. One incomplete saved PNG was regenerated from the unchanged saved scene, with the original execution and repair records preserved. There were 74 initial native render operations and one repair operation for 74 accepted final images.

The 43 cases are selectable study endpoints. Contact baselines deliberately reuse newly authored cg04, as03 and cc03 envelopes at fixed local contact sites. No prior rendered image is reused.

## Geometric limits

`U` is the authored span from `(−0.5, 0, 0)` to `(0.5, 0, 0)`, not a human measurement. Shapes and angle presets are artistic choices.

The rig does not preserve total enclosed source volume exactly. The compact hinge measures **1.02574×** its rest volume and compact deep flexion **1.05018×**. Balanced hinge is **1.05310×**, versus **1.04431×** with correction disabled. Soft deep flexion reaches **1.11596×**. Loaded contact endpoints span approximately **0.99400–0.99865×** their own rest cage. Measurements include planar crop caps and precede display subdivision.

Contact examples prescribe displacement and show a rounded single-fingerpad proxy. They do not measure force, stiffness, relaxation, muscle activation or material response. Shoulder stubs are supporting crop surfaces, not an upper-arm/axilla demonstration. Full-character animation topology, foot IK, ground contact and collision simulation remain separate work.

## Evidence locations in the archive

| Record | Purpose |
| --- | --- |
| `COVERAGE-VERIFICATION.md` and `verification/production-counts.json` | Overall study/image/source counts and release gates. |
| `verification/browser-reader.json` and `verification/browser-desk.json` | Functional checks bound to the final reader and desk. |
| `verification/pdf-checks.json` and `verification/pdf-visual-review.json` | Automated PDF checks and agent visual inspection. |
| `native/native-index.json` | Accepted native cases, image hashes, units, volume measurements and download records. |
| `native/asset-manifest.json` | 95 native delivery and verification file hashes. |
| `verification/native-execution.json` | Executed build, source hashes and final export identity. |
| `verification/native-reopen.json` | Independent saved-file geometry, controls and PNG checks. |
| `verification/native-visual-review.json` | Agent inspection of all 74 final native images. |
| `verification/native-render-repair.json` | Incomplete-PNG recovery with unchanged scene and geometry. |
| `research/blender-version.md` | Exact executed build and documentation access limits. |
| `research/source-register.json` | 32 canonical anatomical/software URLs with supported claims and limits. |

Generated, inspected for teaching defects, owner-accepted as art and licensed for a proposed use are separate states. This handoff asserts the recorded execution and agent review only. Existing owner choices in [HUMAN_TODO.md](../../../../HUMAN_TODO.md), including Studio art direction/replacement artwork, parallax usability and the island default switch, remain open; this course handoff does not answer them.

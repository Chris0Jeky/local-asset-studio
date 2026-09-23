# Status by goal — 14 September 2026

The one page that says where each owner goal stands. `CURRENT_STATE.md` is the reverse-chronological
evidence ledger; this page is the view over it. Percentages are a coordinator's rough estimate from the
13–14 September assessment ([STUDIO-REVIEW-2026-09-13.md](STUDIO-REVIEW-2026-09-13.md)); evidence pointers are exact.
Three states stay distinct throughout: generated (a job completed), inspected/accepted (a human judged
the art), licensed (the terms allow the use). Update this page when a goal's state changes, not per PR.

| Goal | State | One-line summary |
| --- | --- | --- |
| G1 Workflows that genuinely work and are elaborated | ~65 % | Image lanes proven on this PC (63 of 66 graphs live-valid, 39 presets with completed jobs); video lane executes but fails inspection; per-backend validation missing |
| G2 Chosen images at baseline quality | ~60 % | All six baseline families executed with retained IDs; the brief's four steps and a posed full body that keeps the face exist (16 Sep), all unreviewed; zero accepted images; hands and feet unresolved; AniFox never ran |
| G3 Character sheets → figures, poses, in-betweens | ~35 % | Primitives proven (face/hand repair, upscale, Krita protected edit, Godot playback); no addressable-figure capability exists; in-betweens are research only |
| G4 UX that reflects the real work | ~72 % | Workflow-first IA is real and wired to ComfyUI; the owner's 14 Sep verdict ("pretty much unusable") drove seven merged UX PRs under #278; review loop now has a queue, shortcuts and bulk review but is still unused by the owner; no task family for sheet/figure/sprite work |
| G5 UI that works and feels good | ~55 % | 79 synthetic journeys pass; ten agent-driven use cases measured (fixture 10/10, live read-only 4/10, 4 dead ends ranked in UX-USE-CASE-MATRIX.md); the owner's first-hand statement is on record (UX-AUDIT-2026-09-14.md) and the next pass is the verdict (q-7) |
| G6 Modular workflow editing in the Studio | ~55 % | Revisioned documents, Steps, bundles, agent parity exist; edited graphs are not runnable by design (#122); dynamic ComfyUI inputs were mis-read (fixed in PR #262) |
| G7 Everything else | ~40 % | Runtime resilience strongest; video/Wan and voice weakest; #77/#89 crash root causes still open |

## G1 — Workflows that genuinely work

**Proven.** `python scripts/validate-live.py` against ComfyUI 0.35.0: 66 of 66 graphs checked, 63 pass; the three
failures are true local facts (AniFox checkpoint not downloaded; two HiDream presets whose nodes live on the idle
isolated 8192 backend). The live job store held 94 jobs, 80 completed, across 39 distinct presets. Elaboration is
wired, not decorative: six-slot LoRA chains, FaceDetailer face-then-hand passes, img2img polish with the 4-step
distill LoRA, one/two/three-reference Qwen edits, TRELLIS auto-cutout 3D, ESRGAN, Fooocus inpaint.

**The strongest routes** (job or prompt ID, output hash and a written inspection all retained): `wai`, `anime`,
`pony`, `noob`, `anima-artist-stack`, `krea-anime-atelier`, `krea-style-lab`, `krea-refine`, `anime-detail-fix`,
the four modular baselines (`cstati-v3-baseline`, `yumeflux-ilv1-baseline`, `janima-v1-baseline`, `anima-v1-baseline`),
`lineani-portrait`, `anima-portrait`, `krea-portrait`, `hunyuan-draft`, `trellis-rgba`, `trellis-auto-cutout`,
`h3-preview` (isolated backend), `hidream-o1-concept` / `hidream-o1-edit` (isolated backend). Timings are in
[ANIME-FANTASY-ATELIER.md](ANIME-FANTASY-ATELIER.md) and the curated folders under `experiments/curated/`.

**Not working.** Video: both inspected Wan 2.2 outputs failed (breakup from frame 1; mosaic smearing by frame 4) and
the canonical control died in VAEDecode after 995 s of sampling; only the synthetic decode-only probe succeeded
([WAN-DECODE-CAPACITY.md](WAN-DECODE-CAPACITY.md)). 27 presets have never produced a completed job, including every
masked-repair and most detail-pass variants.

**Fixed in PR #263.** The `verified` flag is now auditable: every verified preset carries an execution note and
the validator enforces it; `flux`, `sdxl` and `sdxl-variation` were flagged without any recorded run and are now
`verified: false`. Seven presets have completed live jobs but stay unverified because no inspection was written
(`anime-refine`, `anime-complete`, `lineani-environment`, `cinematic-lighting-*`, `qwen-1ref`, `wan22-i2v`).

**Next slice.** Per-backend schema validation: capture an `object_info` fixture per declared backend and validate each
preset against its own backend (the only residual of #97). Open issues: #97, #10, #21, #2, #11, #34, #3.

## G2 — Chosen images at baseline quality

**Done.** CSTati v3, YumeFlux ILv1 and JANIMA v1 base runs (832x1216, seed 2026091301, 28–36 s each) with full model
hashes re-verified; Anima modular baseline with the owner's chosen look B (softer cinematic shading); the Krea target
stack (TextFusion + Niji Sweet Spot + koukouya, 827.6 s) is the closest match to target image 142028671; WAI and the
screenshot stack executed with owner verdicts recorded ("experiment only").

**Not done.** Zero accepted images: the Workspace held 111 assets, 108 unreviewed, 3 needs-work, no accepted or
favourite membership. The four-item deliverable in [FANTASY-CHARACTER-BRIEF.md](FANTASY-CHARACTER-BRIEF.md) (portrait,
full body, expression variation, documented correction) has never been produced. Hands and leg/foot overlap are
unresolved on all three new baselines and no baseline output has been put through the verified `anime-detail-fix`
pass. No controlled with/without-adapter comparison at matched seed exists. AniFox v2 is the one family that never ran
(download parked; two ledger entries disagree on the partial size and are reconciled in the assessment).

**Done 16 September 2026.** Look B ran through the brief's four steps at seed 2026091301 (portrait, full body, expression, a detail pass on the portrait) as four Studio jobs, inspected and recorded in `experiments/curated/fantasy-pack-20260916/`; the four assets wait unreviewed in the review queue (HUMAN_TODO q-30). The seed did not carry identity across prompts (the hair changed on the expression render) and the detail pass changed the face's eye colour without touching the hands, so the same night the expression was redone as a *Change one thing* edit of the portrait (identity kept) while the depth Combine into the full-body pose lost the face at that scale: the next slice is a full-body route that keeps the face (Copy Pose or a face pass) plus a targeted hand repair, not another seed.

**Later on 16 September 2026 (identity).** An edit route keeps identity for expressions, and the replace-character route (`combine-klein-9b-replace`, PR #481) puts the
portrait's face into any picture that keeps its own pose and scene, including the depth Combine's own posed output, so the pack's posed full body is
*pose route, then face route* on the tested seeds (three research seeds and two Studio jobs, not a guarantee for others). Both proved through the Studio and recorded in the pack folder; the assets wait unreviewed (q-30).

**Previous next slice (13 September).** Run look B through the brief's four steps at a fixed seed, push each through `anime-detail-fix`, and
present the before/after pairs to the owner as one review batch. Every ingredient is proven; the missing artifact is an
owner decision. Open issue: #14.

**16 September 2026 (pose transfer).** Two strong pose-transfer routes are recipes on the Combine route (depth map leading, Copy Pose second), the ankle cut is a control on the depth recipe, a drawn stick figure is a recipe, and a keypoint pose editor draws that figure on the page (PR #466); every one proved through the Studio on the owner's pair. Identity across a body-pose change from a portrait-sized reference was open at this point (the depth route lost the face at full-body scale, `experiments/curated/fantasy-pack-20260916/`); the identity paragraph above records the same night's answer, *pose route, then face route* (PR #481), on the tested seeds.

## G3 — Character sheets, figures, poses, in-betweens

**Proven primitives.** `anime-detail-fix` repaired a six-finger hand (job 14caa4fb, 36.2 s, only the two crops changed); *(correction, 23 September 2026: at full resolution six digits remain after that job; see [quality/QUALITY-BACKLOG.md](quality/QUALITY-BACKLOG.md))*
`anime-esrgan` upscales; `character_krita.py` carried a protected edit into a real Krita 5.2.16 document (4,032 changed
pixels, 94,272 preserved); Godot 4.7.2 played a four-frame cycle at 479 ms against a 480 ms target with the Khronos
GLB validator; actor-scoped edit planning exists with a completed 12-attempt pilot (0 accepted).

**Missing.** No character-sheet decomposition exists anywhere: no endpoint, preset or UI action addresses a sub-region
of an asset as a first-class child. In-betweens are a research lead (LayerInbetween) with no route. Per-figure pose
change has no route; masked repair, the natural per-figure primitive, has zero completed jobs. No consistent
character exists to decompose for (pilot ended 0 selected).

**Next slice.** Build the addressable-figure primitive and nothing else: one endpoint plus one Asset-library action that
takes a multi-figure image and N marked rectangles and emits per-figure child assets with lineage back to the parent,
each routable into the verified upscale/repair presets and back into the parent via the proven Krita path. Tracked as
issue #252. Related: #23, #24, #65, #66, #71, #72, #22, #225.

## G4 — A UX that reflects the real work

**Real.** Nine surfaces with owned scope ([UX-WORKFLOWS.md](UX-WORKFLOWS.md)); 80 completed jobs came through this UI
and worker; guardrails derive from measured failures (source-bound continuation, 32 GiB host-commit gate, Wan decode
hold, timing estimates from 35 completed local samples).

**Gaps.** The five task families (idea, change, refine, motion, 3D draft) contain no lane for sheet/figure/sprite work.
The review surface that the whole architecture funnels into has processed 3 of 115 assets; PR #291 added the review
queue, shortcuts, bulk review and grouping the owner asked for, unused so far. The owner's first-hand verdict of
14 September is recorded in [UX-AUDIT-2026-09-14.md](UX-AUDIT-2026-09-14.md) (#278); seven PRs answered it the same
night and the owner's next pass decides whether they land (HUMAN_TODO q-7).

**Next slice.** Add the sixth task family ("work on one figure / build a sprite sequence") once #252 exists. Open
issues: #16, #36, #37, #38, #204.

## G5 — A UI that works and feels good

**Measured.** 79 synthetic Playwright journeys pass at 1440 px and 390 px; PR #211's native reload lane ran 19/19 in CI;
read polling is bounded and visibility-aware; the frontend reviewer found no dangling handlers, no missing endpoints,
no page-load submission and no double-submit path. Two real defects were found and fixed in PR #262: a recipe
swap during a reference upload could submit the wrong recipe, and a mid-upload slot change discarded the upload
silently. **Owner's verdict, 14 September.** Recorded first-hand in [UX-AUDIT-2026-09-14.md](UX-AUDIT-2026-09-14.md)
and owned by #278: seven UX PRs merged the same night, and `tests/studio_use_cases.py` now measures ten agent-driven
journeys (fixture 10/10; live read-only 4/10 with 4 dead ends ranked in [UX-USE-CASE-MATRIX.md](UX-USE-CASE-MATRIX.md)).
**Unmeasured.** Native-browser default lane; whether the merged wave changes the owner's verdict (HUMAN_TODO q-7).

## G6 — Modular workflow editing

**Real.** Revisioned documents with CAS receipts, named Steps, guided paths, the Bundle Explorer with tuning, and
SDK/CLI/MCP parity over one command vocabulary; six saved documents exist, one reopened at revision 3 with 1,224 nodes.
**Blocking limitation.** An edited graph cannot run: the executor accepts only registered recipes with the 22 projected
scalar/LoRA fields, and native visual-workflow import is refused by design. **Fixed in PR #262.** The installed-node
schema mis-read every V3 dynamic input (`COMFY_DYNAMICCOMBO_V3`, `COMFY_AUTOGROW_V3`, `COMFY_MATCHTYPE_V3`; 50 inputs
across 39 installed classes) as a plain socket, so the repo's own video presets could never pass "Check connections";
they now report "native adapter needed" honestly. **Next slice.** The narrowest widening of #122: run a saved document
whose graph equals a registered template except for inputs already named in that preset's catalog bindings. Open
issues: #118–#123, #143, #144.

## G7 — Everything else

Runtime resilience is the most thoroughly earned area (bounded recovery, Windows refusal timing, process ownership,
no duplicate generation on resume, mixed-batch recovery). The 64 GiB page file is configured and the commit gate is in
code. 3D generation works on the Radeon (TRELLIS, Hunyuan draft). The owner confirmed authorised-territory use
for Hunyuan3D 2.1 in issue #26; this records owner authorisation for that model and scope, without independent
legal verification, blanket approval, a terms change or new restrictions, or a new generation allowance. Voice stops at a working CPU
baseline. Resource efficiency is two of six children done (#172).
The two crash root causes, #77 (Qwen VAE host allocation) and #89 (0xC0000005 on IP-Adapter + ControlNet SDXL), remain
open and gate heavy work. Agent tooling for ComfyUI outside the Studio is wired for both runtimes
([AGENT-TOOLING.md](AGENT-TOOLING.md)). Next slice: #178, stage-aware admission that estimates decode-stage VRAM
separately from sampling, so a 995-second failure becomes an instant explained refusal.

## Open owner items

Items q-1 to q-6 in [HUMAN_TODO.md](../HUMAN_TODO.md) are answered. The owner's q-6 feedback is recorded
in the [UX audit](UX-AUDIT-2026-09-14.md); improvements and the owner's subsequent verdict remain under #278.
Creative acceptance of any generated image remains the owner's alone.

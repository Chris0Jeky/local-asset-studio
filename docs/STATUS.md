# Status by goal — 26 October 2026

## Private creation qualification — 28 October 2026

The existing private-session implementation is in PR #1677, tracked by #1673.
The continuation fixes two request-disclosure paths, failure-safe Make draft
migration, finder intent and the six previously failing workflow families' known
causes. See [qualification evidence](verification/2026-10-28-private-creation-qualification.md).
Fresh final-head CI remains the merge gate; local renderer/contract passes are not
claimed as configured-host rendering, human UX acceptance or archive completion.

## Current engineering delivery

This section records the current repository work. The September percentages and workstation asset counts below are a historical assessment, not a fresh measurement. The dated ledger in [CURRENT_STATE.md](../CURRENT_STATE.md) and the [repository snapshot](generated/REPOSITORY-STATE.md) retain the source revisions and verification receipts. Completed implementation, successful model execution and owner art acceptance remain separate.

| Area | Current delivery | Remaining acceptance |
| --- | --- | --- |
| Recovery shelf | Merged [#1659](https://github.com/Chris0Jeky/local-asset-studio/pull/1659): transactional IndexedDB owner, explicit legacy-copy handling, native closed-tab export/import, keyboard and actual 200% browser zoom. Issues #392 and #825 are complete. | Broader keyboard/lifecycle and assistive-technology matrix in #393; clearing browser data remains outside durability guarantees. |
| Library browsing | Merged [#1660](https://github.com/Chris0Jeky/local-asset-studio/pull/1660): coherent asset/collection observations, bounded paging, unavailable details, preserved selection and off-page consumers. Issue #1627 is complete. | Browser memory/media/query budgets at 100, 1,000 and 10,000 assets remain in #177. |
| Recovery explanations | Merged [#1664](https://github.com/Chris0Jeky/local-asset-studio/pull/1664): retain the last recorded refusal alongside exact unconfirmed command bytes and preserve it through reload and shelf round-trip. | #393 retains its wider lifecycle acceptance. |
| Setup history and agents | Merged [#1665](https://github.com/Chris0Jeky/local-asset-studio/pull/1665): read-only MCP history, comparison and revision export with strict response bounds and revision sequence checks. The dedicated Linux/Windows SDK gates execute all 17 reader cases without skips. | Browser history, receipt associations, fork/import and retention in #395; broader artifact/progress/reconnection workflow in #123. |
| Audio/video finishing | Merged #1656/#1658: trim against actual source video-track bounds and verify decoded output coverage before issuing successful receipts. | These synthetic/render contract checks do not establish new neural video quality or owner acceptance. |
| Runtime readiness | Merged #1668 protects MOSS admission; merged [#1667](https://github.com/Chris0Jeky/local-asset-studio/pull/1667) and [#1672](https://github.com/Chris0Jeky/local-asset-studio/pull/1672) extend Qwen/MOSS direct-launcher refusal for incomplete encoder support. Issue #1661 is complete; all seven direct launcher cases passed on Windows without skips. | Stat-only preflight is separate from node compatibility, installed-host inference and output quality. |
| Verification fixtures and CI | Merged #1659/#1660/#1666 correct queued-close sequencing, dependency setup/order and incomplete synthetic owners while retaining original failures and application assertions. Merged [#1674](https://github.com/Chris0Jeky/local-asset-studio/pull/1674) adds Guided failure receipts and bounds the measured Bundle, UX and Linux Lifecycle installers. Merged [#1675](https://github.com/Chris0Jeky/local-asset-studio/pull/1675) corrects the observed Windows response-abort cleanup gap; both new regressions and the unchanged native Lifecycle journey pass on Linux and Windows. | Native and inert evidence retain their separate limits; full proof is tied to each exact source tree. |
| MOSS study records | Merged #1668 and #1671 preserve 42 completed image/recipe records and a separate blind reread of 12 existing images. | Agent ratings are not owner acceptance; nine follow-up renders and eight Kromoss comparisons remain unrun. |

The final integration record is [26 October closeout](verification/2026-10-26-integration-closeout.md). It records merged revisions, exact-tree CI and retained failures; this page is the product-level view.

## Next bounded work

- **#177:** measure Library browser/SQLite resource costs on the stated catalogue sizes, with explicit memory, media and latency budgets. Paging correctness does not establish performance acceptance.
- **#393:** finish the remaining keyboard, disappearing-opener, collection-focus, browser-menu zoom and screen-reader matrix. The shelf's native 200% zoom proof is narrower than this complete matrix.
- **#395 / #123:** continue the existing setup-history and agent-workflow owners; the new MCP readers do not authorize imports or create a second history store.
- **Repository operating model:** use the fresh authored queue, SHA-bound snapshot and explicit ledger retention procedure delivered under #315; labels and automatic connector capture are optional independent improvements.
- **#1662:** resume the pinned Kromoss transfer only under a new bounded transfer attempt. This is an agent-executable external dependency, not an unresolved owner licensing decision.

Dependency and readiness details are retained in the [captured active queue](../research/repository-state/active-work.json): #178 remains blocked by #77/#89, #313 is owner-run, and #395/#123 are parked beyond the next two ready slices. The dated capture records #315 in review before this documentation closeout; this update completes its operating-model acceptance.

Owner choices remain in [HUMAN_TODO.md](../HUMAN_TODO.md), including the first-hand UX verdict (q-7), art acceptance and MOSS Make-look placement/wording. Existing answers stay recorded; this engineering closeout does not infer new answers.

## Historical goal assessment — 24 September 2026, with later dated annotations

The original assessment below is retained with its original counts, estimates and later annotations. Its open/closed issue references and installed-host observations describe those dates; they do not override the current engineering section or live GitHub state.

The one page that says where each owner goal stands; `CURRENT_STATE.md` is the evidence ledger it views. Percentages are
the coordinator's rough estimate, set in the 13–14 September assessment ([STUDIO-REVIEW-2026-09-13.md](STUDIO-REVIEW-2026-09-13.md))
and re-estimated after 409 PRs merged from 14 to 24 September (`gh pr list --state merged --limit 1000 --search "merged:>=2026-09-14"`);
each section says what moved its number. Pointers are exact. Three states stay distinct: generated (a job completed),
inspected/accepted (a human judged the art), licensed (the terms allow the use); an agent's judgement is never acceptance.

| Goal | State | One-line summary |
| --- | --- | --- |
| G1 Workflows that genuinely work and are elaborated | ~70 % (was ~65 %) | 89 presets, 47 `verified: true` (66 and 36 after #263); 19 newly verified routes (Klein Combine and Restyle, Qwen-Image 2.1, Krea GGUF, Z-Image fp8, `wai-skeleton`, masked repair, Style + Pose); the six most-used SDXL presets wait for a re-proof after #888; video still fails inspection |
| G2 Chosen images at baseline quality | ~65 % (was ~60 %) | The brief's four steps plus identity routes exist, and the owner chose the pack's face, expression and full body from them (q-30); a hand repair works (agent-judged); zero owner-accepted images, 0 keepers of 1,205 assets (#939) |
| G3 Character sheets → figures, poses, in-betweens | ~45 % (was ~35 %) | The figure splitter with lineage is merged (#379, #647) but has never split a real sheet; masked hand repair verified; pose editor and pose routes exist; in-betweens are research only |
| G4 UX that reflects the real work | ~70 % (was ~72 %) | Create workshop layouts, the Combine workbench and completed Create/Overview/library journeys; the 24 Sep live QA found the library and desk buried under lab output (#939, #940); no sheet/figure task family |
| G5 UI that works and feels good | ~60 % (was ~55 %) | Live use-case mode reaches 15 of 15 journeys (5 PASS, 10 STOP, 0 FAIL, 22 Sep); UX tracker #772 open; the owner's verdict on the UX wave is still open (q-7) |
| G6 Modular workflow editing in the Studio | ~58 % (was ~55 %) | Step reordering, portable Step modules, lossless input adapters and control previews merged; an edited graph still cannot run (#122) |
| G7 Everything else | ~50 % (was ~40 %) | Backend switches work, the VRAM guard and checkpoint-switch eviction target the measured spills, idle cache release; stage-aware admission merged opt-in; Spoken Briefs merged but unproved on real narration; #77/#89 open |

### G1 — Workflows that genuinely work

**Moved up by** nineteen presets proved through the Studio since 14 September (Studio jobs, agent-inspected,
`verified: true`, none art acceptance; `presets/catalog.json` against the #263 merge); **held back by** eight that lost the flag (`qwen21-t2i` and `qwen21-edit`, which lost it after #1059, were re-proved on 27 Sep).
- Combine: `combine-klein` (FLUX.2 Klein 4B, job `fb0eb95d`), and on Klein 9B `combine-klein-9b` (pose first),
  `-depth` (`22ff6394`), `-skeleton` (`26448d58`), `-copypose` (`61dd5375`, #452) and `-replace` (`7051b297`, `2752190c`, #481).
  Since the owner's q-28 answer (23 Sep) the route order is Copy Pose, drawn skeleton, depth, replace, pose-first 9B, 4B.
- Restyle: `restyle-klein` (job `db25b173`, 65.9 s including the model load; 16–20 s warm in research) leads, `restyle-wai` (`0c13590c`) is second (owner, q-27, 23 Sep).
- Qwen-Image 2.1 on the isolated v0.37.0 backend: `qwen21-t2i` (`be94bd02`, 52.9 s), `qwen21-rgba` (`b377572d`),
  `qwen21-edit` (`dc8f18f8`) (#858, #876, [QWEN-IMAGE-21.md](QWEN-IMAGE-21.md)); t2i and edit lost the flag on 26 Sep when #1059 rerouted their output to RGB and got it back on 27 Sep (`c11448cc`, `74597f0d`, RGB PNGs); #739 open for 2048², multi-reference, text, LoRA, VRAM.
- Krea 2 Q5_K_M GGUF with the text encoder on the CPU: `krea-portrait-gguf` (`c6049b90`), `krea-anime-atelier-gguf`
  (`29e468ca`) (#880); the atelier target stack took 173.2 s on it against 827.6 s on fp8.
- `zimage-fast` (`4f5974cc`, 57 s), `wai-skeleton` (`6a342bbf`, #855), `anime-masked-repair` (`1f9b3e11`, #881, #885),
  and the Style + Pose recipes `style-pose-wai`, `-nova`, `-yumeflux` ([STYLE-AND-POSE.md](STYLE-AND-POSE.md)).

**Lost the flag.** #888 moved `wai`, `anime`, `pony`, `noob`, `cstati-v3-baseline` and `yumeflux-ilv1-baseline` to
`VAEDecodeTiled` 512 (a blind quality tie, `experiments/curated/overnight-20260923/sdxl-vae-decode/`), unverified until each
has a Studio proof; `anime-detail-fix` and `pixel-lora` because their 14 September revisions were not re-run (execution notes).

**Not working.** Video is unchanged: both inspected Wan 2.2 outputs failed and the canonical control died in VAEDecode
([WAN-DECODE-CAPACITY.md](WAN-DECODE-CAPACITY.md)); the one surviving clip (`e33116f1`) holds together because it barely
moves ([quality/QUALITY-BACKLOG.md](quality/QUALITY-BACKLOG.md)). *History: on 13 September 27 presets had never completed a job; not re-counted.*
**Next slice.** Six Studio proofs for the tiled-decode presets, then per-backend schema captures. Open: #97, #739, #10, #21, #2, #11, #3.

### G2 — Chosen images at baseline quality

**Moved up by** the fantasy pack's batch, the identity routes and the owner's q-30 choice; not by acceptance.
**Done 16 September.** Look B (`anima-v1-baseline`, seed 2026091301) ran through the brief's four steps as Studio jobs
(`ca5c5082`, `373d0b35`, `053f6cf5`, `009eddad`; `experiments/curated/fantasy-pack-20260916/`). The seed did not carry
identity; *Change one thing* edits of the portrait did (`d0e8524e`, `ccf4fbf4`); and *pose route, then face route*
(`combine-klein-9b-replace`, #481) gave a full body that keeps the face on the tested seeds.
**Owner, 23 September (q-30, [HUMAN_TODO.md](../HUMAN_TODO.md)).** Adopting the [agent pre-review](quality/pre-reviews/q-30.md):
portrait 1 is the character's face, edit 7 the expression variation, replace render f1 the full body, and posed full
bodies are made pose route, then face route. The Runs & review marks were not changed, so no asset is recorded as accepted.
**Hands and adapters.** Anime Detail Fix fixed 0 of 3 recorded hand targets (correction in G3); the feathered
`anime-masked-repair` at 0.6 fixed the NoobAI six-finger hand on 3 of 3 seeds (agent-judged,
[second-judge/hand-inpaint.md](quality/second-judge/hand-inpaint.md)); Anima hands are clean where visible (agent-judged). A matched-seed
with/without-adapter comparison now exists: the 23 Sep LoRA smokes (#846) set 11 LoRAs on WAI, NoobAI and Pony against a
no-LoRA control, and the three-seed retest found every candidate ties its control ([q-32 pre-review](quality/pre-reviews/q-32.md)).

**Not done.** No asset is marked accepted in the library (q-30 chose representatives but left the marks unchanged): live QA on 24 Sep counted 1,205 assets, 1,184 unreviewed, 0 keepers (#939).
The full body's fine facial features are redrawn at that scale; a face pass at portrait fidelity needs renders (backlog).
*Correction to 14 Sep "AniFox never ran":* AniFox v2 is installed with a matching hash (21 Sep) and has run in the labs
(105 `anifox-v2-baseline` assets, #939); no inspected baseline entry for the pack exists. q-25 is answered (27 Sep 2026): Style + Pose stays in the pack on WAI v17 at style weight 0.3-0.45.
**Next slice.** A face pass on the chosen full body, masked repair where a hand needs it, one owner review batch. Open: #14.

### G3 — Character sheets, figures, poses, in-betweens

**Moved up by** the figure splitter, a working hand repair and the pose tools. **Built, not yet used on a sheet.**
`POST /api/assets/split-figures` and the Asset-library *Split figures* editor turn marked rectangles into child assets
with lineage that can enter *Continue with this* (#354, #379, #400, #560, #647; [ADDRESSABLE-FIGURES.md](ADDRESSABLE-FIGURES.md)).
#252 stays open for its runtime acceptance: split one owner-reviewed real sheet, route one child through repair, curate the receipts.

**Proven primitives.** `anime-esrgan`; the Krita protected edit (4,032 changed pixels, 94,272 preserved); Godot playback of
a four-frame cycle; `anime-masked-repair` (above); the pose editor on the Combine screen (#466, precise joints #480, redo
#548) and saved pose artifacts (#448, #570), with the drawn pose carried by Klein 9B (`8b571dd4`) and WAI (`wai-skeleton`).

**Not proven: automatic hand repair.** `anime-detail-fix` has not fixed a hand in any recorded run: on job 14caa4fb and the
Gentle trial e4e49006 it left six digits; on 009eddad it changed the eyes and earrings and left the hands. *History: until
23 September 2026 this page listed 14caa4fb under Proven primitives ("repaired a six-finger hand"); the full-resolution
check that corrected it is in [quality/QUALITY-BACKLOG.md](quality/QUALITY-BACKLOG.md).*

**Missing.** In-betweens are a research lead (LayerInbetween) with no route; split-then-repose of one figure is untried.
Next slice: #252's runtime acceptance. Related: #23, #24, #65, #66, #71, #72, #22, #225.

### G4 — A UX that reflects the real work

**Moved down by** the 24 Sep live QA: the new surfaces are real, but the everyday lists stopped signalling. **Real.** The
dense Create page became a workshop: Focus (#540), a Studio layout with Arcade and Sakura skins (#541), Immersive Studio
with Retro Anime and local ambience (#574), recovery reachable on Focus (#565); the owner's
qualification of the layouts is #539 (open). The Combine workbench keeps sources, engines and seed results together
(#430, #451); Create, Overview and library journeys were completed in #790. The Adaptive Studio strategy, asset kit and
behaviour lab are documents, not shipped UI (#549, #551, #556; [adaptive-studio/README.md](adaptive-studio/README.md)).
The owner chose on 23 Sep: run the maintainer/CI-only TypeScript + Vue island spike (#907, not started), defer
pilot artwork, allow reviewed remote decorative media.

**Gaps.** The library is buried under unlabelled lab output (#939); stale work never leaves the desk (#940); no
sheet/figure task family in Create (the splitter lives in the Asset library). **Next slice.** Run labels and a source
filter (#939), then a reversible "put away" (#940). Open: #16, #36, #37, #38, #204, #539.

### G5 — A UI that works and feels good

**Moved up by** the live use-case mode. **Measured.** #839 made live mode reach every journey: the 22 Sep live run on
main `12307176` reached 15 of 15 (5 PASS, 10 STOP at a control that would write, 0 SKIP, 0 FAIL), with 0 generation
submissions and 0 page errors ([UX-USE-CASE-MATRIX.md](UX-USE-CASE-MATRIX.md), "Live mode").
**Open.** The UX QA tracker #772 (skip link #769, the Generate dock with readiness and ETA #775) and #844 (pose guide
stale after a size change). **Unmeasured.** The owner's verdict: the 14 Sep statement is in
[UX-AUDIT-2026-09-14.md](UX-AUDIT-2026-09-14.md) (#278, open) and the first-hand pass over the answering wave (q-7) was
kept open by the owner on 23 Sep.

### G6 — Modular workflow editing

**Moved up a little by** new editing primitives: named Step reordering (#390, #587), portable Step modules with guarded
undo/redo (#650, relanding #645), lossless input adapters with fail-closed schema validation (#646, #119), and typed
control previews in the builder (#402, #415). **Blocking limitation, unchanged.** An edited graph cannot run: the executor
accepts only registered recipes and their projected fields (#122 open). **Next slice, unchanged.** Run a saved document
whose graph equals a registered template except for inputs already named in that preset's catalog bindings. Open
issues: #118–#123, #143, #384.

### G7 — Everything else

**Moved up by** runtime fixes measured on this PC. Backend switches work since #863 and #870 (the Qwen-Image 2.1 switch
took about 40 s each way). The idle cache release (#470) took ComfyUI from 5.3 GB to 463 MB resident. GPU spill is
measured (`experiments/curated/vram-spill-20260923/`, [RUNTIME-PRECONDITIONS.md](RUNTIME-PRECONDITIONS.md) §8) with the
reserve kept at 0.6 (#854); the Studio now unloads the previous checkpoint before a graph that drops it (#900) and loads a VRAM guard from
`runtime-patches/comfy-extensions/studio_vram_guard` without editing ComfyUI (#909). Stage-aware admission is merged
opt-in (#656); #178 stays open until profiles carry measured values. #77 (Qwen VAE host allocation) and #89 (0xC0000005
on IP-Adapter + ControlNet SDXL) remain open. The 64 GiB page file and commit gate stand; 3D works (TRELLIS, Hunyuan draft). The owner confirmed authorised-territory use for Hunyuan3D 2.1 in issue #26; this records
owner authorisation for that model and scope, without independent legal verification, blanket approval, a terms change
or new restrictions, or a new generation allowance.

Models: the LoRA disk audit hashed 85 LoRAs and moved nothing ([LORA-DISK-AUDIT-2026-09-23.md](research/LORA-DISK-AUDIT-2026-09-23.md));
the owner's q-32 answers pinned the eight orphans and kept the Krea TextFusion LoRA at 1.0. Voice: Spoken Briefs turns a
handoff Markdown file into one local narration WAV over the Kokoro CPU baseline (#643, #653, #700, #707, #749, #905); it
passes CI, but no real workstation narration is recorded ([spoken-briefs/README.md](spoken-briefs/README.md); #637, #641).
An owner-authorised adult-content prompt lab ran through the Studio from 21 September (q-29, q-31); details and local-only
media records: `experiments/curated/nsfw-lab-*`. Agent tooling: [AGENT-TOOLING.md](AGENT-TOOLING.md).

## Known live issues (24 Sep QA)

*Correction 25 Sep 2026: #939 is CLOSED (was open in this 24 Sep snapshot); #942 is CLOSED by PR #998 — the lab passes have moved with a correction. #940 and #772 stay OPEN. This list stays the dated 24 September snapshot.*

- #939 (CLOSED 25 Sep; open at this snapshot): the Asset library held 1,205 assets, 1,184 unreviewed and 0 keepers, mostly unlabelled lab outputs; owner work was buried.
- #940: old problems, desk items and plans never leave Overview, Create → Problems or Runs & review.
- #942 (CLOSED by PR #998; 25 Sep): the lab passes no longer sit atop `CURRENT_STATE.md`; see [LEDGER.md](../experiments/curated/nsfw-lab-20260923/LEDGER.md), whose correction shows the p40–p92 header times are not execution evidence.
- #772: the open UX QA tracker for the Studio journeys and Create layouts.

## Open owner items

Open in [HUMAN_TODO.md](../HUMAN_TODO.md): q-7 (first-hand pass over the UX wave) and q-28 (a)–(d) if the owner wants to weigh in. Answered 27 September: q-25 and the asset plan. Answered 23 September: q-27, q-28 (e), q-30, q-31, q-32 (its optional art judgement of the LoRA smoke winners stays open), the three
Adaptive Studio choices; q-29 on 20 and 23 September; the ZZZ age-guide intake on 24 September. No output is licence-cleared:
the owner set licence gating aside for private experiments (15 September); terms stay recorded in `models/library.json`.
Creative acceptance of any generated image remains the owner's alone.

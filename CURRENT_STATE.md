# Current state — 11 September 2026

## Plan — anime & fantasy atelier (12 September 2026)

Planned, not executed: four LoRA slots per preset with zero-strength pruning, an installed-LoRA and
sampler options endpoint, a sourced settings knowledge base with a grid/remix planner, named recipes,
prompt wildcards, two new Krea 2 Turbo presets, corrected SDXL anime grammars, download/intake scripts
and the [atelier guide](docs/ANIME-FANTASY-ATELIER.md). No agent submitted a generation for any of it;
every new or restructured preset ships `verified: false`, and the only local measurement behind the
plan is a direct ComfyUI API probe of Krea 2 Turbo with NIJISIS at 768×1152 and 15 steps — prompt
`09dadd6e-3e60-4c37-80d1-9244bb8e848d`, 986.6 seconds, submitted before these presets existed, so it
proves the model and adapter combination and nothing about the bindings. Results, when they exist,
belong in the executed sections below, not here.

## Creative production milestone

Studio now has **54 recipes**, a persistent asset Workspace, role-guided Qwen
references, bounded comparisons, native exports, and explicit model-environment
switching. Models and operational outputs remain outside Git. HiDream concept
and reference-restyle recipes both produced 2048-square PNGs through Studio:
184.697 seconds and 76.260 seconds respectively, at eight steps. Their distinct
loading/cache conditions are not a model benchmark. See [HiDream](docs/HIDREAM.md).

The comparison `fbb384c70a5e48b39a9eba6c227374eb` completed both Anima seed stages
and awaits creative review. Imported originals can now join collections and
native exports without generation. Browser-selected sprite frames produced
Godot project `d62777fdd019462b99d28357e61393b8`: actual import/playback retained
120/80/120/160 ms, 64-square canvases and anchor [32,32]. An earlier export
`df007b4d33d8465695615535e004be4d` exposed a form-serialization bug (100 ms values);
that bug is fixed and the corrected plan and engine evidence were checked.

The authored chest UI built project `db662bb6e60f42c781e001bd681b9743`, retaining
BLEND, animated GLB and four CPU inspection renders. The first GLB exposed a
hidden collision helper as visible geometry; the exporter now excludes it from
GLB while retaining it in BLEND. Fresh project `44cfa4a0b29a43098d6c7c7609ca6831`
completed with the four intended parts and named hinge animation; its renders and
browser preview were inspected. Native jobs persist before Blender. Recovery
requires a successful exit log and refuses recorded failure evidence, without
repeating a build; focused fault tests pass.

Krita is now an option in the native-export dialog. Browser project
`e563585717324f54aa57e6fc9bd9f773` selected two existing 64-square frames, retained
both requested layer names in KRA, reopened to PNG and produced a complete source
pack. The isolated offscreen crash and successful hidden Windows batch proofs
are preserved. This proves flat native layers, not automatic part segmentation.

H3's opt-in stdlib mmap loader constructed all 2,054 encoder tensors and the
MiniMax encoder model in 6.65 seconds (process peak working set 4.14 GiB). CUDA
was initialized by the runtime; this was construction, not inference proof. The
first video attempt with copy-on-write mapping passed encoder loading, then
failed in UNETLoader with Windows error 1455 (commit/pagefile exhaustion), prompt
`cce6da2a-0978-4c98-95d7-1c7ba8274a7c`. The machine has a 40 GiB paging file.
A read-only encoder attempt also reached the same diffusion-file error, prompt
`af49ef6a-433e-47eb-95d1-0efe7cb9ef52`. Extending the exact-file read-only loader
to the FL2VA diffusion file then constructed MiniMaxH3/legacy ModelPatcher in
5.603 seconds, with 4.30 GiB peak process working set. The subsequent short video
prompt `49873807-fda1-4fe0-afdd-62b13f5329d8` completed in 398.096 seconds:
39 H.264 frames at 512×320 and 32 kHz stereo AAC, both 1.625 seconds. All frames
and audio decoded; first/middle/last frames were inspected. The tested defaults
now match the executed graph. No system paging settings changed. The normal
native loader remains incompatible; use the [isolated H3 route](docs/H3-WINDOWS.md).

The broader research backlog is still open: Seed Hunter dependencies/execution,
shot-continuation/control comparisons, interactive Krita diffusion, automatic 3D
part/rig experiments and the full accepted character-pack vertical slice. The
completed native exports are scoped engine checks, not art or gameplay acceptance.
[HUMAN_TODO.md](HUMAN_TODO.md) still holds the optional subjective choices.

**149 tests pass**, with one existing Windows symlink skip; the 54-preset catalog
validator and changed JavaScript syntax checks pass. Independent reviews caught
and resolved recovery/provenance defects. Gallery handoffs now retain the source
asset identity and populate Qwen's first reference slot. The browser saved
`Ember chest → Qwen reference` with the correct parent and hashed input metadata;
no extra generation was submitted. Comparison planning also rejects numerically
equivalent values before reserving runs, so `1`, `1.0` and `1e0` cannot consume
duplicate candidates. The branch is pushed as PR #39; this is a scoped
milestone, not completion of every research issue. See the [usable routes, execution
records and issue-by-issue remainder](docs/PRODUCTION-WORKSPACE.md). The completed
worker worktree was removed after preserving its ignored runtime receipts.

## Earlier checkpoints during this implementation pass

The user requested an ambitious implementation pass across merged PRs **#20**
(game-asset planner, reference graphs, atlas/ORA tools) and **#8** (frontier research).
They are now the branch base `f6e046b`; work continues on
`codex/creative-production-workspace` with incremental commits and one writer.
The original Workflow Lab evidence below remains scoped to its recorded runs.

First implemented slice: a persistent Workspace view with collections, search,
media filters, favorites, tags, review notes, multi-select, recoverable Trash/Restore,
image-to-workflow handoffs and ZIP exports containing snapshots, recipes and metadata.
SQLite and immutable hashed media live under the configured shared experiments
directory, outside Git. Original ComfyUI outputs are preserved. Saved setups now
live on the server, with browser-local migration. Read [the workspace guide](docs/WORKSPACE.md).

Startup identity is independent of ComfyUI; the launcher reuses an existing Studio
even when its backend is unavailable. Full node discovery is cached for 120 seconds
with an explicit refresh. Uploads are decoded/verified, capped at 40 megapixels,
and retain original dimensions and SHA-256 metadata.

Verified at this slice: 106 tests pass (one existing Windows symlink availability
skip), catalog validator passes, both JavaScript files parse, and launcher syntax
parses. Actual browser actions created a collection, assigned an existing Anima
render, saved tags/notes, moved it to Trash and restored it. The new store indexed
46 existing outputs; no generation was submitted. Wider browser checks and
independent review are in progress. Review states remain unreviewed unless the
user explicitly changes them; the optional choices in [HUMAN_TODO.md](HUMAN_TODO.md)
remain open.

Outstanding work in the active goal: role-specific Qwen references (#21), bounded
experiments and trusted stage execution (#10/#22), isolated HiDream integration
(#2), H3 loader compatibility (#18/#11), shot/control experiments (#12/#13),
native editing and engine exports (#14–#16/#23–#25), and accurate source/terms
metadata (#9/#26). Research entries are not automatically executable or accepted.
The secondary workspace request has an implemented foundation; it is not a claim
that the broader production goal is complete.

The next increment adds three Qwen Atelier API/visual pairs (52 presets total),
with one/two/three role-specific references, preserved aspect, byte hashes, a
resolved-graph preview, and saved-reference recovery. See
[Reference atelier](docs/REFERENCE-ATELIER.md). All three pass live node/file
validation without submission. Browser upload and preview succeeded with
identity, pose and manga-style references; controlled generation
`c8b752b5-cb25-4438-8c66-f0e5fafcae04` is being observed, not yet accepted.
The saved Anima-to-ESRGAN handoff survived a fresh page and generated successfully
as `60949ec3-2ec2-471f-88cb-73fa78a5491c`, retaining its parent asset.

Godot adapter commit `af4ccb5` adds actual headless import/playback. Its fixed
120/80/120/160 ms QA sequence played in 480.000003 ms with anchor [24,60] and no
anchor error. The existing Ember GLB loaded with 12 nodes, 9 meshes, 3 materials
and `Lantern bob rigAction`. This is scoped engine evidence, not rig, collision,
root-motion or art acceptance. Evidence is retained locally under
`.runtime/godot-adapter-evidence/qa-480ms-godot-4.7.2/`.

The production runner now prepares pinned one-axis comparisons, uses the existing
Studio worker, reserves generation budgets across branches, and persists stage
identities and known prompt IDs. Fault-injection tests cover lost responses,
restart observation without duplicate submission, shared caps and changed plans.
Workspace can prepare timed atlas, flat ORA and Godot exports with native source
ZIPs. Actual engine verification is an explicit export option. Read
[Experiments](docs/EXPERIMENTS.md) and [Native exports](docs/NATIVE-EXPORTS.md).
At this increment, 126 tests pass (one existing skip); browser preflight and Start
created comparison `fbb384c70a5e48b39a9eba6c227374eb`, currently being observed.
Native export UI round-trip remains pending.

The three-reference Qwen run above completed: **1334.646 seconds**, 512×768,
four steps. It produced a manga portrait with the requested extended hand and
compass; design fidelity and subjective acceptance remain open. Only the
three-reference recipe's execution badge was updated. One- and two-reference
variants have schema/preview proof, not fresh inference proof.

## Changed

Workflow Lab expands the Studio to **49 presets, 49 visual ComfyUI workflows and
50 API graphs**. The 20 additions cover manga line art, screentone, cinematic
lighting, Anima Aesthetic 1.1, free Krea 2 retro anime, MiniMax H3, Wan 2.2,
Hunyuan3D 2.1 and TRELLIS.2. Portrait/environment, preview/quality,
reference-image and seed-audition variants expose the relevant controls.

The three UI views are Create, Models & folders, and Workflow lab. Model paths,
dependency inspection, pinned downloads, named setups, exact recipe import,
image comparison, image-to-video/3D handoff, MP4 playback and an interactive GLB
viewer are available. Selection, import and page load never submit a generation.
A separate Generate action queues work serially.

All **22 curated expansion assets** finished installation with matching SHA-256
receipts. The 20 new native graphs pass the running ComfyUI node schemas with no
missing file selections. Weights remain outside Git. The existing H3 diffusion
download is hard-linked into `models/diffusion_models`, avoiding a second 20 GB copy.
Its companion encoder, video/audio VAEs and Turbo LoRA are installed as well.

The desktop shortcut now launches this checkout. Local config points at the
original `C:/Users/jekyt/source/local-asset-studio/experiments` so its 18 existing
jobs and uploads remain available. Source files in that checkout were preserved.
The launcher detects another Studio workspace on its port before reusing it.
Services remain loopback-only: Studio 8191, ComfyUI 8188.

The user chose **free alternatives** to the 1,000-Buzz NIJISIS LoRA; no Buzz was
spent. Krea Turbo FP8 plus the official retro-anime adapter is a different recipe
from the linked Krea Raw INT8 / NIJISIS example. The user confirmed eligible
territory use for H3. Subjective choices remain open in [HUMAN_TODO.md](HUMAN_TODO.md).

## Verified

Runtime: RX 9070 XT 16 GB, 32 GB system RAM, Windows ROCm 7.2.1 / Torch 2.9.1,
ComfyUI 0.35.0 at `40c4fcdf513a4523e39d54a9d391908af8df8171`.
These are single observations at the listed controls, including different amounts
of model loading and caching; they are not comparative speed rankings.

| New route | Observed execution | ComfyUI prompt ID |
|---|---|---|
| Manga Line Art portrait | PNG, 512×768, 20 steps, CFG 5, adapter 0.8; 34.15s | `6e37e90d-ef45-4e07-af31-045b4938fe53` |
| Anima Aesthetic portrait | PNG, 512×768, 24 steps, CFG 4; 20.01s | `6d136e16-132f-4964-a07b-988a2a34b5ac` |
| Free Krea retro-anime portrait | PNG, 512×768, 8 steps, CFG 1; 188.67s | `144048d4-d6ea-4142-87f5-bdf11d87031c` |
| Hunyuan3D Draft | GLB, octree 128, 20 steps; 36.88s | `ba5ce9da-f6e5-4322-8f73-d56980ef61d6` |
| Wan Animate Image | MP4, 512×768, 33 frames at 24fps, 20 steps; 141.77s | `460ed2dd-1a6b-45e1-9374-ac130595517c` |
| TRELLIS automatic cutout | GLB with UVs, base color and metallic/roughness textures; 74.89s | `5f53db1c-574b-4754-94d5-51d5428729a3` |
| TRELLIS transparent reference | Same PBR stages, actual alpha matte, padding 1.1; 83.48s | `79e4362c-8bcb-4695-9222-e48eb6eecee3` |

The seed was 2026091103, except the transparent-reference trial used 2026091104.
The three images were visually inspected. The Hunyuan
GLB has one mesh, 80,924 triangles and no textures; it rendered in the embedded
viewer. Wan's MP4 decodes to 33 frames, reports 1.375s in the browser, and its
media endpoint returned the requested 1,024-byte range with HTTP 206. ComfyUI
automatically fell back to tiled VAE decoding after ordinary decoding ran out of
VRAM. A sampled video frame was inspected; long-shot consistency is not established.

TRELLIS first failed in the native GPU FP64 UV solver. A local two-line
[CPU UV compatibility patch](runtime-patches/README.md) selects ComfyUI's existing
NumPy solve for small charts while retaining GPU segmentation and PBR baking.
The original runtime source is backed up; patch reversal passes `git apply -R --check`.
Both subsequent PBR trials completed, but both invented a large ground plane.
A separate mask/crop probe confirmed correct foreground isolation. The real
transparent starter is now `examples/references/studio-lantern-cutout.png`;
the old RGBA PNG had an opaque alpha channel and is not used as the matte example.

The explicit Blender finishing script trimmed 3.5% from the bottom of the second
mesh and reduced it from 939,564 to **80,335 triangles**. The resulting 9,944,176-byte
GLB retains UVs and both PBR textures and was inspected in the Workflow Lab viewer.
The cut can leave an open base; this is a useful draft, not game-engine acceptance.
Original 24+ MB generated GLBs remain in ComfyUI output. Exact source/output hashes
and finishing settings accompany the small curated export.

Small selected outputs and exact recipes are in
[the curated execution record](experiments/curated/workflow-lab/README.md).
Only the individual new presets that completed have the Executed badge.

Browser interactions inspected an H3 visual workflow (15 nodes, five weights,
no missing dependencies), imported an exact manga recipe, saved/restored a
three-seed setup, attached a generated image through Animate, and submitted the
known video/3D jobs. Reload and inspection did not create extra jobs. Create and
Models views fit a 390px viewport without horizontal overflow. Final browser checks
played the Wan clip through to its end, exercised keyboard orbit on the trimmed
3D preview, and reported no browser warnings or errors.

Twenty-two regression tests and the catalog/payload validator passed before final
closeout. Twenty native expansion graphs passed live node/link/enum validation.
Independent adversarial review found recipe-import drift and unbounded media
buffering; both were fixed and the follow-up review found no remaining blocker.
Recipe imports verify the embedded graph and guard against a changed template
before submission. Media streams in bounded chunks and preserves Range responses.

Earlier evidence remains valid at its original scope: the original 20 simple
presets were exercised, the Lanternkeeper example includes 96 frames and three
animated GLBs, and isolated HiDream O1 FP8 produced 2048×2048 in an eight-step run.
The five anime finishing graphs were schema-checked and CPU detector/upscaler
probes passed; this expansion does not turn them into new art acceptance.

## NOT verified

Hunyuan Detail, new environment variants, screentone/cinematic adapters,
Wan text-to-video and longer shots have not received
separate execution or quality comparisons. Presence and schema validation alone
do not prove GPU compatibility.

MiniMax H3 produced **no video**. Two accepted tiny trials crashed the ComfyUI
process with Windows access violation `0xC0000005` in text-encoder loading:
`c36094f8-04bd-4673-8020-07e3940e4df6` and
`239417ce-136a-49d7-aa44-98950646df85`. The second used a fresh process with
`--disable-mmap`; it still failed. A CPU safetensors-header/tensor-access probe
completed but does not prove full inference compatibility. The flag was reverted,
the failures were reconciled from logs, and neither uncertain job was repeated.
Local `runtime_blocks` disables H3 submission while retaining its visual graphs.
The compatibility follow-up is tracked in
[issue 18](https://github.com/Chris0Jeky/local-asset-studio/issues/18).
Logs: `C:/AI/logs/20260911-154507-error.log` and
`C:/AI/logs/20260911-162226-error.log`.

The exact Seed Hunter 1.6 JSON was recovered through Civitai's public no-credit
endpoint and its SHA-256 matched official metadata. It is saved in
`workflows/community` and ComfyUI's `Studio Workflow Lab/Community` folder.
Static inspection found 154 nodes, 24 missing node classes and three additional
missing weights. Its custom-node code was not installed and the graph was not
executed. Native H3 variants do not establish its continuation, latent-upscale or
interpolation behavior. Provenance and the full dependency report are beside it.

Qwen's 40-step preset, FLUX.2 dev 32B Q4 inference, higher-step/reference-edit
HiDream comparisons, character-LoRA training, faithful animation in-betweens,
Krita integration and game-engine imports remain outside this completed expansion.
The FLUX.2 weights and Mistral encoder are already installed and checksum-verified.
Fresh-machine setup and broad browser coverage are not claimed.

## Residual risk

Heavy model switches can exhaust RAM/VRAM or crash Windows ROCm. H3 is blocked
locally after direct failures; untested settings remain experiments. The curated
installer preserves 20 GiB headroom, verifies before exposing the final filename,
and leaves interrupted partial downloads for an explicit resume.

Successful outputs are drafts: image anatomy, identity consistency, mesh topology,
UVs, materials, rigging and commercial suitability still need review. Anima weight
terms are non-commercial; Krea/H3 and third-party adapters have their own terms.
NoobAI remains hobby-only, and WAI mirror provenance is not creator authentication.

[Workflow Lab guide](docs/WORKFLOW-LAB.md) explains folder placement, the free
alternative, pipeline controls, sources and recovery. The implementation branch is
`codex/studio-workflow-lab`, based on `6bd4e5b`; final Git/CI status is reported with
the handoff. [HUMAN_TODO.md](HUMAN_TODO.md) contains the optional creative choices.

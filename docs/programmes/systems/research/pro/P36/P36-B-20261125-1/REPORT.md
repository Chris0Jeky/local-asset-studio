# P36-B-20261125-1: concept to playable character

**Implemented:** an offline Studio receipt graph, conservative sheet-consistency gate and Lumenfold-compatible draft export. **Planned:** the first real Sable A2 family, live Studio admission, native import, visual inspection, owner acceptance and intended-use licence decisions.

Run date: **2026-11-25 UTC**. Studio base: `0270760a3d4fd9e005a1788bba59d8242b77c2f4`. Branch: `pro/P36-B-20261125-1`. [Studio PR #2046](https://github.com/Chris0Jeky/local-asset-studio/pull/2046). Import-side disposition: **Refs [Chris0Jeky/lumenfold#3175](https://github.com/Chris0Jeky/lumenfold/issues/3175)**; live consumer integration and native qualification remain open. No issue is claimed closed.

## Kill criterion and outcome

Any failed, missing, uncertain or stale required identity observation against the exact accepted concept blocks the dependent stage. A high mean cannot cancel one failed critical trait. The eighth prototype stage (`unreal`) means accepted handoff readiness, so export can precede the separate native import/playback receipt required by issue #3175. Eight prototype receipts do not prove a playable character. Every descendant retains a direct concept binding, so matching only the previous stage cannot gradually redefine identity. Replacing the selected concept invalidates all seven descendants; replacing a selected non-root head invalidates its dependent branch while preserving immutable history.

The implemented graph links **concept, turnaround, expressions, outfits, mesh, rig, toon and unreal**. Each receipt binds Workspace/character scope, exact artifacts, full recipe, references, parent digests, the concept digest and a frozen policy. Separate attestations retain generation, inspection, acceptance and licence-use states. No score upgrades any of those states. The first-character plan contains no fabricated asset IDs, hashes or accepted members.

This is a bounded, inspectable prototype under the requested run path. It does not add a second media store or alter the app, catalogue, server binding, browser load behavior, Production queue or installed ComfyUI. No generation was submitted. There was no model download, runtime upgrade or native application run. Procedural software-test images and an unrigged triangle model are synthetic fixtures; none is character output.

## Measured software evidence

The command and hashes are in the [prototype README](https://github.com/Chris0Jeky/local-asset-studio/blob/pro/P36-B-20261125-1/prototypes/pro/P36/P36-B-20261125-1/README.md), [EVIDENCE.json](https://github.com/Chris0Jeky/local-asset-studio/blob/pro/P36-B-20261125-1/prototypes/pro/P36/P36-B-20261125-1/EVIDENCE.json) and [VERIFICATION.md](https://github.com/Chris0Jeky/local-asset-studio/blob/pro/P36-B-20261125-1/prototypes/pro/P36/P36-B-20261125-1/VERIFICATION.md). Use a new `.runtime/` output directory on every run. These links point to the delivered Studio branch, including from a standalone report copy.

| Measurement | Result | What it establishes |
| --- | ---: | --- |
| Prototype tests | 84 passed, 0 skipped | Current Python software regressions; no native qualification |
| Labelled scorer cases | 20 | A fixed synthetic challenge set |
| Strict false passes | 0 / 16 invalid cases | Every required invariant/view is a blocking condition |
| Mean >= 0.90 false passes | 13 / 16 invalid cases | A deliberately weak aggregate threshold loses critical evidence |
| Valid controls admitted | 4 / 4 | Allowed diagnostic outfit/expression variation does not cause rejection |
| Drift descendants blocked | 6 / 6 | Turnaround failure cannot reach expressions, outfits, mesh, rig, toon or Unreal |
| Replaced-concept descendants blocked | 7 / 7 | Old acceptance and ancestry do not survive a changed anchor |
| Uncertain same-stage retry | Blocked | Resolution retains the same payload and prompt reference |
| Actual consumer file validation | Passed for 26 synthetic artifacts | Supplied Lumenfold schema/validator accepted real fixture hashes and sizes |
| Real generations / real owner acceptances / native imports | 0 / 0 / 0 | No end-to-end character outcome is asserted |

The baseline comparison is intentionally simple: the same diagnostic score, accepted at 0.90. It is **not a claim that the existing Studio uses this baseline**, and the 16 cases are not a representative real-world sample. Missing views, wrong eyes/hair, mirrored asymmetry, wrong proportions, stale evidence, duplicate media and nonfinite/boolean numbers exercise specific failure modes. There is no statistical confidence interval or production accuracy claim.

The known-limit case is part of the proof, not hidden from the results. Geometry outside the frozen colour regions changes while the proxy still passes. Its output remains `perceptual_identity_verified: false`; pending owner acceptance blocks progression. Real-world calibration must therefore use owner-labelled candidates, declared views and matched cameras, with per-trait false passes and false rejections reported. Acceptance is still required after any proxy result.

Repeated runs produced the same deterministic evidence, family, pack and handoff hashes. Host-specific timing and environment are separate. Timing measures an eight-stage metadata walk only, not disk reads, model inference, generation throughput, Blender or Unreal. No workstation speedup or 16 GB GPU fit is claimed.

The existing hosted Studio workflow also passed its full offline suite and repository validator for a source checkpoint: 7,321 tests, 124 skips, and 98 preset graphs / 194 pinned assets validated. Exact run/head/merge identities and any later check status are retained in VERIFICATION.md. A prototype test count is never presented as the full Studio suite.

## Implementation and consumer decisions

### Family and identity authority

The family is a sidecar over current Workspace identities. All active and historical receipts are validated, including scope and digests. Acceptance binds the entire payload: changing media, recipe, policy or ancestry invalidates the old attestation. The operational `record`, `next` and export paths recheck actual production bytes. A metadata-only `assess()` result is diagnostic and explicitly reports that bytes were not verified.

Production RGB anchors and candidates are remeasured from exact PNG bytes using policy-owned regions. Supported encoding is encoded sRGB with straight/opaque alpha and a fixed minimum coverage; unsupported colour/alpha encodings, embedded ICC profiles, animation and unsafe image sizes refuse. Ratios and named traits are disclosed as annotations. The metric is an audit-friendly proxy, not a face recognizer or colour-managed perceptual system.

Local `actor=owner` and evidence references are caller assertions. Content hashes are not signatures and cannot prove who approved a picture or whether approval has since been revoked. Before live adoption, the adapter must read actual Workspace acceptance/revocation and selected heads immediately before queueing/export. Uncertain upstream jobs with no output artifact remain authoritative in existing job history; the artifact graph alone cannot see them. Neither limitation is papered over with a fake acceptance or retry.

### Pack contract

The exporter validates the actual `lumenfold.pack/1` schema snapshot and preserves source, licence and commercial facts per file. It adds structured lineage only under the allowed root `x-studio-character-pipeline` extension. The existing consumer recursively interprets any key named `file` as a file reference, even inside an extension, so sidecar pointers use `family_sidecar` and `handoff_sidecar`. `models.ue` records a planned request; no native success is inferred.

All exports remain draft. Release-mode preflight additionally requires explicit intended-use clearance across every ancestor and refuses synthetic families. It does not publish or mark a character playable. The tool validates before creating a destination, writes the handoff marker last and refuses reuse of existing destinations. Consumer staging, interruption recovery, rollback and atomic promotion remain in issue #3175.

The exact schema SHA-256 is `9892f716abfff35a85088c5b5c798a8ae38ddbff50f1e67845f799c7af16a28a`; the live connector-read Git blob matched `fd00e2fb6de69b80b3b0756ab89fcbfb32945b37`. The supplied validator SHA-256 is `268588d7d01d09f9c597dce7c7dfafe050066586702676cfe633bad941af4de7`. Native format checks remain deliberately bounded: a renamed GLB must contain an actual decoded VRM extension to dispatch as VRM, but no header proves a useful skeleton, deformation, facial animation or valid Unreal material graph.

### Gaps found on the Lumenfold side

The current pack schema permits `commercial: unknown` even for playable metadata. Its validator establishes structure and optional file integrity, not identity or whole-chain rights. Existing cast metrics are useful diagnostics but do not impose this concept gate. Character-build warnings can coexist with successful commands, and some fighter checks report stretch/contact values without hard-failing on them. A printed success line therefore cannot replace named numerical and visual acceptance criteria.

Rigged VRM/GLB/FBX intake and raw geometry finishing are different paths. The joiner expects an armature and skinned mesh; feeding an unrigged generator GLB into that path does not create a game rig. Existing intake also needs stronger staging/rollback semantics before overwriting a live pack. Issue #3175 asks for exact concept/ancestry validation, live authority checks, unchanged file proofs, decoded native dependency checks, no uncertain replay and transactional publication. It is intentionally an open implementation plan.

### Independent review and hardening

Parallel agents reviewed the Studio contracts, researched existing routes/terms and exercised the implementation independently. Review produced concrete counterexamples; these were fixed and retested. The final focused review found no remaining blocker among the reviewed findings and independently passed all 84 tests.

Fixed cases include unmeasured production anchors, cross-stage measurement-cache overwrite, malformed quality evidence, explicit fixture provenance relabelled as production, private-root path bypass, incompatible colour encodings, Windows device paths, missing-media idempotent admission, diagnostic-view handling, renamed GLB-as-VRM dispatch and malformed inactive history. The prototype does not promise authenticated writers, a malicious concurrent filesystem, live queue enforcement, native correctness or perceptual identity recognition.

## First adoption decision

Start with **Sable A2 source resolution**, not a new image batch. The 20 November record provides a target and an acceptance pointer, but no exact bytes. Recover its separate portrait, matched body view, native source, textures, skeleton/motions and the scope of the original acceptance. The legacy slender pack, old BIBLE palette and a similarly named export are not substitutes.

The [ADOPTION.md](https://github.com/Chris0Jeky/local-asset-studio/blob/pro/P36-B-20261125-1/prototypes/pro/P36/P36-B-20261125-1/ADOPTION.md) proposal names Studio agents, `lf-characters-3d` and `lf-anime-look`, with runnable checks and target numbers. The first move is **0 to 1 exact A2 mapping recorded by P36**, then **0/8 to 8/8 realized stage receipts** only as the gates pass. Zero here describes this run's evidence, not the absence of existing project work. Real critical false-pass rate remains unmeasured; the target is zero observed failures on an explicitly counted held-out labelled set. The lane must record adoption or rejection; delivery alone is not adoption.

No third-party implementation or dataset was copied into the prototype. Python is PSF-licensed, installed Pillow 13 reports MIT-CMU (with historical PIL notices), and jsonschema is MIT. The copied schema is the owner's Lumenfold contract. Model, runtime, content, output and distribution rights are separate; the detailed research below records unresolved components rather than silently clearing them.

---

# Research: existing Studio semantics and the first 2D character plan

Research record, 25 November 2026. Repository baseline: `Chris0Jeky/local-asset-studio@0270760a`, inspected through read-only GitHub connector fetches. Lumenfold inputs are the supplied `lumenfold-context` records. All web sources below were accessed **2026-11-25**. This document proposes adoption; it does not register assets, submit jobs, download weights, modify runtimes, or claim native execution.

## Recommendation

Make **Sable A2** the first reference-resolution target, with **Kiri A4** an explicit alternative if the A2 evidence cannot be recovered. The 20 November coordinator order names these as accepted cast demos and specifically points to Sable's separate portrait for a near-eye read and the paired wide for the matched exchange. That gives a useful existing identity-check target. It does not identify exact media bytes and does not accept any new asset produced by P36.

Build the offline addition around existing Workspace asset/job IDs, source hashes, character cards, canon/study contracts, and a small revisioned sidecar manifest. Keep Production, Workspace storage, reference uploads, Review Desk and native adapters as the owners of their existing responsibilities. The next useful milestone is an anchored, inspectable first-character plan; broader model acquisition or another asset platform would add little to this slice.

## 1. Existing semantics to reuse

| Existing owner | Reusable contract | Boundary the P36 addition must retain |
| --- | --- | --- |
| `app/workspace.py` | Content-addressed bytes, asset IDs, jobs, output indexes, parent lineage, review, privacy, collections, reversible trash, metadata revisions. It also has a separate `asset_acceptances` table containing the exact asset/hash, use and reviewer. | Favourite, keeper, lineage, successful output and licence notes are not an acceptance for a particular use. A sidecar should point to these records, not copy a second authoritative library. |
| `app/characters.py` | A `character` Workspace card has one canon image selected by `asset_id` and SHA-256; body fields are `who`, `clothes`, `avoid`, optional `look_id`. Changing canon retains the replaced content as `previous_canon`. | The owner decided on 16 October that **any picture may be a canon regardless of review**. Canon means the chosen reference; it must not be relabelled accepted art. New pictures return to that canon rather than accumulating edits of edits. |
| `studio_workflow/asset_family.py` | Bounded read-only ancestry and optional direct-child projection over existing `assets.lineage`, plus output-specific recipe recall. Multiple parents stay multiple edges; missing/trashed records and cycles remain visible gaps. | Returns `observation_only: true`, `generation_submitted: false`, `media_bytes_verified: false`. It proves attribution, not current bytes, artistic equivalence or licence rights. Child reads scan at most 5,000 newest rows and return at most 20 children; a sidecar must not portray this as a complete reverse index. |
| Family recall | Uses the selected output's decimal seed and its uniquely matching submission's positive/negative wording. Baseline recipe is separate from effective output controls. | Missing/trashed assets, specialized native/tile/parallax jobs, unresolved submissions and divergent wording refuse. Recall is not reference staging or permission to Generate. |
| `scripts/character_study.py` and character-consistency architecture | Immutable identity/costume/representation/style facets; ordered typed reference hashes; named checks; draft/agent-selected/human-approved canon; deterministic cases; plan-wide attempt cap; exact-output reviews. Existing request v2 can scope canon text used in a prompt. | Approval hashes are integrity attestations, not reviewer authentication. Failed, cancelled, warmup and uncertain attempts consume budget. An uncertain submission blocks the case until reconciled; it is never a reason to submit again. |
| Existing media/native paths | Pixel-preserving crop/composition; explicit repair masks; Krita/Blender/Godot handoffs; accepted regions and source retention. | An export receipt is not engine playback or visual acceptance. Final layout-only work should reuse accepted pixels and never cause diffusion. |

**Recommended sidecar role:** relate an existing character-card/canon revision to named output roles such as portrait, front, side, back, expression, pose, costume, sprite sheet, and native source. Each realized member references the original Workspace identity, file SHA-256, job/prompt receipt and exact review/acceptance record when available. Planned roles have no pretend asset ID or fake hash. Family membership is an explicit semantic association; generation parentage alone does not establish identity retention.

Keep orthogonal evidence fields. A member may be generated, agent-inspected, unaccepted and terms-recorded simultaneously. Use the product-direction ladder only within its actual scope: planned → implemented → executed → reviewed → qualified → project-accepted; `cleared` remains a separate intended-use decision, never the result of moving along the visual ladder. In everyday summaries explicitly separate **generated**, **inspected/accepted**, and **licensed/terms assessed**.

### Integration caveat found in the real compiler

Do not claim that the current generic character-study handoff already expresses every proposed model route correctly. `_handoff_template` appends `Picture N [role]: take… Ignore…` wording designed around Qwen picture tokens. Anima Reference Adapter instead asks for scene-only prompts without repeating identity/outfit tags. `prompt_scope` v2 reduces canon text but does not remove that appended wording. The compiler also handles `reference_slots` or a single `reference`; Klein Combine additionally uses a separate `last_reference` canon slot and an architecture-specific image order. A later runtime integration needs explicit prompt/binding verification for those routes. P36 can reuse the contracts now while leaving `submission_payload` absent and dispatch unavailable.

## 2. First character: exact evidence before new imagery

### What the records establish

- `packs/sable/pack.json` and `packs/kiri/pack.json` both say `status: draft` and `default_variant: slender`. That default is a rendering choice, not an owner preference. Sable's old Versus entries are only `posted`; Kiri's array is empty.
- Sable's old bible describes an original adult courier, age 25, black/violet/pink styling and twin chakrams. Kiri's old bible describes an original adult mechanic, age 24, silver/cyan hair, orange techwear and a wrench. These are useful historical identity documents.
- The later `charspec/specs/sable-a.json` uses a different measured magenta/gold palette and an owner-study source. It explicitly calls its numeric settings lab defaults. This is enough evidence to **avoid automatically combining old bible traits with Sable A2**. The same caution applies to Kiri's evolving biography and costume.
- `docs/ORDERS.md`, 20 November 04:19, calls Kiri A4 and Sable A2 accepted cast demos, without filenames/hashes. `pipelines/characters/fighter/ROUTE.md` separately records the owner's 19 November direction to build Kiri and Sable from two provisional images, without changing design or making cast art. These scoped records do not promote legacy manifests.
- The 14 November cast-image/study hold remains relevant to genuinely new 2D character studies. The later fighter instruction is narrower. Current offline planning is authorized; the plan must not convert either record into blanket generation permission.

### Reference intake and canon gate

On the workstation, resolve the exact A2 concept/reference receipt, separate portrait and relevant body view; retain their source location, provenance, bytes, SHA-256 and existing acceptance scope. Recover any matching native/model receipt separately. If the only evidence is a filename, label, old default or prose statement, keep the anchor unresolved.

Compare exact references for conflicts before writing visual invariants. Record observable face construction, hair masses and asymmetry, eye appearance, silhouette, costume construction, accessory placement and palette. Do not invent unseen rear construction. Keep `not_visible` or `uncertain` for required details that the source cannot establish. A chosen reference may be useful without being accepted; an approved production canon needs the appropriate owner attestation against the entire new canon hash. Existing approval of the A2 demo is an evidence pointer and may be carried only after its exact subject and scope are verified.

**Proposed initial family roles:** canonical identity image; close portrait; full-body source; independently reviewed front/side/back panels when those views exist; expression variants; one simple full-body pose; optional native model and engine receipt. Missing roles stay planned or unresolved. If all required views already exist, preserve and compose those pixels before proposing new images.

### Required checks for any new candidate

| Check | Acceptance condition |
| --- | --- |
| Identity | Face structure, hair shape/asymmetry, eye appearance and distinctive features agree with the exact anchor at matched crop scale. A similar colour scheme alone is insufficient. |
| Costume | Construction, layer order, side-specific details and prop counts agree with visible source evidence. Hidden details are explicitly unresolved. |
| Pose and camera | Requested view, crop and orientation are achieved; full-body tasks include head and feet. |
| Anatomy/contact | Visible hands, feet and prop contact are plausible. Sable's two rings must remain two distinct props with coherent contact where visible. |
| Style/colour | Rendering family and approved palette are preserved within a declared comparison context; unwanted saturation/eye drift is named. |
| Delivery | Dimensions, alpha expectations, files, hashes, source lineage and use are explicit. A review sheet is not an animation atlas or a rigging blueprint. |

Every required check must pass for selection/acceptance. A high aggregate score cannot hide one failed or unseen required identity feature. Agent inspection can reject, flag or select a candidate for review; it cannot manufacture owner art acceptance.

## 3. Small route portfolio, using existing presets

These are **planned choices for Sable**, grounded in existing route records. Historical times are contextual single-run evidence, not new benchmarks or performance promises.

| Role | Primary and meaningful fallback | Existing evidence and limitation |
| --- | --- | --- |
| Existing views and deliverable layout | Deterministic extraction/composition from exact already-reviewed media. | Strongest way to preserve pixels. It cannot reveal unseen geometry, create another pose, or elevate source acceptance. |
| Identity-conditioned portrait/simple scene | `anima-ref-adapter-turbo`; quality comparison with `anima-ref-adapter` (base v1.0). | Catalog records 6.3 s Turbo and 40.0 s base Studio examples on 1 November; HUMAN_TODO records the owner's 2 November acceptance of the presets as they were. No Sable A2 qualification follows from that. Official adapter limitations include detail loss, garment colour drift and weaker painterly-style transfer [W3]. |
| Ordinary pose/edit with explicit references | `combine-klein` (4B), only for its demonstrated ordinary pose range. `combine-klein-9b-skeleton` is a later fallback for a measured pose gap. | Catalog records 4B's simple lean success but failure on a deep bend, and third-reference costume leakage. 9B skeleton retains a drawn pose better in a small historical study. Neither guarantees precise identity or protected pixels. Image order must be verified against the current catalog/graph. |
| Missing turnaround proposal | `character-sheet-klein-9b` with its existing TripleView adapter, only after the view gap and new-study authority are explicit. | Front/side/back output already exists as a route; the recorded Studio job took 104.5 s and showed eye/proportion drift. Owner said existing sheets were usable, not that all future views are truthful. The author notes asymmetry/accessory/anatomy inconsistency [W8]. Do not use it to decide hidden costume canon. |

For the first new-image trial, propose **8 primary attempts** (Turbo vs base × portrait vs simple full-body scene × two seeds) and **4 shared reserve attempts**, with at most one repair per case. This is a proposed cap of **12 total image-producing attempts**, not a grant of execution authority. All warmup, failed, cancelled or uncertain attempts count. If warmup or failures consume reserve, fewer repairs remain. Start with batch size one and inspect the first paired case before spending the rest. Keep output settings and source identical where comparison is meaningful, while preserving each model's native sampling. Two seeds are a small screening study, not general consistency qualification.

Use the real Anima graphs as baseline: 832×1216, `er_sde` / `simple`; Turbo v1.1, eight steps, CFG 1, reference guidance 1; base v1.0, 30 steps, CFG 4.5, reference guidance 4.5, APG. The installed custom-node version/schema and full effective prompt need a read-only check before run. The author has not tested the full Turbo checkpoint in the current upstream card, while Studio has a specific historical local test; preserve that distinction. Avoid opportunistically adding unrelated artist LoRAs or background-removal models.

Qwen-Image-Edit-2511 is an Apache-2.0 alternative with an official consistency claim [W9], but the local one-reference route measured roughly 672 seconds and its historical character-pose route lost style/pose. Keep it outside this first small portfolio unless a measured gap justifies that cost. Qwen-Image 2.1 has different recorded terms/backend; do not transfer 2511's Apache label to it. WAI repaint remains a poor first identity route because of the recorded owner rejection of eye drift and unresolved component provenance.

## 4. Model, code and output terms are separate

Current official sources were read; installed files were **not** rehashed in this session. The following facts supplement the repository's historical evidence without changing its model library or owner decisions.

| Component | Current primary-source finding | Exact-local qualification remaining |
| --- | --- | --- |
| Anima Base v1.0 / Turbo v1.1 | CircleStone Labs Non-Commercial License v1.2 distinguishes models/derivatives from outputs. Section 2(e) permits output use including commercial uses; the current card explicitly lists concept art/assets for paid products. The card also names NVIDIA Cosmos derivative terms [W1, W2]. | Keep existing pin and intended-use position; this is not blanket clearance for all references or distributed models. The 1 November owner answer is already recorded and need not be reopened for this private plan. |
| Anima adapter v2 r64 | Creator card declares the weights a CircleStone-licensed Anima derivative; node code is Apache-2.0 [W3, W4]. | Adapter licence file could not be reopened through the web tool; the repository retains its pinned 1 November read at `b729afd0…`. Treat that distinction honestly. The node can fetch weights on first use, so verify the pinned local file before an authorized run; missing weights must not trigger an implicit download. |
| Anima compact encoder / Qwen VAE | Repository pin `anima-text` explicitly says its own licence is not confirmed; the Qwen VAE repackaging card declares Apache-2.0 [W12]. | Do not infer the exact repackaged 0.6B encoder's rights solely from the Qwen family name. Recheck provenance if use or distribution changes. |
| FLUX.2 Klein 4B FP8 | Official FP8 card and full model licence declare Apache-2.0; official Qwen3-4B card and its Comfy repackaging card also declare Apache-2.0 [W5, W6, W10, W11]. | Retain notices applicable to distributed model/code; source-image rights remain independent. Existing per-file hashes identify the intended installed bytes, not current host integrity. |
| FLUX.2 Klein 9B | Official licence is FLUX Non-Commercial v2.1. Section 2(d) permits commercial outputs, with restrictions including use of outputs to train competing models; section 2(e) requires filtering or review and applicable AI disclosure [W7]. | A non-commercial model licence is not the same as “all images must be non-commercial.” Record the actual use and terms rather than a blanket all-purpose approval. The Q6_K repackager and encoder still need exact revision/source accounting. |
| FLUX.2 VAE | BFL's official inference repo explicitly releases the autoencoder under Apache-2.0 [W13]. | Studio's `vae-flux2` pin currently has a local SHA but only a name/size match to upstream and no confirmed source-hash match. The new publisher statement does not prove those installed bytes are that autoencoder. Resolve this as a source-intake task before asserting route-wide clearance. |
| TripleView Klein9B v1 | Author card names Civitai Model License and points to its original listing [W8]. | The original listing could not be opened in this research. Do not guess commercial flags or redistribution terms. Leave source-specific clearance unresolved; this is a known limit, not a reason to alter the weights or blanket-ban private research. |
| Existing Lumenfold VRM/GLB/rendered sprites | Legacy pack entries record the pixiv VRM sample base, scripted edits and Anima concept lineage; `commercial: unknown` remains on the character outputs. Props have their own records. | A generated 2D reference, current model-licence summary or old pack default cannot clear the entire model/material/motion chain. Exact A2/A4 provenance may be different. |

### Exact model-library identities to carry forward

These are **recorded pins from baseline 0270760a**, not claims that files currently exist or were verified here.

| Pin | SHA-256 | Source revision in existing record |
| --- | --- | --- |
| `anima-base-v1-0` | `bd43b7cffe1ed1153d9c41e7beb2f18cb1273eafbaa3af3edd6a173dc90a006e` | Source URL uses `main`; historical terms refer to `f973fc41ec7545364ac9776c2440285f43ff2a30`. |
| `anima-turbo-v1-1` | `fba11953276b57edf59d1dc4f1857ac05aa079c56f982b4d7c20298d57d3f7eb` | Download URL pins `f973fc41ec7545364ac9776c2440285f43ff2a30`. |
| `anima-ref-adapter-v2-r64` | `71dda6079e18d354e16e3347bc49a9b710afd9495c378efbb833d30cac9cb81b` | `b729afd0c3307f27438df42697ccafaecf051d26`. |
| `flux2-klein-4b-fp8` | `97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6` | `5b4408e59397a4a37ccb46afe426d8ed86379441`. |
| `flux2-klein-9b-q6k` | `1cd667293607431e79c9e7e01ecf5c602bd00539c2c0f49d4817a62998b5fe98` | Existing source revision is mutable `main`; preserve exact digest and improve source snapshot later. |
| `tripleview-klein9b-v1` | `2db1f0bb7995e936b58011fb864b4f9909c3858548f2c8d8206514f06694454e` | `3dc4295163dacc924d213168d67bf16850fd954f`. |
| `vae-flux2` | `868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3` | Source attribution unresolved despite recorded local digest. |

## 5. Gates and remaining adoption work

1. **Finish the offline slice now.** Implement/validate the sidecar and plan without touching app/catalog/runtime state. Map named roles to existing IDs; keep planned entries explicit and strict. Reuse source-path and JSON bounds, reject duplicate IDs/roles where ambiguous, detect cycles/stale references and preserve privacy/workspace boundaries.
2. **Resolve the exact anchor on the workstation.** Recover A2 evidence and bind exact reference hashes. Do not substitute the legacy slender pack or silently switch to Kiri. Missing bytes or ambiguous approvals stop promotion into a generation-ready plan, not the current offline work.
3. **Resolve new-study authority only when execution is concrete.** If proposed work is new 2D cast art, retain the 14 November hold as an owner-run gate. The 19 November fighter authorization remains scoped to its two supplied images. No new request should ask the owner again about Anima terms already answered, generic model installation, or memory purchase.
4. **Read-only route preflight.** Compare catalog entry, graph bytes, model/encoder/VAE/adapter hashes, node package revision, runtime/backend identity, reference order/crop, batch size, and effective prompt. Refuse missing models and unverified binding rather than replacing a checkpoint or installing a node. Preserve queued/manual work.
5. **Use normal Production for a later authorized trial.** Reserve a shared cap before each expensive attempt, save intent and prompt ID, collect actual outputs, and reconcile uncertainty without duplicate work. The offline sidecar does not enforce a live budget or queue lock.
6. **Review and package.** Review each output against every hard check and exact hash; retain failures and intermediate candidates. Owner acceptance names the concrete use. Publish/export only the selected intended members with source receipts; native save/reopen and engine playback require their own real evidence.

The latest Studio state still lists owner-run #313 acceptance, configured-native follow-ups (#1983/#2026), #1864 retention/native journey work, paused #1923 illustration direction, parallax usability and the island default-switch decision. These are existing open boundaries; this plan does not close them or claim the historical full-suite/native receipts qualify P36.

### Freshness sweep

A bounded 60-day GitHub repository search (`character-consistency created:>2026-09-26 sort:stars-desc`), current Hugging Face image-to-image/Anima trending lists and Comfy registry search were inspected. They expose newer/experimental candidates, including character-sheet variants and extra reference/control nodes. No new candidate is promoted: current installed routes address this first bounded identity test, and a trending entry supplies neither AMD evidence, reproducible pins, licence assessment nor accepted outputs. Primary cards also now mention FLUX.2 9B KV and experimental dynamic sheets; neither is the installed route named above. This is discovery context, not an exhaustive market survey.

## 6. Sources

### Repository sources

All Studio facts above were read at baseline `0270760a`: `AGENTS.md`, `CLAUDE.md`, `CURRENT_STATE.md` head, `docs/PRODUCT_DIRECTION.md` priorities 1–5 and evidence states, `docs/STATUS.md`, `docs/OPERATIONS.md`, `HUMAN_TODO.md`, `presets/catalog.json`, `app/workspace.py`, `app/characters.py`, `studio_workflow/asset_family.py`, `docs/asset-family/README.md`, `docs/character-consistency/ARCHITECTURE.md`, `docs/character-consistency/README.md`, `research/character-consistency/canon.example.json`; additional connector reads: `scripts/character_study.py`, `models/library.json`, `docs/ANIMA-LICENCE-POSITION.md`, and the exact Anima base/Turbo, Klein Combine and TripleView API graphs. Example immutable-revision URL: [Studio catalog at 0270760a](https://github.com/Chris0Jeky/local-asset-studio/blob/0270760a/presets/catalog.json).

Lumenfold supplied records: `packs/sable/{BIBLE.md,pack.json}`, `packs/kiri/{BIBLE.md,pack.json}`, `pipelines/characters/charspec/specs/{sable-a,kiri-a}.json`, `docs/ORDERS.md`, `docs/lanes/lf-characters-3d.md`, `docs/lanes/lf-anime-look.md`; fighter authorization nuance cross-checked with the parallel contract reader. Local references are source records, not newly verified workstation media.

### Official/publisher web sources — all accessed 2026-11-25

| ID | Source | Scope |
| --- | --- | --- |
| W1 | [CircleStone Anima card](https://huggingface.co/circlestone-labs/Anima) | Versions, recommended sampling, output/model distinction, paid-product asset examples, Cosmos derivative notice. |
| W2 | [Anima LICENSE.md](https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md) | CircleStone Non-Commercial v1.2, sections 1 and 2; displayed licence-file commit `6e0b2da`. |
| W3 | [ElectronGirl Anima Reference Adapter card](https://huggingface.co/ElectronGirl/anima-ref-adapter) | Weight terms, required custom node, native prompt grammar, compatibility, limitations, first-use download. |
| W4 | [ArcAnima custom node repository](https://github.com/ArcAnima/ComfyUI-Anima-Ref-Adapter) | Apache-2.0 code licence and distinct weight dependency. |
| W5 | [BFL Klein 4B FP8 card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) | Exact deployed model family, Apache-2.0 declaration and model limitations. |
| W6 | [BFL Klein 4B licence](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/main/LICENSE.md) | Apache License 2.0; displayed licence-file commit `6dfcebf`. |
| W7 | [BFL Klein 9B licence](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/blob/main/LICENSE.md) | FLUX Non-Commercial v2.1, model/output distinction and restrictions; displayed licence-file commit `07c5ac6`. |
| W8 | [Alissonerdx CharacterSheet card](https://huggingface.co/Alissonerdx/CharacterSheet) | TripleView base/model match, limitations, Civitai licence pointer. Original [Civitai listing](https://civitai.com/models/2764727/tripleview) failed to open; exact original permissions remain unresolved. |
| W9 | [Qwen-Image-Edit-2511 card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) | Apache-2.0 and publisher consistency claim; distinct from Qwen-Image 2.1. |
| W10 | [Qwen3-4B card](https://huggingface.co/Qwen/Qwen3-4B) and [Qwen3-8B card](https://huggingface.co/Qwen/Qwen3-8B) | Upstream encoder model licence declarations; not a substitute for exact repackaged-file provenance. |
| W11 | [Comfy-Org Z-Image-Turbo repackaging card](https://huggingface.co/Comfy-Org/Z-Image-Turbo) | Apache-2.0 and the `qwen_3_4b.safetensors` file role. |
| W12 | [Comfy-Org Qwen-Image repackaging card](https://huggingface.co/Comfy-Org/Qwen-Image) | Apache-2.0 and `qwen_image_vae.safetensors` role. |
| W13 | [BFL official FLUX.2 code repository](https://github.com/black-forest-labs/flux2) | Apache-2.0 inference code; explicit separate Apache-2.0 autoencoder release; 4B/9B licence distinction. |

Freshness discovery: [GitHub character-consistency query](https://github.com/search?q=character-consistency+created%3A%3E2026-09-26&type=repositories&s=stars&o=desc), [HF image-to-image trending](https://huggingface.co/models?pipeline_tag=image-to-image&sort=trending), [HF Anima trending](https://huggingface.co/models?other=anima&sort=trending), [Comfy registry candidate](https://registry.comfy.org/publishers/raspie10032/nodes/comfyui-rs-multicharacter-sampler). These sources support discovery only; their claims were not treated as qualification.

**Evidence statement:** no generations, model downloads, runtime mutation, media inspection, native applications or engine playback were performed by this research task. That research task wrote only its notes; the enclosing implementation run separately created and tested procedural software fixtures.

---

# Research: 3D route, finishing and rights

Research supplement, **2026-11-25**. Read-only evidence: Studio baseline `0270760a`, supplied Lumenfold records, and official sources below. This extends the 2D research above; it changes no repository, runtime, model installation or native project. No image, mesh, rig, render, engine import or playback was executed. All new P36 members remain **planned and unaccepted**.

## Route decision

**Resolve and reuse Sable A2's existing geometry, textures and native source first.** The accepted-demo owner record is an evidence pointer, not a file manifest. Recover the exact concept, mesh/native project, material images, rig, animation dependencies and accepted frame receipts, hash each, and connect them to the existing Workspace/family identities. Do not substitute the old `slender` pack, a similarly named Tripo export, Kiri A4, or a new generated reconstruction when an A2 source is missing.

The existing Lumenfold fighter route supplies concrete finishing tools. It describes Tripo HD mesh intake, Blender reduction/UV preservation, deterministic Manny skinning, AnimeLook materials, and GroupSwordMotion proof clips. It does **not** establish that the current accepted A2 used every one of those components. Its route-level Tripo example is a yard-pell stand-in. Recover the A2 build receipt before assigning that provenance.

If existing A2 geometry cannot satisfy a documented requirement, the **single proposed local neural fallback is the already catalogued `trellis-rgba`**. It is an explicitly unqualified candidate for this character. It has a historical Studio execution note, not a fresh Sable identity, deformation or commercial-clearance result. A missing source asset leaves a gap in this plan; selecting the fallback requires an explicit new route decision and the applicable owner-run gate. Current offline work proceeds without GPU/native execution.

## Eight-stage route, evidence and rights checklist

| Stage | Proposed route and actual tool/model | Next evidence required before advancing |
| --- | --- | --- |
| **concept** | Anchor the exact accepted Sable A2 image. For a later authorized new study, use existing Anima Turbo v1.1 + Reference Adapter v2 r64; Anima Base v1.0 is the quality fallback in the main report. | Exact asset ID/hash, owner acceptance scope/date and original generation/reference receipts. Preserve the Anima model/output distinction and unresolved exact compact-encoder provenance already recorded. Acceptance of A2 does not accept a newly generated picture. |
| **turnaround** | Reuse attributable accepted views; deterministic views of the resolved A2 native model can supply future native evidence. A missing-view 2D proposal uses existing `character-sheet-klein-9b`/TripleView only after authority and terms resolve. | Front/side/back bytes and camera definitions, face/proportion/silhouette/asymmetry review, and explanation of which unseen regions are proposals. Resolve original TripleView terms and its FLUX.2 Klein 9B dependency. A generated back view cannot silently define costume canon. |
| **expressions** | Reference-conditioned Anima proposals for named expressions after the new-study gate; map accepted expressions to the native face separately. | Per-expression identity checks and exact reviewed bytes; native blendshape/morph inventory, neutral pose and engine playback. The fighter route says `dump.py` drops morph targets: a sheet does not establish a functioning face rig. Record face-template rights if geometry is transplanted. |
| **outfits** | Preserve A2's accepted default. Later named costume variants use the existing identity-preserving edit route and explicit masks/protected regions; each variant stays a distinct family member. | Owner-selected costume scope, approved views, exact texture/mesh dependencies and protected-region review. New accessories/base parts need their own provenance; inherited character membership is not inherited acceptance or rights. |
| **mesh** | Primary: exact existing A2 GLB/FBX/Blender source and textures. Finishing: existing Blender/fighter reduction and UV-preserving path. Contingency only: `trellis-rgba` with the diffusion, shape, texture and vision files below. | Hash geometry and every texture; recover generator/model/plan receipt if applicable, base/avatar terms and edit provenance. Inspect front/side/back silhouette, face, fingers, open coat, separate parts, UV seams, texture colour and unwanted surfaces. Record tris/scale/surface error; do not call an unrigged textured GLB game-ready. |
| **rig** | Existing A2 rig first. If a build is necessary, existing `fighter.py` fits `SKM_Manny_Simple`/`SK_Mannequin` and transfers template weights; Sable's route uses GroupSwordMotion **OneHandedV6** clips. No learned-rig model is added. | Exact template/skeleton/weight hashes and Epic source entitlement; exact motion product/version, acquisition and licence. Measure p99.9 edge stretch <2, left-behind vertices <100 and grip <20 mm, plus shoulder/hip/hand pose review. OneHandedV6 is a proxy for twin rings, not a qualified dual-chakram moveset. Require per-clip contact/frame and native playback receipts. |
| **toon** | Existing AnimeLook `M_AL_Character` unlit cel ramp, inverted-hull outlines and pinned palette/maps. Optional existing KawaiiPhysics/VRM4U only when the actual A2 path needs them. | Exact local code/material versions, source texture and any face-shadow-map provenance, inspected native turntable under agreed light/camera, outline/face/hair/cloth checks. Preserve authored look; inherited plugin licence does not license the avatar, material inputs or motions. Resolve actual missing chains/constraints rather than treating old Kiri tests as Sable proof. |
| **unreal** | Accept Studio handoff readiness, then export the draft pack/sidecars. Consumer import follows under issue #3175 with pinned Unreal/plugin builds. | Before export: complete file/dependency hashes, accepted required ancestors, matching identity evidence and handoff-contract check. After export, a separate mandatory consumer receipt must bind actual native import, resolved material/skeleton/animation paths, inspected turntable/action clip and intended-use acceptance. Engine EULA, plugin/base/motion rights and raw-pack versus embedded-use terms remain separate. Eight prototype receipts or manifest validation cannot stand in for this later native gate. |

These are future evidence requirements, not claims that all eight stages are presently runnable. The 14 November hold remains a gate for genuinely new cast 2D studies; the later fighter order is scoped to the supplied images. None of this reopens already answered Anima terms or blocks the authorized offline P36 implementation.

## The existing image-to-3D fallback, precisely

`presets/catalog.json` already contains `trellis-rgba`; its graph is `workflows/api/trellis-rgba-api.json` at baseline `0270760a` (Git blob `d37333ad0368ae6de11a66d55551901b530265f7`). It crops an explicit RGBA foreground, conditions through DINO-NAF, samples sparse structure, 512 shape and texture latents, decodes them, unwraps UVs, bakes a 1024 texture atlas and saves a textured GLB. Its material wiring includes base colour, metallic and roughness. No skeleton, animation, clean deformation topology, native toon look or accepted hidden surfaces follows automatically.

The following are **recorded library pins**, not hashes freshly verified on the owner's machine:

| Role | Installed file named by the graph | Source revision and SHA-256 from `models/library.json` |
| --- | --- | --- |
| Geometry/texture diffusion | `trellis_2_int8_convrot.safetensors` | `Comfy-Org/TRELLIS.2@463441b1c32829ee876e4f297dcfff533cb357a7`; `d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31` |
| Shape decoder | `trellis_2_shape_vae_bf16.safetensors` | Same revision; `de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4` |
| PBR texture decoder | `trellis_2_texture_vae_bf16.safetensors` | Same revision; `714e5ebf094a610e12a8e3b5175c18a62f37f6ea4218acb6073644456b73ab0e` |
| Vision conditioning | `dino_v3_L_naf_fp32.safetensors` | `Comfy-Org/Pixal3D@b35ffffa61fa02a86c377d94b755d9fe65d185d9`; `4ad2ec4e0879a5b5b04cd97325cc37da954a7b6edca5170b86510f17f2b2290f` |

Microsoft describes TRELLIS.2 code and model weights as MIT; Comfy's TRELLIS.2 repack also declares MIT [S1–S3]. The **vision file is a different dependency**: Comfy's Pixal3D page declares MIT, Tencent's original page explicitly preserves third-party terms, and Meta's DINOv3 uses the custom DINOv3 License rather than MIT [S4–S6]. Exact DINO-NAF derivation and applicable terms still need a source receipt; the local `license: mit` label is insufficient to clear that chain. Preserve any applicable model/code notices and distinguish them from generated asset and input rights.

The upstream TRELLIS.2 implementation states Linux/NVIDIA with at least 24 GB VRAM and testing on A100/H100 [S2]. Studio instead records experimental Radeon/Native Torch support and a local CPU UV patch. That historical integration evidence is not upstream AMD support or a current character qualification. Before any future authorized test, verify exact local graph/node/patch revisions and file integrity; absence must not trigger a model download. Require an already reviewed RGBA cutout, with source and mask provenance. This plan does not silently switch to the catalog's automatic-cutout route or add BiRefNet.

## Finishing and rights distinctions that must survive adoption

- **Blender and local code:** Blender uses GNU GPL; Blender explicitly distinguishes the application's licence from artwork created with it [S7]. Record the actual Blender build plus local `fighter.py`, `dump.py`, `charspec` and AnimeLook revisions. Their ownership/licensing cannot be inferred from Blender's GPL or a neighbouring MIT model. No source-distribution licence for that project code was established in this snapshot.
- **Tripo/base geometry:** if the recovered A2 receipt identifies Tripo, preserve original job/model/version, generation date, account plan and the terms applicable to that output. A contemporary generic Tripo page cannot retrospectively clear an unknown export. If the route used pixiv `VRM1_Constraint_Twist_Sample` or transplanted face/hands, recover the actual avatar file metadata and `intake/ledger.jsonl` entry. The route's “modification allowed” note does not establish every distribution/commercial permission. Legacy pack `commercial: unknown` stays unknown.
- **Template and motion:** `fighter.py` explicitly reads Epic sample `SKM_Manny_Simple.fbx` and transfers body weights. This requires base-content provenance, not merely permission to reuse bone names. GroupSwordMotion OneHandedV6 needs its own exact acquisition/licence record. Do not add Paragon Countess, Yura or paid rigging as implicit substitutions.
- **Plugins and engine:** KawaiiPhysics code is MIT; VRM4U code is MIT, with separately documented dependencies including assimp's BSD licence [S8–S9]. Retain exact installed-version notices. Unreal's proprietary EULA governs Engine Technology; marketplace/Fab content has separate terms, and designated UE-only content has its own limits [S10–S11]. None of these licence labels conveys rights to all models, motions or raw redistributed packs.
- **Historical proof:** the fighter route's dense stand-in had 167 left-behind vertices against a <100 bar and 24 mm grip error against <20 mm; another body's animation-pose stretch reached 2.57. These results identify remaining checks. They are neither Sable tests nor a passed production gate.

Maintain independent records for **generated**, **inspected/accepted**, and **licensed/intended-use assessed**. A failure or uncertainty in one dimension must remain visible and prevent the corresponding next adoption claim. This research does not make a whole-chain clearance decision.

## Sources

All external sources accessed **2026-11-25**. Dynamic upstream pages establish research facts; capture the exact licence versions associated with installed files before executing/distributing them.

- Local: Studio [catalog](https://github.com/Chris0Jeky/local-asset-studio/blob/0270760a/presets/catalog.json), [TRELLIS graph](https://github.com/Chris0Jeky/local-asset-studio/blob/0270760a/workflows/api/trellis-rgba-api.json), [model pins](https://github.com/Chris0Jeky/local-asset-studio/blob/0270760a/models/library.json); supplied Lumenfold `docs/ORDERS.md`, `pipelines/characters/fighter/ROUTE.md`, `fighter.py`, `docs/lanes/lf-anime-look.md` and legacy Sable/Kiri packs. The exact A2 media/ledger was not supplied.
- S1: [Microsoft TRELLIS.2 licence](https://github.com/microsoft/TRELLIS.2/blob/main/LICENSE).
- S2: [TRELLIS.2 upstream implementation and requirements](https://github.com/microsoft/TRELLIS.2), [official model card](https://huggingface.co/microsoft/TRELLIS.2-4B).
- S3: [Comfy TRELLIS.2 repack](https://huggingface.co/Comfy-Org/TRELLIS.2).
- S4: [Comfy Pixal3D repack and encoder listing](https://huggingface.co/Comfy-Org/Pixal3D).
- S5: [TencentARC Pixal3D original card and third-party terms statement](https://huggingface.co/TencentARC/Pixal3D). Its linked HF `NOTICE` path returned 404 during research; no missing notice was reconstructed.
- S6: [Meta DINOv3 licence](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md), dated 2025-08-19.
- S7: [Blender licence explanation](https://www.blender.org/about/license/?wvideo=akzb57a5z3) (official indexed text; unparameterized page returned 403).
- S8: [KawaiiPhysics MIT licence](https://github.com/pafuhana1213/KawaiiPhysics/blob/master/LICENSE).
- S9: [VRM4U MIT licence](https://github.com/ruyo/VRM4U/blob/master/LICENSE), [dependency licence table](https://github.com/ruyo/VRM4U).
- S10: [Unreal Engine EULA](https://www.unrealengine.com/eula/unreal), especially Licensed Technology versus separately licensed content.
- S11: [Epic Content Licence Agreement](https://www.unrealengine.com/eula/content), applicable only when identified as the governing content agreement; retrieve the actual Fab/Marketplace acquisition terms for each asset.

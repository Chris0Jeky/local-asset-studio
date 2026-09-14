# Reference intelligence: a shorter route from pictures to a useful image

Research/design and first implementation, 14 September 2026. Reconciled against
main `4789e0a56c99226d5b2b2cb061ec52478ffde3eb` and open PR #331. This extends
#21, #35, #36, #37, #38 and #232; repair stays under #243. It does not introduce a
model registry, queue, persistent document store or new painting application.

## Product decision

The target interaction is: add pictures, say something brief such as “same
feeling, use this pose”, see a compact interpretation, optionally change it,
then generate through the existing Studio. Model names, conditioning graphs and
prompt syntax belong behind an expandable explanation, not in the required path.
ChatGPT Images 2.5 is an interaction and output-quality benchmark, not a claim
that its proprietary system can be reconstructed by wrapping an open model [S1].

A useful first screen has the reference strip, the short instruction and one
**Analyze references** action. Analysis returns a sentence describing the intended
image and per-picture chips such as “appearance”, “pose” and “style”. The chips are
editable. Opening a chip reveals observed description, selected traits, exclusions,
uncertainty and source metadata in different sections. Ask at most one important
question in the ordinary flow; keep other nonblocking assumptions inspectable.
There must also be a no-helper/manual path. Merely adding more mandatory forms
would recreate the problem reported in #278.

## What already exists

The current Style + Pose recipes have a one-to-three-picture style board with
averaged IP-Adapter embeddings and a separate pose input. Their WAI/YumeFlux/Nova
workstation evidence is in CURRENT_STATE.md and experiments/curated/style-pose-matrix/.
Do not replace these with an untested universal editor or describe them as absent.
Qwen one/two/three-reference recipes provide a different instruction-edit route.
Prompt Lab already has typed intents, model-specific compilation, proposals,
metadata inspection and an optional loopback Ollama helper. Setup proposals and
shared drafts already belong to studio_workflow. #328 records the remaining board
handoff assumptions; #331 is a separate character-review line and is not modified.

The missing link is an approachable interpretation of the whole reference set,
with useful editable descriptions and honest routing to these capabilities.

## Three separate records

**Recovered metadata:** bytes, source hash, container fields, embedded prompts and
reachable graph evidence from recipe_intake/graph_provenance. It is an imported
claim, not necessarily authentic history. Never execute an imported graph merely
because it was embedded in a picture. Missing metadata stays missing.

**Visual observations:** what the local vision model saw in the supplied analysis
derivatives: description, descriptive tags, subject/action/style/palette/camera
facets and unknowns. Retain original and derivative hashes. An observation cannot
recover a unique original prompt, seed, checkpoint, LoRA, artist or hidden body
part. A valid JSON schema does not prove its content true [S2].

**Reviewed intent:** what the user chooses to transfer or changes deliberately.
Keep original observations immutable; edits become attributed user descriptions.
A style reference must not automatically copy its person/costume. A pose reference
must not silently replace identity. Tags are optional vocabulary suggestions,
not verified model triggers or an invitation to mix derivative-specific syntax.

## Implemented contract

`studio_prompt/reference_analysis.py` supports one to four images, enough to
analyze a three-image board plus a separate pose together. The cap is explicit:
no montage, truncation or hidden extra model calls. Analysis capacity and a
generator's native slot capacity are separate; four analyzed images cannot be
stuffed into a three-slot Qwen recipe.

`new_request(brief, references)` accepts short or empty text and per-image
`role_hint: auto`. Explicit hints must survive model analysis. `make_report`
validates exact image coverage/order, roles, bounded facets and uncertainty,
and binds original/analysis identities. `review_template` suggests only compatible,
non-uncertain traits and selects no tags automatically. `draft(report, review,
workspace)` rechecks every original and produces a **new** standard CreativeIntent
plus transfer provenance. It does not overwrite an existing draft or circumvent
its locks. Applying this new intent to an existing project remains an expected-
revision command under #38/#232, not a direct file replacement.

The review object can change a selected description through `overrides`, for
example `{"palette": "cool blue and silver"}`. The old observation remains in the
report. An uncertain facet needs an explicit user description before it enters
the new intent. Unknowns/questions survive projection. Oversized combined facets
fail instead of silently truncating a constraint. Hashes establish integrity,
not reviewer authentication or artistic correctness.

This first commit supplies the pure contract and tests. The next slice adds an
explicit local analysis operation and CLI through the existing helper boundary.
There is no new GUI or live inference in this commit.

## Generation route selection

Choose by requested control, not a universal “quality” score:

| Intended change | First route to qualify | Important boundary |
| --- | --- | --- |
| Match look while following a pose | Existing Style + Pose board | Appearance embeddings are not exact subject/identity locks. Inspect the pose guide before applying it. |
| Combine subject/outfit/background instructions | Existing native multi-image Qwen route | Semantic editing can still drift. Keep each native slot and preprocessing transform explicit. |
| Preserve a known character | Approved canon plus compatible appearance/pose route | A style match does not establish identity fidelity. Re-anchor to the canon rather than accumulating generated drift. |
| Repair a hand or contact | Existing scoped repair with effective mask and protected compositor | Correctness inside the patch needs review; exact outside pixels alone do not prove a useful repair. |
| Repeat a sheet or layout | Existing crop/layout/finishing tools | Do not regenerate good figures or typography just to rearrange them. |

Qwen-Image-Edit-2511 documents multi-image input and improvements to consistency
and geometric edits [S3]. That is a candidate capability, not evidence that every
quantized/accelerated configuration matches its native schedule or fits this PC.
IP-Adapter exposes distinct style/composition controls [S4]; these are still not
interchangeable with geometric pose/depth guidance or a final pixel-write mask.
Use the actual registered graph, model family, reference count and preprocessing
contracts from #21/#34/#232. Show unsupported controls rather than quietly omitting
them. Do not transplant published sampling numbers into the installed Lightning
path without an independently budgeted comparison.

## Analysis and resource ownership

Start with one already-installed local vision helper, not a new model shelf.
Qwen3-VL-4B-Instruct is an inspectable primary-source candidate [S5]; its model
card and upstream hardware examples do not certify the user's Windows/Radeon
runner. Ollama documents image input with structured output [S2]. Validate both
schema and semantics, and retain the exact installed model digest, prompt template,
input derivatives, call count, latency and failure outcome.

The current helper's workspace lock and idle confirmation are not a global GPU
reservation. An explicit operator-run CLI can reuse that boundary honestly; an
**Analyze** button must wait for #35/#178 coordinator admission. Do not expose a
web endpoint that turns an untrusted `idle_confirmed: true` into resource authority.
Analysis should finish/unload before image generation, and cached descriptors
should avoid re-analysis of unchanged inputs. Actual unload and available RAM,
Windows commit and VRAM need observations; `keep_alive: 0` is only a request.
There is no automatic hosted fallback, model pull or shared Comfy/ROCm upgrade.

## Anatomy/composition passes

Do not run a generic face/hand detailer on every output. Reuse #66's calibrated
rubric and #243's repair plan: identify the affected instance and visible defect;
distinguish occluded, out-of-frame and ambiguous anatomy; propose a small context
crop plus explicit writable/protected regions; generate a bounded candidate;
compare intended change, identity, contacts and protected pixels separately.
When the same defect persists, change the hypothesis (context, mask, authored
pose/depth/hand geometry or route) rather than hiding an unlimited reroll loop.
A broken hand estimate must not automatically become authoritative ControlNet
geometry. Multi-person contacts need joint scope and instance-specific references
under #249. Global relighting/upscale is a new derivative, not an exact-pixel repair.
The proposing model never approves its own result. #250 owns finite escalation;
#257 owns held-out/fault evidence. This work adds no repair allowance or critic.

## Implementation sequence and acceptance

1. **Interpret/review contract** (this slice): new module plus 19 offline tests,
   including all image IDs, explicit role hints, role leakage, edit provenance,
   uncertainties, stale review/source and no execution authority.
2. **Executable local analysis:** extend the existing helper mode without another
   lock/queue; strip paths/metadata from model input; one bounded structured call;
   CLI request/inspect/analyze/review/draft. Test real PNG preparation, fake
   loopback transport, response loss, invalid output, caches and no auto-retry.
3. **One shared UI vertical slice:** reference chips, one explanation and optional
   text edits over existing #38/#232 commands. Compare-and-swap against current
   draft/source/template, board-aware binding, explicit Generate, real browser
   tests at desktop/390px and keyboard. Reads/import/analysis completion do not
   submit generation. #328's board-specific handoff remains a prerequisite.
4. **Qualification:** under #37/#313 choose original authorized references and a
   finite separately registered campaign. Compare unchanged short prompt,
   concise manually clarified prompt and assisted intent with the same actual
   route/inputs. Keep all rejects. Do not claim local artistic quality from tests.

Use a held-out set with at least: empty prompt; “same vibe”; style board plus pose;
identity plus different outfit; conflicting palettes; two figures with contact;
already-correct hands; and legitimate occlusion. Split by source/canon, not adjacent
crops. Count accepted distinct tasks, wrong-identity/pose/style failures, clarification
turns, user edits, actual attempts, total waiting and cleanup time. Report assumptions
and remaining uncertainty, not a single opaque aesthetic score. Existing #72's
frozen design and HUMAN_TODO q-7/q-25/q-26 are unchanged.

## Verification scope

The 19 contract tests passed in an isolated Python 3.13 source subset, using the
exact main schema.py blob `d5170021c9bfb6537dd2587c67fb0b79bcc183b8` (Git hash
verified). The fixtures intentionally use tiny byte artifacts for hash/review
contracts, not pictures and not visual-quality evidence. Git transport was not
available in this execution container; full repository and validator results must
come from the PR's hosted checks. No local workstation, user images, GPU, model,
Comfy queue, creative decisions or runtime configuration were touched.

## Primary sources (accessed 14 September 2026)

- **S1:** OpenAI, [Introducing ChatGPT Images 2.5](https://openai.com/index/introducing-chatgpt-images-2-5/).
- **S2:** Ollama, [Structured outputs, including vision](https://docs.ollama.com/capabilities/structured-outputs).
- **S3:** Qwen, [Qwen-Image-Edit-2511 model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511).
- **S4:** cubiq, [Style and composition transfer](https://github.com/cubiq/ComfyUI_IPAdapter_plus/discussions/376)
  and [reference implementation](https://github.com/cubiq/ComfyUI_IPAdapter_plus).
- **S5:** Qwen, [Qwen3-VL-4B-Instruct model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct).

These are source-reviewed leads, not installed versions or new license decisions.

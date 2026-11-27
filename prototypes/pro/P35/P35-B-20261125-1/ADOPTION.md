# Adopting P35 reference qualification in the existing Studio

Task: **P35-B-20261125-1**. Source baseline: **0270760a**. This package is a prototype beside the existing Studio. Its new image evidence remains **planned / unreviewed**. Software checks, source inspection and historical receipts do not establish a successful owner run, a Keep decision, project acceptance or licence clearance.

The adoption goal is measurable: **at least +15 percentage points in first-pass owner Keep rate against a frozen paired baseline**, with no pose-family regression, no concealed required-axis failure, **zero uncertain resubmissions**, and **zero metric–owner contradictions for any metric allowed to screen**. That is a target for a later observed campaign, not this implementation's result.

## What already exists, and who owns the next change

| Existing owner | Responsibility to retain | Native adoption work |
| --- | --- | --- |
| `studio_workflow/qualification.py` — `inspect_route`, `inspect_repository` | Static graph, catalog, model, node and runtime provenance. | Feed its exact source identities into behavioral receipts; keep static qualification separate from output quality. Do not replace this module with the prototype's similarly named file. |
| `presets/catalog.json`, `models/library.json`, `workflows/api/` | Existing preset IDs, installed component identities and native graphs. | Keep the four current graphs unchanged. Resolve model/auxiliary provenance gaps explicitly. A different quantization, LoRA, renderer or runtime receives a different route identity. |
| `app/references.py` — `compile_references`, `image_record`, `apply_drawn_pose_sidecar` | Reference order, uploaded byte identity, native preprocessing and drawn-guide lineage. | Project identity/costume/pose/style roles into the route's actual slots, retain corrected-guide bytes and renderer, and refuse unsupported facets or source substitution. Semantic roles are requested behavior, not proof of separation. |
| `studio_workflow/pose_route_contract.py`, `studio_workflow/pose_screening.py` | Corrected-pose route mechanisms, representation, detector behavior, bindings and the existing 48-cell protocol. | Reuse the canonical contract. Klein geometry consumes a precomputed skeleton; SDXL receives a precomputed guide with detector bypass. Coordinate P35 scope with #446 instead of expanding or duplicating its existing campaign implicitly. |
| `app/combine_plan.py` — `stages`; `app/server.py` — `Studio.prepare` | Native recipe intent and preparation. | Preserve current control/reference binding semantics, template hash, full prepared graph and model/input hashes. Source-subset agreement is necessary but does not prove the running server's schema. |
| `app/production.py` — `Production.create`, `start`, `_run_comparison`, `get` | Comparison projects, generation reservations, ordered stage execution and retained attempt/job/prompt evidence. | Continue to create and start bounded comparisons here. The prototype runner is an API adapter, not another queue or ComfyUI worker. |
| `app/server.py` — `host_commit_preflight`, `_pre_submit_commit_check`, `_run_generation`; `app/backends.py` | Backend identity/readiness, resource admission and actual submission. | Preserve the live GPU lease and resource gates. Retain memory readings and phase timing alongside attempts; do not convert planner estimates into measurements. |
| `app/workspace.py` — `AssetWorkspace.get`, `metadata`, `update`, `acceptances` | Exact output bytes, Library Keep / Needs work / Not this marks and separate use-specific acceptance records. | Build a read-only join from each frozen trial to its actual output and owner-attested mark snapshot. Existing review marks do not independently authenticate who made them. A Keep is not a project acceptance. |
| `app/review_desk.py`; `app/character_review.py` — `validate_record`, `collected_review` | Human/agent reviewer declarations, per-candidate review evidence and character-study attestations. | Add the six-axis P35 review as a versioned evidence adapter. Do not reinterpret existing character-review checks as P35 scores or an agent verdict as an owner mark. |
| `app/static/continuation-core.js`, `app/static/studio-core.js` | Existing Combine route order and entry points, identified in q-28's recorded answer. | Expose scope, failures, provenance and comparison evidence in the current workbench. Change route order only on a new explicit owner decision supported by the resulting evidence. |

`qualification.py` in this prototype is a pure consumer of declared receipts. It currently reports **human rubric pass**, including `first_pass_rubric_rate_lower_bound`; it does **not** compute owner Keep rate from Workspace marks. `owner_acceptance` remains null. The native collector and the separate paired Keep report are required adoption work, not features to claim as finished.

## Ordered integration work

1. **Freeze the actual experiment before any submission.** Bind the owner-selected canon, donor/style uploads, corrected guides, renderer identities, character descriptions and exact byte hashes. Resolve every source group; retain per-subject facet ownership. Review the baseline, candidate, case/seed pairs, allowed interventions, limits and evidence mode. Use a newly compiled prospective protocol for an intended live study. Changing `evidence_mode` after execution changes suite/trial hashes and invalidates the comparison; do not relabel an old planned suite.
2. **Confirm the native contract on the selected machine.** Compare the frozen graphs and model set with the installed backend's exact node schemas and aliases. Run the package's offline source-contract check against the supplied Studio source. Then use Production preparation to check its actual prepared graphs, inputs and model bytes. A graph hash mismatch is a refusal; do not guess around it or update the expected hash to whatever the server returned.
3. **Collect through the existing Production path.** Keep one active job, the declared per-chunk allowance and the campaign cap. Preserve create/start intents before their POSTs, all response evidence, reservations, attempts, known prompt IDs, failures and termination states. A lost or ambiguous response stops mutations. Read-only reconciliation does not create a new attempt.
4. **Add the native receipt collector.** Join the frozen suite/trial ID to Production stage, job, prompt, Workspace asset ID and output SHA-256. Capture every cost field and resource-measurement provenance. Keep missing, unsupported, cancelled, failed and submission-uncertain cells in the original denominator. Validate against `score_case`; never create a completed receipt from a filename or a project status alone.
5. **Collect separate owner marks and human observations.** Review outputs in a blinded paired order where practical, retaining the alias/order mapping. Record all six axes for every subject and a separate owner Keep / Not this snapshot bound to output bytes. Preserve Needs work and unreviewed explicitly. Obtain the owner's actual declaration identifying their own marks; local reviewer names and a snapshot hash alone are not authentication. Do not write marks on the owner's behalf.
6. **Compute the paired Keep target and hard guardrails.** Use the definitions below in a separate, deterministic report; do not rename the existing rubric rate. Calibrate any screening rubric only against the frozen, correctly scoped owner cohort. Diagnostic geometry/palette/protection observations remain diagnostic even after numerical agreement.
7. **Review adoption in the current Combine workbench.** Show the first-pass Keep difference, family/axis failures, coverage, attempts, intervention time and resources together with actual pictures. Owner approval of a route's creative behavior, asset acceptance for a named use and licence review remain distinct. Only then consider a native route-order or capability change; no frontier recipe is silently substituted into the current four-route bundle.

## Frozen comparison and finite metric definitions

The supplied full suite contains **20 cases × 3 seeds × 4 routes = 240 cells**: 60 cells per route, six per pose family per route. The ten families are ordinary, unusual, foreshortened, occluded, contact-heavy, floor, seated, lying, dynamic-action and multi-character. The three canon entries are placeholders until the owner supplies real identities and bytes. The default smoke has three cases, two routes and two seeds: **12 cells**, six per route. It demonstrates a bounded execution path only.

For the initial engineering comparison, declare `klein4-reference` as baseline and `klein9-copy-pose` as candidate before collecting any outputs. That matches the smoke pair; it does not justify replacing the already selected Copy Pose leader. A later leader-change study must compare the challenger against **`klein9-copy-pose` as the incumbent baseline**, frozen before the study. Comparing a challenger only against the cheaper 4B route cannot establish that it should displace Copy Pose.

A paired unit is one declared **case ID × seed** with the same owner canon and source situation on both routes. Route-specific representation differences, such as a corrected skeleton replacing RGB geometry input, must be explicit and byte-bound in `route_inputs`. They cannot appear only in a prose description. No best-of-seed selection, substituted easier pose or repaired output counts as a first-pass result.

| Metric | Exact definition and denominator | Missing/invalid evidence |
| --- | --- | --- |
| First-pass owner Keep rate `K_r` | For route `r`, count a cell only when its first completed output has exactly one attempt, zero retries, matching output bytes and an explicit owner-attested Keep (`selected`). Divide by **all N preregistered paired cells** for that route. | Not this and Needs work contribute zero to the numerator. Unsupported, failed, cancelled, uncertain, missing and unreviewed cells remain in N and are shown separately. An unreviewed output does not become a Not this judgement. The resulting incomplete rate is labelled a lower bound and cannot satisfy adoption. |
| Paired gain `Δpp` | `100 × Σ_i(keep_candidate_i − keep_baseline_i) / N`. Target **Δpp ≥ 15**. Also show the four paired counts: both Keep, candidate only, baseline only, neither. | Null if the frozen pair set or owner provenance cannot be established. Never use route-specific survivor denominators. At N=60, +15 points requires at least nine net extra first-pass Keeps. |
| Family Keep rate | Apply the same numerator/denominator within each preregistered family. | Empty family yields null; it is not a pass. A family omitted from the claim must be explicitly scoped out before collection, while its unsupported cells remain in the broader suite ledger. |
| Required-axis result | Six integers 0–4 per subject: identity, outfit/detail, pose/geometry, style, anatomy/contact, composition. The case value on each axis is the **minimum across subjects**. The frozen threshold is 3. | Null/absent axes or subjects block a rubric pass. An average cannot compensate for a failed axis. Agent observations are not human rubric evidence. |
| Uncertain resubmissions | Count a new create/start/prompt submission made while the previous attempt's side effect remains unresolved. Target **0** across the complete campaign journal. | An unresolved attempt is visible and stops the runner; it must not be erased, assigned a new ID or retried automatically. |
| Metric–owner contradictions | Count every scored, byte-bound mark for which the frozen threshold prediction differs from the owner's Keep / Not this, in either direction. Target **0** for a screening metric. | One disagreement disables that metric immediately, including disagreements in available development rows. Incomplete holdout coverage cannot establish zero contradictions. |
| Attempts and retries | Count every actual generation attempt, including failed attempts. `retry_count = max(attempts − 1, 0)` per cell. Unsupported cells have zero attempts. | Unknown attempt count stays null; it is not zero. Preserve the underlying receipt ledger. |
| Runtime and intervention | Record finite nonnegative seconds. Freeze the runtime clock boundaries before collection; report load/encode/sample/decode and queue time separately when available. Active operator time includes manual corrections/retries, excluding passive waiting. | Never substitute estimated warm ranges. Unknown runtime or intervention remains null and prevents complete resource evidence. |
| Peak memory | Record finite nonnegative byte counts with producer/version, process/backend and sampling cadence. Define `peak_vram_bytes` as sampled dedicated GPU use and `peak_ram_bytes` as sampled process working set for this protocol; retain shared GPU, process private commit, system commit/headroom and physical availability separately. | A missing reading is unknown. Weight-file size, PyTorch allocated memory, system commit and process working set are not interchangeable measurements. The current pure evaluator validates declarations, not the measurement producer. |

The +15-point target is a bounded pilot criterion, not a population estimate or evidence of broad generalization. With six pairs per family, show the actual counts and examples; do not manufacture statistical certainty from the percentage.

### Hard promotion guardrails

- Every family in the claimed scope has at least **two distinct source cases and three paired seeds**. All planned attempts are reconciled; every completed first output has an owner decision and complete human observations. No missing or uncertain cell is hidden in a filtered denominator.
- Candidate first-pass owner Keep rate is **at least the baseline rate in every claimed family**. The overall +15-point gain cannot buy a regression on contact, foreshortening, occlusion or another family.
- Every required subject/axis must meet the frozen **3/4 threshold** for a route to receive the evaluator's complete-qualification status. Report each observed minimum and count of failures. Identity swaps, wrong costume, impossible contact or wrong scene are not offset by prettier style.
- The owner mark remains authoritative. If the threshold-based rubric says pass for a Not this, or fail for a Keep, preserve the mark and **disable that rubric's screening gate**. Do not relabel the artwork or silently tune the threshold. Reconsider screening only after a new protocol is frozen against an untouched holdout with its own scope and owner evidence.
- **Zero uncertain resubmissions; zero contradictions for a metric enabled to screen; zero hidden retries or role/source substitutions.** Resource and intervention evidence must be complete, and observed failures/time limits must remain visible.

The current routes deliberately refuse unsupported multi-character, independent scene and unsupported outfit/detail references; those refusals make a general all-family qualification impossible today. That is a faithful capability result. The current `summarize` additionally requires every planned family trial to pass, complete costs, prospective/owner evidence and exact scoped owner calibration. A 12-cell smoke cannot satisfy it. A future narrower single-character adoption claim needs a separately frozen, explicitly scoped protocol and UI claim; it must not weaken the existing full-suite evaluator or quietly drop hard cells after seeing results.

### Automatic diagnostics have finite, narrow meanings

`automatic_metrics` performs no image extraction or semantic review. PCK is the fraction of declared visible joints whose Euclidean error divided by the reference bounding-box diagonal is within the frozen normalized threshold, with no fitted alignment. It is null unless every declared visible joint has usable coordinates/confidence and the declared minimum visibility is met. Silhouette IoU is intersection/union of matching supplied binary grids; empty union or insufficient confidence yields null. Palette delta is Euclidean ΔE76 on supplied CIE Lab triples, not an overall style score. Protected pixels compare exact same-canvas sRGB RGBA8 values inside a nonempty binary protected region; a changed canvas refuses, and an empty region yields null. Hash the extractor, alignment/crop, mask and measurement specification before comparing images. These diagnostics never replace owner identity, contact or Keep judgements.

## Owner commands for the next bounded run

Run from the owner's **full Studio repository root** with Python 3.12+. The package path is `prototypes/pro/P35/P35-B-20261125-1`. The commands below are instructions for the owner; they were not run against a live Studio here. Existing model/input aliases, primary backend, admission settings and permissions must already be available. No model or package installation is part of this procedure.

First perform the offline checks and create the input template:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py verify --source-root .
py -3 prototypes/pro/P35/P35-B-20261125-1/plan.py --template --out .runtime/P35-B-20261125-1/inputs
```

Populate `.runtime/P35-B-20261125-1/inputs/owner-inputs.json` from the exact existing Studio uploads and retained hashes. Copy the actual absolute workspace identity from Studio's `GET /api/identity`; fill character description, outfit, style and distinctive details. A corrected guide must name the expected renderer and exact output bytes. Obtain uploads through the existing Studio, preserving the owner's source provenance. The runner does not upload references or infer missing text.

Freeze a **new prospective** smoke plan before any live run:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/plan.py --owner .runtime/P35-B-20261125-1/inputs/owner-inputs.json --profile smoke --prospective --out .runtime/P35-B-20261125-1/prospective
```

`--prospective` sets the protocol's evidence mode before suite/trial hashes are created. It does not claim that any picture exists: every image `output_claim` remains planned until a real receipt is collected. Default planning without that flag remains planned and cannot later be reclassified by editing the JSON. A changed protocol uses a new output directory and new identities.

Inspect `plan.json`: require `ready:true`, no blockers, the expected 12 cells, unchanged native preset IDs, correct reference roles and byte hashes, and the declared limits. The default smoke selects three cases (`ordinary-neutral`, `foreshortened-arm`, `contact-heavy-grip`), Klein 4B and Copy Pose, two paired seeds. Its current conservative chunk allowances total **5,400 seconds / 90 minutes**, not a measured runtime prediction. Full-plan selection may refuse unsupported cases or exceed the four-hour cap; use explicit reviewed shards, retaining all other suite cells rather than reducing the denominator.

Preparation creates Studio comparison projects and verifies their prepared provenance; it does not generate:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/owner_run.py --plan .runtime/P35-B-20261125-1/prospective/owner-run.json --prepare --runtime .runtime --base-url http://127.0.0.1:8191
```

After reviewing the concrete prepared projects, the following is the explicit generation action:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/owner_run.py --plan .runtime/P35-B-20261125-1/prospective/owner-run.json --start --runtime .runtime --base-url http://127.0.0.1:8191
```

Use status after any interruption, uncertainty, failure or completed run:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/owner_run.py --plan .runtime/P35-B-20261125-1/prospective/owner-run.json --status --runtime .runtime --base-url http://127.0.0.1:8191
```

`--status` makes GET requests only; it may save fresh response evidence under `.runtime` while leaving the journal unchanged. Do not delete a retained lock, replay start, invent a fresh plan ID or switch backends to bypass an unresolved request. The runner has no automatic resume. Its time allowance bounds observation and admission of later chunks; it does not guarantee that an active GPU prompt is cancelled when observation ends. Use Studio's existing owner controls to inspect and resolve the retained work.

The native collector, owner-mark join and paired Keep report are not implemented by these three commands. Do not hand-author successful output receipts or run an unreviewed receipt through `score_case` and call it owner acceptance. The implemented run.py entry point and Run-P35.cmd launcher expose the same operations. The one-click path uses the default owner-inputs.json described in README, freezes prospective mode, and preserves the prepared plan, journal and explicit start boundary. Do not mix the README default configuration path with the explicit inputs/ path above without passing --owner.

**Qwen three-reference stays outside the default smoke.** A separately reviewed one-case, paired-seed feasibility shard requires explicit `--allow-heavy`, its declared source/style inputs and the existing native admission gate. An OOM, failed allocation, native exit, missing telemetry, unknown dispatch or exceeded budget ends further submissions. The 16 GB GPU and 32 GB RAM do not supply a fit guarantee. Frontier routes are not accepted by this primary-only runner.

## Issue disposition and the q-28 owner gate

| Existing item | P35 contribution | Remaining acceptance and disposition |
| --- | --- | --- |
| **#21** — role-specific Qwen references | Explicit role/slot bindings, source identity, current corrected graph provenance, conditional three-reference plan and refusal of unsupported semantics. | Keep **Refs #21**. The corrected current graph still needs an actual Studio proof with retained outputs and per-facet review; old timing receipts and source validation do not complete it. |
| **#446** — corrected-pose artistic comparison | Family/axis rubric, paired planning, actual-input lineage, honest unsupported cells and uncertainty controls that can inform the existing protocol. | Keep **Refs #446**. Its existing **48-cell** campaign remains its own bounded work: installed route qualification, real source selection, actual attempts/costs, per-axis human review and failure-inclusive report. P35's 240-cell authored suite does not authorize or replace those generations. |
| **#408** — `[Adult Illustration A3] Qualify role-separated multi-reference, regional and multi-adult composition workflows` | Explicit semantic role conflict/refusal, per-subject suite structure and recipe evidence. | Keep **Refs #408**. Still required: live changed/reordered/excess-source and ambiguous-subject/stale-crop/hidden-montage/missing-adult-declaration refusal; intended-facet and ignored-facet leakage evidence; identity/outfit/pose-contact/style/cleanup review; an accepted three-source adult-character case and an accepted two-adult contact/prop scene with failures/bindings retained; canon re-anchoring; native regional/multi-subject support; and #232's expected-revision apply with zero jobs until Generate. This prototype does not claim those capabilities or acceptances. |
| **HUMAN_TODO q-28** | New research and a reviewable comparison path toward the owner's difficult-pose concerns. | Preserve the already recorded answers: **(e)** selected Copy Pose as leader on 23 September; **(c)** accepted the experiment-loop shape on 27 September. **(a), (b), (d)** remain optional/open. This package creates no new image judgement and does not tick them. A new leader choice or claim that the requested pose/contact behavior is solved requires the owner's review of actual paired images. |

These are **Refs**, not closing dispositions. Recheck live issue state when an implementation PR is eventually proposed; this document records the task's supplied acceptance, not a new live issue audit. The q-28 answer is not a reusable blanket approval for new artwork. Likewise, the current owner ordering does not erase the failures or alternative routes that the new study is intended to expose.

## Concrete frontier recipes, still conditional

`frontier-recipes.json` is a research appendix, not a current catalog or execution-plan extension. Each draft has a concrete authored API graph and sidecar role bindings, but remains `planned`, `verified:false`, `runtime_admitted:false`, `submit_enabled:false`. Deliberately unresolved owner-installed aliases must block submission.

- **FLUX 3 Image Klein distilled:** 5.6B INT8 ConvRot generator; Qwen3-VL 4B INT8 ConvRot encoder with `CLIPLoader(type=flux3)`; FLUX.2 VAE; `ReferenceMultiLatent` at one megapixel with `images.image0/1/2` as identity, pose and style; Euler/simple, 16 steps, CFG 1; direct full-scene caption with `<ref_image_0>` numbering. This omits the separate 9B prompt upsampler as an explicit supported direct-caption condition. Output latent dimensions follow the first resized reference. Soft layout boxes are not protected edit masks. The official template's actual 16/1 widgets take precedence over its stale prose 50/3.5 note. AMD operator support, memory, component bytes and FLUX Kommunity eligibility remain unresolved. [S05, S20–S25, S35 in the source ledger]
- **Qwen-Image 2.1 base:** its own INT8 ConvRot image model, Qwen3-VL 8B INT8 encoder and Qwen2.1 BF16 VAE; `TextEncodeQwenImage21` binds `images.image_1/2/3` as identity, pose and style, returns both conditions and a first-reference-sized latent; inherited 25-step Euler/simple, CFG 1, cache auto/default and RGB split. This is a proposed extension of the supplied isolated one-reference route, not a proven multi-reference route or a Turbo approximation. The official model supports ten references despite the generic node's sixteen slots. Isolated-backend schema, memory, three-reference behavior and Qwen Research License permissions remain unresolved. [S14–S19, S33–S34]

No frontier draft establishes identity retention, contact quality or fit on Windows AMD. Admit it only as a separately pinned route after those concrete prerequisites are satisfied, then judge it under the same paired owner-Keep and failure-inclusive protocol.

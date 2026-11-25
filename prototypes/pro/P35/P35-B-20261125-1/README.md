# Characters that stay themselves: qualification prototype

**Pro-Run P35-B-20261125-1 · lane P35 · part B · base `0270760a`**

Implemented: a deterministic qualification suite, explicit reference-role refusal, four source-pinned native route recipes, two disabled frontier proposals, a bounded owner launcher, and reproducible offline evidence. **Every image output remains planned.** No owner image, generation, artistic review, acceptance, installed model rehash or licence clearance was produced by this run.

This package lives beside Studio's existing owners. It uses the existing Production API when the owner explicitly starts it; it does not add a model manager, generation queue, database, public server, page-load action or app/catalog modification. Read [ADOPTION.md](ADOPTION.md) for the native integration work and the number that must move.

## Kill criteria first

1. **One disagreement with an available frozen-spec owner Keep/Not this mark disables the candidate metric for gating.** Training/tuning contradictions count as well as holdout contradictions. Missing labels, unauthenticated actor provenance, source leakage, stale specifications or absent route/family coverage cannot enable a gate. Synthetic perfect agreement also cannot enable one. Current owner calibration is unavailable.
2. Changed sources, graphs or models; unsupported reference facets; ambiguous ownership; incorrect corrected-guide representation; or omitted/extra inputs block admission. A role label never proves native control. Unsupported cells stay in the denominator.
3. An uncertain create/start, interrupted process, lost response, changed prepared identity, wrong backend or failed execution receipt halts progression. Durable intents precede effects. There is no automatic retry, resume, lock reclaim, project adoption or backend switch.
4. A route that exceeds the observed resource allowance, crashes or cannot retain complete attempt evidence does not advance to a quality campaign. Published NVIDIA memory figures do not qualify this Windows/RDNA4 machine. Output bytes, human review, owner Keep, project acceptance and licensing remain separate.

## Reproduce the evidence with one command

From the full Studio repository root, using **Python 3.12 or newer**:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py verify --source-root .
```

This runs the isolated behavioral tests, compares prepared graphs against exact pinned Studio source, regenerates four deterministic reports and checks every report against [HASHES.sha256](HASHES.sha256). It contacts only inert loopback HTTP fixtures created by tests; it does not contact the owner's Studio or ComfyUI. Test fixtures, logs, JSON plans and evidence go beneath `.runtime/P35-B-20261125-1/`.

The source check deliberately requires the frozen bytes of `app/server.py`, `app/references.py` and `presets/catalog.json`, the original four graph files and model inventory used by integration tests. A newer Studio tree may refuse. Investigate and requalify a changed preparation contract; do not edit the pins merely to obtain a green result. The parent repository's `.gitattributes` already pins Python/JSON/Markdown to LF; this package additionally pins its launcher and hash manifest to LF.

In this remote Linux workspace the same command uses `python` and `--source-root /workspace/scratch/bb51a4d8d01a/studio-context`, a selected read-only source subset retrieved through the GitHub connector. No full repository was copied or cloned. [EVIDENCE.md](EVIDENCE.md) records the actual commands, environment, outcomes and limits. The full-repository proving commands remain `python -m unittest discover -s tests` and `python scripts/validate-repo.py`; their GitHub CI status is reported separately. This prototype does not replace those gates.

## The owner run

### Set up the real inputs once

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py init
```

Fill `.runtime/P35-B-20261125-1/owner-inputs.json` with actual retained Studio upload basenames and SHA-256 hashes, the exact absolute workspace from `GET http://127.0.0.1:8191/api/identity`, and the character descriptions/outfits/styles/details. Upload through the existing Studio. The prototype does not invent missing references, upload files or infer descriptions.

For the default smoke, fill these six `reference_bindings`: `canon-a`, `canon-b`, `canon-c`, `pose-ordinary-neutral`, `pose-foreshortened-arm`, `pose-contact-heavy-grip`. Fill the three canon character descriptions. Other missing suite inputs remain visible but do not authorize any additional run. To compare later shards under one full-suite identity, freeze the complete reference/guide packet before the first shard; changing any reference changes the suite identity.

Check the exact plan without contacting a service:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py plan --prospective
```

The command prints the immutable campaign directory and blockers. A runnable plan needs `ready:true`. It writes `plan.json`, `owner-run.json` and a **blank authoring** `review-template.json` under `.runtime/P35-B-20261125-1/plans/<campaign_sha256>/`. The authoring template is not a completed receipt. Expected graph/model/settings hashes are separate from observed hashes; review fields, job identities, output hashes and measurements remain null.

`--prospective` declares the experimental protocol **before** suite/trial hashes are frozen. It does not claim execution: all image claims still say planned. Relabeling an old plan after seeing outputs invalidates the experiment's identity.

### One explicit click to run the smoke

Double-click [Run-P35.cmd](Run-P35.cmd), or use its equivalent:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py owner-start --prospective
```

This is the generation boundary. It prepares the six two-seed Production projects, verifies their exact prepared inputs/graphs/models, and starts chunks in sequence. It never starts during import, offline planning, page load or source checking. The owner should already have reviewed the chosen sources and available allowance. The Windows launcher is provided but has not been run on Windows in this build.

For a separate preparation-only step, use `run.py prepare --prospective`; then the same owner-start command consumes the unchanged prepared campaign. Preparation creates planned Studio projects without generation. Its independent timeout defaults to 600 seconds and can be set explicitly up to 1800 seconds before creating a project. Start/status requests remain capped at 60 seconds. This accommodates fresh model hashing without relaxing uncertain-submission handling.

After any uncertainty or interruption, use the **original** retained owner plan:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py status --plan .runtime/P35-B-20261125-1/plans/<campaign_sha256>/owner-run.json
```

Status sends GET requests only, retains fresh observations and leaves the journal unchanged. Do not remove the lock, reset `.runtime`, re-create the same work under a new plan ID or replay Start. A create timeout may finish on the server later; zero search matches at one instant is not proof that retry is safe. [OWNER_RUN_API.md](OWNER_RUN_API.md) describes reconciliation through the existing Studio controls.

The wrapper accepts only numeric loopback HTTP hosts, ignores proxy environment variables, rejects redirects, sends same-origin headers, checks the exact Studio workspace/version and pins the primary backend URL/root. It neither installs nor modifies ComfyUI, models, Python packages or backend configuration.

## Which routes, seeds, time and memory

All current comparison conditions use **832 × 1248** output, CFG 1, existing encoders/VAEs and exact inventory byte identities. This is an explicit comparison setting; the inherited source graphs retain their original bytes. Six-step Klein and four-step Lightning Qwen are different route conditions. Seed numbers are paired identifiers; equal integers are not equal noise across architectures.

| Route ID / existing preset | Reference contract | Steps | Estimated warm time / image | Estimated peak VRAM | Admission |
| --- | --- | ---: | ---: | ---: | --- |
| `klein4-reference` / `combine-klein` | Character first; RGB pose second; optional trailing slot explicitly pruned | 6 | 30–120 s | 9–15 GiB | Default budget baseline |
| `klein9-copy-pose` / `combine-klein-9b-copypose` | Character first; RGB pose second; exact Copy Pose LoRA/trigger | 6 | 60–180 s | 11–15.5 GiB | Default incumbent |
| `klein9-skeleton` / `combine-klein-9b-skeleton` | Corrected skeleton **first**, character second; no detector rerun | 6 | 60–180 s | 11–15.5 GiB | Explicit geometry comparison |
| `qwen-3ref` / `qwen-3ref` | Identity, pose, style in both conditioning encoders | 4 | 900–2400 s | 12–16 GiB | Explicit heavy feasibility opt-in |

**These are planning ranges, not measurements or fit guarantees.** Host RAM estimates are 12–28 GB for Klein and 20–32 GB for Qwen. Cold loading, fresh SHA hashing, memory pressure, paging, queue delay and runtime state can dominate. Qwen's historical host-allocation failures make its feasibility uncertain on 32 GB RAM. The source and assumptions are in `routes.json` and the research report.

The default smoke uses cases `ordinary-neutral`, `foreshortened-arm`, `contact-heavy-grip`, routes Klein 4B and Copy Pose, and seeds **2026112501, 2026112502**: **12 planned outputs**, six per route. The estimated warm total is **9–30 minutes**. Conservative chunk allowances sum to **5,400 seconds / 90 minutes**, including declared headroom; generation observation/admission has a separate four-hour upper cap. Preparation can add up to six ten-minute default request windows before generation begins. The timer does not forcibly cancel an active GPU job; it stops observation and subsequent admissions, while Studio enforces its own stage-boundary limits.

For a deliberate two-seed geometry comparison:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py plan --prospective --routes klein9-copy-pose klein9-skeleton --cases foreshortened-arm contact-heavy-grip --seeds 2
```

The skeleton condition additionally needs the real corrected guide and renderer `studio.coco18-lines/v1`. The RGB donor and corrected guide have separate hashes. Reusing the existing generator as its own sole pose judge is not valid evidence.

A Qwen feasibility shard requires `--routes qwen-3ref --cases ordinary-neutral --seeds 2 --allow-heavy`, explicit style bytes and the same prospective flag. It remains outside the default launch. Its two-seed allowance is 5,400 seconds; three seeds receive 7,800 seconds. An OOM/native crash/uncertain receipt stops further work. Plan first, then explicitly choose `prepare` or `owner-start` with the same arguments.

## Qualification and calibration

[suite.json](suite.json) has **20 cases, two per family**, three canon placeholders, three seeds and four routes: **240 planned cells**. Families are ordinary, unusual, foreshortened, occluded, contact-heavy, floor, seated, lying, dynamic action and multi-character. The six axes are identity, outfit/detail, pose/geometry, style, anatomy/contact and composition. Each subject has its own 0–4 observations; a weighted mean cannot conceal a failed axis. See [QUALIFICATION.md](QUALIFICATION.md) for anchors, exact schemas and failure/repair categories.

The current routes support one subject under these contracts. Independent outfit/detail/scene inputs, unsupported style combinations and multi-character bindings refuse rather than becoming silent collages or ignored inputs. One identity source may contribute identity/outfit/detail; a pose source may contribute pose/composition; a style source supplies style. Explicit contradictory metadata is detected. These rules do not inspect image semantics or establish actual facet isolation.

PCK on supplied confidence-qualified landmarks, supplied silhouette IoU, Lab palette distance and exact protected-pixel equality are diagnostics. They do not judge identity, style, anatomy or artistic acceptance. Human review is required. Geometry input confidence, crop/resize conventions, actual guide pixels, source lineage and metric/preprocessing/model versions must be retained.

The calibration protocol freezes owner-mark bytes, lineage groups, threshold, rubric and route/family scope before blind holdout scoring. Existing Workspace selected/rejected marks lack actor provenance; an actual owner declaration must attest the frozen cohort. The evaluator does not authenticate people. Missing/abstained predictions remain in the denominator; any observed disagreement disables gating. No real corpus was available, so all supplied demonstrations leave gates disabled.

After a native collector or careful evidence adapter has produced actual receipts, the offline assessment entry points are:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py calibrate --input .runtime/P35-B-20261125-1/calibration-input.json --out .runtime/P35-B-20261125-1/calibration-result.json
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py score --plan .runtime/P35-B-20261125-1/plans/<campaign_sha256>/plan.json --receipts .runtime/P35-B-20261125-1/receipts.json --calibration .runtime/P35-B-20261125-1/calibration-result.json --out .runtime/P35-B-20261125-1/score.json
```

These `.runtime` inputs are owner-produced evidence, not files supplied by this package. `calibration-input.json` contains exactly `{spec,rows}`. `receipts.json` is an array of observed receipts; the blank review template is deliberately not accepted as a receipt array. The wrapper checks the frozen selected-trial execution contract, and the evaluator reports the entire bound suite. Failed, missing, unsupported, cancelled and uncertain trials remain counted. A smoke run cannot qualify the full matrix. The native job/resource/review/owner-mark collector is adoption work, explicitly described in ADOPTION.

## 2026 frontier proposals

[frontier-recipes.json](frontier-recipes.json) contains two authored graph/preset pairs: **FLUX 3 Image Klein distilled** with native `ReferenceMultiLatent`, and **Qwen-Image 2.1 base** with three native image slots. Both have concrete node links, role order, caption grammar and schedules. They remain `planned`, `verified:false`, `runtime_admitted:false`, and `submit_enabled:false`. They are excluded from current primary-backend plans.

The research distinguishes model-supported reference counts from generic node capacity, INT8 consumer implementations from NVIDIA-only NVFP4 paths, model storage from peak VRAM, and base/Lightning/Turbo checkpoints from one another. Installed schemas, AMD kernels, exact component bytes, resource feasibility and terms must be resolved before adopting either proposal. No environment upgrade is part of this package.

## Files and evidence inventory

All package paths below are relative to this directory. Generated owner inputs/plans/receipts remain under `.runtime`, outside Git.

| Files | Purpose |
| --- | --- |
| `run.py`, `Run-P35.cmd`, `.gitattributes` | One-command evidence, explicit owner entry points and LF text policy |
| `qualification.py`, `suite.json`, `QUALIFICATION.md` | Full denominators, role conflicts, calibration, six-axis scoring and schema |
| `plan.py`, `routes.json` | Deterministic protocol/compiler, native controls, exact source/component pins and estimates |
| `graphs/klein4-reference.json`, `graphs/klein9-copy-pose.json`, `graphs/klein9-skeleton.json`, `graphs/qwen-3ref.json` | Exact original API graph bytes at the pinned base |
| `owner_run.py`, `OWNER_RUN_API.md` | Durable loopback Production adapter and recovery contract |
| `source_contract_check.py` | Independent preparation-source comparison and its explicit stub boundaries |
| `test_qualification.py`, `test_plan.py`, `test_owner_run.py`, `test_source_contract_check.py`, `test_integration.py`, `test_run.py` | Behavioral/adversarial and independent native-preparation/HTTP tests |
| `fixtures/calibration.json` | Authored synthetic and unavailable-owner calibration inputs; no image dataset |
| `frontier-recipes.json` | Two disabled 2026 graph/preset proposals |
| `evidence/qualification-summary.json`, `evidence/calibration-demo.json`, `evidence/route-summary.json`, `evidence/source-contract.json`, `HASHES.sha256` | Compact deterministic software evidence and byte manifest |
| `EVIDENCE.md`, `verification.json` | Actual software verification environment/commands and residual limits |
| `ADOPTION.md`, `THIRD_PARTY.md`, `DESIGN.md`, `PLAN.md`, `RUN_STATE.md` | Native next steps, terms/provenance, design, work plan and recovery checkpoint |

Research files are at `docs/programmes/systems/research/pro/P35/P35-B-20261125-1/`: `REPORT.md`, `source-ledger.json`, and `route-components-existing.json`. The report cites 43 primary-source records and retains inherited local observations separately from new software checks. [THIRD_PARTY.md](THIRD_PARTY.md) summarizes component licences and unresolved installed-copy provenance. No model, runtime, output image, private reference dataset or third-party executable code is vendored.

## Adoption target

Move **first-pass owner Keep rate by at least 15 percentage points** on a prospectively frozen paired comparison, with no hard-family regression, no concealed failed axis, zero uncertain resubmissions and zero metric/owner contradictions. This is a target, not a result. The initial 4B comparison establishes the budget baseline; replacing the existing leader requires beating Copy Pose as the incumbent. Human rubric pass rate is a separate measurement. Resource/intervention costs and time to accepted asset must accompany the rates. The exact definitions, existing source owners, issue dispositions and remaining native collector work are in [ADOPTION.md](ADOPTION.md).

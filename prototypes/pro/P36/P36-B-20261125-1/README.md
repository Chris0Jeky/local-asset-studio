# P36: concept to playable character, with blocking identity gates

**Kill criterion:** a failed, missing, uncertain or stale required identity check
against the exact accepted concept blocks the dependent stage. An average score,
successful generation, file export or model licence cannot override that failure.

This run implements an offline Studio-side receipt graph, conservative sheet scorer
and Lumenfold pack exporter. It provides a planned first-character route and a
consumer adoption issue. It does not generate character art, submit ComfyUI jobs,
change installed packages, wire a new Studio page, or perform native engine import.
New character-output claims are **planned**; the software capability is **implemented**.

Run: `P36-B-20261125-1`; base: `0270760a`; branch: `pro/P36-B-20261125-1`.
[Studio PR #2046](https://github.com/Chris0Jeky/local-asset-studio/pull/2046).
[Lumenfold import plan #3175](https://github.com/Chris0Jeky/lumenfold/issues/3175).

## Reproduce the evidence with one command

From the Studio repository root, using Python 3.12+ with Pillow and jsonschema in
the Studio/offline Python environment:

```powershell
py -3 prototypes/pro/P36/P36-B-20261125-1/prove.py --output .runtime/pro/P36-B-20261125-1/reproduce --check-evidence prototypes/pro/P36/P36-B-20261125-1/EVIDENCE.json --repetitions 100
```

On Linux, replace `py -3` with `python`. The command runs all prototype tests,
constructs deterministic procedural fixtures, scores the adversarial cases,
checks lineage barriers, verifies real fixture bytes and exports a schema-validated
draft pack. It fails if the deterministic evidence differs from the committed file.
It makes no network request and performs no model inference.

To include Lumenfold's actual consumer validator, append
`--lumenfold-root ../lumenfold` (or the absolute path to your existing Lumenfold
checkout). This calls its `validate_doc(..., check_files=True)` on an isolated copy
of the fixture manifest in memory; it does not write to that checkout. The supplied
schema and validator used here are identified below. A different consumer revision
is useful new compatibility evidence, not an identical environment claim.

Use a fresh output name for each run, for example `reproduce-2`. Existing output
directories are refused, including an incomplete earlier run. Nothing is silently
overwritten or retried. All generated fixtures and logs stay under `.runtime/`.
No installation command is run; do not install these dependencies into ComfyUI.

Tests alone:

```powershell
py -3 prototypes/pro/P36/P36-B-20261125-1/prove.py --tests-only
```

Equivalent discovery command:

```powershell
py -3 -B -m unittest discover -s prototypes/pro/P36/P36-B-20261125-1 -p "test_*.py"
```

This is the **prototype** suite. The repository's full proving commands remain
`python -m unittest discover -s tests` and `python scripts/validate-repo.py`.
The source-slice sandbox is not a complete Studio checkout; hosted full-suite
evidence is recorded separately in [VERIFICATION.md](VERIFICATION.md).

## What the evidence demonstrates

| Measurement | Result | Scope |
| --- | ---: | --- |
| Prototype unit/regression tests | 84 passed | Offline Python, Linux; no native host claim |
| Labelled scorer cases | 20 | Procedural fixtures and explicit rubric mutations |
| Invalid cases admitted by strict gate | 0 / 16 | Required checks are conjunctive |
| Invalid cases admitted by mean >= 0.90 | 13 / 16 | Deliberately naive comparison, not the existing Studio |
| Valid controls admitted | 4 / 4 | Includes permitted expression/outfit diagnostics |
| Dependent gates blocked after turnaround drift | 6 / 6 | Exact root concept retained |
| Dependent gates blocked after replacing concept | 7 / 7 | Old acceptance/ancestry cannot be reused |
| Synthetic files checked by actual Lumenfold validator | 26 | Draft manifest, hashes and sizes; no native import |
| Real generations / owner acceptances / native imports | 0 / 0 / 0 | No real character outcome claimed |

These figures measure the defined rubric and receipt mechanism. They are not
real-character identity accuracy or a statistical estimate of production error.
The proof deliberately changes geometry outside measured regions: the proxy still
passes, `perceptual_identity_verified` remains false, and pending owner acceptance
blocks the next stage. A future calibrated learned metric can add evidence; it
cannot replace acceptance or waive a failed critical check.

## Eight linked stages

| Stage | Required parents | Owner's acceptance concerns |
| --- | --- | --- |
| `concept` | None | Exact identity reference and intended use, distinct from simply choosing canon |
| `turnaround` | Concept | Named views, face, silhouette, asymmetry and unresolved hidden construction |
| `expressions` | Concept, turnaround | Identity through named expressions; a sheet does not prove facial rigging |
| `outfits` | Concept, turnaround | Named variants preserve identity; costume changes are explicit |
| `mesh` | Concept, turnaround, expressions, outfits | Shape, face, hands, UVs, textures, scale and topology |
| `rig` | Concept, mesh | Skeleton, skinning, deformation, contacts and face/motion coverage |
| `toon` | Concept, mesh, rig | Face/hair/shadow/outline/material appearance in declared lighting |
| `unreal` | Concept, expressions, outfits, rig, toon | Accepted handoff readiness: exact intended model/dependencies, identity evidence and pack contract |

The prototype's `unreal` stage is **handoff readiness**, which must pass before
export. Actual native import/playback and visual-use acceptance are a separate
downstream consumer receipt under issue #3175. Eight accepted prototype stages
therefore do not establish an imported or playable character.

Every non-root receipt also binds the exact accepted concept receipt. Replacing a
selected head invalidates its descendants while retaining history. Expressions and
outfits can advance independently once their own required parents pass. There is one
active receipt per stage; a sheet may contain bounded, named outfit variants.

Each family references existing Workspace/character IDs. Each receipt binds its
artifacts, full recipe object, reference IDs/hashes, parent receipts, concept and
frozen policy. Separate attestations record generation, inspection, acceptance and
licence decisions. The scorer never writes acceptance or licence clearance.
Recorded hashes establish integrity, not the identity or honesty of the person
making an assertion. Live Workspace acceptance/revocation and job-history authority
must be connected before integrating this prototype with Production.

## Scoring and admission

`consistency.py` compares every required feature in every required view with the
accepted concept. It supports bounded RGB differences, annotated ratio differences
and exact categorical traits. Missing, occluded, uncertain, duplicate or malformed
required observations fail. Extra diagnostic features cannot rescue a failure.
Candidate-provided scores, thresholds and cropped regions are not authoritative.

Production pixel verification opens explicit artifact paths, verifies SHA-256 and
size, then remeasures frozen PNG regions. The supported comparison is encoded sRGB
with straight/opaque alpha; embedded ICC, animation, incompatible encodings and
insufficient coverage are rejected. This is not a colour-managed perceptual metric.
Required production RGB anchors must themselves be measured and reproduced from
the exact concept. Ratios and traits stay clearly labelled human annotations.

`pipeline.py` supplies `init`, `record`, `check`, `next` and `resolve` commands.
Use `--help` for their exact arguments. Production `record` and `next` require an
explicit `--asset-root` and fresh media checks. The Python `assess()` function is a
metadata diagnostic and reports `media_bytes_verified: false`; it is not submission
authority. A production CLI `check` without a root is blocked.

An `uncertain` receipt prevents same-stage preparation and dependent progression.
`resolve` requires the retained prompt reference plus an external observation
reference; it never contacts ComfyUI or submits anything. Uncertain upstream jobs
with no artifacts must still be represented and reconciled in existing Studio job
history. A future runner must consult that authority before any submission.

Paths reject traversal, Windows device names, private owner-model components,
symlinks/junctions and ambiguous file aliases. Outputs are new files under the
repository's `.runtime/` only. A filesystem that changes maliciously between checks
and reads is outside this offline single-owner prototype's security model.

## Lumenfold contract

`pack_export.py` validates all eight active stages and their media before writing
`family.json`, `pack.json` and `handoff.json` to a fresh output directory. The handoff
receipt is written last. Files are referenced, not copied into a native pack or
installed application. A consumer must stage and atomically promote its own import.

The manifest uses `schema: lumenfold.pack/1`, retains per-file source/licence/
commercial facts, and stores lineage under `x-studio-character-pipeline`. Root
extensions are permitted; file records remain strict. Sidecar pointers deliberately
avoid the key `file`, which the actual consumer recursively interprets as a file key.
`models.ue` records a **planned** engine request, not a successful Unreal import.

All exports remain `status: draft`. `--release --intended-use <use>` adds explicit
owner licence-clearance checks across every ancestor and rejects synthetic families;
it does not publish, declare the pack playable or change an acceptance state.
Ordinary draft export preserves unknown licence facts without presenting them as
clearance. Model headers are bounded format checks: VRM additionally needs an actual
decoded VRM extension, but skeleton/deformation/native correctness remains unproved.

The schema snapshot is from the owner's supplied Lumenfold archive, also matched to
the live connector-read contract on 2026-11-25:

- Schema SHA-256: `9892f716abfff35a85088c5b5c798a8ae38ddbff50f1e67845f799c7af16a28a`.
- Schema Git blob: `fd00e2fb6de69b80b3b0756ab89fcbfb32945b37`.
- Supplied validator SHA-256: `268588d7d01d09f9c597dce7c7dfafe050066586702676cfe633bad941af4de7`.

No third-party implementation or dataset is vendored. Runtime dependencies are
Python (PSF licence), Pillow 13 (MIT-CMU; historical PIL notices retained) and jsonschema (MIT). The schema belongs to the
user's Lumenfold repository. Model, adapter, native-content and plugin terms are
itemized in the report; a permissive software licence never clears a whole asset.

## Files and runtime outputs

Every link in this committed-file index is part of this run's branch:

| File | Role |
| --- | --- |
| [RUN_STATE.md](RUN_STATE.md) | Resumable checkpoint, commands and evidence hash-file path |
| [DESIGN.md](DESIGN.md) | Decisions, constraints and completed implementation plan |
| [pipeline.py](pipeline.py) | Receipt graph, admission, independent attestations and CLI |
| [consistency.py](consistency.py) | Hard per-view/feature scoring and PNG measurement |
| [pack_export.py](pack_export.py) | Byte verification and gated draft pack export |
| [lumenfold.pack.schema.json](lumenfold.pack.schema.json) | Exact consumer schema snapshot |
| [fixtures.py](fixtures.py) | Synthetic eight-stage family and procedural media construction |
| [fixture_helpers.py](fixture_helpers.py) | Small scorer fixture helpers |
| [test_pipeline.py](test_pipeline.py) | Graph, state and admission regressions |
| [test_consistency.py](test_consistency.py) | Scorer and measurement regressions |
| [test_export.py](test_export.py) | Contract, media, path and release regressions |
| [test_review_regressions.py](test_review_regressions.py) | Reproduced cross-stage anchor-cache bypass |
| [prove.py](prove.py) | One-command evidence and optional real consumer validation |
| [EVIDENCE.json](EVIDENCE.json) | Deterministic results; synthetic and implemented labels |
| [OUTPUT_HASHES.sha256](OUTPUT_HASHES.sha256) | Expected hashes for four deterministic runtime outputs |
| [VERIFICATION.md](VERIFICATION.md) | Actual commands, environment, CI and limits |
| [first_character.plan.json](first_character.plan.json) | Planned Sable A2 gates, routes, pins and unresolved facts |
| [ADOPTION.md](ADOPTION.md) | Named cross-repository owners, next actions and target numbers |
| [REPORT.md](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261125-1/REPORT.md) | Findings, first-character research, model/native terms and sources |

Under the chosen runtime output root, `evidence.json`, `packs/p36-fixture/pack.json`,
`packs/p36-fixture/family.json` and `packs/p36-fixture/handoff.json` are deterministic.
`OUTPUT_HASHES.sha256` uses paths relative to that output root; `SHA256SUMS.txt` is
regenerated there. `environment.json` contains host-specific tests/timing/consumer
results; `tests.txt` records full prototype output. Synthetic media are in
`asset-store/` and adversarial scratch is in `cases/`. These are regenerable and
uncommitted. The fixture model is an unrigged triangle, not a character.

Start adoption with the exact A2 source-resolution task in [ADOPTION.md](ADOPTION.md).
The live Studio, target Windows/ROCm host, native applications and real character
calibration remain explicit next gates.

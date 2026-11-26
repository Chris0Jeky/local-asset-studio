# P36-B-20261126-2: current-authority character pipeline

**Kill criterion:** a required identity check that fails against the exact accepted concept blocks the next stage. Missing or unknown evidence also blocks. A completed generation, a selected image, an accepted asset, a recorded licence and a playable Unreal character are separate facts.

This run implements a prepare-only Studio adapter and isolated draft-pack staging for the eight-stage character family. It composes the retained P36 receipt kernel with current Workspace authority, semantic identity vetoes, durable attempt reservations and provenance-preserving export. It does not submit jobs or import Unreal content. Character outputs and native adoption remain **planned**; the software and its synthetic proof are **implemented**.

Start with [ADOPTION.md](ADOPTION.md) for the next owner/agent commands and numerical targets, [VERIFICATION.md](VERIFICATION.md) for exactly what ran, and the [research report](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/REPORT.md) for decisions and limitations. The existing [Lumenfold import issue #3175](https://github.com/Chris0Jeky/lumenfold/issues/3175) owns the remaining consumer work.

## Reproduce the evidence with one command

From the Studio repository root, in the existing Studio Python environment:

```powershell
py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/owner-proof-1 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
```

On Linux, replace `py -3` with `python`. Use a **new** output directory for every explicit proof run. An existing directory is refused and retained for inspection. No network, ComfyUI, model, engine, GPU or native generation is needed. This command runs all retained and new prototype tests, creates isolated synthetic Workspace databases through the shipped API, checks the authored challenges, stages a complete synthetic draft and compares all seven deterministic output hashes. Tests that require an independently supplied Lumenfold source root are skipped unless that root is given; the exact bundled schema is always checked. Skips are recorded, never counted as consumer verification.

To include the inspected Lumenfold pure validator, append:

```powershell
--lumenfold-root C:/path/to/existing/lumenfold
```

That existing checkout must contain the exact validator and schema recorded in [LUMENFOLD_SOURCES.json](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_SOURCES.json), inspected at `19d86763944e842cbce6a3b6ae13f7abc1464b37`. The helper hashes those files before executing the pure validator and refuses other bytes. It never launches `import_packs.py`, Blender or Unreal. The main proof was run with this pinned source supplied. This repository does not include a copy of Lumenfold.

For a test-only run:

```powershell
py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --tests-only --output .runtime/pro/P36-B-20261126-2/owner-tests-1
```

The repository proving commands remain:

```powershell
py -3 -m unittest discover -s tests
py -3 scripts/validate-repo.py
```

No app, catalog, listener or page-load behavior is changed. The server remains governed by its existing loopback-only implementation. Do not install or upgrade ComfyUI packages to run this proof. The Linux sandbox used the supplied Python/Pillow/jsonschema/psutil environment; Windows, MSVC, ROCm/HIP and RX 9070 XT behavior remain unverified here.

## Linked family and gates

Every stage has a content-bound receipt, explicit evidence dimensions and a direct comparison to the accepted concept. Parent receipt hashes preserve the dependency graph. The concept hash is not substituted with the most recent derivative.

| Stage | Immediate parents | Owner decision still required for real content |
| --- | --- | --- |
| `concept` | None | Exact source bytes and current Workspace acceptance for the intended use |
| `turnaround` | Concept | Front/side/back identity, proportions and anatomical side fidelity |
| `expressions` | Concept, turnaround | Expression coverage without identity change |
| `outfits` | Concept, turnaround | Named costume changes; protected identity anchors remain fixed |
| `mesh` | Concept, turnaround, expressions, outfits | Geometry, silhouette and multi-view identity |
| `rig` | Concept, mesh | Decoded hierarchy, deforming motion and expression mapping |
| `toon` | Concept, mesh, rig | Matched game-frame face, hair, bands, outlines and material read |
| `unreal` | Concept, expressions, outfits, rig, toon | Native staged import, motion/look evidence and owner acceptance |

`check_transition` expands the full ancestor closure, always includes concept, and checks the target attempt ledger even if the target has no receipt or output. Export includes the target receipt too. A replacement canon, changed card revision, withdrawn acceptance, altered bytes, unsettled job, failed required proxy, absent semantic observation or wrong anatomical side refuses admission.

## What the scorer establishes

The retained pixel/feature proxy is recomputed and can only be vetoed by the new semantic checker. Frozen policy binds the exact concept asset ID, media SHA-256, receipt digest, required views and allowed semantic vocabulary. Anatomical left/right is explicit. An outfit context may alter only costume anchors; identity anchors stay mandatory. An unknown/occluded required observation is a refusal, not a neutral score. A high average does not hide one required failure.

The semantic checker consumes explicit annotations. It does **not** recognize a character from pixels or authenticate an annotator. Policy and annotations must come from a trusted owner/agent workflow. A forged but internally consistent declaration is outside the prototype's authority model. Production mode refuses `fixture_truth` semantics. The authored challenge set measures those contract rules, not real-image precision, recall or artistic quality.

## Current Studio authority

[studio_authority.py](studio_authority.py) opens the actual Workspace SQLite database read-only. It does not initialize or migrate it. For each selected artifact it binds the Workspace ID, character card/revision/canon, asset ID, actual bytes, explicit `asset_acceptances` row, acceptance subject hash, reviewer, intended use and retained job/workflow hashes. A selected review label alone never supplies acceptance. Current rejection, private/trash state, stale canon or withdrawn acceptance refuses.

The prototype supports the inspected `asset.import` and normal retained ComfyUI job shapes. Other native operations and brief/slot acceptance forms need an explicit adapter and currently refuse. An unsupported state is not silently promoted. This is a current local snapshot, not authenticated remote authority or a transaction across files, SQLite and a native engine. A worker/consumer must capture authority again at its own mutation boundary.

## Attempt ledger and future worker integration

[attempt_ledger.py](attempt_ledger.py) provides `initialize`, `reserve`, `inspect` and `resolve`; admission only inspects. No routine sends a request. Before any future P36 worker submission, it must reserve a unique request/job identity and persist the returned exact `job_binding` under `state.json["p36_attempt"]`. The identity includes Workspace, source-root identity, intent digest and a fresh nonce. Every attempt must use the ledger; an empty ledger cannot discover omitted historical submissions.

`reserve` uses a serialized SQLite write transaction. A replayed request returns `created=false` and `action=observe-existing`, never new submission authority. An unresolved attempt blocks a fresh request even with no prompt ID or artifact. Resolution requires explicit observation of the same retained job, source, nonce and terminal evidence; a queue label is insufficient. A changed resolved observation blocks both inspection and a fresh same-stage reservation. Retained completed/failed observations remain evidence, not automatic permission to retry.

The future worker sequence is: prepare inputs; capture admission; reserve once; durably retain the marker and pending intent; capture authority at dispatch; submit once; observe; resolve from retained evidence. Crash windows remain uncertain. Wiring this into the existing Studio worker is **planned** and must satisfy the failure-injection matrix in ADOPTION before use.

## Guarded staging API and CLI

Use [admission.py](admission.py) for current admission and export. `pipeline.py` and `pack_export.py` are retained comparison kernels; **their old export CLI is not this run's supported handoff path**.

```python
check_transition(experiments, family, binding, stage,
    asset_root=asset_root, semantic_policy=semantic_policy,
    annotations=annotations, ledger_path=ledger_path,
    include_target=False)

export_verified_bundle(experiments, family, binding, metadata, out,
    asset_root=asset_root, semantic_policy=semantic_policy,
    annotations=annotations, ledger_path=ledger_path,
    release=False, intended_use=None, lumenfold_root=None)
```

These are explicit local inputs. The proof's generated `family.json`, `workspace-binding.json`, `semantic-policy.json`, `annotations.json` and `metadata.json` are examples built from synthetic records, not a seed for claiming real owner acceptance. The real-character plan leaves exact Sable A2 IDs and hashes unresolved until the current accepted records are found.

CLI shapes, with placeholders for already-prepared owner-controlled files:

```text
py -3 prototypes/pro/P36/P36-B-20261126-2/admission.py preflight --experiments <experiments-root> --family <family.json> --binding <binding.json> --asset-root <asset-root> --semantic-policy <policy.json> --annotations <annotations.json> --ledger <existing-runtime-ledger> --stage mesh

py -3 prototypes/pro/P36/P36-B-20261126-2/admission.py export --experiments <experiments-root> --family <family.json> --binding <binding.json> --asset-root <asset-root> --semantic-policy <policy.json> --annotations <annotations.json> --ledger <existing-runtime-ledger> --metadata <metadata.json> --out .runtime/pro/P36-B-20261126-2/new-handoff-1
```

Exit zero means the local checks passed; exit two means refusal. `preflight --include-target` checks an existing target receipt. Export always checks all eight stages. `--release --intended-use <use>` additionally checks explicit licence decisions; it never changes `status` to playable, grants rights or starts an import. No ledger is silently initialized by admission. CLI JSON inputs are reread during final publication checks.

Repeated byte/path records must carry identical effective source and complete licence facts before deduplication. Conflicts refuse for reconciliation; iteration order cannot select a favourable licence. Unknown licence facts remain unknown.

The new output directory contains the draft `pack.json`, the unchanged `family.json`, a full `current-authority.json` admission report, exact input sidecars and `assets/packs/<id>/<path>` bytes. Files are copied exclusively and verified. Destination file identities, sizes and modification times are observed around final byte/metadata validation and checked again after the last authority capture, so ordinary changes during that read refuse staging. This is an optimistic snapshot; writes after the final observation or malicious restoration of stat fields still require consumer revalidation. Staging retains `PARTIAL.json`; success also retains `READY.pending.json` and publishes `READY.json` without replacing any existing marker. Failure retains partial evidence and writes `FAILED.json` where possible. Only `READY.json` indicates completed local staging. An incomplete directory is never an instruction to retry generation.

**READY is not Unreal admission.** Its hashes bind the staged observations and inputs; it explicitly requires revalidation at import and says `current_direct_import_allowed=false`. The inspected Lumenfold importer does not enforce this extension, does not apply all variant/model choices and can delete existing native content before a replacement is proven. Do not place this handoff in a directory scanned by that importer. Issue #3175 must implement the staged consumer and rollback/native gates first.

## Proof outputs and deterministic scope

The fresh proof directory contains seven deterministic JSON files plus their LF hash manifest:

| Output | Purpose |
| --- | --- |
| `evidence.json` | Challenge outcomes and exact discovered prototype test count |
| `family.json` | Eight-stage synthetic family and receipts |
| `workspace-binding.json` | Exact synthetic Workspace/acceptance/job bindings |
| `semantic-policy.json` | Concept-bound semantic policy |
| `annotations.json` | Synthetic per-stage/view declarations |
| `metadata.json` | Synthetic pack metadata |
| `pack.json` | Deterministic guarded draft manifest |

[OUTPUT_HASHES.sha256](OUTPUT_HASHES.sha256) names these files relative to the proof output directory. `--check-hashes` compares their complete manifest byte-for-byte. [EVIDENCE.json](EVIDENCE.json) is the compact committed copy of `evidence.json`. The complete synthetic assets, SQLite databases, staged bundle, logs, environment, source-location-bound observations, random ledger nonces and timings stay under `.runtime/` and are not committed. Those observations deliberately have no cross-run determinism claim. The published hashes are verified across repeated runs in the recorded Linux dependency environment; Windows and different imaging-library builds remain a reproduction gate, not an assumed match. Preserve and investigate any mismatch instead of replacing the recorded hashes. The top-level deterministic `pack.json` is distinct from `staged/pack.json`, whose admission hashes bind the particular source roots and observation.

No images or binary character artifacts are committed. Runtime swatches/triangle geometry are software fixtures, not generated anime content or a playable character.

## Source inventory and provenance

All files below are in this run folder unless linked elsewhere. [UPSTREAM.json](UPSTREAM.json) records the ten byte-identical retained files from unmerged [Studio PR #2046](https://github.com/Chris0Jeky/local-asset-studio/pull/2046), head `80b274e8dde6b0333c4d39a9473f6e15e41f38e1`. `prove.py` verifies those bytes. Their source is not silently assumed to be on main.

| Group | Files |
| --- | --- |
| Current admission | `admission.py`, `studio_authority.py`, `attempt_ledger.py` |
| Identity/export additions | `sheet_identity.py`, `export_guard.py` |
| New real-Workspace fixture support | `authority_fixtures.py`, `admission_fixtures.py` |
| New regressions | `test_admission.py`, `test_studio_authority.py`, `test_attempt_ledger.py`, `test_sheet_identity.py`, `test_export_guard.py` |
| Retained kernel/schema | `pipeline.py`, `consistency.py`, `pack_export.py`, `lumenfold.pack.schema.json` |
| Retained fixture support | `fixtures.py`, `fixture_helpers.py` |
| Retained regressions | `test_pipeline.py`, `test_consistency.py`, `test_export.py`, `test_review_regressions.py` |
| Reproduction/evidence | `prove.py`, `EVIDENCE.json`, `OUTPUT_HASHES.sha256`, `VERIFICATION.md`, `UPSTREAM.json` |
| Plan/handoff | `README.md`, `ADOPTION.md`, `DESIGN.md`, `RUN_STATE.md`, `first_character.plan.json` |
| Reports | [REPORT.md](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/REPORT.md), [FIRST_CHARACTER.md](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/FIRST_CHARACTER.md), [SOURCES.md](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/SOURCES.md), [LUMENFOLD_CONTRACT.md](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_CONTRACT.md), [LUMENFOLD_SOURCES.json](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_SOURCES.json) |

No new third-party implementation, model or dataset is vendored. Retained code and the schema come from Chris's two repositories; their provenance is recorded without inventing a public licence grant. Runtime dependencies used here: CPython (PSF licence), Pillow 13.0.0 (MIT-CMU), jsonschema 4.26.0 (MIT), psutil 7.2.2 (BSD-3-Clause). No dependency packages were changed. Model and output terms, including unresolved exact-file provenance, are recorded separately in FIRST_CHARACTER and SOURCES; a model name or successful generation is not licence clearance.

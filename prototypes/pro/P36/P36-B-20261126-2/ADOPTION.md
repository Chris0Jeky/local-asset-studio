# P36-B-20261126-2 — adoption and cross-repository handoff

## Admission criterion

Adopt the checks only while they fail closed on an invalid root-relative identity
observation, stale current authority, changed bytes, unresolved attempt or
conflicting provenance. **A green snapshot is not transferable permission to
submit or import later.** The actual dispatcher and native consumer must recheck
the exact subject at their own mutation boundary.

The implemented unit is the run-local software prototype. All Sable generation,
native finishing and native import remain planned. The first real owner step is
**0 → 1 exact accepted Sable A2 source mapping**, with the current acceptance scope
resolved. Current generation budget is **0**; the proposed **maximum 12** attempts
remains unarmed. The existing cast-study hold and answered Anima position retain
their scope. See the [first-character plan](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/FIRST_CHARACTER.md).

## 1. Source and owner map

| Surface | Source / owner | Adoption responsibility |
| --- | --- | --- |
| Studio fixed baseline | `0270760a3d4fd9e005a1788bba59d8242b77c2f4` | Reuse existing Workspace, character, Production, reference and job services. |
| Earlier P36 kernel | [PR #2046](https://github.com/Chris0Jeky/local-asset-studio/pull/2046), exact head `80b274e8dde6b0333c4d39a9473f6e15e41f38e1`; open/unmerged when read | Ten exact retained files in [UPSTREAM.json](UPSTREAM.json); do not treat that PR as merged or silently alter its baseline. |
| Current prototype | [PR #2049](https://github.com/Chris0Jeky/local-asset-studio/pull/2049), Studio agents | Integrate reviewed authority/admission/ledger seams into the existing worker after reproducing the proof; no second asset store. |
| Character/native intake | `lf-characters-3d` | Recover A2 source, resolve skeleton/variant/model choices, stage native normalization, prove deformation and retain a separate import receipt. |
| Unreal appearance | `lf-anime-look` | Validate actual material/face-SDF/outline/secondary-motion dependencies and judged game-frame evidence. |
| Import coordination | [Lumenfold #3175](https://github.com/Chris0Jeky/lumenfold/issues/3175), still open | Record the named lane's accept/decline/adapt decision and staged-consumer work; do not duplicate or close the issue on a schema pass. |

The inspected Lumenfold revision is
`19d86763944e842cbce6a3b6ae13f7abc1464b37`. Its exact contract and consumer hazards
are in [LUMENFOLD_CONTRACT.md](../../../../docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_CONTRACT.md).

## 2. Reproduce before wiring

Run from the Studio repository root, using the existing Python environment and
dependencies. The commands do not install models, start native applications or
submit generations. Each output directory must be new; preserve an existing
directory and choose another name after inspecting its outcome.

```powershell
py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/adoption-proof-1 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
```

On Linux, use `python` in place of `py -3`. The examples below use shell line continuations; on PowerShell use one line or its backtick continuation.

To exercise the inspected Lumenfold validator as well, use an existing trusted
snapshot at the pinned revision. Set `P36_LUMENFOLD_ROOT` to that snapshot's absolute
path, then run:

```sh
python prototypes/pro/P36/P36-B-20261126-2/prove.py \
  --output .runtime/pro/P36-B-20261126-2/adoption-consumer-proof-1 \
  --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json \
  --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256 \
  --lumenfold-root "$P36_LUMENFOLD_ROOT"
```

The optional validator runs only after its source SHA-256 equals
`268588d7d01d09f9c597dce7c7dfafe050066586702676cfe633bad941af4de7` and the schema
equals `9892f716abfff35a85088c5b5c798a8ae38ddbff50f1e67845f799c7af16a28a`.
It checks actual copied files, not merely metadata. No import or engine execution
is implied. Without this option, inspect the recorded consumer-test skip reason.

Required proof result: exit **0**, deterministic evidence equals
[EVIDENCE.json](EVIDENCE.json), all ten retained-file hashes match, semantic invalid
admissions **0/8**, valid semantic admissions **2/2**, current-authority invalid
admissions **0/9**, zero reissues of the repeated ledger request, and refusal of
the reproduced licence conflict. Inspect `tests-summary.json`, `tests.log`,
`environment.json`, `staging-observation.json` and `OUTPUT_HASHES.sha256` in the new
output. The final discovered prototype test count is recorded by the proof;
component counts are not additive coverage claims.

The separately run repository regression command was:

```sh
python -m unittest discover -s tests
```

It completed **7,321 tests in 615.292 seconds**, with **62 skips** and exit **0**.
[VERIFICATION.md](VERIFICATION.md) owns the complete proving record and applicable
repository validation results. Reproducing the offline proof on Windows is a
future environment check; this Linux result does not qualify ROCm/HIP, ComfyUI,
Blender or Unreal on the owner's host.

## 3. Studio integration contract

### Current implementation

The public preparation API is
`admission.check_transition(experiments, family, binding, stage, *, asset_root,
semantic_policy, annotations, ledger_path, include_target=False)`.
Supply explicit source roots, a current Workspace binding, the complete family,
an operator-controlled concept-bound policy and annotations for all active heads.
The implementation recomputes selected ancestor checks, verifies media, scores
semantics and rereads live authority and the ledger. The target's ledger scope is
included even before its artifact exists. `include_target=True` additionally
requires the target receipt and is used for export.

The return is `prepare-only`, with `submission_authority=false` and
`generation_submitted=false`. Production mode refuses `fixture_truth`
annotations. Local `human_annotated` and `local-user` declarations still do not
authenticate a reviewer or independently recognize image identity.

For already resolved inputs, the exact CLI is:

```sh
python prototypes/pro/P36/P36-B-20261126-2/admission.py preflight \
  --experiments "$P36_EXPERIMENTS" --family "$P36_FAMILY" \
  --binding "$P36_BINDING" --asset-root "$P36_ASSETS" \
  --semantic-policy "$P36_SEMANTIC_POLICY" --annotations "$P36_ANNOTATIONS" \
  --ledger "$P36_LEDGER" --stage mesh
```

These variables are explicit existing paths, not discovery instructions.
`P36_LEDGER` must name an explicitly initialized ledger under this repository's
`.runtime/`. Preflight does not initialize it. Do not substitute the synthetic
proof family for the missing real A2 binding.

### Worker wiring remains planned

Studio agents must add the following sequence at the existing dispatch seam:

1. Resolve exact current source and acceptance scope, then run fresh admission
   against the selected family and frozen policy.
2. Apply the existing Production budget, job ownership and GPU-lease checks.
   An admission result alone supplies no new budget or permission.
3. Reserve the durable attempt before dispatch, binding the canonical intent,
   family/stage, request/job IDs, Workspace, source root and nonce. Persist the
   exact returned `p36_attempt` marker in the retained job record before a request
   could escape the process.
4. Recheck the selected subject at the actual mutation boundary. Dispatch through
   the existing submit-once path only under its current authority. A replayed
   request returns observe-existing; it is never another submission opportunity.
5. Reconcile the original prompt/job. An unresolved record blocks new work even
   with no artifact or prompt ID. Explicit terminal resolution must match the
   stored marker and exact state/workflow observation; altered evidence blocks.

The ledger API intentionally does not provide a network submission method. A
successful reservation is evidence of a reserved attempt, not a dispatch token.
Every attempt must use this seam; omitted historical attempts cannot be recovered
from an empty output folder.

**Next software target:** exercise at least **7 mutation-boundary cases** through
the wired worker: acceptance withdrawal, changed bytes, changed selected head,
wrong Workspace/source root, mismatched marker/intent, crash after reservation
with no prompt, and uncertain upstream response. Target **0 new submissions in
all 7 blocked cases**, plus **1 submit-once valid control** whose repeated request
produces **0 additional submissions**. Use a deterministic fake dispatcher first;
these targets grant no real generation budget.

## 4. Isolated draft handoff

Use `admission.export_verified_bundle`, which calls the new guarded manifest
builder. Do not call retained `pack_export.export_bundle` for adoption: its old
manifest builder remains the comparison baseline.

With resolved explicit inputs, the exact CLI is:

```sh
python prototypes/pro/P36/P36-B-20261126-2/admission.py export \
  --experiments "$P36_EXPERIMENTS" --family "$P36_FAMILY" \
  --binding "$P36_BINDING" --asset-root "$P36_ASSETS" \
  --semantic-policy "$P36_SEMANTIC_POLICY" --annotations "$P36_ANNOTATIONS" \
  --ledger "$P36_LEDGER" --metadata "$P36_METADATA" \
  --out .runtime/pro/P36-B-20261126-2/adoption-handoff-1
```

The optional `--lumenfold-root "$P36_LUMENFOLD_ROOT"` performs the pinned validator
comparison. The default output remains draft. An explicit intended-use check is
separate from art acceptance; it cannot grant missing content rights.

| Bundle item | Consumer obligation |
| --- | --- |
| `pack.json` | Preserve `lumenfold.pack/1`, draft status, exact file facts and `x-studio-character-pipeline`. Resolve requested variant and actual source model explicitly. |
| `family.json`, `binding.json` | Bind the exact selected concept/ancestry and Workspace subjects. Do not rebuild ancestry from filenames. |
| `semantic-policy.json`, `annotations.json` | Preserve the frozen inputs; recompute their checks, then obtain the required real visual review. |
| `character-metadata.json` | Preserve intended metadata and its digest; owner-defined profile/appearance values are not inferred from a synthetic fixture. |
| `current-authority.json` | Complete initial admission report, including nested authority, semantics and ledger. Its digest must equal the final admission captured at export. Recheck again at native mutation. |
| `assets/packs/<id>/…` | Verify every declared byte count and SHA-256 before decoding or promoting. |
| `PARTIAL.json`, `FAILED.json` | Retained staging/failure evidence. Neither is a completion marker; partial output is not automatically retried or deleted. |
| `READY.json` | Sole completed-staging marker, with exact input/pack/family/admission bindings. It still says direct import is disallowed and native import is planned. |

`READY.json` is published after final checks using an exclusive atomic link to a
fully written marker. Destination identity/size/mtime observations reject ordinary
changes during final validation and authority capture; they do not authenticate a
concurrent writer or protect against later changes. There is no cross-process transaction spanning Workspace,
job files and the future native importer. A later withdrawal can invalidate a
completed draft, so a consumer must never treat the marker as permanent authority.

## 5. Lumenfold staged consumer: proposed, not installed

**Do not feed this draft to the current direct importer.** At the inspected pin,
`games/world3d/tools/import_packs.py` does not enforce the Studio extension or
`READY.json`; draft status is not a barrier. It reads raw top-level choices,
depends on external joined-model handling, implements the VRM-humanoid/J_Bip path,
and removes existing native pack content before the whole import succeeds.
`intake_model.py` also has publication steps for which rollback is not proven.
The advisory field is therefore a proposed consumer contract, not an installed
access control. Keep staged output outside its scanned production roots.

Under #3175, `lf-characters-3d` and Studio agents should implement a consumer that:

1. Validates the marker, all sidecar hashes, schema/references and actual bytes;
   rereads live selected ancestry and acceptance scope.
2. Applies the selected variant and explicit consumer choice, decodes the real
   rig/model, and checks joined topology, units, axes and expression availability.
   A Manny source must follow its actual fighter path; a renamed skeleton is not
   a VRM conversion.
3. Imports into an isolated native candidate location, preserving the previously
   accepted pack and registration until all checks pass. Promotion and rollback
   must have explicit failure tests.
4. Emits a separate native receipt binding the admitted handoff, decoded source
   hashes, engine/build/plugins, actual settings, output paths and captures.
5. Presents native results to `lf-characters-3d` and `lf-anime-look` for their
   scoped acceptance. A schema pass does not set `models.ue`, `playable` or a
   judged Versus result.

**Next consumer target:** **1 valid isolated draft** plus **6 refusing cases**:
revoked authority, changed source bytes, incompatible skeleton, missing expression,
missing required material input and injected failure during promotion. Target
**0 changes to the previous accepted native pack across all 6 failures**, and
**1 retained rollback proof**. These are proposed acceptance targets, not completed
results.

## 6. Real-character qualification and numeric next targets

The following are proposed gates for the named owners. They do not authorize
new studies, clear licences or qualify a workstation.

| Owner / step | Next measurable target | Stop condition |
| --- | --- | --- |
| Studio agents + owner: exact source | **0 → 1** attributable Sable A2 mapping: concept, near-eye portrait, paired wide, native source and current accepted scope; retain exact hashes/records | Ambiguous bytes or scope; legacy slender/default substitution; revoked acceptance |
| Studio agents + owner: real review calibration | After source resolution, label a held-out set of **20 comparisons**, with **10 critical-invalid** and **10 allowed controls**, using attributable retained media where possible; target **0/10 critical false passes** and report all false rejections | Any critical false pass; manual declarations presented as recognition accuracy. This is a proposed small acceptance set, not a statistical quality guarantee or 20 generation requests. |
| Studio agents: stage records | **8 individually gated stage receipts**, each comparing directly to the same immutable concept; keep each unresolved stage planned | Missing required view, unknown construction, stale policy/root or unsupported annotation |
| `lf-characters-3d`: native result | **1** staged native receipt with matched front/left/right/back evidence, actual expression controls and **24 consecutive move frames**; apply the existing 60k body, <2 mm surface p99, <2.0 stretch p99.9, <100 left-behind vertices and <20 mm grip gates | Failed deformation, expression loss, wrong axes/scale, or unverifiable source rights |
| `lf-anime-look`: native look | **3** matched neutral/warm/cool conditions, separate near-eye read and paired wide, plus exact dependencies for the accepted face/outline/secondary-motion path | Missing face SDF, unproven motion dependency, wrong palette/eye identity or unjudged look |
| Owner/lane: promotion | **1** explicit native acceptance tied to exact handoff and capture hashes after the previous gates | A manifest/test/hash is used as a substitute for art or native acceptance |

The first-character plan contains the one-primary/one-fallback route choices,
model/code/output licence distinctions, future attempt/time ceilings and bold
experiment kill gates. The normal 3D route uses retained A2 bytes and **0 neural
3D calls**. A separate one-attempt TRELLIS contingency needs its own current
authority and resolved dependency/runtime facts. Upstream Linux/NVIDIA ≥24 GB
requirements do not qualify the owner's 16 GB Radeon path.

Generated, inspected, owner-accepted, intended-use-cleared and native-playable
remain separate records. Preserve existing owner decisions rather than requesting
them again; present only the exact unresolved A2 mapping or changed scope for the
first owner decision. Worker wiring, consumer promotion/rollback and all native
qualification remain planned until their own evidence is recorded.

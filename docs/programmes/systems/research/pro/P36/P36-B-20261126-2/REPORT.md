# P36-B-20261126-2 — character pipeline with current authority

## Kill criterion first

**Stop a character transition when any required identity observation, current
acceptance, selected ancestry, source byte, job history or provenance fact is
missing, stale, uncertain or conflicting.** A high similarity mean cannot excuse
one changed identity cue. A recorded acceptance cannot survive its withdrawal.
An attempt with no artifact still counts as an unresolved attempt. A valid draft
manifest cannot establish native readiness.

For the first real character, the immediate stop condition is concrete: **the exact
accepted Sable A2 source and its current acceptance scope have not been mapped**.
That mapping must move from **0 to 1** before any downstream character work is
admissible. Current generation spending is **0**; the later **12-attempt** proposal
is unarmed. The current cast-study hold remains in force. See
[FIRST_CHARACTER.md](FIRST_CHARACTER.md).

## Result and evidence boundary

This run extends the existing P36 lab with a semantic veto, a read-only adapter to
Studio's actual Workspace database, a durable attempt ledger, provenance-safe
manifest construction, and isolated draft staging. These are implemented software
checks exercised with synthetic inputs. They do not generate or accept a character.

On eight authored invalid semantic challenges, the retained hard numeric proxy
accepted **7/8** and the new composition accepted **0/8**. Both valid controls were
admitted. On nine synthetic stale/withdrawn/wrong-context cases stored through
Studio's real SQLite fixture, the retained offline gate accepted **9/9** and the
current-authority check accepted **0/9**. These bounded results demonstrate the
additional checks; they do not measure subjective identity recognition. The
deterministic cases, outputs and exact test inventory are in
[EVIDENCE.json](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json)
and [VERIFICATION.md](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/VERIFICATION.md).

| State | What is supported by this run | What remains separate |
| --- | --- | --- |
| Implemented | Receipt checks, semantic descriptor veto, fresh Workspace authority capture, attempt identity/uncertainty checks, provenance guard, isolated staging and reproducible synthetic proof | Worker dispatch, authenticated review services and downstream mutation authority |
| Source inspected | Pinned Studio routes/model inventory and Lumenfold schema, validator, intake/importer and native-lane requirements | Installed models, real accepted A2 media and actual native project state |
| Planned | Concept → turnaround → expressions → outfits → mesh → rig → toon → Unreal handoff | Generation, visual review, owner acceptance, intended-use clearance, native import and playability |

The Windows 11/RX 9070 XT 16 GB workstation was unavailable. Windows/AMD runtime
behaviour, ComfyUI execution, Blender finishing and Unreal import/playback were
not verified. The Python checks are not GPU throughput or character-quality
measurements.

## 1. Reuse rather than another receipt system

The fixed Studio base is
`0270760a3d4fd9e005a1788bba59d8242b77c2f4`. The current work is tracked by
[PR #2049](https://github.com/Chris0Jeky/local-asset-studio/pull/2049).
The earlier [PR #2046](https://github.com/Chris0Jeky/local-asset-studio/pull/2046)
was open and unmerged when inspected, at
`80b274e8dde6b0333c4d39a9473f6e15e41f38e1`; it is an explicit source dependency,
not an assumed part of merged main.

Ten files from that exact head are retained byte for byte: the family kernel,
numeric consistency scorer, exporter, two fixture modules, pack schema and four
test modules. [UPSTREAM.json](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/UPSTREAM.json)
records their original paths, Git blobs and SHA-256 values, and the proof checks
those values before running. New behaviour is composed around that retained
kernel. The old export entry point remains a historical baseline; adoption uses
the guarded admission/staging entry point.

Merged Studio already owns Workspace media, lineage, character canon/study plans,
protected edits, Production budgets and output recall. The current adapter reads
those records instead of introducing a second asset store. A character card can
name an image as canon without separately proving an owner acceptance; the new
adapter therefore checks the acceptance records independently. These source
distinctions are documented in [SOURCES.md](SOURCES.md).

## 2. What changed

### Identity is a conjunction of required observations

[sheet_identity.py](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/sheet_identity.py)
first recomputes the retained numeric scorer, then applies an additional semantic
veto. Its policy binds the exact concept asset, media SHA-256 and receipt digest,
plus the numeric policy digest. The complete policy is validated, including
unused contexts and stages. Every required view has identity coverage; a costume
context can override only named costume anchors.

Annotations use a frozen vocabulary and subject-anatomical sides. Required
occluded, unknown or missing observations block. A mirrored eye assignment, a
changed back-view mark, a stale comparison root or an unauthorized costume context
cannot be averaged away by otherwise good views. The report retains per-view
minimum agreement and blocker codes. A passing semantic report cannot turn the
retained numeric scorer's failure into a pass.

This is a consistency check on supplied descriptors, not a visual recognition
model. Fabricated but matching annotations can pass. Production admission rejects
fixture provenance, but a `human_annotated` string does not authenticate a human or
prove that the annotation describes the pixels. Real A2 calibration and owner
visual acceptance remain required.

### Authority comes from a fresh, explicit Workspace subject

[studio_authority.py](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/studio_authority.py)
opens the existing SQLite database read-only, without initializing or migrating
it. It checks the Workspace identity, character-card revision and canon, every
selected artifact's metadata and actual bytes, the exact unwithdrawn acceptance
subject and intended stage use, and retained job/workflow/output identities.

It distinguishes `selected` from a current acceptance. `needs_work` and `rejected`
conflict with admission. A `local-user` acceptance remains a local declaration,
not an authenticated signature. Brief/slot acceptance is refused until a scoped
adapter exists rather than being flattened into a generic approval. Private
records are outside this adapter. A completed `asset.import` can be observed;
other native-operation receipts need their own decoded adapter.

SQLite rows are captured within one read transaction. Files and job records are
checked separately with bounded stable reads and hashes. This provides a fresh
bounded snapshot, not a transaction across every system. The worker and consumer
must recheck authority at their own mutation boundary.

### Uncertainty survives the absence of an output

[attempt_ledger.py](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/attempt_ledger.py)
reserves a durable identity before a future dispatcher could submit. The identity
binds family, stage, request ID, unique job ID, intent digest, Workspace, source
root and random nonce. SQLite serializes competing writers. Repeating the same
request returns its existing identity with an observe-existing action; it never
issues another submission permission.

An unresolved reservation blocks the stage even if no prompt ID, artifact or
target receipt exists. Resolving it requires an exact retained job bearing the
same `p36_attempt` marker and an observed terminal state. Changing that terminal
evidence blocks later admission and a fresh same-stage reservation. A pre-existing unrelated job cannot be attached
to a fresh reservation.

The ledger cannot discover historical attempts that a caller never reserved.
Wiring every future attempt through the existing Studio dispatcher remains
planned. No job is submitted by this prototype.

### Reused bytes retain all provenance facts

The retained exporter deduplicates repeated path/hash/size identities. In the
reproduced conflict, an earlier `commercial: yes` and a later `commercial: no`
refer to the same bytes; the retained output keeps the earlier `yes`.
[export_guard.py](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/export_guard.py)
compares the effective source and complete licence object before deduplication,
and refuses that conflict in either ordering. Case/content conflicts are refused
as well. It does not invent a licence merge or an owner-clearance decision.

The manifest remains `lumenfold.pack/1` with `status: draft`. Its extension binds
the selected family, concept and stage receipts, records the inspected consumer,
and explicitly sets `current_direct_import_allowed: false`. Joined topology and
rig compatibility remain unverified.

### A completed staging marker is narrower than import permission

[admission.py](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/admission.py)
composes the graph, actual media checks, fresh semantic scoring, current authority
and attempt ledger. It does not accept a cached green score. The target's attempts
are checked even before a target artifact exists; export also checks the complete
target receipt.

Export uses a new directory under `.runtime/`, copies declared files exclusively,
verifies their bytes and hashes, writes complete sidecars and rechecks inputs,
metadata, authority and ledger before publishing `READY.json`. It refuses an
existing destination and linked paths. Failed partial staging is retained without
automatic cleanup or retry. The marker says that draft staging completed; it does
not authorize the current native importer. Tests inject changes during copy and
final checks to exercise these refusal boundaries. Destination identity/size/mtime
observations close ordinary changes during the final authority capture. They do
not make this a cross-system transaction or replace consumer revalidation.

Optional comparison against the pinned Lumenfold validator executes only that
exact schema/file-validation code after its own source hashes match. It does not
start Blender or Unreal. Even a successful file check cannot establish usable
topology, a compatible skeleton, expression controls or the intended look.

## 3. Measured evidence and its limits

The proof is implemented in
[prove.py](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/prove.py).
The following denominators refer to authored fixtures, not a sampled population
of real character outputs.

| Experiment | Retained baseline | Current result | Interpretation |
| --- | --- | --- | --- |
| Eight invalid semantic challenges | Hard numeric proxy accepts 7/8 | Composition accepts 0/8 | Added semantic/root/context checks refuse the seven gaps; the numeric-drift case stays refused. |
| Two valid semantic controls | Matching inputs and permitted costume context | 2/2 admitted | The veto does not simply reject everything in this fixture set. |
| Nine current-authority challenges | Offline receipt gate accepts 9/9 after mutation | Fresh authority accepts 0/9; all nine pre-mutation controls pass | Withdrawal and current Workspace context cannot be inferred from old receipts. |
| Same ledger request repeated | One durable reservation | Zero reissues | Idempotent observation is separate from dispatch permission. |
| Reserved attempt with no prompt or artifact | No output exists to enumerate | Admission blocks; a fresh request is refused | Absence of media does not erase uncertainty. |
| Exact terminal observation later changes | Earlier resolution had passed | Later inspection and a fresh reservation block | A terminal observation is bound, not trusted indefinitely. |
| Same-path licence conflict | Earlier `yes` survives later `no` | Guard refuses `artifact_provenance_conflict` | Deduplication cannot erase a contradictory declaration. |
| Repository regression suite | `python -m unittest discover -s tests` | 7,321 tests, 62 skips, 615.292 s, exit 0 | Repository regression evidence; skips and prototype-specific coverage remain explicit. |

The nine authority mutations are withdrawal, another Workspace identity, a forged
acceptance subject hash, another intended use, changed canon, an uncertain
upstream job, changed media bytes, current asset rejection, and selection without
an acceptance. These use actual Studio tables, files and source-job records with
synthetic data. They are not observations of a real user's live acceptance state.

The final discovered prototype test inventory and skip reasons belong to
`EVIDENCE.json` and `VERIFICATION.md`; component runs are not added together as if
they were distinct coverage. Timing output from the proof measures Python
descriptor-check overhead only. No subjective accuracy, deployment reliability,
native performance or generation speed is inferred.

## 4. Reproduction

Run from the Studio repository root in the existing configured Python environment.
Use a fresh output directory; the command refuses an existing one and retains
failure evidence. It verifies the ten retained source files, runs the prototype
tests, rebuilds the experiments and compares deterministic evidence.

```sh
python prototypes/pro/P36/P36-B-20261126-2/prove.py \
  --output .runtime/pro/P36-B-20261126-2/reviewer-proof-1 \
  --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json \
  --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
```

To include the real Lumenfold schema/file validator, add `--lumenfold-root` naming
an already available trusted snapshot at
`19d86763944e842cbce6a3b6ae13f7abc1464b37`. The two executed source files must match
the embedded SHA-256 pins; a different checkout is refused. This option does not
invoke a native importer. Full commands and next-owner responsibilities are in
[ADOPTION.md](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/ADOPTION.md).

The output contains test/environment summaries, deterministic `evidence.json`,
input/pack documents, `OUTPUT_HASHES.sha256`, timing and a separate staging
observation. Live-path/nonces and timing are observations; the deterministic
comparison is not an assertion that every runtime file is identical across runs.

## 5. First real character and cross-repository decision

The first-character plan chooses **safe reuse of exact Sable A2**. Primary routes
retain its existing concept, native views, mesh, rig and look wherever they are
attributable. A later expression proposal uses Anima Turbo with Base as fallback;
a protected outfit edit uses Krita/Blender with Klein 4B as a scoped candidate
fallback. Missing views may be proposed with the existing TripleView/Klein 9B
route, and TRELLIS is a separately gated sculpt-base contingency. Every stage
compares directly to the immutable concept. The plan does not invent hidden-side
design, palette, hashes or acceptance. Exact routes, licence distinctions and
budgets are in [FIRST_CHARACTER.md](FIRST_CHARACTER.md) and the
[structured plan](../../../../../../../prototypes/pro/P36/P36-B-20261126-2/first_character.plan.json).

The bolder experiment is a bounded sheet-to-mesh inspection loop: render frozen
native views of a candidate and compare every view to the accepted root and any
explicitly accepted supplemental construction. Its own generated views never
become identity authority. Identity drift, unresolved source/terms, missing
authority, resource failure or the attempt/time limit kills that branch. It is
planned only.

Lumenfold [issue #3175](https://github.com/Chris0Jeky/lumenfold/issues/3175) stays
open as the import-side owner. The inspected consumer currently skips only
`concept`, does not enforce Studio's sidecars, ignores declared variant/consumer
choices in important paths, depends on external joined-model handling and deletes
existing native pack content before completing the import. Its VRM-humanoid
retarget path is not the Manny fighter path. A draft dropped into its scanned
input would bypass the proposed admission declaration. Therefore **direct
consumption by the current importer remains unsafe for this handoff**. Source
details and the intake transaction limitations are retained in
[LUMENFOLD_CONTRACT.md](LUMENFOLD_CONTRACT.md).

Studio agents own worker/admission wiring and exact A2 source mapping;
`lf-characters-3d` owns mesh, rig, staged intake and native receipt;
`lf-anime-look` owns judged look, face, outline and secondary-motion evidence.
The lane adoption decision remains explicit in #3175. The next owner decision is
the exact accepted A2 mapping, not approval of a synthetic family or a restart of
generation. Generated, inspected, accepted, intended-use-cleared and playable
remain distinct states throughout.

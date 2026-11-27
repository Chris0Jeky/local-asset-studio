# P36-B continuation: from recorded gates to durable handoffs

**Run:** P36-B-20261126-2 · **Date:** 2026-11-27 UTC  
**Studio base:** `0270760a3d4fd9e005a1788bba59d8242b77c2f4`  
**Branch:** `pro/P36-B-20261126-2` · [Studio PR #2049](https://github.com/Chris0Jeky/local-asset-studio/pull/2049)  
**Consumer plan:** [Lumenfold #3175](https://github.com/Chris0Jeky/lumenfold/issues/3175)

## Outcome and kill criterion

The continuation implements the missing software boundaries between a prepared
Studio character operation and a retained handoff: a read-only Production intent
factory, durable dispatch coordination with a local simulation port, and an
independent consumer verifier. It also fixes the current-authority adapter to
accept legitimate outputs from Studio's actual indexer without dropping their
source provenance. The expanded proof has **303 discovered tests**, up from
**202**, and **11 deterministic outputs**, up from seven. All work remains within
the authorized prototype/report directories; all 4,930 fixed-base blobs still
match their Git object hashes.

The kill criterion remains decisive: a failed identity check against the exact
accepted concept blocks the next step. Missing authority, changed media,
unresolved attempts and conflicting provenance also block. A late veto after a
dispatch claim leaves that claim consumed; the coordinator cannot turn a refusal
into permission to try again.

Software is **implemented**. Real character generation, owner art acceptance,
Windows/AMD runtime qualification, native finishing and playable Unreal import
remain **planned**. No actual generation request, model acquisition or native
application was run. The first-character route/licence plan in
[FIRST_CHARACTER.md](FIRST_CHARACTER.md) retains its current scope and zero
armed generation budget.

## Measured changes

The following are authored software challenges using synthetic records and
media. They measure the specified contracts, not visual recognition accuracy,
real-image quality or probabilistic reliability.

| Boundary | Measured result | Meaning |
| --- | --- | --- |
| Actual Studio indexing | **4/4** legitimate controls admitted; **6/6** provenance mutations refused | Normal indexing diagnostics no longer make valid provenance appear unbound; meaningful source changes still refuse. |
| Prepared Production intent | **12/12** changed preparations refused; **13** initial valid controls admitted | Actual plan, graph, source bytes, roots and identity remain bound before creating a future job. |
| Durable dispatch | **23/23** authored outcomes matched; **10** expected simulated callbacks, **0** extras | A committed claim cannot be replayed after a lost response, publication failure or restart. |
| Process boundaries | **4/4** crash recoveries observation-only; **1** callback among **3** competing processes | Claim ownership survives the tested process terminations and serializes competing callers. |
| Consumer handoff | **13/13** selected outcomes matched: **5** passes with explicit limits and **8** refusals | Local integrity and current authority are verified separately. |
| Prior identity/authority challenges | **0/8** invalid semantic admissions; **0/9** stale-authority admissions | The earlier root-relative identity and current-authority vetoes remain intact. |

The old raw stored-source/output equality predicate refuses all four actual-index
controls because indexing adds metadata after registration. The current adapter
admits all four. This comparison deliberately isolates that predicate; it is not
a claim that the entire old implementation was replayed by the new proof.

The full consumer unit suite additionally has 32 test methods covering 34
authored refusal cases. The 13-case deterministic matrix is a selected subset
with retained, inspectable bundle copies. Counts across suites are not additive
coverage or statistical confidence claims.

## 1. Bind actual Studio outputs

The new [GitHub review finding](https://github.com/Chris0Jeky/local-asset-studio/pull/2049#discussion_r4714353061)
identified a real integration mismatch: `AssetWorkspace.register` records a
source descriptor before `Studio.index_outputs` adds its asset ID and inspection
diagnostics. Comparing those dictionaries verbatim rejects normal outputs.

The correction checks the deterministic asset ID from job ID and output index,
checks any explicit descriptor asset ID, then compares canonical source facts.
Only recognized, shape-checked Studio diagnostics may differ. Unknown added or
removed keys, filename/folder/type/prompt changes, upload-source changes and
integer/boolean aliases still refuse. Actual generated-job-shaped fixtures,
imports, quiet-wall metrics, diagnostic failures and reindexing are exercised
through the shipped `_collect_outputs`, `index_outputs` and `register` paths.
No live worker or generation is involved.

The exact fix is in [commit 87783e2](https://github.com/Chris0Jeky/local-asset-studio/commit/87783e2332567972f0c9b77e4e779c8990ca43f6).
The focused root run passed 46 tests. The deterministic indexing matrix reseals
the retained job binding after each authored mutation, so rejection cannot be
explained merely by a stale outer file hash.

## 2. Read the operation Studio actually prepared

The factory reads actual Production project and budget rows, the materialized
plan, catalog, preset, template, model-library pins, preflight bundle and current
model/input bytes. It records the Workspace identity and uses Studio's existing
deterministic future-job derivation. Trusted source roots are supplied by the
caller, not recovered from a candidate intent.

It supports one regular `comfy.generate.v1` member, with an exact prepared graph
and seed. Unsupported native operations, wildcards, private sources, larger
batches, incomplete dependencies, changed files and an existing future job
refuse. The hook is explicitly before `Studio.create_job`. The reader does not
construct Studio, Production or ModelLibrary and never reserves budget or opens
a runtime connection.

Independent review found a subtle equality error: Python considers an integer
graph value and an equal-valued float equal. A serialized candidate with `7.0`
could therefore match a retained graph containing `7`. Canonical-byte comparison
now binds exact graph, plan, recaptured rows and complete intent. The regression
refuses that numeric alias.

The proof also changes model/input contents while preserving size and mtime.
Fresh hashes detect the drift. Source-observation checks preserve file contents,
paths, permissions and logical database rows. SQLite read-only connections may
touch shared-memory bookkeeping timestamps; that exact SHM mtime is excluded
from the measurement after reader initialization. This is disclosed instead of
claiming that every operating-system timestamp stays unchanged.

These facts prove retained preparation and current serial file agreement.
They do not establish a live queue/GPU lease, available budget permission,
current backend schema or atomic engine-open bytes. The source implementation
and API are in [commit 9ad9db5](https://github.com/Chris0Jeky/local-asset-studio/commit/9ad9db55e2b765aa07741a2dd9415653426ea906).

## 3. Make a claim that cannot be replayed

The dispatch laboratory adds a journal to the existing attempt ledger. Preparing
an operation checks current admission, reserves the exact family/stage/request/
job/Workspace/source/intent/nonce identity and publishes its ticket. Ordinary
admission and export still reject that unresolved reservation.

The specialized claim transaction recognizes only its exact owned prepared
reservation, with no other blockers and unchanged authority/input fingerprints.
It cannot ignore a foreign unresolved ancestor, bypass a failed identity gate,
clone an empty ledger or resolve uncertainty early. A serialized SQLite write
transaction commits `claimed` before publishing the job or invoking the port.

The port inserts one row on every callback. It has no deduplication rule that
could hide duplicates. Backend, budget and lease conditions are injected
simulation values. The existing Studio submit-once protocol remains in place;
the experiment does not assert that base Studio repeats uncertain submissions.

The claim is never rearmed. A crash after claiming but before the callback can
produce zero callbacks and a permanently blocked operation. A crash between
reservation and ticket publication leaves an orphan that is refused. This is an
explicit availability tradeoff: the lab exposes no automatic clear/retry path.
An uncertain job with no observed prompt cannot be resolved by inventing one.

Independent review reproduced three additional defects and the fixes now have
regressions:

| Finding | Corrected behavior |
| --- | --- |
| Caller mutates the graph after admission | Canonical snapshots freeze the operation; callbacks receive copies. |
| Terminal evidence names a different prompt | Reconciliation must retain the exact acknowledged prompt. |
| Workflow changes between validation and ledger reread | The exact validated job/workflow observation hash is required inside the settlement transaction. |

A second authority check after pending-marker publication blocks a withdrawal
during that publication. Such refusal retains the permanent claim. Ledger
resolution and dispatch settlement commit in one SQLite transaction; a failed
observation comparison rolls back both. Actual process stops exercise the four
claim/marker/callback/receipt boundaries. Three independent processes compete
for one ticket and produce one callback.

The implementation is in [commit ccf9ced](https://github.com/Chris0Jeky/local-asset-studio/commit/ccf9cedc47d6f39d905d87eb08ed812f78bb6888).
Full-sync SQLite and process termination tests do not prove physical power-loss
survival or an atomic transaction across files, Workspace and a native engine.
Actual worker adoption must reuse its existing budget, ownership, lease and
pending/receipt paths, then prove the same behavior with a counting transport.

## 4. Verify the handoff independently

The consumer verifier requires the completed READY marker and bound sidecars,
checks supported schema and exact claims, streams copied bytes, reruns identity
gates, validates captured subjects, rebuilds the guarded manifest and compares
the complete admission report. Recursive file references must name declared
files, including those inside open engine metadata. A captured job/output index
must derive the retained Workspace asset ID.

Optional current verification requires explicit original experiments and ledger
roots. It recaptures authority and compares the complete source observation.
Only the transported copied asset-root fingerprint is projected for comparison;
the source/ledger identities, selected concept, policies, annotations and facts
must still match. No root from an untrusted bundle is followed as authority.

The outcome separates local integrity from current authority. After an authored
source withdrawal, offline integrity passes while requested current verification
refuses. A late change to destination bytes clears the integrity flag as well.
Independent review reproduced an internally inconsistent captured output index;
the deterministic ID/index invariant now rejects it even after outer hashes
are recomputed.

Hashes remain unkeyed integrity records. A coherent descriptive edit, with all
corresponding hashes updated, can still pass internal consistency. A passing
control demonstrates that limit. Every result keeps owner authentication,
generation, production promotion and native-import authority false. This is
not a signature system or a visual reviewer.

The inspected Lumenfold direct importer is unchanged. It does not enforce this
Studio extension or READY gate and still needs staged native promotion/rollback
work. The existing [contract analysis](LUMENFOLD_CONTRACT.md) and #3175 retain
that boundary. No current draft should be placed in its scanned native roots.

## Reproduce and adopt

Run from the Studio root in its existing Python environment:

```powershell
py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/owner-continuation-proof-1 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
```

Use a fresh output directory. On Linux replace `py -3` with `python`. The optional
`--lumenfold-root` supplies the independently trusted pure validator/schema at the recorded pin;
without it, the two optional source-comparison tests are explicitly skipped. The staged-export helper checks source hashes before execution; one comparison unittest directly imports the trusted caller-supplied validator, so that test path is not a pre-execution hash gate. The actual supplied snapshot matched the recorded pins.
Synthetic fixtures, databases, bundle copies, process contexts and logs remain
under `.runtime/`. The original 202-test evidence is preserved separately.

The first expanded run passed 303 tests without skips in 119.901 seconds using
the pinned validator. It ran on Linux x86-64, CPython 3.12.14 built with Clang
22.1.3, Pillow 13.0.0, jsonschema 4.26.0 and psutil 7.2.2. No C++ compilation was
performed; no MSVC flags apply. The second fresh run passed the same **303 tests**, with **2 optional source-comparison skips**, in **113.942 seconds**; all **11/11 deterministic output hashes** matched. The full repository rerun passed **7,321 tests**, **62 skips**, in **605.399 seconds**. `validate-repo.py` passed **98 preset graphs**, **194 model pins**, **4,992 tracked paths**, **167 LoRA names**, **743 media entries** and **102 references**. Exact commands and log hashes are retained in the run's VERIFICATION.md. Windows, NTFS, MSVC-hosted Python, ROCm/HIP and native
applications remain owner-side verification work.

The updated ADOPTION.md assigns the next measurable moves:

- **Studio agents:** 0 → 1 existing-worker adapter passing 12 boundary cases
  with a counting transport; zero additional callbacks after a retained claim.
- **lf-characters-3d:** 0 → 1 native consumer adapter calling the verifier, with
  one valid isolated draft and six failures that preserve the accepted pack.
- **lf-anime-look:** qualify three matched native lighting conditions and the
  exact face/outline/motion dependencies; retain the separate native receipt.
- **Owner and Studio:** 0 → 1 attributable accepted Sable A2 source mapping
  before new art work. The proposed maximum-12-attempt study remains unarmed.

No new third-party implementation, model or dataset is vendored. New source is
run-owned code using the existing Studio contracts. Retained code provenance
remains explicit; no public licence grant is invented for either repository.
Runtime dependency licences remain CPython PSF, Pillow MIT-CMU, jsonschema MIT
and psutil BSD-3-Clause. Existing model/output licence analysis is retained in
[SOURCES.md](SOURCES.md) and [FIRST_CHARACTER.md](FIRST_CHARACTER.md); none of
these software results clears a missing content-rights decision.

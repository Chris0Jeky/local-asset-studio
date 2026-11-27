# Continuation verification — 2026-11-27 UTC

This section records the expanded continuation. The original proving record below
is retained as history; BASELINE_EVIDENCE.json and BASELINE_OUTPUT_HASHES.sha256
preserve its deterministic 202-test snapshot. Software evidence is implemented.
No generated character, owner art review or native import is claimed.

## Exact commands and outcomes

All commands ran in `/workspace/scratch/fa96af8f7cc8/studio` on the Linux sandbox.
Sources were read through the GitHub connector. No clone/fetch/raw-GitHub shell
networking was used. All writes to GitHub used the connector and the authorized
branch, with at most ten changed files in each commit.

```sh
python prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/continuation-proof-1 --lumenfold-root /workspace/scratch/fa96af8f7cc8/context_lumenfold/sources

python prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/continuation-proof-2 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256

python -m unittest discover -s tests

python scripts/validate-repo.py
```

| Check | Outcome |
| --- | --- |
| Expanded proof with pinned Lumenfold pure validator/schema | **303 tests**, **0 skips**, 0 errors/failures, **119.901 s**, exit 0 |
| Expanded standalone proof with recorded evidence/hash checks | **303 tests**, **2 optional source-comparison skips**, 0 errors/failures, **113.942 s**, exit 0 |
| Deterministic comparison | **11/11 output hashes identical** across separate fresh directories; recorded evidence and hash manifest match |
| Repository regression rerun | **7,321 tests**, **62 skips**, **605.399 s**, exit 0 |
| Repository validator | **PASS**, exit 0: **98** preset graphs/bindings, **194** pinned assets, **4,992** tracked paths, **167** LoRA names, **743** media entries and **102** references |
| Fixed-base byte audit | **4,930/4,930 Git blobs match** commit `0270760a3d4fd9e005a1788bba59d8242b77c2f4`; no base app/catalog/launch/source changes |

The final reporting review also distinguished the staged-export helper's hash-before-execution guard from one optional comparison unittest, which directly imports its independently trusted supplied validator. The README and ADOPTION now state that boundary. The recorded source matched both pins; no result or code changed.

The two optional skips are the exact-consumer-source tests in test_admission and
test_export_guard. They passed in the first run using the independently supplied
20-file pinned Lumenfold source snapshot. The second run did not inherit that
root. The bundled exact schema remains checked in both runs. No Lumenfold native
importer was started.

The host environment was CPython **3.12.14**, built with **Clang 22.1.3**, on
**Linux 6.18.57 x86-64 / glibc 2.41**. Existing package versions were Pillow
**13.0.0**, jsonschema **4.26.0** and psutil **7.2.2**. No packages were upgraded.
No C++ compiler was invoked; MSVC/C++ flags are not applicable. Windows-hosted
Python, NTFS publication, MSVC, RX 9070 XT, ROCm/HIP, ComfyUI model execution,
Blender and Unreal were not tested. The README provides the requested `py -3`
owner command; cross-platform deterministic matching remains a measured owner
check, not an inferred pass.

## Runtime evidence and compact committed copies

All generated fixtures, SQLite databases, process contexts, copied bundles,
stdout, test logs and environment/timing observations remain uncommitted under
`.runtime/pro/P36-B-20261126-2/`. A fresh output directory is mandatory. Existing
output is refused and retained for inspection.

EVIDENCE.json is the normalized aggregate. INDEXING_EVIDENCE.json,
PREPARATION_EVIDENCE.json, DISPATCH_EVIDENCE.json and CONSUMER_EVIDENCE.json are
compact copies of the four deterministic matrix outputs. OUTPUT_HASHES.sha256
uses the eleven runtime output names; each line is `<sha256>  <relative path>`
with LF endings. Random identities, source-root-bound receipts, timing and host
observations are intentionally excluded from those deterministic files.

| Proof matrix | Observed contract results |
| --- | --- |
| Actual indexing | 4/4 valid captures; 6/6 meaningful provenance changes refused; the old raw-equality predicate rejects all 4 valid controls |
| Prepared intent | 12/12 changed preparations refused; 13 initial valid controls; 13 read-only cases preserve retained bytes and logical rows under the explicit SHM-mtime scope |
| Durable dispatch | 23/23 outcomes, 10 expected simulated callbacks, 0 extras; four process-crash boundaries; one callback from three competing processes |
| Independent consumer | 13/13 outcomes: 5 passes with their limits and 8 refusals; source withdrawal leaves offline integrity but fails requested current authority |
| Existing semantics/authority | 0/8 invalid semantic passes; 0/9 stale-authority passes; all original controls retained |

These are authored synthetic software cases, not an estimate of real-image
identity precision/recall. The local callback counter counts every insertion and
has no deduplication rule. It does not issue a request to a backend. Every native,
owner-authentication and real-generation claim remains false.

## Review-driven corrections and focused checks

The actual-indexer correction first reproduced six failures against the former
authority implementation, then passed 46 focused tests in the integrated root
checkout (12.432 s). Consumer development reproduced and fixed a captured
job/index/asset-ID inconsistency and late-destination integrity reporting; the
root's 32-test consumer run passed in 19.403 s. Prepared-intent review reproduced
a serialized integer/float graph alias and added strict canonical comparisons;
its 24 focused tests passed before integration.

Independent dispatch review reproduced mutable caller intent reaching a changed
callback, wrong acknowledged prompt acceptance, and unconstrained reread during
reconciliation. Canonical snapshots, exact prompt identity and transaction-pinned
observation corrected them. Six independent regressions pass; the integrated
coordinator/review/ledger focused run passed **53 tests in 10.806 s**. Four process
crash boundaries are measured separately by the deterministic proof. A process
driver class-identity issue was exposed by the first cross-process run and fixed
by using the canonical simulation module in the CLI.

A consumer test run initially stopped before fixture setup because the shared
workspace volume was full. No external data was deleted; after capacity became
available the focused and complete runs passed. This is not presented as an
application failure or a successful test.

Serial source reads are not a distributed transaction. SQLite `synchronous=FULL`
and process-kill tests are not proof of physical power-loss survival. Synthetic
backend/budget/lease values are not observations of the owner's workstation.
The tested pre-create hook still needs adaptation into the actual existing
worker, and native staged promotion/rollback remains planned in Lumenfold #3175.

## Retained runtime log hashes

These logs are uncommitted and reproducible; they are not part of the stable
output manifest because timings/host observations vary.

```text
0cb6ecf2339dd44d19c91468deed8943f292b304cd84c7001a20eee2c43c0683  continuation-proof-1/tests.log
41b985a5f7c8ef136202bcdbe997adb4c09af5a7db4f473ec2bd067c75ccc55c  continuation-proof-2/tests.log
b1b9276162b3ce71cae3e5df3d9bb19b29ab6b8ebadb23c6dbc2d3950d948e50  full-suite-continuation.log
60f9cd4e2f27063a139c118852b039609d8d7aef5c842dd943ff40f34dee680e  authority-indexing-continuation.log
ad5a41e8205ddede640651d511f777d9cf3ecd5ae549790785517522d88a8845  consumer-continuation.log
e84536074c43f5e18a5fe30fe51e1b6aa2d4ad0e1e9cf19470ea045ec4022d94  dispatch-reviewed.log
```

## Final publication audit

Local publication inventory: **62 UTF-8/LF text files**, no images or binary outputs, **69 valid relative Markdown links**, every file below 300 KB and the complete deliverable below 3 MB. The largest file is the retained pipeline.py at 31,932 bytes. All 4,930 original base blobs match. The GitHub tree at publication commit `70e69c0` was read through the connector: all **62** changed files exactly matched local Git blob hashes, all **4,930** original blobs were unchanged, all **28** README relative targets were on the branch, and there were **0** outside-scope changes or omitted deliverables. That checkpoint totaled **770,386 bytes**; the closing RUN_STATE/verification update is checked again before ready-for-review. Exact closing bytes are reported in the PR. The existing Lumenfold issue received continuation comment `7206910459`; the report-only Drive copy was uploaded and read back with matching name, 15,149-byte size and the existing run-folder parent. No main/other-branch push or merge occurred.

Validator log SHA-256: `4852d553a888de72d26122d350067b1409a6a2aea7cf1a2ca5e493be31496252`.

---

## Original first-pass verification record

# P36-B-20261126-2 verification record

## Result and evidence state

**Implemented software; real-character and native results remain planned.** The final integrated proof passed 202 tests with the exact inspected Lumenfold validator supplied. A second run without that optional source passed the same 202-test discovery, with only the two consumer comparisons skipped, and reproduced all seven deterministic output hashes exactly. The complete synthetic handoff contains eight fixture stage receipts and 26 copied, verified files; it remains a draft with direct native import disallowed.

The kill criterion is exercised through required proxy/semantic failures, root changes, current authority withdrawal, no-output uncertainty and provenance conflict. Every authored invalid semantic case and current-authority case refuses; valid controls pass. These are deliberately constructed software challenges, not a representative sample of real anime outputs or a perceptual accuracy estimate. See [EVIDENCE.json](EVIDENCE.json), [OUTPUT_HASHES.sha256](OUTPUT_HASHES.sha256) and [README.md](README.md).

## Host and source identity

| Item | Actual environment or provenance |
| --- | --- |
| Host | Linux 6.18.57, x86_64, glibc 2.41 sandbox |
| Interpreter | Python 3.12.14, build dated 25 August 2026 |
| Interpreter compiler metadata | Clang 22.1.3; this is how the supplied Python was built, not a project compilation performed by this run |
| Project compiler / flags | No C++ compiler invoked; no MSVC run or flags; Python commands below ran as interpreted code |
| Existing dependency versions | Pillow 13.0.0, jsonschema 4.26.0, psutil 7.2.2 |
| Dependency licences | CPython: PSF; Pillow: MIT-CMU; jsonschema: MIT; psutil: BSD-3-Clause |
| Studio source | `0270760a3d4fd9e005a1788bba59d8242b77c2f4` |
| Retained unmerged P36 source | PR #2046, `80b274e8dde6b0333c4d39a9473f6e15e41f38e1`; ten exact files, verified by `UPSTREAM.json` before each proof |
| Lumenfold source | `19d86763944e842cbce6a3b6ae13f7abc1464b37`; twenty inspected source files recorded in the report's `LUMENFOLD_SOURCES.json` |
| Work directory | `/workspace/scratch/fa96af8f7cc8/studio` |
| Source transport | GitHub connector only. The supplied attachment was checked against the exact base tree; five differing launcher files were replaced from connector reads. All 4,930 base file blobs then matched. |
| Source changes | Run-local prototype and report files only. All 4,930 original base file blobs still match after the work. |

No installed ComfyUI, model, package or owner output was edited. No native app, generator, worker submission or GPU workload ran. Current app/catalog/listener/page-load implementation is unchanged. Source licence terms for proposed models are separate from these code-dependency licences and are recorded in the first-character report; no new third-party code, model or dataset is vendored.

## Commands that actually ran

Commands ran from the Studio work directory above on 26 November 2026 UTC. Logs and large, regenerable fixtures remain beneath `.runtime/pro/P36-B-20261126-2/`.

| Check | Observed result | Runtime record |
| --- | --- | --- |
| `python -m unittest discover -s tests` | Exit 0; **7,321 tests**, **62 skips**, **615.292 s** | `full-suite.log` |
| `python scripts/validate-repo.py` | Final result recorded below | `repo-validation-final.log` |
| Final proof with pinned consumer | Exit 0; **202 tests**, **0 skips**, **91.602 s** for its unittest section | `proof-final-1/tests.log`, `tests-summary.json`, `environment.json` |
| Standalone repeat with exact evidence/hash checks | Exit 0; **202 tests**, **2 optional skips**, **88.447 s** for its unittest section; all **7 hashes identical** | `proof-final-2/tests.log`, `tests-summary.json`, `OUTPUT_HASHES.sha256` |

The first final proof command was:

```sh
python prototypes/pro/P36/P36-B-20261126-2/prove.py \
  --output .runtime/pro/P36-B-20261126-2/proof-final-1 \
  --lumenfold-root /workspace/scratch/fa96af8f7cc8/context_lumenfold/sources
```

The standalone repeat was:

```sh
python prototypes/pro/P36/P36-B-20261126-2/prove.py \
  --output .runtime/pro/P36-B-20261126-2/proof-final-2 \
  --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json \
  --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
```

The second run's two explicit skips were `test_pinned_lumenfold_validator_checks_staged_copy` and `test_supplied_lumenfold_validator_checks_real_fixture_bytes`: both require an independently supplied `P36_LUMENFOLD_ROOT`. Both passed in the first run. The base suite's 62 skips remain skips, not passes or machine qualification. Prototype tests are discovered separately from the root `tests/` suite; repeated component runs are not added to the final count.

Captured log identities, for this observation only:

| Log under the runtime root | SHA-256 |
| --- | --- |
| `full-suite.log` | `b08723cb0d0ee86d7dbcab16a187cf1122800d12124a777cad8fc160a6f1a6a7` |
| `proof-final-1/tests.log` | `eb896e559441e7657e1568914eb84c35d42023cc3cd86b8770ab81d8c176742f` |
| `proof-final-2/tests.log` | `aad65fc9d41db12a61ad868a9d9698122204e5bd99126b35fbb2c65e7f8710a1` |

Log timings and path-bound reports naturally differ across runs. The proof's timing diagnostic used 50 descriptor checks: the two run medians were 0.764 and 0.614 ms; nearest-rank p95 values were 1.594 and 1.419 ms. These measure host Python descriptor-check overhead only. They are not performance targets or a claim about model/GPU throughput.

## Deterministic evidence

The proof verifies all ten retained-source SHA-256 values before testing. It then regenerates `evidence.json`, `family.json`, `workspace-binding.json`, `semantic-policy.json`, `annotations.json`, `metadata.json` and the guarded `pack.json`. `OUTPUT_HASHES.sha256` records `<sha256>  <relative-output-path>` with LF endings. `--check-hashes` compares the complete manifest byte-for-byte; `--check-evidence` also compares the parsed evidence document.

Both final runs produced identical bytes for all seven outputs, despite fresh runtime paths and random reservation nonces. The evidence projects stable outcomes; path-bound authority/ledger reports, nonces, SQLite bytes, staged observations and timings are deliberately excluded from that deterministic set. The deterministic `pack.json` records the guarded manifest; `staged/pack.json` additionally binds that specific staging observation.

The observed challenges are:

| Case set | Baseline | Current result |
| --- | --- | --- |
| 8 invalid descriptor challenges | Deliberately weak mean-only control: 8 invalid admissions; retained hard numeric proxy: 7 | 0 invalid admissions |
| 2 valid descriptor controls | Matching concept and allowed costume context | 2 admitted, 0 false rejections |
| 9 stale/wrong-context actual-Workspace fixture cases | Retained offline gate passes all 9 after mutation | 0 pass after current-authority capture; 9 pre-mutation controls pass |
| Replayed request / unresolved no-output attempt | One durable identity | 0 repeated submissions; fresh request refused |
| Exact terminal observation changed later | Earlier completion retained | Inspection and fresh same-stage reservation both refuse |
| Reused bytes with conflicting commercial declarations | Retained exporter keeps earlier `yes` despite later `no` | Guard refuses `artifact_provenance_conflict` |
| Complete fixture handoff | Eight stage heads | 26 copied files verified, unchanged pack-v1 schema, draft status, direct import false |

Windows and other dependency builds remain a reproduction gate. The published hash match was observed on the recorded Linux environment. A different imaging-library build may require investigation; do not relabel a mismatch as success or replace expected hashes merely to make the command pass.

## Independent review corrections retained as regressions

Component and integration review found concrete failures before closeout. These were reproduced and corrected in source, then included in the final 202-test run.

| Finding | Implemented correction / regression |
| --- | --- |
| A requested stage subset could omit concept authority | Expand full ancestor closure; validate current concept/card/acceptance even for a later selected stage |
| Malformed Workspace fields could escape strict subject checks | Validate primitive types, review enumeration, card body and metadata before capture |
| Other source Workspace/job could clear the wrong reserved attempt | Bind Workspace, source-root identity, intent and fresh nonce; require the exact worker marker; refuse preexisting unrelated jobs |
| Changed resolved evidence still allowed a new reservation | Re-observe retained same-stage terminal evidence before creating a fresh request; two failing regressions became green in the 24-test ledger suite |
| Acceptance withdrawn during last copied-file verification could receive READY | Capture current authority after the longer destination validation; retained regression refuses |
| CLI input changed during final capture could receive READY | Reopen exact CLI inputs after the final authority capture as well as earlier in staging |
| Copied asset / pack / authority sidecar changed during final capture could receive READY | Observe all manifest assets and all eight written sidecars before/after verification and after final capture; three failing regressions became green in the 26-test admission suite |
| Lone-surrogate diagnostic could escape failed-report hashing | Bound and normalize diagnostic strings into valid UTF-8 |
| Timing p95 rank was floored | Use documented nearest-rank ceiling |

The final independent reviewer found no remaining blocking issue within that bounded scope after the destination-guard sanity check. This is code/test review, not review or acceptance of a generated asset. Final destination observations close ordinary changes during the longer checks; they do not make the file/SQLite reads atomic or defend against a writer restoring every stat field. A native consumer must still rehash and recapture authority at its mutation boundary.

## Repository and publication gates

`python scripts/validate-repo.py` completed with exit **0** after staging the complete local inventory: **98 preset graphs/bindings**, **194 pinned assets**, **4,967 tracked paths**, **167 LoRA names**, and **743 local-media manifest entries / 102 references** checked. This inventory consists of the 4,930 unchanged base files plus **37 run deliverables**. The base snapshot's two ignored TLS test fixtures were explicitly included in the local validation index; they are unchanged existing repository fixtures and are not additions to the published diff.

Local delivery inspection found **37 UTF-8/LF text files**, aggregate below **0.5 MB**, largest **31,932 bytes**, **0 images/binary artifacts**, **0 broken local Markdown links**, and no changed original base blobs. Runtime outputs and bytecode are excluded from publication. All README-listed source/report files are present. GitHub readback of verification checkpoint `7d2848c` confirmed all 37 local deliverable blobs, all 4,930 unchanged base blobs, and zero extra changed paths. The final run-state commit is checked again before the PR is marked ready.

The run's [README](README.md) inventories every source/test/evidence/document deliverable. Publication checks verify all named repository files exist, all added paths are under the two requested run directories, no original base file changed, text is UTF-8/LF, each deliverable is below 300 KB, the aggregate is below 3 MB and no images or binary/model/generated runtime files are added. The GitHub branch is read back through the connector and compared by Git blob identity with local deliverables before ready-for-review handoff.

The [Lumenfold issue addendum](https://github.com/Chris0Jeky/lumenfold/issues/3175#issuecomment-7205798489) was published and read back; issue #3175 remains open for worker/current-authority integration, staged native import, rollback and owner/native acceptance. Four report Markdown copies are in the requested [Drive run folder](https://drive.google.com/drive/folders/1H9obf-Zh9OPR7V4Qst4ds1XZ5tjkGfYh); upload results and subsequent metadata reads confirm their filenames, sizes and parent folder. No repository/source/model archive was put on Drive.

## What remains unverified

- Exact accepted Sable A2 bytes, current acceptance scope, real-image identity quality and native source mapping. Synthetic fixtures supply none of these decisions.
- Windows 11, MSVC execution, AMD RX 9070 XT/ROCm/HIP, local installed model completeness, ComfyUI generation and the owner's live queue.
- The future worker's universal use of reservations and existing budget/GPU-lease/submit-once controls. This prototype never dispatches.
- Native geometry, decoded rig and expression compatibility, Blender finishing, Unreal import, AnimeLook, motion, promotion and rollback. Current importer enforcement of the new marker/extension is absent.
- Authentication of annotators, acceptance declarations and semantic policy. Hashes identify contents; matching assertions are not proof of visual truth or rights.
- Cross-system atomicity or durable recovery of every future engine mutation. READY is completed local draft staging with mandatory later revalidation.

[ADOPTION.md](ADOPTION.md) gives the next owner/Studio/character/look commands and numerical targets. The immediate real-content target remains **0 to 1 exact accepted Sable A2 mapping**. This run grants no generation budget or new licence clearance.

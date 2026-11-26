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

Local delivery inspection found **37 UTF-8/LF text files**, aggregate below **0.5 MB**, largest **31,932 bytes**, **0 images/binary artifacts**, **0 broken local Markdown links**, and no changed original base blobs. Runtime outputs and bytecode are excluded from publication. All README-listed source/report files are present. The final GitHub tree comparison is repeated after the verification checkpoint and final run-state commit.

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

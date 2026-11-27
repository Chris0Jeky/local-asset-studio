# Verification record — P36-B-20261125-1

## Exact scope

Software is implemented and tested. All real character output remains planned.
No generation, real-media inspection/acceptance, native import or playback was
performed. Synthetic fixtures are procedural software inputs, not art results.
The app, catalogue, installed ComfyUI and model files were not changed.

## Final local proof

Working directory: `/workspace/scratch/4ad748138137/studio`.
This is a connector-read source slice, not a cloned or complete Studio checkout.

```bash
python prototypes/pro/P36/P36-B-20261125-1/prove.py --output .runtime/pro/P36-B-20261125-1/proof-final-2 --lumenfold-root /workspace/scratch/4ad748138137/lumenfold-context --check-evidence prototypes/pro/P36/P36-B-20261125-1/EVIDENCE.json --repetitions 100
```

**Exit 0.** 84 tests, zero failures/errors/skips. Twenty labelled scorer cases
reproduced exactly. The actual supplied Lumenfold validator passed with
`check_files=True` against 26 synthetic files. All four lines of the regenerated
`SHA256SUMS.txt` matched committed `OUTPUT_HASHES.sha256` byte for byte. Earlier
independent runs also matched; no timing/environment field is part of those hashes.

Environment from that final proof:

```json
{
  "benchmark": {
    "max_ms": 25.793000999328797,
    "median_ms": 13.879805000215129,
    "operation": "full eight-stage metadata gate (no disk I/O)",
    "p95_ms": 18.05142400007753,
    "repetitions": 100
  },
  "compiler": "not-applicable; Python prototype; no MSVC/Unreal run",
  "consumer": {
    "check_files": true,
    "native_import": "not-run",
    "schema_sha256": "9892f716abfff35a85088c5b5c798a8ae38ddbff50f1e67845f799c7af16a28a",
    "status": "passed",
    "validator_sha256": "268588d7d01d09f9c597dce7c7dfafe050066586702676cfe633bad941af4de7"
  },
  "machine": "x86_64",
  "os": "Linux-6.18.57-x86_64-with-glibc2.41",
  "pillow": "13.0.0",
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "tests": {
    "errors": 0,
    "failures": 0,
    "run": 84,
    "skipped": 0
  }
}
```

Additional installed dependency: jsonschema 4.26.0, MIT. Pillow 13.0.0's installed
metadata identifies MIT-CMU; Python is PSF-licensed. No dependency was installed or
upgraded by this run. The Clang string identifies the interpreter build; no C/C++
compilation or compiler flags were used. MSVC, Windows 11, ROCm/HIP, RX 9070 XT,
Blender, Unreal and real asset generation were not run or qualified.

The timing above is 100 repetitions of a complete eight-stage **metadata** gate,
with no disk I/O. It describes this sandbox only. It is not generation speed,
end-to-end asset latency, an AMD benchmark or a comparison with another implementation.

Both CLI and test-runner paths suppress source-tree bytecode generation. The final
run left no `__pycache__` beneath the prototype; generated fixtures, test scratch,
logs and evidence remained under `.runtime/`.

## Full Studio hosted check

The local proof is not the repository's full suite. No partial sandbox discovery
was represented as `python -m unittest discover -s tests`.

The unchanged existing `Check studio` workflow ran:

```bash
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The first command is the repository's full-suite lifetime-diagnostics wrapper.
The normal owner proving command remains `python -m unittest discover -s tests`.
The workflow also installs the repository's existing requirements into its disposable
GitHub runner; that is not a change to the owner's ComfyUI environment.

Confirmed successful checkpoint:

- Source head: `61dcaa78d260ea5fb32057ef9489850dd860385c`.
- [Run 45529356066](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/45529356066), job `138920608372`, conclusion `success`.
- Checked merge commit: `fe6fef345699c7222f96f7fd30ef47e0aff3a801`; tree `55a1e5afd60a336571e929a76f25ea145bffbd34`, matching the source tree.
- Ubuntu 26.04.1 x86_64, CPython 3.12.16; no native compiler invocation.
- 7,321 tests in 1,054.895 seconds; `OK (skipped=124)`.
- Repository validator: 98 preset graphs/bindings, 194 pinned assets, 4,940 tracked paths; 743 local-only manifest entries / 102 references checked; 167 LoRA names checked.
- Earlier planning-only runs were superseded/cancelled by branch updates; they are not reported as successful checks.

Hardened source checkpoint `3a05f8844a60545d7985fd2dc3b6e8875a36e145` has its own
[run 45531869680](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/45531869680).
That run also completed successfully: 7,321 tests in 1,040.121 seconds,
`OK (skipped=124)`, and the repository validator passed 98 preset graphs/bindings,
194 pinned assets and 4,943 tracked paths. The checked merge commit was
`a68d9a149b12e247153117b823f04b8557cae7a1`, tree
`30aa21426c6b25796095465121d8f086b6e60a58`, matching that source tree.
Job `138928900920` used Ubuntu 26.04.1 / CPython 3.12.16.

Publication checkpoint `1271fc4358079c9b8c254d93eb9117ba91b8156b` differs from
`3a05f88` in executable source only by CLI bytecode suppression; the complete
84-test proof above was rerun after that source change. Remaining publication
changes are docs/evidence. No successful CI result is inferred for a newer head;
the final PR shows the separately triggered current checks.

## Contract and independent review

Lumenfold source used locally came from the user-supplied archive, with selected
contract/pipeline files extracted. No whole repository was copied. The actual
schema was also fetched through the connector at Lumenfold commit
`8462d5d3d320d0802f7c491824c97827b1800bcd` and matched Git blob
`fd00e2fb6de69b80b3b0756ab89fcbfb32945b37` and the schema hash in the proof.
No upstream validator or native implementation was vendored.

A separate reviewer independently ran 84 tests and all 20 scorer scenarios. The
following reported defects were corrected and covered by the named checks:

| Defect | Regression / current proof |
| --- | --- |
| Unmeasured production RGB anchor | `test_production_colour_anchor_must_be_pixel_measured` |
| Later-stage ROI overwrites concept measurement | `test_later_stage_roi_cannot_satisfy_a_false_concept_anchor` |
| Malformed quality references | `test_native_quality_reference_requires_nonempty_text` |
| Fixture recipe/quality relabelled production | `test_production_cannot_relabel_explicit_fixture_recipe`, `test_production_quality_cannot_carry_fixture_marker` |
| Private root bypass | `test_private_named_root_is_rejected_before_opening` |
| Unsupported colour/alpha interpretation | `test_encoded_colour_contract_rejects_linear_or_premultiplied_images` |
| Portable device names / traversal | `test_portable_paths_reject_traversal_windows_drives_and_reserved_names` |
| Idempotent admission skips changed bytes | `test_idempotent_production_record_still_verifies_media` |
| GLB renamed to VRM | `test_glb_renamed_vrm_does_not_establish_vrm_format` |
| Invalid inactive history | `test_unreferenced_history_tampering_is_detected` |
| Invalid pack metadata writes output | `test_schema_invalid_metadata_cannot_publish_handoff` |
| Diagnostic-view mismatch | Independent properly bound extra-view probe; ignored view cannot satisfy required coverage |

A final documentation review also found and corrected a circular native requirement:
`unreal` now consistently means pre-export handoff readiness. Actual native import,
playback and acceptance are a separate mandatory downstream consumer receipt; eight
prototype receipts do not establish a playable character.

Reviewer finding disposition: no blocker remained among those reviewed. This is
bounded code review, not qualification of native assets or all possible hostile
inputs. Caller assertions still require authoritative Workspace integration.

Final local core SHA-256 identities:

| File | SHA-256 |
| --- | --- |
| `pipeline.py` | `2a709be22f4414ddc243fb4f94a304d5c5a714898c42cdf57447227c1301a5ef` |
| `pack_export.py` | `89ca912e02b2b236d6970d76c2831fe1f2c7e6d64c4e90fa4d2887b571944f79` |
| `consistency.py` | `2797930aa75448f2c2f6cbf52067d2d1802f9850a6c4fb7a8b78dfec37f2695d` |
| `prove.py` | `113b6734937288a0179f225680a53e73158d7da07ec8d08123ada8a275c3e6ea` |

## Remaining verification

- Exact accepted Sable A2 files, source/acceptance scope and native dependencies.
- Live Studio Workspace acceptance/revocation, job uncertainty and queue integration.
- Held-out real-character rubric calibration, including false rejections and proxy blind spots.
- Target Windows/Python/dependency compatibility and filesystem behavior.
- Native decoded geometry, rig, materials, expressions, motion/contact and Unreal playback.
- Actual model/reference/content provenance and intended-use decisions for all ancestors.
- Import transaction interruption/recovery and preservation of engine-owned metadata.

These gates are assigned in ADOPTION.md and Lumenfold issue #3175. A generated file,
valid hash, passing proxy or successful command never supplies their missing evidence.

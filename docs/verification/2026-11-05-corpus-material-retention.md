# Corpus material retention — 5 November 2026

Refs #1983. The code change removes a reproduced source of repair collateral; the realistic-v2 benchmark remains
open. No previous repair rate is recalculated from a unit test.

## Cause and change

Inspected against main `c07dfc216e700002fd4aa54b5f874d5c109d1fa5`. `seed_defect("material-mismatch")` already
selects an existing alternate material. Before this change, `corpus_defect` first set `use_fake_user` on every
material, including unused ones. Because the alternate selection and scene manifest both include materials with
nonzero `users`, an unused `Material` became eligible and remained in the manifest after the original slot was
repaired. This does not require a new datablock to be created.

The corpus path now asks the shared seeder to retain only the displaced original. The seeder selects the target
slot and existing, used alternate before changing any retention flag. If no target or distinct used alternate
exists, the corpus reports `NotApplicable` without changing materials. The transient sentinel self-test retains
its previous behavior. The semantic checksum and the typed repair vocabulary are unchanged.

## Verification

`tests/test_blender_corpus.py` exercises the production functions with a small model of Blender ID user counts.
Before the fix, three regressions failed: an unused alternate was promoted and selected; missing target slots
still mutated retention; and a scene with only one used material was incorrectly considered applicable. All
three pass after the fix. A fourth check keeps the transient sentinel behavior unchanged. These offline tests
are not native Blender evidence.

The focused `python -m unittest discover -s tests -p 'test_blender*.py' -v` run passed **174 tests, including 14
native skips**, with zero failures or errors. Its first attempt could not import `psutil`; rerunning after the
test host installed the repository-pinned `psutil==7.2.2` produced this result. Python compilation and
`python scripts/validate-repo.py` also passed. The integration PR records the full-suite and hosted CI receipts.

An opt-in native test, `LiveCorpusTests.test_material_swap_repair_preserves_native_checksum_after_reopen`, runs
`tests/blender_corpus_material_probe.py` in an explicitly configured Blender. It creates the geometric lab fixture
and an unused material, seeds the defect, saves and reopens it, repairs the slot through `Worker.apply_edit`, then
saves and reopens the repair. It checks the native material membership and canonical checksums before/after.
This test is skipped when `LAS_BLENDER_LAB_EXE` is unset; Blender is unavailable in this development environment.

Run the focused native check on the configured workstation from the repository root (PowerShell):

```powershell
$env:LAS_BLENDER_LAB_EXE = (Get-Content config/local.json | ConvertFrom-Json).blender
python -m unittest discover -s tests -p test_blender_corpus.py -k material_swap_repair -v
```

## Retained hosted qualification (pending execution)

The separate **Native material retention (opt-in)** workflow requests this same
synthetic native gate when a scoped PR body contains the exact text:

```text
Native Blender material retention qualification: requested
```

It handles PR open/update/reopen/body edits and manual dispatch, uses ordinary
`pull_request` with `contents: read`, checks out the exact PR head and uses no
secrets or persisted checkout credentials. Unmarked PRs skip the job. The shared
[explicit runtime bootstrap](../PROCEDURAL-NATIVE-CI.md) verifies the official
archive checksum before extraction and requires Blender 5.4/build `6f4fc760c138`.
The existing shading workflow and shared bootstrap/identity helpers are unchanged.

The job sets `LAS_BLENDER_LAB_EXE`, `LAS_REQUIRE_MATERIAL_NATIVE=1` and
`LAS_MATERIAL_EVIDENCE` to a new evidence directory. Missing native configuration,
reused output, a nonzero exit, timeout, missing artifacts or failed material/checksum
assertions cannot pass. A post-test check requires the actual passed receipt, so a
skipped or undiscovered test cannot satisfy the requested qualification.

The artifact retains source commit/tree and file hashes, argv and the 120-second
process budget, stdout/stderr/exit status, stage checkpoints and manifests,
`material-repair.json`, clean/damaged/repaired BLEND files, generated PNG and output
hashes. A failed attempt keeps its available evidence; it never overwrites an old
attempt. Runtime checksum/identity receipts and logs share the artifact. Upload runs
with `if: always()` and requests 30 days retention, subject to repository policy.
The job has 10 minutes; the native test step has a 150-second outer process limit.

No local Blender download or native run is implied by these changes. Hosted
qualification is pending. The original runtime archive is not uploaded, daily
builds expire within 90 days, and evidence retention does not preserve a replayable
runtime indefinitely. No agent/API calls, render benchmark, original realistic-v2
corpus recreation or repair-rate recalculation is part of this gate.

## Remaining acceptance

- Execute the native regression with the configured Blender build and retain its result.
- Rebuild affected material-mismatch variants in a new corpus directory from the original realistic-v2 controls;
  an already saved variant can still contain the historical orphan and is not repaired by changing the seeder.
- Rerun the material-mismatch repair cases on the workstation, one asset at a time under the existing heavy-work
  lease. Keep earlier reports and record the new corpus/source identities before comparing rates.
- Keep #1983 open until that native corpus and benchmark qualification is recorded.

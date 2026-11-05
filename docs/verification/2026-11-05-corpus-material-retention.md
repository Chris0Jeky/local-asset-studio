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

## Remaining acceptance

- Execute the native regression with the configured Blender build and retain its result.
- Rebuild affected material-mismatch variants in a new corpus directory from the original realistic-v2 controls;
  an already saved variant can still contain the historical orphan and is not repaired by changing the seeder.
- Rerun the material-mismatch repair cases on the workstation, one asset at a time under the existing heavy-work
  lease. Keep earlier reports and record the new corpus/source identities before comparing rates.
- Keep #1983 open until that native corpus and benchmark qualification is recorded.

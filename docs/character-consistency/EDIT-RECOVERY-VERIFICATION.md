# Character-edit recovery verification — 12 September 2026

## Provenance of this change

The supplied archive names upstream commit `2b911092e889687cd5d247da106f9de0c8348d99`.
Reconstructing its entire Git tree produced
`afe71d1fb3406ec69af7a4bde3399d07805c59b3`, identical to that upstream tree.
Implementation and the local counts below use that baseline. Main subsequently
advanced through #79 (failed-job timing) and #81 (readiness UI); these are not
reimplemented. #80 owns recipe inspection and is also separate.

The claim already recorded on #71 was resumed after the interrupted chat. The
scope is three open follow-ups from #74/#78, not closure of the native integration
issue. No installed model, application, queue, user asset or creative decision was
changed by the local work.

## Tests actually executed locally

Environment: Linux, Python 3.13.5, Pillow 12.3.0. Test fixtures use synthetic
characters, synthetic attestations and substituted model execution; they are not
owner approvals or generated-art evidence.

- Initial causal suite: **24 tests, 15 failures on the unchanged implementation**.
  It reproduced partial final-directory publication, missing final source checks,
  contact mismatch and invalid optional-role/slot-order acceptance.
- Final focused recovery suite: **28 tests passed**, including four added cases
  for staged-byte/receipt corruption, a late destination conflict and receipt size.
- Character-edit subset before those last four additions: **202 tests passed**.
- Final full suite: **804 tests discovered, 797 passed, 7 skipped**, 51.840 seconds.
  Existing Pillow deprecation warnings and a socket ResourceWarning remain;
  this is not a warning-free claim.

Raw logs are retained locally under `.runtime/edit-recovery/`: `causal-before.log`,
`focused-after.log`, `recovery-after.log`, and `full-suite.log`. These logs are not
committed as repository assets. Repository validation and whitespace checks are
reported on the PR after final staging. Hosted merge/Windows checks are separate
from the Linux counts above; the workflow name alone is not a pass result.

## Process-death and integration proof

`RecoveryHTTP.test_killed_collector_retains_lock_then_recovers_same_real_workspace_job`
runs the actual Handler, Production, Workspace and client transport on an ephemeral
loopback port. Only hardware preflight and neural execution are substituted. It:

1. Explicitly stages/starts one ordinary Production project and completes one
   synthetic image through the normal job and Workspace publication path.
2. Launches a separate collector process and calls `os._exit(73)` immediately
   after its candidate image is written. The final directory is still absent.
3. Confirms the retained lock names that exited child. Another Collect is refused
   while the lock remains. The fixture owner removes only that lock after the
   child has exited; product code never steals it.
4. Recollects the same Workspace asset and verifies that the old staging bytes
   remain untouched. There is one original project, one reserved generation and
   zero additional HTTP POSTs, queued work or model submissions during recovery.
5. Composes through the original mask: **4,032 changed pixels**, **zero outside-mask
   changes**, **zero protected-pixel changes** and an unchanged source image. The
   candidate stays `unreviewed` and `semantic_approval: false`.

Additional fault tests cover partial receipt writes, rename rejection, a lost
return after successful rename, source changes during download, existing legacy
partials, empty destinations, symlinks, overlapping commands and stored-byte
corruption. All retain existing evidence; none authorizes another generation.

Contact tests cover pair mismatch, unconnected third actors, missing pair
coverage, reversed/repeated pairs, a connected three-actor chain without invented
clique edges, disconnected groups, scenarios and rehashed invalid plans.
Reference tests exercise real canon/preset preparation and independent handoff
validation, including caller-recomputed hashes and allowed-role controls.

## Reproduce

```console
python -m unittest discover -s tests -p "test_character_edit_recovery.py" -v
python -m unittest discover -s tests -p "test_character_edit*.py" -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The new `Character edit recovery on Windows` workflow runs the character-edit
subset with Python 3.12 and the repository's pinned test requirements. It does
not install ComfyUI or native editors. The existing full Linux suite remains in
`Check studio`; no replacement queue or test-count inflation through inherited
test cases is introduced.

## Explicit limits

No workstation neural repair, native Krita synchronization, universal filesystem
power-loss guarantee, cross-revision budget enforcement or automatic legacy-partial
migration is claimed. The definitive Production creation-rejection recovery
protocol remains separately tracked on #71. The local review was performed by the
implementing assistant, not an independent reviewer. `HUMAN_TODO.md` is unchanged.

# Repair benchmark identity and timeout evidence — 5 November 2026

Scope: [#1986](https://github.com/Chris0Jeky/local-asset-studio/issues/1986), the offline repair-report harness in
`scripts/blender_repair_bench.py`. This changes evidence accounting, not Blender's repair vocabulary or the
historical native results in [BLENDER-LAB.md](../BLENDER-LAB.md#realistic-repair-benchmark-2-nov-2026).

## Reproduced before the fix

- Two reports under `original/` and `renamed-copy/`, carrying the same control semantic checksum
  `25705eb9bb505075252912ca5643343a3a2ac71951ad6f943cec3af14ee17f65`, were accepted as two assets. One exact-repair
  row in each produced `cases: 2`. The directory basename was the identity.
- Distinct assets sharing a directory basename were refused, while `combine` accepted different assets and
  neither `run` nor `combine` persisted content identity.
- The strengthened real-child timeout check failed: `timeout=3` returned after **12.048 seconds**, when a
  child sleeping for 12 seconds released inherited stdout. The earlier POSIX check used an empty string as
  its process-list result, so it could not detect a surviving child.

The added regressions were run against the original production code before implementation: 24 tests ran in
12.118 seconds, with the expected identity/timeout failures and two existing live-Blender skips.

## Implemented contract

`asset_identity` is the control manifest's semantic SHA-256, normalized to lowercase. New runs verify the
manifest checksum before retaining it. Combining runs requires matching asset identities and agents; the
combined report keeps the identity. Aggregation rejects a repeated identity regardless of report location.
Collateral labels include the full identity, so distinct assets with the same directory basename remain distinct.

A legacy report can use only its adjacent `control-manifest.json`, whose kind and semantic checksum must verify.
Report-provided `corpus` and `runs` paths are not followed. Missing identity gives migration guidance; invalid
explicit identity and disagreement with an adjacent manifest refuse. Recombining original runs produces a
self-contained report that can be moved without its manifests. The checksum identifies captured semantic content;
it does not authenticate arbitrary externally edited reports.

POSIX agent launches now create their own session. Timeout cleanup sends SIGKILL only to that owned process
group, then collects output and reaps the parent. Windows retains its PID-scoped `taskkill /T /F` behavior.
The process regression asserts bounded completion, retained output and child termination on the actual host;
on Linux it captures a pidfd while the child is alive and observes kernel exit readiness, including an exited
zombie. Other hosts use a captured psutil process identity. It cleans up only its own child if an assertion fails.

A final-check iteration initially failed because this managed host's `/proc` view sometimes described an older
process at the child's namespace PID: psutil reported a creation time roughly 35 minutes before the new child.
The captured child and parent both had PGID 6, and cleanup sent SIGKILL to group 6. Kernel PID checks observed
the child disappear, while `/proc` status was inconsistent. Using the captured pidfd removes that observer ambiguity;
the production process-group cleanup was unchanged during this test correction.

## Executed checks and limits

```bash
python -m unittest discover -s tests -p 'test_blender_repair_bench.py' -v
python scripts/validate-repo.py
git diff --check
```

The focused module passed: **24 tests, 22 passes and two live-Blender skips**. The final passing run took
3.044 seconds including the three-second real-child timeout. Fixtures use the retained lab-asset and articulated
chest manifests. Coverage includes renamed copies, same-basename distinct assets, missing/malformed identity,
checksum case normalization, corrupt/conflicting manifests, bounded legacy migration, mixed-asset combine,
valid combine persistence, new-run persistence, and existing outage/scoring behavior.

No Blender executable, agent API run, native asset repair or historical benchmark re-aggregation was performed.
The Windows timeout path was retained, not executed on this Linux host. A child that deliberately creates a
different process group is outside this cleanup contract. The full suite and integrated exact-head CI remain the
coordinator's gates; the focused result is not a substitute for them.

Owner items remain open: Studio art direction/replacement of the paused asset wave (#1923), parallax-layer
usability (#1219), and the island default-switch decision. No art acceptance or licensing decision is inferred.

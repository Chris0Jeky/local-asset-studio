# Single-pass Workspace collection counts

Focused optimization under #177 and #175. Those broader issues remain open for
pagination, bounded projections, media/derivative work, heap measurements and
observation transport. Base: `22ec26dc549a4648a6e94f80f5d3c870f03c6520`, whose
exact tracked tree was verified before changing source.

## Existing cost and change

`AssetWorkspace.snapshot()` already reads assets, collections and memberships
within one read transaction. Its final count loop then rescanned every asset
for every collection and searched each asset's membership list. With many
collections this multiplies CPU work even though all membership edges have
already been visited.

Count live memberships during that existing edge traversal instead. Populate
each returned collection's count by dictionary lookup. Assembly work is now
linear in assets + collections + membership edges, rather than a full asset
scan per collection. There is no extra SQL query, cache, persistent counter,
write, migration or change in transaction boundaries.

Trash remains metadata: trashed assets retain their memberships but do not
contribute to visible counts. The prior truthiness treatment of a historical
zero trash timestamp is preserved. Empty collections still receive zero;
collection deletion, ordering, source data and metadata revisions are unchanged.

## Evidence

Four new unittest cases cover sparse/dense/empty/all-trashed counts, restoration,
collection deletion and its existing revision increments, unchanged asset order,
read-only repeated snapshots and an operation-count bound. The oracle computes
counts independently from the returned memberships.

The deterministic performance regression uses 1,000 assets, 100 collections and
3,000 edges, counting accesses to `collections`/`trashed_at` on the actual decoded
asset dictionaries. Original code needed 106,000 such accesses; the new traversal
needs 6,000. The limit of 7,100 allows linear overhead without relying on wall-clock
speed. Changing back to per-collection scans fails that assertion. All four tests
pass after the fix; the other three correctness cases passed before it.

A separate bounded synthetic whole-snapshot benchmark used 10,000 assets,
200 collections and 40,000 edges, one disclosed warm-up and five measured calls
per version, in the same Linux/Python 3.13.5 sandbox:

| Observation | Original | Patched |
| --- | ---: | ---: |
| Median whole-snapshot time | 0.351460 s | 0.126224 s |
| Encoded snapshot bytes | 5,373,088 | 5,373,088 |
| Total live memberships | 34,284 | 34,284 |

These are local microbenchmark samples, not a workstation throughput SLA or a
claim of lower inference memory. **The full-history response is still large.**
This does not implement the pagination or bounded-payload acceptance of #177.

```sh
python -m unittest discover -s tests -p test_workspace_snapshot_counts.py -v
python tests/workspace_snapshot_benchmark.py --assets 10000 --collections 200 --memberships 4 --runs 5
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The benchmark creates and deletes its own temporary synthetic metadata store;
it does not touch user media or initialize Studio. It limits data and repetitions
and uses no extra dependencies. Exact per-run timings, full-suite outcomes and
source identities are retained in the maintenance bundle and PR verification.
Rollback is a code-only revert; there are no cached counts to invalidate.

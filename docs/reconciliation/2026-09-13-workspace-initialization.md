# Workspace initialization under WAL contention

Maintenance for #215. Inspected base: `22ec26dc549a4648a6e94f80f5d3c870f03c6520`,
tracked tree `4768c39cbbbc5f0a6a2a6707fc6f39cde30a382f`. The downloaded tracked
snapshot reproduced that exact tree before editing. This is offline software
work; no owner database or Studio/Comfy process was opened.

## Reproduction and decision

On untouched source, eight brand-new temporary databases with six synchronized
constructor threads each produced two `SQLITE_BUSY` exceptions in 48 calls.
This is a reproduction, not an estimate of the frequency on the owner's PC.
A separate deterministic test retains a real SQLite read lock until the first
WAL transition fails, then releases it. Previously the constructor had already
rejected the client; now it completes without losing the sentinel data.

SQLite's busy handler is not guaranteed to run for lock upgrades that could
deadlock. Merely increasing the connection timeout does not fix that case.
WAL cannot be enabled inside a transaction, so moving it below the existing
migration's `BEGIN IMMEDIATE` would be incorrect. Sources:

- [SQLite busy-handler contract](https://www.sqlite.org/c3ref/busy_handler.html)
- [WAL activation and persistent journal mode](https://www.sqlite.org/wal.html)
- [Journal-mode transaction restriction](https://www.sqlite.org/pragma.html#pragma_journal_mode)

`AssetWorkspace._enable_wal` now isolates that pre-transaction operation. It
retries only `OperationalError` carrying the exact `SQLITE_BUSY` code, with a
15-second monotonic deadline, at most 100 ms SQLite waits and at most 25 ms
between attempts. Each completed failed statement has released its attempt's
locks before another attempt is made. No arbitrary SQL or metadata command is
replayed. A non-WAL result is an explicit initialization failure, not readiness.

On success, the original connection busy timeout is restored before the existing
schema setup and transactional metadata migration. Those statements retain
SQLite's existing timeout policy; the new 15-second deadline is for the WAL
boundary, not a promise of a global startup deadline or bounded OS disk I/O.
Readonly/corrupt databases, other error codes and interruption still propagate.
The existing connection context closes the handle on those failures.

No lockfile, second database, process-global mutex, queue, schema version or
recovery authority is added. SQLite remains responsible for cross-process
locking; the metadata migration retains its existing writer transaction.
A failed schema setup can leave existing idempotent DDL, as before: it is not
reported ready, never automatically retried here, and a later explicit open
can finish initialization. Existing tables/data are never discarded.

## Regression evidence

Ten focused unittest methods cover real lock release, real lock timeout,
synchronized threads and separately spawned processes, sequential reopen,
readonly/corrupt/invalid paths, unsupported journal mode, keyboard interruption,
later schema I/O failure and restoration of the caller's timeout. Separate
processes announce readiness before their shared gate is released. No exception
is invented in the lock-release/timeout cases; a short real busy timeout makes
the early-contention failure observable deterministically on CI.

The initial eight-method suite failed three assertions on unchanged code.
The final ten methods pass; all 26 existing metadata tests also pass. Full-suite
and hosted Linux/Windows results are recorded in the PR and downloadable logs.
The original full baseline was 1,571 tests, 15 skipped, zero failures; existing
Pillow/socket warnings remain disclosed rather than suppressed.

```sh
python -m unittest discover -s tests -p test_workspace_initialization.py -v
python -m unittest discover -s tests -p 'test_workspace*.py' -v
python -m unittest discover -s tests -p 'test_asset_metadata*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The `Workspace initialization and storage` workflow repeats the targeted
storage tests on Linux and Windows. Hosted evidence is not inferred from the
presence of its YAML. Reverting the application change requires no migration;
WAL remains the same persistent mode that Workspace already requested.
The in-flight reload journal/database-identity work remains owned by #216;
this change neither introduces nor resets that identity.

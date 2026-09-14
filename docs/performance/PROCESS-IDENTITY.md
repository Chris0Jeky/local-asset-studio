# Resource counter attribution during PID reuse

14 September 2026. Fixes the observation defect tracked in #319; supports #302.

## Failure and correction

The old observer checked PID creation time before reading memory/CPU counters.
If that process exited and the PID was reused during the read, counters could be
returned under the old identity. The official [psutil API](https://psutil.io/api/)
documents that Process queries address a PID and create_time() is cached after
its first call. Calling it again on the same handle is not a fresh check.

The observer now validates the creation-time type and value before sampling and
obtains a fresh Process handle after both counter reads. It publishes counters
only when both observations match the initial identity. Confirmed replacement
permanently retires that observer. Failed or invalid final identity yields all
null counters and resets the CPU delta baseline; a later valid observation can
resume without bridging the unverified interval. No arbitrary error text escapes.

This is not atomic with the OS. Same creation timestamps, platform clock changes
and a replacement after the final check remain outside the guarantee. The row is
historical observed data, not proof the process is still alive or permission to
control it. The change never enumerates or terminates a process.

## Regression proof

Seven deterministic tests use handles whose creation time stays cached while
counter reads observe a mutable process table. Original code produces eleven
assertion/subtest failures; the stable identity control passes. The correction
passes all seven plus the eleven existing profiler tests. Actual producer/reducer
integration confirms discarded counters remain unknown, not zero or false peaks.
Tests never churn real OS PIDs or depend on scheduler timing.

```powershell
python -m unittest discover -s tests -p "test_resource_probe*.py" -v
python -m unittest discover -s tests -p "test_performance_history.py"
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Existing Windows runtime-safety CI now watches/runs the complete profiler test
family. Full exact-head evidence is recorded on the PR. No job, model, driver,
ComfyUI configuration, GPU generation or HUMAN_TODO decision is changed. Rollback
reverts this observation guard; there is no persisted schema migration.

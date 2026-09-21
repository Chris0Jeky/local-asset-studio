# Full-suite runtime observability

Local Asset Studio's lifetime lane keeps causal evidence when a test process behaves differently in the complete suite than it does in isolation. The harness does not relax request counts, retry a failing test, or increase an assertion merely because leaked work made the suite noisy.

## Ownership surfaces

| Surface | Evidence retained | Trigger |
| --- | --- | --- |
| Test execution | `START` / `END` test IDs plus the current-test watchdog and Python thread dump | A test exceeds the worker's pre-timeout deadline |
| Loopback transport | Exact numeric fixture endpoint, caller thread and bounded basename-only stack | The instrumented fixture receives a connection |
| Python thread shutdown | Current test state and every Python thread stack | A non-daemon thread retains the worker after the suite completes |
| Multiprocessing shutdown | Direct-child name, PID, daemon state and exit code, followed by the shutdown watchdog | `multiprocessing.active_children()` still contains a live child |
| `atexit` finalization | Callback identity, registration thread and bounded registration stack before invocation; return/exception outcome after invocation | A callback registered after worker observation starts is invoked |

The parent process owns one hard lifetime budget. Startup/test completion is recognized by the explicit `LIFETIME SUITE COMPLETE` marker; shutdown observation starts from that signal rather than from a fixed sleep or an assumed startup duration.

## `atexit` marker contract

The worker installs `AtexitCallbackObserver` immediately before unittest discovery. Module-level callbacks registered while importing tests are therefore observed without making imports of `full_suite_lifetime_worker.py` mutate the calling test process.

Markers are one-line JSON records:

```text
LIFETIME ATEXIT ENTER: {"callback":"test_module.block_at_shutdown","id":1,...}
LIFETIME ATEXIT EXIT: {"callback":"test_module.clean_up","id":2,"outcome":"returned"}
```

An `ENTER` record without the matching `EXIT` record identifies the callback in progress when the parent lifetime budget expires. Raised callbacks record only the exception type, not its message.

The observer preserves the public behavior relied on by tests:

- `atexit.register(...)` returns the original callback, including decorator use;
- `atexit.unregister(callback)` removes every observed equal callback and still delegates for callbacks registered before observation;
- callback positional and keyword arguments are delegated but never retained or printed;
- callback diagnostics cannot prevent the callback from running if the diagnostic stream itself fails.

## Bounds and privacy

Retained stacks contain only file basenames, line numbers and function names. Absolute machine paths, callback arguments, request bodies, headers, response bytes, socket objects and exception messages are excluded. Frame counts, text fields, observed loopback calls and fully attributed callback registrations are capped. Hitting the callback-registration cap emits an explicit `SATURATED` marker instead of silently pretending coverage remains complete.

`ProcessCapture.reap()` also preserves the primary failure. If an output-reader thread fails to terminate while cleanup is already unwinding another exception, the reader failure is attached as an exception note; it is raised directly only when no primary exception exists.

## Verification

Focused contracts:

```bash
python -m unittest discover -s tests -p 'test_full_suite*.py' -v
python -m unittest discover -s tests -p 'test_loopback_transport_audit.py' -v
```

Repository gates:

```bash
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The hosted lifetime workflow runs the focused contracts on Ubuntu and Windows and retains the existing measured Windows full-suite budget.

## Deliberate boundary

This observer covers Python callbacks registered through `atexit.register` after observation begins. Native-extension finalizers, callbacks registered before the worker installs observation, detached grandchildren and external processes are not claimed as covered. Those remain distinct follow-up classes under #609 rather than being hidden behind a broader timeout.

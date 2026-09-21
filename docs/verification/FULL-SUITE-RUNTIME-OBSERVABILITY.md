# Full-suite runtime observability

Local Asset Studio's lifetime lane keeps causal evidence when a test process behaves differently in the complete suite than it does in isolation. The harness does not relax request counts, retry a failing test, or increase an assertion merely because leaked work made the suite noisy.

## Ownership surfaces

| Surface | Evidence retained | Trigger |
| --- | --- | --- |
| Test execution | `START` / `END` test IDs plus the current-test watchdog and Python thread dump | A test exceeds the worker's pre-timeout deadline |
| Thread starts | Root owner test, test active at `Thread.start()`, parent thread and bounded basename-only start stack | A later observed action runs on a thread started after worker observation began |
| Executor submissions | Root owner test, test active at `ThreadPoolExecutor.submit()`, submitter thread, callable identity and bounded submit stack | A task runs on a pooled worker, including a worker reused across tests |
| Loopback transport | Exact numeric fixture endpoint, active test, caller thread, thread-start owner, pooled-work owner and bounded current/start/submit stacks | The instrumented fixture receives a connection |
| Python thread shutdown | Current test state and every Python thread stack | A non-daemon thread retains the worker after the suite completes |
| Multiprocessing shutdown | Direct-child name, PID, daemon state and exit code, followed by the shutdown watchdog | `multiprocessing.active_children()` still contains a live child |
| `atexit` finalization | Callback identity, registration thread and bounded registration stack before invocation; return/exception outcome after invocation | A callback registered after worker observation starts is invoked |

The parent process owns one hard lifetime budget. Startup/test completion is recognized by the explicit `LIFETIME SUITE COMPLETE` marker; shutdown observation starts from that signal rather than from a fixed sleep or an assumed startup duration.

## Cross-test thread ownership

The worker installs `ThreadOwnershipObserver` immediately before unittest discovery and publishes each active test ID through the same shared module used by the transport audit. A standard `threading.Thread.start()` therefore records:

```json
{
  "status": "observed",
  "owner_test": "test_a.StartsWorker.test_start",
  "started_during_test": "test_a.StartsWorker.test_start",
  "parent_thread": "MainThread",
  "start_stack": [
    {"file": "test_a.py", "line": 42, "function": "test_start"}
  ]
}
```

When that thread connects to a fixture while a later test is active, the retained transport row keeps both identities:

```json
{
  "active_test": "test_b.UsesFixture.test_contract",
  "thread": "retained-worker",
  "thread_origin": {
    "owner_test": "test_a.StartsWorker.test_start",
    "started_during_test": "test_a.StartsWorker.test_start"
  }
}
```

Nested observed threads inherit the root owner test while retaining their own `started_during_test`, parent thread and start stack. This distinguishes the test observing leaked work from the test that launched it. The observer treats the thread that installed it as the trusted unittest runner root; other threads already alive at installation remain unobserved. Children of an unobserved parent retain an `ancestor-*` reason instead of being reassigned to the current test, including parents skipped because the evidence capacity was full. Nested observers compose in LIFO order so focused contracts can run inside the full-suite worker without replacing its outer ownership state.

## Reused executor work ownership

A thread pool deliberately reuses workers, so the test that created a worker is not necessarily the test that submitted the task currently running on it. The worker also installs `ExecutorWorkObserver` before discovery. Each standard `ThreadPoolExecutor.submit()` wraps only the callable invocation with a bounded context record:

```json
{
  "status": "observed",
  "owner_test": "test_b.UsesPool.test_submit",
  "submitted_during_test": "test_b.UsesPool.test_submit",
  "submitter_thread": "MainThread",
  "ownership_source": "runner-thread",
  "callable": "test_b.request_object_info",
  "submit_stack": [
    {"file": "test_b.py", "line": 73, "function": "test_submit"}
  ]
}
```

The loopback row retains this as `work_origin` separately from `thread_origin`. A reused worker can therefore report that its thread began in test A while its current task was submitted by test B. Submissions made by an observed retained thread inherit that thread's root owner rather than being reassigned to whichever test happens to be active. Nested executor tasks inherit their parent work owner. Cancelled queued futures release their observation capacity without running the task.

Task arguments, keyword arguments and return values are never copied into the diagnostic record. The observer stores only a safe callable identity and bounded submit metadata. Capacity-exhausted submissions remain explicit as `observer-capacity`; they are not assigned a speculative owner.

## `atexit` marker contract

The worker installs `AtexitCallbackObserver` immediately before unittest discovery. Module-level callbacks registered while importing tests are therefore observed without making imports of `full_suite_lifetime_worker.py` mutate the calling test process.

Markers are one-line JSON records:

```text
LIFETIME ATEXIT ENTER: {"callback":"test_module.block_at_shutdown","id":1,...}
LIFETIME ATEXIT EXIT: {"callback":"test_module.clean_up","id":2,"outcome":"returned"}
```

An `ENTER` record without the matching `EXIT` record identifies the callback in progress when the parent lifetime budget expires. Raised callbacks record only the exception type, not its message. Callback identity is snapshotted when it is registered, so finalization never has to inspect callback metadata before writing the `ENTER` marker. Identity projection also avoids `repr()` and callback-controlled instance attributes: functions and methods use their built-in metadata records, while callable objects use their type identity.

The observer preserves the public behavior relied on by tests:

- `atexit.register(...)` returns the original callback, including decorator use;
- `atexit.unregister(callback)` delegates one ordered comparison pass to CPython, so pre-observer callbacks keep their native position and matches removed before a later equality error remain removed;
- callback positional and keyword arguments are delegated but never retained or printed;
- callback diagnostics cannot prevent the callback from running if the diagnostic stream itself fails.

## Bounds and privacy

Retained stacks contain only file basenames, line numbers and function names. Absolute machine paths, callback arguments, executor task arguments, request bodies, headers, response bytes, socket objects and exception messages are excluded. Frame counts, text fields, observed loopback calls, live thread origins, in-flight attributed executor tasks and fully attributed callback registrations are capped. Capacity loss remains explicit in the retained evidence rather than silently pretending coverage remains complete.

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

Thread ownership covers standard Python threads whose `threading.Thread.start()` runs after observation begins. Threads created by native extensions, threads already alive before observation, and custom thread implementations that bypass `Thread.start()` are reported as unobserved rather than attributed speculatively.

Pooled-work ownership covers standard `ThreadPoolExecutor` instances whose inherited `submit()` method runs after observation begins. Executor subclasses that replace `submit()`, native pools, raw queues and other schedulers remain separate evidence classes. They are not attributed by guessing from the worker thread.

The finalization observer covers Python callbacks registered through `atexit.register` after observation begins. Native-extension finalizers, callbacks registered before the worker installs observation, detached grandchildren and external processes are not claimed as covered. Those remain separate evidence classes rather than being hidden behind a broader timeout.

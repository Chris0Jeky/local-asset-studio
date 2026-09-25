# GPU lease failure semantics

Refs #979. These are software contracts, not workstation or generation acceptance.

## State transitions

The persisted `.runtime/studio-gpu-lease.json` record is written before a grant,
renewal, release, or expiry becomes visible in memory. A failed write leaves the
previous committed in-memory state intact. Expiry whose write fails refuses the
observation rather than claiming the GPU is available.

A live holder renews only its deadline. Renewal does not stop processes or repeat
idle checks. An expired holder must pass the full acquisition checks again.
Retained deadlines beyond four hours from startup are clamped, and that absolute
cap is persisted so another restart does not extend it.

## Before stopping a listener

Acquisition holds the Studio interlock and checks the configured endpoints and
local work. It then strictly checks the queue and process identity of every
listener selected for stopping before terminating any of them. A refusal in this
preflight preserves every process, reports an empty `stopped_processes` list, and
does not grant or persist a lease.

Each process is checked again immediately before its individual stop. Preflight
is not an atomic reservation of external ComfyUI queues: an external client can
still submit work afterward. Such a late refusal reports the processes already
stopped and preserves the remaining processes. It does not grant a lease, repeat
termination, or automatically relaunch a non-selected profile. A failed first
grant write can likewise follow a completed physical stop; persistence failure
cannot undo that action.

## Recovery and remaining scope

An active lease takes precedence over healthy endpoint observations in runtime
recovery, including a lease acquired during the health probe. Owner listening,
image acceptance, model permissions, and generation status remain separate.

The launcher enforcement and workflow-run request race listed in #979 remain
separate follow-ups. This contract does not claim every external or manual launch
path observes the lease. Do not load a competing GPU tenant after a refused or
unknown acquisition; inspect the response and authoritative lease endpoint.

## Offline evidence

`tests/test_gpu_lease_state.py` covers durable-before-visible transitions,
renewal, deadline bounds, and recovery precedence. `tests/test_gpu_lease_preflight.py`
uses two inert fake processes to reproduce a later listener's idle or identity
failure before any stop, verify successful ordering, and preserve truthful late
partial-stop reporting. No real process is launched or terminated by these tests.

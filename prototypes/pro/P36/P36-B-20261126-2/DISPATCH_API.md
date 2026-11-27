# Durable dispatch laboratory

This is an implemented, offline coordinator over the actual Studio preparation
and Workspace contracts. Its port records a simulated callback in a local SQLite
database. It contains no HTTP client, starts no worker, grants no generation
budget, and performs no native import. Installing the equivalent gate in the
existing Studio worker remains planned.

The kill criterion applies before reservation, before the durable claim, and
again after publishing the pending marker: identity drift, withdrawn acceptance,
changed subject bytes, unresolved other attempts or missing evidence refuse the
operation. A late refusal retains the claim and never makes it reusable.

## APIs and explicit context

```python
initialize(ledger_path)

prepare_dispatch(ledger_path, request_id=request_id,
    experiments=experiments, family=family, binding=binding,
    asset_root=asset_root, semantic_policy=policy, annotations=annotations,
    intent=intent, studio_root=studio_root)

dispatch_once(ledger_path, attempt_id,
    experiments=experiments, family=family, binding=binding,
    asset_root=asset_root, semantic_policy=policy, annotations=annotations,
    intent=intent, studio_root=studio_root, port=simulation_port)

inspect_dispatch(ledger_path, attempt_id)

reconcile_dispatch(ledger_path, attempt_id,
    experiments=experiments, intent=intent)
```

Source: [dispatch_coordinator.py](dispatch_coordinator.py). The intent must come
from the read-only [Production factory](PRODUCTION_INTENT_API.md), with trusted
Studio and experiments roots supplied independently. Every mutation remains
under repository `.runtime/`; linked destinations are refused. `initialize`
adds its versioned journal tables to the explicit attempt ledger. It never
migrates the Workspace or Production database.

The supported operation is one regular `comfy.generate.v1` member with a frozen
effective graph and seed. Native operations, private sources, wildcard expansion
and batches larger than one are outside this adapter. Capture happens before
the deterministic future job exists. No old job is adopted as a fresh operation.

Caller-owned JSON is copied through bounded canonical serialization at entry.
Condition and submission callbacks receive separate copies. A caller changing a
graph during admission cannot replace the prepared callback body.

## Durable states

| State | Meaning | A repeated call may do |
| --- | --- | --- |
| `prepared` | Current source was checked and an exact attempt was reserved; callback has not been claimed | Recheck all current prerequisites and attempt to claim once |
| `claimed` | The exclusive claim committed before job publication or callback | Observe only, including after a process stopped before the callback |
| `acknowledged` | Exactly one simulated callback returned an exact prompt ID and its retained receipt was published | Observe the same job/prompt; never submit again |
| `uncertain` | Publication, callback response or receipt persistence failed after claiming | Inspect retained evidence; never submit again |
| `settled` | Explicit terminal observation matched the operation and was committed with the ledger resolution | Observe the same exact evidence; changed evidence refuses |

The coordinator favors preventing duplicate side effects over automatically
recovering availability. A crash after the claim but before the callback can
leave **zero callbacks and a permanently consumed claim**. There is no timeout,
lease stealing, clear-and-retry button or automatic rearming. If no prompt or
terminal evidence exists, reconciliation refuses. Do not delete or rewrite the
journal to get another attempt.

Preparing a request uses two publication steps: the existing ledger reservation,
then the dispatch ticket. A process loss between them leaves an orphaned
reservation. The coordinator explicitly refuses to adopt it. This is another
availability cost of retaining uncertainty; the interrupted operation is not
silently reconstructed from missing output.

Each ticket binds the full attempt identity: family, stage, request, job,
Workspace, source-root identity, immutable intent hash and random nonce. It also
binds family/policy/annotations/asset-root/ledger inputs, current authority and
the independently supplied Studio root. Journal states have exact revisions;
malformed retained fingerprints and outcomes refuse inspection/reconciliation.
These hashes detect inconsistent records; they do not authenticate someone who
can coherently rewrite the local database.

## The owned reservation exception

Ordinary `admission.check_transition` and export continue to reject every
unresolved attempt, including this coordinator's own prepared reservation.

Only the claim operation recognizes its **one exact owned reservation**, while
holding the serialized ledger write transaction. It requires all of the
following:

1. The only overall admission blocker is the expected target-stage uncertainty.
2. The nested ledger identifies exactly this attempt, with the same full
   identity, nonce, source scope and unresolved state.
3. All bound input fingerprints and the entire authority capture still match.
4. Media, identity, ancestor and current-authority checks pass independently.

An unrelated unresolved ancestor, extra blocker, changed selection or failed
identity check is never removed. There is no general ignore-list parameter,
temporary ledger clone, cached pass or early resolution. Claim ownership is
compared and changed inside `BEGIN IMMEDIATE`; SQLite commits the claim with
`synchronous=FULL` before the callback.

The simulated backend, budget and lease conditions are checked before claiming
and after pending publication. They are explicitly injected test conditions,
not observations of the owner's GPU, queue, budget or lease. Production intent
is freshly revalidated before the pre-create hook; after the marker, the
coordinator rechecks current identity/acceptance/bytes and ledger ownership.
Production recapture intentionally refuses an already-created future job.

These are serial reads. They do not lock the Workspace, freeze a model until an
engine opens it, or make a transaction across the GPU, files and SQLite. A real
worker integration must use its existing job ownership, budget and GPU lease,
bind the final actual request body, reobserve runtime readiness, and retain the
existing submit-once pending/receipt protocol. Studio already has that protocol;
this laboratory makes no claim that the base Studio repeats uncertain requests.

## Publication and reconciliation

After claiming, the coordinator uses Studio's existing `observation_state`
publication barrier for `workflow.json` and `state.json`. The job retains the
exact `p36_attempt`, `p36_simulation=true` and normal `pending_submission` shape.
The real `submission_evidence.never_submitted` predicate correctly refuses to
classify that pending record as never submitted.

The callback's exact prompt ID is recorded in the normal receipt and journal.
A lost response or failed receipt write leaves a permanent claim. Exceptions
never cause a second callback. A separate process can inspect the claim; it
cannot infer that the callback did not happen from a missing response.

Reconciliation validates the exact graph, integral seed, member index, prompt
identity and attempt marker. An acknowledged prompt cannot be replaced with a
different terminal prompt. The validated job and workflow byte hashes produce
an expected observation hash. The existing ledger rereads them and requires
that hash inside the same SQLite write transaction that settles the dispatch
journal. A change between the operation-specific check and that reread rolls
back both updates. The public ledger `resolve` API remains compatible and also
accepts the optional `expected_observation_sha256` pin.

Terminal status in this lab is an authored synthetic observation, not generated
media. It does not set an asset's inspection, acceptance or licence state.

## Reproduce and inspect

The aggregate command in [README.md](README.md) runs the unit regressions and
[dispatch_evidence.py](dispatch_evidence.py). Its 23 deterministic cases include:

- Ten refusal paths that reach no callback: current acceptance/semantic/source
  changes, injected backend/budget/lease vetoes, a foreign unresolved ancestor,
  and a withdrawal after the pending marker.
- Lost response, malformed response and publication failure, with every retained
  claim remaining observation-only.
- An exact valid terminal observation, caller-mutation isolation, a wrong
  acknowledged prompt and changed bytes during reconciliation.
- Four separate-process stops at claim, marker, callback and receipt boundaries,
  followed by recovery in another process.
- Three independent Python processes racing for the same claim; exactly one
  calls the deliberately non-deduplicating port.

Across that authored matrix the expected total is **10 simulated callbacks**,
with **0 extra callbacks**, **4/4 crash recoveries observation-only**, and
**1 callback across 3 competing processes**. Counts concern this selected
software matrix, not statistical reliability or live generation performance.

Raw contexts, databases and per-case reports remain below the proof output's
`dispatch-cases/`. The normalized `dispatch-evidence.json` contains no random
identities, source paths or timings and is included in the eleven-output hash
manifest. Simulated callback counts are measured by SQLite insertion on every
call; the port has no deduplication constraint that could hide a duplicate.

The process driver is [dispatch_simulation.py](dispatch_simulation.py). Its
`worker` subcommand consumes an existing explicit fixture context and ticket;
it does not initialize or discover production work. The private crash switch
terminates that disposable process with exit 73. Use the aggregate proof to
create those contexts instead of pointing it at real retained jobs.

## Scope still to adopt

Windows/MSVC-hosted Python, NTFS publication, real power loss, ROCm/HIP, ComfyUI
and native tools were not exercised here. No C++ compiler or flags are involved.
SQLite's full-sync configuration and process termination tests do not prove a
physical power-loss guarantee. Concurrent malicious writers or omitted legacy
attempts are outside the local journal's authority model.

The next Studio task is to adapt these gates to the existing production worker
under its actual ownership and budget controls, first using a counting fake
transport. Preserve zero real generation budget for that software test. Follow
the measurable targets and named owners in [ADOPTION.md](ADOPTION.md).

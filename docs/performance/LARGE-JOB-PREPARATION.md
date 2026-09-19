# Measured large-job preparation

Issue #306 adds one same-origin command around the existing generation coordinator,
backend ownership checks and stage-aware admission policy. It does **not** create a
second queue, submit a prompt, delete a job, change a graph or infer that an HTTP
success released memory.

## Default and authority boundary

All new lifecycle settings default to `false`:

```json
{
  "enable_large_job_resource_cleanup": false,
  "enable_idle_retained_commit_cleanup": false,
  "enable_large_job_backend_restart": false
}
```

A request must also opt into each action. Configuration enables a local capability;
it is not standing authorization for arbitrary requests. `idle_policy` is a separate
mode and can release only after its own configuration gate. It cannot restart a
backend. Restart remains an explicit request plus a second configuration gate, so a
new job or a same-model transition never causes a restart merely because it exists.

The older `idle_cache_release_minutes` timer remains cache hygiene, not evidence of
large-job readiness. It has no restart authority and does not close this command's
receipt. Set it to `0` where the operator wants every release decision to flow through
the measured `idle_policy` command.

## Command

`POST /api/large-job-preparation` accepts at most 128 KiB of same-origin JSON:

```json
{
  "request_id": "prepare-klein-board-01",
  "recipe": {
    "preset_id": "klein-character-board",
    "controls": {},
    "batch_count": 1
  },
  "dry_run": true,
  "allow_release": true,
  "allow_restart": false,
  "mode": "explicit"
}
```

The recipe is passed to `Studio.prepare`, not `Studio.create_job`. The command never
spends an allowance and always reports `generation_submitted: false`.

A repeated `request_id` with identical canonical content returns the saved receipt.
Changed content conflicts. A journal record interrupted after an action intent is
converted to `unknown`; the action is not replayed. Receipts are bounded to 32 in
`.runtime/large-job-preparation.json`, which is already ignored by Git.

## Decision sequence

1. Refuse active, partial or uncertain Studio jobs, reference jobs or production
   stages.
2. Prove the selected listener is exactly one configured process using PID plus
   creation time, then prove the real Comfy queue is empty.
3. Prepare the exact graph and bind its runtime identity to an exact #178 stage
   profile. Missing profiles or counters remain `unknown`.
4. Account for active Studio reservations and evaluate the same RAM, Windows commit
   and VRAM dimensions as resource admission.
5. If already safe, return Ready without an action. A dry run stops here after
   reporting planned actions and local gates.
6. Immediately recheck work, queue, profile and process identity before `/free`.
   Persist the intent first. A lost response becomes `unknown` and prohibits restart
   or automatic retry.
7. Recheck the queue and identity, observe counters again, and require measured
   relief plus a fresh safe evaluation. HTTP 200 alone is not Ready.
8. Only an explicit, separately enabled restart can follow insufficient measured
   release. Recheck again, terminate only the exact owner, verify absence, persist a
   launch intent, reconcile a lost launch return without relaunching, and require the
   new PID/creation identity to own the ready idle listener.
9. Observe and evaluate once more. No safe counters means no Ready result.

Every observation can go stale; a new external Comfy job, profile change, reused PID,
foreign listener or inaccessible process invalidates the plan. No executable-name
kill or naked PID authorization exists.

## Local proving protocol

Deterministic tests use fake counters, processes, queues and response loss. They prove
policy and failure handling, not workstation performance. Before closing #306, the
owner should run one bounded Windows proof with an approved idle backend and preserve
ignored raw receipts for:

- observation-only/dry-run refusal cases;
- `/free` before/after counters;
- a deliberately insufficient release, if safely reproducible;
- an owner-approved restart, if still necessary;
- confirmation that no unrelated process or external prompt was affected.

Publish only a redacted summary with exact environment/profile identities and measured
counters. Do not promote a single run into a universal idle threshold.

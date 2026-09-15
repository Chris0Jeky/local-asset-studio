# Durable reference analysis on the Studio worker

The operation API runs the existing reference assistant through Studio's single
worker. It is opt-in, local-only and distinct from image generation. The browser
Analyze integration is the next slice; the operator CLI still works independently.

## Configure once, after qualifying an installed vision helper

Add `reference_helper` to the existing ignored `config/local.json`, retaining all
other configuration. This is an illustrative policy, **not a measured fit claim**:

```json
"reference_helper": {
  "model": "YOUR_ALREADY_INSTALLED_LOCAL_VISION_MODEL",
  "model_digest": "REPLACE_WITH_64_LOWERCASE_HEX_FROM_API_TAGS",
  "port": 11434,
  "min_available_ram_bytes": 4294967296,
  "min_commit_headroom_bytes": 8589934592,
  "min_free_vram_bytes": 4294967296,
  "timeout_seconds": 90
}
```

Obtain the exact name/digest from the configured local runner's `GET /api/tags`.
Use a dedicated local helper: concurrent external Ollama calls are not Studio-owned
work and cannot be controlled by its queue. This feature does not install/pull a
model, start a helper server, change the driver/ROCm environment, free Comfy caches
or claim that an arbitrary model fits those example minima. Choose thresholds from
an independently bounded workstation measurement. The browser cannot override them.
Absent or invalid configuration disables analysis, without affecting manual review.

The first admission implementation targets the existing Windows/single-GPU setup.
It observes physical RAM with psutil, Windows commit via the existing
`host_memory.read`, and device VRAM from Comfy's `/system_stats`. An unavailable
counter or ambiguous multi-device reading refuses inference. In particular, an
unsupported host is not authorized by treating unknown Windows commit as zero.

## API and state

All paths are below `/api/prompt/reference-jobs/`, on the existing loopback Studio
server with its Host/same-origin protections. No new port or HTTP inference thread.

| Operation | Contract |
| --- | --- |
| `GET capabilities` | Configuration, Workspace identity, busy status and eight recent recovery handles; no helper/Comfy calls. |
| `POST create` | `workspace_id`, `request_id`, reference `request`, and ordered `images` as `{reference_id, media_base64}`. Returns the durable operation; queues analysis once. |
| `GET status?workspace_id=…&request_id=…` | Read a known operation, retained result and state identity. Unknown remains unknown; no replay. |
| `POST cancel` | Workspace/request identity plus `expected_state_sha256`. Cancels only a queued, never-dispatched request. |
| `POST release` | Same identity plus explicit boolean `acknowledge_unknown`. Releases a settled resource hold, not a model call or generation. |

`create` accepts the same one-to-four-reference request as the CLI, including empty
or short text and `auto` role hints. Images are bounded to 8 MiB/16 MiPixels/one
frame, original hashes are verified, and the existing orientation/white-matte/RGB
preparation creates metadata-free derivatives up to 768 pixels per side. Those
exact derivatives, source identities and model request are journalled in the
existing AssetWorkspace database. Original image bytes are not saved, staged to
Comfy, or registered as new library assets. The reviewer must retain/reselect them.

One create body may be at most 48 MiB, with intake locked before that HTTP body is
read; prepared payload at most 16 MiB; response at most 1 MiB. One analysis may be
outstanding. There are 64 retained operations and a 128 MiB request/result budget,
including a reserved result allowance before inference. No automatic history
removal/eviction. Keys bind the exact canonical request: an identical key returns
its original operation without requeueing; changed content under that key refuses.

Dispatch runs the existing Studio worker. It refuses stale backend/configuration,
unknown or nonempty Comfy queue, unresolved generation work, insufficient fresh
resource readings, a changed/remote model, or pre-existing helper residency. After
inventory checks, queue and physical/commit/VRAM readings are checked again at the
dispatch boundary. A queued request is not a reservation against external programs.

## Lost replies and resource holds

Before the one `POST /api/chat`, SQLite records `submitting`, `inference_attempts:1`
and `resource_hold:true`. The request contains all images, a structured response
schema, no tools, and `keep_alive:0`. After a complete reply, the result is validated
and retained. The hold clears automatically only when the runner reports an empty
loaded-model list. If residency cannot be confirmed empty, a valid analysis can be
ready for review **while its resource hold remains**.

An incomplete/lost reply is `uncertain`; no automatic retry, alternate-model call
or second reservation occurs. Generation admission/dispatch and backend lifecycle
respect that hold. Existing queued work that reaches a hold is refused without
submission and retains its ordinary job/project evidence. Read-only observation
of known generation jobs remains possible.

Restart cancels queued/preparing requests that never dispatched and preserves any
uncertain/resource-held call. It never restores delivery to the worker. `cancel`
is not available after preparation starts: the transport has no proven server-side
cancellation acknowledgement. Closing a page cannot claim to cancel a model.

Release requires the current state hash and a fresh empty helper residency check.
For an uncertain outcome, the operator must explicitly confirm that the specific
call has stopped; an empty `/api/ps` alone does not prove that an unanswered request
was never accepted or is not waiting. Release records that acknowledgement while
leaving the old outcome/attempt count unchanged. It never restarts a runtime, kills
a process, obtains another inference allowance or replays the original request.
A failed journal write retains an in-memory hold as well as any durable pending
marker; a restart/inspection is required, not a blind repeat.

## Limits and qualification

This is analysis, not automatically accepted wording, art, geometry or native
reference binding. The existing review report still separates per-picture roles,
selected traits, edits, uncertainties and source metadata. Persisted analysis
operations are not yet shared editable CreativeIntent documents (#38).

A socket timeout is not an end-to-end inference deadline or remote cancellation.
The old operator CLI's workspace-local lock is not this Studio coordinator; do not
run it concurrently against the same helper. External Comfy/helper clients can
race an idle observation, so the guarantee is serialization of Studio-owned work,
not universal process exclusion. Check actual helper unloading, latency, memory,
role understanding and accepted-output effort on the workstation before promotion.
No real model inference or artwork qualification is established by synthetic tests.

## Sources and checks

Primary API contracts checked 15 September 2026:
[Ollama chat](https://docs.ollama.com/api/chat),
[model inventory](https://docs.ollama.com/api/tags),
[loaded models](https://docs.ollama.com/api/ps),
[structured vision outputs](https://docs.ollama.com/capabilities/structured-outputs).
The loaded-model API describes residency; it is not a request queue or an execution
receipt. Unload-after-response is requested, then separately observed.

Run `python -m unittest discover -s tests -p 'test_reference_*.py'`, existing Prompt
Studio/server/backend/recovery tests, `python tests/check_full_suite_lifetime.py`
and `python scripts/validate-repo.py`. Tests use real SQLite, the actual worker
branch and HTTP handlers, synthetic images, and simulated sensors/model responses.
Refs #35, #38, #178, #313. HUMAN_TODO and all image-generation allowances remain.

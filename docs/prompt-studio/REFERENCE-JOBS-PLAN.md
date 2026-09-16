# Reference analysis through the Studio worker

## Design and scope

Continue #35/#38/#178 on main `85dc151`. The #333/#336/#346/#349 stack and
board-aware #335 are merged. The new Klein Combine path needs concrete subject
and pose descriptions; this work connects reference understanding, not another
image model. No installed environment, model or generation allowance is changed.

Use a typed operation journal inside the existing AssetWorkspace SQLite database.
The existing Studio queue/worker dispatches one explicit local Ollama analysis.
Persist its exact model request (clean analysis derivatives, never original media
or imported metadata), source/report identities and state before transport. The
existing reference report and review panel consume the result. No new worker,
port, asset registry, graph executor or editable-document store.

Rejected alternatives: an HTTP handler that runs inference synchronously would
compete with generation; a caller `idle_confirmed` flag is not admission. A new
helper queue would split resource ownership. An unguarded timeout/retry can run a
second inference while the first is still alive.

## Slice 1: durable analysis, adapter and worker

Files: `studio_prompt/reference_jobs.py`, `reference_job_http.py`, existing
`local_helper.py`, `reference_vision.py`, `http_extension.py`, `app/server.py`,
`app/backends.py`. Tests: `test_reference_jobs.py`, `test_reference_job_http.py`.

1. Write tests for exact-request replay, changed-key refusal, persisted-before-POST,
   reference order/hash limits, one worker, opt-in configuration, stale runtime,
   unavailable/low headroom, queued cancellation, lost response, restart and release.
2. Reuse image preparation with an in-memory source alternative. Share the existing
   loopback transport; permit read-only `/api/ps` for residency observation.
3. Store bounded operations in the Workspace database, with mandatory workspace
   identity and immutable source/payload/config bindings. One outstanding operation,
   64 retained operations, 128 MiB retained request/result budget; no eviction/replay.
4. Dispatch via `Studio._work`. Admission checks actual Comfy queue, unresolved
   generation work, fresh RAM/Windows commit/Comfy VRAM against operator-configured
   minima, exact installed local model digest and no loaded helper models. Minima
   are policy thresholds, not measured fit guarantees.
5. A durable hold starts before POST. Clear it only after a completed response and
   empty helper residency observation. Lost responses retain an uncertain operation
   and hold through restart. Explicit release requires current state identity,
   observed empty residency and operator acknowledgement for an uncertain outcome.
   It never retries a model call, kills a process or asserts server cancellation.
6. Gate generation preparation/dispatch and backend lifecycle on holds. Queue-only
   operations block backend switching; duplicate dispatch observes the retained
   state, not another model call. No automatic dequeue restoration on startup.
7. Run focused real-SQLite/loopback/worker fault tests and full existing tests.

## Slice 2: browser Analyze and retained operation identity

Files: new `app/static/reference-analyze.js`, existing reference review and Prompt
Lab page; existing Prompt Studio workflow plus new browser/Node contracts.

1. Add an explicit Analyze action for 1–4 original pictures and the current brief,
   with auto roles and optional/empty wording. Server configuration chooses model
   and resource thresholds; the browser cannot supply runtime authority.
2. Persist a bounded request identity/workspace/input fingerprint before dispatch.
   A lost HTTP response or reload offers Check status only, never a blind POST retry.
3. Poll one operation only while visible, single-flight; no inference on load,
   input selection or status reads. Completed observations enter the existing
   review panel only by explicit user action and matching originals.
4. Keep the original manual/import flow; visibly explain missing configuration,
   queued/running/uncertain/held states. Cancel only proven queued work. Advanced
   release acknowledges the specific operation; it cannot submit another one.
5. Exercise actual browser and HTTP at desktop/390px, keyboard, stale inputs,
   reload/status recovery and zero generation. Record model responses as synthetic.

## Evidence and limits

Official Ollama APIs: `/api/chat` supports image arrays and structured output;
`keep_alive: 0` requests unloading after response; `/api/ps` describes loaded
models, not an authoritative queue or cancellation acknowledgement. A socket
timeout is not a server execution deadline. Even empty residency cannot alone
settle an unanswered POST. The configured helper must be dedicated to Studio;
external Comfy/helper clients are outside Studio's single-worker guarantee.

Owner-host VLM/AMD/artistic qualification, persistent shared CreativeIntent edits,
and automatic native generator binding remain separate. The operation journal
preserves analysis provenance; it does not approve art or resolve ambiguity.

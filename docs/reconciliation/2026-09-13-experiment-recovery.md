# Oldest-open reconciliation: Experiment Lab recovery

Date: 13 September 2026. Initial source checkpoint:
`f85c00e6a0a6ad6f357a4899efd839c37808e4e4` (main after #168).
The publication check also reconciles newer main commits; use the PR's final
head and check links for the integrated result, not this dated checkpoint alone.
This is source/CPU/transport evidence, **not a workstation or GPU run**.

## Why this slice, in chronological order

| Oldest open issue | Already implemented / reconciled | Decision in this pass |
| --- | --- | --- |
| [#2](https://github.com/Chris0Jeky/local-asset-studio/issues/2), 11 Sep 04:39:13 UTC | Explicit backend profiles, exact process/queue ownership, API/native HiDream graphs, retained eight-step trials; #137 added the pre-listen startup interlock. | Do not rebuild switching or close the broader issue. Higher-step same-seed/native/runtime acceptance still requires local evidence. |
| [#3](https://github.com/Chris0Jeky/local-asset-studio/issues/3), 11 Sep 04:39:14 UTC | Existing comparison, editing, animation, Workspace and export machinery; newer experiment receipts and owner decisions are in CURRENT_STATE/HUMAN_TODO. | Keep open. Qwen/Lightning, faithful motion, native Krita/engine and later FLUX acceptance require their own outputs, not a mock run. |
| [#9](https://github.com/Chris0Jeky/local-asset-studio/issues/9), 11 Sep 15:52:19 UTC | #142 unknown-role handling, #149 non-destructive intake publication, #156 graph validation, #168 exact-path dependency readiness. #170's completed-partial download fix was also checked before publication. | Keep the broad source/lineage/bundle/hardware task open. Do not duplicate current intake, downloader or bundle-guidance work. |
| [#10](https://github.com/Chris0Jeky/local-asset-studio/issues/10), 11 Sep 15:52:31 UTC | Single Production worker, pinned plans, root reservations, retained prompts, review desk, native exports; #153 fixed materialization before database publication. | Two concrete remaining software defects reproduced: #93 time accounting/reconciliation and #94 pre-POST restart/abandonment. Implement those in the existing coordinator. |

At the initial snapshot, #169 and #171 covered guided/bundle UI work and #170
covered Civitai partial completion. This patch avoids those feature paths.
Main subsequently included #170 at `6dbcaa7b8be5acc600a991aab520dd6b30639f0e`;
the download fix was not reimplemented.

The broader #10 issue remains open: software recovery does not supply its
accepted creative benchmarks, native outputs or generic multistage acceptance.
No new executor, database, model manager or service was added.

## Current flow and the changed boundaries

```text
Create / continuation / character brief
    -> catalog-bound recipe, references and backend/model bundle
    -> immutable comparison plan, materialized before SQLite publication
    -> explicit Start reserves the root generation allowance once
    -> existing single worker
       -> durable deterministic stage/job identity
       -> prove first submission OR reconcile retained prompt IDs
       -> persist pending_submission BEFORE POST /prompt
       -> retain response IDs and exact submitted graphs
       -> observe history, index outputs in Workspace
    -> comparison / review / native export (separate acceptance)
```

The generation allowance still belongs to the root and is **not refunded** by
stop, restart, time extension or abandonment. Expensive jobs whose outcome is
unknown are never automatically replayed. Backend switching still requires
verified, idle queues and owned processes; local abandonment is not a remote
cancellation or permission to kill a process.

### Submission evidence, not the status name (#94)

`app/submission_evidence.py` centralizes the predicates shared by recovery,
Production dispatch and public/UI eligibility. To prove `never_submitted`, a
job must have explicitly present, empty **lists** for `prompt_ids`,
`submissions` and `outputs`, no `pending_submission` key at all, no abandonment
or tracking disposition, and a compatible inactive/pre-POST lifecycle state.
Even an empty or null pending marker blocks that proof. Missing or malformed
receipt collections are not treated as empty receipts.

| Retained state | Restart / explicit action |
| --- | --- |
| Queued/waiting (or legacy uncertain) with complete empty receipts and no pending marker | `not_submitted`; nothing is queued at startup. Explicit Production resume uses the **same job ID and reservation** for its first submission. |
| Queued observation with known prompt/submission records | Remains uncertain on restart. Observation can recover the known prompt without another POST. A queued label never proves a new generation. |
| Pending marker with no returned prompt ID | Remains unknown and non-retryable. The operator can explicitly abandon the local record, acknowledging the unknown remote outcome. |
| Known-only uncertain prompt | Existing Stop tracking / Resume observation path remains available; later Production stages still require the existing explicit continuation authorization. |
| Already abandoned | Terminal locally, never resumed or dispatched. Recipe, exact graph, pending marker and reason remain on disk. |

Recovered first submissions re-prepare the pinned stage and check the saved
and current graph hashes, controls, batch size, preset, seed/prompt bindings
and backend identity. The final `_run` boundary independently requires proof
that this is the first submission. Changed evidence or a concurrent
abandonment cannot silently be overwritten into a generation.

The public job projection exposes `has_pending_submission`, `never_submitted`,
`can_abandon`, `abandon_requires_acknowledgement` and the retained abandonment
receipt. It does not transfer full pending graphs on every gallery poll.
The exact record is still at `experiments/runs/<job-id>/state.json`, beside
`recipe.json` and `workflow.json` (or under the configured experiments root).

**Operator path:** in the gallery, give a reason and choose **Abandon local
job**. For an unknown outcome, first explicitly acknowledge that remote work
may still exist and will not be cancelled. A never-submitted standalone job
can instead be preserved/exported as a recipe for a separately reviewed run;
restart itself never submits it. In an experiment, use **Reconcile and resume**
to continue a proven never-submitted stage.

The abandonment disposition is committed atomically before mutating memory.
Repeating the same command is idempotent; a different reason cannot overwrite
it. A failed disk write leaves the original job and evidence unchanged.

### Active time, not time since the first Start (#93)

`app/production_clock.py` stores a versioned ledger in the existing project
state, separate from both `started_at` (historical) and the immutable plan:

- `limit_seconds`: original allowance plus explicit amendments, at most 14,400.
- `measured_seconds`: accumulated in-process monotonic elapsed intervals.
- `unmeasured_seconds`: conservatively charged allowance for a lost active
  interval or a legacy run lacking accounting; **not a measurement**.
- `active`: a token and remaining reserved interval, persisted before work.
- `revision`, `amendments`, `recovery_reason`: audit and stale-command protection.

Only differences within the same active worker interval are measured; a
monotonic origin is never persisted and reused after a process restart.
Queue waiting and observation during an active comparison count. This is not
GPU kernel time. Time while Studio is stopped is not derived from wall-clock
subtraction and charged as measured runtime. `started_at` is not reset to
manufacture a fresh allowance on each Resume.

Each stage boundary and normal/exceptional worker exit checkpoints elapsed
time. A hard process loss can prevent the final checkpoint. On restart that
interval's remaining reservation is charged to **unmeasured** time, once;
legacy runs similarly start with a conservative unmeasured charge. This is a
chosen fail-closed tradeoff: it can overcharge, but it cannot give repeated
crashes or resumes a free new allowance. Finer-grained heartbeats can reduce
that uncertainty later without changing the ledger contract.

Known prompt reconciliation precedes the time/stop decision for new stages.
Existing storage, bundle and tracking-consent checks still apply. Thus an
exhausted comparison can collect a known result and, when all stages were
already submitted, reach review without adding a generation. Unknown pending
submissions still stop continuation. An exhausted clock and an operator stop
have distinct messages and `stop_reason` values.

This remains a **soft limit between stages**, not a pre-emptive kill timer:
an already-started stage may overrun. No GPU job or foreign queue is cancelled
when the allowance expires.

**Operator path:** inspect the measured/unmeasured breakdown in Experiments.
For an exhausted inactive comparison, enter additional minutes and a reason,
then select **Extend time only**. That records an additive, revision-checked
amendment without modifying `plan.json`, creating jobs, changing generation
reservations or queuing work. Choose **Reconcile and resume** separately.
The minimum increment is 60 seconds; the effective total remains capped at
four hours. Concurrent/stale commands fail with a refresh instruction instead
of silently extending twice. Active/queued comparisons cannot be amended.

## API commands for local agents

Inspect the public job/project first and preserve their IDs and evidence.
These examples are request bodies, not actions performed by this document.

`POST /api/jobs/<job-id>/abandon`:

```json
{"reason":"Retain the lost-response evidence; stop local tracking","acknowledge_unknown":true}
```

`POST /api/production/<project-id>/extend-time`:

```json
{"expected_revision":7,"seconds":900,"reason":"Complete the remaining reserved candidate"}
```

Both use the existing loopback Host/same-origin JSON protections. The latter
returns the new revision; a repeated old revision is rejected. A successful
extension does **not** imply `POST .../resume`. Abandonment sends no ComfyUI
cancel, interrupt, queue-clear or generation request.

## Validation and handoff

`tests/test_oldest_issue_regressions.py` deliberately uses only APIs already
present on the initial main. Running its two cases against `f85c00e6` produces:

```text
#93: AssertionError: 'uncertain' != 'completed'
#94: AssertionError: 'uncertain' != 'not_submitted'
Ran 2 tests -- FAILED (failures=2)
```

Both pass with this implementation. Additional causal tests cover repeated
pre-POST restarts, queued observations, lost POSTs, empty/malformed markers,
changed graph/bindings, concurrent abandonment, disk failure, idempotency,
retained root quotas, busy backend queues, monotonic accounting, repeated
resumes, legacy/hard-loss charging, exhausted known-job reconciliation and
explicit revisioned extensions. HTTP tests exercise the actual Handler;
Node VM tests exercise the shipped gallery and Production handlers, including
missing consent, rapid duplicate clicks and escaped user text.

```bash
python -m unittest discover -s tests -p test_oldest_issue_regressions.py
python -m unittest discover -s tests -p test_submission_recovery.py
python -m unittest discover -s tests -p test_production_clock.py
python -m unittest discover -s tests -p test_recovery_commands_http.py
python -m unittest discover -s tests -p test_frontend_handoffs.py
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The existing Production storage safety workflow also runs the new recovery
checks on Linux and Windows. Consult final-head CI, not an earlier branch's
successful run. The PR records actual full-suite counts and skipped tools.

No local ComfyUI inference, installation, download, workstation restart,
process termination, creative review or model-terms decision was performed.
The existing HUMAN_TODO choices remain unchanged, including the chosen
fantasy-character brief and softer cinematic Anima direction; neither is
finished-art acceptance. The documented owner-controlled Windows restart is
already complete and is not being requested again.

Remaining boundary: a mixed batch with retained prompt IDs **and** an unknown
tail marker is not safely equivalent to a known-only observation. This pass
blocks observation from mislabelling that batch complete. Its detailed manual
reconciliation/terminal-disposition workflow remains separate; do not delete
its marker or retry the tail to make a status badge green.

## Primary references

- [Python: time.monotonic](https://docs.python.org/3/library/time.html#time.monotonic):
  use differences between calls, not a stored clock origin across restarts.
- [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes):
  prompt submission, queue inspection and history observation are distinct calls.
- Repository contracts: `app/server.py`, `app/production.py`,
  `app/backends.py`, `app/project_storage.py`, and the tests listed above.

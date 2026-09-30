# Owner cancel (#1138): live proof — 27 September 2026 (16:41-16:44 local)

Live check of the cancel merged in #1159 (server) and #1160 (UI), run through the Studio's own HTTP API
(`POST /api/jobs`, `POST /api/jobs/<id>/cancel`, with the same Origin header the UI sends) against the primary
ComfyUI 0.35.0 on 8188. The running Studio (PID 42900, started 11:43:54) was on `d214640d`, and `app/` has not
changed between that commit and `ffe5b3f9`, so the cancel code under test is current main.

Recipe for every job: preset `wai` (WAI v17, SDXL), 832x1216, SFW scenery wording ("no humans, scenery, stone
lighthouse on a sea cliff, ..."), LoRA slots off. Driver: `receipts/drive.py`, one case per invocation. It
cancels only the Studio jobs it created. Case a also posts one **blocker prompt of its own** straight to ComfyUI
(client_id `cancel-proof-blocker`); that prompt was never cancelled, deleted or interrupted, and it completed
with `success`.

Preflight: ComfyUI queue empty, GPU lease not held, no active Studio job. Host commit was 52.5 % at the start
(50.3 of 95.7 GiB) and 57.9 % at the end (after the WAI checkpoint loaded; 2.7-6.1 GiB physical RAM free while
several unrelated Muse lens jobs ran on the CPU). WAI is not a commit-gated family.

## Results

| Case | Job | Prompt IDs | Outcome |
| --- | --- | --- | --- |
| e. Studio-queued, never sent | `0519691a` | none | `cancelled` within the cancel request itself (18 ms round trip): "Not started: cancelled by you. Nothing was sent to ComfyUI." |
| b. RUNNING, single output | `660e5525` | `fb0f28c0` | interrupt sent 0.96 s after the request; `cancelled`: "Stopped by you: ComfyUI reported the render interrupted. Nothing is retried." |
| c. RUNNING, batch of 3, output 1 done | `4cfc70ca` | `2eeed75e` (completed), `09eaa504` (interrupted) | `cancelled`: "... 1 of 3 outputs finished and are kept. The remaining outputs were not submitted. Nothing is retried." |
| a. PENDING in ComfyUI's queue, batch of 2 | `3ffa0b39` | `3d3715c6` (completed), `a898e17f` (dequeued) | `cancelled`: "Cancelled by you: ComfyUI removed the prompt before it started. 1 of 2 outputs finished and are kept. Nothing is retried." |

### a. Cancel while PENDING (job `3ffa0b39`)

The Studio waits for an idle queue only before the first output of a job, so the pending state was arranged
honestly: while output 1 (`3d3715c6`) ran, the driver queued its own blocker `3a9786c1` (60 steps). When
output 1 finished, ComfyUI started the blocker and the Studio posted output 2 (`a898e17f`), which waited behind
it. The driver's `/queue` read at 16:43:12.367 showed running = [blocker], pending = [`a898e17f`]; the cancel
was requested at 16:43:12.369.

`state.json` cancellation record (excerpt; times are Unix seconds):

```json
"requested_by": "owner", "requested_at": 1790523792.369, "status_at_request": "running", "state": "cancelled",
"actions": [{"action": "dequeue", "prompt_id": "a898e17f-dbf6-4b1a-91f4-4d8d9a9ca278", "at": 1790523794.311, "reply": "ok"}],
"observations": [
  {"queue": "pending", "running": ["3a9786c1-1397-4082-a278-55f0e9f6b966"], "prompt_id": "a898e17f-...", "at": 1790523794.305},
  {"queue": "absent", "history": "absent", "running": ["3a9786c1-..."], "prompt_id": "a898e17f-...", "at": 1790523794.328}],
"resolved_at": 1790523794.328
```

Submissions: index 0 `completed`, index 1 `cancelled` with `{"basis": "dequeued"}`. Output
`Studio/WAI-Illustration_00050_.png` (832x1216 RGB) stays recorded with asset id `9cc63e35…`. `a898e17f` has
no ComfyUI history entry (it never ran). The blocker kept running during the delete and ended `success`,
so the delete touched only the Studio's own prompt. Delete latency: 1.94 s from request to dequeue, which is the
worker's 2 s history-poll cadence.

### b. Cancel while RUNNING (job `660e5525`, prompt `fb0f28c0`)

The driver saw `/queue` running = [`fb0f28c0`], pending = [] at 16:41:53.111 and requested the cancel at
16:41:56.112. The worker read `/queue` itself (observation `queue: running`, running = [`fb0f28c0`]) and sent
`POST /interrupt {"prompt_id": "fb0f28c0-..."}` at 16:41:57.073 (reply `ok`). ComfyUI's log shows the targeted
form: `Interrupting prompt fb0f28c0-3b5c-43a3-8b6f-f06b2aa35d61` (`receipts/comfyui-log-164150-165110.txt`). History: `status_str: error`, last message
`execution_interrupted` at node 4 (`EmptyLatentImage`), `executed: ["1"]`. The job settled `cancelled` at
16:42:22.108 with submission 0 `{"basis": "interrupted", "interrupt_reply": "ok"}`.

**Latency note (not a defect in the Studio):** 25.0 s passed between the interrupt and the settled record. This
was the first WAI load of the session. ComfyUI checks the interrupt flag between nodes and inside sampling,
so it finished loading the checkpoint (`Requested to load SDXL` at 16:42:19) and then stopped at 16:42:20.710
("Processing interrupted"). A cancel sent during a cold model load waits for the load to finish.

### c. Batch cancelled after one output completed (job `4cfc70ca`)

`batch_count` 3, 40 steps. Output 1 (`2eeed75e`) completed (`Studio/WAI-Illustration_00049_.png`, 832x1216
RGB, asset `4587a8c7…`). With `/queue` running = [`09eaa504`] (output 2), the cancel was requested at
16:42:53.637. The interrupt went out at 16:42:54.660 (reply `ok`), and the job settled at 16:42:56.683
(3.0 s after the request). Output 2 history: `execution_interrupted`. Output 3 was never submitted: the job has
only two prompt IDs, and ComfyUI's `got prompt` count rose by exactly 2.

### d. Checks after every case

- **State:** every job ended `cancelled`, none `failed`, `uncertain` or `partial`. Every cancellation record holds
  `requested_by: owner`, `requested_at`, `resolved_at` and `status_at_request`. The three jobs that had reached
  ComfyUI (cases a-c: `3ffa0b39`, `660e5525`, `4cfc70ca`) also record the prompt ID acted on, ComfyUI's reply and
  the `/queue` observations behind the decision. Each of those three has a `cancel-request.json` beside its state
  (copied as `receipts/cancel-request-*.json`). The never-submitted job `0519691a` has no prompt ID, no actions,
  no observations and no request file: it was settled inside the cancel request, and its record says so.
- **Exactly one `/prompt` POST per submission, no resubmit:** ComfyUI's in-memory log (`/internal/logs/raw`)
  counted (the unfiltered log lines for 16:41:50-16:51:10 are in `receipts/comfyui-log-164150-165110.txt`) `got prompt` 1 → 2 (b: one prompt; e: none) → 4 (c: two prompts for three planned outputs) → 7 (a: output
  1, the driver's blocker, output 2). `Prompt executed` rose 1 → 2 → 4 → 6: the dequeued `a898e17f` never
  executed. Every Studio prompt in history has `client_id: asset-studio`. No prompt ID appears twice.
- **Queue empty afterwards:** `/queue` read `running: [], pending: []` after each case (`post` events).
- **Closed for good:** at 16:43:52, `POST /api/jobs/4cfc70ca/resume` was refused with 400 "A cancelled job is closed;
  reopen its recipe as a new draft instead". A second cancel returned 202 with the same `event_id`
  (idempotent). The job reports `can_cancel: false`, "Already cancelled". `got prompt` did not change
  (`receipts/reopen-refusal.json`).
- Offline: `python -m unittest discover -s tests -p "test_job_cancel.py"` ran 28 tests, OK, at the same time.

## UI click — 27 September 2026 (16:48-16:51 local)

One cheap `wai` job (`f9687adc`, prompt `9454cfd3`, 120 steps, seed 927304) was cancelled by clicking the real
**Cancel** button on its running card in a headless Chromium (Playwright, `receipts/ui_cancel.py`). The driver
created the job with `POST /api/jobs`; the page itself sent no generation. The page was `/#create`. The driver
opened the "Recent runs" disclosure (`#workshopResults`) with a click, as the owner would, because the running
cards live there.

- **Before the click** (16:51:02.842): `/queue` running = [`9454cfd3`], pending = []. The card read
  "WAI v17 • illustration · running / Generating output 1 of 1 / Started 16:50 · 13 s so far / Known prompt IDs:
  9454cfd3-… / Cancel / **Stops the render in ComfyUI. Finished outputs are kept. Nothing is retried.**" The run
  dock's reason line showed the same consequence.
- **The click** (16:51:02.927) opened one `confirm` dialog: "Cancel this render? Stops the render in ComfyUI.
  Finished outputs are kept. Nothing is retried." The driver accepted it. The page then sent exactly one
  `POST /api/jobs/f9687adc-…/cancel` (16:51:02.973); its other POSTs were only `/api/estimate`. No page errors.
- The status line changed to "Cancel requested. The Studio is checking ComfyUI; the card shows what it finds."
  The card changed to "Cancel requested (16:51:02): the Studio is checking ComfyUI for this job's prompt.
  Nothing is retried."
- **Server record:** `requested_by: owner`, `status_at_request: running`. The observation was `queue: running`,
  running = [`9454cfd3`]. The `interrupt` for `9454cfd3` went out at 16:51:03.069 with reply `ok`, and the
  job was resolved `cancelled` at 16:51:03.550, 0.58 s after the click (the model was warm). History:
  `execution_interrupted`.
- **Settled card** (fresh page load, `receipts/ui-04-settled-card.png`): "WAI v17 • illustration · cancelled /
  Stopped by you: ComfyUI reported the render interrupted. Nothing is retried. / Known prompt IDs: 9454cfd3-… /
  Recipe". It shows no Cancel button.
- **d-checks:** ComfyUI `got prompt` 10 → 11 (one POST), `Processing interrupted` 3 → 4, and the queue was empty
  afterwards.

Attempts before it, recorded honestly:
1. `b84538ac` (prompt `f0db30fe`, 60 steps) completed normally in 18.3 s. The card never became clickable,
   because the "Recent runs" disclosure was closed.
2. `5e4ce0fa` (prompt `553b363b`) reused the same seed and graph by mistake. ComfyUI served it from cache in
   0.5 s (the same output file `WAI-Illustration_00051_.png`), and it completed before the page's next poll.
   While no job of its own is active, the page polls `/api/jobs` every 15 s (4 s once one is active).
3. `6154ba50` (prompt `657e3166`, 120 steps) was cancelled by the same click at 16:50:22. The job record is
   complete (`receipts/ui-attempt3-6154ba50.json`: `cancelled`, interrupt reply `ok`). The driver then crashed
   while it collected evidence after the click (an ambiguous `#status` selector), so its dialog and POST log were
   lost. The clean run above repeats it.

Those two completed outputs and all cancelled jobs are throwaway; nothing was viewed or judged.

## NOT verified

- **Lost interrupt reply → `unresolved`/uncertain** was not induced live. It needs a fault in the HTTP reply,
  and it is covered only by the FakeStudio tests.
- **Refusal paths** (unreadable queue, prompt absent, two running prompts, delete ignored twice) were not hit
  live. The pending case does show that a non-Studio prompt running at the same time was neither dequeued nor
  interrupted.
- **UI:** the running card's Cancel and its confirm dialog were clicked live (above). Not clicked: the run dock's
  "Cancel run" button (the same `cancelJob()` call), the Problems-card placement, and the disabled-reason
  rendering. Those are covered by the #1160 frontend tests only.
- **Restart reconciliation** (a `cancel-request.json` left over when the Studio restarts) was not exercised.
- Other backends (hidream, h3, qwen21), Production/comparison jobs, and native-operation jobs were not tested.
  The latter two are refused by design.
- The two kept outputs (`Studio/WAI-Illustration_00049_.png`, `_00050_.png`) were checked only like this. Each file
  was opened with Pillow from ComfyUI's output folder: it exists and decodes as 832x1216 RGB. Its `asset_id`
  (`4587a8c7…`, `9cc63e35…`) was read from the job's `outputs` in `/api/jobs/<id>`. Nobody viewed them. Generated is not accepted and not licensed; the WAI licence notes in the catalog still apply.

## Files

`receipts/{a,b,c,e}-<job>.json`: the public job record, `state.json` (submission graphs removed) and the
ComfyUI history status for each prompt. `receipts/events-*.json` holds the driver's timeline, with the `/queue`
reads, commit readings and log counts. The folder also has `recipe-*.json`, `cancel-request-*.json`,
`reopen-refusal.json` and `drive.py`. UI run: `ui-f9687adc.json`, `events-ui*.json`, `ui_cancel.py`,
`after_card.py`, `ui-settled-card.json` and `ui-04-settled-card.png` (a text-only card crop).
`comfyui-log-164150-165110.txt`: ComfyUI's own log lines for the whole window, read from `/internal/logs/raw` at
about 17:25 and saved unfiltered, with colour codes stripped. The three drivers are as-run copies with local paths.

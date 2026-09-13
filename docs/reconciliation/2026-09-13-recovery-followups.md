# Oldest-open reconciliation: worker, framing and terminal recovery

13 September 2026. Source baseline: `06bd93aed2f019cb978eb5795e9f116cfb7ff749`
(main after #195). The initial GitHub snapshot contained 61 open issues and no
open PRs. PR #186 is merged; #93 and #94 are closed. This document records a
software-contract pass, not a workstation, model-quality or licensing result.
The final PR head and its checks supersede this dated source checkpoint.

## Reconciliation and issue disposition

| Issue, in original creation order | Source / discussion reconciliation | Disposition |
| --- | --- | --- |
| #2: HiDream integration | The backend manager, visual/API workflows and pre-listen startup interlocks already exist, including #137. | Remains open for the higher-step comparison, reference-edit and native/runtime evidence. No replacement backend manager. |
| #3: controlled creative experiments | Production, reference editing, native export and newer owner/runtime records already exist. #195 adds a real mechanical Krita revision proof, not neural-edit acceptance. | Remains open for the requested controlled creative outcomes. Do not repeat the obsolete claim that all FLUX files are missing, or that no Krita operation has ever run. |
| #9: source intake and bundles | #142/#149 intake, #156 shared validation and #168 dependency readiness are merged. | Remains open for its broader provenance, exact source graph and hardware evidence. Reuse the existing services. |
| #10: bounded Experiment Lab | Existing single worker, materialized pinned plans, reservations, Workspace and review. #153 fixed publication; #186 fixed the distinct #93/#94 recovery defects. | Advance the remaining concrete worker/reconciliation boundaries below. Accepted creative and multistage demonstrations remain outstanding. |
| #95: worker-failure containment and malformed responses | The original malformed `/prompt` fix and worker health/Prepare guard were already present. The error-handler I/O escape, direct-enqueue admission gap and exact-ID observation follow-ups remained reproducible. | Implement the remaining scope, including the issue's follow-up comments. |
| #97: graph validation coverage | #156 already fixes unions, optional dynamic inputs, declared socketless literals and all-catalog CLI routing. The issue explicitly remains open for a full per-backend installed-schema corpus. | Leave open. Reduced/source-derived schemas must not be presented as the user's installed 1,001-class runtime. |
| #98: framing and MIME protection | All response paths still lacked the framing and `nosniff` headers. | Implement one common response boundary, including inherited errors and ranged media. |
| #110: stopped-prompt terminal reconciliation | Gallery observation could become `failed` or `partial`, while the earlier completed-only continuation gate kept Production uncertain and its button disabled. | Implement evidence-only negative-outcome reconciliation; retain explicit continuation for successful observations. |

These are focused slices under the oldest broad issues, not a claim that every
acceptance item in the entire backlog was certified. Recent #169/#171 guidance,
#180 Wan capacity, #182 polling/resource work, #191 asset detail, #194 disposition
rules and #195 Krita revisions were reconciled, not reimplemented.

Discussion anchors: [#95 follow-ups](https://github.com/Chris0Jeky/local-asset-studio/issues/95#issuecomment-5648644893),
[#95 direct-queue admission](https://github.com/Chris0Jeky/local-asset-studio/issues/95#issuecomment-5649366898),
[#97 remaining installed-schema evidence](https://github.com/Chris0Jeky/local-asset-studio/issues/97#issuecomment-5650454430),
[#110](https://github.com/Chris0Jeky/local-asset-studio/issues/110),
[previous recovery pass](2026-09-13-experiment-recovery.md).

## Current flow and ownership

```text
Create / source-bound continuation / character study
  -> catalog and reference validation / backend and resource preflight
  -> pinned plan, materialized before database publication
  -> explicit Start: check worker, reserve existing root budget, enqueue once
  -> the same Studio consumer
       persist job and pending intent before POST
       keep returned prompt IDs and exact graphs
       observe the exact ID; never turn response loss into a fresh submission
       contain execution + failure-recording errors
  -> retained outputs and separate review/export decisions

Stop tracking -> explicit Resume observation -> known terminal result
  completed      -> explicit Production continuation is still required
  failed/partial -> Reconcile outcome only -> failed project, retained evidence
  unknown tail   -> remains unresolved; no success label or blind replay
```

AV render requests and direct voice resumes use the same worker-admission
predicate before their attempt/state publication. Native jobs retain their
existing executor and evidence rules. No new queue, process supervisor, model
manager, database or application dependency is introduced.

## Worker boundary (#95)

`Studio.require_worker()` rejects a genuinely started-but-dead worker before
Create/Prepare, Production start/resume, scene render or known-prompt observation
can enqueue or spend a new reservation. Voice's direct resume route is included.
The existing pre-start/offline fixture behavior is retained; this is a liveness
observation, not a heartbeat or an atomic promise that a thread can never die
immediately afterwards. No automatic replacement consumer is started.

`Studio._work()` contains both the execution exception and a second exception
from `_save()` / SQLite / failure diagnostics. It continues consuming later
items on the **same thread**; it never retries the failed item. A last-error
record is bounded and explicitly session-only:

```json
{
  "worker_alive": true,
  "degraded": true,
  "worker_failure": {
    "action": "generate",
    "id": "retained-job-id",
    "error": "RuntimeError",
    "recording_error": "disk full while recording failure",
    "durable": false
  }
}
```

The UI shows this independently of ComfyUI online status. The alert survives
subsequent successful dispatches within the session, but resets on Studio
restart. It cannot truthfully promise durable logging when storage itself
failed. Inspect disk space, file locks, logs and retained job records before
continuing the affected task. Existing backend queue/process interlocks remain
in force; neither the alert nor local reconciliation proves the GPU is idle.

Both direct and Production-owned execution use `record_job_failure()`. Unexpected
local processing after a pending intent or known prompt leaves the remote result
uncertain; a confirmed engine failure remains failed. Completed/partial and
abandoned dispositions are not overwritten by a secondary error.

History requests encode the ID as **one path component** with
`quote(prompt_id, safe='')`; stored IDs and response-key lookup remain exact.
Spaces, slashes, query/fragment characters, percent signs and Unicode do not
become URL structure. Truncated, invalid-encoding/JSON or wrong-shaped history
responses remain unknown, with no additional `/prompt` request. Python's default
quoting preserves `/`, so that default is inappropriate here [1].

## Response boundary (#98)

`Handler.end_headers()` supplies exactly one copy of:

```http
X-Frame-Options: DENY
Content-Security-Policy: frame-ancestors 'none'
X-Content-Type-Options: nosniff
```

This applies to static pages, JSON, composed Prompt/Workflow routes, local and
proxied files, 206/416 range responses and inherited HTTP error responses.
Content type, range, download disposition, ETag and body bytes are unchanged.
`end_headers` is the shared point that completes the response header buffer [2].

The policy intentionally denies both same-origin and cross-origin **document
embedding**. It does not prohibit ordinary image/video elements or advanced
editor links. `frame-ancestors` protects framing; it is not a broad script policy
and does not inherit `default-src` [3]. `nosniff` depends on correct MIME types,
so real script/style and media responses are exercised rather than merely
asserting a header helper [4]. Existing Host, Origin and no-CORS behavior remain.
This is targeted framing/MIME hardening, not a claim of a complete web-security
audit or a network-facing deployment configuration.

## Terminal reconciliation (#110)

The existing `POST /api/production/<id>/resume` can now consume an already
recorded negative terminal observation without submitting anything. Its legacy
HTTP acceptance status remains **202**; inspect the returned project state,
which is `failed`, not `queued`. No additional API/executor is needed.

A read-only project projection exposes `can_reconcile_tracking`. The browser
uses that server-computed flag to offer **Reconcile outcome only**, explains
that repair needs an explicit branch, and guards duplicate clicks. GET/list and
page rendering do not mutate the project. After reconciliation, the Resume
button disappears; the ordinary separately budgeted branch action remains.

`submission_evidence.terminal_failure()` requires matching, unique known prompt
IDs and terminal submission receipts. A failed outcome requires a failed
receipt. A partial outcome requires completed known receipts and a recorded
larger requested batch. **Any** `pending_submission` key, including `{}`, blocks
this classification. A job status string alone is insufficient. The partial
regression uses a retained legacy multi-output shape; it does not enable batched
comparison planning or grant the unsent tail free attempts.

Under the existing Studio -> Production lock order, one SQLite state write
updates the affected attempt status/IDs and retains a versioned
`tracking_terminal_reconciliation` receipt with `new_work_authorized: false`.
Its timestamp records reconciliation, not invented GPU duration. The full job,
recipe, workflow, outputs, stop/resume history, plan, root reservations, previous
start time and accumulated time allowance remain unchanged. Stop tokens are
**not** added to `tracking_stop_authorizations` by this action.

Repeat commands are idempotent. Failed persistence leaves the previous state
available for an explicit retry. A stale queued Production pass also reconciles
negative evidence before bundle checks, clock entry or later-stage creation.
Already recorded terminal evidence needs no live worker or active matching
backend; actions that can actually enqueue still require both existing guards.
Successful stopped-prompt observation continues to require explicit Production
continuation, as tested by the earlier dispatch-race cases.

## Verification and reproducibility

Baseline full suite at the source above: **1,463 tests, 15 skipped, pass**.
The initial published local candidate ran **1,497 tests: 1,482 passed, 15 skipped**
(131.518 seconds), including 34 new unittest cases and real-HTTP terminal
commands. Repository validation passed 66 graphs/bindings, 121 pins and 86 LoRA
names. Use the final PR checks and verification comment for hosted/head-specific
results. New cases cover actual worker
thread continuation, I/O and logging failure, all direct queue owners, malformed
observation, exact HTTP request construction, real loopback receipt lookup,
response headers across transports, terminal persistence, stale queued passes,
unknown tails and shipped frontend actions.

Before implementing each behavior, the corresponding causal tests were run
against the prior code and failed: the secondary persistence error escaped;
late observation remained running/failed; framing headers were absent; terminal
Production outcomes remained uncertain or were rejected. Existing malformed
POST, generation quotas, stop/continuation, failed timing and native paths are
retained rather than weakened to make the new cases pass.

```bash
python -m unittest discover -s tests -p test_worker_recovery.py -v
python -m unittest discover -s tests -p test_http_security.py -v
python -m unittest discover -s tests -p test_production_terminal.py -v
python -m unittest discover -s tests -p test_production.py -v
node tests/frontend_health.cjs
node tests/production_terminal_frontend.cjs
python -m unittest discover -s tests
python scripts/validate-repo.py
python tests/recovery_security_browser.py --out .runtime/recovery-security-proof
```

The existing Production storage workflow runs the recovery/HTTP contracts on
Linux and Windows. Its separate pinned-Playwright Chromium lane exercises the
real UI and header boundary with synthetic routes: top-level boot, worker-error
text, keyboard outcome reconciliation, desktop/390px screenshots, no unintended
mutations, and refusal of both same- and cross-origin frames before Studio
scripts load in them. Real routing is covered independently by the loopback
HTTP tests. Browser installation belongs only in a disposable test environment,
never the shared ComfyUI environment.

Local Chromium launched, but navigating to the fixture returned
`ERR_BLOCKED_BY_ADMINISTRATOR`. No flag disabling browser security or container
policy was used. A local browser pass is **not** claimed; the hosted browser
result and retained screenshots must be read for the exact PR head.

## Review and screenshot follow-ups

The initial hosted browser fixture proved framing and keyboard reconciliation,
but screenshot inspection found the worker warning inside the hidden Models
view. A stronger actual-visibility assertion failed on that candidate. The
shared shell now places the same notice first in the main workspace on navigation,
including after the workbench inserts Overview; it does not start any new poller.
Desktop/mobile screenshots and the visible notice are checked on the final head.

Automated review identified a separate persistence edge: a run-directory write
could fail while SQLite still worked, leaving an unresolved job under a falsely
failed project. Two causal pending/known-ID tests reproduced this. The outer
coordinator fallback now records **uncertain**, including the processing/recording
error, rather than certifying failure. Normal stage reconciliation still records
confirmed terminal outcomes. The tests verify unchanged recipes/workflows and
reserved attempts, restart persistence, repeated observation with no new prompt
POST and continued dispatch of the next item. There are now 36 new unittest
cases; final full-suite and head-specific CI results are recorded on the PR.

## Remaining work and handoff

#97 still needs the full installed-schema corpus. #187 still owns mixed batches
with known IDs and an unknown submitted tail; the new negative predicate does
not relax that hold. Broader #2/#3/#9/#10 acceptance requires appropriate source,
hardware, native and owner-reviewed evidence. No new issue duplicates these
already tracked gaps.

No user machine services, model packages, downloads, ComfyUI queue, art approval,
license decisions or HUMAN_TODO entries were changed. The owner-selected fantasy
pack, experiment-only Anima direction and recorded native/canon decisions remain
as recorded; the page-file restart is not an outstanding action. Native/creative
success must not be inferred from the synthetic tests in this change.

## Primary technical references

Reviewed 13 September 2026; repository changes and acceptance evidence are linked
above. These sources explain only the platform mechanics, not a model run.

1. [Python urllib.parse quoting](https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote).
2. [Python BaseHTTPRequestHandler end_headers](https://docs.python.org/3/library/http.server.html#http.server.BaseHTTPRequestHandler.end_headers).
3. [MDN frame-ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors).
4. [MDN X-Content-Type-Options](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Content-Type-Options).

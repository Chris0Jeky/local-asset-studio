# Analyze pictures directly in Prompt Lab

The **Start with pictures** panel runs the existing local reference assistant on
Studio's shared worker. It no longer needs a CLI-created analysis JSON for the
normal path. The manual saved-analysis and reference controls remain available.

## Use

Configure an already-installed local vision helper once using
[REFERENCE-JOBS.md](REFERENCE-JOBS.md). Until that exact model/digest/resource
configuration exists, Analyze is disabled and the panel explains the missing
setup. The browser cannot download a model, choose a remote provider, change
capacity policy or mutate the installed Comfy runtime.

Select one to four original pictures, enter a short instruction in **Creative
brief**, and press **Analyze pictures**. Blank text is supported. Image roles start
as `auto`; the whole set reaches one structured vision request. Duplicated picture
content is refused, not used as an implicit weighting trick. Analysis does not
start from selecting files, typing, loading this page or inspecting prior results.

The status distinguishes queued/preparing/submitting/completed/failed/uncertain.
**Check status** observes the saved operation. **Cancel queued analysis** is only
available before preparation; it cannot promise to cancel an already accepted
model request. The server checks memory, queue, installed model and saved context
again after waiting for the worker, so a queued request may still be refused.

When a result exists, choose **Review this analysis**. The existing reference
review panel shows its interpretation, per-image roles, descriptions, tags and
unknowns. Originals already selected in this tab are matched by SHA-256, including
reversed order and changed filenames. After reload, reselect those exact originals.
**Review** does not modify your brief. Changes still require **Preview changes**
and **Apply to brief**. A newer instruction typed while analysis ran stays intact.
Description edits, locked fields, Undo and exported provenance retain the existing
reference review behavior.

Native generation is still a later step through a compatible registered recipe.
This feature does not flatten visual references to captions or bypass unsupported
native slot/geometry/mask contracts. In particular, the current text-only Prompt
Lab/Create bridge is not made into a four-image generator by adding this panel.

## Refresh and lost replies

Before create is sent, the browser writes just the Workspace/request identity to
session storage and reads it back. If that fails, it sends **no** analysis. The
stored handle contains no pixels, filenames or prompt. It survives refresh in the
same tab; it is not an authoritative job database or shared CreativeIntent revision.

A lost create reply leaves the handle and disables further creation. Status reads
use that identity; they never replay create. Reload reads the saved operation and
resumes observation, without POSTing. Polling is single-flight, uses one timer, and
pauses when the document is hidden. Settled/unknown failures remain inspectable;
there is no automatic new model call after a timeout or bad response.

The recovery disclosure also lists at most eight recent Workspace operations,
from server state, for explicit inspection when no handle is active. If a saved
handle belongs to a different Workspace, it is not silently rebound. Unknown IDs,
unavailable storage and inconsistent responses are surfaced without claiming the
model was cancelled. Full cross-tab editable intent persistence remains #38.

**New analysis** clears only a settled, unheld local handle. The previous operation
and its result stay in the Workspace. Starting the next request requires another
explicit Analyze action; this is not an automatic retry button.

## Resource holds

A completed report can still carry a resource hold if unloading could not be
observed. A lost/incomplete model reply stays uncertain with its hold retained.
Such holds block new Studio generation and backend lifecycle work. They do not
prevent reviewing an already saved valid report.

The hold disclosure offers **Recheck and release hold**. For an unanswered model
call, the user must confirm that the specific call has stopped. The server also
checks current state and fresh empty helper residency. `/api/ps` is not a queue
or cancellation acknowledgement. Release does not repeat inference, restart a
process, alter the old outcome or refund an attempt. Never use it as a blind
"run anyway" action. External helper/Comfy clients are outside Studio's ownership.

## Verification scope

The tests use the actual controller, original-image hashing, actual HTTP handlers,
temporary Workspace SQLite and the real `Studio._work` dispatch branch. The browser
fixture holds a simulated VLM response while refreshing the page; separately it
drops a committed create reply and proves that reload only observes the saved ID.
It checks review/apply against newer brief text, source retention, uncertain-result
release, keyboard operation and 1440px/390px layouts. It creates zero image jobs.

The model responses and sensor readings are synthetic. Successful browser tests
are not evidence of local VLM understanding, faithful style/pose/identity transfer,
AMD memory fit, improved anatomy or owner artwork acceptance. Configure/qualify
one existing model on the workstation before calling this production-ready.

Commands: `python -m unittest discover -s tests -p 'test_reference_*.py'`,
`python tests/reference_analyze_browser.py`, the existing reference-review browser
journey, full suite and repository validator. Hosted Chromium is the browser gate
where local container navigation is blocked by administrator policy; that policy
is not changed. Refs #35, #38, #178, #313. HUMAN_TODO choices are unchanged.


## A request that never reached the journal

A failed intake or lost create reply can leave a saved request ID with no visible
operation. **Recover an earlier analysis / setup → Retire unqueued request** is
an explicit recovery action. The server atomically returns the existing operation
unchanged, or records a terminal no-dispatch tombstone. A slow create arriving
after that commit cannot run under the retired ID. The action does not cancel a
running helper, release a hold or infer non-submission from a transient 404.

After a retired receipt is visible, **New analysis** clears only this tab's
handle; starting the corrected request still needs an explicit Analyze action.
A lost retirement reply is recovered with Check status against the same saved ID.
Tombstones use a separate 64-record/512 KiB retirement budget and do not consume
the 64-operation/128 MiB analysis history budget. The exact live values are
reported by the server's capabilities response. This does not implement general
history eviction or allow an old retired ID to become new work. Existing queued,
submitting or uncertain operations are returned intact and use their normal
observation/cancel/release controls. See issue #397 and `REFERENCE-JOBS.md`.

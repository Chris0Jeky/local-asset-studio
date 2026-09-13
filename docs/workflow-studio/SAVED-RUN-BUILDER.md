# Saved runs in the builder

This is the browser client for the saved-revision ledger from #150, the agent
clients from #152, and exact-ticket dispatch from #154. It uses those same routes,
not a second workflow store or executor. The original tab-local ticket panel is
kept for existing tickets and unsaved-document work; it is not silently migrated.

## Use it

1. Import a compatible registered image preset in **Guided workflows → Workflow
   builder**. Edit in Steps or Nodes and choose **Save to Workspace**. New saved-run
   preparation is disabled while local edits, a save request or a known revision
   conflict remain unresolved. Reopen current or save explicitly; nothing autosaves.
2. In **Saved runs**, select **Prepare saved revision**. The panel retains a unique
   preparation request before POST, then reads and verifies the committed source
   record. Preparation can check schemas/resources but never queues generation.
3. Review the original revision, projected control changes and expandable exact
   ticket. Use **Run / recover original** only after confirming that source. The
   current editor is not substituted, even after later edits or an agent save.
4. **Observe original job** reads locally retained job evidence without polling,
   submitting, cancelling or resuming work. `not_observed`, `workspace_changed`
   and `evidence_mismatch` remain distinct from a completed or unsubmitted job.
5. Reopen the workflow and choose **Load run history**, or enter the original
   preparation ID. Select a run and **Review original run**. Download exact ticket
   and source-record JSON for an external copy. A new tab can recover from the
   Workspace history without the previous tab's in-memory ticket.

A history entry means *prepared*, not executed. The panel labels an older source
and an editor that differs from that original. Preparation/export, generation,
creative acceptance and model licensing remain separate states.

## Recovery and storage

Preparation requests are bounded JSON objects stored under distinct localStorage
keys `studio.workflow.saved-preparation.v1.<request-id>` before network I/O. Separate
keys prevent two tabs from overwriting a single pending slot. Notes contain IDs,
revision and preset, not image data or a copy of the workflow. The 32-note browser
bound is a guard, not a transactional cross-tab quota; the server has its own
ledger budgets. Corrupt notes are retained and explained, never silently pruned.

A lost POST response, failed readback or stale selection retains the note. **Recover
preparation** sends the original body with the same ID; it cannot create a second
committed ticket for that identity. New preparation requires resolving pending
notes or explicitly removing a local note. **Remove local note** asks for confirmation
and states that server records/work are not deleted; keep its ID first. It does
not infer a preparation or generation failed. After a rejected incompatible
preparation, this explicit action permits editing and a new deliberate request.

A lightweight last-reviewed source reference is also kept locally. Restoring that
reference performs no API call and does not authorize execution. Local storage
failure prevents preparation/dispatch but does not remove server history or make
read-only review unavailable. Browser storage can be deleted or unavailable;
server records, not localStorage, are authoritative. Local keys share the Studio
origin, not a cryptographic workspace namespace: wrong-workspace reads/refusals
are surfaced rather than joining or re-dispatching evidence from another workspace.

## Exact data and command ownership

The read-only `WorkflowProject.snapshot()` bridge exposes only saved identity,
revision and dirty/blocked/conflict flags. It does not expose private save commands
or bypass their compare-and-swap checks. A `workflow:project` event reports changes
including a separate-copy attachment that did not replace the editor graph.

The panel verifies SHA-256 over **UTF-8 `record_json` and `ticket_json` text**, not
parsed/reserialized JavaScript objects. Metadata is checked against the original
request and projection; large seeds stay in exact text for display/download.
Execution sends only `approved: true`, record SHA-256 and ticket SHA-256 to the
saved ID's `/run` route. That route resolves the server's original ticket and
uses the existing retained-intent worker path. The ordinary browser graph editor
still refuses unsafe wide-integer editing; exact review is not a new integer editor.

Requests have a 30-second browser deadline. Abort/HTTP/malformed replies after
Run are conservatively uncertain; no new preparation or automatic retry follows.
The browser deadline does not cancel shared work. Run is explicitly **original**
execution/recovery, not a claim the original has never been attempted.

History uses server sequence cursors, checks document membership/order and
invalidates late pages when the open binding changes. Pending preparation can
finish while a user opens a different workflow; the record remains recoverable
but is not attached as that other workflow's run. There is no startup generation,
automatic polling, queue clearing, environment switch or model installation.

## Verification and boundaries

`python -m unittest discover -s tests -p test_workflow_saved_runs_ui.py` runs
**17 Node contracts**: exact large-number text, corruption/source mismatch,
per-request notes, bounds, storage failure, startup inertness, dirty/conflict gates,
lost preparation and dispatch replies, changed-workflow/history races, exact
downloads, hash-only execution, explicit consent and duplicate-click interlocks.
The existing history-scope test now verifies the read-only project bridge also
reflects a copy attachment without loading another editor graph.

Optional browser test:

```bash
python tests/workflow_saved_runs_browser.py --chromium /path/to/chromium
```

This full-page test binds an unused container loopback port 8191 and uses actual
Studio HTTP routes/SQLite with temporary synthetic catalog/nodes; its worker does
not run. It exercises import, save, dirty gating, preparation, history selection,
an intervening agent edit/rejected stale preparation, original-ticket execution
and recovery, observation, tab reopening and an exact int64 ticket download.
A real installed ComfyUI or GPU is never used by this fixture.

In the source environment normal Chromium navigation returned
`ERR_BLOCKED_BY_ADMINISTRATOR`. It was **not bypassed** and no native-origin/browser
storage result is claimed. Running with `--inert` uses the actual production HTML,
CSS and scripts with injected browser transport, storage and digest plumbing;
HTTP still passes through the actual temporary Studio server. That mode passed
with one queued synthetic job after two original-run calls, zero model submissions,
zero page errors, and exact wide-seed export. Desktop and 390px component captures
were inspected. This is useful integration evidence, not workstation acceptance.

Arbitrary graphs, references/masks, native custom widgets/subgraphs, per-node
progress, owned cancellation, auto-backfill and art acceptance remain outside this
slice. See #118–#123 and [SAVED-RUN-DISPATCH.md](SAVED-RUN-DISPATCH.md).

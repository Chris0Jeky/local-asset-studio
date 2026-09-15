# Save and reopen reference briefs

Prompt Lab's **Saved briefs** panel stores the full creative brief, profile and
reference-review descriptions in the existing local Workspace. It uses the
[shared revision/command service](PERSISTENT-BRIEFS.md), also available to agents.
Original image bytes are not saved here or staged to a generator.

## Working with a saved brief

Give the brief a name and choose **Save as new brief**. After opening a saved
brief, **Save changes** appends a revision. Typing, analyzing, reviewing and
changing a reference description never cause an automatic save. A save does not
approve artwork or generate anything.

**Preview saved brief** displays the saved document beside the current editor.
**Open preview in editor** replaces the editor only if it and its reference review
have not changed since previewing. The original instruction, selected profile,
reference roles, locks and full typed fields are retained. Saved reference-review
selections reopen with their description overrides; their original images must
be reselected before another validated reference transfer. Saved observations may
be historical or unapplied, not necessarily descriptions of the current brief.

The current-revision line distinguishes unsaved editor changes. Pending file imports
and original-image hashing are tied to the draft that started them; completion
cannot overwrite a newly opened brief or attach old pictures to it. Reference
batches are applied together only after every file succeeds. An acknowledged
save never copies its older submitted words over newer typing. If another tab or
agent saved first, the stale save is rejected. Nothing silently merges, rebases,
unlocks a field or overwrites the other writer. Preview the current server version,
compare it with the retained editor, then make a deliberate choice. Saving a new
alternative is separate from changing an existing brief.

**Earlier revisions** reads the newest 32 revisions. The shared history API can
page farther back. Preview an earlier revision, then **Restore preview as a new
saved revision** appends its content if the server head still matches. Older
revisions remain unchanged. Restore offers its result for explicit opening rather
than overwriting unsaved editor changes automatically. Saved locks still apply.

## Interrupted saves

Before sending a create/save/restore, the browser writes and reads back its exact
command and request identity in bounded session storage. If retention fails, no
write is sent. The request is distinct from subsequent edits to the visible form.

After a lost reply or reload, **Check save status** reads the original request's
receipt. It never sends another save. A confirmed receipt describes the historical
revision the command created, not a promise that it is still the latest version.
The editor remains unchanged until **Open preview in editor** is pressed.

**Retry exact save** is a separate explicit command using the original bytes/ID;
the server returns its retained receipt rather than creating a duplicate revision.
A timeout is unconfirmed, not evidence that the save did not happen. No automatic
retry occurs. A rejected/stale request may have no receipt; its local identity is
kept until the user resolves or explicitly forgets it.

**Export pending command** retains the recovery data as JSON. Forgetting a local
handle requires an explicit acknowledgment and does not cancel or undo any server
save. An unresolved handle from another Workspace is not silently replayed into
this one. Malformed local recovery blocks new saves until reviewed/discarded.

Only submitted commands are retained for recovery. Unsaved typing after submission,
selected original files, unsubmitted review changes, browser undo history and
active-project selection are not automatically recovered after reload. Save or
export meaningful work explicitly. Reopening a saved document does not cancel or
replay a separately running Analyze operation; that operation keeps its own handle.

## Boundaries and implementation

`StudioPromptDraft.openSaved` and `StudioReferenceReview.capture/restore` keep the
existing browser owners. The panel is a client of these owners and the shared
service, not a second database. Reads and writes are single-flight in this panel,
with bounded response reads and a transport deadline. Files and commands remain
local; no external provider or generic execution endpoint is introduced.

The command service validates complete documents and saved locks. A server revision
is distinct from the local editor's change counter; compare-and-swap uses the
actual saved revision. Existing analysis and final generator input checks remain
separate. A stored reference hash is not a verified file lease or a native graph
binding. Native generator handoff, held-out model/pose/style qualification and the
owner's accepted asset pack remain #232/#35/#37/#313 work.

## Verification

Run `python -m unittest discover -s tests -p 'test_prompt_projects*.py'`, the
existing reference/Prompt Studio contracts, and
`python tests/prompt_projects_browser.py --output .runtime/prompt-projects/browser`.
The actual browser driver uses real HTTP handlers and temporary Workspace SQLite,
with synthetic data and no model worker. Scenarios cover 1440px/390px, keyboard
save, descriptions after reopen, two-client conflict, append-only restore, lost
reply/reload/read recovery, held save replies and storage failure before dispatch.
The existing Prompt Studio workflow runs it alongside Analyze and Review journeys.

Local Chromium navigation is blocked by administrator policy; the policy is not
changed. Hosted browser results qualify actual navigation. Node tests execute the
real modules with controlled DOM/transport for local state/recovery checks. Passing
software tests is not actual VLM/GPU, artwork-quality or owner-machine evidence.

# Persistent reference-led briefs

Goal: save and reopen the current CreativeIntent, selected profile and reviewed reference context without losing newer human or agent edits.

Continue #38 on the already published #389 -> #396 -> #398 stack. Analysis execution/recovery is owned there; do not add a scheduler. Main was inspected at b29205c; this work's source parent is exact #398 head 1c0c347. Existing workflow document persistence supplies the transaction/receipt pattern, not an interchangeable workflow schema. Use AssetWorkspace's existing SQLite connection and identity.

## Delivery 1: shared project service

- [ ] Test first: real temporary SQLite create/save/read/history/restore, identical command replay, changed request refusal, stale revisions, cross-workspace guards, rollback, restart, contention, limits and corrupted storage.
- [ ] Add a bounded `studio.prompt-document/v1`: title, profile ID, complete CreativeIntent, optional immutable analysis plus selected review context. An empty brief may be saved. Context is a record of selected observations, not proof of current pixels, model execution or approval.
- [ ] Extract source-independent review validation from the existing reference contract. File and in-memory draft generation must still check every original; do not offer a public unchecked generation route.
- [ ] Add named project heads, immutable revisions and exact durable commands in the existing Workspace DB. Save/restore require expected_revision. Receipt/status reads do not replay commands. Restore appends. Existing locks cannot be silently removed or overwritten; deliberate alternatives can be saved as a new project.
- [ ] Add same-origin HTTP create/save/restore and scoped list/read/history/command-status. No asset/media/model access. Initialize at Studio startup, not by a GET.
- [ ] Add an HTTP/CLI client over those exact operations; writes are explicit and never transport-retried. Test the actual composed handler.

## Delivery 2: Prompt Lab Save/Open

- [ ] Add failing UI tests for stale load, save while typing, lost committed response, reload/status recovery, cross-tab save conflict, restore and storage failure before dispatch.
- [ ] Extend the existing draft owner with guarded document replacement. Save/Open is explicit; an agent's change cannot overwrite a local draft. Preserve current reference-review selections as separate context; original files require reselection after reload.
- [ ] Add compact title, Save new/Save changes, saved-project and history selectors, explicit preview/open, restore, request-status/exact-retry controls. Persist the immutable pending request before write; retain newer typing separately. Do not autosave, auto-open, auto-replay or silently rebase.
- [ ] Use actual browser + HTTP + SQLite fixtures at desktop/390px and keyboard. Preserve the existing Analyze/review journeys and zero generation on every persistence operation.

## Bounds and verification

At most 128 projects, 256 revisions each, 256 KiB per document, 32 MiB combined revision/command payload history, 32 history rows per page. Refuse at limits without pruning old request identities. Requests at most 512 KiB. Local source is an exact Git-tree-verified archive, not a clone. Run focused tests, full lifetime suite, repository validator, JS checks and browser evidence. Keep synthetic evidence separate from Windows/VLM/GPU quality. HUMAN_TODO and live runtime remain unchanged. Leave broader #35/#38/#232/#313 open.

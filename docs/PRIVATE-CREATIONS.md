# Private creations

Private keeps personal creations out of the Studio's ordinary history, Library,
search results and default agent reads. It gives their runs and media a separate
folder structure. You can still browse Regular, Private or All without changing
what the current creation will be.

This is an organization and visibility feature. It is not encryption, an account
permission or secure deletion. Anyone who can read the local files or deliberately
request the private API scope can read the content. ComfyUI, browser downloads,
backups and exported files can retain additional copies.

## Start or change a creation

The privacy bar has three controls with distinct roles:

| Control | Effect |
| --- | --- |
| **Private session** | Sets the default for this tab and clears the per-creation override. Turning it on selects Private; turning it off selects Regular. An existing All view stays selected. |
| **This creation** | Overrides the session default for the current creation. Choose Private while still selecting a look, editing wording or arranging references. A job acknowledgment resets this override to the session default unless you made a newer choice while submission was pending. |
| **Regular / Private / All** | Changes the history and Library being viewed. It does not change the current creation, move files or submit anything. |

For a personal session, turn on **Private session**, choose an image goal in Make,
pick a look, describe the scene and generate when ready. For one personal creation
in an ordinary session, choose **Private** under **This creation**. The status line
states the current creation's classification before you submit it.

A creation may be private while the Regular view is selected. Its result will be
hidden there; choose Private or All to see it. Likewise, browsing All does not make
the next creation private. Reusing a private result in a regular Make draft asks
you to choose Private before it copies the source wording or references.

### Keep an unfinished draft

Make now recovers the goal, wording, source identities, selected pose route and
style/fix choices after a same-tab reload. It checks the original Workspace and
the source identities before allowing another submission. Missing sources keep
the wording visible and ask you to choose a source again; restoration never
generates a replacement or silently borrows another asset.

In Full editor, recovery is per recipe: after a reload, select the matching recipe
and use **Restore draft**. Exported private drafts carry their classification.
Importing one selects Private before adopting its contents. A regular or legacy
draft uses the current creation setting. A successfully imported draft is saved
for subsequent reload when browser storage is available.

Converting the current regular draft to Private preserves its in-memory wording
and choices and, when browser storage is available, removes this tab's owned regular
browser copy. If storage refuses that change, the Studio warns that a previous
regular copy may remain and offers export. It does not delete
an unrelated recipe or a newer draft written by another tab. If another tab owns
that saved copy, the Studio keeps it and explains why. Leaving private creation
restores a separate regular draft or clears the editor; private wording and undo
buffers are not copied into regular storage.

Private draft text and private/All recovery records use tab-scoped session storage.
Where recovery offers an in-memory fallback, it lasts only for the current page;
it cannot survive a reload. They do not enter the regular persistent recovery
shelf. An independent new tab starts with regular defaults. Browser session
restoration or duplicating a tab can retain browser data, so closing a tab is not
a secure-erasure operation. Export a private draft if you need a deliberate copy
for later; store that download appropriately.

## Find, review and organize the results

Regular is the default for history, Home, Library pages, search, direct asset/job
reads, family/recall readers and agent tooling. Private and All are explicit views.
An existing Library page may need one refresh after upgrading to the scoped
catalogue. Subsequent private edits do not expire regular pagination or alter its
catalogue revision.
The Trash scope remains separate: **Private + Trash** finds private items in
Trash. The independent **Archive state** selector chooses Active assets, Archived
assets or Active & archived within the current privacy and Trash scope. Selecting
All privacy does not include archived assets unless the Archive filter does too.

You can review, favorite, tag, annotate, collect, export, archive and put private
assets in reversible Trash through the scoped Library. **Return to active** reverses
Archive without changing privacy or restoring from Trash. A collection has one classification;
mixing regular and private members is refused as a whole operation. All view lets
you inspect both classifications without creating a mixed collection.

Changing scope clears visible results, source-picker contents, selections and
detail/recovery panels immediately. Each view keeps its own unfinished Library
recovery. Collection recovery follows the collection's regular or private
classification. Late reads cannot refill the previous view. A delayed
write response remains associated with the original command, so an uncertain
outcome is never treated as permission to submit a replacement automatically.

The regular optional IndexedDB recovery shelf is separate from the private and
All shelves. Private/All shelves are bounded and retained for this tab. Exported
recovery bundles carry their scope, and restoration requires the matching view.

## Where the files go

Paths below are relative to the configured `experiments` directory.

| Content | Regular | Private |
| --- | --- | --- |
| Run state, recipe, graph and submission evidence | `runs/<job-id>/` | `private/runs/<job-id>/` |
| Staged references and sidecars | `uploads/` | `private/uploads/` |
| Immutable asset snapshots | `workspace/media/` | `private/media/` |
| Thumbnails | `workspace/thumbs/` | `private/thumbs/` |
| Export ZIPs | `workspace/exports/` | `private/exports/` |

The shared Workspace database retains asset metadata and privacy labels. Existing
rows migrate additively as regular. Snapshot hashes are kept, but blobs are not
shared across the regular and private roots. A private image job also uses the
private output prefix in its submitted ComfyUI graph; ComfyUI still owns its own
input/output/history files outside this table.

Classification is fixed when a job is admitted and saved before it enters the
queue. Restarts read both run roots and retain prompt IDs and uncertainty without
resubmitting. Corrupt private records, conflicting IDs or invalid storage claims
are not reclassified as regular. Private media responses use `Cache-Control:
no-store`; that policy does not erase earlier copies or downloads.

Exporting an explicitly selected set that includes private assets writes the ZIP
under `private/exports/`, including when the selection was made in All. The export
contains the asset metadata and available exact recipes, so the ZIP itself can
contain personal wording. Downloading it creates a separate browser-owned copy.

Do not reorganize these directories by moving individual files behind the
Studio. The catalogue, job evidence, shared parents and command receipts depend
on their recorded identities and paths.

## Agent and API access

Existing clients keep regular defaults. A caller must deliberately choose a
private or all scope. A known private ID with no explicit scope is unavailable in
the same way as an unknown ID; guessing an ID does not reveal its title or prompt.

| Contract | Values and meaning |
| --- | --- |
| `X-Studio-Privacy` | `regular`, `private` or `all` for existing records and reads |
| `?privacy=` | The same scopes for media/query endpoints; conflicts with a supplied header are rejected |
| `X-Studio-Creation-Privacy` | `regular` or `private` for new creations, including binary uploads |
| JSON creation `privacy` | `regular` or `private`; it must agree with a supplied creation header |

Duplicate, unknown or conflicting scope values are refused. `all` is a read scope,
never a classification for a newly created item. Browsing headers cannot
accidentally reclassify an upload or job.

The bounded read client supports explicit scopes:

```sh
python -m studio_workflow.asset_read_client --url http://127.0.0.1:8191 page --privacy private --limit 50
python -m studio_workflow.asset_read_client --url http://127.0.0.1:8191 selection --workspace-id WORKSPACE_ID --privacy private ASSET_ID
```

The MCP `asset_page` tool accepts `filters.privacy`; `asset_selection` and
`job_status` accept `privacy`. Private creation may deliberately use an existing
regular reference without changing the source's classification. Regular creation
cannot consume private references by omitting the flag.

Existing metadata commands retain the Workspace identity, selected IDs, expected
revisions and one request ID. Preserve that exact command across interruption and
look up its receipt in the original scope. An unknown receipt is an unknown
outcome, not proof that a retry with a new identity is safe. The separately scoped
agent organization follow-up builds on these commands; it does not move physical
files or delete media.

## Supported boundary and remaining work

This first slice supports ordinary image creation in Make/Full editor, image
upload/import, supported image continuations, asset media, scoped Library
metadata/collections/recovery, deliberate ZIP export and bounded SDK/MCP reads.

Private requests on unqualified advanced paths are refused before their side
effects. These include Production comparisons, saved shared setups/looks/cards,
workflow documents and project execution, drawn-pose artifacts, AV/voice/native
handoffs, tiles, parallax, video and 3D generation. Existing regular workflows keep
their regular behavior. A button being available in All does not authorize a
private-to-regular derivative.

An already generated regular run cannot yet be moved into Private. Changing only
its asset label would leave its siblings, original job and prompt visible.
Completed-run conversion needs a preview of the entire affected run, a durable
move journal, verified publication, crash recovery and Windows failure tests.

The Library now has [reversible logical Archive](ASSET-ARCHIVE.md), separate from
privacy and Trash. Archive hides finished assets from the default Library view;
Return to active brings them back under the same privacy and Trash scope. It keeps
original files, IDs, lineage, review and collection membership, retains unsaved
editor wording, and uses the existing revisioned command/receipt recovery. It does
not relocate files, reclaim disk space, reclassify completed runs, introduce a
retention-deletion policy or resolve an uncertain generation. Completed-run
privacy conversion remains separate work under #1678.

## Verification and workflow QA

The implementation has causal tests for default-hidden reads, separate storage,
private restart recovery, strict scope parsing, scoped receipts, source inheritance,
duplicate IDs, storage aliases and private media cache/range behavior. Actual MCP
stdio tests exercise explicit private/all reads. JavaScript tests hold uploads,
reads and writes across privacy changes and verify their original ownership.

Two native browser drivers exercise the shipped controller and views against a
temporary SQLite Workspace: `tests/private_creation_browser.py` and
`tests/private_recovery_browser.py`. They use synthetic media and inert job
acknowledgments. They never load a model or submit to ComfyUI. The dedicated
**Private creation boundaries** workflow runs those checks on Linux and Windows.

See [the measured creation journeys](ux-qa/CREATION-JOURNEYS-2026-10-26.md) for ten
bounded interaction paths, including an adult anime-character brief, model/LoRA
tuning, reference reuse, pose changes, restyling and variation. It separates input
counts from automated wait/capture time. These checks establish workflow behavior;
they do not establish human task time, artistic quality or owner acceptance.

[The proposed owner trial](ux-qa/OWNER-ANIME-TRIAL-2026-10-26.md) provides a fixed
adult-character brief, timed tasks, a bounded output budget and an empty quality
scorecard for that configured-machine session. It has not been run.

## Browser storage refusal and finder choices

Moving an unfinished Make creation to Private verifies the private draft's saved
bytes before removing its earlier regular recovery copy. When browser storage is
full or unavailable, the current wording and selected sources stay in this page,
with a warning to keep it open and copy the wording before reloading. The earlier
regular recovery copy is **not removed** on that failure. This page-only fallback
is not restart recovery; a later successful edit can persist the private draft.
Changing only the Regular/Private/All browsing scope does not discard that draft.

The tool finder passes an explicit goal/look to Make's own state owner. On the main
page it does not reload the editor. From another Studio page it carries only a
single-use catalog choice in tab storage, never private wording or a new regular
persistent preference. An old recovered goal cannot overrule that explicit choice.

Admission and failure tests are recorded in
[the qualification note](verification/2026-10-28-private-creation-qualification.md).

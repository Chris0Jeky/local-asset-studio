# Private creation and browsing — implementation contract

## Scope and boundary

Private is an explicit Studio organization and visibility boundary. It hides private content from ordinary history, search, library, direct-ID reads and default agent tooling. It does not encrypt files, remove past browser caches/backups, or erase ComfyUI's own input/output/history copies. Private creation retains exact recipes and prompt IDs. Nothing auto-generates, repeats uncertain submissions, or deletes engine evidence.

This pass supports Make/Create, image upload/import, ordinary image generation, saved asset media, Library and bounded agent asset reads. Advanced operations must reject private requests or private source material before writing/staging until their storage and recovery owners support privacy. Archive remains separate and follows only after private end-to-end verification.

## Two independent concepts

- Stored classification: `privacy = regular | private`. Legacy records default to regular. Classification is frozen on generation admission and persisted before queueing.
- Requested browsing scope: `privacy = regular | private | all`. Omission means regular. This never reclassifies an item. Existing `visibility = active | trash | all` retains its current trash semantics.

A per-tab private session defaults new drafts/uploads/runs to private; it can survive reload in that tab through sessionStorage. New tabs start regular. A single ongoing draft can become private without changing the session default or overwriting the saved regular draft. A private draft's text, pending input metadata, Make run cards, scene/fill values and recovery handles must never be written to regular localStorage keys. Keep private draft recovery in a privacy-namespaced sessionStorage key and expose it only through an explicit private context.

## HTTP contract

- `X-Studio-Privacy: regular|private|all` selects read scope for core reads and mutations affecting existing entities.
- `X-Studio-Creation-Privacy: regular|private` supplies classification for binary uploads and creates lacking a JSON classification.
- JSON creation payload `privacy: regular|private` is authoritative when present; conflicting header/payload values are rejected. `all` is invalid for creation.
- `?privacy=regular|private|all` supports direct media and bounded query endpoints. Reject duplicated scope fields, duplicate headers and conflicting header/query values.
- No explicit scope means regular, including known IDs and command receipts. A hidden entity must receive the same missing/unavailable response as an unknown identity, without title, prompt, filename, content hash or count disclosure.
- Private media uses `Cache-Control: no-store`; existing `Cache-Control: private` means browser-cache policy and is not this feature.

Root owns `app/creation_privacy.py`: `normalize(value, allow_all=False)`, `scope_for_handler(handler)`, `creation_for_handler(handler, payload=None)`.

## Storage ownership and migration

Retain one `AssetWorkspace` SQLite catalogue and one Studio worker. Never change a mutable global/threadlocal storage root per request.

| Data | Regular | Private |
| --- | --- | --- |
| Run recipe, graph, state and submission evidence | existing `experiments/runs/<job-id>/` | `experiments/private/runs/<job-id>/` |
| Staged upload and sidecar | existing `experiments/uploads/` | `experiments/private/uploads/` |
| Immutable asset snapshots | existing `experiments/workspace/media/` | `experiments/private/media/` |
| Thumbnails | existing `experiments/workspace/thumbs/` | `experiments/private/thumbs/` |
| Deliberate export packages | existing `experiments/workspace/exports/` | `experiments/private/exports/` |

The shared catalogue retains metadata and privacy labels; it is not an encryption boundary. Add `privacy TEXT NOT NULL DEFAULT 'regular'` to asset and collection rows inside the existing initialization transaction. Add command classification to asset receipts so later scope changes cannot expose an earlier private receipt. All old media paths remain valid. Snapshot row paths remain `media/<sha256><suffix>` and resolve relative to the storage root selected by the row's classification. Do not deduplicate blobs across regular/private roots.

`register(job,index,source)` derives classification from the admitted job, never from an HTTP browsing context. Re-registering a known output must not silently change its classification. Duplicate job IDs across regular/private run roots are a recovery error; corrupt private records stay private rather than falling back to regular.

## Workspace/service signatures

All scopes below default to regular and validate strictly:

```python
get(asset_id, privacy='regular')
file(asset_id, privacy='regular')
file_entry(asset_id, privacy='regular')
snapshot(privacy='regular')
snapshot_file(source, privacy='regular')       # creation: regular/private only
storage_root(privacy='regular')               # regular workspace or experiments/private
metadata(asset_id, expected_workspace_id=None, privacy='regular')
command_status(request_id, expected_workspace_id=None, privacy='regular')
update(payload, privacy='regular')
collection(payload, privacy='regular')
collection_page(*, workspace_id=None, limit=50, cursor=None, privacy='regular')
collection_status(request_id, expected_workspace_id, privacy='regular')
asset_by_sha256(digest, privacy='regular')
asset_selection(ids, *, workspace_id, details=False, privacy='regular')
asset_page(..., filters={'privacy': 'regular|private|all'})
```

Explicit `privacy='all'` permits privileged internal reads only where the caller has already established scope. Private creation may read regular source assets; use an explicit source scope of all only after private creation was requested, and preserve the source's classification. A regular request must never silently consume private inputs. Parent IDs and upload filenames must be checked server-side even when the caller omits classification or bypasses the browser.

Keep the existing small metadata editor/conflict envelope unchanged where possible. Full assets and bounded summaries carry a privacy label for All views; regular omission can be interpreted as regular for legacy compatibility. The strict SDK validator must accept the actual emitted shape and reject a private response to a regular query.

## Read and mutation boundaries

Filtering occurs in SQL before search, ordering, pagination, count computation or projection. Bind privacy into cursor identity; scope changes invalidate pagination. `AssetReads.selection` treats out-of-scope IDs as missing. Collection listing/counts and memberships use the same scope. Refuse mixed-privacy collection membership; a private picture must not expose a private collection name through a regular asset row.

Guard these direct routes, including derivatives and error/conflict responses:

- Jobs: list, ID, recipe, image, i2v diagnostic and diagnostic file.
- Assets: metadata, file, thumb, context, selection, family, recall, reference attachment, export and command status.
- Uploads and export package URLs.
- Collections: listing, counts, create/rename/delete, command recovery and conflict current values.

Family traversal filters every visited node and descendant scan. It must not reveal hidden IDs in edge lists, missing-node titles, gaps, scan counts or recipes. Recall must verify the owning job scope as well as the asset scope. Regular asset parents used by a private run remain regular; descendants of private inputs cannot become regular by omitting a request flag.

Advanced leak surfaces currently include `SetupDrafts`, `SetupHistory`, `WorkflowDocuments`, `DocumentRuns`, PromptProjects, ReferenceJobs, looks/characters, Production, AV/voice/native, tiles and parallax. Private creates and private-source derivatives on unsupported paths fail clearly before the side effect. Existing ordinary defaults remain usable. Bare `assets.get/file` defaulting to regular helps enforce this boundary, but raw SQL and direct `studio.jobs` lookups still require explicit review.

## Browser hooks and concurrency

Implemented shared `window.StudioPrivacy`: `creation()`, `scope()`, `capture()`, `storageKey(base, privacy=creation())`, `storage(privacy)`, `headers(captured, supplied)`, `fetch(path, options)`, `mediaUrl(path, record)` and `submitted(captured)`. Capture carries `{privacy, scope, revision}`. `studio:privacy-change` carries `{creation, scope, previousCreation, previousScope, reason}`. An acknowledgment cannot reset a newer choice. The regular-to-private draft move removes only an exact owned saved copy; a newer competing-tab copy is retained.

Freeze creation classification and upload target before any await. Do not let a mode toggle during file upload silently queue a public job. A scope change clears jobs ETags, Library page/cursor/selection/resolved records, thumbnail DOM, source picker snapshots and recovery UI before fetching. Discard late async results using a scope epoch. Regular recovery panels must not enumerate private journal entries.

## Existing item conversion

Do not implement privacy as a bulk edit of only an asset label. The owning regular job would still disclose the private prompt/output through history. A coherent conversion previews and moves the entire owning run, all sibling outputs and associated retained evidence. Shared regular parents are not moved merely because a private child references them.

The reusable safety owner is `AssetWorkspace.update`: workspace identity, expected metadata revisions, BEGIN IMMEDIATE, retained request ID and exact replay receipt. Files use existing content-addressed `snapshot_file`/`_verify_snapshot`; `Studio._job_directory` is the central run resolver. A future conversion command needs a durable prepare/apply journal and fail-closed intermediate classification. Verify destination copies and publish paths before deleting old app-owned files; never delete a shared blob while another row refers to it. Hold Studio lifecycle coordination during commit and refuse unsettled/unknown submissions rather than racing the worker. Do not present conversion as implemented until crash/Windows publication failure and restart cases pass.

## Test matrix

Use distinct synthetic PNGs and recognizable harmless canary text, never live private media.

| Seam | Required proof | Existing focused suites |
| --- | --- | --- |
| Migration | old DB remains regular; simultaneous initialization; invalid stored privacy fails closed | `test_workspace`, `test_workspace_snapshot_durability`, `test_workspace_snapshot_reuse` |
| Admission/storage | private tag saved before enqueue; roots separated; restart preserves privacy/prompt IDs; duplicate/corrupt private records never public | `test_server`, `test_job_record_integrity`, `test_jobs_etag` |
| Reads/search | regular/private/all exact sets; private search term gives zero ordinary matches; counts scoped; hidden selection ID reads missing | `test_asset_reads`, `test_asset_read_client`, `test_asset_metadata_http`, `test_asset_workspace_scope` |
| Media | known private file/thumb/upload/image/recipe/export blocked by default; explicit scope works; no-store for private media | `test_server`, `test_asset_thumbs`, new privacy HTTP tests |
| Derived content | private parent/upload with absent/regular flag refused; explicit private generation accepts regular refs; unsupported paths refuse before side effects | `test_continuation`, `test_workflow_execution`, `test_production`, new privacy inheritance tests |
| Mutation/recovery | hidden metadata conflict and receipt do not leak; scoped idempotent replay; mixed collection scope refused atomically | `test_asset_metadata_commands`, `test_asset_conflict_envelope`, collection command suites |
| Family/recall | no hidden ancestor/child identifiers, titles or prompts; no implicit downgrade | `test_asset_family`, `test_asset_family_client` |
| Browser | private session/draft reload behavior, private-to-regular clear, slow upload/poll scope race, Make regular draft restoration, no private regular-localStorage writes | Make reload regression, new privacy browser/Node contracts |
| MCP/SDK | defaults regular; explicit private/all only; response scope validation; private direct job/recipe sources blocked by default | `test_workflow_asset_mcp`, `test_workflow_mcp_shapes`, `test_asset_read_client` |

After integration run `python -m unittest discover -s tests` and `python scripts/validate-repo.py`; browser flows should make zero generation submissions.

## Ownership

- Root: `app/server.py`, `app/creation_privacy.py`, `app/static/privacy.js`, app.js/workspace.js/index/CSS, central upload/production gating and integration.
- Privacy backend agent: `app/workspace.py`; asset reads, read HTTP, clients, family, collection protocol and MCP asset integration; focused tests.
- Workflow QA agent: Make unsent draft persistence and Make privacy hook integration; isolated regression tests.

Open owner art-acceptance, licensing and MOSS Make-look choices in HUMAN_TODO remain unchanged.

# Shared Scene editor

Open **Scene editor** from the Studio header or **Create scene** from selected Workspace assets.
Choose registered PNG/MP4 visuals and optional 48 kHz, 16-bit PCM WAV audio. Creation snapshots their
bytes and SHA-256 hashes, preserves their Workspace asset IDs, and starts no render or model job.
The first slice has cuts, dissolves, static overlays, audio trim/gain/fades/mute/bus, shot ordering and
shot/audio splits. Sources are served by local range-capable URLs rather than embedded in the page.

Use **Add from Workspace** in Shots, Audio or Static overlays to bring a later asset into the open
scene. **Replace source** on a clip keeps its timing, placement and audio settings when the selected
source fits; an incompatible kind or a short source is refused without shortening the clip. The chooser
searches one bounded page at a time. Save or discard unsaved clip fields before changing sources.
The source and clip operation save together as one new revision; they never start a render.

Every selection carries the exact Workspace, asset ID, hash and metadata revision. The scene copies
the selected bytes into a new input file and keeps historical inputs, including after a restore.
Unavailable, private, linked or changed sources are refused. Retained inputs count toward the
64-source, 512 MiB-per-source and 1 GiB-total limits; repeated replacements cannot evade them.
Continue verifies later sources against their intake events while preserving the original plan.
After an error or an unconfirmed reply, the chooser keeps its selection and disables submission:
close it and reload the scene before deciding what to do. It never retries a mutation automatically.

Use **Save changes** on a clip, then **Render scene**. While one or more clip fields are unsaved, the
editor labels the preview as a saved revision and blocks render, export, restore, add, move, split and
remove. The unsaved notice and disabled actions update immediately while typing, retaining keyboard
focus and the current preview video. Save each draft or use **Discard unsaved changes** to clear only the local fields; it makes no
request and never applies or discards a server revision. Saving one clip advances the remaining local
drafts to that saved revision, so they remain individually saveable; an external change still returns a
conflict. Reload after a conflict to compare the current server revision with retained fields before
saving. History restore creates a new revision and preserves the intervening history. Browser, CLI and
MCP all use the same expected-revision command API and database. Actor labels are provenance supplied by
the client, not authentication or a creative approval.

While a command or manual reload is pending, clip fields and document actions are disabled, including
export, cancel, scene switching and new-scene creation. Polling cannot overwrite a newer command
response. Render completion updates the global status and artifact links show their filenames.
An earlier polling error currently stays in the global status until a manual action; the render panel
still updates after successful polling. This display issue remains tracked in #30.

## CLI and MCP

Run from the repository with its Python dependencies. Keep Studio running normally on loopback 8191.

```powershell
python -m studio_av studio --url http://127.0.0.1:8191 list
python -m studio_av studio --url http://127.0.0.1:8191 workspace
python -m studio_av studio --url http://127.0.0.1:8191 inspect SCENE_ID
python -m studio_av studio --url http://127.0.0.1:8191 create create.json
python -m studio_av studio --url http://127.0.0.1:8191 command SCENE_ID edit.json
python scripts/studio_av_mcp.py --studio http://127.0.0.1:8191
```

Example create file: `{"name":"Opening","asset_ids":["WORKSPACE_ASSET_ID"]}`.
Example edit file:

```json
{"action":"edit","expected_revision":0,"section":"shots","clip_id":"shot0","changes":{"frames":48}}
```

Inspect the scene for its actual clip IDs and current revision. The client makes one direct HTTP
request with no redirects, proxy or retries. A lost response is uncertain: inspect/list before
deciding what to do; never blindly repeat create, edit or render.

For a later source, send `add_source` with `section`, or `replace_source` with `section` and `clip_id`.
Both require `expected_revision`, `workspace_id`, `asset_id`, `sha256` and `metadata_revision` from the
current scene and selected Workspace record. These commands also use MCP's existing `edit_scene`
tool only when `--allow-edit` is present. They do not grant render access.

The optional MCP SDK remains pinned by the existing AV requirements. Studio mode defaults to
list/inspect/source inventory/propose. `--allow-edit` adds persisted create/edit/restore/export;
`--allow-render` separately adds explicit render/cancel. The older `--workspace PATH` offline adapter
and `scripts/studio_av.py` commands remain available; they do not edit persisted Studio scenes.

## Runtime and recovery

Set absolute `ffmpeg` and `ffprobe` executable paths in ignored `config/local.json`. The Studio route
uses these paths, without a global PATH change. The offline CLI continues to use its caller's PATH.
No synthesis, ComfyUI restart, new GPU worker, codec download or transcoding happens on page load.

`experiments/projects/projects.sqlite3` holds current documents, append-only revision events,
immutable render requests and published export records. Render requests enter the existing Studio
worker queue. Each attempt owns its new `renders/ATTEMPT_ID` directory with source snapshots, plan,
logs, output and receipt. Completed video/PCM output enters Workspace with source lineage and the
full scene recipe. Before Workspace indexing, the full native request and receipt are durably recorded
as a publishing attempt; publication failures retain the recipe, diagnostics and any registered assets.
On restart, new AV publication records are indexed only when marked published; failed or incomplete
attempts retain their exact Workspace asset set and diagnostics for inspection. Legacy AV jobs without
a publication marker keep their historical recovery behavior.
Previous previews remain available and are labelled stale after later edits.

Cancel targets a named active attempt. Owned FFmpeg children are terminated and joined; files and logs
remain. Cancellation during the final publication interval can lose to completion (tracked in #30).
A restarted Studio marks active attempts interrupted, queues nothing, and requires explicit action.
Inspect retained attempt files before requesting another render. An interrupted output is not an
accepted result. Incomplete intake folders and losing concurrent export ZIPs may remain unregistered;
they are not silently deleted or treated as published artifacts.

Caps are 120 seconds, 16 shots, 32 audio clips, 16 overlays, 1 GiB of source media and 500 revisions.
Intake/export need source space plus 2 GiB free; rendering also budgets its snapshot. FFmpeg phases
each have a 180-second deadline, 8 MiB logs and 1 GiB top-level output cap. This is a per-process bound,
not a 180-second end-to-end promise; each media probe has a 20-second timeout. Existing file snapshots
are rehashed before edits, source access, render and export. Video trims beyond EOF and audio trims
beyond decoded sample bounds are rejected. Timing uses exact rational, ties-to-even sample rounding.

## Evidence and remaining work

The source-revision regressions in `tests/test_av_source_revisions.py` exercise real disposable
Workspace/scene stores and HTTP/CAS, with media-probe doubles for the short-input edge cases.
`tests/scene_source_revisions_browser.py --out PATH` is the separate synthetic production-route
journey: later PNG/MP4/WAV sources, restore, conflict/lost reply, wide/narrow and native 200% zoom,
then an explicitly requested CPU render and return to the brief. It requires installed Chromium,
FFmpeg and FFprobe plus an allocated proving window. The render oracle is 47 decoded video frames
and 94,000 PCM samples. This does not establish model quality or owner acceptance.

12 September Windows proof used real Chromium 151 and FFmpeg 9.0.1: create without rendering, focused
keyboard input, UI/CLI stale-write rejection, explicit reload, clip split, overlay, queued six-second
render, decoded playback, source ZIP download, CLI inspection, actual stdio MCP proposal/edit/conflict,
UI reload and 390 px layout. No browser JS errors, external browser requests or ComfyUI calls occurred.
Synthetic sources, receipts, screenshots, plans and exports survive in
`.runtime/session-2026-09-12/shared-scenes/` after coordinator closeout.

#30 stays open for cached thumbnails/waveforms, proxy/range renders and targeted cache invalidation,
cancellation/publication arbitration and concurrent-export orphan accounting. This preview editor does
not claim NLE/DAW parity, lossy native editor round trips, voice/music inference or perceptual acceptance.
`HUMAN_TODO.md` retains the owner's optional creative choices; runtime success does not approve art or
model terms.

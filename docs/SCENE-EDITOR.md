# Shared Scene editor

Open **Scene editor** from the Studio header or **Create scene** from selected Workspace assets.
Choose registered PNG/MP4 visuals and optional 48 kHz, 16-bit PCM WAV audio. Creation snapshots their
bytes and SHA-256 hashes, preserves their Workspace asset IDs, and starts no render or model job.
The first slice has cuts, dissolves, static overlays, audio trim/gain/fades/mute/bus, shot ordering and
shot/audio splits. Sources are served by local range-capable URLs rather than embedded in the page.

Use **Save changes** on a clip, then **Render scene**. Rendering and companion export use the saved
revision; unsaved fields are not included. Reload after a conflict to compare the current server
revision with retained fields before saving. History restore creates a new revision and preserves the
intervening history. Browser, CLI and MCP all use the same expected-revision command API and database.
Actor labels are provenance supplied by the client, not authentication or a creative approval.

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
On restart, only completed AV publication is indexed; failed or incomplete attempts retain their exact
Workspace asset set and diagnostics for inspection.
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

12 September Windows proof used real Chromium 151 and FFmpeg 9.0.1: create without rendering, focused
keyboard input, UI/CLI stale-write rejection, explicit reload, clip split, overlay, queued six-second
render, decoded playback, source ZIP download, CLI inspection, actual stdio MCP proposal/edit/conflict,
UI reload and 390 px layout. No browser JS errors, external browser requests or ComfyUI calls occurred.
Synthetic sources, receipts, screenshots, plans and exports survive in
`.runtime/session-2026-09-12/shared-scenes/` after coordinator closeout.

#30 stays open for cached thumbnails/waveforms, proxy/range renders and targeted cache invalidation,
clearer unsaved-field handling for document actions, cancellation/publication arbitration and
concurrent-export orphan accounting. This preview editor does not claim NLE/DAW parity, lossy native
editor round trips, voice/music inference or perceptual acceptance. `HUMAN_TODO.md` retains the owner's
optional creative choices; runtime success does not approve art or model terms.

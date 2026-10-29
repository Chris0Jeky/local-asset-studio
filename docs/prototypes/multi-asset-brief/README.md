# Multi-asset scene brief — interactive prototype

One fictional **Lantern Marsh** scene connects a shared creative brief to six
asset slots: background, sprite, icon, video loop, sound/voice and 3D draft.
This is a standalone, synthetic interaction study. It is not a shipped Studio
route, asset inventory, queue, runtime-readiness observation or accepted pack.

## Open and edit

From the repository root, using the host's existing resource admission helper
when coordinating browser work:

```powershell
py -3 -m http.server 8471 --bind 127.0.0.1 --directory docs/prototypes/multi-asset-brief
```

Open `http://127.0.0.1:8471/`. Stop this owned static server after inspection.
Do not use the Studio launcher: the preview needs no Studio, ComfyUI, models,
native tools, packages or build step. ES modules need HTTP rather than file://.

Edit `index.html`, `style.css`, `app.mjs`, `model.mjs` and `fixtures.mjs` directly.
The palette and control language come from the shipped Atelier workshop
(`app/static/workshop.css`), with list/detail navigation adapted to a scene brief.
All thumbnails are authored schematic placeholders, not generated or imported art.

## The complete walkthrough

1. Expand **Edit the shared brief**. Change the scene name or direction; edits
   are retained as you type. Each slot also has editable wording and usability criteria.
2. In **Background**, choose **Replace candidate**. Search for “moon”, choose
   **Moonlit crossing**, then use browser Back and Forward. Slot, collection,
   search and previous selection remain contextual. **Restore previous** undoes
   the last assignment; it does not alter the Library record.
3. Open **Brass key icon → Prepare an icon concept**. Inspect the contract, then
   choose **Preview preparation** and **Use synthetic result in slot**.
   The returned fixture is selected in that slot and remains explicitly unreviewed.
4. Reload. Brief edits and references survive in the namespaced local draft.
   Prepared handoffs are intentionally re-observed after reload; no prepared
   operation is resumed and no request is replayed.
5. Open **Atmosphere loop → Compose a scene**. The request names the selected
   background and optional audio. Return a synthetic clip; the loop-seam check
   remains. A composition does not promise animated reeds or a seamless loop.
6. Explore **Keeper sprite**, **Sound / voice** and **3D lantern draft**.
   Reuse existing assets where useful. Unsupported or blocked preparation has no
   simulate/return action; it explains the prerequisite or limit.
7. Open **Remaining gaps**. Fill all six slots if desired: missing candidates
   disappear, while technical, art and rights checks remain. There is no “accept all”.
8. In any asset picker, expand **Preview empty and failed reads**. Try both
   states and their recovery controls. A failed read never clears the chosen asset.

The Library picker filters one fixed sample page; it is not a new paging
implementation. Collection discovery and asset-page envelopes follow #1680.
The default scope is Regular. There is no Private mode or live-data import here.

## Contracts and capability map

Source baseline: `3392d27bf0fa8ce5305bcc2c3a88009a33d87114` (28 October 2026).

| Slot / step | Existing owner and real shape | What the prototype demonstrates | Remaining production constraint |
| --- | --- | --- | --- |
| Collection discovery | `GET /api/collections`, `studio.collection-page/v1`; `CollectionReadClient.page` | Stable Workspace, catalogue epoch/revision, collection ID, count and terminal cursor | Reobserve scope/cursor changes through the existing owner; no silent page mixing |
| Existing selection | `GET /api/assets/page`, `studio.asset-page/v1`; `AssetReadClient.page` | `id`, `sha256`, `metadata_revision`, `media_type`, review and exact collection context | Resolve current selection and media bytes; refuse unavailable or changed identities |
| Background | `POST /api/looks/prepare`, `{id, scene, expected_revision}`; `look-night-shift-retro-anime` | Shared brief plus slot wording into a saved-look handoff; explicit synthetic return | Reobserve the look revision; actual generation belongs to the existing explicit jobs action |
| Icon | Same look preparation; `look-zimage-game-icon` | Image-concept preparation and return | Alpha, readability and fit are not guaranteed by the look |
| Sprite | Existing image presets `pixel-lora`, `pixel-concept` | Existing image selection; an honest unsupported directional-sheet route | A single image is not a consistent four-direction sheet; external authoring remains |
| Video composition | `POST /api/av`, `{action:'create', name, asset_ids, fps, size, frames_per_shot, actor}`; `AVProjects.create` | Prepare a 96-frame, 24 fps scene from selected PNG and optional WAV sources | The real call writes a plan and stages files. Source hashing, formats, FFmpeg and disk checks must run; render is separate. Loop quality remains unproven |
| Generated video | Catalog preset `h3-preview` | Blocked readiness, with the existing isolated environment named | No runtime/model/resource observation; no fabricated ready state |
| Existing audio / voice | Workspace audio records; `POST /api/voice-baseline`, `{name, speaker_id, lines:[{id,text}]}` | Existing audio replacement; missing-bundle state for the Kokoro planner | Pinned versions, FFmpeg, disk and performance checks; ambience generation is not offered by the voice route |
| 3D draft | Catalog `trellis-rgba`; existing `3d` Workspace records | Reuse a GLB fixture; missing RGBA and runtime readiness | Validate the uploaded reference and backend; inspect topology/scale/materials/import |
| Restricted 3D | Catalog `hunyuan-draft`; `CLAUDE.md` restriction | Unsupported for this UK scenario | The prototype does not reinterpret or clear the recorded restriction |

Fixtures preserve real observation fields but have fictional IDs, hashes, sizes,
timestamps and readiness. `media_bytes_verified` and `generation_submitted` are
false. No media URL is requested. The strict production readers validate the
observation envelopes in the focused contract check; this is not live integration.

## State and execution boundary

The only persistent value is `studio.prototype.multi-asset-brief.v1` in browser
localStorage. It stores creative text and fixture references, not media or an
asset database. It never reads production recovery keys. A storage error keeps
edits in memory with a visible download escape hatch. An invalid saved draft is
preserved until explicit demo reset. Another-tab changes stop writes from this
tab to avoid overwriting its newer stored draft. Download is a reviewable JSON
copy, not a Studio import format. Reset requires confirmation and affects only
this demo key.

Routes are allow-listed hash navigation. The script has no fetch, XHR, websocket,
beacon or runtime code. CSP sets `connect-src 'none'` and `form-action 'none'`.
The static server has no Studio API or generation handler. Preparing and returning
are explicit in-memory fixture actions. Returning verifies the captured wording,
requirements and source selection; editing them requires a new preview.

## Smallest production integration seam

Keep this preview separate until the journey is chosen. The next implementation
slice would retain a collection ID and lightweight brief/slot references beside
the existing collection context, using the existing discovery/selection owner
and recovery shelf. It would route one image slot to the current look preparation
owner and correlate the returned existing asset identity with that exact slot.
No second job queue, Library store, generic executor or acceptance authority is
needed. Before adding other media, expose required inputs and readiness through
the common capability handoff described in `docs/UX-WORKFLOWS.md`.

Re-read privacy scope, Workspace/catalogue identity, asset hash/revision, look
revision and runtime readiness at the real boundary. Do not promote the fixture
readiness labels, simple localStorage draft or synthetic return IDs into those
contracts. Real private/shared lifecycle, external-tool returns, uncertainty,
concurrent edits and output registration need their own proving checks.

Refs #313 and #772: owner-accepted assets and real measured Studio journeys remain
open. `HUMAN_TODO.md` keeps q-7 UX judgment, art/look choices, licensing, asset
intake and parallax acceptance; this preview settles none of them.

## Focused checks

```powershell
node docs/prototypes/multi-asset-brief/check.mjs
py -3 docs/prototypes/multi-asset-brief/check_contracts.py
node --check docs/prototypes/multi-asset-brief/app.mjs
py -3 scripts/validate-repo.py
```

See [VERIFICATION.md](VERIFICATION.md) for the actual browser proof and limits.
Production app/catalog files are unchanged. No full app integration, live
generation, native export, model licensing or owner art acceptance is claimed.

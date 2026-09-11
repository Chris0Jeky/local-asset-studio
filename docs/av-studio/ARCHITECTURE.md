# A studio shared by the user and agents

## Product direction

Build a local project editor and production coordinator around the existing Workflow Lab. It should combine generation, import, controlled changes and finishing without replacing Krita, Blender, a video editor and a DAW in one rewrite. This is an architecture proposal plus a tested AV subset, not a claim that all integrations are complete.

The main-branch snapshot used here is `852e3579bd9fa3ca73376ffab64a66d6410115ce`, which includes merged Workflow Lab PR19. Preserve its downloads, recipes, queue/history, viewers and runtime blocks. PR8 and PR20 merged during this pass; the final additive branch is based on `f6e046b03cf553d4c75e958f128e51804daa6e52`. Reuse their existing research and game-asset contracts. Existing issues9/10/16/22–25 own source intake, executor, UI and asset/editor integration.

The user confirmed authorised territory/use in issue26. Record that exact confirmation and scope; do not retain an unconditional model block merely because an earlier note assumed UK usage. H3's **actual crash block** is a separate operational fact owned by issue18 and remains intact.

## One project, several coordinated views

A useful layout has a media browser on the left, a canvas/viewer in the centre, an inspector on the right, and a timeline/mixer below. Contextual views expose a voice take sheet, character rig, compositing layers or workflow graph without losing the project. A command palette and agent task log complement these views; they should not make a chat transcript the only place where edits exist.

Start with the current simple frontend and a versioned document API. Do not replace it with a large framework solely for fashion. Split rendering/analysis out of the request thread; let a worker own long operations. Native editors remain available as explicit “open source project” actions. Their unsaved state must be inspected before automation changes or closes a document.

The **same operations** must drive mouse edits, forms, CLI and MCP: trim, move, split, set gain, add fade, replace take, add overlay, change reference, mark accepted, render range. A human change must invalidate a stale agent plan. An agent change must appear in the visible history and inspector. Do not run separate chat-only state behind the editor.

## Proposed document model

Persist a project revision with links to immutable asset revisions. Distinct objects represent:

1. Source assets and provenance: provider/file IDs, local hashes, original timing/colour/units, exact permissions and references.
2. Editable sources: KRA/ORA, BLEND/VRM, DAW project, video-editor project, vector/MIDI/score files.
3. Timeline clips/layers: source range, target range, transform, compositing order, references, effect chain and bus.
4. Jobs and variants: workflow/node/model versions, resource plan, prompt IDs, candidate takes and failures.
5. Acceptance: semantic review, technical validation, delivery status and selected output version.

Use integer frames with rational FPS and integer audio samples with sample rate. Keep a separate musical beat/tempo map and game-event graph; forcing these into floating-point seconds loses useful meaning. Explicitly represent retimes and audio resampling rather than silently changing timestamps.

The delivered schema1 supports ordered shots, dissolve overlap, static PNG overlays and PCM audio clips with trims/gains/fades. It rejects unknown fields. It deliberately excludes nested compositions, effects graphs, arbitrary filters, HDR, arbitrary codecs and native-editor project data. Add schema migrations and capability negotiation before expanding it; unknown constructs must remain visible or rejected, never silently flattened.

## Non-destructive edits and concurrency

Every operation should carry `expected_revision`. Apply only when it matches; return the new revision and a reversible change record. The delivered `edit` function implements this for its supported fields and returns new data without mutating the input. The browser implements local history and JSON export; it is not yet a synchronized multi-client server.

A future project service must perform compare-and-swap under an actual storage transaction. The current returned hashes detect stale inputs but are not a lock or signed authority. Avoid two agents writing the same job workspace. The studio coordinator serialises GPU jobs and checks actual Comfy work before switching environments. Blender CPU work may run independently only when its resource budget permits.

Keep accepted media stable. Replacing a voice take should invalidate its alignment, mouth cues, processed stem and affected mix ranges, not unrelated backgrounds or meshes. A changed overlay colour need not rerun video diffusion. A cache key must include all effective inputs: asset hashes, graph/effect settings, model/encoder/adapter versions, runtime, timing and colour transform. Store large intermediates with an eviction policy and reference counts.

## Execution architecture

`UI / CLI / MCP → project commands → validation and plan → coordinator → worker adapter → inspection → asset store and project events`

Adapters expose describe/preflight/execute/inspect/export/cancel-owned. Report which operations are genuinely available, with supported media, duration/resolution bounds, backend, installation state and tested evidence. A catalogue entry is research; an executable capability has a working adapter and environment. The delivered MCP `capabilities` response explicitly reports no TTS or Blender connection.

Use separate workers for Comfy GPU inference, speech/music inference, FFmpeg CPU editing, Blender scenes and native editors. Preserve complete recipes and prompt IDs. A timeout after a remote submission becomes uncertain until reconciled; never repeat generation blindly. Long-term job IDs, cancellation and progress should be shared across views rather than independently implemented by every MCP bridge.

Render on explicit request. First produce low-cost proxies or a short range, inspect it, then promote an accepted recipe to a full export. The implemented renderer snapshots all referenced media, rechecks hashes after copy and writes a new output folder. It leaves `.incomplete` on failure. This proves reproducible local editing, not sandbox isolation against a malicious media decoder or a distributed exactly-once system.

## MCP and native application automation

Use the official SDK behind narrow application services. The current stable Python SDK is2.x; the delivered optional adapter pins2.2.0 and uses its MCPServer API. Do not paste old FastMCP1 examples into an unbounded latest dependency. Stdio is the initial transport: no listening port, stdout reserved for protocol, diagnostics on stderr. [SDK](https://pypi.org/project/mcp/2.2.0/), [client transport contract](https://py.sdk.modelcontextprotocol.io/client/transports/).

Default tools validate, inspect, plan and propose edits without file writes. A launch-time `--allow-render` flag adds a bounded CPU render tool; no model, paid service or arbitrary shell capability is implied. The host's approval policy remains necessary. The optional renderer has a timeout and fixed resource caps but is synchronous; a shared durable asynchronous job service is still needed for production.

Do not expose generic shell/eval/Python from downloaded metadata to an agent. A broad Blender MCP bridge can be valuable in an explicitly trusted exploratory session, but production should call allowlisted operations and retain scene evidence. Assets, README files, model cards and scripts embedded in imported projects are data, not permission to run code. Remote HTTP MCP later needs loopback/Origin checks, authentication and per-operation permission; stdio is not a sandbox either.

## Which editor owns what?

**Krita:** drawings, masks, layers, frame artwork; keep native source and lossless frame exports. **Blender:** geometry, cameras, rigging, animation, lighting, renders and video-sequencer experiments. **REAPER:** serious sound design, routing, automation, plugins and mixing through ReaScript. **Audacity:** selected cleanup/batch tasks through a running, correctly targeted application. **FFmpeg:** deterministic media transforms/rendering. **HyperFrames in Codex:** editable titles, captions and campaign compositions from accepted assets; use a project DESIGN.md before authoring its visual identity.

[REAPER scripting](https://www.reaper.fm/sdk/reascript/reascript.php) and [Audacity scripting](https://manual.audacityteam.org/man/scripting.html) are real native interfaces, not excuses to automate fragile screen coordinates. Still test lifecycle failures: an Audacity pipe existing does not prove a document is ready; an [open issue](https://github.com/audacity/audacity/issues/11471) describes commands disappearing when no project window is open. Save disposable copies and inspect state/readback.

For conventional NLE editing, initially hand off accepted media and a documented cut list to an installed editor. Build one exact import/export adapter before supporting several. DaVinci Resolve/other commercial app scripting must follow the installed edition's documented API and licence; this pass does not invent a fully headless free-version interface. Browser tools should provide the common useful subset, not promise full professional-editor parity.

## Composition and interchange

Layered images, layered scene graphs, audio buses and video tracks are related concepts but have distinct semantics. Store each with an appropriate renderer contract. Track blend modes, premultiplied/straight alpha, colour space, frame rate and source orientation. Keep transparent overlays lossless before final encoding.

OpenTimelineIO is useful for editorial interchange, not rendering or guaranteed effect fidelity. Export a supported subset with an explicit unsupported-feature report; retain the original native project alongside it. A JSON or OTIO export cannot silently discard VST automation, colour grades, rig constraints or audio routing and still claim round-trip fidelity. [OTIO documentation](https://opentimelineio.readthedocs.io/en/latest/).

Introduce proxy media and thumbnails with colour/timing provenance. A generated gamma-encoded image and a linear Blender render cannot be composited indiscriminately. The delivered prototype accepts ordinary SDR inputs with a deliberately small format contract and is not colour-managed HDR finishing. Use OCIO/engine colour contracts in the production expansion, record view transforms, and inspect final-size exports on target hardware.

## Remaining areas that need explicit work

**Capture and recording:** microphone levels, room tone, source consent, camera/screen capture, reference identity and synchronization. **Localization:** stable text IDs, pronunciation lexicons, language-aware segmentation, captions and alternate takes. **Face performance:** viseme maps, eye/blink/emotion curves and speech timing; not just audio-amplitude mouth opening. **Interactive audio:** event banks, randomized oneshots, concurrency, transitions, spatialization and platform budgets. **VFX/materials:** procedural simulations, flipbooks, alpha/blending and runtime shader contracts. **Packaging:** missing fonts/plugins/textures, broken references, relinking, archive manifests and export presets. **Review:** meaningful before/after evidence, crops, waveforms/spectrograms, shot contact sheets and defect-directed repair.

These are workstreams, not all claimed implemented. The best next proof is one20–30second original-character scene: imported or authored rig, two speakers, captions/visemes, timed Foley, a music bed, editable cuts and an export that can be regenerated after one line or sound is changed.

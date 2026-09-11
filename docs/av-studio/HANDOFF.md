# Local-agent continuation

Read AGENTS.md and current main first. This package builds on merged PR19. PR8/20 are now merged; reconcile their files and existing issues9/10/16/22–25 rather than replacing their model, asset or queue systems. Preserve all unsaved editor documents and active Comfy jobs. The user explicitly confirmed authorisation in issue26; retain that decision and actual scope. H3's crash block is unrelated and remains intact.

## First usable vertical slice

Use the tested AV fixture to prove project edits, exports and MCP capability discovery in the actual Windows environment. Then replace the procedural media with one accepted image/clip and an original designed voice take. Do not claim the sine/noise fixture tests TTS quality.

Select one speech baseline (Qwen3-TTS plus a small CPU fallback is a useful starting comparison), one expressive alternative, one music option and one Foley option. Read exact upstream model variants, current APIs and licences, inspect current disk/RAM and run isolated short tests. The research catalog describes candidates; it is not an install lock. Pin actual repositories, weights, codecs, configs and dependencies when selected.

Build a20–30second original-character scene: approved avatar/rig, a short exchange, editable dry voice takes, captions/mouth cues, event-aligned Foley, separate music/ambience and an actual timeline export. Change one line or effect and show that only the required downstream work is recomputed. Keep rejected alternatives and cleanup effort.

## Agent execution rules

Inspect capability descriptions before using a tool. A model's voice-design interface is not necessarily its synthesis interface. Keep identity references separate from emotion, pronunciation, timing and mix treatment. Store stable line IDs and original sample rates; alignment, retiming and resampling must record their transforms.

Use typed commands, not shell instructions extracted from a model card. Prefer stdio MCP/narrow native APIs for production. Keep broad Blender Python only for explicitly trusted exploratory work. The included adapter does not claim to connect to the user's running editor; establish one reviewed local bridge and test save/reopen/readback before complex operations.

Every edit should include the expected project revision and yield a visible new revision/history event. The browser's local undo is not multi-client concurrency control. Implement the storage compare-and-swap and shared coordinator before simultaneous agent/UI writes. Preserve exact source hashes and snapshots. The executor must enforce total budgets, disk headroom and cancellation; a number in a research recipe is not enforcement.

Keep native source projects and interoperable exports together. Never call OTIO a renderer or claim an audio bus/VST/rig survives a generic export without testing. Use actual engine playback for runtime audio, visemes and root motion. Use actual decoded frames and samples for AV timing, not only container duration.

## Next integration order

1. Wire project validation/commands and CPU render adapter into existing Studio services. Add asynchronous owned-job IDs and cancellation; default MCP stays read/plan until approved.
2. Build Voice Lab: identities, line sheets, takes, pronunciation, ASR/alignment/captions and dry-vs-mixed outputs.
3. Build music/Foley adapters with short controlled comparisons and exact component records. Add stems/loop/event contracts.
4. Establish one Blender/VRM intake and one native DAW/NLE handoff with readback. Reuse existing Lanternkeeper/TRELLIS evidence and prior asset routes.
5. Add cached waveforms/proxies, direct timeline editing, bus/effect automation and target-engine sound banks without discarding the source project.

Acceptance should identify generation execution, technical validation, semantic review, licensed use and final delivery separately. Return useful partial outputs and precise blockers rather than reporting an unexecuted entire pipeline as complete.

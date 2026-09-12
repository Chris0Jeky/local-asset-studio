# Native engine evidence: sprite playback and GLB gates

Implementation slice for **#15 / #24**. It extends the existing Godot adapter used
by Studio native exports and the offline CLI. No additional executor, server,
GPU coordinator or game engine is introduced. #3/#22 can use it for their later
accepted character-pack experiments; this pass does not complete those studies.

## Evidence correction

The previous verifier populated `duration_ms` and `total_duration_ms` by reading
SpriteFrames resources, printed its report from `_ready`, and immediately quit.
It established imported timing values, **not an observed completed cycle**.
Historical reports are retained and must not be relabelled as new measurements.

The v2 verifier starts an AnimatedSprite2D at speed 1, collects `frame_changed`
events, and waits for `animation_looped` (loop) or `animation_finished` (one-shot).
The test runtime uses `--fixed-fps 240`. Reported elapsed times accumulate Godot
process delta; they are simulation time, not wall-clock latency or performance.
The Python verifier checks the entire ordered frame sequence, each expected
boundary and the final duration with at most two fixed-step rounding tolerance
(8.344 ms). For 120/80/120/160 ms frames the target remains exactly 480 ms.

## Architecture and integration

| File | Boundary |
|---|---|
| `scripts/godot_asset_adapter.py` | Existing package/preflight/execute/inspect/export API and CLI; exclusive attempt directories |
| `scripts/godot_probe.gd` | Authored Godot resource inspection, real sprite signals, GLB scene inventory and AnimationPlayer pose sampling |
| `scripts/engine_validation.py` | Bounded JSON/GLB intake, source alpha reference, pinned validator bridge, bounded child process/logs |
| `tools/gltf-validation/` | Explicit isolated npm tool installation; no frontend build/runtime dependency |
| `tests/engine_fixture.py` | Reproducible original QA atlas and animated/skinned GLBs; no external assets/models |
| `tests/test_engine_live.py` | Opt-in actual Godot + Khronos checks, no mocked native tool |

`Production._run_native` already calls `godot_asset_adapter.execute`. Its existing
verify-engine checkbox therefore uses the improved verifier automatically.
No page-load action executes it. Node is resolved only from the explicit CLI
argument or the existing repository's `config/local.json` `node` field; production
never searches PATH. Preserve your other config fields. The Godot path remains
the existing configured executable. No working Torch/ROCm package is touched.

This deliberately strengthens GLB engine verification: it now refuses a missing
Node/pinned-validator setup instead of quietly skipping the format gate. Atlas/ORA
packaging, sprite-only Godot verification and image generation are unaffected.
The old adapter entry points remain available. `describe()` no longer advertises
a working asynchronous cancellation API; `cancel_owned()` explicitly reports that
it is unsupported. Synchronous timeout handling stops only the child it created.

## Gate sequence

1. Validate the root-confined atlas manifest. Create a previously nonexistent
   project directory; copy sources and compare their hashes. Escape clip names
   as scene string literals rather than interpolating them as scene syntax.
2. Persist `package.json`, the resolved manifest and `execution-intent.json`.
   Packaging by itself is **not** engine or format verification.
3. Decode the PNG once in Python, checking bounds and each frame's alpha count
   and bounding box. Transparent frames are allowed when the original is blank;
   repeated/hold frames remain distinct timed entries. Engine values must agree.
4. For an optional GLB, require a bounded self-contained GLB v2. Run the official
   pinned Khronos validator. Keep its complete diagnostic report and source hash;
   errors or a truncated report stop the operation before Godot import. Warnings
   remain visible and are not silently promoted to artistic acceptance.
5. Preflight the selected Godot executable, import the exclusive project using
   `--import`, then run the authored probe. No imported editor project, plugin,
   shell command, script or arbitrary resource resolver is enabled.
6. Require real sprite completion/transition evidence. For GLB, inventory nodes,
   rest transforms, meshes, materials, skins, skeleton/bone names and animations;
   evaluate each imported non-RESET clip at start/mid/end in AnimationPlayer.
   These are named **pose samples**, not real-time/full-clip motion acceptance.
7. Check source snapshots again. Publish `execution.json` only after verification,
   with hashes of evidence files. `inspect`/`export` refuse missing, changed or
   failed evidence. A loose `engine-report.json` does not certify an export.

Native exports reuse the existing Studio packaging. Failure logs are retained in
the attempt directory even when engine execution fails; the existing Production
UI may not publish them for download after a failed native stage. This does not
claim to solve that separate diagnostics-UI backlog. Recovery is explicit: inspect
the retained attempt, correct the cause and choose a fresh output directory.
Neither a missing report nor a crash authorizes a blind rerun in the same folder.

## Limits and threat model

The GLB intake supports JSON plus an optional BIN chunk, embedded buffers/images
only: all URI fields (including data URIs) are refused. Limits are 128 MiB GLB,
4 MiB JSON, 2048 source nodes, 512 materials, 128 skins and 32 animations. This is
a conservative supported subset, not a claim that other valid glTF forms are bad.
The header/intake parser does not replace Khronos semantic validation.

PNG decode is limited to 40 megapixels, aggregate frame alpha inspection to
80 megapixels, at most 512 frames, a 30-second simulation cycle and an explicit
1–600 second execution budget (120 seconds by default). Children have a 4 MiB
per-stream observation limit and are stopped on timeout/log overflow; polling can
allow a small log-write overshoot. Logs and exit receipts survive failed checks.
Native decoders are not a sandbox against hostile binaries. Use trusted installed
executables and reviewed asset sources. Inputs are metadata, never instructions.

Output-directory exclusivity and hashes protect cooperative workflows, not a
privileged local attacker able to forge receipts or swap filesystem components.
Hash receipts are evidence integrity, not reviewer authentication or rights.
Headless inspection is not a colour-managed screenshot or final-scale art review.
Source coordinate/material declarations and imported values are preserved
separately; tests check an authored fixture's known transforms/material factors.
General rig stress, contacts, collision and root-motion contracts remain open.

## Reproduction

Offline checks, in an isolated development environment:

```console
python -m pip install -r research/game-assets/requirements-media.txt
python -m unittest discover -s tests -p test_engine_evidence.py -v
python -m unittest discover -s tests -p test_godot_asset_adapter.py -v
```

Install the format tool explicitly:

```console
npm ci --prefix tools/gltf-validation --ignore-scripts --no-audit --no-fund
```

For actual local native tests, set absolute paths in `STUDIO_TEST_GODOT` and
`STUDIO_TEST_NODE`, then run `test_engine_live.py` through unittest discovery.
Set `STUDIO_ENGINE_EVIDENCE` to a fresh writable directory to retain all reports
and failed attempts. Without tool variables those five tests explicitly skip;
`STUDIO_REQUIRE_ENGINE_TESTS=1` makes missing variables a failure instead.

The path-filtered `Native engine evidence` CI lane provisions checksum-pinned
**Godot 4.5 stable** on Ubuntu and Windows test runners only, and uses the exact
Khronos npm **2.0.0-dev.3.10** dependency. Godot 4.5 is a fixed compatibility
baseline, not a claim to be the latest release or the user's installed version.
It executes five real-tool cases: loop/blank/hold frames; one-shot playback;
animated GLB with known pivot/material/pose checks; a skinned GLB; and an invalid
accessor rejected by Khronos before engine import. It uploads reports, logs and
fixtures even on failure. CI setup uses PATH only to resolve its provisioned Node;
this behavior is not present in the production adapter.

Local Linux evidence at initial publication: **35 offline tests passed**. No
native Godot or Khronos execution is claimed locally: network/runtime provisioning
is unavailable in the chat container. Hosted results are recorded on the PR after
observing their actual logs. No model inference or creative acceptance is implied.

## Primary references and pins

Reviewed 12 September 2026:

- [Godot 4.5 AnimatedSprite2D](https://docs.godotengine.org/en/4.5/classes/class_animatedsprite2d.html): frame, loop and finished signal semantics; speed scale.
- [Godot command line](https://docs.godotengine.org/en/4.5/tutorials/editor/command_line_tutorial.html): `--import`, `--headless`, and fixed FPS disabling real-time synchronization. Unknown flags can be silently ignored; the former undocumented `--user-data-dir` is removed.
- [Khronos Node API](https://github.com/KhronosGroup/glTF-Validator/blob/main/node/index.js): `validateBytes`, format, maxIssues and externalResourceFunction. This adapter rejects resource loading.
- [Khronos package identity](https://github.com/KhronosGroup/glTF-Validator/blob/main/node/package.json): official Apache-2.0 npm distribution.
- [Godot 4.5 release](https://github.com/godotengine/godot-builds/releases/tag/4.5-stable): Linux archive SHA-256 `c7316e1fd782ad276a4d985a7673b5976eaaa8d90561a2bea5289210dc53e9ba`; Windows x64 archive SHA-256 `303206071cb8be502cfa5b1e2b37b848c280347c03f78dcc2eb8a630857f7d10`.

The original fixture generator belongs to this implementation. It supplies tests,
not an accepted character/prop deliverable. #15/#24 stay open for their broader
creative, target-gameplay and workstation-specific acceptance. HUMAN_TODO remains
unchanged; no art choices or model/source permission decisions were inferred.

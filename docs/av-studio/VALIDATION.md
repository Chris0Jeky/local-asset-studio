# Final validation update

11 September 2026. This update supersedes the earlier pending-CI statements in the research snapshot and README. It does not change their model/editor execution boundaries.

## Observed GitHub checks

Code commit: `73f60c4b345da76aa1d33556bee5aa39687b48ba`.

All three checks completed successfully:

- Dedicated `offline-and-mcp`: run `34630727494`, job `103366627395`, completed at 17:59:55 UTC.
- Existing repository `checks` for the PR: run `34630727544`, job `103366627200`.
- Existing repository `checks` for the push: run `34630723249`, job `103366613216`.

The dedicated workflow installs the actual optional MCP 2.2.0 SDK and Pillow, runs the AV test suite, renders the procedural demo and builds the offline browser. The stdio test exercises discovery, published output schemas, a structured capabilities result and rejection of a workspace-escaping path. A separate test verifies that the render tool is registered only after explicit opt-in. This is actual SDK integration evidence, not a mocked protocol exchange; it does not establish installation in the user's agent host.

The initial dedicated run failed because plain `-> dict` return annotations fell back to unstructured content. The fix uses `dict[str, Any]` with `structured_output=True` and strengthens the test to inspect the published output schemas and returned capability fields. The failure was not hidden by dropping the assertion or skipping the SDK tests.

## Local evidence

Final local run: 31 tests discovered, 29 passed and the two optional SDK tests skipped because the SDK is not installed in this isolated chat environment. Actual core render tests include cuts, dissolves, overlays, mixed audio and a 6-second output with 144 decoded video frames and 288000 audio sample frames at 48kHz. The dedicated remote workflow supplies the SDK evidence missing locally.

The final rebuilt HTML passed Chromium checks for audio scheduling, gain edits, undo, actual JSON download and narrow-screen overflow. No JavaScript errors or external requests were observed. This is interaction/technical evidence, not a human listening test. The 46 source records and nine recipes passed JSON parsing, unique/source-reference checks and strict UTF-8 checks.

## Still not performed

No neural voice/music inference, character-model binary download, live Blender/Krita/DAW operation, user-host MCP installation, OTIO/native-editor round trip or game-engine playback was performed by this pass. Blender's named-operation validation was tested without a Blender binary. The procedural sine/noise soundtrack is not a benchmark of a generative audio model. Sample peak/RMS/DC measurements are not LUFS, true peak or perceptual acceptance.

Implementation follow-ups are issues #28–#32. Reuse the existing Studio and prior asset/executor work rather than building competing managers.

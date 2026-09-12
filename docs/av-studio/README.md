# AV Studio research and implementation slice

**Read:** [Audio and voice](AUDIO-VOICE.md), [unified architecture](ARCHITECTURE.md), [Blender and downloadable assets](BLENDER-ASSETS.md), [agent handoff](HANDOFF.md). Source catalog and proposed production recipes live under `research/av-studio/`.

Research began at `852e3579bd9fa3ca73376ffab64a66d6410115ce`; the final additive branch uses main `f6e046b03cf553d4c75e958f128e51804daa6e52`, including merged PR8/19/20. No existing Studio server, queue, preset, model manifest or runtime is modified. The isolated tools should later be wired into the existing project/executor work rather than replace it.

## Implemented

- Strict project schema with hashed local inputs, rational FPS/integer video frames and48kHz sample-indexed audio.
- Immutable validated edits with an expected-revision check and reversible change record.
- Real CPU FFmpeg rendering: ordered PNG/MP4 shots, cuts/dissolves, static PNG overlays, WAV trims/gains/fades/mixing, lossless mix sidecar and MP4 preview.
- Source snapshots, render plans/logs, incomplete markers, output hashes and timing/QC receipts. Explicit command only; no generation on load.
- Offline browser with a rendered preview, editable audio mix, undo, local Web Audio audition and project export. Video remains explicitly stale after edits until re-rendered.
- Optional MCP2.2 stdio wrapper: discovery/validation/planning/edits/QC; render tool only with `--allow-render`.
- Narrow Blender job code for scene inspection, approved-camera frame rendering and GLB export. **Its live Blender execution is not tested here.**

The AV core uses the Python standard library plus installed FFmpeg/ffprobe. The procedural fixture/workbench builders use Pillow (tested12.3.0). MCP is a separate optional dependency pinned in `requirements-mcp.txt`. Keep both outside the working Comfy runtime.

## Use

From the repository root, in a suitable asset environment:

```console
python scripts/studio_av_demo.py --out experiments/runs/av-demo --render
python scripts/studio_av.py validate experiments/runs/av-demo/project.json --workspace experiments/runs/av-demo
python scripts/studio_av.py plan experiments/runs/av-demo/project.json --workspace experiments/runs/av-demo
python scripts/studio_av_workbench.py experiments/runs/av-demo/project.json --workspace experiments/runs/av-demo --preview experiments/runs/av-demo/render/preview.mp4 --out experiments/runs/av-workbench.html
python -m unittest discover -s tests -p 'test_studio_av*.py' -v
```

Open the HTML file. Change an audio clip's gain/timing/fades, audition it and export JSON. Put the edited JSON in the same demo workspace, then render a new output directory. The tool never overwrites an existing render directory.

```console
python scripts/studio_av.py render experiments/runs/av-demo/project-edited.json --workspace experiments/runs/av-demo --out experiments/runs/av-demo/render-edited
```

Video source ranges are expressed in project-frame units after FPS conversion, not a promise of native VFR frame indexing. Audio clips must be48kHz PCM16 mono/stereo WAV; convert other formats deliberately before ingestion. A video's embedded audio is deliberately not copied: extract/register it as a separate audio clip when needed. Output audio is stereo. Dissolves overlap shot ranges; the final frame is held as needed to meet the exact declared output frame count. The cap is120seconds,16 shots,16 overlays,32 audio clips,1080p-equivalent pixels and1GiB total inputs. These are preview constraints, not universal production recommendations.

No silent limiter/normalizer is inserted. QC reports full-scale samples; review high-level mixes before playback or acceptance. Sample peak/RMS/DC are not LUFS or true peak. Browser audition is not sample-identical to the offline mix: browser resampling/channel conversion can differ. The final renderer is authoritative for export timing.

## MCP launch

Install the optional SDK in a separate environment, then point the agent host at the absolute interpreter and script paths. The SDK is currently2.x; the wrapper targets2.2.0. A generic host configuration is:

```json
{
  "mcpServers": {
    "studio-av": {
      "command": "C:/AI/envs/studio-av/Scripts/python.exe",
      "args": ["C:/path/local-asset-studio/scripts/studio_av_mcp.py", "--workspace", "C:/AI/jobs/approved-project"]
    }
  }
}
```

This is a configuration example, not a claim that it was installed in your host. Add `--allow-render` only when the host should be able to request bounded CPU renders. Default tools are read/plan/propose only. Every render needs a matching expected revision and gets a new server-generated folder. No network listener, TTS model, unrestricted shell tool or paid service is exposed.

## Evidence boundaries

Local environment: Python3.13.5, FFmpeg7.1.5, Pillow12.3.0, Linux.29 core/media/Blender-contract tests passed, including real cut/dissolve renders and144 decoded frames/288000 output samples for the6second fixture. Chromium tests exercised audio scheduling, gain editing, undo and real JSON download; desktop/mobile inspected, no JS errors, no external requests. This was not a human listening test.

The local pip install of MCP2.2.0 failed because network DNS is unavailable. Two real SDK tests are supplied and the dedicated CI installs the SDK and exercises stdio discovery/call/denial and explicit render-tool registration. Until remote CI evidence is observed, MCP protocol execution is not claimed. No Blender binary is present here; only its job contract was tested. No neural voice/music inference, downloaded character binary, live editor control, OTIO export, TTS adapter or game-engine audio test was performed.

This renderer is a bounded local tool, not a decoder sandbox, durable background queue or professional NLE/DAW replacement. Media decoders, plugin code and future editor bridges need process isolation and explicit permissions. Paths, hashes and caps reduce accidental misuse but cannot protect against a hostile OS user. Output-root policies and asynchronous job cancellation remain coordinator work.

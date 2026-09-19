# Spoken Briefs

Spoken Briefs turns a Markdown handoff into one local narration WAV by coordinating the existing Local Asset Studio Voice baseline. It solves the immediate workflow gap without adding a second inference worker:

```text
COMPRESSED.md (preferred) or INDEX.md
    -> deterministic Markdown projection
    -> bounded Voice baseline projects
    -> verified 48 kHz scene WAVs
    -> one assembled PCM WAV + receipt
```

The Markdown file remains the source of truth. Generated audio is a hash-addressed view over the source, compiler contract, speaker metadata and exact child Voice projects.

## Use it

Prerequisites:

1. Start Local Asset Studio on its normal loopback address, `http://127.0.0.1:8191`.
2. Configure and prove the isolated Voice baseline described in [`VOICE-BASELINE.md`](../VOICE-BASELINE.md). Spoken Briefs does not install a model or start Studio.
3. Keep the handoff in a directory containing `COMPRESSED.md` or `INDEX.md`. A direct Markdown path also works.

Preview the projection without submitting generation:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\Users\jekyt\Documents\handoffs\<pack>" `
  -PlanOnly
```

Create the Voice projects and assemble the completed scene WAVs:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\Users\jekyt\Documents\handoffs\<pack>"
```

The wrapper uses `LAS_PYTHON` when it points to a file, then the repository `.venv`, then `python` from `PATH`. It passes arguments directly and never evaluates a command string. Useful controls are:

```powershell
.\scripts\speak-handoff.ps1 <pack> `
  -SpeakerId brief-narrator `
  -DeadlineMinutes 180 `
  -PollSeconds 1
```

`SpeakerId` is stable recipe metadata. In the current Kokoro baseline it does **not** choose, design or clone a voice; the configured bundle still produces its pinned built-in `af_heart` voice. The reusable soothing narration identity is a separate Voice Lab programme in #637 and [`VOICE-PROFILE.md`](VOICE-PROFILE.md).

## Existing producer step

The repository-supported producer behind the command is the same bounded Voice baseline exposed by the Studio voice page:

1. `POST /api/voice-baseline` prepares one project with one to six stable `{id,text}` lines.
2. The returned 32-character project ID is persisted locally.
3. `POST /api/production/<id>/start` explicitly queues that existing project.
4. `GET /api/production/<id>` is observed until a durable terminal state exists.
5. The coordinator downloads each hashed `voice/<line-id>-scene.wav` through that project's file route.

The underlying Voice implementation validates the pinned `voice_baseline_bundle`, isolated Python/package versions, model files, runner hash and configured FFmpeg before execution. It produces 24 kHz dry WAVs plus 48 kHz scene-interchange WAVs. Spoken Briefs consumes the scene copies and does not bypass or replicate that producer. This is the supported recipe captured from repository evidence; the exact clicks used in an earlier ad-hoc spoken pass were not separately retained.

## Output

For `COMPRESSED.md`, a run is stored under the handoff pack rather than the repository:

```text
<pack>\_spoken\COMPRESSED-<manifest-hash>\
    manifest.json
    state.json
    receipt.json
    COMPRESSED.spoken.wav
    segments\
        segment-0001.wav
        segment-0002.wav
        ...
```

- `manifest.json` is the immutable source/compiler/segment plan.
- `state.json` records every child project ID before it can be started, plus mutable progress and retained artifact hashes.
- `segments/` contains only verified 48 kHz mono PCM16 scene copies downloaded from their own project routes.
- `receipt.json` binds the source hash, project IDs, segment hashes, pauses and final WAV hash.
- `*.spoken.wav` is the deterministic archival listening file. Chaptered MP3/M4B exports are tracked in #640.

The manifest identity includes the canonical source path, source bytes, speaker ID, compiler version and compiled segment plan. Moving or changing the source therefore produces a new run directory and never mutates an older narration.

## What is spoken

The compiler is intentionally predictable rather than generative. It does not summarise or invent transitions.

| Markdown input | Spoken projection |
| --- | --- |
| Headings | Kept as their own blocks with a longer following pause |
| Prose and list text | Kept, with stable ordered segment IDs |
| Tables | Flattened row by row, cell text separated by full stops |
| Markdown links | Link label is spoken |
| Raw URLs | Replaced with `link omitted` |
| Inline code/emphasis | Formatting removed; contained text kept |
| YAML front matter | Omitted and counted |
| Fenced code | Omitted and counted |
| HTML comments | Omitted and counted |

Current safety bounds are 512 KiB of UTF-8 Markdown, 240 segments, 100,000 narrated characters, 520 characters per segment, and conservative batches of at most six lines, 1,500 characters and 210 words. These remain below the existing Voice baseline's hard per-line and per-project limits; the backend still owns its 120-second sample ceiling.

## Recovery and repeat behaviour

The command is review-first in the operational sense: invoking `run` is the explicit generation action. Merely creating or changing a handoff file does nothing.

| Observed state | Behaviour |
| --- | --- |
| Exact completed receipt and matching output hash | Return the existing WAV without contacting Studio |
| Existing planned/queued/running Voice project ID | Fetch and reconcile that exact project |
| Completed child project | Verify its exact line plan, artifact route, SHA-256 and WAV format, then reuse it |
| Failed, cancelled, stopped, interrupted or otherwise terminal child | Block; never create a replacement implicitly |
| Explicit HTTP 4xx create rejection | Retain the rejection, return to `pending`, and allow a later explicit run after the configuration is fixed |
| Create response missing or uncertain | Retain `creating`/`create-unconfirmed` and block all later submissions |
| Start response uncertain | Re-fetch the known project ID before deciding whether Start is still needed |
| Final WAV missing but child evidence remains valid | Re-download/reassemble from the retained projects without new TTS |
| Final WAV hash differs from the receipt | Block for inspection |
| `.spoken-brief.lock` exists | Treat another coordinator or a stale crash claim as active and block |

A lock is removed on normal return and handled failures. After a hard process termination, inspect `state.json`, the child projects and running processes before manually removing a stale `.spoken-brief.lock`.

## Evidence boundary

The implementation suite uses a fake loopback Studio and synthetic PCM WAVs. It proves source selection, projection, bounds, state recovery, exact project-plan matching, same-origin requests, artifact confinement, hashing, assembly, concurrency exclusion and repeat-command idempotence. It does not prove real workstation inference speed, subjective voice quality, pronunciation or long-form listening comfort.

The next proving action on the configured machine is one `-PlanOnly` preview followed by one short real handoff. Keep its generated files outside Git, listen to the assembled WAV, and record defects against #636 or the long-form QA issue #641 rather than treating a successful process exit as creative acceptance.

## Programme map

- #635: product umbrella and completion criteria.
- #636: this deterministic coordinator and WAV assembler.
- #637: qualify a soothing reusable Voice Lab profile.
- #638: first-class aggregate Production project and Studio surface.
- #639: review-first discovery of new or changed handoff packs.
- #640: chaptered listening exports and playback state.
- #641: transcript, pronunciation and per-segment review QA.

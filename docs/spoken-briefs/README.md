# Spoken Briefs

Spoken Briefs turns one Markdown handoff into one local narration WAV by coordinating the existing Local Asset Studio Voice baseline.

```text
COMPRESSED.md (preferred) or INDEX.md
    -> deterministic Markdown projection
    -> bounded Voice baseline child projects
    -> verified 48 kHz scene WAVs
    -> one assembled PCM WAV + provenance receipt
```

The Markdown file remains the source of truth. Audio is a reproducible local view over exact source bytes, compiler rules, Studio identity, Voice producer configuration, child project plans, artifacts, and assembly parameters.

## Use it

Prerequisites:

1. Start Local Asset Studio on its normal loopback address, `http://127.0.0.1:8191`.
2. Configure and prove the isolated Voice baseline described in [`VOICE-BASELINE.md`](../VOICE-BASELINE.md). Spoken Briefs does not install a model or start Studio.
3. Keep the handoff in a directory containing `COMPRESSED.md` or `INDEX.md`. A direct Markdown path also works.

Preview the exact spoken projection without submitting generation:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\Users\jekyt\Documents\handoffs\<pack>" `
  -PlanOnly
```

Create the Voice projects and assemble their scene WAVs:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\Users\jekyt\Documents\handoffs\<pack>"
```

Useful controls:

```powershell
.\scripts\speak-handoff.ps1 <pack> `
  -SpeakerId brief-narrator `
  -DeadlineMinutes 180 `
  -PollSeconds 1
```

The wrapper resolves `LAS_PYTHON`, then the repository `.venv`, then `python` from `PATH`. It forwards arguments directly, uses invariant-culture numeric formatting, preserves the child exit code, and never evaluates a command string.

`SpeakerId` is stable recipe metadata. In the current Kokoro baseline it does not select, design, or clone a voice. The configured bundle still produces its pinned built-in `af_heart` voice. The reusable soothing narration identity is tracked separately in #637 and [`VOICE-PROFILE.md`](VOICE-PROFILE.md).

## Producer protocol

The coordinator reuses the bounded Voice baseline already exposed by Studio:

1. `POST /api/voice-baseline` prepares one Voice project with one to six stable `{id,text}` lines.
2. The returned 32-character project ID is durably persisted before any further request.
3. `GET /api/production/<id>` supplies the canonical child state and signed Voice plan. Successful create-response state is advisory and is not trusted as the project record.
4. The retained Voice plan SHA-256 and producer fingerprint are verified and persisted.
5. `POST /api/production/<id>/start` explicitly starts that exact project.
6. A successful Start acknowledgement is followed by another canonical `GET`; the response body is not treated as durable child state.
7. `GET /api/production/<id>` is observed until a durable terminal state exists.
8. Each hashed `voice/<line-id>-scene.wav` is downloaded only through its own project file route.

The Voice implementation validates its pinned `voice_baseline_bundle`, isolated Python and package versions, model files, runner hash, and configured FFmpeg before execution. It produces 24 kHz dry WAVs and 48 kHz scene-interchange WAVs. Spoken Briefs consumes the scene copies and does not bypass or duplicate that producer.

## Output

A `COMPRESSED.md` run is stored beside its handoff pack:

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

- `manifest.json` is the immutable schema-v2 source, compiler, speaker, and segment plan.
- `state.json` is mutable coordination evidence. It records the exact Studio endpoint and workspace identity, every child project ID, every child plan SHA-256, one stable Voice producer fingerprint, statuses, and artifact hashes.
- `segments/` contains verified 48 kHz mono PCM16 scene copies downloaded from their own project routes.
- `receipt.json` binds source bytes, Studio identity, producer fingerprint, project IDs and plan hashes, segment text hashes, pauses, exact input WAV snapshots, and the final master hash.
- `*.spoken.wav` is the deterministic archival listening file. Chaptered MP3 or M4B exports remain #640.

The manifest identity includes the canonical source path, exact source byte count and SHA-256, speaker ID, compiler version and settings, omissions, and compiled segments. Moving or changing the source creates a different run directory instead of mutating an older narration.

Generated `_spoken/` directories are ignored by Git so private handoffs and audio are not accidentally committed.

## What is spoken

The compiler is deterministic rather than generative. It does not summarise, paraphrase, or invent transitions.

| Markdown input | Spoken projection |
| --- | --- |
| Headings | Kept as separate blocks with a longer following pause |
| Prose and list text | Kept in source order with stable segment IDs |
| Tables | Flattened row by row, with cell text separated by full stops |
| Markdown links | Link label is spoken |
| Raw URLs | Replaced with `link omitted` |
| Inline code and emphasis | Formatting removed, contained text kept |
| YAML front matter | Omitted and counted |
| Fenced code | Omitted and counted |
| HTML comments | Omitted and counted |

Current bounds are 512 KiB of UTF-8 Markdown, 240 segments, 100,000 narrated characters, 520 characters per segment, and batches of at most six lines, 1,500 characters, and 210 words. These are deliberately below the existing Voice baseline limits. The backend still owns its 120-second sample ceiling.

## Provenance and mutation checks

Before any create, Start, observation, artifact download, or final publication boundary, the coordinator verifies the assumptions that make the run valid:

- the selected Markdown path still has the same byte count and SHA-256;
- the loopback endpoint still reports the same complete Studio workspace identity;
- each adopted child still has the same valid, self-hashed Voice plan;
- all children use one consistent producer fingerprint;
- child line IDs, text, and speaker metadata still match the compiled batch;
- artifact routes remain confined to their exact project and their bytes match the retained SHA-256.

The source is checked again after local assembly. If it changes during assembly, the unreceipted master is removed, state is marked `source-changed`, and no completion receipt is published.

State, lock intent, and completed records use flushed, fsynced temporary files followed by atomic replacement where applicable. The final WAV is fsynced before replacement. Output and completed-reuse hashes are streamed. Each input receipt hashes the exact bounded file snapshot decoded and copied into the assembled WAV, so a later file mutation cannot make the receipt describe different bytes from those actually used.

## Recovery and repeat behaviour

Invoking `run` is the explicit generation action. Creating or changing a handoff file alone does nothing.

| Observed state | Behaviour |
| --- | --- |
| Exact completed receipt and matching output hash | Return the existing WAV without contacting Studio |
| Existing planned, queued, running, or observing project ID | Fetch and reconcile that exact project |
| Completed child project | Verify its signed plan, exact text, producer, artifacts, hashes, and WAV format, then reuse it |
| Failed, cancelled, stopped, interrupted, or otherwise terminal child | Block; never create a replacement implicitly |
| Explicit HTTP 4xx create rejection | Retain the rejection, return the batch to `pending`, and permit a later explicit run after configuration is fixed |
| Successful create response with a valid project ID | Persist the ID, then fetch and validate the canonical project before Start |
| Create response missing an ID, malformed, or uncertain | Retain `create-unconfirmed` and block all later submissions |
| Successful Start acknowledgement | Persist `start-accepted`, then fetch and validate the known project rather than trusting response state |
| Start response uncertain | Retain the known child ID and require observation of that project; never create a replacement |
| Source bytes change during the run | Block; keep the old child evidence under its original manifest and do not publish a new receipt |
| Studio endpoint or workspace identity changes | Block before further mutation |
| Child plan or producer configuration changes | Block before Start or artifact use |
| Final WAV is missing but child evidence remains valid | Re-download or reassemble from the retained children without new TTS |
| Final WAV hash differs from its receipt | Block for inspection |
| `.spoken-brief.lock` exists | Treat another coordinator or a stale crash claim as active and block |

A lock is removed during normal Python unwinding. After a hard process termination, inspect `state.json`, the child projects, and running processes before manually removing a stale `.spoken-brief.lock`. It is intentionally never expired by elapsed time alone.

## Trust boundary

The loopback client accepts plain HTTP only on `127.0.0.1` or `localhost`, with a valid optional port and no credentials, query, fragment, or base path. Proxy environment variables are ignored, redirects are refused, JSON and audio responses are bounded, and JSON endpoints must return objects. Every POST carries the exact loopback origin.

Markdown cannot provide an arbitrary URL, filesystem target, or shell command. The only accepted audio URL is the exact relative route for the retained child project and expected segment scene WAV.

## Evidence boundary

The focused suite currently has 43 offline contracts on Python 3.12 and runs on Ubuntu and Windows. It uses a fake loopback Studio and synthetic PCM WAVs to prove:

- deterministic source selection, Markdown projection, segmentation, and batch bounds;
- exact-byte source revalidation at mutation and publication boundaries;
- durable state, lock, child identity, plan-hash, producer, and Studio-workspace provenance;
- uncertain-create and uncertain-Start fail-closed recovery;
- successful create and Start acknowledgements are reconciled through canonical project reads;
- proxy, redirect, response-bound, JSON-shape, and artifact-route constraints;
- exact PCM ordering, deterministic silence, exact-snapshot input receipts, atomic publication, streamed output hashing, and read-only completed reuse;
- source, workspace, plan, and producer drift rejection on both supported operating-system families.

CI does not prove real workstation inference speed, subjective voice quality, pronunciation, or long-form listening comfort. The next real proving action is one `-PlanOnly` preview followed by one short handoff on the configured workstation. Keep those generated files outside Git and record quality defects against #637 or #641 rather than treating process success as creative acceptance.

## Programme map

- #635: Spoken Briefs umbrella and completion criteria.
- #636: deterministic coordinator and WAV assembler implemented by this slice.
- #637: qualify an original low-fatigue, soothing Voice Lab profile.
- #638: first-class aggregate Production project and Studio surface.
- #639: review-first discovery of new or changed handoff packs.
- #640: chaptered listening exports and playback state.
- #641: transcript, pronunciation, and per-segment review QA.

# Spoken Briefs architecture

Status: first executable slice implemented for #636; broader product tracked by #635.

## Decision

Build Spoken Briefs first as a deterministic coordinator over the existing Voice baseline and Production state machine. Do not introduce another model loader, generation worker or retry policy. Compile Markdown into stable bounded lines, create ordinary Voice projects explicitly, retain every returned project ID, verify their scene WAVs, and concatenate PCM samples directly into one archival WAV.

This is the smallest architecture that removes manual stitching while preserving the Studio's strongest existing properties: local-only execution, pinned voice bundles, explicit Start, durable project evidence, no automatic retry after uncertain work, and inspectable artifact hashes.

## Goals

- One command converts a handoff pack into one listenable file.
- `COMPRESSED.md` is preferred and `INDEX.md` is the fallback.
- Markdown remains authoritative; generated audio is a derived view.
- Every transformation and child project is reproducible and inspectable.
- A rerun is idempotent when the exact completed output still exists.
- Missing assembly output can be rebuilt without repeating TTS.
- Failure, interruption and uncertain requests are visible and never replaced implicitly.
- The producer can later change from Kokoro to an accepted designed voice without replacing ingestion, recovery or assembly.

## Non-goals of the first slice

- A custom character voice or an assertion that `speaker_id` changes voice identity.
- Automatic folder watching.
- MP3/M4B, chapters or playback state.
- ASR, forced alignment or pronunciation certification.
- A new Studio browser surface or aggregate Production kind.
- Starting Studio, installing a model, downloading weights or importing network content.

## Alternatives considered

### Concatenate whatever files exist with one FFmpeg command

This is a useful repair command but an incomplete product. It cannot decide source order safely, explain which text produced a clip, recover child project IDs, prevent duplicate inference or distinguish a missing clip from an uncertain request. It also makes path quoting and format compatibility part of the first critical path.

### Add long-form behaviour inside `voice_baseline.py`

That would tightly couple document parsing, batch scheduling and aggregate recovery to one temporary Kokoro implementation. The existing Voice plan deliberately represents one bounded take and has strong no-retry semantics. Reusing it as a child operation keeps that evidence model intact and creates a clean adapter boundary for later producers.

### Generate one very long model request

The current baseline accepts at most six lines and 2,000 characters and enforces a 120-second sample budget. Larger single requests would increase timeout, memory and partial-output ambiguity. Conservative batches provide bounded failure domains and let later UX replace one segment without regenerating the whole brief.

### Use Windows Narrator, Edge or Piper as the primary route

Those remain valid stopgaps. They do not reuse the accepted LAS quality, Voice Lab provenance or Production receipts, so they are not the primary architecture.

### Chosen: child Voice projects plus deterministic PCM assembly

All scene outputs already share the required 48 kHz mono PCM16 contract. Python's standard-library `wave` module can copy their PCM frames and insert exact silence without re-encoding. This removes an external process from the first assembler while leaving FFmpeg available for later delivery formats.

## Components

```text
scripts/speak-handoff.ps1
    thin Windows argument adapter
              |
              v
scripts/spoken_brief.py + spoken_brief_{compile,transport,runtime}.py
    source resolver
    Markdown projection
    segment/batch compiler
    durable local manifest/state
    loopback Studio client
    child-project reconciler
    artifact verifier
    PCM assembler
              |
              v
existing LAS HTTP + Production + voice_baseline.py
              |
              v
pinned isolated Kokoro bundle -> dry + scene WAVs
```

The coordinator is standard-library-only and does not import Studio internals. Its public dependency is the loopback HTTP contract, which is also the route future UI and agent tooling can share.

## Source and compilation contract

`resolve_source()` accepts either a Markdown file or a directory. A directory resolves `COMPRESSED.md` first and `INDEX.md` second. The selected bytes are read once as bounded UTF-8 and hashed before compilation.

`compile_markdown()` creates ordered blocks and segments. Each segment records:

```json
{
  "id": "segment-0001",
  "text": "The exact text sent to the Voice project.",
  "text_sha256": "...",
  "block": 0,
  "kind": "heading|paragraph|table",
  "pause_after_ms": 650
}
```

Stable IDs are positional within an immutable manifest. A source/compiler/profile change creates a different manifest identity rather than updating old segments in place.

Segmentation prefers sentence boundaries, then hard word-aware splits. Batching preserves order and obeys all of:

- at most 6 lines;
- at most 1,500 characters;
- at most 210 whitespace-delimited words.

The character and word bounds are intentionally more conservative than the backend's 2,000-character project ceiling because the Kokoro runner also owns a 120-second sample limit.

## Files and identities

A run directory is derived from source stem and the first twelve characters of `manifest_sha256`:

```text
<source parent>/_spoken/<stem>-<manifest>/
```

The manifest hash covers the canonical source path, source bytes/hash, speaker metadata, compiler configuration, omissions and segments. The directory holds three record classes:

1. **Manifest**, immutable intent and source projection.
2. **State**, mutable coordination evidence including child IDs and artifact caches.
3. **Receipt**, completed output binding and final SHA-256.

Generated segment and final WAV files live beside those records. Repository `.gitignore` excludes `_spoken/` directories so an accidental in-repository trial does not stage private briefs or audio.

## State and request protocol

Each batch begins as:

```json
{
  "id": "batch-001",
  "line_ids": ["segment-0001"],
  "project_id": null,
  "status": "pending",
  "artifacts": {}
}
```

The coordinator validates the entire retained batch shape against a freshly compiled manifest before any network request.

State transitions are fail-closed:

```text
pending
  -> creating (persisted before POST /api/voice-baseline)
  -> planned + project_id (persisted before Start)
  -> queued/running/observing
  -> completed

explicit HTTP 4xx rejection -> pending with retained error
creating without project_id -> create-unconfirmed -> blocked
known child terminal failure -> blocked
known active child at deadline -> timed-out, child retained
```

`creating` is written before the create request. Therefore a process death, lost response, malformed response or state-write problem cannot turn into an automatic second create. Because the current API has no request-key lookup, the correct recovery is inspection, not guessing. An explicit HTTP 4xx response is different: it proves the loopback service rejected the request, so the batch returns to `pending` with the retained error and can be tried only by a later explicit command after configuration is fixed. HTTP 5xx and transport failures remain uncertain.

A known project ID is fetched from `GET /api/production/<id>`. Before Start or artifact use, its kind, `speaker_id`, stable line IDs and exact text must match the compiled batch. This prevents a corrupted local state file from pointing at a different Voice take.

Start ambiguity is different from create ambiguity because the project ID is already known. A later run fetches that project. If it is queued/running/completed, it continues observation; if the durable project remains planned, Start can be requested again against the same identity.

## Concurrency

An atomic `.spoken-brief.lock` claim prevents two local coordinator processes from creating the same batch concurrently. The lock records process ID, manifest hash and claim time. It is removed in `finally` on normal Python unwinding. A hard-kill can leave a stale claim; automatic expiry is deliberately avoided because elapsed time does not prove the other process or request is dead.

## HTTP and artifact trust boundary

The client accepts only plain HTTP on `127.0.0.1` or `localhost`, with no URL credentials, query, fragment or base path. It verifies `/api/identity` before mutations and sends the exact loopback base as `Origin` on POST requests.

Artifacts are accepted only when:

- the completed child project exposes exactly one `*-scene.wav` for the segment;
- its URL is relative and begins with that exact project's `/api/production/<id>/files/` route;
- its SHA-256 is complete and matches downloaded bytes;
- the WAV is uncompressed 48 kHz, mono, 16-bit PCM.

No arbitrary URL, file path or shell command from Markdown is executed.

## Assembly

`assemble_wav()` opens each verified scene WAV, copies PCM frames in manifest order, and writes zero-valued PCM frames for the recorded pause. It produces a new temporary WAV and atomically replaces the target only after all inputs have been read.

The receipt records every input path/hash/sample count/pause, total samples, exact duration and final hash. Re-running with a matching receipt and output hash is read-only and does not contact Studio. A missing output can be reassembled from retained child evidence. A mismatched completed hash or output path is an integrity error, not permission to overwrite silently.

## Voice identity boundary

The first producer is the existing Kokoro CPU baseline because it is already pinned and proven to generate scene WAVs. Its `speaker_id` is metadata used to keep recipes stable; the actual voice remains the bundle's built-in `af_heart` identity.

Long-term producer selection belongs behind the same conceptual interface:

```text
prepare(profile_id, delivery_id, stable lines) -> durable child project
start(project_id) -> explicit generation
inspect(project_id) -> state + hashed scene WAV artifacts
```

The target profile work in #637 separates identity, delivery, pronunciation lexicon, dry take, mix treatment and human acceptance. The document/compiler and assembler do not need to know whether the child producer is Kokoro, Qwen3-TTS CustomVoice, IndexTTS or another qualified local adapter.

## Product evolution

### Aggregate project and UI (#638)

Promote the external manifest/state into a `spoken-brief` Production kind once the command contract is proven. The Studio should preview spoken text and omissions, show child progress, expose the final player/download, and replace one rejected segment without hiding child evidence.

### Review-first watcher (#639)

Watch a configured handoff root only for stable source hashes. Discovery creates a preview candidate, not TTS. Automatic generation remains an explicit later policy with a visible allow-list and kill switch.

### Listening exports (#640)

Keep PCM WAV as the deterministic master. Derive MP3/M4B and chapters from actual sample offsets through the configured owned FFmpeg executable. Playback position is mutable user state, separate from the immutable generation receipt.

### Transcript and pronunciation QA (#641)

Run independent ASR per segment and on the assembled master, retain diff evidence, and surface exceptions. ASR agreement is not a listening-quality or identity certificate. Replacement takes branch from the rejected segment and trigger assembly only.

## Verification boundary

The focused suite uses a fake loopback Studio and generated PCM fixtures. It exercises red/green contracts for Markdown projection, segment/batch limits, retained state shape, exact child plan matching, uncertain create handling, concurrency claims, project-scoped artifacts, WAV assembly and completed-run reuse on Python 3.12-compatible standard-library APIs.

Real inference remains a workstation proving step because CI has no pinned model bundle. A real successful run proves integration and performance only; it does not accept the voice creatively. Long-form identity, fatigue and pronunciation acceptance remain #637 and #641.

# Spoken Briefs architecture

Status: first executable slice implemented for #636; broader product tracked by #635.

## Decision

Build Spoken Briefs as a deterministic coordinator over the existing Voice baseline and Production state machine. Do not introduce another model loader, generation worker, or retry policy.

The coordinator compiles Markdown into stable bounded lines, creates ordinary Voice projects explicitly, durably retains every project identity, verifies the signed child plans and scene WAVs, and concatenates PCM samples into one archival WAV.

This removes manual stitching while preserving Local Asset Studio's strongest properties:

- local-first execution;
- explicit Start rather than hidden generation;
- pinned producer bundles;
- durable child-project evidence;
- no automatic duplicate work after uncertainty;
- exact source and artifact hashes;
- inspectable recovery decisions.

## Goals

- One command converts a handoff pack into one listenable file.
- `COMPRESSED.md` is preferred and `INDEX.md` is the fallback.
- Markdown remains authoritative; audio is a derived view.
- Every transformation and child project is reproducible and inspectable.
- A rerun is read-only when the exact completed output still exists.
- A missing assembly output can be rebuilt without repeating TTS.
- Failure, interruption, source drift, producer drift, and uncertain requests remain visible.
- A later accepted voice producer can replace Kokoro without replacing ingestion, recovery, or assembly.

## Non-goals of the first slice

- A custom character voice or a claim that `speaker_id` changes voice identity.
- Automatic folder watching.
- MP3, M4B, chapters, or playback state.
- ASR, forced alignment, or pronunciation certification.
- A new Studio browser surface or aggregate Production kind.
- Starting Studio, installing software, downloading weights, or importing network content.

## Alternatives considered

### Concatenate whatever files exist with FFmpeg

A raw concat command is useful for repair, but it cannot determine safe source order, retain text-to-clip provenance, recover child project IDs, prevent duplicate inference, or distinguish a missing clip from an uncertain request.

### Add long-form behaviour inside `voice_baseline.py`

That would couple document parsing, aggregate scheduling, and recovery to one temporary Kokoro implementation. The existing Voice plan represents one bounded take and already has strong no-retry semantics. Keeping each take as a child operation preserves that evidence model.

### Submit one very long model request

The current baseline accepts at most six lines and 2,000 characters and enforces a 120-second sample budget. Large single requests increase timeout, memory, and partial-output ambiguity. Conservative batches create bounded failure domains and permit later segment-level repair.

### Use Windows Narrator, Edge, or Piper as the primary route

These remain valid stopgaps, but they do not reuse the accepted LAS output quality, Voice Lab provenance, or Production receipts.

### Chosen approach

Use bounded Voice child projects plus deterministic PCM assembly. Every scene WAV already conforms to 48 kHz mono PCM16, so Python's standard-library `wave` module can copy frames and insert exact silence without re-encoding.

## Components

```text
scripts/speak-handoff.ps1
    thin Windows argument adapter
              |
              v
scripts/spoken_brief.py
scripts/spoken_brief_compile.py
scripts/spoken_brief_transport.py
scripts/spoken_brief_runtime.py
    source resolver and compiler
    manifest and state contracts
    loopback Studio client
    child-project reconciler
    provenance verifier
    artifact verifier
    PCM assembler
              |
              v
existing LAS HTTP + Production + voice_baseline.py
              |
              v
pinned isolated Voice bundle -> dry + scene WAVs
```

The coordinator is standard-library-only and does not import Studio internals. Its dependency is the loopback HTTP contract, which future UI and agent tooling can share.

## Core invariants

1. The selected Markdown bytes are the authority for one manifest.
2. No mutation occurs after the source, Studio workspace, or retained child evidence has drifted.
3. A child project is adopted only after its exact self-hashed Voice plan is verified.
4. All children in one spoken brief must resolve to one producer fingerprint.
5. A create request is never repeated after an uncertain outcome.
6. Start ambiguity never causes a replacement project because the child ID is already known.
7. Audio is accepted only from the exact child file route with a matching SHA-256 and WAV contract.
8. An input receipt describes the exact bounded WAV byte snapshot decoded and copied into the master.
9. A completed receipt is published only after source bytes still match following local assembly.
10. A matching completed receipt makes a repeated command read-only.

## Source and compilation contract

`resolve_source()` accepts a Markdown file or a directory. A directory resolves `COMPRESSED.md` first and `INDEX.md` second.

`compile_source()` reads at most 512 KiB, decodes UTF-8, records the exact byte count and SHA-256, projects Markdown deterministically, and creates a schema-v2 manifest.

Each segment records:

```json
{
  "id": "segment-0001",
  "text": "The exact text sent to Voice.",
  "text_sha256": "...",
  "block": 0,
  "kind": "heading",
  "pause_after_ms": 650
}
```

Stable IDs are positional within an immutable manifest. A source, compiler, or speaker change creates another manifest identity instead of editing an older run.

Segmentation prefers sentence boundaries and falls back to word-aware hard splits. Batching preserves order and obeys all of:

- at most six lines;
- at most 1,500 characters;
- at most 210 whitespace-delimited words;
- at most 520 characters per line.

The bounds are intentionally below the Voice baseline limits because the producer also owns a 120-second sample ceiling.

## Run identity and files

A run directory is derived from the source stem and first twelve characters of `manifest_sha256`:

```text
<source parent>/_spoken/<stem>-<manifest>/
```

The manifest hash covers:

- canonical source path;
- source byte count and SHA-256;
- speaker metadata;
- compiler version and limits;
- omission counts;
- ordered segment plans and pauses.

The directory contains:

1. `manifest.json`, immutable source and projection intent.
2. `state.json`, mutable coordination and recovery evidence.
3. `receipt.json`, completed publication evidence.
4. verified child scene WAV copies.
5. one assembled master WAV.

Repository `.gitignore` excludes `_spoken/` directories.

## Mutable state schema

The schema-v2 state includes top-level Studio and producer provenance:

```json
{
  "schema_version": 2,
  "manifest_sha256": "...",
  "status": "running",
  "studio": {
    "base_url": "http://127.0.0.1:8191",
    "identity": {
      "app": "local-asset-studio",
      "workspace": "C:\\...",
      "version": "production-workspace-1"
    }
  },
  "producer_sha256": "...",
  "batches": []
}
```

Each batch includes:

```json
{
  "id": "batch-001",
  "line_ids": ["segment-0001"],
  "project_id": "0123456789abcdef0123456789abcdef",
  "project_plan_sha256": "...",
  "status": "queued",
  "artifacts": {}
}
```

The entire retained batch shape is validated against a freshly compiled manifest before network use. Child project IDs, plan hashes, producer hash, Studio identity, and artifact records are treated as evidence, not advisory metadata.

## Signed project and producer provenance

LAS Voice plans carry their own `sha256`. The coordinator recomputes the canonical Production fingerprint over the plan without its `sha256` field. A malformed, missing, or mismatched fingerprint blocks before Start or artifact use.

The exact child plan SHA-256 is retained when that project is first adopted. Later observations must keep that same hash.

The producer fingerprint is derived from the validated unsigned plan after excluding batch-specific fields:

- `name`;
- `lines`;
- `created_at`.

The remaining configuration covers the Voice kind, bundle and runner evidence, speaker metadata, model and executable hashes, formats, limits, and other producer settings returned by LAS. Every child in one spoken brief must produce the same fingerprint. A change blocks before the later child is started.

## Source and Studio revalidation

Before create, Start, project observation, artifact download, and final assembly, the coordinator:

1. fetches `/api/identity`;
2. requires the exact previously bound loopback base URL and full Studio identity object;
3. rereads the bounded source bytes;
4. requires the retained byte count and SHA-256.

The source is also checked after local assembly. This closes the publication window in which the Markdown could change after the final pre-assembly check. On drift, the unreceipted master is removed and state records `source-changed`.

A workspace restart that retains the same complete identity is acceptable. A different workspace path, identity version, or base endpoint blocks further mutation.

## Request protocol

State transitions are fail-closed:

```text
pending
  -> creating        persisted and fsynced before POST /api/voice-baseline
  -> created         returned project ID persisted and fsynced
  -> planned         canonical GET verified before Start
  -> start-accepted  persisted after a successful Start acknowledgement
  -> queued/running/observing
  -> completed

explicit HTTP 4xx create rejection -> pending with retained error
unknown create outcome             -> create-unconfirmed -> blocked
unknown Start outcome              -> known child retained -> blocked for observation
known child terminal failure       -> blocked
active child at deadline           -> timed-out, child retained
```

A successful create response is authoritative only for a syntactically valid project ID. The ID is persisted immediately, then `GET /api/production/<id>` supplies the canonical project state and full signed plan. A malformed or incomplete success-body state therefore cannot be mistaken for durable evidence.

A successful Start response is an acknowledgement, not the canonical child record. The coordinator persists `start-accepted`, then fetches the known child and verifies its plan and state through `GET`.

Because the current API has no request-key lookup, an uncertain create result cannot be reconciled automatically. Repeating the create could duplicate expensive inference, so inspection is required.

An explicit HTTP 4xx response proves the loopback service rejected the request. The batch can return to `pending`, and a later explicit command may retry after configuration is corrected.

Start ambiguity is different because the child identity already exists. A later run inspects that exact project. It never creates a replacement.

## Durable local persistence

State and receipt writes use unique temporary files in the destination directory, flush and `fsync` their contents, then atomically replace the target. Parent directory metadata is synced on supported POSIX systems.

The `.spoken-brief.lock` claim is created with `O_CREAT | O_EXCL`, written and fsynced before any network use. It records process ID, manifest hash, and claim time. Automatic expiry is deliberately avoided because elapsed time does not prove the original process or request is dead.

The assembled temporary WAV is closed, reopened read/write for cross-platform `fsync`, then atomically replaces the final path. This is verified on both Linux and Windows runners.

## Loopback transport boundary

The client accepts only canonical plain HTTP URLs on `127.0.0.1` or `localhost`. It rejects:

- non-loopback hosts;
- HTTPS or other schemes;
- credentials;
- invalid or out-of-range ports;
- query strings, fragments, or base paths;
- protocol-relative request paths.

Proxy routing is disabled and redirects are refused. Every POST includes the exact loopback base as `Origin`. JSON and audio responses are bounded, and JSON endpoints must return objects.

## Artifact trust boundary

A scene artifact is accepted only when:

- a completed child exposes exactly one expected scene WAV for the segment;
- the retained relative path is exactly `voice/<segment-id>-scene.wav`;
- the URL is the exact relative route under `/api/production/<project-id>/files/`;
- the retained SHA-256 is complete;
- downloaded bytes match that SHA-256;
- the WAV is uncompressed 48 kHz, mono, 16-bit PCM.

Markdown cannot supply an arbitrary URL, file path, or shell command.

## Assembly and publication

`assemble_wav()` reads each scene WAV into a bounded byte snapshot, validates and decodes that snapshot, copies its PCM frames in manifest order, and writes zero-valued frames for each recorded pause. There is no resampling or lossy re-encoding.

The receipt hashes the exact input snapshot used for decoding rather than reopening the path after assembly. This prevents a concurrent file replacement from making the receipt describe bytes different from those copied into the master. Final-output and completed-reuse hashes are streamed.

The receipt records:

- every input path, exact-snapshot SHA-256, sample count, and pause;
- total sample count and exact duration;
- final format and SHA-256;
- source record and manifest hash;
- exact Studio identity;
- global producer fingerprint;
- child project IDs and plan hashes;
- segment text hashes and pauses.

After assembly, source bytes are checked again before `receipt.json` is written. A changed source causes the new master to be deleted. A matching receipt and master hash makes later invocations return before constructing a Studio client.

A missing master can be rebuilt from valid retained child evidence. A changed completed hash or escaped output path is an integrity error, not permission to overwrite silently.

## Voice identity boundary

The first producer is the existing Kokoro CPU baseline because it already produces pinned scene WAVs. Its `speaker_id` is recipe metadata; the active bundle still uses the built-in `af_heart` voice.

Long-term producers fit the same conceptual interface:

```text
prepare(profile_id, delivery_id, stable lines) -> durable child project
start(project_id) -> explicit generation
inspect(project_id) -> state + hashed scene artifacts
```

The voice programme in #637 separates identity, delivery, pronunciation lexicon, dry take, mix treatment, resource cost, and human acceptance. The compiler and assembler remain producer-agnostic.

## Product evolution

### Aggregate project and UI (#638)

Promote the external manifest and state into a `spoken-brief` Production kind after the command contract is proven. Studio should preview spoken text and omissions, show child progress, expose the final player and download, and permit explicit segment replacement without hiding child evidence.

### Review-first discovery (#639)

Discover stable source hashes under a configured handoff root. Discovery creates a preview candidate, not TTS. Automatic generation remains a later explicit policy with an allow-list and kill switch.

### Listening exports (#640)

Keep PCM WAV as the deterministic master. Derive MP3 or M4B files and chapters from actual sample offsets through the configured owned FFmpeg executable. Playback position is mutable user state, separate from generation receipts.

### Transcript and pronunciation QA (#641)

Run independent ASR per segment and on the assembled master, retain diff evidence, and surface exceptions. ASR agreement is not a listening-quality or identity certificate.

## Verification boundary

The focused Python 3.12 suite currently contains 43 contracts and runs on Ubuntu and Windows. It uses a fake loopback Studio and generated PCM fixtures to exercise:

- Markdown projection, bounds, and stable identities;
- exact-byte source races before and after mutating boundaries;
- complete Studio workspace pinning;
- signed child plan and producer provenance;
- uncertain create and Start recovery;
- canonical project reconciliation after successful create and Start acknowledgements;
- fsynced state and locking;
- strict loopback transport and bounded response handling;
- project-confined artifacts and WAV validation;
- exact-snapshot input receipts, exact PCM assembly, atomic publication, streamed output hashing, and completed reuse.

Real inference remains a workstation proving step because CI has no pinned model bundle. A successful real run proves integration and performance only. Long-form identity, fatigue, pronunciation, and creative acceptance remain #637 and #641.

# Chaptered listening exports

This implements the archive/export and local playback-state core of #640. It
accepts completed schema-v2 runs from #636 and never creates a Voice project,
loads a model, invokes TTS, downloads tools, or uploads media. The aggregate
Studio UI/export button and browser playback wiring remain part of #638.

## One explicit action

Use the run directory printed by `speak-handoff.ps1`, containing `manifest.json`,
`receipt.json`, the assembled `*.spoken.wav`, and `segments/`:

```powershell
$run = 'C:\Users\you\Documents\handoffs\pack\_spoken\COMPRESSED-<manifest-prefix>'
python scripts/spoken_brief_exports.py "$run" inspect
python scripts/spoken_brief_exports.py "$run" export
```

`inspect` is read-only and returns the sample-derived chapter/transcript sidecar.
`export` without a format writes chapter JSON, FFmetadata, and a received export
record. It needs **no FFmpeg**. Neither operation needs the original Markdown or
a running Studio, but the retained manifest, receipt, master and segment WAVs
must still be present and mutually consistent.

For a listening copy, choose the actual FFmpeg executable you already own and
trust, rather than a shell wrapper or an executable discovered implicitly from
PATH. These commands pin its current bytes; they do not authenticate its vendor:

```powershell
$ffmpeg = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$pin = (Get-FileHash -LiteralPath $ffmpeg -Algorithm SHA256).Hash.ToLowerInvariant()
python scripts/spoken_brief_exports.py "$run" export --format mp3 --preset quick --ffmpeg "$ffmpeg" --ffmpeg-sha256 "$pin"
python scripts/spoken_brief_exports.py "$run" export --format m4b --preset high --ffmpeg "$ffmpeg" --ffmpeg-sha256 "$pin"
```

`quick` uses 96 kbit/s; `high` uses 192 kbit/s. Both are mono, 48 kHz **lossy**
listening derivatives. MP3 is the simple phone-listening copy; M4B is the
chapter-oriented audiobook copy for a compatible player. Chapter navigation
support depends on the receiving player. Neither replaces the retained PCM WAV.
The high preset is not lossless archival storage.

The result names an immutable directory under `<run>/exports/<full-export-id>/`:

```text
chapters.json       exact sample ranges, narrated text, hashes and provenance
chapters.ffmeta     global identity tags and sample-timebase chapters
receipt.json        request, tool/version/argv, decode evidence and file hashes
listening.mp3       only for an MP3 export
listening.m4b       only for an M4B export
```

The export ID binds the manifest, actual master hash, exact sidecar bytes, format,
preset and configured tool identity/commands. Copy the listening file to a phone
manually; there is no implicit sync or cloud player. Sidecars remain useful when
a container/player does not preserve or display all metadata.

## What is verified

The inspector validates strict JSON, the manifest's canonical digest, typed
segment/text/pause identities, source and Studio/project-plan/producer bindings,
and confined artifact paths. It then hashes the actual master and each segment,
compares every segment's PCM with the corresponding master samples, and verifies
every inserted zero-valued pause. Forged receipt sample counts cannot move a
chapter boundary. The master is streamed rather than loaded entirely into RAM.

A segment records its start, speech end, and end including its trailing pause.
A heading begins a chapter; contiguous pieces of one split heading produce one
chapter title. Introductory prose before the first heading becomes Introduction.
A chapter ends at the next heading's start, or the verified end of the master.
All offsets are integer samples at 48,000 samples/second. They are not estimates
from text length. Container timestamps can round to their own timebase; the JSON
retains the exact sample offsets.

Title, source hash, manifest hash, producer hash and master hash are placed in
FFmetadata global tags and a standard comment field. Full text and provenance
remain in JSON. The manifest and producer hashes bind the narration configuration
available in the existing coordinator; this does not invent a selected or
owner-approved voice profile while the #637 profile stack is still separate.

For MP3/M4B, the exporter checks the configured executable's SHA-256 before every
invocation and after encoding/decoding. It records the version output and exact
encode/decode argument arrays, uses no shell, restricts input protocols to local
files, and encodes an owned copy of the verified master. It decodes the derivative
back to PCM16 WAV and records its frame count and PCM hash. Decoded duration must
be within **2,400 samples / 50 ms** of the master, allowing codec padding. This is
integrity/duration evidence, not an audition, ASR comparison or speech-quality
score. The binary hash does not pin its dynamically loaded libraries, CPU,
environment, or vendor authenticity. No cross-build lossy bitstream determinism
is claimed; exact produced bytes are retained and hashed.

## Idempotency, failure and storage

An identical export verifies and reuses the existing directory without invoking
FFmpeg or TTS. Corrupt or partial existing exports are refused, not overwritten.
A changed master/configuration gets a different export ID; earlier valid exports
are left untouched. This exporter does not replace segments or retain old master
versions on behalf of the future #641 regeneration workflow.

New exports use the coordinator's exclusive `.spoken-brief.lock`, a private
same-parent staging directory, flushed files and one final directory rename.
Master/metadata/claim/parent identities and all staged bytes are rechecked before
publication. A normal failure kills/reaps the owned child and removes that
attempt's staging directory, preserving the master and earlier valid exports.
A crash can leave a stale claim or `.export-*` directory: inspect them before
manual cleanup. Never delete a live coordinator's claim. A failure after the
final rename may leave a valid export without an acknowledgement; retry verifies
and reuses it. Filesystem checks serialize cooperating local tools and reject
detected link/replacement races; they are not an adversarial-OS sandbox.

Limits: 240 segments, existing 32 MiB per-segment limit, 1 GiB master and decoded
WAV, 256 MiB derivative and tool, 2 MiB per JSON record, 1 MiB subprocess log,
600 seconds per encode/decode, and 15 seconds for tool version. Output/log limits
are polled and checked again after child exit, not OS disk quotas. At most 32
export directories/crash remnants are allowed per run; there is no silent
pruning. A lossy attempt temporarily needs space for the master copy, decoded
WAV, derivative and metadata. Existing files and crash remnants consume additional
space. Keep private handoff state, transcripts, generated audio and models out
of Git. JSON sidecars contain source paths and narration text.

## Playback state is separate

```powershell
python scripts/spoken_brief_exports.py "$run" playback
python scripts/spoken_brief_exports.py "$run" playback --sample 96000 --rate 1.25
python scripts/spoken_brief_exports.py "$run" playback --sample 96000 --loop 48000 144000
```

The first command reads a default without creating a file. Updates atomically
persist `playback.json`, bound to the manifest and master hash, without changing
the generation receipt or media. Positions/loop boundaries are integer samples;
48,000 samples equal one second. Rate must be 0.5–3.0. Position zero is unheard,
a position inside the audio is in-progress, and the exact total sample count is
completed. Invalid/stale state is refused, not silently rebound to different
audio. Detected external writes during persistence are not overwritten.

This is a durable CLI/integration contract, not an audio player. A later Studio
player must call it explicitly, use the chapter sample offsets, and decide when
to checkpoint progress. It should not run full archive verification on every
`timeupdate` event. Restarting Studio does not discard the file.

## Verification

```powershell
python -m unittest discover -s tests -p 'test_spoken_brief*.py' -v
python scripts/validate-repo.py
```

Synthetic fixtures cover actual coordinator-to-export handoff without additional
requests, precise PCM/pauses/chapters, tampering, stale identities, idempotency,
file confinement, claim contention, executable changes, timeout/log limits,
write failures and playback persistence. Installed FFmpeg tests perform real
MP3/M4B encode/decode. Installed FFprobe independently checks both containers'
chapter titles/start offsets (within one millisecond) and embedded manifest
identity. Those optional executable-dependent tests explicitly skip when the
tools are absent. No real voice-model, pronunciation or listening-quality
acceptance is inferred from synthetic fixtures.

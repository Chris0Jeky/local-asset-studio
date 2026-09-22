# Spoken Briefs in Studio: retained-archive listening and review

Open **Voice baseline → Spoken Briefs**, or `/spoken-briefs.html` on the existing
loopback Studio. This page reviews completed archives from the Spoken Brief CLI.
It is not a second executor, a source watcher, or the full aggregate Production kind.
There is deliberately no generation or replacement Start endpoint on this surface.

## Opt-in configuration

In your private `config/local.json`, add a `spoken_briefs` object containing only
`archive_root`, an **absolute local directory** containing your handoff packs. Keep
other existing configuration unchanged, then restart Studio. Do not commit that path.
Leaving this object absent or setting `archive_root` to null disables archive access.
Malformed configuration refuses these routes without preventing other Studio tools
from starting. Network roots, traversal, symlinks and Windows reparse points are refused.

**Discover archives** searches for manifest-bearing directories. A listed directory
is explicitly **not verified**: interrupted or damaged runs remain available for
inspection and a visible error. Discovery reads metadata, not audio, and does not
create jobs or write state. It checks at most 4,096 entries, 128 candidates and 20
levels; refusals are capped at 32. A limit produces a visible truncation notice, not
an assertion that the root was completely scanned. Narrow the configured root when
these limits are reached. Discovery order is bounded filesystem traversal, not a
complete sorted pagination protocol. Hidden directories and segment/export/QA trees
are not walked; nested replacement archives can be inspected where within the limits.

## Listen and save a bookmark

Select a directory and choose **Inspect selected archive**. Inspection uses the
existing archive verifier: source/manifest/receipt/producer bindings and the actual
master PCM, every segment and every pause must agree. Chapter positions use integer
48 kHz sample offsets. The original Markdown and a live TTS producer are not needed.

Play the master or one exact segment, seek to a chapter, or loop a chapter. None of
those actions writes anything. **Save position** explicitly saves the current
master-relative sample, speed and loop in `playback.json`. A segment-relative position
is converted using its verified start sample. Saving zero without a loop is unheard;
saving the master end is completed, as defined by the existing playback contract.
Use **Seek to saved position** to resume; opening an archive does not autoplay or seek.
WAV and chapter/transcript JSON downloads are read-only and identity-named. The
archival WAV is retained; MP3/M4B production remains the explicit CLI export operation.

The browser submits both the inspected archive digest and its prior playback digest.
The existing playback writer compares the latter under its ownership claim. A second
tab cannot silently overwrite a newer bookmark. Conflict or an unconfirmed response
locks additional saves for that archive until explicit inspection; no retry or rebase
is automatic. A read begun before a failed save cannot clear its uncertainty.
Closing/reloading a tab does **not** checkpoint playback automatically.

## Machine evidence is not your listening judgement

Choose an exact machine report ID and **Inspect report**. The server reconstructs
that report from retained evidence and the verified archive, rather than trusting a
stored score. The table and exception filter reflect that selected report only.
Missing transcripts, empty outputs, non-independent alignment and budget-limited
comparison remain distinct states. No machine report is selected automatically.

Choose an exact owner record to inspect it separately. Record ordering is not a
“latest” decision or an acceptance policy. The form creates a new immutable record
with explicit target/audio identity, reviewer, reason and four independent findings:
pronunciation, omissions/repetitions, delivery and fatigue. It can optionally link
the inspected machine report; that link does not convert word agreement into human
acceptance. **Request a replacement take** records `replace` only. Follow the
[replacement CLI workflow](SEGMENT-REPLACEMENT.md) to separately prepare/start a take.
No old record, audio, recipe or generated receipt is overwritten by a review.

Unsaved notes stay in this tab, keyed to the exact archive, while switching views;
they are not restart recovery. At most 64 drafts are retained. Capacity blocks a
switch until an explicit discard, rather than silently evicting notes. A late save
response never resets newer typed notes or attaches itself to another archive.
Use **Discard unsaved notes** to deliberately clear the current in-tab draft.

## HTTP and filesystem boundaries

The extension is composed at `studio_prompt.http_extension.extend_handler`, using
the existing server, Host checks and port. Reads are GET; only `/bookmark` and `/review`
accept POST. Mutations require exactly one local Host and matching HTTP Origin,
bounded unambiguous Content-Length and UTF-8 JSON. Duplicate fields, non-finite
numbers, lone surrogates, extra fields and alternate transfer framing are refused.
The request body is capped at 16 KiB, with a two-second read timeout.

Paths are canonical relative archive keys under the private root; audio targets and
QA IDs cannot be arbitrary file paths. Media is served from the same checked handle
that was hashed. Single byte ranges and HEAD are supported; invalid/multiple ranges
receive 416. A failure after audio headers closes the response, never appends JSON to
WAV bytes. No remote redirects, uploads, new media server or TTS client is introduced.

Inspection and media requests reverify archive evidence and PCM. This intentionally
costs disk reads, potentially substantial for long briefs or repeated range seeks.
There is no cross-request verification cache or per-timeupdate server call. Existing
master/segment bounds remain; no claim of OS disk quotas or bounded total concurrent
server memory is made. Cooperating-writer checks detect specified replacement/link
races; they are not a sandbox against a hostile same-user process or OS. Hashes and
reviewer IDs provide retained identity, not authentication or subjective certification.
Record lists inspect at most 256 entries per group, with visible refusals/truncation.
Stale ownership claims remain subject to the parent CLI's explicit inspection policy.

## Verification and programme boundary

The regression suite uses synthetic PCM and inert archives. Real HTTP tests cover
origin/framing, bounded reads, ranges, stale writes and exact immutable reviews. Node
executes the shipped request-ownership state machine. The separate Ubuntu/Windows
Chromium lane drives the shipped page on the actual composed handler, with no worker.

This supplies the retained-listening/review surface of #638/#640/#641, not all of those
issues. Source preview, first-generation Start/progress, aggregate Production records,
watch-inbox actions, lossy-export buttons, independent ASR execution and replacement
reconciliation controls remain separate work. The #637 profile stack and owner-only
originality, pronunciation and long-listening/fatigue qualification remain unchanged.

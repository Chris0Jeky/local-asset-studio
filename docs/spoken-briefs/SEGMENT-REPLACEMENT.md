# Replace one Spoken Brief segment without losing the old take

Part of #641, stacked on the transcript/owner records in #707 and the archival
inspector/exports in #700. This is an explicit CLI coordinator using the existing
Voice baseline and Production worker. It is not another inference queue or the
#638 Studio aggregate/browser surface.

## Four separate actions

1. Listen and record an owner `replace` judgement for one exact segment/audio
   hash using `spoken_brief_qa.py review`. A machine mismatch alone cannot prepare
   a replacement. An owner can also reject a take whose transcript matched.
2. **Prepare** a stable request ID, optionally with exact corrected spoken text.
   Preparation writes a local request and initial state, but performs no network
   requests, project creation, model loading or synthesis.
3. **Start** explicitly admits one Voice child through the original Studio
   workspace and producer recipe. Later calls inspect the retained child rather
   than creating or starting another one after an uncertain mutation.
4. **Assemble** uses the verified cached take and every unchanged parent segment
   to publish another self-contained WAV archive. It cannot invoke TTS.

```powershell
$run = 'C:\handoffs\example\_spoken\COMPRESSED-<manifest-prefix>'
$review = '<owner-review-sha256>'
python scripts/spoken_brief_replacement.py prepare $run pronounce-v1 `
  --segment segment-0002 --review-sha256 $review `
  --text 'Local asset studio has seventeen checks.'
python scripts/spoken_brief_replacement.py inspect $run pronounce-v1
python scripts/spoken_brief_replacement.py start $run pronounce-v1
python scripts/spoken_brief_replacement.py assemble $run pronounce-v1
```

Replace placeholder identities with actual retained hashes. `Start` is the only
one of these commands that can create/start a Voice project. The endpoint is
pinned to the parent archive's loopback Studio identity; there is no arbitrary
server override or automatic workspace migration. Keep that Studio running at
its retained address for generation/recovery. Assembly and completed replay do
not need Studio or the original Markdown file.

The optional `--text` is an explicit pronunciation/text projection override,
not an edit to the Markdown. Omit it to repeat exactly the same text/recipe.
The latter may yield the same audio with a deterministic producer; a new attempt
is not a guarantee of a better take. A QA comparison lexicon is **not** silently
applied to TTS. Supply and review the actual intended replacement words explicitly.
The original and replacement texts/hashes are both retained.

## Identity and admission

A request binds to the parent's manifest, exact manifest-file bytes, assembly
receipt, source, producer and master hashes; the old segment ID/audio/text; the
speaker metadata, exact Studio workspace; and the explicit owner review. It also
retains the selected text/hash and unchanged pause. The request digest includes
its stable caller-selected ID. Reusing that ID with changed content fails rather
than overwriting the earlier request. Exact repeat preparation is read-only.

Only one unresolved request for the same segment is admitted in an archive.
A different request ID does not bypass an uncertain Create, attempted Start,
terminal child or unresolved preparation. A retained verified completed take
settles that request; another deliberate request can then be prepared. A new
revision can itself be reviewed and used as a parent. It retains all earlier
revision directories instead of replacing their media or review records.

The current route stays within the existing `voice-baseline` recipe. Signed child
plan and producer fingerprints must match the exact selected words, line ID,
speaker metadata and original producer. A changed producer, workspace, plan or
artifact blocks the operation; there is no implicit model/voice fallback. This
slice does not integrate or claim acceptance of the separate #637 profile stack.
`speaker_id` remains metadata, not a claim of cloning or custom voice identity.

Admission bounds are 32 retained request-directory entries per parent archive,
the existing 240-project archival history ceiling, the existing 520-character
conservative line limit, 210 words per line, and 100,000 total narrated characters.
An override that would exceed the full-brief text limit is refused before request
writes. IDs are bounded portable lowercase identifiers; Windows reserved device
names and paths are refused. Source, state and artifact reads remain bounded.
No history is automatically pruned when a limit is reached.

## Recovery states

| Retained state | What another Start call may do |
| --- | --- |
| `prepared` | Explicitly create one child, after revalidating archive/workspace/request/state. |
| `creating` / `create-unconfirmed` | Refuse. A lost Create result cannot authorize another child. |
| `create-rejected` | Refuse; retain the rejection for inspection. |
| `created` | Canonically inspect the saved child. If still planned and no Start was attempted, explicitly Start it. |
| `starting` / `start-unconfirmed` | Observe that child. A `planned` response does not authorize another Start. |
| `observing` | Observe the same child until complete, terminal, changed, or the polling deadline. |
| `start-rejected` / `terminal` | Refuse resubmission; retain the exact child/observation. |
| `artifact-verified` | Verify and reuse the cached take locally; no Studio requests. |

Creation intent is flushed **before Create**. Returned child identity is flushed
**before Start**, and Start intent is flushed before its POST. A crash between
intent and response therefore cannot revert to a fresh submission. A known child
whose Create acknowledgement was saved but whose canonical read failed can be
inspected again. Successful response bodies are acknowledgements, not substitutes
for canonical project reads. Child plans/artifacts are checked again after the
actual download before the take is published.

If a successful Create cannot persist its returned ID, the earlier `creating`
intent survives and blocks another Create. If take bytes were cached but their
state receipt could not be saved, a later explicit Start invocation reconciles
the already-completed known child and reuses those bytes without another Start.
Once `artifact-verified` is durable, a missing/corrupt cache fails locally; it does
not silently download, synthesize, or select another take.

The default polling interval is one second (allowed 0.01–30 seconds); the polling
deadline is one hour (allowed 1–86,400 seconds). Values must be finite numbers,
not booleans/NaN/Infinity. Transport calls retain their own bounded timeout, so
the polling deadline is not a hard wall-clock process quota. Deadline expiry
retains the active child; a later invocation observes that same ID.

There is no command in this slice that clears uncertain/rejected/terminal intent,
steals a stale claim, kills a worker, or reconciles an unknown Create to a manually
chosen project. Inspect Studio and the retained request/state before any manual
repair. Deleting a state file or changing its status to `prepared` is not a safe
retry procedure. An explicit reconciliation protocol/UI remains future work.

## Files and immutable reassembly

For request `pronounce-v1`:

```text
<parent-run>/
  manifest.json, receipt.json, segments/, archival WAV, exports/, qa/  (unchanged)
  replacements/pronounce-v1/
    request.json      exact source/review/text/recipe binding
    state.json        retained mutation intent, child ID, signed plan, artifact
    take.wav          exact verified replacement scene WAV
    result/
      manifest.json
      receipt.json
      replacement.json
      segments/       byte-identical copies of unaffected takes + replacement
      COMPRESSED.spoken.wav
```

The result is a new manifest identity with explicit replacement lineage. Its
source hash still names the original Markdown; the override and prior text remain
visible in the retained request. Its receipt preserves parent project/plan IDs
and adds the new child. `replacement.json` binds the parent directory/request,
old and reused hashes, signed child plan, replacement artifact and new master.
Loading/reusing a result reconstructs that expected lineage and receipt rather
than trusting a self-rehashed replacement claim.

Every unchanged segment is copied byte-for-byte, not resynthesized or reencoded.
PCM is assembled in the original order with the exact original pauses. A longer
replacement moves later chapter offsets by its actual sample-count difference;
prior offsets are unchanged. Existing chapter/export tools accept the new
self-contained archive. New QA/review/playback state is separate; no owner
acceptance or current-listening selection is automatically copied or inferred.
Earlier exports remain valid historical derivatives of the earlier master.

The existing archive inspector validates the staged revision against actual PCM.
Final receipt paths are bound to the destination before one directory rename.
Every staged file must still match its expected verified content before/after
final flushing. A failed attempt preserves the old parent and verified take;
assembly can be repeated without TTS. An existing partial/corrupt result is
refused, never overwritten. The WAV master is limited to 1 GiB and total staged
scene/master bytes to 2 GiB; these are checked byte budgets, not OS disk quotas.
Nested revision paths and available local disk remain practical limits.

## Filesystem and evidence boundary

The parent run claim serializes cooperating preparation, generation and assembly
operations. State transitions use same-directory flushed temporary files and
atomic replacement, comparing exact prior file identity/content before commit.
External request/state changes, link/reparse ancestors, malformed/ambiguous JSON,
Boolean schema aliases and inconsistent lifecycle markers fail closed. The claim
is an explicit ownership file, not an automatically recoverable OS-held lock.
After a process dies, inspect it and establish that its owner is no longer active
before manual removal; no timer is treated as proof of death.

Take publication is no-overwrite through an atomic hard link; a filesystem that
does not support it fails visibly. Prepared request/state and complete revisions
are published by directory rename under the owned parent claim. Failure/crash can
leave temporary directories or a completed artifact before acknowledgement.
Only owned attempt staging is cleaned on handled failure; ambiguous crash state
is retained for inspection. These checks protect cooperating tools and detect
specific races; they are not a sandbox against an adversarial same-user process
or privileged OS. Hashes and reviewer IDs are not authentication.

Offline tests use the actual coordinator against an inert loopback fixture and
synthetic PCM. They cover response loss, pre-POST intent durability, no-repeat
recovery across request IDs, producer/workspace drift, post-download plan drift,
external edits during identity reads/fsync, late staging changes, corrupted
cache/state, quotas, measured sample shifts, second revisions, export and owner
review compatibility. No real model inference, original-voice qualification,
ASR correctness, pronunciation, fatigue or subjective acceptance is established.
Keep private handoffs, transcripts, review files and generated audio outside Git.

The #638 aggregate Studio UI, playback-linked review controls, native ASR runner,
explicit uncertain-request reconciliation and real long-form listening remain
separate work. No umbrella issue is closed by this CLI slice.

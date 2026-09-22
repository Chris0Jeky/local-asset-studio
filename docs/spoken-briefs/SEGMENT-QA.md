# Spoken Brief transcript and listening review

Part of #641; based on the archive inspector in #700, itself stacked on #688.
This is the offline QA/owner-record core, not the Studio aggregate UI or an ASR
executor. No model is loaded and no network/Production request is sent by these
commands. An ASR result, a listening judgement and permission to generate are
three separate things.

## Workflow

Use a completed `_spoken/<source>-<manifest>/` archive. Its original Markdown
need not still exist. The inspector checks retained manifest/receipt identities,
every segment's WAV hash and actual PCM, the actual silence between segments,
and the entire assembled master before exposing the archive to QA.

1. Obtain independent transcripts using a separately configured local ASR tool,
   or transcribe manually. Record the actual producer identity and hashes.
2. Import the bounded JSON evidence below with `report`.
3. Use `show-report` to inspect substitutions, insertions, deletions, empty or
   unaligned outputs and the `review_targets` list. Missing transcripts are
   visible; absence is never interpreted as a pass.
4. Listen to suspect segments and record an explicit owner decision with `review`.
   These records do not change a machine report, audio or generation receipt.

```powershell
$run = 'C:\handoffs\example\_spoken\COMPRESSED-<manifest-prefix>'
python scripts/spoken_brief_qa.py report $run .\transcripts.json --lexicon .\lexicon.json
python scripts/spoken_brief_qa.py show-report $run <report-sha256>
python scripts/spoken_brief_qa.py review $run segment-0002 `
  --audio-sha256 <exact-segment-wav-sha256> --decision replace `
  --reviewer owner --reason 'The project acronym was unclear.' `
  --pronunciation needs-work --delivery acceptable `
  --report-sha256 <report-sha256>
python scripts/spoken_brief_qa.py show-review $run <review-sha256>
```

The angle-bracket values are placeholders to replace with actual retained
identities, not literal command arguments. The run path is an example only.
`report` and `review` are explicit record writes; `show-*` is read-only.

## Transcript input

The exact top-level keys are `schema_version: 1`, `manifest_sha256`,
`master_sha256`, and `observations`. The manifest/master identities must match
this archive. `observations` may contain any subset of segments plus one optional
`master` observation. Duplicate targets and unknown fields are refused.

Each observation contains exactly:

| Field | Contract |
| --- | --- |
| `target` | A stable segment ID such as `segment-0002`, or `master`. |
| `audio_sha256` | Exact WAV-file hash of that segment or the assembled master. |
| `text` | Independent transcript, including the empty string when no words were recognized. Never substitute the intended text for missing evidence. |
| `method` | `independent-asr`, `manual-transcript`, or `forced-alignment`. |
| `producer` | Object with `id`, `revision`, `runtime_sha256`, `configuration_sha256`. |

Producer `id` is a stable lowercase identifier; `revision` records the exact
model/runner revision being attributed. For ASR/alignment, both hashes must be
full SHA-256 values. For manual transcription, both must be `null` and the
producer identifies the transcriber/manual protocol instead of inventing runtime
evidence. These are **declared provenance fields**: importing them neither runs
nor independently authenticates the producer. An actual pinned ASR execution
adapter and native workstation evidence remain separate work.

`forced-alignment` is retained as `not-independent`, with no word-error score,
even when its text equals the intended script. Alignment against supplied words
cannot establish that those words were independently recognized.

## Normalization contract v1

The exact original intended and observed text hashes remain in the report.
Comparison uses Unicode NFKC, case folding, straight/curly apostrophe equivalence,
and punctuation tokenization. Apostrophes within words are retained; contractions
are not expanded or silently made equivalent to other words. Slash, backslash,
plus, percent and a leading numeric minus remain meaningful spoken tokens.

ASCII/full-width decimal digits are converted to English cardinal words up to
999,999, without inserting `and`; leading-zero and longer integers are read as
individual digits. Decimal fractions use `point` plus individual digits. Standard
three-digit grouping commas are recognized. This is a narrow English comparison
policy, **not** multilingual number, date, version, path or pronunciation
understanding. Differences outside these rules remain visible for review.

An optional lexicon has exactly `schema_version: 1`, a stable `id`, positive
integer `revision`, and `entries` containing `written`/`spoken` strings. It permits
up to 128 entries, each side 1–200 characters and 1–32 normalized tokens. Duplicate
normalized source phrases and empty expansions fail closed. A single
longest-token-match pass is applied to each side, without recursive rewriting.
The full lexicon and canonical hash are retained in each report. Changing its
revision/content creates a different report; it never rewrites Markdown or audio.
Aliases deliberately affect comparison and must be reviewed: broad aliases can
hide word differences even though the raw evidence remains inspectable.

Word alignment is exact Levenshtein distance with deterministic diagonal,
deletion, insertion tie order. Each edit retains normalized word indexes and the
expected/observed word. The score is `(substitutions + insertions + deletions) /
expected_words`; it can exceed 1 when there are many insertions. It is not a voice
quality score. Empty expected text has no score.

Bounds: 200,000 input characters, 16,000 normalized words per comparison,
4,000,000 alignment cells. Exact equal transcripts take a linear fast path.
An unequal pair above the cell budget is `unaligned-budget`, with no edit counts
or score; it is never truncated and called successful. A typical brief can be
reviewed per segment even when its full-master comparison reaches this bound.

## Separate owner review

A review is bound to the exact archive, target, text and audio hash. It names the
reviewer, reason and explicit `keep`, `replace` or `unreviewed` decision. Findings
for pronunciation, omissions/repetitions, delivery and fatigue are independently
`not-reviewed`, `acceptable` or `needs-work`. A linked report is optional but must
be a valid report for this exact archive. A machine match never writes a human
judgement. The owner may intentionally retain a take with a machine mismatch.
Reviewer IDs are attribution, not authentication.

A `replace` decision is evidence for an explicit replacement workflow, not a
queued job. This module does not create, start, cancel or retry anything. It also
does not select a voice profile, certify identity/naturalness, or promote a default.

## Persistence and recovery

Records are content-addressed JSON under `qa/reports/<hash>.json` and
`qa/reviews/<hash>.json`. Existing records are never rewritten. An exact replay
verifies bytes and returns the same record without touching its modification time.
A changed transcript/lexicon/decision creates another record, preserving earlier
reports, takes and receipts. No "latest" pointer or automatic acceptance is inferred.

Each group permits 128 directory entries, with 2 MiB per JSON document. Capacity
refusal never prunes history; exact replay works when full. Import rejects
ambiguous JSON (duplicate keys, NaN/Infinity), invalid UTF-8, malformed bindings,
linked ancestors and non-regular files through the existing archive boundary.
Loading a report reconstructs its result from retained evidence/lexicon and the
verified archive, rather than trusting a locally rehashed `match` flag. Canonical
JSON comparison distinguishes booleans from integer schema versions.

Writers take the existing run claim, flush a same-directory temporary file,
recheck its exact bytes, archive and directory identity, then publish using an
atomic no-overwrite hard link. Unsupported hard links fail visibly rather than
falling back to overwriting a record. A crash before publication can leave a
private temporary file; after publication it can leave a complete record and a
stale claim. Inspect the claim and confirm its owner is no longer active before
removing it. No process is killed or claim automatically stolen. Existing exact
records can be inspected/replayed without claiming the run.

These are cooperating-tool durability/integrity guarantees on local filesystems,
not a sandbox against a hostile same-user process, privileged OS or a party that
can replace all evidence. Keep private transcripts/reviews outside Git.

## Verification and next integration

`python -m unittest discover -s tests -p 'test_spoken_brief_qa.py'` covers word
edits, numbers/punctuation, lexicon identity, complexity bounds, empty and missing
transcripts, attributed forced alignment, manual evidence, immutable replay,
quotas, corruption, boolean aliases, link/race refusal and publication failure.
The integration fixture creates an archive through the actual existing coordinator
and verifies that QA sends no additional HTTP requests.

The next slice supplies explicit single-segment replacement and no-inference
reassembly. The #638 Studio aggregate/listening surface, a pinned ASR execution
adapter, playback-linked review controls and real 5–10 minute owner listening
remain outstanding. No synthetic test establishes subjective voice acceptance.

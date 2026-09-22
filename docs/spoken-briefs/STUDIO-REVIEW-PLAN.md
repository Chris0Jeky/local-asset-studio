# Spoken Brief archive review implementation plan

Goal: make the existing verified archives listenable and reviewable in Studio, without
turning reads, playback, bookmarks or a `replace` judgement into inference approval.
The user requested continuation of #635–#641 through tested draft PRs.

## Design and boundaries

Reuse #700 archive inspection/playback and #707 immutable QA records. Compose a small
`studio_spoken` HTTP extension at the existing handler seam, on the existing port.
One optional, absolute `spoken_briefs.archive_root` in private config confines access.
No second server, worker, watcher, model install, Production kind or generation route.
An explicit bounded archive scan lists unverified directories; selection verifies PCM.
Every subsequent operation names the exact chapter/archive digest. Mutations enforce
that identity inside the existing operation, not only in a preliminary HTTP read.
Playback saves additionally compare the previous state digest under the existing claim.
The browser checkpoints only with an explicit Save position action. It never writes on
page load, timeupdate, pause, navigation or reload. A failed save retains the form and
requires inspection; it is never retried or rebased automatically.

Machine reports are selected explicitly from retained IDs, not sorted into a fictitious
"latest" authority. Listening judgements remain separate immutable records. A saved
`replace` judgement does not prepare or start a replacement. The page provides master
and segment playback, measured chapter seeks, WAV/JSON downloads and owner review.

## Sequential tasks and files

- [x] Add causal guards in `scripts/spoken_brief_archive.py`, `spoken_brief_exports.py`
  and `spoken_brief_qa.py`; test stale bookmarks, stale archive and pre-write races in
  `tests/test_spoken_brief_web_guards.py`. Existing CLI calls remain compatible.
- [x] Add `studio_spoken/core.py` for confined archive/record access; use the existing
  captured-file and PCM verifier. Test disabled config, bounded scans, links, changed
  archive IDs, immutable review replay and read-only observations with real fixtures.
- [x] Add `studio_spoken/http.py` and compose it in `studio_prompt/http_extension.py`.
  Test real HTTP strict framing/JSON, same-origin checks, fixed route schemas, native
  range playback, bad ranges, confined downloads and zero generation calls.
- [ ] Add `app/static/spoken-briefs.html`, `.css`, `.js`; link from Voice baseline.
  Test actual Chromium against the real handler: selection, chapter/segment playback,
  stale requests, by-exception report display, bookmark/review persistence and reload.
- [ ] Add Ubuntu/Windows browser workflow and operator documentation. Run full suite,
  validator, fresh focused tests, byte/tree publication checks and exact-head CI.

## Review focus

1. A late response after selecting another archive must not replace its player or form.
2. Two tabs must not silently overwrite each other's bookmarks; conflict stays visible.
3. Same segment audio in a changed archive cannot launder a stale review attachment.
4. A pathname must never be reopened unchecked after verification for media streaming.
5. Missing/corrupt QA evidence must be distinct from a matching machine transcript.

## Deferred acceptance

#638 remains open for source preparation/preview, aggregate Production registration,
explicit first-generation Start/progress and uncertain-child reconciliation. #639 remains
open for the Studio discovery inbox. #640 still has CLI lossy exports; this slice supplies
archive playback and downloads, not a browser FFmpeg launcher. #641 remains open for
live independent ASR, replacement controls and real long-form listening evidence. #637
profile integration and subjective acceptance stay with their separate stack/owner.

## Execution record

The writer boundary is isolated in PR #748. This Studio slice builds on its exact
head, preserving #714's pre-POST recovery correction. No generation code is copied.
Local regression-first checks cover 5 writer guards, 18 facade cases, 13 real HTTP
cases and 8 Node request-ownership scenarios. The full combined suite passed 3,466
checks (21 skips). A renderer-only Chromium fixture also inspected the real page and
saved a synthetic owner record without JavaScript errors; it is not native HTTP/audio
evidence. The local managed Chromium refuses loopback navigation, so the separate
GitHub Actions Ubuntu/Windows lane is the native browser authority.

Adversarial review corrected final root checking on discovery-quota exits, archive
changes during record enumeration, lone-surrogate paths, and delegation of unsupported
HEAD requests. The final diff removes the temporary read-only source snapshot workflow.

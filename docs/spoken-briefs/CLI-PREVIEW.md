# Preview a handoff without preparing or generating speech

`preview` exposes the existing deterministic compiler through the existing Spoken Briefs CLI:

```powershell
python scripts/spoken_brief.py preview <pack-directory>
```

The directory uses `COMPRESSED.md` first, then `INDEX.md`, like `plan` and `run`. An explicit Markdown file is also accepted. Output is the existing compiler manifest: exact source-byte hash, selected profile, spoken segments and omission counts. No extra producer/consumer schema is introduced.

Inspect the segment text before generation, especially failed checks, numbers and units. Compilation is a Markdown projection, not a factual comparison against REPORT. Omission counts describe compiler transformations, not proof that an upstream compressed summary is complete.

The command reads the current source and selected profile. It does not create `_spoken`, acquire a generation claim, replace an existing manifest, inspect or repair retained run state, call Studio, or submit inference. A successful preview does not mean existing audio is valid or that the next run will succeed. Source or profile changes after preview require a fresh inspection.

`--profile-id`, `--delivery-id`, `--profile-registry` and the metadata-only `--speaker-id` use the current resolver. Preview can describe a valid but non-executable profile; `run` independently requires an executable binding. The default remains the existing Kokoro control with `calm-brief`. Execution-only endpoint/poll/deadline arguments are rejected by preview.

Output includes source text and an absolute source path. Keep it local/private, like the handoff itself. Do not redirect stdout onto a source, retained manifest, receipt or other existing evidence file: shell redirection occurs before Python can protect those bytes. To retain a preview, choose a separate new file through an operator-controlled path.

`plan` still writes its planning manifest. `run` still owns generation and recovery. This change does not alter Action Stack bundles, browser playback, narration admission, Notion indexing, voice acceptance or social publishing.

## Verification

```powershell
python -m unittest discover -s tests -p "test_spoken_brief_cli_preview.py" -v
```

Routing tests cover argument forwarding, success/failure output and unchanged plan/run controls. Real compiler tests cover CRLF source identity, caveat retention, code omission, fallback, invalid UTF-8, and byte-identical retained uncertain state. They use synthetic text and the checked-in profile catalogue, not a speech model or owner listening acceptance. See the implementation PR for executed results and remaining native checks. Refs #635 and the provenance architecture in #851.
## Studio source preview

The existing **Spoken Briefs** page also previews a handoff within the opt-in
`spoken_briefs.archive_root`. Enter a relative pack path (or `.` for the root),
or an explicit `.md` path, then choose **Preview narration**. A folder chooses
`COMPRESSED.md`, then `INDEX.md`. Selection and navigation do not read the source.

The page uses the same compiler manifest and default `kokoro-af-heart-control-v1`
profile with `calm-brief` delivery as the CLI. It shows the exact source byte hash,
ordered segments, omission counts, profile status, and segment/batch counts.
No duration is estimated. The preview does not check engine availability, establish
run readiness, or infer voice acceptance. Use the CLI when selecting another profile.

Source reads are bounded to 512 KiB, strict UTF-8, and the configured local root;
traversal, symlinks, and Windows reparse points are refused. Source and retained
archive files are not written. An in-flight source change is refused; a completed
preview remains a snapshot until another explicit preview. Changing the path or
refreshing source access clears the snapshot and discards delayed results. Paths
and narration remain local and are not saved in browser storage.

## Studio first narration

After reviewing the source, omissions, baseline profile and destination, choose
**Start narration**. Admission compares the exact preview, including its source,
profile, configured root and producer configuration. It retains one
`studio-start.json` beside the existing compiler manifest and coordinator state
under the displayed `_spoken/` directory. The existing CLI coordinator creates
Voice baseline children and explicitly starts them through Production; there is
no additional inference queue. The built-in Kokoro control is not an accepted
custom voice. Producer bundle/runtime checks still belong to Voice baseline.

The progress section shows prepared, running, partial, uncertain, blocked or
completed evidence, exact child IDs and links, plan/producer hashes, and failure
messages. **Inspect completed WAV** opens the existing hash/PCM verifier, player
and download controls. Discovery also finds incomplete manifests; **Follow
selected narration** opens the retained aggregate for a run started here.

The page address retains the relative run key and root identity before sending
Start, so a lost browser reply or reload can read the same run. Repeated Start
requests for that identity return retained state. **Refresh progress** and reload
only read. **Recover retained progress** runs the coordinator in observation-only
mode: it may collect already completed children and assemble their verified PCM,
but never posts Create or Start. A missing child, ambiguous Create/Start, failed
child or stale coordinator claim remains visible and blocked; inspect the exact
child/evidence rather than submitting a replacement. A process restart does not
remove a stale claim. Completed segments and prior masters are preserved; an
unreceipted master requires inspection before replacement. Source/profile changes
require a new preview and do not rewrite the earlier manifest or listening output.

This first-run slice leaves #638/#635 open. Remaining scope includes registration
in the general Production project index, selected custom/accepted-profile
integration and owner listening qualification, explicitly continuing never-created
batches after an interrupted run, replacement/reconciliation controls, browser
lossy exports, independent ASR and source-watch actions. No duration estimate,
native-engine qualification, model licensing or voice acceptance follows from
synthetic HTTP/browser fixtures.

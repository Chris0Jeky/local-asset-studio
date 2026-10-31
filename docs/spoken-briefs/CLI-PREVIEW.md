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

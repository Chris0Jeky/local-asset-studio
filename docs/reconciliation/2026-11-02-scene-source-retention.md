# Retain scene inputs across an interrupted commit acknowledgment

2 November 2026. This is the bounded #1884 follow-up to the parked #1883 source
introduction branch. It does not introduce that feature into main or qualify
the whole feature for main.

## Exact source boundary

The GitHub connector confirmed `codex/studio-scene-source-revisions` still points
to `ea63046155f23ac0c7ef23230c00100d39d37db5`, tree
`bc2663fccdd3b439ce73fbde0265d68f72c84422`. Reconstruction reused verified local
Git blobs and fetched 43 exact text blobs through the connector. All 4,719
tracked blobs and the complete tree matched before edits. Raw blob line endings
were preserved. The isolated synthetic local base is
`43e9e86f2e46e329b1d6c9efed48e2967bebfac2`, with that same tree.

The original branch, its evidence and the
[parked qualification record](https://github.com/Chris0Jeky/local-asset-studio/issues/1883#issuecomment-6550238315)
remain unchanged. This separate source-level regression pass does not supersede
the earlier failed and interrupted full qualification attempts.

## Cleanup rule

`AVProjects._source_command` can lose acknowledgment after SQLite commits the
new document and event. Its local `committed` flag alone cannot justify deleting
the copied input on an exceptional exit.

Before deleting an unacknowledged copy, the command now holds the Production
lock and opens a fresh SQLite connection with `mode=ro`. One consistent query
examines both the current document and all retained revision documents. A
reference in either keeps the input, including after a restore removes it from
the current document. Missing, malformed, oversized or unreadable evidence also
keeps it. Inspection is bounded by the existing 500-revision budget and a
16 MiB metadata budget. The original command failure is preserved.

The observer cannot create a missing database or recover a hot rollback journal
to authorize cleanup. Existing path/link checks still apply. An ordinary
rollback with readable, unreferenced history can still remove its partial or
failed copy; retained uncertain copies continue to count toward existing input
budgets. No automatic retry, adoption or recovery is added.

## Causal checks

The unchanged parked source passed its existing 11 source-revision tests in
4.133 seconds. Five new regression methods then produced seven failing cases:
committed add and replace operations lost their input; a committed historical
reference also lost it after restore; three malformed-history shapes and an
unreadable hot database incorrectly authorized deletion. The real pre-commit
rollback control already passed.

The commit-boundary fixture allows the real SQLite context to commit and close,
then raises `KeyboardInterrupt` before the command sets `committed=True`.
Fresh database reads prove revision 1 and two retained events. The history-only
case commits a restore before the interruption and proves the older revision's
input survives.

The hot-database fixture uses a finite child process with a two-page SQLite
cache. It spills a 128 KiB update and exits without commit, leaving SQLite's
actual rollback journal. Read-only access raises `SQLITE_READONLY_ROLLBACK`;
the database and journal bytes stay identical through cleanup observation, and
the input remains. Only explicit fixture cleanup afterward opens a writable
connection and proves the committed row is recovered. The child has a
10-second timeout and is fully reaped.

After correction, the five new tests passed in 1.219 seconds. The complete
`test_av_source_revisions.py` module passed **16 tests in 7.187 seconds**, with
no skips. It includes existing partial-copy, changed-source, two-client CAS,
unread HTTP reply, immutable-history and frozen-render-record checks.

```sh
python -m unittest discover -s tests -p 'test_av_source_revisions.py' -v
python -S scripts/validate-repo.py
```

The validator passed with site packages disabled: 94 graphs/bindings, 189 pinned
assets and 164 LoRA names. No installed media tool, render, generation, browser
journey or full-suite feature qualification was run for this correction.
Existing `HUMAN_TODO.md` choices and the broader #1883 acceptance remain open.

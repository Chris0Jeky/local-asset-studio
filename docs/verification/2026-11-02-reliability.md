# Startup, migration and Spoken Brief reliability

This maintenance slice follows the recorded-source comparison PR #1876. It uses
the uploaded source snapshot reconciled against GitHub main, including the
Blender compatibility merge at `84b66fba0da1b70be895caf8ec3831cb0a9055bd`.
GitHub PR checks and artifacts remain the authority for the final published head.

## Picture acceptance in privacy moves — #1900

Migration previews now enumerate retained acceptance records, including withdrawn
records and records attached to siblings in the same run closure. The existing
dialog names them as acceptance records that stay. Uses, notes and scene-brief
criteria remain in the Workspace database, hidden while the asset is Private and
visible again when it returns to Regular. Migration never changes the acceptance
decision itself.

Acceptance writes do not bump asset metadata revisions. Each planned acceptance
therefore binds a digest of its complete retained row. The publication transaction
checks both digests and exact membership before reclassifying assets. Inserts,
withdrawals, restores and deletions before apply or during copy invalidate the
preview. Notes and criteria are hashed, not returned as preview text.

Five regression methods failed before the implementation, including twenty
failed assertions/subcases. The corrected migration planning, apply and recovery
group passed 64 tests; the preview wrapper passed. Independent review also checked
legacy-journal recovery: it rolls back uncommitted work or cleans up committed
work, and does not call the new publication path on an older journal.

## Hot SQLite recovery evidence — #1799

The remaining test creates an actual hot rollback journal with a finite child
process and a 128 KiB uncommitted update. SQLite reports
`SQLITE_READONLY_ROLLBACK` on a read-only connection. Planning reports
`production_unreadable`, upload-consumer discovery returns unknown, and both the
database and journal stay byte-identical. A later explicit writable fixture read
recovers the original row, proving that the journal is valid recovery evidence.
This adds regression coverage for existing fail-closed production behavior.

The focused regression and all 25 planning tests pass. Earlier overflow,
non-iterable reference, missing-database and locked-database fixes were already
present; they were not reimplemented.

## Runtime patch observations — #1905

The desktop launcher invokes a bounded, read-only hash checker before its existing
startup admission steps. Recorded patched bytes stay quiet; original, unexpected,
missing, unreadable and invalid evidence have distinct warnings. No runtime source
is imported or changed. A diagnostic failure warns without changing admission.
Per-invocation detached-launch logs retain warnings for the invoking parent.

Temporary-file tests cover classifications, bounds, path containment, unchanged
bytes and diagnostic content. Native PowerShell cases use inert service/process
doubles. The existing Windows launcher workflow runs these cases in addition to
its unchanged GPU-lease checks, within the existing five-minute budget. Local
PowerShell was unavailable; its hosted result belongs to the PR evidence.

## Spoken Brief access and preview evidence — #1877, #1879, #1880

Every current access refresh now updates both source preview and archive discovery.
The existing session rejects obsolete capability successes and failures; a
discovery ticket also prevents old archive responses or errors from replacing the
latest view. Preview wording explicitly describes only the preview operation.

Eight new race cases failed before their corresponding fixes. All 29 page/session
Node contracts pass. The complete Spoken Brief Python group passed 280 tests with
one Windows-junction skip. The source symlink case now uses a distinct alias and
a separate pack candidate; it executes on this host instead of converting an
existing-path fixture error into an unsupported-platform skip. The original
source remains regular and byte-identical.

## Limits and related work

All new media, database, process and narration fixtures are synthetic. No personal
asset was moved and no live model generation was submitted. Local Chromium download
failed before a browser could launch; the existing hosted browser lanes supply
browser qualification. Source-comparison captures and acceptance remain owned by
PR #1876; this note does not substitute for its feature journey.

The interruption report #1884 belongs to the parked #1883 source-introduction
branch, whose `_source_command` is absent from this main maintenance slice. It
remains open with that dependency. Broader project acceptance, art and licensing
choices remain recorded in `HUMAN_TODO.md`.

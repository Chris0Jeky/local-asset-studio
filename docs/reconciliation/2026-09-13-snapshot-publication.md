# No-clobber publication of immutable Workspace snapshots

Fixes #230. Related #10 and #177 remain open for their broader acceptance.

## Root cause and reproduction

`AssetWorkspace.snapshot_file` streamed source bytes into its own unique `.part`
file, calculated a digest, checked the destination and then called
`Path.replace`. A writer creating that name after the check was overwritten.
This contradicted the existing refusal to replace a snapshot whose bytes had
changed. An identical competing snapshot was replaced unnecessarily as well.

The regression runs a real competing file write immediately before the actual
publication syscall, instrumenting both the original replace and proposed link
boundaries. It does not simulate a successful publication. The old path both
overwrote differing bytes and registered an asset. The new path retains those
bytes, raises WorkspaceError and registers nothing.

## Architecture

Keep the existing copy/hash loop and suffix/path convention. Once the private
copy has closed, `os.link(temporary, destination)` atomically creates the final
name only when absent. It links the private copy, **not the mutable source**.
The existing `finally` removes the temporary name.

An existing or concurrently created destination is reused only if it is a
regular non-symlink file with the expected hash. Differing content, directories,
valid links and dangling links are preserved and rejected. The existing model
publication path already uses the same no-clobber filesystem primitive; its
model-specific owner and policy are not imported into Workspace.

No separate mutex, stored counter, metadata migration, new asset store or
transaction is introduced. Registration and conditional metadata writes retain
their existing semantics. No additional automatic retry is added.

## Filesystem compatibility and limits

Publication requires same-filesystem hard-link support in the Workspace media
directory (for example local NTFS or supported Unix filesystems). A filesystem
that cannot create the link now raises its I/O error rather than falling back
to an overwrite-capable rename. A verified existing snapshot can still be reused.
Do not move or reformat an owner's Workspace automatically.

This prevents this publisher from replacing an existing name. It is not access
control against a hostile process rewriting files after validation, an atomic
capture of a concurrently modified source, or a new fsync/power-loss guarantee.
No such guarantees are added to the pre-existing store contract.

## Regression and verification procedure

Eight tests in `tests/test_workspace_publication.py` cover differing/equal
competing writers, independence from later source writes, corruption retention,
links/directories, unsupported publication and six concurrent equal publishers.
The unchanged code produced **four assertion failures and a directory-handling
error**; after the fix the full Workspace group runs **28 tests, all passed**.
The symlink scenario may skip on a Windows host without link privileges; it ran
locally on Linux. No skipped case is claimed as executed.

```sh
python -m unittest discover -s tests -p 'test_workspace*.py' -v
python -m unittest discover -s tests -p 'test_asset_metadata*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
git diff --check
```

The existing Workspace storage CI already selects these filenames and runs the
Workspace/metadata groups on Linux and Windows. No duplicate CI lane is needed.
Final full-suite/hosted outcomes are recorded on the PR separately.

## Rollback

There is no schema or format change. Reverting the source restores rename-based
publication; existing files remain readable. A failed competing destination is
never deleted by this patch; inspection/recovery of that data remains explicit.

## Primary references

- [Python os.link](https://docs.python.org/3.12/library/os.html#os.link) and [os.replace](https://docs.python.org/3.12/library/os.html#os.replace): link creation versus replacement semantics.
- [Windows CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw): local filesystem and volume constraints.

## Reconciliation and operating boundary

Inspected main `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`, tree
`5e920817385cf6c6d4aef2154267eb6c0d0c4511`. The downloaded tracked-source
archive reproduced that tree before edits. No PR was open at the initial
check. The untouched offline suite ran **1,674 tests, 16 skipped, no failures**.
Optional/live cases were not executed. Existing Pillow deprecations, deliberate
storage-fault diagnostics and the exit-time socket ResourceWarning were retained.

This is a software-only maintenance slice. No owner database, source media,
configuration, model, runtime process or HUMAN_TODO decision was changed.
No generation, upload, download or new artistic/rights acceptance follows from
the fixtures. Independent review and owner-runtime acceptance remain separate.

## Native Windows fixture follow-up

The first hosted Windows storage run passed all publication/preservation checks
but failed an expected return-path assertion: the fixture hard-coded a POSIX
separator while the unchanged Workspace protocol returns the platform's native
relative path. The expected path now uses `str(Path('media') / name)`. Digest,
size, inode reuse, actual syscall interception, source retention and cleanup
assertions are unchanged. This is a test portability correction, not a change
to product path serialization. Native rerun results are recorded on the PR.

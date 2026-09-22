# Explicit manual-copy catalog sources (#787)

The actual `models/library.json` correction is now committed, following the
initial RED checkpoint in PR #816 and the source-admission guard merged in #794.

Exactly nine issue-owned records now have an empty transfer `url` and the appended
note: “Automatic download endpoint is not pinned; manual copy only.” Historical
`source` pages, pinned hashes/byte counts, names, file paths, model families,
licence labels, all original permission/ownership caveats, triggers and strengths
are unchanged. Every unrelated record and collection URL is unchanged.

This distinguishes source provenance from automatic transfer authority. It does
not negate the recorded owner downloads, authenticate the source, grant rights,
or assert that a live download endpoint was verified. Do not derive new transfer
URLs from page/version IDs without separate source evidence. Already-present
model verification remains available through the existing ModelLibrary behavior.

## Exact data identity

Original library Git blob: `faa0272171fcbd86edffcca1da136c36c9c9280a`.
Corrected library Git blob: `e99c7d679e5083ca15e23eda410934e001e6b493`.
Corrected raw SHA-256:
`467568c8399653a5595f6295fa07afafe3ae6b5e7228e7f5293056c1db1fcff8`.

Independent whole-document comparison verifies exactly eighteen field edits.
The regression tests exercise the real initial-source admission function against
every nonempty catalog URL and inspect the nine explicit manual-copy records.
They fail on the original library with nine failures and nine refusal errors,
and pass on the corrected data. The latest affected-source overlay model suite
runs 97 tests successfully with one skip; the real validator passes. This overlay
is not the complete current branch. Hosted complete-head checks remain separate.

## Publication and integration

A temporary, branch-scoped GitHub Action verified the retained patch, original and
candidate hashes, and whole-document equality, then created only the unreferenced
corrected data blob. Run `35674011658`, job `106576556829`, succeeded. It did not
create commits, move refs or merge a PR. The GitHub connector subsequently built
and published the actual branch commit. The temporary workflow and obsolete patch
are removed from the final tree; their audit history remains in the branch.

Integration order is merged #738 and #815, then #817, then #816. Before merging,
check the final head's full offline suite, applicable Windows/browser/payload
checks and review. No model installation, inference, private-media publication,
source retrieval or HUMAN_TODO decision is part of this correction.

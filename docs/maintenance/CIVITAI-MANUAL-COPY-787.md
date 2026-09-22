# Civitai catalog follow-up — issue #787

This is a **draft RED checkpoint**, not a mergeable catalog fix. PR #794 merged the
production install guard; this follow-up retains the remaining metadata correction
and its regression contract. `models/library.json` is intentionally unchanged in
this checkpoint commit. Apply the adjacent patch as the next implementation commit
before promoting or merging this branch.

## Exact proposed change

`civitai-manual-copy-787.patch` changes exactly two fields on each of the nine
issue-owned records: blank the unverified transfer `url`, and append
“Automatic download endpoint is not pinned; manual copy only.” to `terms`.

Historical `source` pages, hashes, byte counts, filenames, names, model families,
licence labels, permission/ownership caveats, triggers, strengths and all unrelated
records and collections remain unchanged. This records lack of a pinned transfer
endpoint; it does not negate an earlier owner download or assert new permissions.
No provider access, installation, GPU work or owner decision is needed to disable
an unverified automatic transfer. Do not synthesize download URLs from version IDs.

Input: main `55cb96e8635a6da0725b141a11cb1f3d17958984`, library Git blob
`faa0272171fcbd86edffcca1da136c36c9c9280a`.

Expected candidate library Git blob:
`e99c7d679e5083ca15e23eda410934e001e6b493`.
Candidate raw SHA-256:
`467568c8399653a5595f6295fa07afafe3ae6b5e7228e7f5293056c1db1fcff8`.
Patch SHA-256:
`770d7dc17db3d126a54442a6ae65d54f0a45a7d33c58d0e4161895aacbf2f550`.

## Retained evidence

The two new tests run the production source-admission function against the real
library. On the unchanged library: nine failed manual-copy assertions and nine
refused initial-source errors. With the candidate patch applied locally: **98 model
tests pass, one skipped**, and the real repository validator passes. A whole-document
comparison against the original plus the expected eighteen field edits confirms
all other content, including collection URLs, is unchanged. These are candidate
results, not claims that this RED checkpoint's hosted CI is green.

## Finish on this PR branch

Reconcile the library blob with current main first. For the recorded input:

```sh
git apply --check docs/maintenance/civitai-manual-copy-787.patch
git apply docs/maintenance/civitai-manual-copy-787.patch
git hash-object models/library.json
python -m unittest discover -s tests -p 'test_model*.py'
python scripts/validate-repo.py
git diff --check
```

Commit the actual `models/library.json` change on this branch; keep the regression
tests. Preserve the RED checkpoint in history. Obtain fresh full-suite and applicable
Windows/browser CI plus review on the new head, then merge with an expected-head
merge commit. Only that completed implementation closes #787. The generic admission
guard already in main remains the first defence while this draft is open.

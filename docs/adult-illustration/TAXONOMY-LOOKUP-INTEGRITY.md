# Taxonomy lookup identity and relationship bounds

Follow-up to #432, #437 and #561. Read alongside [TAXONOMY-MEMBERSHIP-INSPECTION.md](TAXONOMY-MEMBERSHIP-INSPECTION.md).

## One normalized spelling cannot identify two source entries

A reviewed display name is a lookup key, not just presentation text. For example, consider a reviewed `solo` entry whose display is `mystery tag`, while the pinned CSV contains an unreviewed canonical `mystery_tag`.

The review-only compiler would resolve that spelling to `solo`. A full-source membership lookup would prefer the canonical `mystery_tag`. All source and index hashes could still be correct: the defect is contradictory ownership, not changed bytes.

Index construction and persisted-index structural validation now reject:

- a reviewed display colliding with another source canonical, including unreviewed canonicals;
- two reviewed displays sharing a normalized spelling;
- an alias colliding with any reviewed display, independently of entry order.

A display may equal its own normalized canonical. Unique custom displays remain valid. The existing canonical/alias collision checks still apply. Recomputing an index ID does not bypass these checks.

Fix the reviewed overlay and rebuild the index when a collision is reported. Do not change lookup precedence to choose one of the contradictory identities.

## The compiler still does not load the source CSV

Compilation deliberately uses the checked-in review. It cannot prove absence from an unloaded full source. The source-backed index and membership-inspection boundaries validate the complete namespace and retain exact CSV reconstruction. They reject an ambiguous overlay rather than issue a contradictory authenticated membership report.

This does not grant vocabulary acceptance, change prompt emission for valid contracts, or turn source membership into execution, content-approval, training or generation authority. Valid artifact schemas and content identities remain unchanged.

## Depth is an admission bound, not a post-traversal warning

Both taxonomy-index and prompt-overlay relationship validators enforce the configured depth before descending into an unseen child. A chain longer than the bound fails with ValueError before reaching Python's recursion limit.

Memoized subtree depth is still accounted for when it is reused from a longer path. Shared tails remain valid; short cycles remain rejected; a path exactly at the configured depth remains valid. Very long cycles may fail the depth limit before the cycle is reached, which is an intentional bounded refusal.

## Offline regression coverage

`tests/test_adult_illustration_taxonomy_integrity.py` covers source-backed builder rejection, self-rehashed saved indexes, a compiler-versus-membership collision with matching source/contract identities, valid displays, a 2,000-node chain, cached longest paths, shared tails and cycles.

```sh
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The fixture sources are synthetic CSV bytes. No network access, model execution, generated index in Git or checked-in provider CSV is required.

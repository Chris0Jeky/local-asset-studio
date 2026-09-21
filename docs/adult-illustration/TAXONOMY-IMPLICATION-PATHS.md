# Reviewed implication paths must stay eligible

Follow-up to #432/#437/#561 on #562. This is a separate correction from #690's
namespace/depth checks, #733's contract reader and #741/#745's fallback budgets.

## A rejected intermediary cannot contribute a path

Previously the resolver built the complete transitive closure before checking
individual entry eligibility. Given accepted A -> rejected B -> accepted C,
compilation omitted B but still emitted C from that same rejected branch. A root
with no usable profile-ordering facet could similarly emit its descendants.

Resolution now admits an entry before scheduling its outgoing implications. A
rejected entry is retained in the trace and produces its existing diagnostic,
but traversal stops on that branch. Deprecated entries are ineligible under the
existing review contract, so their implications and suggested replacements do
not become an automatic route around deprecation.

This is path-local, not a global ban on a descendant. An independent eligible
A -> D -> C path can still reach C, in that path's ordinary depth-first order.
An explicitly supplied C can also resolve independently. Shared descendants are
deduplicated only when actually visited. Canonical and alias inputs obey the
same rule, and both tag and hybrid profiles use this resolver.

## Evidence and compatibility

The trace lists entries actually examined along admitted paths, including the
first rejected entry. It does not claim that unvisited descendants were checked.
Membership inspection retains this compiler trace and still authenticates its
index by reconstructing the exact pinned source. Source membership is not
compilation acceptance; a source-known leaf need not have an eligible path from
a particular input.

All-eligible graphs retain the existing depth-first ordering, prompt strings,
identities and authority flags. Artifacts that previously emitted through a
rejected path intentionally change and must be recompiled; self-rehashing an old
artifact cannot bypass deterministic revalidation. No schema, source vocabulary,
review decision or profile-polarity compatibility rule is changed.

No provider access, model/reference bytes, runtime, installation, inference,
generation, training or promotion is introduced. HUMAN_TODO q-29 remains open.
The existing source taxonomy depth and graph validation contracts still apply;
this correction does not replace #690's pre-descent bound.

## Offline tests

Seven methods cover blocked/deprecated bridges, alias/canonical and tag/hybrid
inputs, missing ordering facets, an independent eligible route, explicit leaf
input, unchanged eligible diamonds, and source-authenticated membership. The
sources and reviews are synthetic temporary fixtures, never downloaded CSVs.

```sh
python -m unittest tests.test_adult_illustration_taxonomy_paths -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

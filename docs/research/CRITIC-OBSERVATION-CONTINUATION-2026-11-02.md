# Critic observation continuation — 2 November 2026

## Outcome and scope

This continuation fixes the integration defect in issue #1977 and connects saved
sentinel results to the existing offline policy-replay tool. It also brings the
24-case synthetic experiment's raw observations into Git and losslessly preserves
the earlier public capture-contract patch that had only been delivered as an
attachment. No production detector threshold, native execution owner, environment,
private asset or artistic decision changes.

PR #1974 was observed merged by concurrent repository work at
`686411437a9c3264434851c4624ff8a2cf3b0621`; this is the follow-up's base. Its three
final-head CI workflows were successful. That is historical evidence for the prior
PR, not a passing result for this continuation.

## Reproduced failure and repair

The critic deliberately returns `error`, `evidence_complete=false` and a conservative
`changed=true` when source evidence is unsupported. The old sentinel adapter dropped
the error/completeness fields and converted that compatibility bit into an available
second opinion. It could agree with a warning primary result even though the critic
had performed no usable comparison, or create a critic-only warning on a quiet
primary result.

A regression uses real 16-bit PNGs. The primary comparator sees a large change;
the precision-aware critic refuses the sample representation. Before repair, the
sentinel reports an available change. After repair, it returns unavailable, retains
the diagnostic observation and returns null agreement without changing primary
warnings. A quiet-primary case is covered separately. Missing modules/images,
exceptions, malformed booleans/counts and empty error strings are also covered.

Successful signals retain the existing summary fields and add `observation`, the
complete raw critic result. Failed observations stay diagnostic data, not a score.
The optional critic remains optional: the sentinel's existing primary pass policy
is unchanged. A primary pass with an unavailable critic is not two-signal agreement.
The two implementations also inspect the same images; their agreement is not an
independent experimental replication or a probability of asset correctness.

## Replay the saved result, not another render

```console
python scripts/render_critic_policy.py replay PATH_TO_RESULT_JSON --input-kind sentinel --fraction 0.004 --out .runtime/critic-replay-NEW.json
```

Replace `PATH_TO_RESULT_JSON` with an existing `blender_sentinel.py` `result.json`.
The output parent must exist and the output file must be new. The parser still
limits input to 2 MiB, rejects duplicate/non-finite JSON and excessive nesting,
and retains the original input byte hash. It never follows source/artifact paths
from the document, opens native assets, starts a renderer or calls a model.

The explicit selector requires the sentinel-v1 schema, an available non-error
render-critic signal, a complete raw observation and consistent summary/counts.
Legacy summary-only results remain incomplete; dimensions are never guessed.
The default input mode remains a raw critic receipt, preserving existing callers.
The saved overall `pass` and primary warnings do not override this pixel-policy
experiment. A contradictory envelope cannot clear a candidate.

`below_floor` means only that the proposed fraction suppresses the raw signal.
It does not mean noise was established. Exit 0/1 describes the hypothetical review
policy; exit 2 describes incomplete/invalid evidence. None accepts art or assets.
A full successful receipt remains usable when a vision model only named the change;
replay does not rerun that model or endorse its labels.

## Repository-retained experiment

[The retained experiment](../../research/agentic-creation/critic-observations/README.md)
contains 24 raw receipts, constructed labels, per-case hypothetical decisions,
source/environment identities and aggregate counts. Tests re-score every receipt
and regenerate the entire owned pixel recipe, checking exact semantic observations.
Encoded PNG hashes identify the historical run, not a cross-Pillow/zlib guarantee.

| Proposed per-view floor | Detected constructed defects | False alarms | Missed constructed defects |
|---|---:|---:|---:|
| 0 (existing raw gate) | 15 | 3 | 0 |
| 0.1% | 12 | 0 | 3 |
| 0.4% | 10 | 0 | 5 |

This rerun reproduces the previous counterexample; it is not a new independent
sample or native noise measurement. The 26 dispersed pixels are nuisance by
construction. The five missed defects at 0.4% remain a reason not to silently
promote that floor. Issue #1970 therefore remains open.

## Earlier source preserved, not silently activated

[The archived capture-contract follow-up](../../research/agentic-creation/archive/capture-contract-followup/README.md)
contains the exact earlier patch's six files: implementation, tests, owned profile,
design, plan and usage guide. Its original SHA-256 is
`ae6a13b5dfbc8a762593376e3444b6f0a769d8ab2640b6623389e9924542ea5f`.
A regression checks compressed bytes, decompression completion, original bytes and
all six paths. The archive can be restored with Python's standard library, but is
not imported, executed or automatically applied. Its original comparator assumptions
must be reconciled with the now-evolved native producer before integration.

Only that public source patch is archived. Complete private research exports,
private character source and workstation configuration are not copied into public LAS.

## Verification and limits

[Machine-readable verification](../verification/critic-observation-2026-11-02.json)
records **83 passing focused tests**: 69 critic/policy/retained-study tests, 13
sentinel-adapter tests and one archive-integrity test. The new contribution is 34
of those tests. ResourceWarnings were treated as errors. The causal sentinel run
failed before repair (13 tests, 11 failures plus two errors); the 17 saved-result
replay tests failed before implementation. The retained-record test initially
exposed ordering of otherwise identical triggering-view sets; it now compares
sorted membership, not incidental JSON object order, without changing detection.

The exact base sentinel blob `02efafe0ae652c3f49f1b7ec7cd82c0b0972306f` was
reconstructed and hash-verified before editing. Relevant critic inputs were also
verified against their published blob identities. Local verification used the old
supplied ZIP plus these exact relevant files, **not a full current-main clone**.
The local sentinel tests stubbed only the absent native dispatch module; they ran
the real sentinel adapter, real image comparator and real Pillow decoding. Hosted
CI uses the actual complete repository and actual native-dispatch module imports.
No native process was launched by these tests.

Local repository validation passed (98 graphs/bindings, 194 pinned assets, 167
LoRA names, 4,757 tracked paths in that local snapshot). This is not full-current-tree
qualification. Independent review and exact-head hosted checks remain separate
merge gates. No native Blender, AMD/Windows, model inference, browser, private MIRA
or art acceptance is claimed.

## Next native experiment

Use the existing owned chest, explicit configured executables and existing resource
admission. Start with the bounded repeated-source versus export/reimport controls
in the [original qualification plan](RENDER-CRITIC-POLICY-STUDY-2026-11-02.md), keeping
actual camera/light/frame/sampling/color settings fixed. Three pilot repeats can
locate gross instability; they cannot establish a production false-alarm rate.

New runs now retain the full observation automatically. Existing PNG evidence can
be compared offline through `render_critic.py check ... --reference ... --diff-only`
without re-rendering. Save a new receipt; never overwrite or reinterpret the old
summary as complete. Separate tuning and held-out scene/pose families, include small
texture/silhouette/alpha defects, and report missed real defects alongside cleared
nuisance alarms before selecting any versioned policy. Preserve uncertainty and
stop rather than resubmit an uncertain native job.

## Primary reference checked during this continuation

[Pillow ImageChops documentation](https://pillow.readthedocs.io/en/stable/reference/ImageChops.html),
accessed 2 November 2026, states that most channel operations are implemented for
8-bit images. It supports the precision distinction; it does not supply a native
noise floor or establish correctness of LAS. The agreement repair is justified by
the actual returned error state and the causal tests, not by a library-version claim.

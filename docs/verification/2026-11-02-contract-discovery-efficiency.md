# Contract discovery without repeated parsing

Issue #1904 records a full-suite run at 1168.122 seconds against the unchanged
1200-second hosted lifetime budget. Issue #1882 records broader runner variation.
The contract-discovery tests contributed avoidable work: three calls reparsed
the entire tracked Python/workflow runner corpus, although the assertions inspect
one checkout.

## Change

`ContractDiscoveryTests` now builds one full parsed runner snapshot at class
setup. The existing `runners(exclude_self=...)` filter still supplies both views,
so the discovery module cannot vouch for its own sentinel filenames. Class cleanup
releases the snapshot. A direct helper call without a supplied snapshot still
reads the current runner corpus.

Contract inventories continue to read the live Git index. The untracked scratch
contract test still checks that its temporary file cannot enter the gate. All
existing AST/docstring, comment, filename-boundary and workflow-trigger matching
rules are unchanged, as are the minimum corpus and orphan-contract assertions.

## Evidence

The same ten tests passed before and after, with no skips. Instrumenting actual
`runner_text` calls on the same 953-file corpus measured 2857 parses before and
953 after. The complete parsed-corpus digest was identical:
`09db53abf3cbbd0f35a63023371d20c5f60a976fbd58fe8fe5941b0f65fc7885`.
An independent cleanup probe confirms the class snapshot is released.

Ordinary local runs took 41.179 seconds before and 12.073 seconds after; the final
version with class cleanup took 16.744 seconds. Other tests were running on the
host, so these are observations, not a controlled speedup estimate. A later
isolated tracing measurement and the final hosted full-suite result belong to the
PR evidence. Repository validation and whitespace checks pass.

No test, parser rule, workflow, timeout, lifetime diagnostic, leak check or shard
boundary is removed or relaxed. This change removes repeated work; it does not
claim that every form of hosted runner slowdown is resolved. #1882 remains open
for that broader measurement question.

# Critic observations: truthful agreement and saved-result replay

## Intent and constraints

Continue the owner's agentic-creation programme in LAS, committing code, tests,
findings and reproducible evidence rather than relying on a chat attachment.
Issue #1977 identifies the immediate integration defect: the critic's conservative
`changed=true` compatibility bit on unsupported evidence becomes a valid sentinel
second opinion. Issue #1970 remains a separate native-noise qualification task.

Keep the primary sentinel decision, current pixel thresholds, execution owners,
installed environments and private character assets unchanged. No Blender/model
execution is part of this slice. Successful comparison is not art acceptance.

## Approaches and choice

Changing the detector boolean would reintroduce false clears for old consumers.
Raising thresholds would hide the small defects reproduced in the previous study.
The selected approach is to preserve the complete observation and make the adapter
respect its evidence status before comparing verdicts. Extend the existing offline
policy replay with an explicit sentinel input mode instead of a second evaluator.
This is an implementation choice under the owner's continuation instruction.

## Contract

`critic_signal` returns unavailable with a bounded reason for error, incomplete,
malformed or failed results. Unsupported observations remain retained for diagnosis;
no top-level changed verdict is manufactured. `second_opinion` returns null and
leaves primary warnings untouched for unavailable/failed/incomplete evidence.
Successful signals keep existing summary fields and add the raw `observation`.
Legacy success remains usable as a signal but cannot qualify for offline replay
without the required dimension/policy evidence.

Offline replay explicitly selects `receipt` or `sentinel`, hashes the original
input bytes, verifies envelope/summary consistency, and never reads any paths from
the document, launches tools, changes production thresholds or overwrites output.
Missing/unsupported observations become incomplete, not noise or a clean score.

## Evidence and limits

Exercise the real image comparator with owned 8-bit/16-bit PNGs, primary warning
and quiet states, malformed result objects, and successful/failed saved-result
replay. Retain the previous 24-case experiment's recipe, compact machine-readable
receipts, implementation hashes and outcomes in a public, synthetic-only directory.
Raw native/private media stays outside Git. Hosted exact-tree qualification is
separate from the local focused snapshot; document that distinction.

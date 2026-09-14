# Metrics and evidence gates

## North-star measure

> **Accepted reusable assets per owner-hour, with complete lineage and no ambiguous replay.**

This is intentionally stricter than jobs completed per hour. It includes the creative decision and the ability to continue from the result.

A single number should never hide quality classes, but this north star keeps the system oriented toward useful output rather than feature volume.

## Core product measures

| Measure | Definition |
| --- | --- |
| Time to reviewed setup | From task start to a setup the owner is willing to run |
| Time to first candidate | Includes interaction and queue wait; report model time separately |
| Time to accepted asset | Includes review, rejects, repairs and cleanup |
| Accepted-task yield | Distinct intended tasks with an accepted result / distinct tasks attempted |
| Useful-candidate yield | Candidates judged useful or repairable / all image-producing attempts |
| Reuse rate | Accepted assets reused as a reference, branch, export or native-tool source |
| Owner interaction cost | Meaningful clicks/actions, view switches, typed duplication and manual calculations |
| Explanation load | Standing instruction words encountered and peak visible instruction load |
| Cleanup effort | Active masking, editing, metadata correction and native-tool time |
| Recovery integrity | Ambiguous writes/submissions recovered without duplicate application |
| Early-refusal value | Expensive jobs prevented by exact preflight/resource evidence |
| Route reliability | Prepared requests that reach a terminal technically classified state |

Always report numerator and denominator. “Zero failures” on a tiny held-out set is not a population claim.

## Evidence states

The repository should use one common vocabulary while allowing domain-specific sub-states:

| State | Meaning |
| --- | --- |
| Planned | Declared work; no execution authority or result |
| Prepared | Inputs and identities validated for a bounded request |
| Submitted | Request accepted with durable local/remote identity evidence |
| Uncertain | Remote outcome cannot be safely inferred; no blind replay |
| Completed | Technical operation produced its claimed output |
| Inspected | A person or named review process examined the result |
| Selected | Chosen relative to alternatives, not necessarily final |
| Accepted | Owner approved for a stated creative/production role |
| Rights-reviewed | Exact resources and intended use reviewed separately |
| Export/engine accepted | Named downstream contract passed independently |

Do not compress these into one `verified` boolean. Catalog flags may remain for compatibility, but explanatory evidence should state which dimension was actually established.

## UX gates

A common task route should normally satisfy:

- no primary action disabled without an adjacent specific reason;
- no side effect from page load, import, browse or read-only checking;
- no requirement to choose an implementation-specific recipe before the user can provide the task inputs;
- source/reference selection preserved across wrong turns;
- common reviewed setup in approximately five meaningful interactions after brief/references;
- one picker visit for ordered multi-reference input;
- visible cost as measured, estimated or unknown;
- direct path from completed candidate to review, acceptance and continuation;
- keyboard and 390px coverage for the route's essential controls;
- owner session evidence before claiming the experience feels good.

The use-case matrix should fail on dead ends, unexplained disabled controls, page exceptions and generation-capable calls during read-only mode.

## Route/model promotion gate

A route becomes **recommended** for a named task only when:

1. exact model/encoder/VAE/adapter/node/runtime identity is retained;
2. graph/schema/resource preflight passes against the intended backend;
3. at least one bounded live execution completes;
4. representative results include a typical case and a failure case, not one flattering image;
5. the owner accepts at least one result for the named role;
6. timing and resource measurements are labelled by environment and stage;
7. terms/source evidence is recorded separately;
8. rollback or fallback route is clear.

`Executed`, `inspected`, `accepted` and `recommended` must remain separate.

## Repair promotion gate

A repair route becomes recommended for a defect class only when:

- target/context/write/protection semantics are explicit;
- exact pixels outside final effective support are verified where promised;
- source, mask, transform and candidate identities are retained;
- intended change succeeds, not merely preservation;
- seams/final-size quality are inspected;
- identity/costume/contact checks are scored separately;
- failed and no-op attempts remain in the denominator;
- total effort is lower or capability is materially better than the baseline;
- owner acceptance is explicit;
- ambiguous submissions and changed sources fail closed.

## Authored-workflow execution gate

Before enabling a wider Workflow Studio execution level:

1. document and graph identities are immutable and revisioned;
2. only supported adapter types are executable;
3. model/resources/schema/backend are checked and rechecked at dispatch;
4. selected output closure and side effects are explicit;
5. request intent is durable before submission;
6. accepted-but-response-lost faults reconcile without replay;
7. progress/output/failure map back to document IDs;
8. one owner-approved live route passes;
9. the capability flag remains false for unsupported/native-only elements.

The first gate should cover registered-template-equivalent documents, not arbitrary graphs.

## Resource-profile gate

A launch/cache/offload profile becomes a default only after a matched experiment records:

- exact runtime and arguments;
- fixed workflow/model/input/seed;
- cold and warm timing;
- process working set/private bytes;
- system physical and commit headroom;
- runtime VRAM counters;
- stage completion/failure;
- final output identity and separate visual inspection;
- rollback to the previous profile.

One successful run does not establish universal safety. A profile that improves one graph but increases native crashes elsewhere remains task-scoped.

## Native/export gate

A generated artifact is not engine/native accepted because a file was written. The named target must:

- reopen/import in the actual application/version;
- retain the promised layers, timing, scale, pivots, alpha/material or rig properties;
- expose unsupported/lost properties;
- preserve original/native sources;
- produce an inspectable downstream result;
- record exact package and application identity.

## Development health measures

Use these to manage engineering without turning them into vanity metrics:

| Measure | Desired behaviour |
| --- | --- |
| Active implementation lines | within #315 WIP limit unless explicitly overridden |
| PR integration age | short enough to avoid repeated moving-main reconciliation |
| Focused test duration | proportional to changed seam |
| Full-suite-only failures | owned and investigated, not dismissed as normal flakiness |
| Warning count | trends downward; persistent warnings have owners |
| Documentation drift | generated factual blocks match source evidence |
| Duplicate issue rate | low; new issues name distinct ownership and dependencies |
| Accepted outcome cadence | increases before feature breadth increases |

Raw test count, issue count and merged PR count are not health measures.

## Reporting template

Each bounded experiment or vertical slice should report:

```text
Task:
Owner-defined acceptance:
Exact source/setup/runtime identities:
Attempt allowance:
Attempts: completed / failed / uncertain / refused
Useful candidates:
Accepted results:
Time: interaction / queue / generation / cleanup / total
Resource observations:
Main UX friction:
Known remaining defects:
Rights/export state:
Next decision:
```

## Generated versus authored status

Issue #315 should generate facts such as commit identity, validator counts, open PRs/stacks and issue taxonomy totals. It must not generate:

- product-completion percentages;
- artistic acceptance;
- licensing judgements;
- causal claims from warnings;
- whether the owner prefers one workflow.

Those remain explicit human or evidence-based prose.
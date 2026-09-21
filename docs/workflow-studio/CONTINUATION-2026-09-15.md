# Workflow Studio continuation — 15 September 2026

Reconciled against main `85dc151ea89fa730967dcee4920750411f0c14cd`, including the
existing issue discussions, workflow implementation and current UX findings.
This is a continuation of the original guided Studio / headless agents / in-Studio
ComfyUI authoring request, not a replacement architecture.

## What is already implemented, and what is not

| Original issue | Preserve the existing implementation | Real remaining work |
| --- | --- | --- |
| #118 Guided creation | Seven guided paths, automatic debounced observations, current-step markers, recipe shortcuts, context invalidation, resume, source-aware recipe advice and reviewed setup application. | Specialist journey predicates, stronger capability-backed guidance, clear feature transitions and owner/assistive-technology acceptance. |
| #119 Installed-node controls | Installed-schema normalization, typed controls and connections, explicit unsupported-node/widget diagnostics. | Versioned installed corpus, separate editable/serializable/executable/native-only support levels, dynamic/list/union widget adapters and lossless wide-integer editing. |
| #120 Shared authoring | Workspace immutable document revisions, CAS, command batches, preview/apply/restore/fork, conflict recovery, named Steps over the same nodes and exposed controls. | Typed reusable interfaces and multi-target controls, reference-slot lineage, measured 50/150/256-node and large-catalog interaction budgets. |
| #121 Native interoperability | API documents deliberately distinguished from native visual workflows; unsupported conversion refused. | Version-pinned original-artifact preservation and measured widget, reroute, mode and subgraph adapters. |
| #122 Authored execution | Registered-recipe tickets, a limited compatible image-document projection, saved-revision run preparation, exact-ticket review/dispatch and the existing worker. | Reference-bearing authored graphs, broader graph adapters, side-effect/resource admission and failure/recovery evidence. |
| #123 Headless agents | CLI, Python SDK and optional read/author/execute stdio MCP, shared commands, saved-run review/observation/recovery. | Bounded artifact/provenance access, reconnectable lifecycle/ownership semantics, new-machine and mixed human/agent acceptance. |

All six remain open. The old issue-body foundation paragraphs are not instructions
to implement a second SDK, MCP bridge, graph store, save journal or worker. Merged
infrastructure alone is not evidence that every broad acceptance criterion passed.

The older roadmap's export-only setup-proposal paragraphs describe historical
slices. Reviewed application, explicit shared revisions, copy-only staging, Undo
and recovery now have their own implementation and [SETUP-APPLICATION.md](SETUP-APPLICATION.md).
#232 still requires its full residual acceptance to be checked before closure.
Do not reimplement its Apply path from the older proposal text.

## This pass

The guide disclosure correction is in #380. It separates one-time/explicit reveal
from ordinary visibility inspection and accounts for native closed-details layout.
See [GUIDE-DISCLOSURE-OWNERSHIP.md](GUIDE-DISCLOSURE-OWNERSHIP.md). It addresses the
guide portion of #360 and advances #278/#118; the other review findings remain.

[Step ordering](STEP-ORDERING.md) implements the shared-command part of #382.
It is presentation-only and does not change graph execution identity. The matching
keyboard-accessible Move up/down UI passed local tests but could not be published:
the UI write was blocked twice by an indeterminate OpenAI safety-status result. That source and its test driver are retained
in the session handoff, not this PR; #382 stays open for UI publication/integration.
The command/documentation PR is stacked on #380 and references its guide correction.
Review the child diff independently and integrate the parent first. Neither PR
claims reusable native subgraphs or arbitrary graph execution.

No models, packages, user runtime, Workspace contents or generation jobs were
changed. Creative choices and licence decisions in HUMAN_TODO.md, including the
Style + Pose and Restyle/Combine reviews, remain with the owner.

## Architecture to extend

```text
Guided journeys                 Steps / Nodes / CLI / SDK / MCP
    |                                      |
existing feature observations    one document + explicit commands
                                           |
                                Workspace revisions and CAS
                                           |
                              supported execution adapter only
                                           |
                         saved preparation + exact ticket review
                                           |
                           existing admission / worker / outputs
```

A display control is a projection of actual graph inputs, not another value store.
A visual connection is not proof of executable compatibility. A saved document
revision is not a runtime receipt. Preserve those boundaries while making the UI
less laborious.

## Next bounded authoring slice: typed multi-target preview (#384)

**Status: designed and seeded, not implemented by this pass.** The current exposed
control binds one node/input. A future friendly setting may bind several explicit
inputs, but it must show what each change will touch before mutation.

Start with a pure read-only planner adjacent to the existing Steps/command modules.
Its request identifies the exact document revision, backend/schema fingerprint,
control-interface version, ordered `(node_id, input_name)` targets and proposed
literal. Its response reports current values, support/block reasons and the exact
ordered batch of existing `set_input` commands. It must not return an executable
ticket or make a backend call that installs, stages or submits anything.

The first adapter should accept only scalar inputs with fully understood metadata.
All targets must have compatible literal types. Booleans are not integers; JSON
numeric values must stay finite. Bound intersections and enum intersections must
be nonempty. Numeric step metadata is a widget hint unless its actual constraint
semantics are pinned; do not invent a divisibility rule or round input silently.
Differing current values must display as **mixed**, not an arbitrary first value.

Reject unknown inputs, duplicate/conflicting targets, forced sockets, unsupported
widgets, dynamic/list/union types, stale schema/revision and empty intersections
with per-target explanations. Check all targets before emitting any usable command
batch. A rejected preview returns diagnostics, never a partially usable batch.
Preserve the exact existing single-target contract and opaque metadata; specify a
versioned migration or explicit older-client refusal before expanding document data.

### Implementation sequence and proving gates

1. Add pure planner fixtures for supported scalar fan-out, mixed values, incompatible
   bounds/enums, booleans versus integers, non-finite values, large integers, duplicate
   targets, stale identity and unsupported widgets. No persistence or Comfy imports.
2. Publish a read-only service result through the existing agent/UI boundary. Compare
   exact proposed command bytes across consumers. No loading or previewing writes.
3. Add an accessible preview panel showing every target, old/new value and blocker.
   Measure keyboard/390px behavior and late-response invalidation on the real UI.
4. Keep reviewed application outside the first issue's acceptance. When designed,
   use existing CAS, a retained request ID and atomic command batch; bind review to
   the interface/schema/document identity. Do not add another mutation journal.

The planner is the next small increment toward powerful controls, not a substitute
for typed module import/fork or native subgraphs. Those still need installed-version
fixtures and lossless interoperability evidence under #119–121.

## Verification record

Local source reconstruction was pinned and checked against Git blob hashes. Guide
regressions: 12 real-DOM Chromium tests pass; ordering: nine reducer/compiler tests
pass, with six further real-DOM/shared-reducer tests passing for the unpublished UI.
Discriminating tests failed against the original source first. Syntax/compilation checks passed. These fixtures do not establish full
Studio navigation, true session storage, live SDK/MCP, GPU quality or owner acceptance.

Hosted CI for #380 subsequently passed all seven triggered workflow runs, including
Check studio, Guided journey browser, UX use cases and Windows runtime safety. The
child PR's CI must be checked separately; a green parent is not proof of the child.

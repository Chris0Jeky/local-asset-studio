# System assessment

## Overall assessment

Local Asset Studio is an unusually mature engineering system for a single-user local creative tool. Its runtime and evidence disciplines are stronger than its present day-to-day usability and creative acceptance loop.

The correct interpretation is not “the engineering was wasted.” The repository has built valuable foundations. The risk is that those foundations continue expanding before they are consumed through repeated owner-accepted work.

## Directional scorecard

These scores are a strategic judgement, not generated repository metrics.

| Area | Assessment | Rationale |
| --- | ---: | --- |
| Runtime and recovery engineering | 9/10 | Single owner, retained prompt IDs, uncertain-state handling, bounded recovery, backend ownership |
| Provenance and evidence discipline | 9.5/10 | Technical execution, visual acceptance and rights remain distinct; recipes and artifacts retain identity |
| Local-first architecture | 9/10 | Loopback service, user-owned files, no required hosted dependency, isolated runtimes |
| Agent development infrastructure | 9/10 | Repository laws, skills, parity checks, explicit authority and bounded MCP/CLI contracts |
| Test discipline | 8.5/10 | Large causal suite, real SQLite/files/browser fixtures, fault injection and platform lanes |
| Model/workflow architecture | 8/10 | Clear catalog-to-graph allow-list, paired visual graphs, source and bundle evidence |
| Resource awareness | 8/10 | Physical RAM, commit, VRAM and stage failures increasingly separated; admission unfinished |
| Product architecture | 7.5/10 | Coherent control-plane direction, but many parallel programmes compete for attention |
| UX architecture | 6/10 | Rapid improvement and good measurement; default flow remains conceptually fragmented |
| Day-to-day owner usability | approximately 5/10 | The owner audit described the Studio as close to unusable before the latest UX fixes |
| Creative-output validation | 4/10 | Many completed and inspected routes; too little accepted reusable output relative to infrastructure |
| Scope discipline | 4/10 | Image, video, 3D, voice, music, AV, agents and native tools advanced concurrently |
| Delivery/WIP management | 5.5/10 | Strong per-PR rigor, but prior parallel stacks caused repeated integration and evidence overhead |
| Long-term potential | high | The control-plane/evidence concept is differentiated if convergence succeeds |

## Architecture as it exists

The project now spans several layers:

| Layer | Current responsibility |
| --- | --- |
| Runtime | ComfyUI and isolated model environments; process and memory ownership |
| Execution | Jobs, prompt IDs, queue discipline, recovery, budgets and reservations |
| Workflow/model | Presets, graphs, references, bundles, schema and resource checks |
| Workspace | Assets, metadata, collections, lineage, review and reversible trash |
| Authoring | Create, Prompt Lab, guided paths and Workflow Studio |
| Experimentation | Comparisons, bounded studies, receipts and candidate review |
| Native integration | Krita, Blender, Godot, export packages and document guards |
| Production programmes | Character consistency, Repair Studio, AV, voice, 3D and sprites |
| Agent layer | CLI, typed client, MCP, skills and shared command contracts |
| Evidence | Revisions, hashes, raw requests, jobs, review status and terms records |

This is no longer a small UI over ComfyUI. Design decisions should acknowledge the system's control-plane role.

## Strongest assets

### Evidence is a product capability

The repository treats these as different states:

```text
planned → prepared → submitted → uncertain → completed → inspected → accepted → rights/export approved
```

That separation prevents many common generative-system errors: duplicate submissions, false success, silently stale resources and the promotion of attractive demos without reproducible inputs.

### Runtime isolation is correct

HiDream, H3 and the primary runtime should continue using explicit isolated environments. A Windows AMD system is especially vulnerable to package/runtime changes that invalidate otherwise working routes. The current no-automatic-upgrade posture is a strength.

### Failure evidence is increasingly specific

Issues #77 and #89 distinguish host allocation, Windows commit, VRAM residency, unloading/reloading and native access violations. This is much more useful than a generic OOM label and supports real stage-aware admission under #178.

### Agent infrastructure is mature

`AGENTS.md`, `CLAUDE.md`, skills, parity checks and authority tiers make the repository agent-operable without pretending agents have human creative authority. The laws around uncertain submissions and separate acceptance states should remain foundational.

### The latest UX method is better

The owner audit and use-case matrix changed the optimisation target from “the workflow is represented correctly” to “the owner can complete the task with tolerable interaction and explanation cost.” That is the right correction.

## Principal liabilities

### Sophistication exceeds consumption

The dated assessment recorded a large amount of executed evidence and a Workspace dominated by unreviewed outputs, with no accepted image pack at that checkpoint. The project needs repeated use, not another architecture wave.

### Scope is too broad for simultaneous mainline work

The repository has active plans for image generation, references, character consistency, repair, animation, video, 3D, rigs, sprites, voice, music, Foley, timeline editing, DAW/NLE handoffs, prompt compilation, model intake, workflow authoring, MCP and resource orchestration.

Each can be justified independently. Pursued together, they dilute owner acceptance and increase integration cost.

### Product concepts are fragmented across surfaces

Prompt Lab, Create, recipe selection, guided paths, Workflow Studio and Bundle Explorer each hold part of “help me make the right thing.” The default experience should converge around one task-oriented route with advanced inspection, not require the user to choose the correct abstraction layer first.

### The catalog binding contract is under pressure

Mapping controls to raw `[node_id, input_name]` pairs remains elegant, but dynamic inputs, native visual workflows, custom widgets, subgraphs and multiple backends increasingly require one canonical schema/adapter interpretation. Issue #97 and the V3 dynamic-input corrections demonstrate this pressure.

### Repeated reliability infrastructure is emerging

Workflow documents, setup application, asset metadata, collection recovery and other domains increasingly implement revisions, request IDs, receipts, recovery and append-only restore independently. Issue #314 should extract only proven shared invariants.

### Test and evidence machinery has its own maintenance cost

A large suite and many path-filtered workflows provide confidence, but #227, #297, import coupling and persistent warnings show that the test system itself is now an architectural component. Test count should no longer be treated as a success metric.

### Narrative status drifts

Fast development can leave counts or conclusions stale across `README.md`, `STATUS.md`, `CURRENT_STATE.md` and agent instructions. #315 should generate stable factual blocks while leaving subjective status authored.

## Code-structure implications

The Python standard-library server remains appropriate for one user, one machine and localhost. Framework replacement would add migration risk without solving the main product problem.

The useful refactoring direction is narrower:

- keep `server.py` as composition/routing rather than a growing domain owner;
- split large domain modules when boundaries are already visible;
- centralise schema normalisation and safe media capture;
- use typed revision/receipt helpers after #314 proves compatibility;
- strengthen browser module ownership and type checking before considering a framework rewrite.

## Current strategic conclusion

The system has enough foundation to enter a convergence phase. The next major proof is not a new model or a larger architecture diagram. It is a compact accepted asset pack created, reviewed, repaired and reused through the shipped system with bounded effort.

Issue #313 owns that proof. The rest of the strategy should support it or wait.
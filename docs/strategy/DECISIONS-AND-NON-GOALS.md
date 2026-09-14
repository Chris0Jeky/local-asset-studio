# Decisions and non-goals

This record makes the strategic conclusions explicit so later work does not reopen settled questions without new evidence.

## Decisions to retain

### Keep the Python standard-library server

The deployment is one user, one Windows machine, loopback only and no horizontal scaling. `ThreadingHTTPServer`, SQLite and local files are appropriate. Refactor domain ownership; do not migrate frameworks for fashion.

### Keep plain JavaScript for now

The no-build deployment is valuable. Improve module ownership, JSDoc typing, pure projections and lifecycle helpers incrementally. A framework migration needs measured maintenance benefit and a bounded compatibility plan.

### Keep one trusted execution owner

Generation, resource admission, budgets, prompt IDs and recovery must continue through the existing Studio/Production owners. No raw `/prompt` proxy, second GPU semaphore or native-plugin generation loop.

### Keep backends isolated

Do not mutate the working shared Torch/ROCm environment to make every model coexist. Backend switches remain explicit, idle-gated and identity-bearing.

### Keep originals and evidence

Sources, submitted graphs, prompt IDs, retained failures and accepted derivatives remain distinct. Undo/restore appends state; it does not rewrite history or imply remote cancellation.

### Keep native tools authoritative in their domains

Krita owns painting/layers/masks, Blender owns geometry/rigging/animation, Godot or the selected engine owns playback acceptance, and later DAW/NLE tools own serious editing. Studio coordinates rather than reimplements them.

### Keep human acceptance separate

A completed job, passing test, detector score or agent recommendation cannot mark art accepted or rights cleared.

## Decisions to change

### Change the default information architecture

Lead with tasks and desired outcomes. Recipes, profiles, graphs and detailed settings remain advanced reviewed controls.

### Change success metrics

Prefer accepted reusable assets, time to acceptance, owner effort, reuse and recovery integrity. Do not optimise for test count, merged PR count, installed model count or completed jobs alone.

### Change Workspace emphasis

Treat review, acceptance, organisation and continuation as central product functions rather than secondary gallery features.

### Change development throughput policy

Adopt #315's WIP limit and explicit stacks. High agent throughput should shorten feedback loops, not multiply moving branches.

### Change status maintenance

Generate stable facts, keep `STATUS.md` concise current truth and treat `CURRENT_STATE.md` as a historical evidence ledger.

### Change PR communication

Put decision-useful summary first and detailed receipts in linked evidence. Preserve rigor without requiring every reviewer to parse the full forensic record before understanding the change.

## Work to stop by default

- adding model families without a concrete blocked task;
- opening duplicate epics for capabilities already owned;
- creating another queue, asset database, model registry or recovery store;
- automatic package/runtime changes;
- automatic generation on page load, import or navigation;
- blind replay of uncertain submissions or writes;
- generic “stronger settings” escalation after a creative failure;
- broad refactoring while the accepted-asset loop remains unproven;
- using raw test/issue/PR counts as progress;
- copying exact workstation/private evidence into public docs when sanitised structure is enough.

## Work deliberately deferred

- broad voice identity and dialogue production;
- music/Foley generation and runtime sound banks;
- interactive NLE/DAW parity;
- arbitrary third-party graph execution;
- autonomous critic-based promotion;
- broad 3D/rig model shelf expansion;
- generic remote collaboration/authentication;
- hosted fallback services;
- a universal cache/offload profile;
- full source ontology for every media type.

Deferred does not mean rejected. Each item needs a concrete owner task, finite proof and available WIP slot.

## Architecture invariants

1. Loopback-only by default.
2. No generation or installation from reads, page load or import.
3. One authoritative owner per persistent state and execution concern.
4. Unknown or uncertain is never silently converted to success/failure.
5. Request identity binds exact canonical bytes.
6. Source and accepted derivative remain separate artifacts.
7. Backend/runtime identity participates in execution evidence.
8. Model presence is not compatibility; execution is not acceptance; acceptance is not rights clearance.
9. Agents share the same bounded command semantics as the UI.
10. Advanced/native escape hatches preserve provenance and dirty-state warnings.

## Decision review triggers

Reconsider a retained decision only when evidence changes:

| Decision | Trigger for reconsideration |
| --- | --- |
| stdlib server | concurrency/deployment requirements exceed one local user or current server semantics cause measured blockers |
| plain JS | module/lifecycle defects remain high despite incremental typing and ownership improvements |
| one worker | a real accepted workflow requires safe parallel resources and #178 can prove isolation |
| isolated backends | a pinned shared runtime proves compatibility and rollback across target workloads |
| task-first UX | owner sessions show advanced-first use is consistently faster for ordinary work |
| WIP limit | measured throughput and defect data justify a different bound |
| current evidence model | a domain cannot express a real state without ambiguity, not merely because another schema is fashionable |

## Final decision

The project should enter an accepted-asset convergence phase. Engineering expansion resumes when the existing system demonstrates that it can repeatedly help the owner create, accept, repair and reuse assets with less total effort than direct tool operation.
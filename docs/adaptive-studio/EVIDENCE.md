# Basis, reconciliation and claim boundaries

## Evidence ledger

| Basis | What was actually inspected | What follows |
| --- | --- | --- |
| User's 17 September Create wishlist, 12-page PDF | Supplied text and rendered layout/disclosure tables, especially pp. 5, 8-11 | Preserve workbench-first framing, guarded recipe changes, progressive disclosure and the original run path |
| Owner's current request | Context-aware/dynamic UX, a stack assessment, switchable retro/anime environments, a comprehensive future asset wishlist, strategy/documentation in PRs | Expand beyond v1, without generating images or shipping runtime changes in this pass |
| Earlier generated concept boards | Already present in this conversation | Art-direction references only; their controls, model names, metrics and capacity are not a product specification |
| Repository main | Live ref `eb3fc1e1665f109d90086ad3b3dbe1f5f10dd14b`, guidance and current-state head | Python/ComfyUI remains the backend; no build tool is currently part of the normal launch |
| Local source archive | Earlier workshop-source artifact based on `b4cb8cf29485041027e56c1122310f4b806e0b8f`; main compared against its product base `b8b1409d0f397b7562e67366e51629826ec0ae7d` | Used to inspect unchanged frontend modules, not described as a fresh full checkout of main |
| #540 and #541 | Live PR metadata and scope, not rerun qualification | Open review work; retain the foundation, do not fork its editor |
| Existing UX docs | `docs/UX-WORKFLOWS.md`, `docs/UX-USE-CASE-MATRIX.md`, `docs/UX-AUDIT-2026-09-14.md` | Guides, continuation, ordered references, recoverable drafts and review queues already exist |
| Seedance page | Official page's available text and section structure | Inspiration for a media-led showcase and clear capability chapters; no source-code or animation implementation audit |

The remote compare identified 22 changed paths between the archived product base and inspected main. The shell, workbench, guide-state and guide modules used for this architecture were not among the changes. Changed reference-review and workflow-control-preview files were not treated as fully re-audited here. No full-suite or GPU result is inferred from this inspection.

## Preserve the wishlist's terminology and scope

The PDF's page-5 diagram and route table put **Describe**, **Sources**, and **Review/Generate** in the primary workbench, with recipe discovery and the model catalog out of its main scroll. Pages 8-9 specify section disclosure behavior and user-controlled exceptions. Pages 10-11 distinguish experiments from acceptance.

| Source requirement | Proposed treatment |
| --- | --- |
| Default Create under roughly 1,600 px at 1440x900 | Retain as the v1 scenario-specific target, not a measured result of this strategy |
| Recipe chip plus Change; searchable drawer | Extend with task-aware reasons, installed-state facets and recent choices; preserve explicit application |
| Parameters and adapters progressive | Show the summary in all assistance modes; focus the actual invalid control on request |
| Negative disclosure may open for meaningful content | Retain the user's disclosure choice; do not repeatedly collapse substantive exclusions |
| Mid-flow switch preserves the draft or asks | Expand the difference preview to sources, role order, bindings, backend and unsupported values |
| Mobile 390x844, no horizontal page overflow | Keep a single work column and reachable run control; test keyboard and zoom independently |
| Guided steps are an experiment | Do not force all returning users into a wizard |
| Optional A/B metrics | Use local, explicitly initiated evaluation, not silent analytics |

The supplied v1 non-goals excluded primary redesign of Overview, Library and Settings. The current request explicitly asks for broader workflows, so their treatment in UX-SPEC is a **proposed next phase**, not a claim that the original brief required them.

## Existing ownership that matters

- `app/static/studio-shell.js`: navigation, command dialog, and dynamic loading of current disclosure, setup, bundle and guide modules.
- `app/static/studio-workbench.js`: existing controls, source continuation, readiness explanations and workspace-scoped draft recovery. `StudioSetupDraft.capture/stamp/busy/adopt` is an existing boundary to preserve, not a new object invented by this strategy.
- `app/static/studio-guide-state.js` and `studio-guide.js`: existing authored guidance and target revelation. Extend their semantics before adding another independent coach.
- `app/static/recipe-shortlist.js`: explicit, source-bound shortlist requests; changing context invalidates old advice.
- `app/static/setup-proposal.js` and `setup-apply.js`: reviewed proposals, checked revisions, copied sources and ambiguous-response recovery.
- `app/static/pose-editor-core.js`, `app/references.py`, and `studio_workflow/`: distinct geometry, semantic roles, compilation and execution owners.
- `app/static/read-poller.js`: an existing read-polling utility. A new component must reuse the owner of a read, not quietly add another health loop.

## What the next UI must not repeat

The 14 September owner audit says the guides were wordy and advisory, disabled buttons did not explain their prerequisites, and cross-tool handoffs were unclear. Those are interaction failures. Another illustrated dashboard containing all controls at once would repeat them.

The generated mockup's fictional model label, 12 GB capacity, estimated 28-second duration, five reference thumbnails and ready indicator are not verified facts. Production may display only the selected route's actual capabilities, device observations and receipts. Attractive sample art does not certify any model, pose transfer, adapter stack or source-preservation behavior.

## This pass's boundary

Documentation and isolated specifications may be merged independently of product implementation. No application route, schema, model, package environment, runtime launcher, generation gate or owner decision is changed by the strategy. Planned assets have no bytes, no inferred clearance and no execution authority. Future acceptance distinguishes code present, browser behavior proved, real workflow proved and owner preference confirmed.

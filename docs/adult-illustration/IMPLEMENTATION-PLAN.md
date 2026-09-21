# Implementation plan

Programme #403 is delivered as reviewable slices. Every runtime slice reuses existing typed services and ships tests before broader UI or agent wrappers.

## Foundation delivery

### PR 1 — research, architecture and static contracts

Files in this directory and `research/adult-illustration/`:

- product/authority boundaries;
- control ontology;
- source-reviewed route and technique landscape;
- finite evaluation design;
- programme/route/control/corpus/pack/adapter manifests;
- implementation and agent plans.

This PR is non-executing and references #403–#413.

### PR 2 — offline validator and agent skill

- `scripts/validate_adult_illustration.py`;
- `tests/test_adult_illustration.py`;
- `agent-skills/adult-illustration/SKILL.md`.

Validate schema IDs, authority flags, issue links, adult/content declarations, unique IDs, evidence ordering, bounded ranges/caps and source URLs. Do not fetch the network or inspect installed models.

## Runtime sequence

### 1. Map intent onto existing Prompt/Setup records — #404

- Add a pure `studio_prompt/adult_illustration.py` projection around the existing CreativeIntent/reference records.
- Do not create persistence. Use current Prompt project/setup command services.
- Unit tests first: adult declaration, independent controls, source roles, conflict/unsupported diagnostics, canonical identities.
- Deliver CLI compile/inspect only after the pure contract is stable.

### 2. Route/source intake — #405

- Extend existing model/bundle claim structures with route-card fields only where they are genuinely shared.
- Import cached source snapshots through #9/#144 paths.
- Add current installed route mappings without claiming execution not in `CURRENT_STATE.md`.
- Qualify one fast, quality and multi-image route through existing Experiment/Production commands.

### 3. Adapter qualification — #406

- Implement pure sweep/interference planners and result validators.
- Bind exact installed adapters through existing catalog/bundle substitutions.
- No generic arbitrary LoRA filename input.
- Promote UI controls only after measured interval/interference evidence.

### 4. Geometry artifacts — #407

- Define pure geometry-plan and coordinate-transform contracts.
- Reuse Workflow document asset handles and Repair Studio transform/mask types.
- Add editable pose/silhouette/depth modules to Steps before a bespoke canvas.
- Route difficult geometry to existing Blender adapter.

### 5. Multi-reference and regional binding — #408

- Extend reviewed setup proposals with subject/region and take/ignore projection.
- Recheck source bytes, slot order and transforms at apply and execution boundaries.
- Compare existing boards, role-specific adapters and native multi-image editing through one finite campaign.

### 6. Benchmark harness — #409

- Compile selected corpus cases into existing Experiment Lab manifests.
- Keep generated media and sensitive briefs out of Git.
- Add task-specific review forms and contact sheets using existing Review Desk/Workspace evidence.
- Publish small-sample denominators and retained failures.

### 7. Genre packs — #410

- Map pack modules to exact qualified controls and route alternatives.
- Add Guided and Steps views over the same workflow/setup revision.
- Browser tests: zero submission on navigation/preview, keyboard, 390 px and 200% zoom.

### 8. Training — #411

- Add non-executing dataset/training plan and preflight first.
- Use an isolated runner/environment and explicit human authorization.
- Import only a promoted adapter’s immutable model-library record back into Studio.

### 9. Finishing — #412

- Reuse Repair Studio source/mask/compositor and native export contracts.
- Compare deterministic upscale and diffusion refinement as different derivative classes.
- Retain base and all stage identities.

### 10. Shared agents — #413

- Add domain projections to the existing CLI/SDK/MCP command services.
- UI and headless clients use identical revision/plan identities.
- Fault tests cover stale revision, exact replay, changed request, response loss and no duplicate dispatch.

## Release order

`A0 contracts → A1 one accepted controlled slice → A2 modular controls → A3 multi-reference/contact → A4 packs → A5 training/finishing → A6 shared agent operation`

Do not widen model count or content scope to compensate for a failed earlier gate. Change the hypothesis, control or route and retain the failure.

# Native DCC parity slice: next implementation plan

**Goal:** make one owned authored prop produce honest source-versus-GLB-reimport evidence using current LAS execution owners.

**Status:** proposed. The offline comparator and read-only probe exist; this native integration is not implemented or tested on the workstation by the research-intake pass.

**Read first:** `docs/AGENTIC-CREATION.md`, `research/agentic-creation/README.md`, `app/articulated.py`, `scripts/articulated_prop.py`, `app/resource_admission.py`, `app/resource_receipts.py`, `studio_workflow/agent_bridge.py`. Preserve other active work and follow AGENTS.md.

## Global constraints

No private asset in public fixtures. No install/upgrade. Explicit executable selection, disabled autoexec, immutable source, exclusive tagged output, one durable job identity, bounded process, no retry after uncertain outcome. Existing receipts/provenance remain authority. A native adapter must not pretend to be a Comfy graph merely to use `pre_submit`.

## Review focus

- A candidate must not refit the camera from its own changed bounding box.
- Validation lights/cameras must never leak into the asset export or structural comparison.
- GLB triangulation/renaming/excluded helpers require declared mappings, not ignored differences.
- Missing reimport renders, stale image hashes or incomplete process receipts are not a successful parity run.
- Resource release and process termination must match the actual job lifetime, including failure paths.

## Task 1: qualify the existing probe

- [ ] Run focused offline tests, then admit a 120-second read-only probe on an owned prop copy using the configured Blender path and generated intent.
- [ ] Retain argv, executable/script/source hashes, stdout/stderr, exit status and `scene.json`; rehash source afterwards.
- [ ] Repeat unchanged; compare semantic content. Test installed compatibility lane only with a source file that lane can read. Never feed a newer saved workshop into an older-only transfer script.
- [ ] Add real regression fixtures for any API discrepancy; do not broaden fallback to empty success. Record native evidence separately from unit fixtures.

## Task 2: deterministic capture producer

**Proposed files:** `scripts/dcc_capture.py`, `tests/test_dcc_capture_contract.py`.

- [ ] First write tests for camera-contract equality, frozen baseline framing, helper exclusion, exact resolution/frame/color settings and refusal of unknown view IDs.
- [ ] Implement fixed capture-profile parsing. Generate an external full camera/light/pose record, then derive its digest. Never accept only an opaque agent-supplied camera hash as proof.
- [ ] Load the approved copy with autoexec disabled, observe source semantics before validation helpers, create helpers in a dedicated collection, and render fixed views using the smallest owned CPU fixture first.
- [ ] Write evidence bundles with actual image hashes. Preserve partial failures, but do not write a successful completion marker until all required views exist.
- [ ] Render unchanged twice to establish noise/repeatability before deciding tolerances. Capture hold-out views as independent requested evidence.

## Task 3: explicit export/reimport derivative

**Proposed files:** target-profile logic beside the existing native adapter; `tests/test_dcc_roundtrip_contract.py`.

- [ ] Tests first: hidden collision helper is intentionally excluded; omitted visible mesh is not; triangulation does not masquerade as topology-preserving equality; helper cameras never export.
- [ ] Pin the existing export settings and inclusion list. Export from a copy, start a fresh process, reimport, reconstruct the exact external validation rig and render again.
- [ ] Add a declared source-to-target identity mapping and target-specific invariants. Do not alter the generic strict snapshot comparator to silently forgive GLB differences.
- [ ] Seed missing texture, wrong node color and omitted mesh in owned fixtures. A successful importer exit without controlled reimport views must fail the evidence gate.

## Task 4: bind native operation to existing owners

**Proposed files:** a small native operation adapter following `app/articulated.py`, bounded profile extension under existing resource owners, and tests for prepare/run/recover.

- [ ] Define the native identity from executable/script/source/export/camera pins, not a fabricated model graph.
- [ ] Obtain fresh measurements and a typed resource profile; preserve unknown/unavailable telemetry. Reuse existing reservation/receipt contracts; do not create another global queue.
- [ ] Persist intent before spawn; enforce process timeout; keep exactly-once attempt identity and all failure artifacts. Recovery only observes retained state.
- [ ] Register artifact lineage only through an appropriately private/public workspace profile. The public authored-prop fixture does not authorize private source uploads.
- [ ] Add a narrow tool in the existing AgentBridge only after owner methods and adversarial tests pass. MCP tool cancellation is not job cancellation.

## Completion evidence

Focused tests plus actual source/export/reimport views, unchanged rerun noise, seeded-failure outcomes, process/resource receipts and an unchanged source hash. Verify the broader suite and repository checks. Human review still selects intended visual differences; native technical evidence never resolves identity or licensing acceptance. Do not merge by claiming a fake-API fixture proves Windows/AMD operation.

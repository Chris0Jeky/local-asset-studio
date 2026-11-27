# Durable character handoff continuation implementation plan

> **For agentic workers:** use the existing subagent implementation/review workflow. The owner explicitly requested autonomous continuation in the same manner; the original run's scope, branch, source transport and generation limits remain controlling.

**Goal:** make the current-authority character pipeline usable at the actual Studio indexing boundary, prove a durable at-most-once worker handoff under crashes/concurrency, and verify a received pack before a native consumer could mutate anything.

**Architecture:** retain the eight-stage kernel and ordinary admission gate. Fix only the source-provenance compatibility bug found on PR #2049. Add a durable dispatch journal alongside the attempt ledger, and an independent read-only handoff verifier over complete staged bundles. A synthetic worker port exercises the actual protocol without sending network requests or creating generated content.

**Tech stack:** existing Python 3.12+, SQLite, pathlib/hashlib and current Pillow/jsonschema dependencies. No new installed package, runtime or model.

**Spec:** this plan extends `DESIGN.md`, `ADOPTION.md` and the user's explicit continuation of P36-B-20261126-2. Previous finished head is `835e93c82c64e558302033c81d4bcdb7056a76cd`; base remains `0270760a`.

## Kill criteria and constraints

- Required identity failure against the exact accepted concept blocks preparation, dispatch and consumer admission.
- Old acceptance, a green score, READY, or an empty output folder cannot create current authority.
- A claimed or uncertain attempt is never rearmed, stolen by expiry, or repeated after restart.
- Ordinary admission/export continues to refuse every unresolved attempt. The dispatch operation may recognize exactly its own full identity-bound prepared reservation while holding the ledger claim transaction; no generic ignore list or candidate-provided green report.
- Generated, inspected/accepted and licensed remain independent. All real-character/native claims stay planned; only software/lab results are implemented.
- No actual generation, network submission, native import, automatic page-load action, package change or ComfyUI edit. No main push or merge.
- All source/tests/evidence stay in this run directory; reports stay in the original report directory. Runtime results stay beneath `.runtime/`.
- Only root edits the Studio checkout. Specialists author isolated files; root integrates and publishes through GitHub, at most ten files per checkpoint.

## Approaches and decision

Another offline policy layer would add little while the real indexing compatibility bug remained. Directly wiring the installed worker/native importer would exceed this run's source scope and lacks the owner's native runtime. The selected approach closes the real indexing seam, implements the durable coordination/consumer contracts in the run-local prototype, and uses crash/process/file tests to establish their exact software behavior. Live UI/worker/native adoption remains explicit future work.

## Review focus

1. Real `Studio.index_outputs` mutates output annotations after Workspace registration; those changes must not reject valid provenance or weaken asset binding.
2. A process can stop before/after reservation, durable claim, callback entry or acknowledgement. No retained claim may become a second callback.
3. Another process can race the same request or a changed request; SQLite claims must serialize without adopting foreign/orphaned attempts.
4. Authority, workflow intent or own-ticket identity can change between preparation and dispatch. Exact current checks must still refuse.
5. A bundle can be internally redigested after tampering; schema/hash consistency must be distinguished from original owner authority and fresh checks.

## Tasks

### 6. Actual Studio indexing compatibility

Files: modify `studio_authority.py`; add focused real-indexing regressions to its tests or a dedicated module.

- [ ] Reproduce PR review `discussion_r4714353061` through actual `Studio.index_outputs` with real Workspace/files, without initializing a runtime.
- [ ] Compare stable source provenance and validate added asset binding separately. Only known, validated advisory annotations are excluded; unknown provenance changes refuse.
- [ ] Test import and normal generated-job shapes, side annotations, wrong asset/index/source fields, and preserve all existing authority refusals.
- [ ] Publish the corrected source/tests and update the review disposition.

### 7. Durable dispatch coordinator

Files: create `dispatch_coordinator.py`, simulation support and `test_dispatch_coordinator.py`.

Consumes: current `admission.check_transition`, `attempt_ledger` identities/observations, actual Studio submission-evidence rules, an explicit immutable effective submission intent and a simulation callback port.

Produces: a durable prepared/claimed/observed/uncertain journal, structured prepare/dispatch/recovery reports and a bounded simulator. Interface details are frozen after the current worker-seam audit.

- [ ] Write failing tests for the seven adoption refusals and one valid/replayed control.
- [ ] Implement exact own-reservation recognition under a serialized claim transaction; persist the claim before callback invocation.
- [ ] Add real multi-process competition, restart, lost response and interruption tests at each durable boundary.
- [ ] Demonstrate changed workflow/authority/marker and orphaned reservations cannot be replayed or silently adopted.
- [ ] Publish source/tests with numerical callback/duplicate outcomes, separating simulation from live worker adoption.

### 8. Independent handoff consumer verification

Files: create `handoff_verifier.py`, `test_handoff_verifier.py`.

Interface: `verify_handoff(bundle, *, experiments=None, ledger_path=None, require_current=False, allow_synthetic=False, expected_pack_id=None)` returns a structured, hashed report with separate integrity/current-authority facts and no native import authority.

- [ ] Write failing tests over actual exported bundles: changed assets, sidecars, semantic/root/provenance data, absent/duplicate JSON keys, links and paths.
- [ ] Reconstruct and compare the guarded manifest, all sidecar bindings, schema/references and every copied file. Recompute supplied semantic/family checks.
- [ ] Add optional fresh authority using explicit caller-provided Workspace/ledger roots. Bundle-claimed paths never select a local authority source.
- [ ] Test withdrawn authority after export, synthetic refusal by default, and explicit synthetic integrity-only mode.
- [ ] Publish verifier/CLI/tests and its bounded acceptance matrix.

### 9. Reproduction, review and handoff

Files: extend `prove.py`; add compact continuation evidence/hashes; update README, ADOPTION, VERIFICATION, research report and RUN_STATE.

- [ ] Preserve the prior 202-test evidence as a historical baseline and generate the expanded proof under fresh runtime directories.
- [ ] Run the full relevant prototype suite and actual-indexing seam tests; run repository validation. Run the repository's mandatory full suite if app/catalog code changes; neither is planned.
- [ ] Reproduce deterministic continuation outputs twice and compare hashes. Record failure distributions and callback counts without turning simulation into native qualification.
- [ ] Obtain independent review of coordinator and consumer boundaries; fix concrete findings with regressions.
- [ ] Update existing Lumenfold #3175 additively, publish report-only Drive copies, inspect all final branch files, set phase done and return PR #2049 to ready.

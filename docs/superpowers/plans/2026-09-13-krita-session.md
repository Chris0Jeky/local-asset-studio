# Krita document session implementation plan

**Goal:** Import an existing protected result into the inspected open Krita
document as a reversible layer, rejecting stale unsaved state.

**Architecture:** A native session owns the current document reference and a
revision fingerprint. A small menu extension and an external request builder
share typed artifact contracts; existing Studio commands still own inference.

**Tech stack:** Python stdlib, Krita Python API and PyQt5 inside Krita; existing
Pillow compositor outside Krita.

**Spec:** [Open-document design](../specs/2026-09-13-krita-session-design.md).

**Execution:** Root owns implementation in the isolated checkout, with one
fresh-context independent review after proving checks. This follows the owner's
explicit frontier-architecture and worker-review routing.

## Constraints

- No Studio/Comfy restart or new generation; retain all existing attempts.
- Never save/close/clear modified state on the user's native document.
- New artifacts and proposed layer only; no deletion on failure or retry.
- Existing flat normal RGBA/U8 profile contract and 16-million-pixel ceiling.
- Real layer and selection state participates in each revision check.

## Task 1: native session and causal tests

Files: `integrations/krita/document_session.py`,
`tests/test_character_krita_session.py`.

Interfaces: `Session(document)`, `inspect()`, `capture(output)`,
`import_request(path)`, `show_source()` and `show_result()`. Capture returns a
source/snapshot manifest; import consumes a pinned native plan and that manifest.

- [ ] Write failing tests for import into a modified document, changes hidden by
  another layer, stale selection/order, failed native readback, repeat import,
  exact source/result toggles and refusal after user changes to the proposal.
- [ ] Run `python -m unittest discover -s tests -p test_character_krita_session.py`.
- [ ] Implement the session without network, shell, file overwrite or document
  save/close on the active object. Persist exclusive intent before mutation.
- [ ] Run the focused suite and existing `test_character_krita.py` contracts.

The main causal shape is:

```python
snapshot = session.inspect()
document.hidden_layer.setPixelData(changed, 0, 0, width, height)
with self.assertRaisesRegex(ValueError, 'stale'):
    session.import_request(request_path)
self.assertEqual(document.layer_count, original_count)
```

## Task 2: explicit user/agent entrypoints

Files: `integrations/krita/studio_session/`, its `.desktop` entry,
`scripts/character_krita_session.py`, and session tests.

- [ ] Build a request from a capture and the existing prepared native package;
  revalidate source hashes and serialize a new typed JSON request, never code.
- [ ] Package the optional fixed-source extension; install only to an explicitly
  configured native scripts directory, without replacing another installation.
- [ ] Wire menu Capture/Import/Show source/Show result to the shared session.
  Initialization has no canvas or filesystem mutation.
- [ ] Prove invalid packages and changed snapshots fail before canvas mutation.

## Task 3: native proof and handoff

- [ ] Run a fixed repository harness via configured Krita on an owned synthetic
  document. Prove active unsaved-source preservation, exact import, source/result
  toggle and rejection after a hidden-layer edit; preserve failure artifacts.
- [ ] Inspect native exported comparisons; run full unittest discovery and the
  repository validator serially.
- [ ] Document commands, native evidence and unverified GUI/creative limits in
  the character runbook and CURRENT_STATE; leave #71/#65/#72 open.
- [ ] Obtain one independent review, fix confirmed blocking defects, qualify
  the final PR head, merge within T2 gates and remove only the owned clean tree.

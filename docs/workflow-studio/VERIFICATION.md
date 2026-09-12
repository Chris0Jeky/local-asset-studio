# Verification and known limits

## Evidence from this implementation environment

- `python -m unittest discover -s tests -p test_workflow_studio.py`: **34 tests passed**. These include strict JSON and graph validation, output closures, type/value errors, explicit bypasses, native-adapter refusal, stale schemas, retained-ticket replay, concurrent callers, response loss, intent-without-job, reference-byte changes, real loopback HTTP security/dispatch and a CLI prepare/run/replay round-trip against a fake Studio.
- Node syntax checks passed for `workflow-studio.js`, `studio-guide.js` and the modified `studio-shell.js`; Python compilation of the modified handler extension passed.
- An inert Chromium DOM smoke run passed with the actual new page/CSS/JS and an in-memory synthetic Comfy schema: seven goal cards, recipe import, numeric edit, undo/redo, schema-refresh check invalidation, disabled-node rejection, explicit bypass, checked graph download, 390px navigation/no horizontal page overflow, zero page errors and zero model submissions. The exported graph was parsed and its bypass wiring asserted.
- Desktop goal/builder and mobile screenshots were rendered and inspected from that inert fixture. They show synthetic Number/Scale/Output nodes, **not the installed model inventory or generated media**.

Browser command used:

```sh
python tests/workflow_studio_browser.py \
  --browser-executable /usr/bin/chromium --inert-dom \
  --screenshots /path/to/local-evidence
```

The environment's Chromium policy refused normal loopback page navigation (`ERR_BLOCKED_BY_ADMINISTRATOR`). No browser policy was changed. The inert mode uses inline authored assets and an in-memory API fixture with browser network requests aborted. It therefore does **not** prove full navigation, localStorage persistence or contextual-coach interactions against the actual server. Separate unit tests did exercise real loopback HTTP through the new handler; the two evidence types must not be conflated.

## Reproduce the fuller browser smoke on an authorized local environment

With Playwright and its Chromium already available:

```sh
python tests/workflow_studio_browser.py --screenshots .runtime/workflow-studio-proof
```

A `--browser-executable` path may select an existing permitted Chromium. Without `--inert-dom`, the script also checks actual navigation, browser draft reload/restore and coach next/pause against its synthetic HTTP fixture. It still does not run the configured Studio, installed Comfy classes or a GPU job. Browser tooling is opt-in test tooling, not a new application dependency.

## Repository and live gates

The full private repository could not be checked out into this environment through the available local network path. The source integration was audited through the GitHub connector, and the new isolated suite ran locally. **Do not treat 34 passing tests as the full repository suite.** Hosted CI status on the published PR is the authoritative source for full-suite/repository-validator evidence; inspect the actual run before merge.

On the configured machine, additionally verify: server startup and existing Prompt routes; the new sidebar entry from all shared-shell pages; every guide anchor after selecting appropriate recipes/assets; draft save/restore and localStorage-denial UX; model inventory/schema refresh across backend changes; representative large and custom-node graphs; int64 seed refusal; no auto-submission on navigation/import/check; and a deliberately approved registered-recipe ticket with its real retained job/asset evidence.

No GPU execution, actual Comfy schema compatibility, full native workflow fidelity, live crash recovery, VRAM/host-memory fit, generated asset quality or licensing acceptance was established by this work.

## Deliberate limitations

1. Generic edited graphs are compile/export-only. The `/run` path only accepts registered recipe tickets and delegates to the existing worker.
2. Custom widgets, native visual/subgraph round-trip, Step modules, server workflow storage, command CAS, SDK and MCP parity are tracked work, not hidden unfinished buttons.
3. Run receipts provide at-most-one dispatch attempt per retained intent inside the existing Studio ownership model. They are not a distributed exactly-once protocol. Receipt deletion, filesystem loss and multiple independent processes are outside the guarantee.
4. Preparation can stage local references. Pinning covers staged LoadImage bytes and existing recipe metadata, not all model/custom-node external files or subsequent filesystem changes.
5. Browser history/draft revisions are local. Large-graph performance, zoom/wire-drag polish, semantic coach anchors and completion evidence need further testing and implementation.
6. Core structural validation is intentionally conservative. A “valid” export is not a successful Comfy runtime validation or hardware preflight. Existing issue #97 and related runtime owners remain relevant.

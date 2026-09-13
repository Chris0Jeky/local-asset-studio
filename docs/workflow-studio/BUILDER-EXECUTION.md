# Builder run controls and retained-ticket recovery

Implementation slice for #122 over the preset-document adapter in #138.
No changes to the shared Studio executor, model runtime or job schema.

## Use in the Studio

Open **Guided workflows → Workflow builder**. Choose a registered image recipe,
import its graph, and edit its supported prompt, dimensions, sampling or LoRA
controls in Nodes or Steps. Keep the chosen recipe in the dropdown. Near the
bottom of the builder, **Run a compatible recipe** offers these explicit actions:

1. **Prepare run ticket** proves the complete graph still maps to that recipe.
   It returns no ticket when fixed inputs, wiring, node membership or outputs
   have changed. Reference recipes still use Create. Nothing is queued.
2. Review the returned preset ID, controls, source hash, ticket hash and job ID.
   **Download ticket** and **Download source report** preserve the exact request
   outside this browser tab. The report is a companion provenance artifact;
   it is not a new durable shared-document-to-job relationship.
3. **Run prepared recipe** asks for confirmation, retains dispatch intent, then
   calls the normal `/api/workflow-studio/run` route. One graph invocation may
   produce more than one output. Existing readiness and host-memory checks apply.
4. **Observe job** reads the known job once. **Recover same request** explicitly
   resends the original ticket when needed. It can dispatch if the original
   request never reached Studio, or recover the existing job/intent if it did.
   Recovery never uses later draft changes or prepares a replacement ticket.

Clear an unsubmitted or terminal ticket deliberately before another attempt.
An active, uncertain or reconciliation-required record cannot be cleared through
these controls. Clearing does not delete server evidence or cancel work. A file
exported for another agent may have been executed outside this tab; retain its
identity and inspect it rather than treating local prepared state as proof of
non-execution elsewhere.

## State and transport boundaries

`workflow-ticket-state.js` owns only a small browser request record:
`{version, phase, source, report, last_status}`. It has two local phases,
`prepared` and `attempted`; server job status is separately observed. It is not a
new job lifecycle or execution journal. The server remains authoritative.

- Exact report/ticket and the source signature are held in **sessionStorage**.
  This survives a same-tab reload, not necessarily closing the tab, browser
  storage deletion, a crash or a different origin. Download the files.
- Storage writes succeed before a run request is sent. A storage failure does
  not grant permission to dispatch. Failed clearing retains the in-memory record.
- Preparation captures the draft epoch, recipe choice and displayed schema.
  A changed value while awaiting the result discards that late result without
  replacing current work. Editing after preparation disables the initial Run.
  Schema comparison uses only backend/schema fingerprints, not unsafe numeric
  bounds in installed node metadata (for example a uint64 seed maximum).
- After dispatch intent is retained, all HTTP errors, malformed/null replies,
  wrong-job identities and transport failures leave the same ticket available.
  No failed response is used to claim generation did not occur.
- Requests have a 30-second client abort deadline. Aborting a wait does **not**
  cancel shared Studio work. Recovery remains a deliberate operation.
- No startup requests, automatic polling, automatic retries, node installations,
  backend switches or model work are introduced by this component.
- The browser rejects unsafe integer values rather than rounding a seed. The
  Python CLI/SDK is the exact-integer path. Fingerprints shown are server-issued;
  the browser does not claim cross-language canonical-hash recomputation.

The plain-JavaScript component uses the existing frozen `WorkflowStudio` bridge,
its snapshots/render events and the existing recipe dropdown. It does not own
or mutate editor documents. It uses textContent, semantic buttons, status text,
visible native confirmations and scoped responsive CSS. The new scripts load
after the editor/Steps scripts; other Studio pages are unchanged.

## Verification and limitations

Two normal unittest wrappers execute **14 ticket-state contracts and ten
actual-UI wiring contracts** through Node. They prove no startup dispatch,
prepared/run separation, stale results, consent refusal, double clicks, storage
failure, response loss, exact replay, mismatched replies and observation-only GET.
The wiring fixture executes the real component but supplies a minimal DOM and
mocked fetch/storage; it is not a browser or full-shell integration.

Optional Chromium reproduction:

```bash
python tests/workflow_execution_browser.py --chromium /path/to/chromium --out .runtime/workflow-execution-browser
```

Requires an external Playwright/Chromium tools environment; ordinary Studio
requirements are unchanged. The test renders the actual component scripts and
scoped CSS, with fixture global styling, editor bridge, storage and transport.
It calls real Python projection and ticket journaling over the fake runtime.
The measured run made five fixture requests, created exactly one fake job despite
two run calls, reported zero browser errors, and posted zero model submissions.
Desktop and 390px screenshots were inspected; no horizontal page overflow.
This does not prove the complete Studio shell or native browser-origin storage.

No installed-Comfy inference, workstation deployment, artwork evaluation or
licensing acceptance is claimed. Arbitrary graphs, new nodes, selected-output
subsets, full reference lineage, event-stream progress and owned cancellation
remain #122. Native widget/subgraph fidelity remains #121. These run controls
are a usable registered-compatible path, not complete ComfyUI frontend parity.

# Keep tuned bundles as shared Steps workflows

13 September 2026. Implementation extends #144 and is stacked on #151 at
`395b22de2bc203a199599a509fd0f098c78020b3`, itself on #146.

## Reconciliation

Main was rechecked at `a8eacdb108531c8c12a36c93f5a4f8a793e2fb74`. Recent merges
#137/#138/#139/#141/#142/#145 cover backend observations, preset-compatible
execution, Anima evidence, runtime status, intake and builder run controls.
#131/#134 already provide shared Steps/documents and agent commands. Neither
#146 nor #151 was merged when this work started. The source-404 review fix in
#146 is retained; #151's bot review was unavailable because of its usage limit.

This change connects bundle drafts to those existing shared documents. It does
not replace their commands, ticket journal, model manager or worker. #143 still
owns representative portfolios; the owner's Anima B preference is not promoted
to finished-art acceptance. HUMAN_TODO and workstation runtime remain unchanged.

## User workflow

In **Create → Explore creative bundles**, choose and tune an image recipe. Expand
**Keep this setup as a reusable workflow**, give it a name, then choose
**Prepare workflow**. Inspect its named Steps and optionally download the document.
Check the explicit save confirmation and choose **Save new workflow**.

This saves a new ordinary Workspace workflow, not an additional bundle database
or a replacement of another saved workflow. The original Create controls and
references are not reset by this action. No job is prepared, submitted or approved.

Follow **Go to Workflow builder**, choose **Refresh saved**, select the saved
name, then **Open current → Steps view**. Opening/replacing the builder draft
retains its existing warning. The new handoff does not silently navigate into or
replace an unsaved builder document. Further edits use the existing shared
revision checks, history, restore and agent interfaces.

Steps describe idea/conditioning, appearance/adapters, canvas/sampling, resource
loaders, decode/output, and any unclassified graph nodes. Every exposed control
points at an actual graph input, including companion bindings. Model and
text-encoder strengths remain native inputs, not an invented universal style
slider. A later builder edit to one companion may require updating the others
before preset-compatible execution; the existing projection explains that rule.

## Projection contract

`bundle-workflow-core.js` is pure. The small addition to `bundle-explorer.js`
provides a detached snapshot of the exact preset, staged source recipe, resolved
controls and inspected graph. Fixed same-origin modules are loaded only when the
reusable-workflow surface is mounted; loading them performs no API request.

Prepare reads the existing `/api/workflow-studio/presets/<id>` authoring route.
The converter compares its node classes and effective inputs with the earlier
inspection; a changed graph, checkpoint, connection, catalog default or backend
refuses. It never trusts a family label as a substitute for preset identity.
A late response cannot replace preparation after the bundle or name changes.

Only declared scalar controls may write the declared primary and companion
inputs. Conflicting overlapping controls, connections disguised as values,
unknown controls, invalid binding targets and native type changes refuse.
Fixed outputs and filenames remain untouched. Zero-strength adapters remain in
the authoring graph rather than being translated into disabled-node bypasses.
The existing executor remains responsible for its own pruning and final proof.

Nonoverlapping named Steps retain all nodes. Large groups split at 32 exposed
controls; existing 64-group, 256-node and bounded-JSON limits apply. Unknown
classes are preserved under a neutral label, not certified as executable.
Unsafe JavaScript integers and nonfinite values refuse rather than being rounded;
use the exact-integer SDK for inputs outside the browser subset.

The document is ordinary `studio.workflow/v1`. Its `source.bundle` records the
source recipe ID/name and effective controls with an explicit **unexecuted
authoring** statement. It does not inherit a render receipt, art acceptance or
server-recorded fork origin. Model binaries and runtime packages stay external.
The new metadata identifies the source recipe by ID, not an authenticated
immutable model/version provenance chain. Source-version claims remain #144.

## Persistence and uncertain replies

`bundle-workflow.js` reuses `WorkflowProjectState.State` unchanged, including the
existing `studio.workflow.pending-save.v1` session record and exact request-body
journal. Save always creates a **new** document using the ordinary document POST.
The exact request is retained before fetch. A storage failure prevents dispatch;
there is no automatic retry and no fresh identity after an ambiguous result.

An explicit Retry sends the same request. Before accepting a successful receipt,
checks bind it to the existing service's UUIDv5 request identity and original
revision, require a non-generating response, and compare the returned full
document with the requested one (apart from the server revision). A malformed,
wrong-ID or wrong-content response keeps the journal. Detached panels do not
clear pending records unseen. Existing builder pending writes are not replayed
by this surface; the user is directed to resolve them in the builder.

The service already stores requests and append-only revisions in a single SQLite
transaction. Replaying a create returns its original revision even when the head
has subsequently advanced. The UI states both revisions; it does not overwrite
the advanced head. Later in-place edits belong to the builder's existing
`expected_revision` commands. Initial bundle save is a new copy, not a revision
update or a cryptographically authenticated approval.

Session storage is tab/origin scoped: it survives a same-tab reload but is not
permanent evidence after tab closure or deletion. Download the authoring document
before leaving. This change adds no pending-request export or cross-tab journal.
The 30-second browser timeout stops waiting; it does not cancel a committed save.
A successful save does not mean its workflow can currently execute.

## Verification and limits

Executed in the focused local source workspace:

- 23 Node policy checks passed: exact control/companion mapping, full graph and
  destinations, named groups, stale inputs, unsupported reference routes, limits,
  storage-before-dispatch, Python/JS UUID identity and receipt/replay checks.
- The normal unittest wrapper passed; six tests requiring the actual shared
  service source were skipped locally, not reported as full-repository proof.
- JavaScript syntax and Python compilation passed.
- The actual new UI files passed Chromium component checks at 1440px and 390px:
  stale drafts, quota failure before POST, a committed save with malformed reply,
  component reconstruction and explicit same-request recovery create one fixture
  record, with no inference-route calls. Screenshots were inspected.

Normal local browser navigation returned `ERR_BLOCKED_BY_ADMINISTRATOR`. The
successful local run uses explicit `--inert --fixture-store`: set_content,
simulated session storage, a disclosed crypto shim and simulated read/write
transport/receipt storage. It tests UI behavior, **not** native-origin persistence
or the real SQLite service. No networking restriction was bypassed.

The committed driver defaults to real local HTTP, native sessionStorage and
WebCrypto, and the real WorkflowDocuments/commands/validation implementation on
temporary SQLite. Its optional receipt fixture is never the default. The new
`Bundle workflow browser` CI lane installs test-only Playwright 1.57.0/Chromium
and runs that default plus the six real-service tests. It also retains screenshots.
No normal application dependency or startup build is added. The repository's
existing full-suite/validator and Windows checks remain in place.

Read the actual PR check results for the hosted outcome; a configured lane is not
a passing result. Even a passing component HTTP run is not the full Studio shell,
owner's Windows/Comfy runtime, model inference, screen-reader/200%-zoom audit or
an actual representative-art portfolio. Full owner-PC acceptance remains below.

```bash
node --test tests/bundle_workflow_core.cjs
python -m unittest discover -s tests -p 'test_bundle_workflow.py' -v
python tests/bundle_workflow_browser.py --out .runtime/bundle-workflow-proof
# Limited environment only; output must be labelled as simulated:
python tests/bundle_workflow_browser.py --fixture-store --inert --out .runtime/bundle-component-proof
```

## Next acceptance

Save one unchanged and one deliberately tuned Anima setup through the real
Explorer, reopen both in the existing builder and compare their actual bindings.
Edit one in the builder while an agent holds its old revision: the existing stale
command must conflict; restoring an older revision must append rather than erase
history. Preparing this acceptance need not generate an image. Preserve all
uncertain jobs, active downloads and the owner-controlled Windows restart.

Remaining #144 work: exact resource/source-version recommendation claims,
general dependent substitutions and an explicit shared-document re-entry route
from Explorer. Remaining #143 work: bounded representative trials with retained
failures, representative selections and exact resource/runtime evidence.

## Primary references checked 13 September 2026

- [MDN sessionStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage):
  tab/origin lifetime and storage-policy failure explain retaining requests before
  sending while avoiding a permanent-storage claim.
- [RFC 9562 UUIDv5](https://www.rfc-editor.org/rfc/rfc9562.html#name-uuid-version-5):
  the existing Python service's deterministic namespace/name identity. SHA-1 is
  used only to match that identifier, not as an authentication or approval check.
- Repository contracts: `studio_workflow/http_extension.py`, `documents.py`,
  `document_http.py`, `core.py`, `steps.py`, and
  `app/static/workflow-project-state.js`. These existing interfaces, not a new
  model-provider API, are the implementation authority.

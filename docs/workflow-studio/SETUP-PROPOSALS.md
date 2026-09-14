# Review a proposed setup before changing Create

[Reviewed setup application and recovery](SETUP-APPLICATION.md) extends the preview with explicit shared revisions, copy-only Apply, Undo and original-request inspection. Preview remains read-only; see that guide for supported routes and remaining #232 limits.


This extends [ordered source advice](ORDERED-SOURCES.md) with a complete **review-only
setup proposal**. It does not implement the staging/apply/undo portions of #232.
The current Create draft, local file selection, attachments and lineage remain intact.

## In the Studio

Select one to three images in the Asset library, choose **Find recipes for selected
images**, set each Picture's role and explicitly check the starting recipes. On a
source-bound suggestion choose **Preview proposed setup**. The dialog starts from
your current positive and negative wording, never the target recipe's example.
Change the desired result and each Picture's **Use from this image** / **Do not
transfer** contribution, then choose **Build proposal**.

The review shows all current versus proposed bound settings, including controls
that would disappear. It also shows recipe identity, batch reset to one, every
source/role/slot, projected reference transforms, source lineage, cleared
continuation context and pending local inputs. The exact primary prompt after
reference guidance is expandable. Sampling and adapter values are the **target
graph defaults**; this slice does not offer arbitrary numeric edits or inherit an
unrelated source model's schedule.

Expand **Edit wording and source contributions** to revise the proposal. A wording
edit clears the old report. Changing Create or recipe advice makes the captured
context stale: close the preview, check the chooser again, and reopen it. Closing
or pressing Escape restores focus to its opener where available. **Export proposal
JSON** downloads the reviewed report, not an executable recipe or an approval.
The export includes captured prompts, filenames and reference metadata; review its
contents before sharing. It contains no source image bytes.

Opening, building and dismissing a proposal never attach/upload, save, switch
backends, install dependencies or generate. Export is the only explicit file
output and is a browser download. There is intentionally no Apply button.

## Shared request and agent use

The existing loopback server exposes `POST /api/workflow-studio/setup-proposal`.
Capabilities advertise `recipe_setup_proposal: true` and `recipe_setup_apply: false`.

Use the actual graph hash from the checked candidate and exact Workspace IDs/hashes.
The shape below is illustrative; replace every marked identity before requesting
an observation. The `draft` must be the complete current declaration, not an
invented substitute for a person's active browser state.

```json
{
  "goal": "reference-image",
  "preset_id": "qwen-3ref",
  "expected_template_sha256": "ACTUAL_TARGET_GRAPH_SHA256",
  "sources": [
    {"asset_id": "ACTUAL_ID_1", "sha256": "ACTUAL_SHA256_1", "role": "identity"},
    {"asset_id": "ACTUAL_ID_2", "sha256": "ACTUAL_SHA256_2", "role": "pose"},
    {"asset_id": "ACTUAL_ID_3", "sha256": "ACTUAL_SHA256_3", "role": "style"}
  ],
  "draft": {
    "version": 1,
    "updatedAt": 0,
    "templateHash": "ACTUAL_CURRENT_GRAPH_SHA256",
    "pendingInputs": [],
    "recipe": {
      "preset": "ACTUAL_CURRENT_PRESET",
      "controls": {"positive": "My current brief", "seed": "9223372036854775807"},
      "batch": 1,
      "references": [],
      "parent_assets": [],
      "parent_by_input": {}
    }
  },
  "positive": "Keep the character, use the second picture's stance and the third picture's rendering style.",
  "negative": "",
  "guidance": [
    {"contribution": "face and costume", "avoid": "background"},
    {"contribution": "stance", "avoid": "identity and costume"},
    {"contribution": "rendering style", "avoid": "subject and composition"}
  ]
}
```

`parent_by_input` maps `reference` / `lastReference` to a **single parent ID**, not
an array. Existing reference records and optional `continuation` are retained in
the before state. `pendingInputs` records pending local inputs; their bytes are not
exported. `updatedAt=0` removes a volatile browser timestamp from proposal identity.
Numeric controls, especially 64-bit seeds, should be strings. Unsafe numeric JSON
values are refused rather than rounded. Missing negative-prompt bindings require
explicitly empty negative wording rather than silent omission.

With the Studio already configured and running:

```console
python -m studio_workflow.setup_proposal request.json --url http://127.0.0.1:8191
```

The CLI reads only this bounded UTF-8 file and prints a report to stdout. Input,
transport and observation errors produce structured stderr and exit 2, without
retrying or producing a success report. It does not start Studio or ComfyUI.

```python
from pathlib import Path
from studio_workflow.core import decode
from studio_workflow.sdk import WorkflowClient

request = decode(Path("request.json").read_bytes())
report = WorkflowClient("http://127.0.0.1:8191").setup_proposal(request)
assert report["can_apply"] is False
print(report["proposal_sha256"])
```

The existing stdio MCP bridge exposes **`recipe_setup_proposal` in read mode**.
Its `request_json` argument is the JSON text above, preserving wide integers as
text and using the same validation/client. It has no arbitrary-file or mutation
argument. Existing bridge installation and mode setup are in
[AGENT-QUICKSTART.md](AGENT-QUICKSTART.md).

An agent cannot fetch the live browser-local Create draft from this service. It
can review a caller-supplied declaration or the request retained in an exported
proposal. Interleaved human/agent application requires the later shared draft
revision contract; do not market this preview as already providing that contract.

## Ownership and implementation

| Component | Responsibility |
| --- | --- |
| `studio-workbench.js` / `StudioSetupDraft` | Copied normalized before state and synchronous stamp from the existing draft owner; no new persistence |
| `recipe-shortlist.js` | Explicit candidate selection for preview; ordered source context and invalidation event |
| `setup-proposal.js` / `.css` | Review dialog, captured request, async guards, exact-byte verification, diff and deliberate export |
| `studio_workflow/setup_proposal.py` | Stateless bounded proposal service, CLI and shared response checks |
| Existing `shortlist.py` | Target-scoped graph, source-role and prerequisite observations; public shortlist behavior retained |
| Existing `app/references.py` | Same-byte reference record, shared pure transform/wording helpers and actual reference compiler |
| Existing HTTP/SDK/MCP | Same loopback, request-size, response-framing and permission-mode boundaries |

### Source and graph binding

The service validates the complete request before observing Studio. It checks a
unique registered target, exact raw graph SHA-256 and agreement between parsed
graph and raw bytes. Bound controls are read from that graph, not a stale catalog
projection. Ambiguous fan-out or unsupported defaults refuse rather than inherit
arbitrary values. Explicit positive/negative text replaces example wording.

Each image is checked with the existing bounded reference reader: one captured
buffer determines its hash, byte count and EXIF-oriented dimensions. This preview
opts into an explicit pixel-limit guard before orientation/decoding, without
changing Pillow globals or relaxing the legacy compiler policy. The image must
match both the expected hash and the current nontrashed Workspace record. Sources
are reobserved after proposal construction. Backend operation, catalog bytes and
raw graph bytes are also checked again. None of these observations is an atomic
lease against a later external writer.

Candidate assignments must match the exact number and order of sources. Named
role inputs reuse `guidance_text` and `reference_transform`; tests compare the
proposal with the actual compiler on one-, two- and three-reference Qwen graphs.
Per-Picture guidance is added to the same primary positive binding as compilation;
other positive bindings receive unprefixed desired-result text. A `source` role is
not silently renamed `identity`. Whole-image routes reject per-Picture text that
they would ignore and label unprojected preprocessing honestly.

A shared transform regression exposed dimensions rounded to zero before the next
scale calculation. The helper now rejects an extreme aspect ratio before division,
retaining the existing deliberate-crop guidance. No source is recropped here.

### Complete diff and identity

The seven diff sections retain exact before and proposed values, including removed
controls, attachments/lineage and continuation/pending-input changes. The proposed
`intent` uses source handles with `staged:false`, not executable upload filenames.
The report flags `can_apply`, `execution_authorized` and `generation_submitted`
are always false. Neither a valid checksum nor a displayed prerequisite gives
execution authority.

`proposal_json` is the exact UTF-8 canonical server JSON text of the report body;
`proposal_sha256` hashes those bytes. The response also has a parsed copy for
rendering. Both clients compare the copies and request context. Browser WebCrypto
hashes the retained text, not a JavaScript reserialization that might alter number
spelling. This is a repository-specific integrity envelope, **not** a claim of
RFC 8785/JCS compatibility, signing or authentication. Rehashing an edited report
cannot make it an approved setup. Client checks independently retain explicit
wording, ordered role contributions and the before/after diff contract.

The draft hash is labeled **caller-declared browser draft; not a server revision**.
The browser additionally compares the existing draft stamp, reference epoch and
pending attachment state. It rechecks before and after asynchronous hashing and
rejects changed context and A→B→A edit sequences. A 15-second single-flight deadline
aborts the browser request and invalidates any late reply; it neither claims to
cancel server computation nor automatically retries. Opening a dialog does not
start that request. Failed/expired reads cannot enable export of an old report.

### Bounds and unsupported cases

Input is at most 128 KiB of strict JSON, with one to three checked sources, up to
8000 characters of positive/negative wording and up to 1500 characters per
contribution/avoid field. The existing 20 MiB per-reference byte limit and Pillow
pixel policy apply. Graphs are at most 1 MiB, catalog observations at most 8 MiB;
proposal body at most 1 MiB and browser reply at most 2 MiB. Existing transport/MCP
limits still apply and may refuse an oversized envelope rather than truncate it.

Mask routes and recipes with motion modes refuse this proposal path until their
complete mask/mode/transform intent is supported. It does not normalize arbitrary
native ComfyUI subgraphs, certify native resampling parity, reserve memory, approve
licenses or grade artwork. Checks still show missing/unknown prerequisites; they
are about the default graph, not runtime execution validation of the proposed text.

## Design choices and remaining #232 work

A stateless read-only report was chosen instead of a second draft database or a
client-only diff. The first would compete with Workspace ownership; the second
would not share graph/source/role decisions with headless agents. Shared pure
reference helpers avoid a separately maintained prompt/geometry compiler.

Next, add a persisted expected-draft revision and a proposal command receipt to the
existing shared command boundary. Then implement explicit staging and apply with
source/graph/backend revalidation at the actual mutation point, retaining all
old draft/local-file state for inverse operations. Partial staging, response loss,
reload and concurrent edits need fault-injected recovery before enabling Apply.
Undo must create a new editable revision, not delete media or replay generation.
Use this exact proposal shape only as reviewed input, never as implicit authority.

#232 remains open for these mutation/recovery/undo gates. #118 retains specialist
journey predicates and owner-reviewed creative acceptance; #123 retains real
owner-host/new-machine and broader artifact/progress acceptance; #21 retains live
reference-variant acceptance. Native interoperability and broader authored-graph
execution stay with #121/#122. No new issue duplicates these owners.

## Reconciliation and proving record

Started from #258 head `c4074ca05eec7898ee36938f5cc8e766647e032d`, tree
`cb58a2b89cacfb4bc238464ec84094e48cc2c1fe`, after live PR/issue reads. #237 was
merged; #258 was open and already retargeted to main. During development #258
merged. The exact newer main `ff6c0f494ba3f8f74e7fd4af10cdbfd0fec186d9`, tree
`6428f2f4d66481381e5b2476c44693a6106430a6`, was acquired and verified before
reapplying the feature patch without conflicts. It retains concurrent runtime,
Generate-upload, catalog-honesty, schema-capture and documentation changes.

The immutable original baseline ran 1775 tests with 18 skips and no failures.
The preintegration full run passed 1800 tests with 19 skips before two further
geometry/raw-graph regressions were added. The integrated full suite then passed **1843 tests: 1824 passed, 19 skipped**
in 150.448 seconds. Focused shortlist checks passed 96 tests with four optional
MCP-SDK skips; all eight proposal Node contracts passed. The integrated local
browser passed 72 assertions in the explicitly inert mode described below.
Hosted native-browser/WebCrypto and required official-MCP results belong to the
PR verification record; do not reinterpret these local checks as hosted acceptance.

Initial twelve feature tests produced five assertion failures and seven missing
operation errors. Later causal cases covered CLI null fallback, pixel warning
limits, source transformation extremes, raw/parsed graph mismatch, self-consistent
but incorrect response wording/diffs, and the absent actual preview control. The real browser
JavaScript engine in inert transport mode exposed a timer callback's wrong receiver; its fixed
wrapper now reliably clears/invalidate reports on input. A subsequent Escape
fixture race was fixed by awaiting the actual close event, not a product timeout.
These failures and their corrected runs remain in the handoff evidence.

```console
python -m unittest discover -s tests -p "test_recipe_shortlist*.py"
python -m unittest discover -s tests -p "test_reference*.py"
node tests/setup_proposal_client.cjs
python tests/recipe_shortlist_browser.py --out .runtime/setup-proposal-proof
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The existing Recipe shortlist CI lane requires the pinned official MCP SDK on
Linux/Windows, discovers the new tests and runs the native Chromium driver. Local
container navigation is blocked with `ERR_BLOCKED_BY_ADMINISTRATOR`; its explicit
`--inert` mode substitutes transport/storage and a test-only SHA adapter while using
actual production scripts and proposal computations. It is not native HTTP/storage
or WebCrypto evidence. Hosted default mode supplies that separate gate. Tests use
synthetic images/dependencies, not owner artwork or live inference. Existing
Pillow/socket warnings remain visible. Skips are not completed acceptance.

## Primary references and rollback

Reviewed 14 September 2026: Python's [JSON encoder/decoder documentation](https://docs.python.org/3.12/library/json.html)
defines the serialization options used by the existing canonical helper. The W3C
[Web Cryptography API](https://www.w3.org/TR/webcrypto/) specifies digest operations;
its current Level 2 document is a working draft, not a new final recommendation.
These sources explain the exact-byte design, not graph correctness or approval.
Existing [reference-workflow documentation](../game-assets/REFERENCE-WORKFLOWS.md)
retains the underlying Qwen model/slot research; this slice does not replace it with
new inferred compatibility claims.

Reverting this slice removes its capability, route, clients and dialog together,
and restores the inlined reference helpers. No data migration, installed package,
model, runtime restart, source attachment or owner configuration change is required.
Owner UX feedback and the Hunyuan3D policy choice remain open in `HUMAN_TODO.md`;
this work records no new creative or licensing decisions.

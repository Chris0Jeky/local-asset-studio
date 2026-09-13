# Find a starting recipe

This slice advances #118 and the read-only discovery part of #123. It does not
complete either issue. **Create → Recipe library → Help me choose a recipe** now
answers which registered default routes match an outcome and what needs attention.
The Guided workflows page links to the same chooser; it is not a second launcher.

## Use it

Choose an outcome and declare 0–3 images you plan to attach, then select **Check
starting recipes**. The first page contains at most six suggestions. **Find in
recipe library** clears only the picker filters and focuses the existing recipe
button. It does not select that recipe, replace the prompt, drop attachments,
upload files, switch environments, prepare a ticket or generate an output.

Read the first prerequisite on a card; expand **How it works and what it needs**
for the route's purpose, wording role, checks and exact model locations. The
usual recipe selection and preparation remain explicit. A page with no matching
route says so; it never substitutes an unrelated model family.

Supported outcomes: new image, image change, pose/identity references, upscale,
masked repair, image animation and image-to-3D. The scope is **registered preset
default graphs**, not every tuned named recipe, your current controls, arbitrary
custom graphs or guarantees about the quality of a model's output.

| Label | Meaning | Not established |
| --- | --- | --- |
| Listed prerequisites observed | The listed checks had no known hold or unknown result | Native validation, complete external dependencies, memory fit, model hashes, rights or art quality |
| Some checks are unknown | At least one applicable observation is unavailable or incomplete | Unknown is not ready, missing or failed inference |
| Needs attention before preparation | A known prerequisite or existing hold prevents this default route | It is not a permanent limitation of the model family |

A declared image count is **not a selected asset**. Matching the count still
requires staging, roles, source-byte checks and any mask preparation. Missing or
excess images are called out; no extra source is silently dropped. A mask route
cannot be made ready merely by claiming to have an image. Model locations reuse
current folder/loader contracts; a present file is not a verified weight.

## Headless use

Use the normal Studio service, including its existing no-browser launch option.
Nothing here installs a dependency or starts a second runtime.

```sh
python -m studio_workflow.shortlist --goal new-image
python -m studio_workflow.shortlist --goal edit-image --references 1
python -m studio_workflow.shortlist --goal animate-image --references 1 --limit 6
```

The command prints structured JSON and returns 0 on an observed report (which may
contain blocked/unknown choices), or 2 on invalid input/transport/inspection error.
It prints no executable ticket and has no output-file write option. A failed
observation can be explicitly requested again; it cannot duplicate a generation
because this operation never dispatches one. Errors retain a bounded server
explanation rather than reducing a changed page to an opaque HTTP status.

```python
from studio_workflow.sdk import WorkflowClient

studio = WorkflowClient("http://127.0.0.1:8191", timeout=30)
page = studio.shortlist("edit-image", reference_count=1, limit=6)
for option in page["candidates"]:
    print(option["name"], option["status"], option["checks"])
if page["next_offset"] is not None:
    following = studio.shortlist(
        "edit-image", reference_count=1, limit=6,
        offset=page["next_offset"], expected_snapshot=page["snapshot_sha256"],
    )
```

The existing stdio MCP bridge exposes **recipe_shortlist** in its default `read`
mode. Its schema enumerates the same goals and integer bounds. It uses the same
operation and exact-JSON response envelope as the existing agent tools; it has no
independent selection policy, filesystem state or access to Comfy's `/prompt`.
Reading `studio_capabilities` advertises `recipe_shortlist: true`.

HTTP: `POST /api/workflow-studio/shortlist`, JSON object with `goal`, optional
`reference_count` (0–3), `limit` (1–12), `offset` (0–256), and `expected_snapshot`.
Further pages require the original SHA-256. The POST is observational, but retains
the actual Studio's Host/Origin, content-type and body-size guards.

## Architecture and source ownership

```text
Browser / standalone CLI / SDK / read-mode MCP
                  |
       existing Workflow HTTP extension
                  |
       studio_workflow.shortlist.request
         |          |             |
  Studio.catalog  node_info    preset_requirements
    + real graph   (cached)    (shared file observations)
         |                        |
    continuation.capability   existing ModelLibrary
                  |
    existing Wan capacity + host-commit predicates
                  |
    bound observation report — never prepare or run
```

`shortlist.py` owns deterministic matching/ranking and a small client read-error
wrapper. `recipe-shortlist.js` owns the disposable observation session and DOM
presentation. `studio-shell.js` loads the optional chooser after the shell is
ready. Existing owners retain selection, references, preparation, native graph
validation, queue/budget ownership and output review. No new project store,
executor, model manager, prompt helper, scheduler or polling loop is introduced.

The matching rule uses the existing **graph-derived operation plus modality**;
recipe titles and family names cannot establish an image-edit or animation route.
Image counts are compared with the graph-derived number of consumed source
bindings. Unknown or contradictory capability metadata produces diagnostics.
Historical `verified`/execution badges never outrank current prerequisites or
become artistic acceptance. Order is deterministic: observed, unknown, needs
setup; then fewer known holds, name and stable preset ID. This is an availability
ordering, **not a learned quality recommendation or performance benchmark**.

One explicit request reads the current catalog (maximum 256 presets, 8 MiB), the
active cached node schema once, and the existing model manifest. It shares cheap
file observations across candidates. It does not force a schema refresh, hash
model binaries or evaluate node Python/JavaScript. Node classes are presence
checks only. Missing or malformed schema is unknown, not an invented list of
missing nodes. Another backend never borrows the active backend's node evidence.

Static Wan default-graph holds and current host-commit holds call the existing
predicates rather than copying thresholds. Changing controls may change admission;
the shortlist deliberately does not validate an edited draft or certify tiled
decode. General model resources and native `VALIDATE_INPUTS` remain preparation
concerns. The source schema cache may be up to the existing cache interval old.

Each report includes a content identity over goal/count, backend/endpoint/switch
operation, catalog and raw-schema hashes, complete ranked observations and
unavailable-route diagnostics. Layout, UI selection and the check's timestamp do
not affect identity. The operation refuses a backend switch, A→B→A switch receipt,
catalog or schema replacement detected during inspection. Every later page
re-observes and requires the original identity; changed evidence asks the caller
to start a fresh first page rather than silently mixing observations. It does not
hold a long generation lock while inspecting files or contacting Comfy.

This is an observational snapshot, **not an atomic lease over the operating
system**. A file or backend can change after inspection. Preparation must recheck
current state; a hash authenticates neither a person nor a model installation.
Response pages contain at most 12 candidates and each candidate at most 128 model
requirements. Bounds do not prove constant total cost across many browser tabs;
resource-observation work remains #175. No new cross-client cache is added.

### Browser lifecycle

There is no request on load, opening, changing the goal/count, navigation or
following the entry link. Checks and pagination are explicit. A single client
session rejects duplicate in-flight checks, passes an AbortSignal to the real
fetch and has a 15-second deadline. Query edits, actual Create input changes,
leaving Create, a requested environment switch and page exit invalidate the
observation epoch. When available, #197's recipe-change events are consumed.
A→B→A cannot revive an old reply. Failure or context mismatch removes old cards.

Aborting the browser stops accepting that response; it does **not** claim to stop
server inspection. An explicitly started replacement may overlap an old
server-side read that has not exited yet. Nothing automatically retries. The
Find action also checks the current library's template identity and known active
backend before revealing a button. It never calls `selectPreset` or `applyRecipe`.

All source-controlled and external labels are rendered with textContent. No
source URL is made into executable markup. Nested details leave initial cards
focused on the route, main prerequisite and handoff; precise checks remain
inspectable. Keyboard focus, 390px width and 200% zoom are tested separately from
screen-reader or owner-workstation certification.

## Reconciliation and delivery sequence

Initial main: `e9a062036f2f38ece4e6cf90ccb2ca40939695d4`, tree
`105e996187c98a261957268ecb1f6c377c183912`. Its complete tracked archive was verified
against the Git tree before editing; ignored machine data was not imported.

#197 is still open at initial reconciliation and owns the guide-state fixes and
updated general roadmap. This slice is based independently on main and does not
claim or duplicate #185/#190. Concurrent #198 owns recovery/headers, #202 setup
lineage, #203 model-guidance coverage, #208 Wan readiness, #209 Anima receipts and
#210 legacy CLI output recovery. Their closure claims and shared owners remain
unchanged. The new CLI module avoids modifying #210's legacy output path.

Before publication, main advanced to `a5f2e3f2fd0188c9538d1d5be7f6889804afacae`
(tree `20f2747a98b466c225e6a622473c0b04ffb54c93`). The complete tracked delta
was applied and its tree identity verified before reapplying this slice without
conflicts. #197 had merged by then; its recipe notifications and guide remain
intact. Focused contracts and the full-shell inert browser scenarios passed again
against this integrated source. The PR is not stacked on an unmerged guide PR.

Next work stays with the existing issues: #118 source-bound recommendations from
actual selected assets and specialist journey predicates; #119 installed-schema
adapter evidence; #120 typed reusable modules and role-bearing asset handles;
#121 native visual/subgraph interoperability; #122 wider authored graph execution;
#123 live interleaved human/agent and new-machine acceptance. Selection with a
reviewable, reversible setup diff should reuse #144's existing bundle handoff,
not bypass it. These tests do not establish an owner-run accepted creative output.

## Repeatable QA

```sh
python -m unittest discover -s tests -p 'test_recipe_shortlist*.py' -v
node --test tests/recipe_shortlist_client.cjs
python tests/recipe_shortlist_browser.py --out .runtime/shortlist-browser
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The focused cases cover exact route/count matching, malformed/unknown evidence,
model missing versus unknown, backend/ABA and schema/catalog races, graph drift,
existing worker/memory/Wan/mask holds, bounded pages, stale pagination, shared
HTTP/SDK/CLI/agent identity, useful read errors and no forbidden execution calls.
The protocol test uses the repository-pinned optional MCP SDK; hosted Linux and
Windows jobs require that SDK so the protocol gate cannot pass by skipping it.

The browser driver uses the complete actual shell and policy with synthetic
model/node presence. Native HTTP/storage is its default. This container's normal
navigation returned `ERR_BLOCKED_BY_ADMINISTRATOR`; local `--inert` results use
injected transport/storage and are explicitly not native-origin evidence. Hosted
CI supplies the native gate. Logs, source-hashed result JSON and desktop/mobile
screenshots are retained. The synthetic long label is tested in cards/picker;
this is not a certification of arbitrary-length titles in every pre-existing
Studio heading.

Known fixture distinctions: protocol versus live MCP-host installation; fixture
files versus user assets; node presence versus native validation; default-graph
capacity checks versus memory measurements; navigation versus artistic success.
No GPU run, source upload, package/driver/page-file change in the managed runtime,
service restart, HUMAN_TODO edit, licence approval or private asset acceptance is
performed by this slice.

## Review follow-up: effective defaults and document events

The first hosted candidate (`a306afa`) passed all nine workflows, including 25
native-browser assertions and the real official-SDK MCP protocol test. Independent
review then exposed two gaps outside that initial coverage:

- Disabled optional LoRA loaders were counted as missing prerequisites even though
  preparation removes them. Shortlisting now deep-copies the raw default graph and
  calls the existing `Studio.prune_disabled_loras` before class, dependency and
  capacity observations. Raw template identity is retained; shared graph objects
  and template files remain unchanged. Active model/CLIP strengths still require
  the loader and its files; explicit catalog `model_files` remain requirements.
- `studio:recipe` is dispatched on `document` without bubbling. The chooser now
  subscribes there, like the guide, rather than on `window`. Selection, same-preset
  setup and import clear old cards and invalidate in-flight replies without a new
  request. A real A → B → A selection cannot revive the earlier result.

The added actual-catalog cases reproduced four assertion failures on the original
candidate (WAI, Animagine, Anima and the explicit-declaration comparison). The
expanded full-shell browser reproduced the missing notification using actual
`selectPreset`, not a synthetic substitute event. After correction, all 32 focused
cases run locally with one optional MCP-SDK skip, and 29 inert browser assertions
pass. Native coverage adds three entry/deep-link checks; final hosted evidence is
recorded in PR #217. These distinctions remain separate from workstation/model
execution and artistic acceptance.

## Primary technical references

Reviewed for this implementation, 13 September 2026:

- [Comfy server routes](https://docs.comfy.org/development/comfyui-server/comms_routes):
  object_info is discovery, whereas prompt validates and enqueues. The chooser
  never uses submission as a readiness probe.
- [Backend server overview](https://docs.comfy.org/custom-nodes/backend/server_overview):
  native validation can involve node-specific checks; the chooser's class presence
  is not substituted for those checks.
- Existing installed-version constraints, known capacity evidence and source pins
  remain in this repository. Current documentation does not certify the user's
  installed custom-node or frontend version.

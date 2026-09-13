# Find recipes for a selected image

Continuation of #118/#123 after merged #217. This adds an actual primary Workspace
image and a proposed use to the existing chooser. It does not apply a recipe,
attach a source, set a reference role, or approve execution.

## In the Studio

Open an image in **Asset library**, then choose **Find recipes for this image**.
Unsaved asset notes/tags keep you in the details dialog; save or discard those
edits deliberately before leaving. The action opens the existing Create recipe
chooser, selects the image for advice, and makes **no inspection or upload call**.
Your current prompt, recipe, sources and lineage remain unchanged.

Choose the outcome, total reference count and **Use the selected image for**.
Press **Check starting recipes**. Source status identifies the image, its recorded
size and role, and explicitly says **Not attached**. Expand a candidate's details
for the exact primary binding and its limitations.

| Intended use | What the report can establish | Still not established |
| --- | --- | --- |
| Whole image / first frame | A bound `LoadImage.image` reaches every supported saved output | Pixel preservation, identity fidelity or a staged reference |
| Identity, pose, style, costume, composition | The route exposes an explicit primary role slot and wording control; role assignment is proposed | Geometric control, a role already applied, or a guarantee of visual preservation |
| Named role on a whole-image-only route | Needs attention; no role slot is guessed | The role must not be silently ignored |

**Find in recipe library** continues to reveal/focus a recipe, not apply it.
Select the recipe normally, attach the intended image through the existing source
picker, assign its role where supported, and review the wording/settings before
preparation. The advice role is not transferred into that separate operation.
**Clear advice source** forgets only the chooser's source; Create attachments do
not change. Source advice is transient tab state, not a saved setup or project.

Only the **primary image** is checked. A declared count of two or three does not
verify additional assets, their order or role assignments. A mask-required route
still needs its own prepared/validated mask. Static default-graph inspection is
not inspection of a tuned current draft or arbitrary native subgraph.

## Headless contract

Existing HTTP, SDK, CLI and read-mode MCP keep one observation service. Capability
`recipe_shortlist_source: true` advertises this additive support. The source trio
is optional but must be supplied together; an incomplete trio fails before reads.
Use the ID and SHA-256 from the existing Workspace asset record, not a local path.

```json
{
  "goal": "edit-image",
  "reference_count": 1,
  "source_asset_id": "asset-id-from-workspace",
  "source_sha256": "<64 lowercase hex characters from the asset record>",
  "source_role": "pose",
  "limit": 6,
  "offset": 0
}
```

Send that object to `POST /api/workflow-studio/shortlist` or the read-mode
`recipe_shortlist` MCP tool. The example hash is a placeholder: replace it with
the real recorded value. Count-only requests retain their existing behavior.

```sh
python -m studio_workflow.shortlist --goal edit-image --references 1 \
  --source-asset-id "$ASSET_ID" --source-sha256 "$SOURCE_SHA256" --source-role pose
```

```python
from studio_workflow.sdk import WorkflowClient

client = WorkflowClient("http://127.0.0.1:8191", timeout=30)
# asset is an existing record returned by the Workspace service.
page = client.shortlist(
    "edit-image", reference_count=1,
    source_asset_id=asset["id"], source_sha256=asset["sha256"], source_role="pose",
)
```

Roles are `source`, `identity`, `pose`, `style`, `costume`, `composition`.
No custom path/URL, source upload, role mutation or execution flag is accepted.
`source` in the report carries ID/hash, requested role, bounded title, dimensions,
`bytes_verified: true`, and `staged: false`. A candidate may carry
`source_assignment` with the exact primary binding, slot 1 and role mode
`whole-image`, `prompt-guidance`, or `unsupported`. A failed graph observation
may have no assignment; callers must not invent one. SDK and browser refuse a
response with a different source, role, slot or claimed execution authority.

The existing result/exit contract is unchanged: CLI exit 0 means a report was
received, including any blocked/unknown routes; exit 2 means invalid input or an
observation error. Neither is a generation result. Later pages require the same
source trio and `expected_snapshot`. Changed evidence requires a new first page.

## Architecture and limits

`shortlist_source.py` is the narrow source adapter. It calls the existing
`continuation.source_context` boundary through Workspace: nontrashed image,
resolvable asset path, maximum 20 MiB, source hash matching the Workspace record,
and image header dimensions. It additionally compares the caller's expected hash.
Pillow's decompression-bomb error becomes an actionable validation error, without
relaxing the image library's safety setting. Headers/dimensions do not prove every
pixel/frame decodes, mask geometry, licensing, or creative acceptance.

The adapter strips private filesystem paths, retained generation prompts and
unrelated metadata from its response. The source is observed again after catalog,
schema, dependency and capacity checks. A changed/missing/trashed source fails the
whole request rather than degrading to count-only advice. Source identity, role
and observed dimensions join the existing snapshot hash and pagination contract.
This is not an atomic filesystem lease: source bytes can change after the read;
actual preparation/staging/execution retain their own checks.

Candidate wiring reuses `continuation.reference_bindings` and
`consumes_reference` on a deep copy after `Studio.prune_disabled_loras`. It keeps
existing graph/model/resource ownership. Unknown topology and named roles without
explicit slots remain blocked; no field-name or model-family heuristic certifies
a source assignment. The role vocabulary is checked against `app/references.py`.

The existing workbench details hook adds the image action. It sends only advice
identity through `studio:shortlist-source` on `document`. The chooser owns an
in-memory source and role selection. Its existing epoch/deadline/AbortSignal
machinery discards replies after source/role/recipe changes and clear-source.
No new persistence, polling, queue, executor, schema refresh or LLM is introduced.
An aborted browser observation need not stop a server-side file read.

Alternative approaches rejected for this slice: inserting a source count alone
would still ignore changed assets and roles; reusing the immediate staging
handler would mutate attachments before review; embedding a second source store
would split identity and trash authority from Workspace.

## Reconciliation and next increments

Inspected main `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3` (tree
`5e920817385cf6c6d4aef2154267eb6c0d0c4511`) already contains merged #197 and #217.
No PR was open at the first reconciliation. Source-aware matching was still
explicitly outstanding in #118/#123; existing #21/#38 reference compilation and
handoff ownership is preserved. This is partial delivery, not closure of those
broader issues. Owner creative decisions in `HUMAN_TODO.md` are unchanged.

Next, #232 extends #118/#21 with an ordered multi-asset proposal and a **reviewed,
reversible handoff**, not an automatic consequence of checking. Its acceptance:
show complete source hashes, roles, transforms, prompt/settings and lineage diff;
recheck current source/graph and expected draft revision at apply; reject missing,
changed or extra sources rather than truncating; preserve unsaved editor work;
provide undo without deleting staged user media; expose the same proposal to
agents. Proposal/approval and generation remain separate. Native visual/subgraph
interoperability is #121; wider authored execution remains #122.

## Verification and reproduction

The new tests use temporary Workspace databases and real small image files with
synthetic dependencies. Cases cover exact bytes and primary bindings, actual
Qwen binding, role semantics, additional-reference/mask holds, malformed queries
and replies, size/type/trash/missing-source failures, mutations during inspection,
SDK/HTTP/read-agent parity and CLI syntax. Official MCP protocol acceptance is
optional locally and required by the existing Linux/Windows shortlist CI lane.

```sh
python -m unittest discover -s tests -p 'test_recipe_shortlist*.py' -v
node --test tests/recipe_shortlist_client.cjs
python tests/recipe_shortlist_browser.py --out .runtime/source-advice-native
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The full-shell browser fixture additionally checks the real Asset detail entry,
unsaved metadata guard, no automatic request, unchanged Create state, role
invalidation, changed bytes, clearing a delayed response, mobile layout and
forbidden writes. It preserves prior shortlist/history/late-response scenarios.
`--inert` is an explicitly disclosed component transport mode; it is not native
HTTP/origin evidence. Local native navigation is policy-blocked in this container;
separate hosted Chromium evidence belongs to the actual PR run. Screenshots and
source-hashed receipts are emitted by the checked-in driver.

Baseline: 1,674 tests, 16 skipped, no failures. Source feature tests failed on
baseline before implementation; additional client assignment and image-safety
regressions also failed before hardening. Final totals and hosted acceptance are
recorded on the PR and in the accompanying evidence bundle; skips are not passes.
Rollback is the source-advice commit: no storage migration or owner data exists
to reverse, and ordinary recipe selection remains usable.

## Primary research consulted, 13 September 2026

- [ComfyUI Qwen nodes](https://raw.githubusercontent.com/Comfy-Org/ComfyUI/master/comfy_extras/nodes_qwen.py):
  `TextEncodeQwenImageEditPlus` supplies ordered image1/2/3 and Picture references
  to prompt/image conditioning. This supports the distinction between semantic
  wording and geometric pose control; it does not certify installed versions or
  quality. Mutable upstream source was consulted, not executed or vendored.
- [Pillow Image reference](https://pillow.readthedocs.io/en/stable/reference/Image.html):
  pixel-limit warnings/errors are distinct from compressed file size; the adapter
  preserves the safety check and translates its error for this read operation.
- Local `app/continuation.py`, `app/references.py`, `app/workspace.py` and existing
  shortlist/agent tests are authoritative for this integration's actual behavior.

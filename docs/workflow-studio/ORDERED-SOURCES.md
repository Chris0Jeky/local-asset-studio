# Check recipes against an ordered set of images

This is the observation part of #232, extending #237's single-source chooser.
It checks one to three actual Workspace images and explains the proposed slot for
**each** image. It does not stage sources, generate wording, apply a setup, or
provide undo for an applied setup. Those mutation boundaries remain in #232.

## In the Studio

In **Asset library**, check one, two or three images, then choose **Find recipes
for selected images** beside the existing bulk actions. The chooser also offers
**Choose images in library** to reach those controls without replacing Create.
The single-image details action remains available.

All checked images are included, even when a library filter hides some of them.
The initial Picture order is selection order, not the current grid sort. The
chooser displays every selected title before inspection. More than three images,
a non-image, a trashed image, or an unavailable selected ID causes a visible
refusal: no selection is silently shortened and no file is read by that action.
Unsaved asset metadata retains the existing leave guard.

Set each **Intended role**, then use the arrows to move an image earlier or later.
Its role follows the image. Keyboard focus follows the moved row. **Remove** only
removes an advice row; it does not change library checkboxes, Create attachments,
source lineage, or user files. Removing the last row returns to count-only advice.
**Clear advice source** clears the complete advice set, not Create.

Press **Check starting recipes** explicitly. The reference count is derived from
the selected rows and cannot be edited separately. Every source is checked before
and after prerequisite discovery. A changed or unavailable second/third image
refuses the complete report and names its Picture number. Reordering, changing a
role, removing a source or changing recipes discards prior and delayed results;
there is no automatic retry or recheck.

Each candidate retains one assignment record per requested image, including
unsupported assignments. Missing, duplicate or disconnected graph bindings are
reported without compacting the remaining slots. Whole-image wiring differs from
a named semantic role: a role-aware route can propose prompt guidance, not
geometric pose control or a promise to preserve identity. Mask-required routes
remain held for their existing explicit mask preparation.

**Find in recipe library** still reveals and focuses a recipe. It does not select
it or transfer these source roles into Create. Applying multiple images requires
the separate reviewed handoff described below.

## Shared HTTP, SDK, CLI and MCP contract

Capability `recipe_shortlist_ordered_sources: true` advertises this addition.
Existing count-only and legacy primary-source requests keep their prior shapes.
An ordered request to `POST /api/workflow-studio/shortlist` is:

```json
{
  "goal": "reference-image",
  "sources": [
    {"asset_id": "identity-asset-id", "sha256": "<recorded SHA-256>", "role": "identity"},
    {"asset_id": "pose-asset-id", "sha256": "<recorded SHA-256>", "role": "pose"},
    {"asset_id": "style-asset-id", "sha256": "<recorded SHA-256>", "role": "style"}
  ],
  "limit": 6,
  "offset": 0
}
```

Replace the example IDs/hashes with real Workspace records. `sources` contains
one to three objects, each with **only** `asset_id`, `sha256`, and `role`.
`reference_count` is inferred when absent; when present it must equal the array
length. Empty/null/malformed collections, extra fields, unknown roles and mixed
legacy `source_*` fields fail before observation. The same asset may explicitly
occupy two positions with different roles; the service does not deduplicate it.
No paths, URLs, transforms, upload instruction or execution flag are accepted.

```python
from studio_workflow.sdk import WorkflowClient

# records are existing Workspace asset records, in your desired Picture order.
roles = ("identity", "pose", "style")
if not 1 <= len(records) <= len(roles):
    raise ValueError("Choose one to three Workspace images")
sources = [
    {"asset_id": asset["id"], "sha256": asset["sha256"], "role": roles[index]}
    for index, asset in enumerate(records)
]
client = WorkflowClient("http://127.0.0.1:8191", timeout=30)
page = client.shortlist("reference-image", sources=sources)
if page["next_offset"] is not None:
    next_page = client.shortlist(
        "reference-image", sources=sources, offset=page["next_offset"],
        expected_snapshot=page["snapshot_sha256"],
    )
```

The ordinary configured Studio must already be running. Save just the `sources`
array to a UTF-8 JSON file, then use:

```sh
python -m studio_workflow.shortlist --goal reference-image --sources-json sources.json
```

The CLI reads at most 8 KiB plus one rejection byte and uses the shared strict JSON
parser. Duplicate keys, invalid JSON, `null`, non-arrays and oversized input cause
exit 2 without HTTP. There is no output-file or asset mutation in this command.
Exit 0 means a report was received, including blocked/unknown routes; it is not a
generation result. `--references` is optional with ordered sources and must agree
with their length when provided. This does not modify legacy CLI write recovery.

The existing read-mode MCP tool `recipe_shortlist` accepts the same object. Its
JSON Schema exposes the bounded array and exact item properties; runtime checks
also enforce mutual exclusion and count agreement. No second tool or permission
mode is introduced. The pinned official MCP SDK is unchanged.

Ordered replies contain `source: null`, plus `sources` in requested order with
one-based `slot`, ID/hash, role, bounded title, dimensions, `bytes_verified: true`
and `staged: false`. Every candidate contains a matching `source_assignments`
array. An unsupported slot retains its identity and `role_mode: unsupported`;
a graph-read failure never silently removes that source. The old singular
`source_assignment` does not stand in for a collection. Clients reject missing,
reordered, mislabelled, incorrectly slotted or purportedly staged evidence.
Source order and roles participate in the snapshot hash; later pages must use
the same ordered request and snapshot.

## Architecture and ownership

`shortlist_source.py` extends the existing `continuation.source_context` adapter;
Workspace remains the owner of source identities, paths and trash state. Each
entry retains the existing 20 MiB source-size and hash/header checks. Bounds are
per source, with at most three sources; this is not a new image decoder or an
aggregate memory reservation. Image-safety limits are unchanged. Hash/header
observation does not prove all pixels or frames decode, mask validity, licensing,
art acceptance or a filesystem lease. The future staging/apply operation must
recheck its own effective bytes and concurrent-edit state.

The source adapter observes the entire set before catalog/schema/dependency work
and again afterwards. Only one complete result is returned. It retains no source
bytes or new server state. Existing queue, resource checks, disabled-LoRA pruning,
backend epochs and snapshot-bound pagination remain authoritative.

Ordered graph inspection preserves raw `reference_slots` positions, including
invalid placeholders. For the existing non-role first/last-frame structure it
uses `reference` and `last_reference` in that order. It never deduplicates slots,
guesses field names or shifts Picture 3 into a broken Picture 2 slot. Existing
`consumes_reference` reachability checks determine supported output wiring. Real
registered two/three-reference Qwen graphs are tested, separately from synthetic
fault fixtures; no model execution is implied.

The workbench sends an in-memory `studio:shortlist-sources` document event with
only advice identities/titles. The chooser owns transient rows and reuses its
existing request epoch, AbortSignal, deadline and single-flight policy. The
request snapshots nested source records before awaiting a reply. Browser abort
is not a claim that server-side reads were cancelled. Advice rows are not a
persisted draft or authoritative shared workflow revision.

Alternatives rejected: representing all sources with the first source plus a
count would leave the other bytes/roles unchecked; compacting valid bindings
would relabel images; reusing immediate attachment would mutate Create before a
complete diff and consent. A new source store or queue would duplicate existing
Workspace and execution ownership.

## Reconciliation and remaining #232 scope

The initial GitHub check found #237 still open at `992b2240a9397f7542188781a95b1c8428e77c6c`,
with tested tree `a64151ad0c8829ee4aa31684eeb41d265fe685b4`. This continuation was
built on that exact tree. Main was `3d3135a17811d2e4846ada05aae35e06f60d92f4`;
#197/#217 were already merged. Concurrent #233 library-selection UX, #234 bounded
reference capture, #235 Workspace publication, #236 HTTP framing, #238 schema
capture and #239 recovery keep their own ownership. This patch does not rewrite
those services. Final integration and PR base are recorded on the PR.

This delivers ordered read-only source/slot observation within #232, not the full
reviewed handoff. Still required: a complete wording/settings/transforms/lineage
diff, current draft revision, explicit source staging and apply, revalidation at
the mutation boundary, partial-staging/response-loss recovery, persisted undo and
reload behavior, and shared agent mutation semantics. Existing #120 commands and
Workspace revisions should own those changes; never treat this observation hash
as authorization or as an expected draft revision.

#118 retains specialist journey and owner-reviewed creative acceptance. #21
retains live reference-variant acceptance; #123 retains broader host/artifact/
progress acceptance. #121/#122 own native interoperability and wider execution.
No owner configuration, models, runtime, generated outputs or HUMAN_TODO decisions
are changed by this slice.

## Verification and reproduction

```sh
python -m unittest discover -s tests -p 'test_recipe_shortlist*.py' -v
node --test tests/recipe_shortlist_client.cjs
python tests/recipe_shortlist_browser.py --out .runtime/ordered-sources-native
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The initial 12 feature tests failed on the parent code (3 failures, 9 errors).
Expanded coverage includes real Workspace files, source changes during discovery,
explicit reused assets, malformed/duplicate/disconnected slots, mask/excess-source
holds, real Qwen bindings, caller snapshot immutability, production HTTP guards,
CLI strict input, and shared SDK/agent/protocol replies. The explicit JSON `null`
CLI case exposed a false count-only fallback and failed before its correction.
The initial client additions also failed before response/snapshot support existed.

Full-shell browser scenarios retain earlier single-source and count-only cases
and add the real bulk entry, filter-hidden selection, all three role controls,
keyboard reorder/focus, removal, count derivation, second-source drift and delayed
A-to-B-to-A results. They assert unchanged Create state and no generation/install/
switch/asset mutations. An initial browser test had a reused fixture variable;
that test-only bug was corrected before recording the missing-entry regression.

Local `--inert` mode is component evidence only. Native navigation is blocked by
this container policy; the existing hosted shortlist lane supplies separate real
HTTP/storage/Chromium evidence and requires the official MCP SDK on Linux and
Windows. It emits result JSON, source hashes and screenshots. Test counts, skips,
final source identity and hosted results are recorded per revision on the PR and
in the downloadable handoff; they are not inferred from another branch's tests.
Rollback removes this additive ordered mode; there is no storage migration or
applied user state to revert, and legacy advice remains available.

## Primary sources consulted

- [ComfyUI Qwen node implementation](https://raw.githubusercontent.com/Comfy-Org/ComfyUI/master/comfy_extras/nodes_qwen.py):
  ordered image inputs and Picture enumeration motivate retaining the actual
  slot order. The local catalog/graph, not upstream head, determines support.
- [MCP tools specification, 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools):
  discoverable input schemas and tool calls. The implementation keeps the
  repository's pinned SDK and tests the actual protocol; no version upgrade.

These references explain the interface design, not installed-runtime or neural
quality evidence. The three-source limit is this Studio contract, not a universal
limit on image models or future workflow authoring.

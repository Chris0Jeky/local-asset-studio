# Resource-scoped settings explanations

13 September 2026 · first contextual-claims slice of #144.
Inspected baseline: `aebe10c58c7fa3ce8f89276740096eaf98c2cc20`.

## In the Studio

In **Create → Explore creative bundles**, choose a non-reference image bundle.
**Why these settings?** explains the current draft, not just its model-family
label. It shows applicable records, missing prerequisites, unknown identities,
values outside a source's recommendation and conflicting recommendations.

A typical question is why a four-step accelerator is selected with fifteen
sampling steps. The panel names the upstream four-step schedule while the
accelerator is active. Disable it, and that recommendation becomes **Not
applicable**. A historical fifteen-step result is an observation rather than a
reason to override accelerator advice. The panel changes no values and blocks
no deliberate artistic experiment; Create's existing validation still governs
preparation and execution.

Open a record for its source kind, locator, retrieval date, source revision,
conditions and actual bound input values. **Find control** focuses an existing
draft field. **Download explanation** saves the report, including its context
fingerprint, for a local agent or an experiment record. A download is not an
executable recipe, permanent source snapshot or an approval receipt.

Read the states literally:

| State | Meaning |
| --- | --- |
| Applies to catalog pins | All declared resource hashes and prerequisites match the authored draft and current pin registry. Installed bytes were not hashed. |
| Not applicable | A required resource/version or declared prerequisite differs. The record is retained for explanation. |
| Scope unknown | A pin, activation rule, control binding or supported node convention cannot be established. |
| Outside recommendation | An applicable record recommends another value/range. This is advisory, not a quality score. |
| Sources disagree | Applicable recommended bands have no common value. No source is silently selected and no compromise is averaged. |
| Review due | The authored review date has passed. This does not establish that the source has changed, disappeared or become wrong. |

Historical observations retain their tested values but never become prescriptions.
General legacy family notes remain available in a separate folded section,
labelled as **not checked against this stack**. Unsupported reference/video/3D
routes do not receive image-only guidance. Missing coverage is explicit rather
than filled with guessed values.

## Architecture

There is one evaluator, `studio_workflow/guidance.py`, used by the existing HTTP
extension and a dependency-free offline CLI. The browser module renders its
report; it does not implement another recommendation engine. No new database,
model manager, queue, schema poller or inference adapter is added.

`presets/settings-kb.json` gains an optional `guidance` section. Its older
families/LoRAs remain intact. Claims reference exact `models/library.json`
relative filenames and SHA-256 pins. They do not upgrade the registry's stored
identity into verification of the currently installed files or runtime support.

The read-only operation uses POST because a draft graph/control snapshot can be
larger than a URL:

```text
POST /api/workflow-studio/guidance
{ preset_id, controls, expected_graph, expected_bindings }
```

The **production** `create_server()` Handler stack retains Host/same-origin,
strict JSON and 1 MiB request checks. The operation reads only the registered
preset/graph, settings KB and pin registry. It never calls `prepare`,
`node_info`, ComfyUI, Workspace storage, a model provider or a source website.
No ticket is created. Unsupported controls and altered graph/binding snapshots
are rejected rather than interpreted as a new workflow.

Effective controls are projected through the existing primary and companion
bindings, preserving unrelated graph inputs/connections. Target rules specify
exact node classes; a generic `cfg` label is not sufficient to transfer advice
between different conditioning conventions. Resource-strength targets resolve
the actual selected file's node and field instead of assuming that slot two
always has the same purpose.

Core `LoraLoader` and `LoraLoaderModelOnly` activation uses every present
model/text-encoder strength. A live CLIP strength is not mistaken for an off
adapter. Opaque loader activation stays unknown. The `none_active` condition
examines recognized `lora_name` graph resources; it is not a universal claim to
understand every custom patch, IPAdapter or native module.

The response is `studio.settings-guidance/v1`, with `authoring_only: true`,
`generation_submitted: false`, the evaluation date and a SHA-256 context over
preset, effective graph, KB and pin registry. This fingerprint identifies the
checked inputs; it is not authorization, external-file locking, persistent
revision control or proof of deterministic output. Changes on disk after the
response require another check; there is no background file watcher.

## Claim contract

Each bounded claim contains an ID/title, `runtime: comfyui`, exact resource pins,
prerequisites, setting targets, independent recommended/tested bands, source
metadata, rationale and an optional review date. One schematic example:

```json
{
  "id": "example-four-step",
  "title": "Synthetic example, not model advice",
  "runtime": "comfyui",
  "resources": [{"file": "loras/example.safetensors", "sha256": "<64 lowercase hex characters>"}],
  "when": [{"resource": "loras/example.safetensors", "state": "active"}],
  "settings": [{
    "target": {"control": "steps", "node_types": ["KSampler"]},
    "recommended": {"values": [4]},
    "tested": null
  }],
  "source": {
    "kind": "authored_hypothesis",
    "locator": "An explicit design reference",
    "url": null, "revision": null, "retrieved_at": null
  },
  "rationale": "An illustrative schema entry; replace the placeholder hash before validation.",
  "review_after": null
}
```

Bands are finite numeric ranges or bounded homogeneous choice sets. Targets are
catalog controls plus allowed node classes, or an exactly pinned resource's
`strength_model`/`strength_clip` input. Preconditions can require a pinned resource
to be active/inactive, all recognized LoRA resources inactive, or another
control's value. Duplicate claim identities are all excluded, not first-wins.
Invalid entries produce diagnostics while unrelated valid claims remain usable.

Source kinds are `creator_documentation`, `local_observation`,
`controlled_experiment` and `authored_hypothesis`. A local observation may contain
only tested values. Conflicts use the **joint intersection** of all applicable
recommendations for a physical node/input, not merely pairwise comparisons. A
historical tested value participates in no recommended-band intersection.
Source text is data rendered with text nodes, not HTML or agent instructions.
Source links must be credential-free HTTPS and open only after a user click.

## Initial real records and research

Four records seed the mechanism; this is not complete model-library coverage.
All resource pins refer to existing repository inventory, not new installations.

1. **Krea four-step ComfyUI schedule.** The [adapter author's model card](https://huggingface.co/lvladikov/Krea2-Turbo-Distill-4step-LoRA#comfyui),
   checked on 13 September 2026, documents ComfyUI steps 4, CFG 1, Euler/simple.
   The [exact adapter file page](https://huggingface.co/lvladikov/Krea2-Turbo-Distill-4step-LoRA/blob/main/krea2_turbo_4step_rank_64_lora_comfyui.safetensors)
   reports SHA-256 `7590b2d2772f45d7b1252124c63918b1b807e93fbf9eab20546fa7233b4dc482`,
   matching the catalog pin. The same card's Diffusers guidance value is 0;
   it must not replace ComfyUI CFG 1. A card retrieval date is retained, but
   its immutable repository revision was not retrieved: `revision` stays null.
2. **Krea unadapted comparison.** The same card gives eight steps for stock
   Turbo. This entry is deliberately limited to inactive LoRA slots; it is
   not a general override for style-specific recipes or other native modules.
3. **Anima turbo v0.2 authored schedule.** The existing KB supplies the
   eight-step/CFG 1/Euler/simple starting point. The [official adapter mirror](https://huggingface.co/circlestone-labs/Anima-Official-LoRAs)
   and [Comfy tutorial](https://docs.comfy.org/tutorials/image/anima/anima) were
   inspected, but their available model-card text did not establish that
   specific numeric schedule. It is labelled **Authored starting point**, not
   freshly verified creator advice; no invented source retrieval/revision pin.
4. **Historical Krea target-stack trial.** The existing curated recipe at
   `experiments/curated/anime-fantasy-atelier/krea-target-stack-koukouya-recipe.json`
   retains prompt ID `a63ca7e1-c87a-4288-bcd9-959ff93d1827` and its actual
   fifteen-step settings. The source record pins the local recipe bytes.
   This is related historical evidence, not an exact draft-reproduction claim;
   changed prompts, dimensions, strengths and additional modules remain different
   experiments. It contributes tested values only.

The [official ComfyUI LoRA tutorial](https://docs.comfy.org/tutorials/basic/lora)
provides the model/CLIP-strength distinction used by the activation rules.
No Civitai or Hugging Face descriptions are fetched automatically in Studio.
Reviewed intake snapshots and richer source-version coverage remain #9/#144.

## Browser behavior and testing

The panel clears stale advice immediately when a bound draft value changes,
debounces local explanation requests by 200 ms, and aborts superseded requests.
A ten-second timeout produces a visible unavailable state. Requests are never
automatically retried. An epoch plus the captured draft identity prevents a late
reply from overwriting a newer edit, reset, undo or closed panel. Module or
metadata failures leave the editable draft untouched. The normal preset/recipe
and Workspace save paths are unchanged.

Reproduction:

```bash
python -m unittest discover -s tests -p test_bundle_guidance.py -v
node --test tests/bundle_guidance_client.cjs
python -m studio_workflow.guidance --preset krea-anime-atelier --controls '{"steps":4}'
python tests/bundle_guidance_browser.py --out .runtime/bundle-guidance-browser
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The targeted suite includes real production-Handler HTTP tests, all registered
non-reference image graphs against the offline evaluator, exact/missing/ambiguous
pins, moved adapter slots, live CLIP strengths, incompatible node conventions,
conditional advice, stale dates, malformed claims, joint conflicts and historical
observations. The browser driver loads the **actual Explorer and new modules**,
using a synthetic recipe and a read-only fixture behind the **production Handler
stack**. It checks dynamic conditions, late replies, conflicts, raw markup as
text, unavailable registry, input focus, responsive layout and zero workbench or
inference mutations. It is not the complete Studio app or a GPU runtime test.

This environment blocks normal browser localhost navigation with
`ERR_BLOCKED_BY_ADMINISTRATOR`. The locally executed `--inert` mode substitutes
inline assets/data-module URLs and a Python HTTP bridge, while keeping actual
HTTP Handler and evaluator calls. It does not establish browser-native transport.
The existing **Bundle workflow browser** Actions lane now also runs the normal
native-browser version and retains screenshots; use the PR's executed results,
not merely this configured lane, as evidence. Tests install browser dependencies
only in disposable CI, never on the owner workstation. No native screen-reader
or real 200% browser-zoom audit, new inference, representative portfolio, model
compatibility or quality guarantee is claimed.

## Reconciliation and remaining work

#146/#151/#155 are merged, as are the saved-run builder, native graph validation,
layout and Wan diagnostic work. Open #164 owns source-bound continuation; #165
owns explicit download resume. This slice is based directly on main, not on an
old bundle stack, and changes neither continuation nor download behavior.
The current owner choices and runtime/uncertainty evidence remain unchanged.

#144 stays open for general dependency substitution, immutable external source
snapshots, fresh installation evidence and guidance across shared document
revisions/native tools. #143 still owns representative portfolios. A local
agent can call the same CLI/HTTP evaluator now, but this does not add a new MCP
permission, agent execution command or automatic correction loop.

## Executed checkpoint

Local verification used the complete tracked source at `aebe10c` (every Git
file blob checked, including declared line-ending normalization), plus this
patch. The targeted suite passed **33 test methods**, including a wrapper for
**nine Node client contracts**. The full suite passed **1,338 tests: 1,323 passed,
15 skipped**. Repository validation passed **66 graphs/bindings and 121 pins**;
JavaScript syntax, Python compilation and Git diff whitespace checks passed.
The browser `--inert`/real-Python-HTTP driver passed at **1440, 720 and 390px**;
all three screenshots were inspected. Native browser transport is a separate
hosted CI result, not inferred from the local fixture.

Main advanced to `f251f828a29334fe7e7da4bc9f8e1f63c0ccaf10` during the pass.
Its 19 changed paths (continuation, download resume and related tests/docs)
do not overlap this patch. Publication is on that newer main; hosted CI must
establish the combined state, rather than treating the earlier local suite as
a test of code not present locally. The helper branch used for source/patch
transport is not part of the feature PR.

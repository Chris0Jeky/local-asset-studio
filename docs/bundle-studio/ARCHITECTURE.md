# Bundle architecture and interaction design

Status: accepted for the first frontend slice; deeper contracts below are planned.
Date: 13 September 2026. Inspected main: `8f471d62a63c339429f95e6a4b55707e99949d8b`.

## The usability problem

A recipe title alone does not explain why someone should choose it. A model
filename is not a visual style, an installed adapter is not necessarily
compatible, and a beautiful example may have used a different graph or extra
post-processing. The existing Studio already owns recipes, settings knowledge,
model inspection, controlled comparisons, saved setups and guided workflows.
The next interface should connect those capabilities, not add a competing
preset store, wizard framework or queue.

The useful selection unit is a **creative bundle**: an outcome-oriented view of
an exact workflow, its resource composition, effective controls, source claims
and examples. The word bundle describes the view; it does not promise a new ZIP
of model weights or a self-contained runtime.

## First slice: a projection, not a migration

`studio-shell.js` loads the new assets only on the main Studio page.
`bundle-core.js` is a pure CommonJS/browser policy module. It resolves allowed
controls from **preset defaults → authored recipe → explicit edits**, validates
finite values and safe integer seeds, projects bound graph resources, filters
local preview paths and formats evidence without inventing acceptance states.
`bundle-explorer.js` is a client of existing global workbench commands and read
APIs. `bundle-showcase.json` is an index of two existing preview/receipt links,
not a source of executable graphs or a new evidence ledger.

The explorer reads the already-loaded catalog/recipes/KB, gets a selected
preset's resource graph from `/api/inspect/<id>`, and reads the static showcase.
It does not POST, poll, call a provider, download a model, switch an environment
or create a job. Local examples use the existing `/api/examples/` route. Other
URLs are explicit HTTPS source links; third-party image hotlinking is rejected.

Apply requires a visible confirmation and a fresh comparison against the
workbench. A changed workbench or catalog invalidates the preview. It delegates
to `selectPreset`, `applyRecipe`, existing draft hooks and `showView`, with batch
one and an explicit reference reset. No second submission path is introduced.
The browser equality snapshot is **not** a cryptographic identity, persistent
revision, cross-client lock or authorization token. Server preflight and
submission controls remain authoritative.

A failed inspection means resources are unknown, not ready. Loading a bundle
can still populate Create for inspection; it cannot certify execution. Unknown
bindings fail visibly instead of being discarded. Reference/non-image routes
stay inspect-only because a generic recipe reset is not a valid reference or
asset-lineage handoff.

## What the user sees

| Layer | Question answered | Interaction |
| --- | --- | --- |
| Outcome card | What kind of work could this help with? | Search a look, family or file; see a historical preview or an explicit gap. |
| Ingredient view | What is actually involved? | Checkpoint/diffusion model, encoders, decoder and adapters, with graph bindings. |
| Adapter explanation | What does this add? | Stored role, trigger/position, authored strength, source range, notes and recorded checksum. |
| Settings guide | Why these values? | Family-scoped guidance and separately labelled local observations; source links. |
| Adaptation | What will I change? | Edit named fields, reset, compare against the bundle and the current workbench. |
| Preparation | Can this machine run it now? | Existing Create/readiness/preflight; still a separate Generate decision. |

Native details elements provide progressive disclosure; buttons, labelled
controls, visible focus and dialog Escape/cancel semantics provide keyboard
operation. The narrow-screen layout uses a horizontal card shelf and a vertical
detail flow, not a squeezed desktop control grid. Motion is unnecessary and
reduced-motion/forced-colour preferences are respected. This is a first useful
entry point, not a completed studio-wide redesign.

## Next contract: source-scoped claims (#144)

Keep a recommendation separate from a chosen value. A future claim should carry
`control`, `resource_revision`, `source_kind`, `source_locator`, `retrieved_at`,
`recommended_range`, `tested_range`, `prerequisites`, `evidence_refs` and
`supersedes`. Distinguish creator documentation, a local observation, a controlled
experiment and an authored hypothesis. Missing values stay unknown. Conflicting
recommendations remain inspectable; do not average them into a false optimum.

Current KB family axes can refer to a slot number rather than a resource. The
explorer therefore omits family-level LoRA-slot axes from its setting guide and
uses the actual selected file's KB entry for adapter ranges. It does not
silently treat an arbitrary new file in slot two as the old style adapter.
Stored hashes are displayed as stored hashes, not as a new local verification.

Source intake belongs in #9. Civitai/Hugging Face retrieval must be an explicit,
reviewed, cached operation with exact source/version/file identity and local
credentials. Page descriptions, embedded workflows and image metadata are
untrusted data, never executable instructions. Blocked access must not be
replaced by invented recommendations. This PR consumes the existing KB and
source links; it does not implement a new Civitai crawler.

## Next contract: modular changes, one document (#120/#144)

Expose meaningful modules over the existing graph: core generator; appearance
adapters; identity/pose/reference controls; sampling/acceleration; correction;
finishing/export. The UI should offer a simple outcome view, expandable steps
and a native graph escape hatch over the **same** revisioned state.

A module toggle must change real bindings and dependency closure, not just a
checkbox's appearance. An accelerator may require a matching step/CFG/sampler
schedule. A checkpoint substitution may invalidate the encoder, VAE, adapters,
trigger syntax, stored examples and memory estimates. Pose control requires
actual reference roles and transforms, not a promise hidden in prose. Distinguish
compatible, incompatible, unknown and native-only capability results.

Propose the entire change set first: changed values/resources, required input,
source rationale, invalidated examples, download/compute implications and how
to revert. Apply atomically through existing Workspace/shared commands with
`expected_revision`; a stale agent proposal must conflict rather than overwrite
a human edit. Reuse the existing Production coordinator and budget. Never hide
installation or inference inside a visual toggle.

Connect #118's existing guide to observed state: resource resolved, input valid,
run prepared, output recorded, review recorded. Opening a panel is navigation,
not successful work. A lightweight "why / what changes / try next" coach beside
the relevant control is preferable to an unsolicited blocking tour.

For video, audio and 3D retain this navigation pattern but use modality-specific
controls and evidence: synchronized clip comparisons, labelled dry voice takes,
and neutral turntables, rather than pretending steps/CFG describe every tool.
Native Krita/Blender/DAW work remains in those applications.

## Research and source limits

Primary sources checked on 13 September 2026:

- [ComfyUI LoRA tutorial](https://docs.comfy.org/tutorials/basic/lora): separates
  model and text-encoder strength, supports chained adapters and illustrates a
  same-parameter baseline comparison. Hence no generic "style amount" meaning
  should be imposed on every adapter control.
- [Diffusers reproducibility](https://huggingface.co/docs/diffusers/using-diffusers/reusing_seeds):
  explains RNG state and runtime/platform considerations. This is evidence for
  recording the full execution context, not advice to change ComfyUI's runner.
- [Civitai API wiki](https://github.com/civitai/civitai/wiki/REST-API-Reference)
  redirects developers to [the current reference](https://developer.civitai.com/site/reference).
  The new reference could not be retrieved in this session. No new endpoint or
  response-field contract is claimed verified here.

Model-specific numerical advice in the UI is **existing repository KB data**,
with its own date and source links. It was not independently re-fetched from
every model card for this PR. Do not promote it to newly measured guidance.

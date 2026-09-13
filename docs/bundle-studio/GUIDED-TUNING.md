# Guided setup changes and reversible bundle drafts

13 September 2026 · focused implementation of #144 · stacked on #146 at
`931a732a90fb490683a802288f0c0d2ba5d91882`.

## Reconciliation before implementation

#146 is still open. Its review correctly identified that the real Studio static
handler rejected the showcase JSON route. The parent now imports a generated,
checked-in ES module through the existing allowed JavaScript route, without
broadening the static-file policy. Serialization/parity and real-Handler HTTP
regressions were added. Parent head `931a732` passed Check studio #426 and Windows
runtime safety #120. See [delivery correction](DELIVERY-FIX.md); the original
mocked fixture was not proof of HTTP integration.

Merged #138/#145 already provide preset-compatible builder tickets and run/recover
controls; #131/#134 already own shared documents, steps and agent access. This
slice does not replace any of them. #142 and open #149 own download/intake
behavior; nothing here installs or moves model files. #139 records the owner's
choice of Anima B's softer cinematic shading; its images remain experiments,
not finished-art acceptance or a representative portfolio. HUMAN_TODO and the
remaining owner-controlled restart are unchanged.

#143 remains the owner of representative portfolios. #144 remains open for
version-scoped source claims, general dependency resolution and shared revisioned
bundle persistence. The implementation below is a useful bounded step toward
those contracts, not a claim they are complete.

## User workflow

In Create, open **Explore creative bundles**, then choose a bundle. Under
**Try a related setup**, choose an authored alternative using the same preset.
Choose independently whether to preserve your prompt/negative prompt, seed and
canvas size. The default preserves all three.

**Review setup change** shows grouped differences: adapter stack, sampling,
composition and wording. Names say "Adapter 2 file" or "Guidance (CFG)" rather
than only internal keys. Inspect the source recipe's recorded execution status,
notes, links and the proposed stack's stored per-file guidance. Missing triggers,
misplaced triggers, missing hashes, conflicting family labels and values outside
recorded ranges produce explanations, not automatic prompt edits.

After acknowledging that proposal, **Use changes in draft** stages the entire
change in one operation. The workbench is still untouched. Edit a field, undo or
redo the staged changes, or reset to the source bundle. **Apply to Create** is a
second explicit decision; it retains the existing reference-reset consent and
one-output batch. Generation remains the existing separate action.

Example: a four-step authored recipe includes its accelerator and sampling
settings. Adopting it moves all authored adapter filenames/strengths and sampling
controls together. Preserving your prompt may omit the new adapter's trigger;
the proposal points this out without silently adding text. Preserving your canvas
creates a deliberate variation of the recipe, not a claim that its old example
or performance measurements apply to this new size.

## Implementation and authority

`bundle-core.js` implements a pure immutable tuning session with a monotonic local
revision, current controls and source-recipe snapshot, and bounded 32-entry
undo/redo history. No server, store or inference dependencies are added. A
proposal contains before/after controls, preservation choices, grouped diffs,
source/knowledge identity, warnings and the source evidence's actual scope.

Only text-to-image alternatives on the **exact same preset ID** are proposed.
Sharing a family label does not authorize checkpoint replacement or a reference
handoff. The target recipe is fully resolved from that preset's defaults before
explicitly preserved fields are overlaid. The complete sampling and adapter
configuration is moved as one draft operation, rather than selectively copying
an accelerator while leaving the old steps behind.

Acceptance recalculates the proposal against the current preset, source recipe,
target recipe, knowledge base and local revision. Any difference or tampering
refuses the change; undo also increments revision, so an old proposal cannot
become current merely by restoring similar values. Further edits clear redo
history. Raw invalid input remains visible and blocks proposals/apply; it is
not replaced by a last-valid value without the user's decision.

The current workbench and source snapshots are rechecked at final apply. The
staged origin is retained through undo/redo and checked again. Missing browser
select choices refuse before `selectPreset` can reset anything, rather than
silently blanking a sampler or model selector. The existing workbench and server
continue to perform their own preparation and resource checks.

An edited recipe is passed to Create as `unverified`, with no inherited execution
receipt and a source-variation note. An unchanged recipe may retain its historical
execution record; it still acquires no quality or installed-runtime guarantee.
This prevents an edited prompt/stack from inheriting an "Executed locally" note
merely because the source recipe had one.

## Deliberate boundaries

"Atomic" here means one validated, reversible **browser draft change**. It is not
a Workspace transaction, cross-tab conflict control, persistent document revision
or cryptographic authorization. Closing/reopening the explorer clears this
transient draft; normal saved setups/draft recovery apply after transfer to
Create. No new autosave, second queue or agent command protocol is introduced.

Same-preset authoring is not a proof that all chosen files are installed,
architecture-compatible or supported by the current runtime. The proposal uses
existing authored recipes as candidate configurations. It does not solve general
checkpoint/encoder/VAE/LoRA dependencies or enforce every creator's accelerator
schedule. Subsequent manual edits can still create a poor configuration.

Per-file knowledge is explicitly **stored metadata**. Family equality is only a
label comparison, a listed checksum is not a fresh hash of local bytes, and the
KB date is not a per-source retrieval date. No model card is fetched implicitly,
no source conflicts are averaged, and no filename-only compatibility claim is
made. Rich version-scoped claims and atomic shared-document module commands
remain #144, using the existing Workspace/Workflow services.

## Verification

Executed in a focused source workspace, not a full repository clone:

- `node --test tests/bundle_tuning.cjs`: **24 passed**. Preservation, full stack /
  sampling transfer, unknown flags, exact-preset scope, triggers, unknown/invalid
  guidance, atomic acceptance, immutable/bounded history, stale/tampered
  proposals, invalid controls, selector availability and unexecuted handoff.
- `python -m unittest discover -s tests`: nine tests run, five passed and four
  full-Handler tests skipped because this local file set lacks app/server.py.
  This includes the Node wrapper; it is not the full Studio suite.
- JavaScript syntax and Python compilation passed.
- `python tests/bundle_tuning_browser.py --inert <output-directory>`: actual new
  UI/core/CSS in Chromium at **1440, 720 and 390 pixels**, reduced motion enabled.
  Delayed index arrival preserves typed text; reviewed staging, undo/redo, invalid
  dimensions, stale-source refusal, final single-output transfer and execution
  label invalidation pass. No page errors, horizontal dialog overflow or write
  requests were observed. Screenshots were inspected.

Normal HTTP browser navigation was blocked by the environment with
`ERR_BLOCKED_BY_ADMINISTRATOR`; it was not bypassed or reported as passed. In
`--inert` mode assets are inserted with set_content, reads are mocked and the
fixed import URL is replaced in the fixture by a data module containing the same
generated payload plus an artificial delay. Native module parsing and UI behavior
are exercised, not the production import URL's delivery. Parent real-Handler
HTTP tests establish that separate boundary in hosted CI. Default driver mode
supports a normal local HTTP fixture for a less restricted environment.

Hosted CI must establish the full combined unittest/repository-validator result
on the published head. None of this is an owner-PC UI test, 200% browser zoom /
screen-reader audit, inference, timing comparison or art-quality evidence.
No model downloads, runtime changes, queue actions or new artwork occurred.

## Source research and next acceptance

Primary sources checked 13 September 2026:

- [ComfyUI LoRA tutorial](https://docs.comfy.org/tutorials/basic/lora) distinguishes
  model and text-encoder strengths and chained adapters. This supports keeping
  controls tied to actual bindings instead of a universal style slider.
- [Diffusers adapter loading](https://huggingface.co/docs/diffusers/main/en/using-diffusers/loading_adapters)
  documents model-specific adapters and trigger/scale considerations. It is
  background for preserving resource conditions, not an implemented Diffusers
  or hotswap integration in Studio.
- [Native dynamic import](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/import)
  supplies the module-loading contract used by the parent's delivery fix.

On the actual Studio, first compare the authored Anima base/first-style recipes
without generating; confirm the real file choices, full diff and revert. Then
exercise one supported accelerator alternative. Keep #143's bounded representative
experiment separate from this UI acceptance. Use existing shared workflow
commands when promoting these transient changes to revisioned reusable modules;
do not add an independent bundle database or hidden generation path.

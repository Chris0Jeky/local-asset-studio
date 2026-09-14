# Guided repair, native editing and agent parity

Design for #251. Reuse #118 guided journeys, #120 workflow documents, #123 SDK/MCP, #71 native revisions and #232 reviewed reference apply. No parallel client-owned plan or invisible second executor.

## 1. The everyday path

**Choose the source.** From an image in the existing asset library, open Repair/Extract. Retain unsaved metadata and existing Create state. Show the original and available larger source, not an automatic global enhancement. For a sheet, preview panels and let the user correct boundaries before extraction.

**Choose the target and problem.** Click an instance or draw/select a region. Offer concise tasks: fix anatomy, refine a small detail, isolate subject, enlarge, complete missing area, or repair shared contact. The problem can be described in plain language; detected regions are proposals. A visible rock beside a character and a rock hiding the desired arm lead to different operations.

**Review what may change.** Show target selection, context and final write/protection overlays separately. Use labels, patterns and text as well as colour. The default preserves correct faces, clothing and neighboring subjects. Detailed painting opens the existing native editor rather than a half-built duplicate brush engine.

**Inspect the proposed route.** One card states the intended change, protected features, exact model/route, required references, why this route fits, remaining uncertainty, attempt limit and measured/estimated/unknown cost. A blocked route explains a concrete remedy. Do not show a universal percentage called Quality.

**Request candidates explicitly.** Default to a small serial comparison within the registered allowance; preview is never Start. Preserve the command identity across a lost reply. The user can navigate away or inspect artifacts without silently submitting new work.

**Compare and decide.** Keep original, candidate and protected composite distinct. Provide a synchronized region zoom, full-context view, mask overlay, changed-pixel view and optional flicker compare respecting reduced-motion preferences. Review intended change, identity/costume, contact and seams individually. Accept a patch, revise scope/strategy, keep for later or stop; a rendered image is not automatically a keeper.

**Finish deliberately.** Show the accepted repair master before optional enlargement. New background, missing body completion and global relighting are explicit branches. Reassemble panels and expressions without regenerating typography or accepted artwork. Draft and accepted exports remain visibly different.

## 2. Progressive disclosure

Guided view exposes the next useful decision. Steps view exposes ordered operations, their inputs and dependencies. Native/advanced graph view exposes supported Comfy controls through the existing workflow-studio architecture. All three edit the same revisioned document. A change to a hidden node cannot bypass scope/budget/preflight requirements; a semantic change in advanced view invalidates relevant previews and evidence.

Suggested standard modules are Intake, Panel layout, Target/context, Repair candidate, Review, Finish and Export. They are typed projections of real registered operations, not arbitrary checkboxes whose hidden incompatibility is discovered after a long generation. Module substitution reuses #144 and shows changes to model, references, transforms and preservation before applying them.

## 3. Context-aware assistance

Ask only the question that unblocks the case: which of these repeated figures is the target; whether the obscured hand should remain hidden; which costume back construction is canonical; whether the wrist or the prop should move. Show the relevant crop. Do not ask the user to understand latent masks before they can request a hand repair.

A helper can propose a defect description, targeted prompt and likely route. Display its uncertainty and let the user edit it. It cannot convert a source instruction, metadata string or generated critique into authority to download packages, run commands or accept artwork. The same experience remains usable with no local language model installed.

Prefer a no-op for intact areas. If only a hand is defective, face detailing is off. After repeated failure, explain the changed hypothesis rather than suggesting another identical seed indefinitely. A native paint/pose-guide handoff includes the source, current crop, mask, references, intended joint/contact, failed candidate and exact return dimensions.

## 4. Proposed shared command vocabulary

Names below are design interfaces, not claims of already exposed endpoints. Bind them to existing versioned workflow/native commands during #251 implementation.

| Command | Effect and required boundary |
|---|---|
| `repair.inspect` | Read existing source/observations; no model work |
| `repair.propose` | Deterministic plan proposal; optional AI analysis is a separate explicit request |
| `repair.preview` | Exact effective scope, dependency and graph diff; no generation |
| `repair.request` | Existing Production admission with campaign, source revision and retained command ID |
| `repair.observe` | Observe known project/job; never recreate unknown work |
| `repair.collect` | Retrieve known artifacts without generating replacements |
| `repair.compare` | Present evidence, not auto-accept |
| `repair.accept` | Record an explicit authorized review decision on the exact candidate/revision |
| `repair.revert` | New revision restoring a prior accepted state; no source deletion |

Commands return document/revision and artifact IDs, evidence status and stable machine reasons. Suggested reasons: `stale_source`, `scope_conflict`, `mask_encoding_ambiguous`, `unsupported_reference_count`, `unreviewed_geometry`, `runtime_unobserved`, `budget_exhausted`, `submission_unknown`, `registration_mismatch`, `visibility_uncertain`, `native_revision_changed`. Do not leak arbitrary local paths into web projections.

The offline `repair_proposal.py` has only `describe` and `validate`; it is not this API. Its `executable:false` is deliberate.

## 5. Recovery and concurrent work

Separate current typing, last saved document, accepted edit and unconfirmed command. A reload cannot resend Start. A changed mask cannot inherit the prior command's authority. A late reply must not replace later typing or a different source. Store only appropriate bounded recovery data in the existing mechanism; native unsaved state remains owned by the native revision guard.

User and agent edits use expected revisions. Refuse stale application and offer a comparison against the new source, never silently rebase a semantic patch. Undo changes the local document revision; it does not prove cancellation of remote work. Cancellation controls state whether they stop observation, remove queued owned work or request interruption.

## 6. Acceptance scenarios

Actual browser tests must exercise the shipped shell through real HTTP and temporary Workspace state at desktop, 390px and actual 200% zoom, with keyboard navigation, visible focus, announcements and no colour-only status. Synthetic inert transport is labelled separately from native-origin evidence. Test switching source while a preview is pending, two clients editing masks, lost Start response, reload, restored draft, a hidden neighboring target and cancelling a proposed scope expansion.

Headless tests submit equivalent semantic documents and compare effective input/graph identity with the UI path. Native tests include unsaved painting, hidden/off-canvas changes, layer reorder and later edits to the proposed layer. A supported flat RGBA8 native fixture is not general Krita document compatibility. Real owner workflow and successful neural repair remain a separate release gate.

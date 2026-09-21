# Adaptive UX specification

## 1. A workbench, not an omnipresent dashboard

Keep the creative act visually dominant. The top row holds the active task, recipe summary and optional appearance control. The main work area holds the brief and task-relevant sources. A contextual support area contains **one next action**, at most two secondary observations and an expandable explanation. The persistent run area shows the actual operation and its state.

At narrower widths, support becomes an inline section after the relevant input, not a third column. At 1440x900, Guided and Focus should keep the starting prompt, recipe and run summary discoverable without scrolling through education. A wide Bench is justified for side-by-side comparisons or temporal work, not as the default for every task.

A proposed task switch changes the *lens* first. It may suggest compatible recipes but cannot select one implicitly. Choosing a recipe invokes the existing guarded application path. An explicit difference review names what is retained, replaced, unsupported or still needs a source. Cancelling restores focus and leaves every draft value and File object intact.

## 2. Assistance levels and adaptation rules

**Guided:** one short imperative, a visible destination, and an optional two-sentence explanation. Example: “Add a pose picture” followed by “Picture 2 supplies geometry; the character remains Picture 1.” The source order must come from the selected route, not this example.

**Studio:** compact summaries and relevant controls; guidance appears on a blocker, an explicit Help request or a consequential context change. No automatic prompt rewrites.

**Expert:** direct access to expanded technical controls and provenance. Expert is not an authorization bypass. Recovery warnings and unsupported-source explanations remain visible.

All levels retain searchable commands and a “Show all controls” route. No time-limited help, personality inference or hidden adaptive ranking based on private prompt text. Allow users to pin a panel, dismiss advice for the current rule/context, and reset presentation independently of their draft.

Adaptation changes relevance, not spatial memory. Preserve the editor's DOM identity, cursor selection, composition/IME state, keyboard focus and scroll anchor. Do not reshuffle cards while typing. Commit a new guidance projection after a settled edit or explicit navigation; present changed advice at a stable location. Announce only meaningful changes, not every keystroke or job poll.

## 3. Workflow atlas

These are proposed task lenses over existing services or explicit future prerequisites. A lens is not proof that a route exists or is qualified. Capability inventory decides which actions appear.

| Task / desired result | Primary workspace | Context-aware next action | Explicit limitation / owner |
| --- | --- | --- | --- |
| W01 Start from words | Large brief, style intent, canvas summary | Find a compatible starting recipe or resolve its first prerequisite | Catalog/compiler owns supported prompt grammar; no universal “quality” slider |
| W02 Edit an existing image | Source plus change request, keep/change summary | Attach an edit source and inspect supported edit mechanism | A text instruction is not a protected-pixel mask |
| W03 Combine identity, style and outfit | Ordered reference board with per-image contributions | Resolve an unassigned role or an unsupported source count | `references.py` and exact route bindings own order/capacity; never silently drop extras |
| W04 Transfer a pose | Character, geometry source, optional guide preview | Inspect pose ambiguity; choose supported skeleton/depth/picture route | Style reference is not a pose controller; unusual pose fidelity requires evaluation |
| W05 Build a character sheet | Canon reference, shot list and consistency checklist | Prepare one reviewed view before expanding the series | Existing character/figure services determine which operations are available |
| W06 Repair a local defect | Source, target region and preservation declaration | Open the real mask/native editing path or explain its absence | No fake brush UI; scoped edits require an actual supported write-scope mechanism |
| W07 Upscale or finish | Before/after area, target size and detail preference | Review exact output dimensions and finishing route | Do not describe interpolation as model-based detail recovery |
| W08 Animate a still | Source, duration/framing and first/last-frame affordances | Supply the frame required by the selected route | Route-specific temporal support; no unsupported interpolation switch |
| W09 Assemble a sequence | Ordered clips, timing and audio lanes | Open the existing Scene editor with supported registered inputs | Use existing AV bounds and validation; a storyboard is not a rendered video |
| W10 Compare settings | Candidate matrix, fixed context and budget summary | Plan a bounded comparison and inspect its total work | Production plan, reservation and Start remain separate |
| W11 Review and continue | Large output, compact decisions and provenance | Record a confirmed review, then prepare a copy/continuation | Existing revision guards; no automatic artistic approval |
| W12 Organize/export a pack | Selection, manifest, naming and destination preview | Resolve an export requirement or inspect a collision | Existing Workspace/native export owners; metadata suggestions require review |
| W13 Build a workflow | Node canvas plus readable selected-node inspector | Fix the selected connection or unresolved binding | Node-schema and compile results remain authoritative; no invented node capability |
| W14 Choose a model/adapter | Searchable inventory, compatibility and source evidence | Review a replacement stack's changes before application | Installed, compatible, source-reviewed and artistically preferred are distinct |
| W15 Recover interrupted work | Operation receipt and current draft side by side | Inspect the original operation ID | Unknown outcome never becomes a Retry button without disposition |
| W16 Voice or 3D exploration | Task-specific native/voice/mesh entry | Open the supported tool with its prerequisites | A planned tool appears as planned, not as a disabled mystery control |

## 4. Contextual components

**Task lens chooser:** show a small initial set (Create, Edit, Combine, Pose, More), with search for all lenses. Explain what a lens changes before any recipe mutation. Remember an explicit user choice, not inferred preferences.

**Recipe navigator:** task compatibility is a filter with an explanation, not an opaque score. Cards show the exact recipe name, supported input shape, required backend, installed/unknown state and observed timing only when it applies. Compare replacements in one review surface. Favorites scope is a pending owner choice; start with local user favorites only if accepted, without inventing a project concept.

**Reference board:** persistent asset IDs, human-readable roles, ordered slot numbers where required, local File/pending staging state, and per-source take/avoid notes. Reorder handles need keyboard controls. Remove is reversible within the current edit; staged server copies follow existing retention rules. A route change previews role reassignment, excess sources and missing slots rather than relabelling silently.

**Model and adapter inspector:** recipe model summary remains visible; the full stack is a drawer. Each adapter gets filename/identity, strength, known trigger guidance, compatibility evidence and a reset-to-authored value. Unsupported combinations stay explicit. A future adapter preview may show approved examples, clearly separate from the current prompt's output.

**Prompt workspace:** default to one readable brief. Optional Style, Keep, Avoid and Output sections are views over existing intent/compilation contracts, not simultaneous incompatible prompt stores. Editing an intent facet invalidates its compiled preview. Applying compiled text requires a preview and preserves unsupported content as a clearly identified review note rather than pretending it reached the model.

**Next-action card:** short title, one action, and “Why this?” containing source, observation freshness and affected control. Examples: “Check the local backend”, “Attach Picture 2”, “Review the original request”, “Choose a supported negative-prompt path”. Action adapters target stable semantic commands, not brittle CSS strings supplied by an LLM.

**Run dock:** one explicit operation action, actual job state, bounded estimate when known, and the first actionable blocker. No green badge from an empty failure-to-load response. Never hide a submission receipt under ambient art. A disabled action has an adjacent explanation and reachable remedy; it must not rely on hover.

**Continuation shelf:** distinguish “Prepare same seed”, “Prepare new seed”, “Open as copy” and “Inspect original run”. Avoid one ambiguous Continue action that conceals a destructive replacement. Retain original recipe, prompt ID and input lineage.

## 5. Dynamic-state matrix

| Situation | Main UI | Suggested action | Must remain unchanged |
| --- | --- | --- | --- |
| No recipe | Brief remains editable; catalog placeholder has no fake ready count | Open discovery | Draft text and appearance |
| Sources required | Empty required slots become prominent | Attach to the exact named slot | Other source roles and text |
| Unsupported extra source | Show all source cards and route limit | Review a compatible route or remove deliberately | No implicit truncation |
| Missing model / wrong backend | Keep current setup; show exact missing prerequisite | Open Models & setup | No installation/switch on navigation |
| Stale readiness | Display “Needs a fresh check”, retain last observation as historical | Recheck through existing owner | No stale green execution affordance |
| In-flight run | Preserve recipe and visible receipt; animate only genuine measured progress | Inspect run | No second submission; ambience pauses |
| Unknown submission outcome | Recovery takes precedence over creative advice | Inspect original request ID | No replay; no invented cancellation |
| Another tab edited draft | Conflict choice with export/reload/keep options | Review conflict | No silent local overwrite |
| Internet absent, local API healthy | Core workbench stays usable | None solely due to internet hint | Local creation remains available |
| Studio API absent | Keep editable draft/export where existing state permits | Reconnect and inspect before submitting | No fabricated saved status |
| Optional media fails | Quiet same-theme poster or token-only fallback | Optional retry after deliberate action | Workbench capability and focus |
| Reduced motion / low-power mode | Static ambience and immediate state changes | No action needed | All guidance and functionality |

## 6. Two concrete journeys

### Character plus difficult pose

Start from an existing character asset, choose Pose, and keep the character's identity/source link. Ask for the geometric source only if the chosen route needs it. The board states which picture supplies what. When a skeleton would help, open the real pose editor rather than a decorative approximation. Review its rendered guide and its missing/unknown joints. A recipe switch shows changed ordering and whether the previous pose wording is still valid. Generate remains separate. Review the output for pose and identity independently; prepare a targeted correction rather than claiming the first run succeeded artistically.

### Connection loss while a run is uncertain

A wallpaper timeout changes only the ambience. A Studio API interruption changes execution evidence to unavailable. The current request ID remains visible. Recovery offers a read of that ID; it does not resubmit. Once a committed receipt is checked, the user can deliberately load or continue its output. Reconnection does not replay a command or force an animation. The editor's unsaved text survives every presentation transition.

## 7. Language, accessibility and customization

Use “what happened / what remains / next action” rather than repeated explanatory essays. Keep diagnostic codes and raw details one disclosure away. Use native buttons, fields, labels and dialog semantics; keep Esc and focus restoration across nested flows. Do not hide required references merely to hit a control-count target.

Panels can be pinned or reset in a future layout preferences editor, but do not begin with an arbitrary drag-and-drop dashboard builder. Provide two tested layouts before exposing free placement. Skin assets are decorative; labels, contrast, validation, source roles and progress semantics are real HTML. Normal mode must be as usable without any artwork as with it.

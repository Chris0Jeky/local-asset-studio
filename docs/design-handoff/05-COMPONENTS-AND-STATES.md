# 05 · Components and states

The component catalogue a redesign must cover. "Today" names the current implementation so a designer can find it in
the screenshots; "Must show" is the contract every design has to honour. Items marked **Proposal** are new.

## 1. Execution state: jobs (single runs)

Server truth: `app/server.py` job `status`, plus two dispositions that are **not** statuses.

| Status | Plain meaning (use this copy) | Visual weight | Allowed actions | Never |
| --- | --- | --- | --- | --- |
| `queued` | Waiting its turn | neutral, position if known | Inspect | Cancel is not offered today (no endpoint) |
| `waiting` | Waiting for ComfyUI to finish other work | neutral | Inspect | — |
| `submitting` | Sending to ComfyUI (prompt N of batch) | active | Inspect | — |
| `running` | Generating; elapsed time, estimate, sampler step when reported | active, **the only animated state** | Inspect | Fake progress; ambience motion (must pause) |
| `completed` | Finished; outputs saved | success, quiet | Open, Keep / Needs work / Rejected, Continue with this, Compare, Download, Recipe | "Approved" stars (completion is not art acceptance) |
| `partial` | Some outputs of a batch arrived | warning | Resume observation, Put away | — |
| `failed` | ComfyUI reported an error, or it failed before sending | error, with diagnosis ("Memory allocation failed" + Next: …) | Open as draft, Recipe, Put away | Auto-retry |
| `uncertain` | **Sent, but the outcome was not seen.** It may have run | distinct "unknown" style (not error red, not success) with a retained-receipt motif | Resume observation (reads only), Stop tracking (reason required), then Put away | **Retry / Run again** — never; never shown as failed or as done |
| `not_submitted` | Proven never sent (restart or queue timeout) | neutral-warning | Abandon (reason), Open as draft | — |
| `abandoned` | Written off locally; remote work not cancelled | muted | Put away / Bring back | Implying it was cancelled |
| disposition: tracking stopped | Owner stopped watching an uncertain job | muted + reason shown | Resume observation of retained prompt | — |
| disposition: put away | Hidden from Problems/desk; reversible | hidden; counter "Show put away (M)" | Bring back | Deleting anything |
| mixed batch | Some prompts known, one send unknown | unknown style | Check known batch receipts, Abandon remaining batch locally | — |

Polling today: jobs every 4 s while anything is active, else 15 s; paused when the tab is hidden.

## 2. Execution state: plans (Runs)

`planned` (prepared, nothing sent; Start is yours) · `queued` · `submitting` · `running` · `waiting` · `observing` ·
`rendering` · `awaiting_review` · `reviewed` · `completed` · `partial` · `failed` · `uncertain` (keeps its reservation,
never retries) · `interrupted` · `stopped` (you stopped it or time ran out; nothing resumes by itself).
Plan kinds: comparison, scene (av), voice, native export, articulated prop.
Actions: Start · Stop after current stage · Reconcile… · Extend time (minutes + reason) · Branch this study ·
Open review desk · Full plan. Budget: "N of M runs reserved" and a time allowance.
Design must show **all 15** statuses (the current legend shows 7) and group them: *Ready to start*, *In progress*,
*Needs your decision*, *Needs attention*, *Done*.

## 3. Environment and health

| Component | States |
| --- | --- |
| Health pill (top bar) | Connecting… · Checking ComfyUI… · Readiness unavailable · Studio worker unavailable · ComfyUI offline · Checking node readiness · Recipe needs models · ComfyUI connected |
| Environment switcher (Models only) | Main library 8188 · HiDream O1 8192 · MiniMax H3 8194 · Qwen-Image 2.1 8196; switch: running · completed · failed · interrupted; disabled while busy: "A local operation is running. Switching is disabled until it finishes." |
| Runtime recovery line | idle · checking · healthy · startup · reconnecting · unreachable · unreachable-but-alive · crashed-absent(-busy) · foreign-or-ambiguous-listener · blocked · leased · breaker-open (only state with Retry) · disabled |
| GPU lease (not shown today) | held by holder until time; new jobs and switches refused while held. **Proposal:** show as a top-bar chip "GPU reserved by <holder> · 12 min" |
| Connection distinctions (AMBIENCE.md) | Never merge: internet hint · Studio API reachable · ComfyUI/schema ready · decorative media available · job activity |

## 4. Disabled-with-reason (the pattern that fixes #278)

Rule: a disabled control has an adjacent, visible reason (not hover-only), linked with `aria-describedby`, and where
possible a fix button. Where a disabled button would swallow the click, keep it enabled and answer the click with the
reason (Create's *Pull from library* already does this).

Reasons already written in code (reuse the copy):

| Control | Reason text |
| --- | --- |
| Generate | "Choose a recipe." · "An attachment or submission is in progress." · "The model environment is switching." · "Studio worker is unavailable. Restart Studio; no generation can be queued safely." · "ComfyUI is offline. Start it with the Studio launcher." · "Switch explicitly to {backend} in Models & setup." · "Missing requirements: …" · "Attach every required reference before starting." · "Fill in the wording: replace "…"" · "You added a second picture, but this recipe reads one. Say what it is for." |
| Pull from library | "This recipe takes no reference image. Choose a reference recipe…" |
| Use this pose | "Mark at least two joints: a guide with fewer draws no limb." |
| Export review evidence | "Save your unsaved changes first" / "Finalize the review first" |
| Voice: Prepare take | "Install and configure the isolated voice bundle to prepare a take." |
| Scene: Render | "Render unavailable: <tools>." |

Disabled **without** a reason today (each needs one): Review next (0 unreviewed), Select visible, Save details while a
save is pending, Save collection, Prepare plan, Undo/Clear/Create child assets (figure split), Import planned case,
Restore assessment, *Prepare in Create* (handoff, incl. mask-required), Restore source wording / Change route / Leave
continuation, pose X/Y fields and joint buttons, result-tile Keep/Seed buttons while busy, Refresh overview, bundle
Undo/Redo/Use changes, Install while another download runs, uninstalled environments, Prompt Lab saved-brief buttons,
reference-review buttons, Workflow builder toolbar (Undo, Redo, Accept refreshed schema, Export document, Check
connections, Export checked API graph, Load revision history, Restore revision).
Also: Review desk *Record decision* is never disabled and fails on the server; it needs a pre-flight checklist instead.

## 5. Component catalogue

| # | Component | Variants / states | Today | Notes for design |
| --- | --- | --- | --- | --- |
| C1 | App shell | sidebar expanded/collapsed/mobile drawer; top bar | `studio-shell.js` | One shell for every page including Spoken Briefs and Workflow Studio |
| C2 | Command palette (Ctrl K) | empty, results, no match | tools only | **Proposal:** also recipes, assets, runs, actions ("Review unreviewed") |
| C3 | Status pill / chip | 8 health states; job and plan status chips | text pill | Shape + icon + text, not colour alone |
| C4 | Page header | title, one-line purpose, primary action | eyebrow + slogan + paragraph | Drop slogans; one line of purpose |
| C5 | Task lens chips | Create, Edit, Combine, Restyle, Pose, Animate, 3D, More | 7 task cards | Selecting a lens never changes the recipe by itself |
| C6 | Recipe card | ready / needs files / other environment / unverified / selected; with thumbnail, input shape, time, family | text card with chips | Thumbnail from the recipe's example; time "about 42 s on this PC" or "no timing yet" |
| C7 | Recipe picker dialog | search, filters, empty, difference review on change | "Find your recipe" | One way to choose; "Help me choose" becomes a filter |
| C8 | Brief editor | plain, with wildcard chips, with compiled preview | textarea | Large, auto-growing; Negative as a sibling field when the recipe binds one |
| C9 | Parameters drawer | summary line ("768×1152 · 30 steps · seed 2026…"), expanded controls, LoRA slots, reset to recipe | disclosures | Show summary always, controls on demand |
| C10 | Adapter (LoRA) slot | off (strength 0), on, trigger word hint, missing file | slot rows | Trigger word visible when on |
| C11 | Source board slot | empty required, empty optional, attached (thumb + size), staged, invalid, extra/unsupported; role label fixed or selectable; reorder | reference cards | Keyboard reorder; thumbnails always |
| C12 | Library picker | slot target, search, grid, "advances to next empty slot" | modal | Keep behaviour |
| C13 | Pose editor | joints, selected joint, unknown joint, start-from, undo/redo, keyboard nudge | canvas | Keep; add visible key hints |
| C14 | **Run dock** | ready, blocked (first blocker + count + fix), submitting, running (this draft's job), estimate, variations, Ctrl+Enter | fixed bottom bar | Must never cover the field being edited; compact on mobile |
| C15 | Readiness checklist | pass, fail with fix button, unknown, stale ("needs a fresh check") | collapsed disclosure | Expand automatically when blocked |
| C16 | Time estimate | calculating, "Expected: 42 s", range, unavailable | text | Show measured source ("last 3 runs") in a tooltip-free disclosure |
| C17 | Job card | every status in §1 | gallery card | Status by shape/icon/text; running shows elapsed + step |
| C18 | Problem card | failed (diagnosis + next), uncertain (receipt), abandoned, put away | card with forms | Reason fields appear only after choosing the action |
| C19 | Result tile / strip | image, video, 3D, audio; seed; Keep / Needs work / Rejected; Continue; Same seed / New seed | output tiles | Grouped by draft or source pair |
| C20 | Continue-with-this menu | Edit, Refine, Restyle, Combine, Animate, Make 3D, Split figures, Upscale | dialog with tabs | Verbs on the tile; details in Make |
| C21 | Asset card | selected, focused, favourite, review state, run label, trashed, video/3D/audio badge | grid card | Title fallback from prompt, not "<recipe> · 1" |
| C22 | Asset grid + bulk bar | none/n selected, n outside view, batch progress, per-item failure | grid + 17-button bar | Group bulk actions: Decide · Organise · Export · Danger |
| C23 | Asset detail panel | view, edit, unconfirmed save, conflict | modal dialog | **Proposal:** side panel so the grid stays visible |
| C24 | Review mode | queue position, decision keys, reason chips, undo, auto-advance after confirmed save | queue strip in dialog | See §7 |
| C25 | Reason chips | hands, face, style off, composition, anatomy, artifacts, crop | chips | Number keys 1-7 in review mode |
| C26 | Collection list | item, count, new, rename, delete, recover | sidebar | Recovery out of the default view |
| C27 | Compare board | 2-4 candidates, blind, revealed, synced crop/zoom, swap, preference 1-5, verdicts | Runs candidate cards + Review desk canvases | One board for both |
| C28 | Plan row + detail | 15 statuses, budget, time allowance | list + detail | Status groups (§2) |
| C29 | Plan wizard | setting, values, budget arithmetic at top, advanced variants | dialog | Primary action always visible |
| C30 | Export wizard | format, frames strip, anchors, filtering, verification | dialog | Drag reorder + keyboard |
| C31 | Dialog | default, destructive, with difference review | native `<dialog>` + ~10 `window.confirm()` | Replace every `confirm()` with a styled dialog that names what changes |
| C32 | Empty state | first use, filtered empty, unavailable (data unknown), trash empty | text blocks | One line + one action; distinguish "none" from "couldn't load" |
| C33 | Notice / status line | info, success, warning, error, persistent banner | single `role=status` line per view | Messages stack or queue; errors don't overwrite successes |
| C34 | Recovery panel | unconfirmed save (request ID, Check status, Retry exact request), conflict (your draft / saved elsewhere / when opened), local draft restore | several variants | Unify into one component; raw IDs in a detail disclosure |
| C35 | Draft bar | saved in browser · time; another tab changed it; storage unavailable; restore / discard / export / import | strip | Quiet by default |
| C36 | Guide coach | step N of M, instruction, observed evidence, show the control, next, pause | panel above Create | **Proposal:** anchored coach mark beside the target control |
| C37 | Next-action card | blocked, ready, running, uncertain, completed | Immersive rail | Must represent running and uncertain |
| C38 | Appearance popover | layout, skin, ambience, hide environment | popover | One control per choice |
| C39 | Ambience slot | none, still poster, subtle loop (paused on run/reduced motion/hidden) | CSS art banner | Decorative only, `aria-hidden` |
| C40 | Environment card | active, available, not installed, switching, busy | select + button | Card per environment with purpose and recipes that need it |
| C41 | Model file card | present/verify, missing, downloading (progress), verified, copy by hand | cards | Long paths truncated with copy button |
| C42 | Node canvas + inspector | empty, draft, selected node, diagnostics | SVG canvas | Pan/zoom/fit; large text fields |
| C43 | Audio player + chapters | playing, looped chapter, saved position | native audio | Voice and Spoken Briefs |
| C44 | Timeline (scene) | clips, selected, unsaved changes | lists | Low priority |
| C45 | Disclosure ("Why?", "Details") | closed/open, remembered per tab | `<details>` | One sentence visible, rest inside |

## 6. Progressive disclosure rules (Proposal, derived from UX-SPEC and the matrix)

| Level | Visible by default | Behind one click |
| --- | --- | --- |
| Every screen | purpose line, the object, the next action, blockers | explanations, provenance, raw IDs, receipts, licence notes |
| Make | recipe chip, brief, sources, run dock, results | parameters, adapters, readiness details, graph, saved setups |
| Run/job | status, elapsed, outputs, one action | prompt IDs, submission record, engine error detail |
| Asset | image, decision, title, tags | file identity, lineage graph, same-run, figure split |
| Review desk | candidates, verdict keys | checks, cleanup seconds, reveal/provenance, evidence export |

Assistance levels (UX-SPEC): **Guided** (one imperative + visible destination), **Studio** (compact; guidance on
blockers only), **Expert** (all controls, provenance). They change explanation, never permissions.

## 7. Keyboard

Shipped today:

| Keys | Where | Action |
| --- | --- | --- |
| Ctrl/⌘ K | everywhere with the shell | Tool finder |
| Ctrl/⌘ Enter | Create | Generate (reports the blocker when blocked) |
| `/` | recipe dialog | Focus search |
| Esc | dialogs, drawers, finder | Close, restoring focus |
| K / W / X / S, ← / → | Library review queue (asset dialog) | Keeper / Needs work / Rejected / Skip; previous / next |
| Ctrl/⌘ A, Esc, Shift-click | Library grid | Select visible (≤ 200), clear, range |
| Arrows (+Shift), Enter | Pose editor | Nudge joint 1 % (5 %); apply typed position |
| Ctrl + wheel, drag | Workflow canvas | Zoom, pan |
| Paste image | Create | Fills the first empty reference slot |

Proposed additions (**Proposal**): `?` shortcut sheet on every page; `G` then `H/M/L/R/S` to go Home/Make/Library/
Runs/Setup; in Review mode `1-7` reason chips, `Z` undo last decision, `Space` zoom 100 %, `F` favourite; in the
Compare board `←/→` focus candidate, `K` keep, `1-5` preference, `B` toggle blind; in Make `Ctrl+Shift+Enter`
Generate with a new seed, `Alt+1..3` jump to slot N. Letter shortcuts never fire while typing in a field.

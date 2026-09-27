# 04 · User journeys

Fourteen journeys, ranked by how often the owner does them. "Current" is the shipped path (click counts from
`docs/UX-USE-CASE-MATRIX.md`, fixture mode, 14-16 Sep 2026, and the 24 Sep live QA). "Desired" is a **Proposal**.
Every journey ends before or at an explicit Generate/Start; nothing in a desired flow runs by itself.

Success criteria apply on top of these global ones: Generate reachable without scrolling at 1440×900 and 390×844; no
disabled control without an adjacent reason; no more than ~120 instruction words visible by default; draft, sources and
focus survive every navigation, recipe switch and presentation change.

## J1 · First image from a brief (daily)

| | Steps |
| --- | --- |
| Current | Overview → "Start with an idea" card (selects a ranked recipe) → Create → type brief → (optionally open Negative prompt disclosure) → Generate. 2 clicks, ~450-470 words on screen. Result appears in collapsed "Recent runs". |
| Desired | Home → **Make** already open with last recipe → type → Ctrl+Enter. The result lands in a results strip directly under the brief with seed, time taken and Keep / Needs work / Continue. |
| Success | ≤ 2 actions; recipe name, expected time and readiness visible beside Generate; result appears in place; the page never scrolls to show it. |

## J2 · Find the right recipe for an intent

| | Steps |
| --- | --- |
| Current | "Change: <recipe>" → dialog with task select, bundles, search, modality, collection, "Help me choose", text cards without thumbnails. Choosing replaces the draft after a `confirm()` when text was typed. |
| Desired | Task lens chips (Create · Edit · Combine · Restyle · Pose · Animate · 3D) filter one grid of **recipe cards with an example thumbnail**, input shape icons (words / 1-3 pictures / pose), measured time on this PC, readiness (ready / needs files / other environment), verified mark. A styled difference review ("keeps your brief, drops picture 2") replaces `confirm()`. |
| Success | Recipe chosen in ≤ 3 actions; the user can see *why* a recipe is unavailable before choosing it; cancelling keeps draft and focus. |

## J3 · Edit an existing image ("change one thing")

| | Steps |
| --- | --- |
| Current | Library → open asset → *Continue with this* → Edit tab → destination recipe → *Prepare in Create* → Create with source attached and wording prefilled → edit wording → Generate. Wrong turn (text-only recipe) now explains itself (fixed 14 Sep). |
| Desired | From any output tile or asset: **Edit** action → Make opens in the Edit lens with the picture on the board and a single "What should change?" field plus "Keep" chips (face, outfit, background, pose). |
| Success | ≤ 3 actions from output to Generate; the source thumbnail stays visible next to the brief; before/after is shown side by side when the result lands. |

## J4 · Combine: put this character into another picture's pose (#422)

| | Steps |
| --- | --- |
| Current | Library → character → Continue with this → Combine → Prepare → Pull from library → pose picture → fill three bracketed parts (who / pose / clothes) → Generate. 9-13 steps, 5 clicks, 3 view switches. Engine switch (Copy Pose, skeleton, depth, replace, pose-first 9B, 4B) keeps sources. *Draw the pose* editor available. |
| Desired | Combine lens: **two source tiles side by side** (Character · Pose), three short named fields remembered per character, engine chips with measured time, optional "Draw the pose" panel, and a **results-per-pair strip** showing each run's seeds next to both sources with Keep / Needs work / Same seed / New seed. |
| Success | Both pictures and the latest results visible together without scrolling at 1440×900; switching engine is 1 click and never loses the fills; failed/uncertain runs for this pair are visible but folded. |

## J5 · Restyle a picture

| | Steps |
| --- | --- |
| Current | Continue with this → Restyle → recipe (Klein 4B leads, WAI second per owner q-27) → Prepare → edit the finish sentence → Generate. |
| Desired | Restyle lens: source tile + "Look" chooser (named looks with example thumbnails, or "from a picture") + finish sentence. |
| Success | The chosen look is visible as an example, not a paragraph; the result is shown next to the source. |

## J6 · Three references: identity + pose + style

| | Steps |
| --- | --- |
| Current | Choose a 3-reference recipe → Reference mode 3 → Pull from library (picker stays open and fills slots in order) → set roles → Generate. 5 clicks, 2 view switches (after fixes), ~560 words peak. |
| Desired | Board of numbered slots with role labels fixed by the recipe, drag or pick into slots, keyboard reorder, per-slot "use from / avoid" collapsed by default. |
| Success | Slot order and roles visible at a glance; a recipe change previews role reassignment and blocked extras before applying. |

## J7 · Review a batch and keep the winners (the missing daily loop)

| | Steps |
| --- | --- |
| Current | Library → *Review next (N unreviewed)* → asset dialog with queue strip → K / W / X / S, ← → → each decision saves then advances. Reason chips optional. Live: 1,188 unreviewed, 0 keepers. Runs & review and the Review desk use different decision words. |
| Desired | **Review mode** of the Library grid: large preview + filmstrip, K / W / X / S / ← → / 1-7 for reason chips, Z undo, group by run or recipe, "Review this run's 4 seeds" from a result strip. Bulk: select a group → one decision. |
| Success | 20 outputs reviewed in ≤ 25 keystrokes without the mouse; each decision confirmed visibly; undo last decision; the same four words everywhere. |

## J8 · Compare settings and keep a winner

| | Steps |
| --- | --- |
| Current | Create → *Plan comparison* → dialog (one setting, values, total graph runs, minutes) → Prepare plan → Runs & review → Start → wait → candidate cards (Choose / Keeper / Needs work) or *Open review desk* → Prepare review → crops, assessment, reveal, record decision. 4 clicks to prepare; the desk has no keyboard. |
| Desired | "Compare" from the run dock: pick a setting, see the candidates as columns with the budget ("3 runs · about 2 min") at the top → Start → one **Compare board** that shows candidates equally, with blind mode, synced zoom/crop, keyboard (←/→ select, K keep, 1-5 preference), and "Reveal settings" as the last step. |
| Success | Purpose of the screen stated in one line; budget visible before Start; Start and Record decision each explained when disabled; one decision vocabulary. |

## J9 · Continue from a keeper

| | Steps |
| --- | --- |
| Current | Output tile or asset → *Continue with this* → intent tabs Edit / Refine / Restyle / Combine / Animate / Make 3D → destination recipe → Prepare in Create. Also *Pull from library* inside Create. |
| Desired | The same verbs as buttons on every output tile and asset panel; each opens Make in that lens with lineage shown ("from Lantern study · seed 42"). |
| Success | ≤ 2 actions from keeper to a prepared draft; lineage visible on the resulting asset. |

## J10 · A run failed or its outcome is unknown

| | Steps |
| --- | --- |
| Current | Create → expand *Problems · N* → card with raw status, diagnosis, known prompt IDs, Resume observation, reason field + Stop tracking, Abandon (reason + acknowledgement), Put away / Bring back, Recipe download. Overview desk repeats the item with no action. |
| Desired | **Runs** timeline with a "Needs attention" filter. Failed: plain diagnosis + one suggested fix ("Try 768×768 or fewer adapters") + "Open as draft". Unknown outcome: a retained-receipt card: "We sent this but didn't see it finish. Check again" (observe only) · "Stop watching" (reason) · "Put away". Never "Retry". |
| Success | The user can tell failed from unknown at a glance; no action on an unknown outcome can resubmit; put-away is reversible and counted. |

## J11 · Brief in Prompt Lab → image in Create

| | Steps |
| --- | --- |
| Current | Prompt Lab (2,900 px page) → scroll past saved briefs and analysis → brief + profile + facets → auto-build → diagnostics → *Open Create with this prompt* → Create asks to choose a matching recipe. 4 clicks, ~700 words. |
| Desired | "Help me write this" panel inside Make: facets (subject, style, keep, avoid) compile against the **current recipe's** profile live; Apply writes into the brief with a preview diff. Full Prompt Lab page remains for saved briefs and reference analysis. |
| Success | No page switch; no locked button without reason; the compiled text is visibly what Generate will send. |

## J12 · Export a game asset

| | Steps |
| --- | --- |
| Current | Library → select frames → bulk bar *Create native export* → dialog (format, clip, anchors, filtering, loop, verify in Godot/Krita, per-frame order/duration/layer) → Prepare export → Runs & review → Start. |
| Desired | Export wizard from a selection or collection: format cards (Sprite atlas · Layered Krita · Godot project) → frame strip with drag reorder and durations → preview → Prepare → Start from the same panel. |
| Success | Frame order and canvas requirement visible before Prepare; output files and verification result shown on completion. |

## J13 · Missing model / wrong environment

| | Steps |
| --- | --- |
| Current | Create blocker "Missing requirements: …" or "Switch explicitly to <backend> in Models & setup" → fix button → Models & setup → download (SHA-256 verified) or Switch environment. |
| Desired | Blocker chip in the run dock → side panel listing exactly the missing files with size and "Download" or the environment with "Switch (about N s, stops nothing running)" — explicit, never automatic. |
| Success | Fix without losing the draft; switch refused with reason while work is active. |

## J14 · Reshape a workflow (expert)

| | Steps |
| --- | --- |
| Current | Guided workflows → Workflow builder → Load installed nodes → import recipe graph → edit in Nodes or Steps → Check connections → Save to Workspace → Prepare run ticket → Run prepared recipe (confirm). ~30 buttons, 604 words peak. |
| Desired | Setup › Workflow builder with a real canvas (pan/zoom, minimap), readable inspector with large text fields, one primary action per state (Check → Save → Prepare → Run). |
| Success | Every disabled step names its precondition; a changed graph cannot be run by accident. |

## Secondary (design last)

| Journey | Current | Note |
| --- | --- | --- |
| Assemble a scene from assets | Scene editor timeline | Owner: not needed now |
| Record a voice take | Voice takes form | Works; keep simple |
| Listen to a Spoken Brief | Separate page, own shell | Bring into the shell only |
| Organise with collections | Sidebar ＋, dialog | Recovery UI is heavy; keep it out of the default view |

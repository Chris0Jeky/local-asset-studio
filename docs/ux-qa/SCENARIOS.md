# Practical QA baseline and next-pass scenarios

Run against a frozen source identity with synthetic APIs first. Record expected result, observation, transport mode, source hash, mutations and evidence path. Retain failed checks. Then repeat selected journeys on the actual workstation only under explicit execution authority. No scenario in this file itself grants that authority.

**Status vocabulary:** `verified here` is limited to the stated fixture; `reproduced open` is an observed unresolved defect; `source/issue mapped` is inspection or tracked work, not a browser pass; `planned` has not been exercised here. Use `RESULTS.json` for the individual ASSET-01…30 observations.

## First session, source continuity and generation

| ID | Practical scenario and perturbation | Required outcome | Observation / owner |
|---|---|---|---|
| FLOW-01 | New user opens Studio with ComfyUI offline, then reconnects | Useful entry point, unknown/offline evidence, no generation or install; explicit recheck | source/issue mapped; #118/#169 |
| FLOW-02 | Start an illustration, type a long brief, explore another recipe, return | Preserve user intent and distinguish example text from authored text; disclose unsupported controls | planned; #16/#38; existing draft owner |
| FLOW-03 | Open a recent output, choose repair, inspect before Generate | Source identity, original intent, chosen repair and retained constraints remain visible; no inherited unrelated example | source/issue mapped; merged #164; continuation/browser tests already exist |
| FLOW-04 | Attach identity/pose/style; replace one slot; clear/reorder another | Preserve role and byte/transform provenance; release only replaced lineage; never silently drop a reference | source/issue mapped; #21; existing handoff contracts ran in full suite |
| FLOW-05 | Restore a setup after a required file is actually deleted | Name the missing slot, withhold readiness, explain restaging; no false parent claim | source/issue mapped; existing reference check and #117 |
| FLOW-06 | Restore while availability request fails, then Save setup without reattaching | Unknown must remain distinguishable from absent; durable lineage cannot claim an empty input | reproduced in prior issue, source mapped here; #117; not fixed by this PR |
| FLOW-07 | Change source/recipe while a helper, inspect or readiness request is delayed | Reject stale evidence and keep the new source/intent; no invisible rewrite | source/issue mapped; #118/#169, #38; broaden browser fault fixture next |
| FLOW-08 | Switch bundle/checkpoint or disable required accelerator | Show complete dependent change set and invalidated recommendations before consent | source/issue mapped; #144/#171; no duplicate substitution engine |
| FLOW-09 | Choose Wan long/default T2V after known decode-capacity failure | Explain admission hold before an expensive run; retain valid short option | source/issue mapped; #163/#180 and #181 |
| FLOW-10 | Prepare while jobs are busy; restart or lose POST response | Preserve known IDs and uncertainty; never infer permission to submit again from a UI timeout | source/issue mapped; #93/#94/#95/#110/#122; no runtime changes here |

## Review, organization and next use

| ID | Practical scenario and perturbation | Required outcome | Observation / owner |
|---|---|---|---|
| FLOW-11 | Write repair notes, edit review/tags/title, then Favorite | Favorite is independent; all edits survive; no implicit approval | verified here, ASSET-01/02/21 |
| FLOW-12 | Escape, Close, follow source lineage, or request a missing asset while dirty | Consistent leave/retain choice; missing target does not clear the current identity | verified here, ASSET-03/04/05/22 |
| FLOW-13 | Save, keep typing during slow response, then Continue | One click-time snapshot, preserved newer edits, clear dirty state, handoff held while saving | verified here, ASSET-06/08/09/10/23/24 and Node contracts |
| FLOW-14 | Save/Favorite/Trash returns error or Save times out | Error visible in the modal, retained draft, released controls, no automatic retry | verified here, ASSET-07/25/30; timeout/abort additionally in Node contracts |
| FLOW-15 | Request diagnostics, move A→B, A→B→A, close/reopen | Neither old success nor old failure changes the current panel; current failure remains retryable | verified here, ASSET-11/12/13/18/19/20; fixes #183 |
| FLOW-16 | Two clients edit from the same metadata snapshot | Stale same-field writes conflict without erasing confirmed edits | **implemented and verified in this continuation**, two clients, actual SQLite/metadata HTTP, local inert browser; #188 and METADATA-RESULTS.json |
| FLOW-17 | Refresh browser or crash while editing asset notes | Draft recovery is explicit, source-scoped and does not become a server revision | planned; open-session guard in this PR does not survive reload |
| FLOW-18 | Mark selected/rejected, then export or hand off | Review, art acceptance, licensing and execution remain separate; originals/recipes persist | source/issue mapped; #10/#16/#65; no live export/acceptance performed |
| FLOW-19 | Filter, select, Trash/restore, page through a large library | Stable selected IDs, recoverable originals and bounded media/DOM work | source/issue mapped; #177; no 10,000-asset benchmark here |

## Multi-stage work, accessibility and agent parity

| ID | Practical scenario and perturbation | Required outcome | Observation / owner |
|---|---|---|---|
| FLOW-20 | Repair a localized defect and compare against original | Show write vs protected scope, original/candidate crops, retained failed attempts and remaining budget | source/issue mapped; #66/#71/#72; no neural quality assessment here |
| FLOW-21 | Replace one voice line after timeline preview | Preserve exact words and line identity; invalidate affected cues/mix only; show stale preview | planned; #28/#30 |
| FLOW-22 | Send asset to scene, native editor or game engine and return | Clear native-only/unsupported losses, retained editable source, explicit actual application evidence | planned; #23/#24/#31/#32; no native app connection claimed |
| FLOW-23 | Guide navigation, source changed mid-step, failed evidence read | Step navigation is not task success; resolve current anchors, show unknown and owner decision | source/issue mapped; #118/#169; do not add a competing coach |
| FLOW-24 | Keyboard-only asset review, narrow viewport, reduced motion | Reach Save from Notes, see status and stay in dialog; previews leave form space | verified here within synthetic Chromium, ASSET-14/15/26/27/28/29 |
| FLOW-25 | Screen reader, actual 200% browser zoom, high contrast, native image/video/audio/3D | Named dialog, meaningful focus return, readable controls/errors, media lifecycle verified | planned; not established by narrow viewport checks or invalid-video placeholders |
| FLOW-26 | Human changes source/revision while an agent proposes an edit/run | Agent uses same owned commands, stale proposals conflict; no raw prompt bypass | source/issue mapped; #38/#120/#123/#188; no live agent/browser parity claim |

## Promotion gate for subsequent UX changes

A change is ready for review when a specific failed expectation becomes passing under the same fixture, existing source/lineage/queue constraints still pass, and limitations are recorded. Do not close an umbrella issue after a navigation-only or component-only proof. An owner-run accepted output is a separate later gate; record its actual model/runtime, source, costs, failures and review without retroactively reclassifying these synthetic tests.

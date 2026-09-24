# Live journey QA: 24 September 2026

A coordinator walked through the everyday Studio journeys on the owner's running Studio (main `b57466e8`, port 8191, ComfyUI 8188) in the built-in browser. The walkthrough was **read-only**: no Generate was pressed, and nothing was queued or restarted, because an agent lab session had the GPU. Review dialogs were opened but closed without saving. Text was read from the DOM; no picture was opened or judged (the library holds adult-lab outputs).

Viewports: 1440×900 (Focus and Immersive layouts) and 390×844.

## Journeys and what happened

| Journey | Result | Outcome |
| --- | --- | --- |
| Overview → *Start with an idea* → Create | Works. Recipe, prompt, readiness, *Expected: 28 s* and Generate all appear in the first viewport. | Generate dock verified on Focus, Immersive and mobile; #775 closed |
| Keyboard entry | The first focusable element is *Skip to workspace* (`#studioMain`) | #769 closed |
| Create on arrival | Showed a permanent banner: "A failure record was not saved for generate 60934d27… Inspect local storage and retained job records…" | Cause: `[WinError 5] Access is denied` replacing `state.json` while another process held it. Bounded retry + plain wording: #945 |
| Create → Problems | 19 problems going back to mid-September, including an abandoned job whose replacement already ran. The pre-submission file-lock failure showed a raw Python exception. | Friendlier classification in #945; reversible *put away*: #940 |
| Asset library | 1,205 assets, 1,184 unreviewed, 0 keepers. Almost all are agent-lab outputs, all titled `<recipe> · 1`, so the owner's own work can't be found by text | Run labels, source filter, prompt subtitles: #939 |
| Review next | Keyboard queue works (K/W/X/S, ←/→). *Leave queue* leaves the details dialog open, and the dialog shows no prompt text. | Prompt subtitle in #939; dialog close is a minor follow-up |
| Runs & review | "Your plans" mixes voice takes, scenes, exports and 12-day-old planned/uncertain comparisons, with no filter or archive | #940 part 3 |
| Overview → On your desk | The same stale items from 11–12 September, with no way to resolve them | #940 |
| Prompt Lab | Page status read **"StudioUX is not defined"** | Script-order race; fixed in #951 with a load-order test |
| Guided workflows | Loads; 64 visible controls, no duplicated visible labels | No action |
| Models & setup | Loads; inventory and free space shown. One card reads "PRESENT · PIN ONLY … Copy in by hand" | Minor wording, not filed |
| Tab title | Main page was titled "Local Asset Studio · Workflow Lab", an old name | #944 |

## Evidence-integrity finding

The lab's `CURRENT_STATE.md` headers carry clock times that come from neither receipts nor Git. p60–p70 say 25 September 00:20–04:30, but they were committed on 24 September 14:43–16:16. Tracked in #942; not edited while the lab's PR #937 is open.

## What this pass did not cover

- No generation, so readiness → submit → output → *Continue with this* was not exercised end to end.
- Screen-reader and native-keyboard acceptance (#539).
- The scene editor, voice and Spoken Briefs pages.
- Owner usability judgement. Agents record friction; the owner's verdict (HUMAN_TODO q-7) is separate.

# Recovery fixture: wait for the queued close handoff

## Retained failure

On Library head `777082d51e6236fb87d194f1a607a4d9dee230b5`,
[Ubuntu shelf job 121731576713](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40368213797/job/121731576713)
passed `SHELF-CONFLICT-01`, then timed out waiting for the hidden
`#openAssetRecoveryShelfDetails`. Windows on that head passed. Neither fact
turns the failed Ubuntu result into a pass.

The fixture sent Escape, navigated to the retained-draft opener with native Tab,
sent Enter, then tried the detail shelf button. Native dialog closure queues a
`close` event; the shipped shelf close listener returns focus to its launcher.
That event can run between the fixture observing its keyboard target and sending
Enter. The result is reopening the shelf instead of opening the editor. The
fixture's existing `restore_record` path already waits for the corresponding
queued close handoff, but this occupied-session-conflict path did not.

## Controlled causal check

A disposable native Chromium page loaded the exact shipped shelf close listener
and the exact fixture `tab_to` / `activate` functions. A test-only gate intercepted
the native close event and released an equivalent close event to the unchanged
listener at the adverse boundary. Dialogs, focus movement, Tab and Enter were
native browser behavior; no wall-clock delay or repeated random run selected the
outcome.

| Original sequence | Focus | Editor | Shelf |
| --- | --- | --- | --- |
| Fixture observes retained-draft target | retained-draft opener | closed | closed |
| Queued shipped close listener runs | library shelf opener | closed | closed |
| Fixture sends Enter | shelf Close button | closed | open |

The original sequence fails the intended-editor assertion. The corrected fixture
waits for the queued close event and closed dialog before beginning the next
keyboard activation; the identical adversarial schedule then opens the editor
and leaves the shelf closed. A subsequent editor-open condition precedes using
its shelf launcher. Both observations and complete local logs are retained.

This is a focused event-order proof on a small synthetic page, not a new execution
of the full Studio/SQLite/IndexedDB journey. The restored local source is incomplete;
fresh exact-head hosted Linux/Windows shelf qualification remains required.

## Bounded correction and identity

Only `tests/asset_recovery_shelf_browser.py` changes: one close-event helper and
its use at the affected transition, followed by the editor-open condition.
Production code, the original 54 journey assertions, the 14 transaction-owner
checks, browser deadlines, requests and storage semantics are unchanged. Reversing
those two edits reconstructs the original fixture byte-for-byte.

- Original fixture Git blob: `4643f2aaba321eaadfaa3441738d2463ee58d748` on both
  recovery head `fd15295b01bd2a3d51fac8fa487ce811a7f71875` and Library head `777082d…`.
- Original fixture SHA-256: `7a520b1c6e2118e267bdf88fbc044bfbf680cdcb0812128b6d3797564130591b`.
- Corrected fixture Git blob: `0a444045c5f5586a1a90fb5f069fa62b8b1f1fa1`.
- Corrected fixture SHA-256: `28f98abf54cbcb28e6b35579508d8e4ef1ac9d04ed53bf73654eed69f1b20065`.
- Unchanged shelf UI Git blob: `772076539a05b51e82707e97a556e9f21599b86c`.
- Local runtime: Python 3.12.14, Playwright 1.56, Chromium 141. Hosted Playwright
  1.57 remains a separate qualification.

The retained local bundle is `final-fixes/shelf/`: `probe_dialog_order.py`,
`evidence/close-order-before.json`, `evidence/close-order-after.json`, complete
before/after logs, and `evidence/source-identity.json`. The first sandboxed browser
launch was blocked at local socket initialization and is not a test result; the
scoped native runs produced the red/green observations above.

This correction does not close #393's broader keyboard and assistive-technology
acceptance. It removes a demonstrated test-driver sequencing assumption.

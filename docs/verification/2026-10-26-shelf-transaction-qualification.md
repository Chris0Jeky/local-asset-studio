# Shelf transaction qualification — 26 October 2026

Refs #825 and #392. This replaces the current local shelf's unsafe storage
boundary while preserving its bundle format, bounds, exact command bodies and
optional relationship to the session journal. It adds no server metadata writer,
automatic replay, model action or owner acceptance decision.

## Confirmed failure and cause

The owner had closed #825 on 16 October with instructions to reopen it if the
native assertion recurred with retained writer outcomes. It recurred on Library
PR #1660 head `12ff76929dea86b847a17382632368d87a051f3f`,
[run 40357121775, Ubuntu job 121692469089](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357121775/job/121692469089).
Windows passed on that same candidate. Artifact 12667150927, SHA-256
`cd6f79633be54881de762082adaea5a2b6977b750e908f9ab0785a75075718a8`,
records both tabs returning `written: true`: generation 4 became generation 5,
six records remained, and only Tab B's viewpoint survived. There were no browser
JavaScript errors. This proves a two-success overwrite; it is not a timeout or
an inference from a Boolean assertion alone.

The first controlled local native race reproduced it on unchanged shelf SHA-256
`8a18dc2f80bac6cd3974bf7788b455e9d7f322ca519f6ffc37ac2617df778441`.
Chromium trace marks identified separate renderer processes 163261 and 163289.
Both contenders queued the same exclusive origin Web Lock. A exited its callback
at 29.1 ms; B entered at 29.6 ms but read the old generation at 29.7 and 34.2 ms,
wrote its own generation 5 at 34.3 ms, and received A's storage event only at
35.4 ms. The lock serialized correctly. Renderer-local storage visibility did not.

This matches the boundary documented by the
[HTML storage specification](https://html.spec.whatwg.org/multipage/webstorage.html)
and Chromium's
[cached-storage implementation](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/modules/storage/README.md).
A delay or repeated localStorage read cannot establish an atomic storage
guarantee. The retained original failure and all local probes remain separate
from subsequent passing evidence; #825 was reopened according to the owner's
[recorded instruction](https://github.com/Chris0Jeky/local-asset-studio/issues/825).

## Delivered correction

One IndexedDB entry is now the sole current shelf owner. Its value contains a
version, the exact existing bundle string and a digest of the preserved older
localStorage copy. Decode, hashing and candidate construction happen before the
transaction. A readwrite transaction compares the complete observed entry and
queues its replacement in the same request callback, verifies readback, and
reports success only after transaction completion. The
[IndexedDB transaction lifecycle](https://w3c.github.io/IndexedDB/#transaction-lifecycle)
is the atomic boundary; cooperative Web Locks remain bounded coordination.

The native reader uses `getAll(key, 1)` to distinguish absent `[]` from malformed
present `[null]` or `[undefined]`. Corrupt/future entries refuse use without repair
or overwrite. An initialized empty bundle remains an entry, preventing legacy
records from reappearing after explicit discard of the final current record.
There is no unlocked or localStorage write fallback.

Legacy inspection remains read-only. The first explicit mutation or enabled
checkpoint can copy a strictly validated bounded legacy snapshot into the current
owner. Original bytes stay unchanged and separately exportable. Observed legacy
divergence pauses shelf-dependent writes and offers both raw exports. A confirmed
acknowledgement is bound to the inspected current entry and legacy digest; only
compatibility metadata changes. Newer current state or a newer visible legacy
copy refuses that acknowledgement. Another old-tab write pauses checkpoints again.

Older code can continue writing its preserved legacy copy until closed or
reloaded. It cannot overwrite the new current owner. Detection occurs when that
legacy change becomes visible; no immediate coherence across the two storage
APIs is claimed. Neither copy is automatically merged or deleted.

## Exact source and executed evidence

The production correction was independently reviewed at local `dc8e9f4`, after
the coordinator's UI changes and a first core candidate `357983c`. These are
local integration identities; the coordinator owns authoritative GitHub heads,
stack reconciliation and final merge verification.

| File | Qualified SHA-256 |
| --- | --- |
| `app/static/asset-recovery-shelf.js` | `f9cb3904ef35628979c073e8a1b18e283efb976b239745a116689ac59003a5a7` |
| `app/static/asset-recovery-shelf-ui.js` | `2dc0c6cb021999b82f5d394443632004088d46459ba793d11985cce8c815b2aa` |
| `app/static/asset-recovery.js` | `244e884a3963929466ffbe8fd74e3de2a11defac6af960586b9a13b36c27bea0` |
| `tests/asset_recovery_shelf_owner_browser.py` | `5bc789d8438c6500dc5c6c3b2b9470d8161bd10e6fd2e70dbc01dd1d7feef72c` |
| UI fixture used for the 54-check native run | `e4f1f6cf2de066c1fd8575d55ad0d425e0bd26e908e957c8706c54413ff3682e` |
| Shared native/inert owner helper | `9edc97f321fbbee5286df4c47b9ba368c940bd06c61a213c374b09d04744d8a4` |

### Causal and component contracts

The new owner contract set initially produced **14 expected failures** on the old
implementation. Independent review then reproduced malformed null/undefined entry
overwrite and an acknowledgement token offered for corrupt current bytes with
legacy divergence. Actual native IndexedDB probes failed on `357983c` and passed
on `dc8e9f4`; absent and initialized-empty controls remained explicit.

One additional captured-legacy race was found during implementation: a second
read could hash bytes different from the inspected migration snapshot. Its
causal test failed before the digest was bound to the captured bytes and passed
afterward. The full focused component command passed **73/73**: 18 owner, nine
UI and 46 existing codec/session/checkpoint/restore contracts. The coordinator
also ran the normal Python wrapper on the actual recovery parent successfully.

The UI's first seven new contracts failed before its integration. A later native
focus probe reproduced focus falling to the document body when acknowledgement
hid its own control. The corrected UI conditionally returns focus to visible
Refresh while preserving newer user focus; its nine contracts and independent
native probe passed. Corrupt reads now report an unavailable count instead of an
apparently empty shelf.

### Focused native transaction gate

```console
python tests/asset_recovery_shelf_owner_browser.py --out .runtime/shelf-owner-transaction-qualified
```

Result: **14/14 passed**, zero JavaScript exceptions, Chromium 141.0.7390.37 via
local Playwright 1.56.0. The receipt embeds the three relevant source hashes
above. Its raw trace confirms renderer processes 203171 and 203194 on the same
loopback origin; one fixture document uses cross-origin isolation to require a
separate renderer while preserving the shared origin/storage bucket.

The gate proves one actual stored winner under queued native Web Locks. Separate
controlled lanes prepare two candidates from the same observed snapshot, omit
cooperative lock scheduling explicitly in the fixture, and exercise the real
IndexedDB comparison for initialization, append, discard and capacity. They
assert both API outcomes and the exact complete stored record set, including the
nineteen prior records at capacity. This is not a replacement CAS implementation.

Native quota and abort injections cover initial creation and replacement. The
existing journal's real dispatch gate retains its exact bytes and sends zero
dependent POSTs. Unavailable IndexedDB and a genuinely blocked open also refuse.
A subsequent upgrade/abort probe verifies that a timed-out open left no live
database handle. Legacy inspection and final-record discard demonstrate that an
initialized empty owner cannot resurrect the preserved older snapshot.

### Native UI and explicit fallback

At fixture commit `69d70a2`,
`python tests/asset_recovery_shelf_browser.py --out .runtime/shelf-owner-ui-native-final`
passed **54/54**, zero JavaScript exceptions, on the exact production hashes
above. It uses shipped UI, temporary HTTP/SQLite, native IndexedDB, WebCrypto and
Web Locks. Existing import, reload, exact retry, GET-only recovery, native
browser-owned zoom, capacity and quota checks remain. The CAS assertion now also
requires the persisted generation/digest/text to match the sole reported winner.

Its new quarantine journey downloads current and older bundles byte-for-byte,
reaches the actions by keyboard at 390px without horizontal overflow, confirms an
acknowledgement that changes only compatibility metadata, and observes a later
old-tab write quarantine again. The screenshot was inspected: both exports and
the focused Continue action remain visible and wrapped appropriately.

The initial run reached that acknowledgement but its fixture expected a different
confirmation phrase. The existing UI says “Nothing will be merged or deleted.”;
only the assertion's expected literal changed. No product change, assertion
meaning or timeout was relaxed to obtain the 54-check pass.

The explicit inert fallback subsequently passed **46/46**, zero JavaScript
exceptions. Its Storage shim first lacked `clear()`, which was added to match the
standard API. It then exposed a final-checkpoint observation race: the captured
status was “Saving local recovery on this device…” until the editor's scheduled
checkpoint settled. The shared fixture now awaits the existing `session.flush()`
and requires its actual capacity refusal while retaining exact bytes, 20 records,
newer typing and zero POST assertions. The before/after statuses are retained in
the receipt. That final fixture SHA-256 is
`7a520b1c6e2118e267bdf88fbc044bfbf680cdcb0812128b6d3797564130591b`;
the 54-check native result is not relabeled as a local rerun of this later
settlement assertion. Exact-head hosted CI qualifies the final shared fixture.

The lifecycle inert adapter passed **19/19**. Its subsequently corrected empty
`jobs` fixture mapping removes an observed unrelated family-read server traceback;
it is not a product fix. Inert storage/crypto/transport substitutions are component
evidence, not native persistence or browser-origin proof.

The first focused native fault fixture also correctly refused its synthetic
journal setup because canonical bundle key ordering differed from body ordering.
The fixture now rebuilds only the in-memory command from its unchanged wire body,
as the existing shelf restore bridge already does. The original five race passes
and setup failure remain recorded separately from the complete 14-check result.

## Gates and limits

The read-only shelf workflow now checks out/logs the exact PR head, runs the
focused native owner gate on Ubuntu 24.04 and Windows, and retains its receipt and
trace inside the existing artifact subtree. Linux uses the separately reviewed
bounded Chromium dependency helper with a four-minute step; Windows retains its
existing install command and the job remains limited to 15 minutes. Shared helper
paths trigger the shelf, lifecycle and refusal workflows. Full exact-head hosted
qualification and merge reconciliation remain with the coordinator; local
results do not imply those hosted gates have finished.

Raw synthetic evidence remains under ignored `.runtime/`: original
`shelf-cas-trace-baseline`, initial corrected `shelf-cas-trace-owner`, final
`shelf-owner-transaction-qualified`, `shelf-owner-ui-native-final`, and
`shelf-owner-ui-inert-qualified`. Independent native corruption/focus evidence is
retained in the coordinator's browser-fixture review workspace. Earlier failed
and partially completed runs are not overwritten or counted as completed passes.

No OS crash/power-loss campaign, browser-menu interaction or screen-reader session
is claimed. #392/#393 broader accessibility acceptance remains explicit, and
`HUMAN_TODO.md` art, model/runtime and publication choices remain owner decisions.

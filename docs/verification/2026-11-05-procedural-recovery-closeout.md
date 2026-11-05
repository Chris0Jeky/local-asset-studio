# Procedural tools and native-data recovery — 5 November 2026

This record distinguishes software qualification, native runtime execution and
owner art acceptance. The work started from GitHub main
`c07dfc216e700002fd4aa54b5f874d5c109d1fa5`, tree
`6a7f707917017ae403f5af776fb6cc1d800b6b6e`. The uploaded source archive was reconciled
against all 4,894 tracked blobs before editing. Five Windows-script line endings
were restored to the authoritative GitHub bytes; no source changes were inferred
from the archive. GitHub had zero open pull requests and 149 open issues at intake.

## Recovered capability

The inspected main contained eight standalone procedural generators, with no
`procgen` integration in `app/`: `room_kit`, `prop`, `shrine`, `lighthouse_room`,
`pier`, `coastal_path`, `tide_pools` and `market_street`. It also contained separate
level assembly, labelled-dataset and toon spring/gait tools. The search did not
find a dormant fluid, cloth, particle or boid simulation family; this is a finding
about the inspected source, not proof that no earlier branch ever contained one.

[#2021](https://github.com/Chris0Jeky/local-asset-studio/issues/2021) bounds the
software integration: expose the existing schema, preserve explicit preparation
and Start, use the shared Production queue and lease, retain uncertain work, and
publish checked results to the Library. The implementation and API contract are
described in [Procedural assets](../PROCEDURAL-ASSETS.md).

## Qualified component records

| PR | Reviewed head | Tested tree | Actual main merge | Hosted evidence |
| --- | --- | --- | --- | --- |
| [#2022](https://github.com/Chris0Jeky/local-asset-studio/pull/2022), triangle reporting | `de98c919472514cada46e0e455bb92e6f65774ce` | `87f7e7039f81e6b0ac87c1a68e646c858e1085f5` | `a11d0f0d48a987f917ac0956ccaf40d7490e098c` | [Check studio 42079878794](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42079878794): 7,221 tests, 113 skipped, zero failures/errors; 98 graphs, 194 pins, 4,894 paths. All three applicable workflows passed. |
| [#2023](https://github.com/Chris0Jeky/local-asset-studio/pull/2023), corpus material retention | `45f89699a11d01729b8a47781799ce4f329a84c8` | `88abe0327420641702b0a1183be60029dc81f1fb` | `216b1368fd210d0fe45a713ef25d3f2ec29b85cd` | [Check studio 42081028774](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42081028774): 7,226 tests, 114 skipped, zero failures/errors; 98 graphs, 194 pins, 4,896 paths. All three applicable workflows passed. |
| [#2024](https://github.com/Chris0Jeky/local-asset-studio/pull/2024), shared-material position maps | `cb30ddfeb7e0454ac243a03604a6a5c773b66045` | `474a591ca5fcf216b42defac5d351eab68ac09d1` | `706c199cb1322b9d31225f611db14f0d70961978` | [Check studio 42081349472](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42081349472): 7,229 tests, 117 skipped, zero failures/errors; 98 graphs, 194 pins, 4,898 paths. All four applicable workflows passed. |
| [#2027](https://github.com/Chris0Jeky/local-asset-studio/pull/2027), spring settings and centers | `59912e3b37cd53be6dffb21822696c91d96b23c8` | `92a5ad4053803bb98428b7ab3070ddf63198158f` | `dd20e5c663701263f795124148886ba30b3a3d30` | [Check studio 42085224834](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085224834): 7,235 tests, 118 skipped, zero failures/errors; 98 graphs, 194 pins, 4,901 paths. All four applicable workflows passed, including the native engine probe. |
| [#2025](https://github.com/Chris0Jeky/local-asset-studio/pull/2025), Studio procedural integration | `b2292a43c38d85aae54b0a37912bb8e60ffb5712` | `cdfd2ce96892bb1333b88b783967d37a3cd97272` | `28cc3f39679fd5621da4d9fa6e896ea9af02f3a0` | [Check studio 42085746767](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085746767): 7,264 tests, 118 skipped, zero failures/errors; 98 graphs, 194 pins, 4,913 paths. All 29 applicable workflow identities have a successful exact-head run; the failed duplicate fixture run is retained below. |
| [#2028](https://github.com/Chris0Jeky/local-asset-studio/pull/2028), browser synchronization and setup | `e6808973110a17159411fcb78c102d1344b3dd83` | `5bd12e764f55c403a966e58725a23f20a6e9bb18` | `2414928245a6a4f72152a4d9575b7070010b7a75` | [Check studio 42089170398](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42089170398): 7,270 tests, 118 skipped, zero failures/errors; 98 graphs, 194 pins, 4,913 paths. All seven applicable workflows passed. |
| [#2030](https://github.com/Chris0Jeky/local-asset-studio/pull/2030), Library scope and filter readability | `be37e73bd7a9e787947d67c681b3d9e8d5ed6f3e` | `c40f63b261dec75d26d9ef17bcf0998a7d8bf63e` | `f9e4187e9062553ca35f4b8eb9d099838457a604` | [Check studio 42092084866](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42092084866): 7,270 tests, 118 skipped, zero failures/errors; 98 graphs, 194 pins, 4,913 paths. All 11 applicable workflows passed. |

The full-suite logs record clean lifetime shutdown. The tested synthetic merge
checkouts were `8f019ac070c333fcb69c633c4fdc70085bdfc104` for #2022 and
`2587dd85ba988b937abb9135d00d63b8c7da8d50` for #2023. Their trees equal the
reviewed branches and actual main merges above. Duplicate #2023 runs cancelled
while its stack was assembled are retained; the successful combined-tree run is
the qualification, not a cancelled attempt. Independent source reviews found no
actionable findings in these slices. The position-map full-suite checkout was
`eb3857e31f3861797088f4bc961066d7a03e3f35`, with the same tree as its actual merge.
The optional NumPy dependency causes three position-map skips in the generic full
suite; [dedicated run 42081350166](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42081350166)
installed NumPy and ran all three cases without skips on both Linux and Windows.
The spring full-suite checkout was `594cdd7d824d7dc6e1c2ff3eddde3f007bfc89aa`;
the integration full-suite checkout was `ebc5cdb21b39c656049a63c8618ee6059d2a76b4`.
Each resolves to the tested tree and actual merge listed above. The two bounded
acceptance issues, #1928 and #2021, were checked open before merge and closed
afterward. #2026 explicitly retains native generator qualification.
The browser full-suite checkout was `81cd6ca1d25a63f3daa717cf17ac001915981142`,
with the same tree as its actual merge. Issues #1952 and #1987 were checked open
before merge and closed afterward. No unresolved GitHub review threads remained.
The final Library full-suite checkout was
`15b0337f2f8a9d10edee688af9f55ccbc1c8adb6`, whose tree equals the reviewed head
and actual code merge above. #2029 was verified open before merge and closed
afterward; #2009 remains open with a progress comment for this bounded correction.

## Findings retained from qualification

The first independent review of the Procedural assets integration found two
reproducible defects at tree `0f0aa24487261cecc72a461b8404a69f55ac52f5`: a later
Library-registration failure erased known published identities and permanently
refused recovery, and failed setup refresh followed by success reset typed fields
to defaults. The reviewer reproduced the first with actual SQLite and the second
with the shipped JavaScript handlers. Both were accepted for correction before
merge; the initial passing component tests did not cover them.

The corrections were independently re-reviewed at local commit
`9d191c494e3722670f6b64a477029cc304a43e35`, tree
`a90e71a9beec2619fb6785dce17fd34ceeba1122`. All 29 procedural tests passed with no
skips. Three actual-SQLite cases now cover later-output insertion failure, a final
receipt barrier failing after publication, and lost receipt evidence followed by
changed-output refusal, restart and reconciliation. Known asset identities remain
in uncertain jobs; recovery validates native evidence again and registers remaining
outputs idempotently. Native failure markers remain terminal. The page captures
draft parameters before requesting setup state, so repeated failed reads no longer
discard edits. The reviewer approved both corrections without further findings.

The initial [UX run 42083391579](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42083391579)
passed all 29 new procedural browser checks at head
`3faa1014f7fa5e280cced8ee748e7948e1e4736a`. Its artifact
`13441488256`, SHA-256
`943dfb5e46fd18b3c66bbe1b99259026a980ee2b53ad52804678b1768a6ac9c3`, was downloaded
and its five procedural screenshots inspected. The desktop form, plan and
completed-state layouts were readable. The phone full-page captures retained the
current scroll position, placing fixed shell elements inside the long screenshot;
fresh captures must reset scroll before the final visual check. Flat fixture
images and an empty synthetic model pane do not establish native rendering.

The final [UX run 42085747774](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085747774)
passed all 29 procedural checks, the existing 31 use cases and 295 pose assertions.
Checkout `ebc5cdb21b39c656049a63c8618ee6059d2a76b4` resolves to the published
combined tree `cdfd2ce96892bb1333b88b783967d37a3cd97272`. Artifact `13443401979`
was downloaded and verified against SHA-256
`5b3cd5bc06bc9d6dbe84daef542c2660865af2f892fd03c2ba15999aa41cd3ea`. All six
screenshots were inspected: missing-runtime desktop form, desktop planned and
completed states, phone settings and prepared states, and a 390-by-844 viewport
capture. Resetting scroll and waiting for layout corrected the earlier capture
defect. Controls and headings fit without horizontal clipping; the fixed shell
stays at the top. The synthetic media limitation still applies.

The same initial head failed the Windows Parallax browser reload in
[run 42083391788, job 127442021499](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42083391788/job/127442021499).
The 1440px journey passed; the 390px reload timed out waiting for startup, with
six missing `$` and two missing `esc` page errors. The artifact
`13441348046` was downloaded and verified against SHA-256
`0980313705390b9cd071faca2e2800e64a3e4f238a9f8180efc3d343b2f18ded`.
The fixture's aborted JSON writes during navigation do not by themselves prove
the cause of the missing script globals. Linux passed the same journey. This
failure remains evidence and is not reclassified as a passing check.

The browser follow-up adds bounded, async-safe request/startup/server diagnostics
to that fixture. Independent review and seven diagnostic plus two Parallax
contract tests passed. The change preserves every readiness wait and assertion;
it does not claim to resolve the historical loader symptom in #1901 or prove a
production transport defect under #1029.

One duplicate Spoken Brief run at the combined integration head failed in
[run 42085746175, Ubuntu job 127450232108](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085746175/job/127450232108):
the fixture joined a worker after publication but before thread startup. Its
corresponding same-head run `42085746132` passed, as did Windows. The production
manager publishes and starts the worker under its lock; the fixture read the
dictionary without that lock and could match stale uncertain status before a
recovery response. This concrete fixture failure is retained alongside the
passing run; the bounded correction is part of #2028.

The fixture correction was reproduced through actual HTTP recovery while holding
`Thread.start` at the worker-publication boundary. The old wait raised the same
`cannot join thread before it is started` exception. The replacement snapshots
workers under the lifecycle lock, joins outside that lock so cleanup can finish,
and rechecks the registry under one five-second monotonic deadline. The browser
case also awaits the actual recovery POST's HTTP 202 response before observing
its result. Existing uncertainty, no-replacement, disabled-playback and page-error
assertions remain. Independent review approved local commit
`6e1a2a4bab35c18483cca024f866b96dce99ad59`, tree
`aa5430fa7f76db217acfb644cc0bfec638ff41bc`, and separately ran all 26 narration
contracts without skips. No production narration change was needed.

## Spring settings and native engine evidence

[#2027](https://github.com/Chris0Jeky/local-asset-studio/pull/2027) carries ordered
per-joint settings, gravity direction and the authored motion center into the
Godot proof. Regenerate existing sidecars from the source VRM with
`python scripts/vrm_toon.py springs MODEL.vrm OUT.json`. Missing/ambiguous imported
names and sparse chains are refused explicitly; a uniform approximation is no
longer substituted for missing per-joint data. The binding updates center space
before the simulator and converts authored world gravity into that space.

Independent review found a callback signature error in the initial revision:
Godot exposes `_process_modification_with_delta(delta)`, while the deprecated
`_process_modification()` has no argument. The first native Linux run
`42085011282`, job `127447635260`, independently failed on that exact compile
error. Renaming the callback and its initial call corrected the cause; no test
assertion was removed.

Corrected head `59912e3b37cd53be6dffb21822696c91d96b23c8`, tree
`92a5ad4053803bb98428b7ab3070ddf63198158f`, passed the actual Godot 4.5 probe on
both platforms in [run 42085224621](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085224621).
Linux job `127448385378` and Windows job `127448384663` ran the native test without
skips. Tested checkout `594cdd7d824d7dc6e1c2ff3eddde3f007bfc89aa` has that same
tree. Its required 16 cases cover production binding, independent/deferred joint
settings, rotated world gravity, zero gravity, bone/node/world centers, legacy
sidecars and invalid bone/center/collider/chain mappings. The full native lane also
passed its existing 36 evidence, five live-engine and 32 toon tests on each host.

Both native artifacts were downloaded, hash checked and their spring result
receipts inspected: Linux artifact `13442424387`, SHA-256
`90bd6c0e4812826d6406aec37bb30db7322bb05740215ccf292d3fe663bbb4aa`; Windows artifact
`13441029345`, SHA-256
`3fc4c261098f1f09242d032e0f264880ef4ebf28205a01f3688e7eaae2fb36cb`.
Each receipt contains all 16 cases as true and an empty failure list. Both record
zero joint-angle change for the bone/node center cases and about 1.209 radians for
the world-center case, after actual simulator steps. This distinguishes observed
center-relative behavior from configuration getter checks alone.

Independent review checked the pinned engine source for callback signatures,
modifier order, deferred joint updates and coordinate transforms, and approved
the corrected slice. These synthetic native tests do not establish a new avatar
render or physical/visual parity on Godot 4.7.2.

## Browser setup and retained capture evidence

The first browser-reliability candidate, head
`d59780df1ebd9ee0f96d2edb28f80e2cdaf24636`, tree
`edd23ba551fefb8ae8964b5c5e860170829c6cf2`, passed its actual Archive and privacy
journeys on Linux and Windows. Windows privacy job `127450701204` in
[run 42085877565](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085877565)
had a cold cache for `playwright-Windows-X64-1.57.0-chromium-shell-v1`. Its mandatory
headless Chromium installation completed in about 125 seconds, within the new
six-minute step budget, and the subsequent browser tests passed. The cache is an
optimization; an unconditional successful install remains required. This single
run does not measure a long-term flake-rate improvement.

The [Archive run 42085877534](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42085877534)
checked out that exact head and tree on both hosts. The Windows artifact
`13443122417` was downloaded and verified against SHA-256
`6ba56d6d2163fc052e3bd8e897ab40c172dd16405b036d2852902cbf69cabde3`.
Its receipt records all 28 checks passing, no page/server errors and no client
disconnects. Both screenshots were inspected. The filter and cards fit at 390px,
but focus had scrolled the page before full-page capture, placing the fixed shell
inside the long image and obscuring the introduction. This is retained as a
capture defect, not evidence of a production CSS regression.

The follow-up resets scroll and waits for two layout frames after the unchanged
focus/overflow assertions, then captures both the full page and a phone viewport.
Independent review approved local commit `db7dae191c8df2a1d4004179025cdc368f4ac578`,
published as head `e6808973110a17159411fcb78c102d1344b3dd83`, tree
`5bd12e764f55c403a966e58725a23f20a6e9bb18`. Final hosted receipts and visual
inspection are recorded at documentation closeout below.

Final [Spoken Brief run 42089170357](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42089170357)
passed all 26 narration contracts and all 25 browser tests on Linux and Windows,
including the previously failing lost-create/recovery case. Both jobs checked out
`81cd6ca1d25a63f3daa717cf17ac001915981142`, which resolves to the final candidate
tree above. The [Archive run 42089170124](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42089170124)
also passed on both hosts. Its Linux artifact `13443259829`, SHA-256
`a201ce0655848dc0e3447342f57b97ddf8126c43e454a8c67e12721e7153f613`, and Windows
artifact `13443354723`, SHA-256
`bf8fbc7602745981e1e94a8f7ba7eeedeb3c91b5c3007910a4b5427208d141d0`, were
downloaded and verified. Each receipt has all 28 checks passing and no page/server
errors. All six desktop/phone full-page and viewport captures were inspected:
the shell now stays at the top and the introduction is visible. The inspected
Linux desktop still showed mid-word scope-label wrapping and a clipped selected
filter label; that separate existing CSS defect was recorded in #2029 and is
addressed by #2030 below.

Final Windows privacy job `127463078670` in
[run 42089170429](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42089170429)
restored the exact versioned cache and still ran the mandatory installer. Its
Media Foundation dependency step took about 203 seconds, within the six-minute
limit, and all subsequent browser journeys passed. The cache avoids repeating
the browser download; it does not remove required Windows dependency work.

## Library labels and selected filters

[#2030](https://github.com/Chris0Jeky/local-asset-studio/pull/2030) lets scope counts
wrap below whole label words and gives fixed-choice toolbar selects their native
intrinsic widths. The change is confined to the Library selectors in
`app/static/asset-review.css` and the existing Archive browser fixture. Page-scoped
counts, collection-name handling, filtering and command behavior remain intact.
Independent review approved local commit
`d7aaede6fad4cb1537dd9985113fed9210c1ad07`, published as head
`be37e73bd7a9e787947d67c681b3d9e8d5ed6f3e`, tree
`c40f63b261dec75d26d9ef17bcf0998a7d8bf63e`. The existing frontend contract,
Python/embedded-JavaScript parsing and repository validation passed locally.

The [Archive run 42092085240](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42092085240)
checked out that exact head and tree on both hosts. Linux job `127472468391` and
Windows job `127472468414` each passed all 39 checks, with empty page/server-error
lists. The original 27 check call expressions remain; the prior two-width loop
produced 28 checks. The expanded three-width loop and new word/filter measurements
produce 39. All selected filters fit at 1440, 768 and 390 pixels, and ordinary
scope words remain on one line without removing the "on this page" count scope.
The Archive filter measured 166 pixels wide on Linux and 151 on Windows, matching
each host's required native width at all three viewport sizes.

Both artifacts were downloaded and hash checked: Linux `13446645052`, SHA-256
`dcc827067eac920c4a2ea349594f941668cc4c7f76492ee082fe2655bad8acb7`; Windows
`13446415597`, SHA-256
`59dda2d3ab0bc525e197317bddc1e62e2f68d291f80e4d78fddd0189ba4deb20`. The receipts'
source and stylesheet hashes match the reviewed code. All eight images were
inspected: desktop, tablet and phone full-page captures plus a phone viewport per
host. Favorites remains intact, Active & archived is fully visible, and the shell
stays at the top. This is bounded readability evidence with synthetic Library
assets; #2009's broader UI findings remain open.

## Local evidence and limitations

- Focused procedural adapter, actual HTTP/SQLite, frontend, Production/storage,
  corpus and position-map suites were run against their named component trees.
  Full hosted receipts, rather than an aggregate of component counts, qualify the
  combined code.
- The initial unmodified local full-suite run reported 7,145 tests, 80 errors and
  74 skips. Missing `psutil` accounted for many errors. Installing the repository's
  pinned dependency allowed the relevant Blender and benchmark suites to run.
  The managed host also could not inspect its own PID through `psutil`; correct
  backend-suite invocations still failed process-ownership checks for that reason.
  Those guards were not weakened.
- An attempted targeted rerun through a stdin Python loader was invalid for
  multiprocessing spawn and is not repository qualification. The integration
  author's full-suite attempt was stopped after the same process-visibility
  limitation was established. Neither local full run is reported as a pass.
- Local browser downloads were unavailable. Actual browser execution and visual
  checks use hosted artifacts. Browser fixtures use synthetic local data and
  native-output substitutes; they do not establish generated-geometry quality.
- Blender and Godot were not available in this development container. An opt-in
  native Blender probe being present in the repository does not mean it ran.

## Remaining acceptance

- [#2026](https://github.com/Chris0Jeky/local-asset-studio/issues/2026): run the new
  Studio path on the configured Blender 5.4/Godot workstation for all eight
  generators, retain exact source/output identities, inspect the models and
  exercise interrupted publication recovery. No model or native build was
  submitted on the owner's workstation during this session.
- [#1983](https://github.com/Chris0Jeky/local-asset-studio/issues/1983): run the
  material-retention save/reopen/repair probe, regenerate affected realistic-v2
  corpus variants and rerun the relevant benchmark cases. Old variants and
  historical rates stay unchanged. The original issue diagnosis was corrected:
  blanket fake-user retention promoted unused materials; the implementation
  already selected an existing alternate.
- [#1948](https://github.com/Chris0Jeky/local-asset-studio/issues/1948): smooth
  shading and exported-normal qualification remain separate from triangle counts.
- Level assembly, labelled datasets and dedicated SDK/MCP wrappers remain separate
  integration work under #15/#25. The generator page does not imply their delivery.
- The paused illustration wave in #1923, parallax usability review and island
  default-switch decision remain as recorded in `HUMAN_TODO.md`. Engineering
  qualification does not answer those creative or product choices.

## Documentation closeout

All seven code PRs above are merged, and the six bounded issues #1949, #1928,
#2021, #1952, #1987 and #2029 are closed. The final combined full suite finished at
**2026-11-05 19:31:12 UTC** in job `127472467030`: **7,270 total, 7,152 passed,
118 skipped, zero failures/errors**, with no retained non-daemon thread or active
child process. Repository validation finished at 19:31:13 UTC: 98 preset graphs,
194 pinned assets, 4,913 tracked paths and 167 LoRA names. These measurements
belong to checkout `15b0337f2f8a9d10edee688af9f55ccbc1c8adb6`, tree
`c40f63b261dec75d26d9ef17bcf0998a7d8bf63e`.

The **19:32:51 UTC** repository capture records actual main
`f9e4187e9062553ca35f4b8eb9d099838457a604`, the same code tree, with no open PRs
before creating the documentation closeout. The capture's `facts_sha` and both receipts' `source_sha` retain the measured
checkout; they do not relabel the later docs commit as a fresh full-suite run. Catalog blob
`a9b0d600dc3812a2ef7ea198550a5fba6631aab0` and unchanged `HUMAN_TODO.md` blob
`f771832974d0d583eaa9ed31707d58ec1a69ded3` identify the capture's source inputs.
The ten-issue capture is a bounded work queue, not a complete inventory of all
open issues. #1948 and #2009 remain next-ready; #2026 and #1983 require configured
native execution rather than a new creative permission decision.

This closeout changes documentation and snapshot data only. Its separate payload
validation passed with 98 graphs, 194 pins, **4,914 tracked paths** and 167 LoRA
names, including this new verification record. Snapshot regeneration/check,
local links in the touched/current sections and diff whitespace checks passed.
The hosted code receipt above retains its original 4,913-path count. Historical
failures, earlier captures and owner choices are preserved.

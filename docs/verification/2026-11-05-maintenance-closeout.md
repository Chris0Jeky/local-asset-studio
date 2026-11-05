# Runtime recovery, Review guidance and native follow-through — 5 November 2026

This third maintenance pass continues the
[procedural-tools and recovery pass](2026-11-05-procedural-recovery-closeout.md).
Software qualification, hosted native execution and owner acceptance remain
separate. The records below name actual reviewed heads, CI checkouts and merged
trees; a passing component run does not qualify a later combined tree by itself.

## Merged and qualified components

| PR | Reviewed head | Tested and merged tree | Actual main merge | Hosted full-suite evidence |
| --- | --- | --- | --- | --- |
| [#2032](https://github.com/Chris0Jeky/local-asset-studio/pull/2032), protected-process recovery | `c782d237826303987c0cdbd42ea9ff97c560a50d` | `7dbf22dd00adcda2ab8caea351eb126b42888e00` | `f20a22ae64180d2e3308f740c99f50eb37205e3e` | [Run 42104236634, job 127514723840](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42104236634/job/127514723840): 7,273 tests; 7,155 passed, 118 skipped, zero failures/errors, 816 seconds. All five applicable workflows passed. |
| [#2033](https://github.com/Chris0Jeky/local-asset-studio/pull/2033), Library Review guidance | `235a180cff327d42b8d7e9f65c96a3623dc47b04` | `68cc8d2dd52fed53b605b18b588d20fc6d526ae2` | `daebc630b2fa5b770faa3c8f7a909ae03fa96d19` | [Run 42105301545, job 127518422604](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42105301545/job/127518422604): 7,273 tests; 7,155 passed, 118 skipped, zero failures/errors, 1,126.776 seconds. All 20 applicable workflows passed. |
| [#2034](https://github.com/Chris0Jeky/local-asset-studio/pull/2034), procedural smooth shading | `195cf046269e08165a2ddfca0f36c02005ecb259` | `5121753668bed0ccf15e71773f1ee2990a24a31f` | `3bfb7da4adb775ff83e6b371c8bf1650dc944408` | [Run 42106959107, job 127524419082](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106959107/job/127524419082): 7,298 tests; 7,179 passed, 119 skipped, zero failures/errors, 1,013.837 seconds. All applicable required workflows passed. |
| [#2035](https://github.com/Chris0Jeky/local-asset-studio/pull/2035), Jobs cache identity | `7cef2fb15f7ab2104d3fd79dfbab64f077c10318` | `6f65d902d814bd0ae698f2c634da6e69a928642a` | `17c0e33b0d9754615220de1f59550d0ddf1283de` | [Run 42107729284, job 127526885108](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42107729284/job/127526885108): 7,300 tests; 7,181 passed, 119 skipped, zero failures/errors, 1,077.573 seconds. All 22 applicable workflow families passed. |
| [#2036](https://github.com/Chris0Jeky/local-asset-studio/pull/2036), Krita saved-version bring-back | `d80fa1d18898f6997a05d142f986908b564938fc` | `8e65438bc71d4cec28394d09c8dc4b6e0a7434ce` | `88a8c09adf6e9dd5cd3325ddf2c952ab2b0ff0ea` | [Run 42107828886, job 127527231977](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42107828886/job/127527231977): 7,306 tests; 7,187 passed, 119 skipped, zero failures/errors, 1,060.312 seconds. All 12 applicable workflow families passed. |
| [#2037](https://github.com/Chris0Jeky/local-asset-studio/pull/2037), native material retention and worker startup | `ee1cb2c26ac6a757860b1c9368840c08fa9965a9` | `a78258e0c3fecd8a060d1295ed304885c3a2105a` | `96ab62a2a4bca43b721e68d8b8a87d8093b89c23` | [Run 42109976829, job 127535031112](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42109976829/job/127535031112): 7,321 tests; 7,202 passed, 119 skipped, zero failures/errors, 995.880 seconds; clean lifetime shutdown. Four applicable workflow families passed. |
| [#2038](https://github.com/Chris0Jeky/local-asset-studio/pull/2038), bounded Windows Archive setup | `5d7b66cf3ebcab319c82eae5478606b7afe11a1f` | `b480bec71897fa24c23ce8fe07b43a3f7c8a4e05` | `881185ad8825ce13c5b37299a2b255146a5c1a6d` | [Run 42110786216, job 127538098520](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110786216/job/127538098520): 7,321 tests; 7,202 passed, 119 skipped, zero failures/errors, 1,032.068 seconds; clean lifetime shutdown. Both applicable workflow families passed. |

The actual full-suite checkout was
`b13690d8e9b220b1fd1d3e3f44126332d512f6e3` for #2032 and
`9e05794befa3984ff60a12e0251e832ccdad548d` for #2033. Their trees equal the
respective reviewed heads and actual main merges above. Independent review
approved #2032–#2036; #2033–#2036 also passed connected Codex review. Jobs
and Krita had no findings or unresolved review threads. The later full-suite
checkouts were `0473eccac4d6d3d9b8104e69ac31b01cc272515a` (#2034),
`d6d1ac70d28c555636b82e59d2c1dcc1de1bc30e` (#2035) and
`6dd6f8bbfc548adc293c13e0a5c4494b257833a7` (#2036), each with the respective
reviewed and merged tree above. The Jobs and Krita suites ran on Ubuntu 24.04
with Python 3.12.16.

### Recovery keeps ambiguous processes in view

Process classification previously shared exception handling between the
candidate being inspected and the Studio's own PID lookup. If a candidate's
command line or working directory was protected and the own-PID lookup raised
`NoSuchProcess`, that exception could discard the live candidate as though the
candidate had disappeared. A protected launcher could then be absent from the
recovery decision.

The correction scopes candidate disappearance separately from failure to read
the Studio's own identity. A candidate that remains live but unreadable stays
ambiguous. The classifier regressions cover 24 combinations of identity faults.
A regression also calls actual `RuntimeRecovery.tick()` with the shipped
`BackendManager` classification, a protected candidate and an unreadable own
identity. Repeated ticks retain `foreign-or-ambiguous-listener`, zero launches,
zero recovery attempts and only `/system_stats` probes.

Earlier read-only observations of protected processes on Windows retain their
original scope. This pass did not execute an actual recovery restart on the
corrected code at the owner's Windows workstation. The regression and hosted
suite establish the conservative decision under the injected faults; they do
not establish that workstation restart behavior.

### Review names its queue and decisions

The Library explains that **Review next** opens unreviewed assets **shown on
this page**, that current filters set the queue, and that checkboxes select
assets for bulk actions. The button includes the current unreviewed count.
The existing decisions remain **Keep**, **Needs work** and **Not this**, saved
with K, W and X respectively.

[UX run 42105301633](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42105301633)
passed all 31 use cases without skips, page errors or generation. Its
[artifact 13452051826](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42105301633/artifacts/13452051826)
was downloaded and checked against ZIP SHA-256
`d9e1c891b7f05b6fc6a18d48e93f9358514e2730f851a1edab77f92edf7d6a39`.
Seven screenshots were inspected, including desktop, tablet and phone guidance.
The fixture filtered four unreviewed assets to three, saved one decision with
each of K/W/X, left the hidden fourth unreviewed and preserved the separate
checkbox selection. Selecting, filtering and opening the queue did not save a
review. This proves the browser flow with fixture assets; it adds no new owner
art acceptance. Broader terminology, workflow and accessibility findings remain
open in #2009.

## Native shading qualification

[#2034](https://github.com/Chris0Jeky/local-asset-studio/pull/2034) adds the schema
`smooth=0..1` switch while preserving the faceted default and the existing
stale-plan rules. Reviewed head `195cf046269e08165a2ddfca0f36c02005ecb259`, tree
`5121753668bed0ccf15e71773f1ee2990a24a31f`, passed the actual hosted Blender gate
in [run 42106959396, job 127524187967](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106959396/job/127524187967).
That native lane checked out the reviewed head directly with clean source.

Six production builds cover lantern, crate and potted plant with flat and
smooth shading, each at three LODs. The retained 18 GLBs passed normal,
interpolation, hard-cap and paired-geometry invariance gates. The downloaded
artifact's ZIP identity and all 18 GLB hashes and normal summaries were
rechecked. The [shading record](2026-11-05-procgen-smooth-shading.md) retains the
runtime/archive identities, complete artifact identity, gate scope and both
failed attempts: the first used the wrong displayed Blender socket name; the
second reused an immutable aggregate receipt path. Their later corrections and
passing run do not relabel those attempts.

Issue #1948 is closed following #2034's qualified merge. This sampled
exported-normal proof does not complete #2026: all eight generators still need
qualification through the configured Studio/Windows/Blender/Godot path,
including interrupted publication. No owner native application was launched by
this documentation pass.

## Jobs and Krita follow-through

The Jobs cache now retains the actual jobs collection alongside its revision.
Replacing `studio.jobs` with a new collection at the same revision cannot reuse
the old cached response or let a delayed old builder replace a newer answer.
Concurrent HTTP and mutation regressions cover this behavior. The
[Jobs evidence](2026-11-05-jobs-cache-identity.md) retains the causal collision,
existing mutation/invalidation contract and offline checks. Issue #1808 is
closed after #2035's merge.

Krita bring-back now reads a bounded, stable PNG snapshot, requires a complete
IEND chunk and CRC, verifies the image and decodes its pixels. A file changed or
replaced during the read is refused without importing a repair or changing the
session. The session remembers every successfully imported byte hash across
restarts: save A, then B, then A returns the first repair for A. A malformed
session is refused, and valid legacy last-import receipts survive migration.
[The Krita guide](../KRITA-ROUNDTRIP.md) keeps these exact boundaries visible:
Studio cannot lock Krita or predict a save after its read, and it does not find
a `.kra` or a PNG exported somewhere else. Synthetic-PNG tests and mocked
application launch qualify the software; a native owner GUI save/export run and
a safe working-directory retention policy remain open in #1864.

## Native material qualification

[Material run 42110231187, job 127535527882](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110231187/job/127535527882)
passed exact head `ee1cb2c26ac6a757860b1c9368840c08fa9965a9`, tree
`a78258e0c3fecd8a060d1295ed304885c3a2105a`.
[Artifact 13454425561](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110231187/artifacts/13454425561)
has verified ZIP SHA-256
`5acfe50e0c27fb8f477474cd7d856a477511f7e6d242f254b72db678525a531b`.
All 14 output hashes were rechecked after download. Original and repaired
semantic checksums agree; seeded and reopened damage agree and differ from the
original. Material membership remains unchanged and only displaced
`BadgeGreen` gains fake-user retention. Stderr is empty.

The first native attempt aborted during GPU initialization before creating the
fixture. The production correction keeps worker startup's GPU and Cycles device
discovery explicitly `not-probed`, with `ok: null` and reasons. Its critical
review and 23 focused tests passed. The explicit capability CLI retains device
probing, and requested renders retain their actual runtime behavior. No GPU
availability or render success is inferred from this material pass. The
[material record](2026-11-05-corpus-material-retention.md) keeps the failed
attempt, runtime identities, exact checksums and remaining configured-Windows,
realistic-v2 corpus and benchmark requirements together. Issue #1983 remains
open after #2037's qualified merge. Its full-suite checkout
`aa1dca1ceec48d33114f06a926ae4f7e1a552a4d` shares the native/reviewed/merged
tree above. The suite finished at 21:26:45.027Z on Ubuntu 24.04/Python 3.12.16;
validation at 21:26:45.199Z passed 98 graphs, 194 pins, 4,929 tracked paths and
167 LoRA names. The actual requested native run supplies the native evidence;
later opt-out skipped jobs do not. Connected Codex review found no findings,
and inline/submitted reviews were empty.

## Windows Archive setup qualification

[#2038](https://github.com/Chris0Jeky/local-asset-studio/pull/2038) merged the
bounded cached headless-shell setup on the qualified material parent. This
completes that setup correction while preserving the browser fixture's existing
checks. Broader user-facing browser-flake issue #1306 remains open.

The first Windows Archive attempt,
[run 42106959456, job 127524238550](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106959456/job/127524238550),
spent about 237 seconds enabling Media Foundation and hit the four-minute
setup limit. The bounded workflow change uses the headless shell for this
fixture, caches the browser installation and allows six minutes for setup.
The retry within run `42106959456` passed the unchanged shading head.
The cache/workflow child's separate passing result at head
`8aae89cb1ed672ccee833dfc63edfc1f49608b8a` is component evidence; the final
integration head is qualified below. That earlier child run also hit
the cache; neither result establishes a cold-cache fallback. The setup failure
is retained and does not establish a production Archive defect. Broader
user-facing issue #1306 remains open.


### Final Archive browser gate

[Run 42110786128](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110786128)
passed exact head `5d7b66cf3ebcab319c82eae5478606b7afe11a1f`, tree
`b480bec71897fa24c23ce8fe07b43a3f7c8a4e05`. Windows job `127537463227` and
Linux job `127537463665` each passed **39 browser checks**, with no page/handler
exceptions or unrelated mutations. Windows reported a hit on cache key
`playwright-Windows-X64-1.57.0-chromium-shell-v1`; browser installation still ran
for about 171 seconds before browser completion at **21:19:05 UTC**. The cache
hit therefore does not establish that installation is free or skipped.

The Windows [artifact 13454696251](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110786128/artifacts/13454696251)
has SHA-256 `d99f653d55b1ba0b42b5078b5951938101c7ef66db5e07984719492c1c520d7a`.
The Linux [artifact 13454716109](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110786128/artifacts/13454716109)
has SHA-256 `4d69946adfd82a0aecc7f89e210892e66534b0437833066c47fbe2fdeb2dbd0c`.
Connected Codex reviews completed on the actual #2037/#2038 heads without
findings. #2038 also passed independent review; no submitted reviews or inline
threads remained.

## Final combined code qualification and capture

All seven code PRs, #2032–#2038, are merged. The final #2038 code identity is
separate from its actual CI and main commit identities:

| Identity | Git SHA |
| --- | --- |
| Reviewed head | `5d7b66cf3ebcab319c82eae5478606b7afe11a1f` |
| Actual full-suite checkout | `802f7c57f098229cb953c103452472c75bbdf8d2` |
| Actual main merge | `881185ad8825ce13c5b37299a2b255146a5c1a6d` |
| Common tested and merged tree | `b480bec71897fa24c23ce8fe07b43a3f7c8a4e05` |

The actual merge's parents are prior main
`96ab62a2a4bca43b721e68d8b8a87d8093b89c23` and the reviewed head above. No code
intervened between qualification and merge.
[Check studio 42110786216, job 127538098520](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42110786216/job/127538098520)
ran `python tests/check_full_suite_lifetime.py` on Ubuntu 24.04/Python 3.12.16.
The **2026-11-05T21:33:02.586Z** result is **7,321 total, 7,202 passed, 119
skipped, zero failures/errors, 1,032.068 seconds**. Lifetime shutdown was clean
and all five atexit callbacks returned. At **21:33:02.767Z**, the validator passed
**98 graphs, 194 pinned assets, 4,929 tracked paths and 167 LoRA names**. The two
applicable workflow families, full suite and Archive, passed. The committed test
and validation receipts name the actual CI checkout, matching `facts_sha`;
they do not claim this later documentation branch ran that suite.

The post-merge GitHub observation at **2026-11-05T21:34:33Z** records actual main
`881185ad8825ce13c5b37299a2b255146a5c1a6d`, its common tree and **no open PRs**,
before publication of this documentation PR. The observed catalog blob is
`a9b0d600dc3812a2ef7ea198550a5fba6631aab0`; the observed `HUMAN_TODO.md` blob is
`f771832974d0d583eaa9ed31707d58ec1a69ded3`. The generated repository snapshot
is a pure projection of that bounded work capture and the two SHA-bound
measurement receipts. The earlier second-pass capture remains historical.

### Selected queue reconciliation

The final post-merge read at **2026-11-05T21:34:33Z** confirmed #1948 and #1808
closed as completed, and #2009, #1983, #2026, #1864, #177, #393, #395, #123, #178,
#77, #89 and #313 open. The capture removes closed #1948 and authors
`next_ready: [2009]`. The existing parked #177/#393/#395/#123 selection remains
an intentional deferment; #178 remains blocked on open measured-memory issues
#77/#89. #1983 and #2026 retain configured-native execution work, and #313
retains its owner acceptance milestone.

The latest live comments distinguish current scope: #2009
[comment 6669787703](https://github.com/Chris0Jeky/local-asset-studio/issues/2009#issuecomment-6669787703)
credits #2033 while keeping broader UX open; #1983
[comment 6669806742](https://github.com/Chris0Jeky/local-asset-studio/issues/1983#issuecomment-6669806742)
credits the synthetic native pass and retains the original corpus/benchmark;
#2026 [comment 6669788547](https://github.com/Chris0Jeky/local-asset-studio/issues/2026#issuecomment-6669788547)
credits the exported-normal pass while retaining all-eight Studio/Windows/Godot
qualification; #1864
[comment 6669788193](https://github.com/Chris0Jeky/local-asset-studio/issues/1864#issuecomment-6669788193)
credits findings 1–4 and retains safe working-copy retention and native GUI
acceptance. The later #1983
[merge comment 6670011293](https://github.com/Chris0Jeky/local-asset-studio/issues/1983#issuecomment-6670011293)
records #2037's merged synthetic proof while keeping the corpus benchmark open.
The #1306 [setup comment 6670130170](https://github.com/Chris0Jeky/local-asset-studio/issues/1306#issuecomment-6670130170)
records the bounded setup subpoint; that broader issue remains open. #1864 is
captured as ready for bounded retention/recovery design, with native GUI
qualification still separate. This closeout is source and execution evidence;
it records no human art acceptance.


## Documentation verification

This eight-file documentation/state closeout passed **27 repository-snapshot
contracts**, snapshot generation and its `--check` drift gate, relative-link
checks and the Git whitespace check. All ten relative links in the three
verification records, generated projection and new ledger entry resolve. The
local payload validator passed **98 graphs, 194 pins, 4,930 tracked paths and
167 LoRA names**, with 743 local-media entries and 102 references checked. The
one extra tracked path is this closeout note; the committed CI measurement
receipt correctly retains the **4,929** paths observed in the actual code
checkout. No full suite was repeated locally for these docs-only changes.

The earlier `CURRENT_STATE.md` body is unchanged, and `HUMAN_TODO.md` is
unchanged. The third-pass record is source and execution evidence, with human
art acceptance kept separate throughout.

## Evidence limits and owner decisions

The local container's incompatible PID and `/proc` views remain a limit for
unmocked process-owner tests. Hosted receipts supply those checks; this docs
change does not claim a new local full-suite result. No installed ComfyUI or
model packages were changed, no generation was submitted and no installed-host
inventory or artistic-quality estimate is introduced.

The illustration wave stays paused pending #1923 and replacement-wave choices.
Parallax usability and the island default-switch decision remain open as
recorded in [HUMAN_TODO.md](../../HUMAN_TODO.md). This technical pass answers none
of those decisions and adds no art acceptance or model-licence conclusion.

# 5 November 2026 integration closeout

This record separates merged code, its component qualification, the final combined
code run and owner decisions. It accompanies [STATUS.md](../STATUS.md) and the
dated entry in [CURRENT_STATE.md](../../CURRENT_STATE.md). Earlier failures and
historical measurements remain in their original receipts. The slice notes retain
what was known when they were written; this closeout adds the later qualification.

**Qualification boundary:** all eleven PRs below are merged. The final
[selector-scope follow-up #2019](https://github.com/Chris0Jeky/local-asset-studio/pull/2019)
under #2009 passed its full/native gates, and its tested tree is identical to the
actual merged main. The final section binds that combined code result to its
real checkout, merge and fresh work capture. Earlier component results retain
their separate source identities and scope.

## Actual merges

GitHub PR metadata was read directly on 5 November. All times below are UTC.

| PR | Reviewed head | Actual merge | Merged at | Delivery |
| --- | --- | --- | --- | --- |
| [#2007](https://github.com/Chris0Jeky/local-asset-studio/pull/2007) | `d0bbe7a923855a0e08caeb489f1628909cf82fd6` | `26036b05e22b6adfd486b6e511b4fc0cae05593d` | 01:08:16 | MIRA / FORM VII handoff |
| [#2010](https://github.com/Chris0Jeky/local-asset-studio/pull/2010) | `a80e87e46a21119d42ad4d57d58efc92308a0942` | `8cc77bdf5980b86819061b021a4831997540a60d` | 02:02:56 | Complete critic views and benchmark asset identity |
| [#2011](https://github.com/Chris0Jeky/local-asset-studio/pull/2011) | `782f747411c9c3bf07a646b46a81a87ac6cac91e` | `2dc4efe4ae8a540f83da931288d8cc34ac1dffac` | 02:20:49 | Discoverable editor and review navigation |
| [#2012](https://github.com/Chris0Jeky/local-asset-studio/pull/2012) | `a7b6c9cee14790e127189b31a6dddcc741b53614` | `1dcb7e8e774e9a8c76a07fcb9eb3fed86a298ec9` | 02:22:57 | Stable drafts and visible repair feedback |
| [#2014](https://github.com/Chris0Jeky/local-asset-studio/pull/2014) | `55cc4a6c15871557c3d70d16bad0d53cd67feb43` | `d7392c025027b2df8e4a045f44e54f05529f111f` | 02:24:19 | Sampler identity and imported-material preservation |
| [#2013](https://github.com/Chris0Jeky/local-asset-studio/pull/2013) | `f6e90750d0dcf6272601006c1c203a56897cbfed` | `107a5bc69a67246d101ff1754dfe15f67d81e6e9` | 02:38:55 | Finished pictures and comparison choices first |
| [#2015](https://github.com/Chris0Jeky/local-asset-studio/pull/2015) | `64432679b7002c18b8937a1fd0e1d3cc5b5d6df1` | `4102c714c08bc15772333613df0ddc537654fc6b` | 02:53:03 | Truthful History restore outcome and refresh; [#1874](https://github.com/Chris0Jeky/local-asset-studio/issues/1874) complete |
| [#2016](https://github.com/Chris0Jeky/local-asset-studio/pull/2016) | `62702f40112590d003826ed1ba01ff23889356b9` | `2ceda747d7f39605c663240d641dd28c0689b80e` | 02:55:58 | Bounded Blender scene descriptions; [#1984](https://github.com/Chris0Jeky/local-asset-studio/issues/1984) complete |
| [#2017](https://github.com/Chris0Jeky/local-asset-studio/pull/2017) | `09f80825f04ad3cf9c95129d3945ffef72ed9f6e` | `4a59dabb0fb8f402317590e115369fe52601e73f` | 03:04:36 | Make saved-look ownership and presentation |
| [#2018](https://github.com/Chris0Jeky/local-asset-studio/pull/2018) | `8c034c77fe2a06a17fb4408be1b667482da6a568` | `821ac33d9b61b562e60d2cfb6024edcce9679a24` | 03:50:11 | Models file summaries, actions and startup/layout corrections |
| [#2019](https://github.com/Chris0Jeky/local-asset-studio/pull/2019) | `18d0cb4b57c46fe40260667500214d6118f35709` | `d9eb214b03a5ef50f1558e12b5ad7f06ea9d4938` | 04:17:36 | Models selector scope and preserved Back preference |

The final code-main tree is `939557b9d6968b5ee22987681245bb004bf0adeb`.
The local mirror has that exact tree under a different local commit identity;
local mirror commits are never substituted for the live GitHub source SHAs.

## Component qualification

Each full-suite row belongs to the named PR's final reviewed head and its hosted
checkout. These are separate runs, and their counts are not cumulative. Earlier
component runs do not measure later code; the final #2019 row also supplies the
combined-code evidence through the tree identity recorded below. Each completed
with zero failures/errors and clean suite-lifetime shutdown.

| PR | Check studio run | Tests | Skips | Suite seconds |
| --- | --- | ---: | ---: | ---: |
| #2007 | [41628935000](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41628935000) | 7,181 | 112 | 956.854 |
| #2010 | [41950391439](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41950391439) | 7,197 | 112 | 1,096.301 |
| #2011 | [41951658098](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41951658098) | 7,183 | 112 | 1,108.578 |
| #2012 | [41951764526](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41951764526) | 7,183 | 112 | 1,119.802 |
| #2014 | [41952080938](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41952080938) | 7,191 | 113 | 1,015.852 |
| #2013 | [41954674708](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41954674708) | 7,197 | 112 | 790.156 |
| #2015 | [41955963453](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41955963453) | 7,205 | 113 | 1,085.246 |
| #2016 | [41956327111](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41956327111) | 7,218 | 113 | 1,068.825 |
| #2017 | [41957704867](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41957704867) | 7,205 | 113 | 776.617 |
| #2018 | [41961836803](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41961836803) | 7,218 | 113 | 1,081.932 |
| #2019 | [41964696908](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41964696908) | 7,218 | 113 | 1,083.821 |

For #2018, the full suite actually checked out
`7daaa62bcb9f7d6fc2ec3c5071e33e08f7966005`; GitHub's actual merge is
`821ac33d9b61b562e60d2cfb6024edcce9679a24`. Both have tree
`b5701bfd65c3c47138cbf437c0e00f744e899f75`. The
[merge qualification](https://github.com/Chris0Jeky/local-asset-studio/pull/2018#issuecomment-6649169645)
records this identity, all 24 completed workflows and the validator result.
The final combined revision after #2019 is recorded separately below.

The current-main candidate checks before merge are narrower integration evidence,
not another full suite. The corresponding PRs retain their exact candidate trees
and check counts. Final-head Codex reviews reported no findings or unresolved
review threads before these merges. Manual/native findings and their corrections
remain recorded below.

The [timing analysis for open #1882](https://github.com/Chris0Jeky/local-asset-studio/issues/1882#issuecomment-6649423658)
compares four existing successful logs while preserving skipped and duplicate
test occurrences. It finds broad timing variation across shared cases, without
establishing a host-load cause or steady-state distribution. Unittest duration
does not measure the whole wrapper budget; startup, discovery and shutdown also
consume it. No new run, budget change or assertion weakening was used.

### Browser and native evidence

- Navigation and editor browser workflows passed on their final heads. The
  comparison run passed 31/31 UX journeys and 295 pose-handoff assertions;
  [its artifact](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41954674755/artifacts/13382763041)
  was downloaded, digest-checked and visually inspected at 1440×900, 900×700,
  390×844 and 390×500. Native browser checks preserve focus, notes and disclosure
  state through refresh. The Node render harness additionally verifies that
  per-asset disclosure state and focus survive candidate reordering.
- History passed 69 native browser checks, with inspected desktop and phone
  screenshots. Its actual HTTP/SQLite fixture verifies the refreshed revision,
  truthful success and Saved setups event boundaries; it does not judge the
  owner's broader workflow comfort. [History receipt](2026-11-05-history-restore-1874.md)
  and [final qualification](https://github.com/Chris0Jeky/local-asset-studio/pull/2015#issuecomment-6648378556).
- Make's [browser run 41957704886](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41957704886)
  qualified head `09f80825f04ad3cf9c95129d3945ffef72ed9f6e`: 11/11 checks on each
  of Linux and Windows, without skips. The four source hashes matched, artifact
  digests were checked, all 16 screenshots were inspected at desktop/phone sizes,
  and all eight preview geometry receipts passed hit tests without overflow.
  GETs use the actual local HTTP fixture; saved-look POST responses are crafted
  fixture replies. This proves browser UI ownership and rendering, not persisted-look
  backend behavior. The Windows log retains static-file connection-abort traces
  during transitions; the page-error assertions and all cases pass.
  [Final merge qualification](https://github.com/Chris0Jeky/local-asset-studio/pull/2017#issuecomment-6648542547)
  retains both platform artifact identities and the complete gate results.
- Models' final [browser run 41961836906](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41961836906)
  qualified head `8c034c77fe2a06a17fb4408be1b667482da6a568`. All 12 captures
  were inspected: ten Models/startup views and two retained dependency views.
  [Artifact 13385283345](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41961836906/artifacts/13385283345)
  has SHA-256 `a3d17dc8c94076173f72ffa68f6853c563ae535ba4240780c1c9402cbb80340f`.
  The [native qualification](https://github.com/Chris0Jeky/local-asset-studio/pull/2018#issuecomment-6648973462)
  binds the source hashes, healthy startup, keyboard/file navigation, geometry and
  zero-mutation assertions to those captures. Synthetic read data does not prove
  installed-host model behavior. The observed selector-scope ambiguity remains
  explicit in #2019; the two earlier failed attempts remain below.
- The selector-scope follow-up's [native run 41964697014](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41964697014)
  qualifies head `18d0cb4b57c46fe40260667500214d6118f35709`, with browser checkout
  `5f2ff0bd4c1213cec6754be4a3cade759e9b5672`. The Ubuntu browser and Ubuntu/Windows
  contract jobs pass. All 14 screenshots, ten geometry records, two healthy
  startup records and six source hashes were inspected. [Artifact 13387296450](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41964697014/artifacts/13387296450)
  is 3,010,044 bytes with SHA-256
  `b928f9ec0350c41f84949413f748ea15ae22a968270637d19576d97ea50ca3c1`.
  Actual Back restores **Show** and preserves Installed/storage; **Show everything**
  keeps its separate reset. Target center/top/bottom hit tests pass, with no page
  or visible errors and no model mutations. The 0.5 CSS-pixel bottom tolerance is
  used only by desktop Back (+0.078125px) and phone Verify (+0.03125px); text remains
  intact and bottom-interior hits pass, while the desktop lower focus outline
  reaches the viewport edge. This is Ubuntu native Chromium evidence; Windows
  supplies contracts. The original phone dependency capture retains its run-dock
  overlap and content/control-only scope. [Final native qualification](https://github.com/Chris0Jeky/local-asset-studio/pull/2019#issuecomment-6649367345)
  records these limits.
- [Native engine run 41952080922](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41952080922)
  passed on Linux and Windows with pinned Godot 4.5: 36 engine-evidence checks,
  five live-engine tests and 32 toon tests on each platform, without native skips.
  The imported-GLB policy probe's 15 cases exercise the production guard and file
  loader. The Ubuntu artifact was independently inspected, including material
  identity, source hashes and the receipt's empty failure list. This establishes
  material-application policy, not Godot 4.7.2 visual parity or a new Blender render.
  The file-availability guard does not validate compilation of nonempty malformed
  shader code; that limit remains explicit in the material PR.
- The course handoff validates repository text, diagrams and recorded artifact
  identities. Its linked native/media receipts retain their original scope;
  public access to owner-scoped downloads was not verified.

### Failures remain recorded

The first evidence-integrity full run failed because a legacy-success test supplied
only one of four required critic views. Its corrected fixture supplies all four,
preserving the original 40-pixel total, raw observation and non-replayable legacy
policy. Production completeness was not weakened. Earlier navigation/editor
browser fixtures and comparison phone screenshots also failed; their later passing
heads do not erase those records.

The initial Models head `d040de23cef1bb19cd319d0eeedb82ba0fbc919f` passed its
browser driver, but visual review of [artifact 13385490475](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41959800864/artifacts/13385490475)
found the phone Search label clipped under the privacy row, an oversized placeholder,
and a visible caught error, `Cannot read properties of null (reading 'controls')`,
with Runtime recovery disabled while `page_errors` was empty. This remains failed
visual evidence. GitHub reports artifact SHA-256
`f5bbf92fa04ac81cf21ff25c24658022486655b7bcd0e21044a9a2e45fdfddc1`.

A direct current-main reproduction located the startup error in the existing
[Looks owner's `applicationBlocker`](https://github.com/Chris0Jeky/local-asset-studio/blob/4a59dabb0fb8f402317590e115369fe52601e73f/app/static/looks.js): a null application and undefined preset ID
compare equal through their undefined IDs, then dereference `application.controls`.
A null application with a selected preset returns an empty blocker, and a matching
failed application correctly blocks. This identifies a production owner defect
exposed by the screenshot, alongside the real layout defects.

Correction head `8b2b6e62911b6f2a7c85ffd048484787f58c517c` adds explicit non-null
owner checks to the Looks payload and blocker while retaining global preparation
holds and matching failed-application refusals. Its layout changes address the
Models sticky offset and placeholder size. Its [native run 41961317964](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41961317964)
then failed in the driver's final cleanup with `Route.continue_: Route is already handled!`
after unroute and continuation of a held catalog request. [Artifact 13385995666](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41961317964/artifacts/13385995666)
contains only three startup-capture files and no complete result; its recorded
SHA-256 is `cbfdc5b1949dfbdeca617add7596f93122dce9dcaf62c3a82d9ab5da1914c6c1`.
The retained startup receipt is healthy, but it does not cover the complete
journey. The cleanup cause was confirmed against the Playwright 1.57 route owner:
unroute had already handled the held request before the driver continued it again.
Fixture-only head `8c034c77fe2a06a17fb4408be1b667482da6a568` drains held routes
before unroute, preserves all assertions, and leaves production unchanged from
`8b2b6e6`. Its full suite and inspected native evidence passed before #2018 merged.
The initial green driver result alone did not establish acceptance.

The first #2019 head `8a65abcfcc227764414dfa3aa3885031fe85e2d6` then failed its
new desktop Back-return geometry assertion: a link's bottom was `1000.078125`
against a `1000`-pixel viewport. Actual browser Back, the restored **Show** label,
**Installed** value and saved preference, healthy status, and center/top hit tests
passed. This does not establish a new production defect or a complete native pass.
The retained [artifact 13387220301](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41964114843/artifacts/13387220301)
has SHA-256 `1572fe2aa0b5554ebbb8d0ea92c55580a4e5d28e442ba8d7fc86d9909a9d3b64`.
Correction head `18d0cb4b57c46fe40260667500214d6118f35709` leaves application
code unchanged. Its driver records a maximum 0.5 CSS-pixel tolerance only at the
target's viewport-bottom edge and adds a bottom-interior hit test; header clearance,
other bounds and native scrolling remain strict. Fresh native qualification passed
with the limits recorded above; the failed first attempt is not relabeled as a pass.

The local container has incompatible PID and `/proc` visibility: even the current
Python PID cannot be resolved through `psutil.Process()`. The unchanged baseline's
process-owner/admission failures are environmental evidence, not a passing local
full-suite receipt. Production ownership checks were retained; hosted suites supply
those gates. Local Chromium and native Blender are unavailable. No local installation
workaround, new generation or owner-host runtime qualification was performed.

Detailed causal records:
[critic evidence](2026-11-05-blender-evidence-integrity.md),
[benchmark identity and timeout](2026-11-05-benchmark-evidence-identity.md),
[navigation](2026-11-05-navigation-review-clarity.md),
[editor](2026-11-05-editor-guidance-2008.md),
[comparisons](2026-11-05-comparison-pictures-first.md),
[toon materials](2026-11-05-toon-material-integrity.md),
[Blender scene summaries](2026-11-05-blender-scene-summary.md),
[Make saved looks](2026-11-05-make-saved-look-1867.md),
[Models file clarity](2026-11-05-models-clarity-2009.md),
[Models selector scope](2026-11-05-models-filter-scope-2009.md).

## Final combined code qualification and snapshot

Models #2018 is merged with the tested tree recorded above. Its native inspection
found that the existing required-file route keeps needed cards visible even when
the status selector says **Installed**. That selector continues filtering the
lower **Files on disk** list. Follow-up #2019 names its scope **Files on disk below**
while the required files are open, and **Show** in ordinary browsing; visible and
accessible labels agree. It preserves the selected value, saved preference,
query/search behavior, required cards, inventory filtering and request handlers.
Its final head passed all 23 workflows and completed review with no findings or
unresolved threads. The first head and incomplete native attempt remain recorded
above. [Final merge qualification](https://github.com/Chris0Jeky/local-asset-studio/pull/2019#issuecomment-6649542100)
binds the full/native proof to these distinct identities:

| Identity | Git SHA |
| --- | --- |
| Reviewed #2019 head | `18d0cb4b57c46fe40260667500214d6118f35709` |
| Actual full/native CI checkout | `5f2ff0bd4c1213cec6754be4a3cade759e9b5672` |
| Actual main merge at 04:17:36 UTC | `d9eb214b03a5ef50f1558e12b5ad7f06ea9d4938` |
| Common tested and merged tree | `939557b9d6968b5ee22987681245bb004bf0adeb` |

GitHub Git objects independently confirm the checkout and merge trees and their
parents: prior main `821ac33d9b61b562e60d2cfb6024edcce9679a24` and the reviewed
head above. No code intervened. This full run therefore qualifies the combined
code without a duplicate main-push run; it does not claim that the two commit
SHAs are the same or that this later documentation branch ran that suite.

[Check studio run 41964696908, job 127039122136](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41964696908/job/127039122136)
ran `python tests/check_full_suite_lifetime.py` on Ubuntu 24.04.5 with CPython
3.12.16. The 04:15:55 UTC summary reports **7,218 tests: 7,105 passed, 113 skipped,
zero failures/errors, in 1,083.821 seconds**. Lifetime completion was successful,
no non-daemon thread or active child remained, and all five recorded atexit
callbacks returned. The separate 1,200-second child-lifetime budget retains the
timing limits explained in #1882 above.

At 04:15:56 UTC, `python scripts/validate-repo.py` passed **98 preset graph/bindings,
194 pinned assets, 4,893 tracked paths and 167 LoRA names**, with 743 local-media
entries and 102 references checked. The two committed measurement receipts name
the actual tested checkout `5f2ff0bd4c1213cec6754be4a3cade759e9b5672`; the capture's
`facts_sha` agrees with it.

The live work capture at **2026-11-05T04:18:51Z** separately records main
`d9eb214b03a5ef50f1558e12b5ad7f06ea9d4938`. No PR was open at that capture, before
publication of this documentation PR. Catalog and `HUMAN_TODO.md` blob identities
were observed on that merged main. The generated snapshot is a pure projection
of this bounded capture and the two receipts, not a fresh inventory of the whole
backlog or a measurement inferred from the documentation branch.

The live issue read confirms that #2009 remains open after its bounded Models
dependency-clarity and selector-scope work. The authored `next_ready: [2009]`
selects the remaining Review action names: reproduce their actual jobs before
changing labels, retaining navigation, shortcuts and selection. #177/#393 stay
parked, #178 is blocked by open #77/#89, #313 is owner-run, and #395/#123 stay
parked. Closed #315 is removed from the captured queue. These are selected current
dispositions, not a renewal of the old October priority ordering.

### Documentation verification

This eight-file documentation change passed all 27 repository-snapshot tests,
the generated projection's `--check`, and the Git whitespace check. The local
payload validator passed with 98 graph/bindings, 194 pins, 4,894 tracked paths,
167 LoRA names, 743 local-media entries and 102 references. Its one extra path is
this closeout note; the committed measurement receipt correctly retains the
4,893 paths observed in the code CI checkout. All 22 relative links in the new
authored sections resolve. The older `CURRENT_STATE.md` body and all 26
`HUMAN_TODO.md` checklist lines are unchanged. No full suite was repeated locally.

## Owner decisions and issue scope

The replacement q-7 tour was completed and closed on 2 November, as already
recorded in [HUMAN_TODO.md](../../HUMAN_TODO.md). Its broader findings remain in
#1920/#1921 and the current clarity work; completing the tour is not blanket UX
approval. The old illustration wave stays paused pending #1923 and replacement
wave decisions. Parallax usability remains an open owner item although #1219 is
closed; the island default switch remains a separate open decision although
preparation issue #1207 is closed. Existing recorded art acceptances remain valid
within their stated scope; this technical closeout adds no new acceptance.

This documentation pass closes no implementation or owner issue. #2009's wider
workflow, terminology, Voice, Make, Library and accessibility findings remain open.
The dated [Full editor progress note](https://github.com/Chris0Jeky/local-asset-studio/issues/1920#issuecomment-6648934504)
and [Workflow lab progress note](https://github.com/Chris0Jeky/local-asset-studio/issues/1921#issuecomment-6648934759)
preserve the remaining work needed for the owner to understand those workflows.
[#1970](https://github.com/Chris0Jeky/local-asset-studio/issues/1970) still requires
native controls and corpus qualification: #2010's checks for complete views and
distinct assets do not tune the render threshold or re-score the earlier corpus.
No new product percentages, installed-host inventory or artistic-quality estimate
is introduced.

# Current state — 11 September 2026

## Interactive timing estimates and failure clarity — 13 September 2026

Studio now exposes a read-only `/api/estimate` calculation beside the Create workspace. It learns
from completed local ComfyUI runs and weights workflow, model files, LoRA names and strengths,
resolution, steps, frames, references, sampler/scheduler, prompt size, graph-node complexity and
batch size. Failed, uncertain, imported and native-only records are excluded. The browser refreshes
the estimate after recipe, control, LoRA, variation, reference and seed changes; sparse history is
shown as a wide, explicitly provisional range rather than false precision.

The historical Krea failure is now classified as a memory-allocation failure when the engine reports
`KSampler: bad allocation`; the UI retains the prompt ID, engine detail and a next action. A bare
historical record may not contain the new structured `failure` field, so the client also derives a
safe explanation from the retained message without retrying the prompt. A live estimate for the
current Krea 2 Anime Atelier shape returned 812.2 seconds, a 496–1128 second typical range, medium
confidence, 35 completed local samples and 3 exact-workflow matches. This is a timing aid, not an
execution guarantee, and it excludes queue wait.

The Studio server was restarted from the current checkout as PID 7376 after confirming an empty
ComfyUI queue; ComfyUI PID 20212 was not restarted. Both endpoints are healthy, the schema is
available, and the queue remains empty. No generation was submitted by this pass. Browser smoke is
not verified because the environment lacks the optional `playwright` package. HUMAN_TODO q-4 now
records the owner-controlled Windows restart as actioned; a live read confirms `C:\pagefile.sys` at
65,536 MiB and 38,506,180,608 bytes (~35.9 GiB) of commit headroom, above the 32 GiB gate. Large
Qwen/FLUX execution and art-quality acceptance remain unproven.

Focused server tests (50), UX policy checks (34), repository validation and the full suite (1,256
tests, 1,206 passed and 50 skipped) pass. The full suite needed `C:\Python314` first on PATH so
Node's bundle test could resolve `python`; without that explicit environment the Windows Store
`python.exe` alias caused one harness-only failure.

## Session closeout — 13 September 2026

The implementation evidence in this closeout was taken at main `042f40e39d0f965b2bd8677a59a99cf7491c3571`; this documentation-only closeout is now recorded on top of it. This pass merged
#137 (backend startup final observation, `042f40e`), #138 (preset-compatible document execution,
`1f198ca`), #139 (curated Anima evidence, `07d643f`), #141 (fresh runtime-status displays,
`c26cefc`), #142 (unknown-header intake, `ac19add`), and #145 (saved-workflow run controls,
`559347c`). Current main validation ran **1,102 tests: 1,086 passed, 16 skipped**, with repository
validation passing 66 graphs/bindings, 121 pins, 910 tracked paths and 86 LoRA names. The latest
browser check reopened `Anima - B softer cinematic shading` at revision 3, loaded 1,224 nodes,
passed connections, changed the first style strength from 1.0 to 1.25 with keyboard input and
Tab, and Undo restored 1.0; no job was queued.

The live loopback endpoints are healthy (`127.0.0.1:8191` Studio PID `28992`,
`127.0.0.1:8188` ComfyUI PID `24720`, worker and recovery healthy, schema available, queue
empty), but `/api/jobs` retains uncertain records
`a2908800-7214-4caa-ad23-3844527cdf5d` and `0cbaae1b-1134-548c-9e03-50bac00b75b9`, and
production retains one uncertain record. The closeout therefore did not stop either runtime;
the merged runtime and backend fixes are source-verified but not live-reloaded. Host commit
headroom is 11.72 GiB, below the documented 32 GiB gate; the effective page file is still
40 GiB pending the owner-controlled restart.

The four large model transfers remain active and incomplete: CSTati PID `7800`, JANIMA PID
`24844`, and the resumable YumeFlux/AniFox helper PID `12952` (wrapper PID `40040`). Their
`.part` files and failure receipts remain preserved; no model-install or checksum-complete claim
is made. PRs #146, #149 and #150 remain open and parked for a later pass; their latest hosted
checks are green, but review and merge decisions remain unfinished. HUMAN_TODO decisions remain
recorded; only q-4's owner-controlled restart is still an action, and it must wait until
downloads finish and work is saved.

## Modular Anima baseline execution — 13 September 2026

Three bounded Anima v1 runs completed and were visually inspected by the root agent at the same
832×1216 canvas: base with all style slots disabled (job
`058abcb0-e962-45da-8534-43443e9a3f60`, prompt
`47dd2edd-8fc1-45d2-9d99-64ccb6f587dd`, 28.098 s), first style with only slot 1 at `1.0` (job
`91b42081-f15f-46ac-9d36-a819d6e5d857`, prompt
`75f6f833-6e5f-41bf-9eac-ab8c202f117d`, 20.146 s), and the same style at seed `2026091302`
(job `a14fac06-2359-46f3-867e-feea7497118e`, prompt
`52345ff4-863b-4b79-a69b-e0f7784f7fde`, 18.078 s). A showed a clean graphic coat, trousers and
boots at the station; B supplied softer cinematic shading; C kept a similar wardrobe but changed
the face and bangs. Hands were hidden in pockets in all three, so hand quality is unproven. The
owner chose B as the starting look; A and B remain experiments and neither enters the shortlist.
Full output hashes and paths are in [the execution record](docs/ANIMA-BASELINE-EXECUTION-2026-09-13.md).

Five saved Workflow Studio baseline documents are present. Anima v1 is valid against the live
schema; CSTati v3, YumeFlux ILv1, AniFox v2 and JANIMA v1 remain blocked by missing local model
files. The source checkout is `8f471d6`; the live Studio process is PID `28992` from source
`07da7f1`, and ComfyUI is PID `24720` unchanged. The later compiler/MCP deployment is not yet
deployed. Timings are cache-confounded and carry no performance claim. Native crash prevention,
reliability, licensing and art acceptance remain unverified.

## Live reconciliation and creative baseline — 13 September 2026

The two earlier handoffs were reconciled against merged GitHub heads, checks and local receipts. The original screenshot resources are installed and pinned; PR #127 supplies separate WAI/Noirpopwave and Anima/Failleaf/sky02/BunnySlop recipes. Both produced inspected 832×1216 images, in 38.26 and 34.22 seconds respectively. Their exact job/prompt IDs and limitations are in [the reconciliation report](docs/STUDIO-REVIEW-2026-09-12.md). The owner chose **experiment only** for both; neither enters the promising shortlist. They are not a controlled cross-family comparison or proof of source-image likeness.

Live recovery initially failed because Windows refusal took about two seconds but the monitor timed out after one. PR #128 fixed that deadline. The controlled idle-stop test then observed exactly one automatic ComfyUI replacement, a healthy loopback endpoint, an idle queue and unchanged uncertain jobs. Pinned memory is disabled in the managed launcher. Two real inference runs and an idle cache release succeeded; native crash prevention remains unproven. The late protected-process ambiguity fix is merged as PR #132, separately from this successful recovery test; its live deployment remains pending.

PR #126 Guided Workflow Studio and PR #129 host-commit admission are deployed. Local memory enforcement is enabled and a non-submitting check rejected a qualifying large graph below 32 GiB without creating a job. The page file is configured at 64 GiB but still effectively 40 GiB until the owner restarts Windows. No automatic reboot is authorized. See [HUMAN_TODO](HUMAN_TODO.md) for the supplied creative choices, verified curation membership and remaining owner execution step; those choices are no longer undecided.

The new modular baseline catalog and larger resource downloads are in progress. Download source pins, local hash verification, executed generation and art acceptance are tracked separately. [The production brief](docs/FANTASY-CHARACTER-BRIEF.md) records the owner's non-sexual creative scope and preserves the separate character-study canon.

## Protected pre-listen launcher ambiguity — 13 September 2026

Recovery now inspects the cheap process name before reading full command identity. When psutil returns a blank protected name, a bounded hidden Windows `GetProcessById` lookup resolves that observed PID without any special-case PID or name exemption. A resolved non-Python process is excluded; a protected process named as the configured Python launcher, or one whose name cannot be resolved, remains ambiguous and blocks recovery rather than risking a duplicate pre-listen ComfyUI process. A process that vanishes during the scan remains absent. Offline tests cover fallback non-Python, fallback Python and unresolved cases; the prior read-only host probe saw `Secure System` at PID 284 through Windows while psutil returned blanks.

## Windows refusal classification — 12 September 2026

The recovery monitor gives its read-only `/system_stats` probe three seconds to receive a Windows connection refusal. A one-second urllib probe timed out at 1.011 seconds on this host and was conservatively classified as unreachable; three and five seconds received `ConnectionRefusedError` (errno/winerror 10061) at about 2.04 seconds. The monitor still starts only after that exact refusal and all existing process/work interlocks; ordinary timeouts remain unreachable and do not authorize launch. This records a host fault-injection observation, not a live recovery success or GPU execution.

## Bounded ComfyUI recovery — 12 September 2026

Studio now has an opt-in (`runtime_auto_recover: true`, default false) monitor for the currently selected configured backend. It persists a bounded state and event log under `.runtime/`, classifies healthy, startup, absent, live-but-unreachable and foreign/ambiguous listener states, and may start only a confirmed-dead selected profile with no fresh queued, submitting or running Studio work. It never switches backend family, scans/reassigns ports, stops a process, clears a queue or calls `/prompt`; retained uncertain jobs remain evidence and are never replayed. Startup processes are retained, repeated failures open a breaker, and a same-origin Reset recovery control only clears that breaker for a later monitor observation. A dead Studio worker is reported as degraded and blocks new jobs. Offline causal tests cover one launch across repeated polls, no prompt route, foreign/live/busy preservation, bounded restart attempts, retained startup and healthy reconnect/schema invalidation. No live process, generation, GPU or endpoint was exercised; runtime health, recovery effectiveness and creative acceptance remain unverified.

## Prompt response uncertainty — 12 September 2026

The `/prompt` submission boundary now treats malformed JSON, invalid UTF-8, truncated HTTP
responses, non-object replies and blank or non-string prompt IDs as uncertain. It keeps the
expanded pending graph and earlier batch evidence, and does not retry or alter reservations;
valid prompt ID strings remain exact and HTTP 400 rejection remains definite failure. Focused
server and production tests passed 51/51; the source full suite ran 872 tests: 837 passed and 35
skipped. Repository validation passed (61 graphs/bindings, 62 pinned assets, 808 tracked
paths). This is inert mocked HTTP proof only; no live backend, generation, GPU or art-quality
evidence was produced.

## Retained observation dispatch race (#113) — 12 September 2026

Late review of #105 exposed a duplicate-generation dispatch when Gallery Resume changed a retained
known-prompt job to queued after Production's entry check. Production now rechecks fresh tracking
authorization around stage dispatch and reconciliation, and queued jobs with submission evidence
take the observation path. Locks are released before backend I/O. Three offline causal assertions
failed on the original code; all 16 Production tests pass with the fix. Prompt IDs, graph receipts,
budgets and explicit continuation consent remain intact. No live prompt or runtime was touched;
GPU execution, creative quality and licensing acceptance were not assessed. The configured full
suite passes 875 tests run / 861 passed / 14 skipped in 85.169 seconds; repository validation passes
61 graphs/bindings, 62 pins, 808 tracked paths and 65 LoRA names. A scoped independent check confirms
the baseline's extra synthetic POST and finds no remaining duplicate path in the changed dispatch.

## Stop tracking uncertain prompts — 12 September 2026

The local Gallery can record an explicit reason for stopping observation of an
uncertain known prompt without changing its prompt IDs, submissions, recipes,
graphs, outputs, timing, lineage, or Production reservation. The retained
state records immutable stop/resume history. An explicit Gallery Resume only
queues observation of those retained prompt IDs; it never resubmits a graph or
continues Production. A prior stop event blocks stale Production work until a
later explicit Production Resume authorizes continuation after a terminal
observation record. This is local synthetic coverage only: no Studio project,
queue, ComfyUI request, generation, refund, or artistic acceptance occurred.

## Identity-plus-pose probes and runtime instability — 12 September 2026 (evening)

Two direct ComfyUI probes of an SDXL identity-plus-pose route (WAI v17 + `ip-adapter_sdxl_vit-h` on the canon
front + `xinsir-openpose-sdxl` on a skeleton extracted from the canon back, 704×1536, 30 steps) completed:
probe A with the `aqua (konosuba)` tag (prompt `550346d1…`, 111.1 s) reproduced the back-view costume closely;
probe B without the tag (prompt `932c3093…`, 82.1 s) drifted, so the tag did the work and the base adapter at
weight 0.6 on a centre-cropped torso does not carry an original design. Of four follow-up probes, one never executed, two sampled all 30 steps and died in `VAEDecode` without
writing an image, and one was never submitted: ComfyUI died six times this evening with `0xC0000005` inside host-side tensor moves (checkpoint mmap reload,
`partially_unload`, GGUF `.to()`), once on a FLUX.2 job the other agent submitted; three launch-flag sets
(`--disable-mmap`, `--cache-classic`, defaults) made no difference and the investigation is parked in #89.
Two Studio `qwen-2ref` jobs with front+back canon bound (`a2908800` uncertain, `f29937b7` failed on a host
allocation at 87 % commit under `--reserve-vram 0.6`) confirm #77's host-commit ceiling; per-process
attribution is on that issue. Seven files were downloaded with SHA-256 receipts (yolov9c hand/face detectors,
person segmenter, the fal Qwen multiple-angles LoRA, the CCIP identity model, IP-Adapter plus and plus-face).
Curated record: `experiments/curated/character-identity-pose-probes/`; nothing in it is art acceptance, and
no HUMAN_TODO item changed.

## UI handoff follow-ups — 12 September 2026

Gallery Continue now refreshes the exact output identity when it arrived after the current Workspace
snapshot. Missing, trashed and failed-refresh identities remain rejected, and an older refresh response
cannot replace a newer handoff. The dormant legacy handoff adapter keeps the active asset as its source
and uses its `data-handoff` value only as the destination. Overview activity now includes the server's
`submitting` state. Synthetic browser coverage exercises these paths with no model, Studio, project,
queue or generation activity; the policy check covers the submitting display classification.

## Runtime preconditions — 12 September 2026

Measured, not inferred. `qwen-image-edit-2511-Q4_K_M` is 12,738.98 MB resident in every log that
loads it; it loaded **partially** at 11,379.72 / 12,584.27 / 12,633.22 MB usable
(`C:/AI/logs/20260911-171055-error.log:282`, `20260912-043327-error.log:246,274`) and **completely**
at 12,751.49 MB and above (`20260911-053144-error.log:311`). At `--reserve-vram 2` the 17:31 pilot
did fully load at 12,888.02 / 12,899.61 MB usable and was then partially *unloaded* twice for the
VAE (`20260912-173147-error.log:109,127,130,137`): reserve 2 sat on the boundary rather than always
forcing a partial load. `Get-CimInstance Win32_OperatingSystem` reads a fixed 40 GiB page file
(`SizeStoredInPagingFiles` 41,943,040 KiB) and a 77,014,286,336 B commit limit; #77 failed at 97 %
committed and `/free` released 35,099,705,344 B
(`C:/AI/character-lab/pilot-20260912/cache-release-{before,after}.json`; the process also exited, so
the two are confounded). #89's four deaths were `0xC0000005` access violations during host-side
tensor moves after a partial load or unload. All four installed SDXL checkpoints are
epsilon-prediction (Animagine 4.0 and Pony v6 declare `modelspec.prediction_type = epsilon`; NoobAI
v1.1 and WAI v17 carry no v-pred key; ComfyUI logged `model_type EPS` for every SDXL load today), so
a mis-sampled v-pred NoobAI is **not** the six-finger cause. The owner's launcher
`C:/AI/Start-ComfyUI.ps1` (outside Git) went from `--reserve-vram 2` to `0.6` at ~20:55 local —
SHA-256 `526fcda5…c604c` before, `0c3fbc95…969e` after, backup `…ps1.bak-20260912-reserve2` — and
`app/backends.py` now matches. One Qwen job ran after the change and failed before the load line:
job `f29937b7-478f-4598-b756-661305d18ed9` (`qwen-2ref`, 512-wide, two refs, prompt
`0603c5be-0321-4325-ae5f-9a268b94d605`) on PID 4916 started 20:59:22 with `--reserve-vram 0.6`
(`C:/AI/logs/20260912-205922-error.log`: `13,870 / 14,250 MB usable`, unreachable at reserve 2 where
the same logs read `12,436 / 12,817`). After `Requested to load QwenImage` it raised
`DefaultCPUAllocator: not enough memory (4,377,600 bytes)` in a device→host unload at 44.93 s, with
**no** `loaded completely`/`loaded partially` line for QwenImage; the prompt worker then died with a
`TypeError` in `cleanup_models_gc` and ComfyUI was cycled (`20260912-210954`). Commit went 60 % → 87 %
(29 → 9.2 GB headroom) and `POST /free` did **not** release it (87 % → 87 %); a restart did (→ 67 %).
Per-process attribution is in #77's newest comments (idle ComfyUI 16.8 GB after `/free`, 158
`node.exe` 10.7 GB, ~15 GB non-process). **Measured:** the reserve does not move the host-commit
ceiling. **NOT verified:** the narrow exit test — no log yet shows `Requested to load QwenImage` then
`loaded completely; … full load: True` at 832×1216 with two references. Derivation, fit table and the
≥32 GiB commit gate (raised from 20 GiB: the run above started at 29 GB headroom and still failed):
`docs/RUNTIME-PRECONDITIONS.md`.

## Integrated Studio workflow UI verification — 12 September 2026

The shared workspace navigation, guided creation, saved drafts and reusable image
handoffs in PR #82 integrate main `896f948` at `0cc4970`. The configured Windows full
suite ran 864 tests: 850 passed and 14 skipped, in 206.251 seconds; repository
validation passed (60 graphs/bindings, 62 pinned assets, 805 tracked paths). The
independent review's confirmed gallery identity defect was fixed in `720b8f9`, and
its scoped recheck passed all 58 inert browser checks. Newly completed assets can
still need a library refresh (#86); a dormant legacy handoff adapter is tracked
separately on the PR. The current asset-detail and indexed gallery paths passed.
This local proof does not claim the interface is already deployed or that the
longer full-suite duration has been attributed to a cause.

PR #85 merged as `896f948`, after PR #84 (`04903e9`) and PR #83 (`06d2750`). One
guarded idle Studio reload to PID 27572 preserved all 77 job-state hashes and 17
projects and loaded the tested Voice and character-scope sources. ComfyUI had
restarted outside this task to PID 40412; the reload preserved that process and
its history. The receipt is `primary/.runtime/session-2026-09-12/scope-reload/after.json`.
The two new portrait-scope cases were then imported with shared allowance two and
zero reserved attempts. Their first Start check found external ComfyUI work and
stopped before writing intent or sending a request. Both remain planned at this
checkpoint; the old pilot and blocked boot-edit probe remain unchanged.

## Gallery handoff identity guard — 12 September 2026

The Studio UX now refuses a gallery output that has no saved `asset_id` instead of substituting the
last active Workspace asset. A fixture-browser run opened an unrelated asset detail, removed the
gallery output identity, and proved that the gallery action opened no handoff, made no reference
request and retained the prior lineage. Restoring the output identity selected its own asset, while
the asset-detail action retained its active-asset behavior. The 58-check fixture journey had no
browser exceptions and no execution/setup mutations. This is a local UI boundary proof only: no
live Studio, ComfyUI, model, project, queue or generated output was touched.

## Matched portrait prompt scope — 12 September 2026

Opt-in request/plan/handoff v2 can select existing canon descriptions and invariants
for each task; v1 plan, brief and handoff golden hashes remain identical. Full canon,
approval and required checks stay in the retained plan, with a verified selected-text
audit in each v2 handoff. Integration `77ac0af` includes main `06d2750` through PR #83.
The configured Windows full suite ran 860 tests: 846 passed and 14 skipped, in 69.301
seconds; validator passed (60 graphs/bindings, 62 pinned assets, 796 tracked paths).
The original-head independent review found no defects and ran 257 character tests:
253 passed and four skipped. Publication and final base-delta review remain on the PR.

The exact approved standard canon and portrait bytes were copied into
`C:/AI/character-lab/portrait-prompt-scope-20260912/`. The actual offline CLI compiled
plan `7208de8012ecf62fbe8587d740818ae23f08c8151ebe316f786c063e7e767656` and two
validated handoffs: identical FLUX route, reference, seed 12001, checks and bindings;
positive text is 1,217 versus 627 characters. Canon/reference preflight passed. This
is a new two-attempt, zero-repair study; the exhausted twelve-case pilot is unchanged.
No new Production project, generation or artistic acceptance is claimed here.

## Character-edit recovery on Windows — 12 September 2026

PR #83 integration `d9cd223` includes main `04903e9`. Interrupted collection retains
partial staging and recovers the same completed asset without another generation or
reservation; exact native reference roles and connected actor-contact coverage are
validated. The full configured Windows suite ran 854 tests: 840 passed and 14 skipped;
repository validation passed. A fresh independent review found no defects and its
28-test recovery run passed with one Windows symlink-privilege skip. The real local
HTTP/subprocess-death test passed with inert neural execution. See
`docs/character-consistency/EDIT-RECOVERY-VERIFICATION.md` for the evidence and limits.
No live neural repair or art acceptance is claimed; PR #71 remains open.

## Recipe inspection on the configured Windows host — 12 September 2026

The PR #80 integration at `2402763` includes main `db066ec` (the failed-job timing and readiness
fixes). The configured Windows suite ran 825 tests: 812 passed and 13 skipped; repository validation
passed (60 graphs/bindings, 62 pinned assets, 791 tracked paths). A fresh independent review found
no defects and ran 47 provenance/HTTP tests plus the real frontend behavior and syntax checks.
The procedural demo and CLI ran locally: explicit output `final` remained selected, the deliberately
conflicting sidecar retained both graph claims, and matching the image hash did not authenticate
either claim. No model or generation service was used. Reports are retained under the primary
checkout's `.runtime/session-2026-09-12/recipe-inspection-demo/`, with test logs in the review
worktree's `.runtime/recipe-inspection-review/`. Windows browser file-selection behavior was not
separately exercised; the author's Linux browser evidence and its fixture boundary remain recorded
in `docs/prompt-studio/INSPECTION-VERIFICATION.md`.

PR #81 merged as `db066ec`. The running Studio served the updated static JavaScript, and its Create
page reached ComfyUI connected with Generate enabled for the ready Anima recipe in the local
browser. The temporary verification tab was closed without submitting anything. Its 12 raw
evidence files were archived with verified hashes under
`primary/.runtime/session-2026-09-12/readiness-status/raw/` before plain worktree removal.

## Confirmed Comfy error timing — 12 September 2026

The #77 follow-up now records a confirmed ComfyUI history error as a failed Studio job before
propagating the existing exception. It persists the observed finish time and computes the Studio
wall interval only from a finite, non-boolean start that is not in the future; legacy or invalid
starts keep elapsed time unknown, and repeated observation preserves the first terminal timestamp.
PR #79 merged as `451a681`. The actual idle reload was verified at 18:10 UTC: Studio PID 1236
reloaded from 31288 while retaining the same 77 terminal jobs, raw state-file hashes and timestamps,
17 projects, ComfyUI PID 10984 and history, with an empty queue. The raw receipt is
`primary/.runtime/session-2026-09-12/timing-reload/after.json`. The full Windows suite ran 781 tests:
768 passed and 13 skipped, using the configured Studio test interpreter. Repository validation and a
fresh independent review passed. The causal test records
60 seconds from Studio start to failure observation, distinct from the fixture's 25-second Comfy
event interval; it fails on the original history-error method and passes on the fix. Transport-loss
and uncertain submissions retain unknown completion times. No historical jobs were backfilled and
no neural failure run was used for this proof.

## Readiness state wording — 12 September 2026

The Create view now keeps ComfyUI readiness neutral while its first health request is pending and
labels failed health requests as unavailable rather than offline. Generate remains disabled until a
known online, schema-ready response with the selected recipe's models present; periodic health
refreshes retain the last known result until their response arrives. The focused VM check covers
pending, online, known-offline, request-failure, recovery, missing-schema and missing-model states
without posting a job. The full configured Windows suite ran 782 tests: 769 passed and 13 skipped;
repository validation passed (60 preset graphs/bindings, 62 pinned assets and 783 tracked paths).
The real Create page was also checked in a browser against an inert loopback fixture serving the
changed static files: pending and unavailable responses disabled Generate, known online enabled it,
a healthy poll recovered from the request failure without a reload, and known offline stayed explicit
and disabled. Every write was rejected by the fixture and its request log recorded zero POSTs.
Test logs are retained under `.runtime/readiness-status/`; browser evidence is under
`primary/.runtime/session-2026-09-12/readiness-browser/`.

## Controlled edits through Studio - 12 September 2026

The local character-edit client can prepare a pinned handoff, stage one ordinary Production
comparison, explicitly request Start, collect a completed Workspace candidate and compose it through
the original write mask. Studio retains ownership of execution, reservations and prompt IDs. The
client pins both the authored catalog entry and raw workflow, independently checks native previews
against the prepared bindings, and rejects compiled instructions over Studio's 8,000-character limit.
Its journal preserves uncertain requests; there is no automatic retry or native-editor layer import.

Author fix `1c13415`, integrated with main `7264134` as `56e2c505`, passed the full Windows suite:
776 tests, 763 passed and 13 skipped. Repository validation passed. These checks include real Handler
integration with inert execution. See [the bridge guide](docs/character-consistency/STUDIO-BRIDGE.md).
The independent review and hosted checks remain recorded on PR #78 rather than inferred from these
local results.

A real boot-trim proposal was prepared and staged with the earlier local client `e409c242` at
`C:/AI/character-lab/scoped-boot-edit-20260912/`. Production project
`98f83d0d3304472f9db5dbc065357aa3` remains planned: allowance 1, reserved 0, no job or prompt ID.
Its 288x488 source context and approved front identity image were uploaded and pinned; the supplied
back view is the review canon. Automatic approval review rejected the Start command as "blocked by
policy" before execution. No candidate was generated or composited, and neural edit quality and
memory improvement remain unverified. The preserved pre-integration handoff uses a different catalog
pin schema from the final client; it is historical staging evidence, not final-client execution proof.
Retain its original journal/project and the adjacent status note; do not reset them for a new allowance.

## Controlled character edits: Windows proof - 12 September 2026

The actor-scoped offline planner and pixel bridge were integrated with main `44fc561` and exercised
on this Windows checkout. The full suite ran 693 tests: 681 passed and 12 skipped; repository validation
passed. An independent review found no remaining Critical/High defect. The known three-actor contact
relationship mismatch is a nonblocking proposal-validation gap tracked in #71.

The real CPU demo prepared and applied a supplied candidate at
`C:/AI/character-lab/actor-windows-proof-20260912/`: 4,032 permitted pixels changed, all 94,272 pixels
outside the mask remained exact in decoded RGBA, and no protected pixel changed. The resulting
384x256 image was inspected. This proves the offline pixel boundary with a synthetic fixture; it does
not prove neural edit quality or a native-app connection. Original context-transparency regressions
are included in the full gate. Native execution remains #71 and measured artistic yield remains #72.

## Character primary-case import - 12 September 2026

An explicit character plan/handoff/upload request can now prepare one primary case through the existing
Production service. Import reconstructs the canonical handoff against current raw catalog/template
bytes, checks approved reference roles and both Studio/Comfy input copies, and stores the case, canon,
handoff and resolved recipe evidence. Separate cases share the study allowance; each remains batch one.
Import queues nothing, and duplicate primary imports are refused. Canon approval is a local attestation,
not reviewer authentication or generated-art acceptance.

The opt-in v2 prompt-scope planner can prepare a matched two-case portrait-edit study using the same
approved canon, reference, FLUX edit route, seed and checks. Its selected-canon case carries only
the requested identity, bodice and style canon text in its positive control while its handoff retains
  the plan's full approved canon identity plus a hash-checked audit of the selected text. This is offline planning
coverage only: no new project, queue item, reservation, prompt ID, generation or art approval is claimed.

Inert direct integration checks proved zero-work import, shared budget, concurrent Start reservations,
restart persistence, duplicate refusal and preflight rollback. Rehashed prompt/binding drift, non-image
routes and changed Comfy input bytes were rejected before project/budget writes. The full suite ran 598
tests: 588 passed and 10 skipped; repository validation passed. One independent review plus its scoped
fix verification found no remaining Critical/High defect. This is the first import seam in #65;
repairs, warmups, review promotion, dependency invalidation and live import execution remain unverified.
The existing database-commit-before-plan-file-write recovery gap is tracked separately in #65.

After the idle Studio reload to `4cb514c`, the actual loopback HTTP importer prepared project
`01fc7329c0406172b3fd512653648d0f` from a separate one-case smoke study using the approved pilot canon
and existing pinned front upload. It remains planned with allowance 1, reserved 0 and no attempts.
The identical import returned HTTP 400 as already imported. All 77 job IDs and Comfy history IDs stayed
unchanged, with an empty queue. No Start or Resume was sent. The live smoke did not repeat a restart;
restart persistence remains covered by the integration checks above. The receipt is retained beside
the pilot ledger and raw proof under `C:/AI/character-lab/pilot-20260912/production-import-smoke-20260912/`.

## Character-consistency offline foundation - 12 September 2026

The character study, archive and media commands now have local Windows integration evidence.
The full suite ran 589 tests: 579 passed and 10 skipped; repository validation passed. The character
subset ran 68 tests: 67 passed, with symlink creation unavailable for one test. Both checks against the
real game-asset brief validator and native preset templates passed. The actual planning CLI produced
the expected 12-case draft; restored-reference preflight retained `submission_authorized: false` with
only the draft canon approval blocker. No model job or reference upload was submitted.

The owner's original ZIP was verified and restored outside Git to
`C:/AI/character-lab/windows-proof-20260912/original/`: all 71 members and 27,336,577 expanded bytes
matched their pinned hashes. All 33 newly extracted crops matched their original source rectangles
pixel-for-pixel. All three source sheets are opaque. The standard review card was composed twice with
identical bytes in this Windows runtime and inspected; crop fragments remain, and it is not a cleaned
sprite sheet. Prior CPU evidence remains attributed to its original session. Raw Windows logs and
draft reports are retained under `.runtime/session-2026-09-12/character-review/`. The live pilot, shared
execution and review/repair work remain in #64/#65/#66. The owner selected the supplied standard costume,
including its shown back view, as the private study canon; this is recorded in `HUMAN_TODO.md` and does not
accept art, clear rights or authorize production use.

The completed twelve-case pilot is curated at `experiments/curated/character-reference-pilot/`; raw
histories, receipts and original PNGs remain outside Git at `C:/AI/character-lab/pilot-20260912/`. It reserved
and recorded twelve primary attempts: eleven completed images and one Qwen `VAEDecodeTiled` CPU-allocation
failure. The failed profile's already-reserved second slot was consumed once by ordinary Studio job
`03903f6a-8e84-43b2-b953-00678167acfb`, which has no `project_id`; the collector's
`c8c05b34c6f7439ebb89aca3978433dc` grouping identifies the reservation source only. It was neither a retry
nor a new credit. Ten completed images are agent-rejected, one requires review, and there are zero agent
selections or human acceptances. The standard back was review canon while one-reference full-figure baselines
conditioned only on the front. Unequal canvas/resolution, cold/warm state and memory conditions make this
unsuitable as an equal-compute benchmark. Current routes are stopped from production promotion; preserve the
evidence and pursue any runtime/fidelity follow-up separately, without additional pilot generation.

## Voice runtime consistency and recovery - 12 September 2026

Prepare and Start now use the configured isolated Python to observe declared distribution versions through
metadata only; the plan retains those observed versions and Start rejects either a bundle-manifest or
Prepare-time drift. This is not a complete-environment hash and imports neither Torch nor a model. Controlled
voice success, failure and cancellation terminalize attempt 0. The Production API can explicitly resume only
a demonstrably unstarted interrupted plan. Both Voice and Production pages expose Resume only when
the backend reports eligibility. Queued plans and any durable request, attempt, job, artifact or voice
directory block resume; no browser action automatically retries inference.

Voice Workspace publication is now marked `published` only after every output is registered. Failed,
cancelled and still-publishing marked voice jobs retain their exact existing asset descriptors on Studio
restart and are not newly indexed; legacy unmarked voice jobs keep the historical indexing path. A stop that
arrives after complete publication is recorded as too late while retaining the published outputs. Inert
version-drift, terminal-state, resume, publication and restart regressions passed. Stop and the final
completion decision now share a lock. Startup reconciles active nested voice attempts to `interrupted`
while preserving identifiers and evidence, and submits nothing. Full integrated suite: 593 run,
583 passed and 10 skipped. Voice recovery UI, late-stop and abrupt-attempt follow-ups are implemented;
real Chromium with inert API fixtures verified explicit Start/Stop/Resume routes, hidden unsafe recovery,
one request on rapid keyboard Resume, and no horizontal overflow at 390 px. The fixture emitted no console
warnings or errors. This does not claim human listening or voice acceptance.

## Voice resume polling snapshot follow-up - 12 September 2026

The interrupted Voice resume eligibility check now snapshots `Studio.jobs` while holding the
Studio lock, then uses that same snapshot for deterministic and metadata job checks after releasing
the lock. The causal regression inserted an unrelated job from an unrelated job's metadata callback:
the baseline raised `RuntimeError: dictionary changed size during iteration` from `production.list()`;
the fixed `production.list()` and `production.get()` remain eligible and the queue stays empty. A
small lock probe also verified snapshot acquisition under lock and metadata scanning after release;
matching voice jobs under nonstandard IDs remain a resume refusal. Focused Voice and Production
discover suites passed: 15 and 13 tests. The configured full suite passed 826 tests (813 passed,
13 skipped), and repository validation passed. Raw command logs, including the baseline failure, are
retained under `.runtime/voice-polling/`; the direct `unittest tests.test_voice_baseline` form failed
at import because this repository's test module imports its sibling without the tests directory on
the module path, while the discover form is the valid proving command.

## Scene editor interaction checks - 12 September 2026

Unsaved clip notices and disabled document actions now update on input without replacing the focused
field or preview video. Commands and manual reloads are serialized; stale polls cannot overwrite a
newer command response. Completion updates the global render status, and artifact links show filenames.
An earlier polling error can still remain in the global message until a manual action (#30).
Chromium 151 with synthetic sources and real FFmpeg verified typing focus, continuing playback,
persisted edits, a held export blocking conflicting actions, download completion and a 390 px layout.
The browser recorded no JavaScript errors, external requests or ComfyUI calls. Full suite: 516 run,
507 passed and 9 skipped; repository validation passed. Raw proof is retained under
`.runtime/session-2026-09-12/scene-interactions/`. The remaining Scene work stays tracked in #30;
`HUMAN_TODO.md` retains optional creative choices, and this proof makes no art acceptance claim.

## Spoken atelier scene and manual repair option - 12 September 2026

The primary Studio explicitly generated “The lantern is ready. Follow the light.” with the isolated
Kokoro CPU baseline, then assembled it with two retained atelier images. Voice job
`5e0982574aa450dd8f8538148fdd67af` produced 2.8 seconds of dry audio (3.187 seconds measured model
load/inference). Scene job `513bd06980514be5930a9aa981caf8cd`, scene
`f14b08eba5e84375a2c604fd4e3db686` revision 2, produced a 720x1080, 156-frame/6.5-second preview with
a dialogue offset and dissolve. No ComfyUI prompt was submitted. Both shots were inspected; the square
shrine source is letterboxed. Browser playback and decoded PCM/frame checks passed. Independent
offline ASR matched all seven normalized words; no human listening or character acceptance is inferred.
Exact recipes and observations are in `experiments/curated/atelier-voice/`; raw output stays outside Git.

The existing manual `anime-masked-repair` graph is now catalogued with RGBA-alpha instructions and
`verified: false`. Upload preservation, binding and live node/file schema checks passed; no masked
repair generation was submitted. PR #67 now enforces a supplied nonempty RGBA alpha mask with dimensions
divisible by eight before any job is created; valid PNG bytes remain unchanged. This does
not imply a successful Krea hand repair: the earlier unsuccessful Gentle digit trial used the NoobAI
portrait. `HUMAN_TODO.md` retains the owner's optional creative choices and model-use decisions.

## Offline CPU voice baseline - 12 September 2026

The Voice baseline page now prepares pinned original-text takes and explicitly queues Kokoro CPU
inference through the existing Production worker. Each take retains its request, model/tool pins,
text/phonemes, logs, partial files and 24 kHz dry/48 kHz scene WAVs with Workspace recipes. Cancellation
owns its processes; interrupted inference is never resumed automatically. The isolated Python3.12.10
environment and model bundle are outside Git and separate from ComfyUI.

A real browser/inference fixture generated and played a 2.85-second original line: 68,400 dry samples,
136,800 scene samples, zero full-scale samples and no JS errors/external browser or ComfyUI calls.
Page load and Prepare did not generate. Six additional dry lines have an offline installation receipt.
This verifies CPU inference and the user flow, not listening quality, acting, voice design, cloning,
alignment or independent transcription. See `docs/VOICE-BASELINE.md`; raw evidence is retained under
`.runtime/session-2026-09-12/voice-baseline/` and `C:/AI/voice-lab-kokoro/metadata/`.
`HUMAN_TODO.md` retains the owner's optional creative choices.

## Shared Scene editor - 12 September 2026

The Studio header and selected Workspace assets now lead to a saved Scene editor. UI, CLI and optional
MCP use one HTTP command service over the Production database, with transactional revision checks,
source snapshots/lineage, append-only history and explicit restore. Existing cut/dissolve/overlay and
audio controls are joined by timeline order/split. Render attempts use the existing owned worker queue,
pinned revisions, configured FFmpeg paths, progress/cancellation and retained incomplete evidence.

A real Windows Chromium 151 fixture exercised a shared UI/CLI/MCP edit sequence, stale rejection with
retained fields, explicit reload, queued rendering, decoded playback, source ZIP download and mobile
layout. It completed a six-second 144-frame/288000-sample procedural preview with zero ComfyUI calls,
external browser requests or JS errors. A later real Chromium draft proof at
`.runtime/browser-proof-1789222397/receipt.json` exercised dirty render, New Scene and current-scene
guards without an extra POST, then stale rejection, reload and a saved edit; its isolated fixture made
zero ComfyUI requests. The disposable-port fixtures adapt only Host/Origin to an ephemeral port; separate
HTTP tests exercise the unchanged product 8191 guards. Full source and runtime evidence is preserved at
`.runtime/session-2026-09-12/shared-scenes/`.

Independent review found no critical/high product defects. Draft fields now visibly identify the saved
revision and block document and scene-navigation actions until each clip is saved or the local draft is
explicitly discarded. A full native scene recipe and receipt are durably written before Workspace
publication (PR #54), so a publication failure retains its provenance and diagnostics. Nonblocking #30
follow-ups remain: draft notice/action-state refresh after the first input, UI response serialization
after reload/export/cancel, cancellation/publication arbitration, and concurrent-export orphan accounting.
Cached waveforms/thumbnails and proxy renders remain future work. See `docs/SCENE-EDITOR.md` for limits
and recovery. No neural audio, native editor parity, licensing or creative acceptance is claimed;
`HUMAN_TODO.md` remains unchanged.

## Model download redirect policy - 12 September 2026

Curated automatic installs now check the original HTTPS source and every redirect before opening
the next URL: provider-specific delivery hosts, port 443, no URL credentials, public DNS answers and
a five-hop limit. Cross-host requests retain only transfer headers; pinned sizes/hashes, exact Range
resume, complete offline partial validation and no-clobber publication remain in place. DNS is
checked before connection, not pinned to the connected peer. The current production opener has no
cookie processor; this is not a guarantee about arbitrary future urllib handlers.

Independent review found no confirmed critical/high blockers. Inert transport fixtures exercise
allowed delivery hops, rejected targets before contact, loops, header stripping, resume and retained
failure receipts. A read-only live HEAD followed a Hugging Face file to `us.aws.cdn.hf.co` with 200;
Civitai returned 403 before redirect, so its current delivery path is not live-verified. No model
bytes, authenticated transfer or model quality were tested by this change. `HUMAN_TODO.md` remains
the source for optional creative choices.

## AV renderer, local utilities and live Prompt Lab - 12 September 2026

The AV workbench slice now runs with a checksum-verified portable FFmpeg 9.0.1 installation outside
Git. A real 640x360/24 FPS procedural preview contains 144 frames and a six-second, 288000-sample
stereo PCM mix. Measured sample peaks are -16.68 dBFS; no full-scale samples were counted. These are
codec/timing checks, not neural voice/music, perceptual loudness or creative acceptance.

Chromium 151 decoded the preview and exercised keyboard gain changes, mute/apply, stale-preview
indication, actual project export, CLI media validation of that export, Web Audio decode/start/stop,
undo and 390 px layout. Source hashes stayed unchanged; no JS errors, external requests or model jobs.
Raw render plans, source snapshots, outputs, browser exports and receipts are preserved under
`.runtime/session-2026-09-12/av-workbench/`. FFmpeg archive/hash/license records are in the adjacent
`ffmpeg-install/` folder; explicit ffmpeg/ffprobe paths are recorded in local config, without global PATH
or ComfyUI package changes. CLI sessions still need that portable bin directory on their own PATH.

Input demuxers are constrained to declared PNG/MP4/WAV formats, with image patterns and MOV external
references disabled. The initial review HIGH was withdrawn: FFmpeg 9.0.1 rejected the proposed HLS
filename mismatch. An inert ffconcat probe did read an undeclared relative segment; the constrained
MOV probe rejected it, but render exfiltration was not demonstrated. This is input-contract hardening,
not a claim of proving the original HIGH. Three nonblocking workbench limitations remain tracked in
#30: source-range edits need media validation, embedded audio needs an aggregate cap, and Python/JS
half-sample rounding differs at some fractional rates.

Against main `4796a87`, the full dependency-equipped suite discovered 473 tests: 464 passed and nine
skipped (five native opt-ins and four Windows directory-symlink cases). FFmpeg and actual MCP SDK tests
ran. The first full run exposed an inherited HTTP redirect test fixture closing with an unread POST
body; draining it and declaring a zero-length response fixed the Windows reset. The rerun and validator
passed. No production helper behavior changed for that fixture correction.

PR #33 is merged as `4796a87`. The primary Studio was reloaded through the supported launcher after
verifying terminal jobs, idle production and an empty ComfyUI queue. Live Chromium navigated from the
main header, loaded all nine profiles and compiled a brief with unchanged job IDs. ComfyUI PID 2600
was preserved. No art or rights choices were inferred; `HUMAN_TODO.md` remains the creative backlog.

## Prompt Lab normal startup and browser proof - 12 September 2026

Prompt Lab now uses the normal Studio launcher and its existing port. Startup binds before
constructing a Studio worker, and the compatibility script delegates to that same entry point.
The header links to Prompt Lab. A broken profile-response callback was also repaired; its real-script
regression fails on the old page and passes on the fixed page.

On current main `83b77ac`, the dependency-equipped Windows suite discovered 441 tests: 433 passed,
eight skipped (five explicit native opt-ins and three directory-symlink privilege cases). The repository
validator passed. Independent Terra review found no remaining HIGH/CRITICAL defect after the callback
fix. The LOW proposal-separator encoding defect is tracked for later polish, not a generation blocker.

Chromium 151 loaded all nine profiles and exercised custom brief compilation, actual compilation and
brief downloads, stale-export invalidation/recompile, keyboard edits and 390 px layout with no JavaScript
errors, external requests or generation submissions. The fixture used the actual server factory and
HTTP handler with an inert Studio; only the accepted loopback port was adjusted for an ephemeral test
port. Separate HTTP tests verify the unchanged production Host/Origin guards. Raw evidence is preserved
under `.runtime/session-2026-09-12/prompt-lab/`. Live primary launch is checked separately after merge.

PR #44 is merged as `83b77ac`. The primary local config now names the bundled Node executable and
has the locked Khronos npm dependency installed. The native evidence worktree was removed after its
receipts were preserved. Art, model licensing and q-3 creative choices in `HUMAN_TODO.md` remain open.

## Runtime safeguards and local native-engine proof — 12 September 2026

Runtime/install safeguards PR #41 merged as `e279509` after current-base CI and a fresh independent
review with no blocking defects. The Windows dependency-equipped suite discovered 328 tests: 325
passed, three directory-symlink privilege skips. Read-only runtime checks identified the actual primary
listener and idle queue, and found all required primary/HiDream/H3 files. No backend switch or model
download was performed for that verification. Redirect transport policy remains tracked in issue #48.
Receipts: `.runtime/session-2026-09-12/runtime-safety/`.

The native-engine adapter ran **all five opt-in tests on this PC's configured Godot 4.7.2**, Node
24.19.0 and locked Khronos glTF validator 2.0.0-dev.3.10, with no skips. Actual loops and one-shot
completion retained the four ordered frames and completed at 479.1667 ms of simulation time against
480 ms authored timing. Animated GLB pose/material checks, skin inventory and tamper rejection passed;
an invalid accessor was rejected by Khronos before Godot startup. Headless tests do not establish
rendering performance, visual quality, collision/root-motion correctness or gameplay acceptance.
The GLB tamper test deliberately leaves its packaged copy modified; that fixture is not an approved
export. Local reports, logs, runtime executable hash and source fixtures are preserved under
`.runtime/session-2026-09-12/native-evidence/`. Primary runtime configuration is a separate setup step.

Repair actions and the Gentle trial landed in PR #47 (`fb0d38d`). Its code/CI checks passed, but the
merge happened 160 seconds after the final push, **20 seconds short of the required 180-second age**.
That waiting gate was unmet and is recorded on the PR; subsequent merges check a persisted push time.
No human creative choice or rights clearance is implied by these changes; see `HUMAN_TODO.md`.

## Review desk and direct correction handoffs — 12 September 2026

PR #43 is merged as `4b6b94e`: completed image comparisons can open a revisioned Review desk with
stable blind aliases, matched crops, reversible assessments and checksummed evidence packs retaining
rejected candidates. The integration against `23f08718` passed 269 discovered tests (267 passed, two
Windows directory-symlink privilege skips), catalog validation and hosted Ubuntu/Windows checks.
An independent review found no blocking defects. Actual Windows Chromium 151 exercised direct localhost
fixture transport, stale-edit rejection, draft/download preservation, ZIP hashes, restore, keyboard and
390 px layout; no generation occurred. Six separate real-Handler HTTP tests passed. This is review
infrastructure proof, not art acceptance. Evidence is retained under `.runtime/session-2026-09-12/review-desk/`.

Gallery images and Workspace image details now expose **Fix hands & face** (`anime-detail-fix`) and
**Refine image** (`krea-refine`). Both use the existing reference-copy/lineage path and await an explicit
Generate action. Node behavior checks exercised both entries through save/submission and kept repair
actions off video assets. Windows browser checks used the running Studio APIs with the exact changed
static files: all four handoffs retained source identity and reference filenames through saved-setup
readback; the temporary QA setups were removed. Desktop and 390 px mobile views were captured, mobile
inspected, with no JavaScript errors or generation calls. Receipts: `.runtime/session-2026-09-12/repair-actions/`.

The browser driver needed two corrections (its route callback signature and waiting for the exact
reference-copy response); the corrected run passed. These were QA-driver failures, not Studio failures.
The separate **Gentle (denoise 0.3)** trial then completed on the authored 832×1216 NoobAI example
in 42.280 s: job `e4e49006-fb1b-419c-8045-fe54d1ddeb12`, prompt
`a31964f3-3ba7-47f5-a6bd-e6fbd22ce9ea`. Both passes ran at 0.3 with seed 2026091201.
The inspected result sharpened the face but retained an extra digit: completed execution, failed
hand-repair objective, no human art approval. Exact recipe, hashes and the unaltered PNG are linked
from `experiments/curated/anime-fantasy-atelier/README.md`. The catalog defaults are unchanged.
The optional creative choices, including the Anima look selection q-3, remain in `HUMAN_TODO.md`.

## Civitai access, Anima baselines and the correction pass — executed (12 September 2026, second pass)

**Runtime (outside Git, recorded here and in `runtime-patches/README.md`).** The owner's civitai API key is stored as
the user-scope environment variable `CIVITAI_API_TOKEN` (never in the repo). ComfyUI now starts with
`--enable-manager` (`comfyui_manager` 4.2.2 installed into the embedded Python, only new packages added;
`GET /v2/manager/version` → `V4.2.2`) and loads `custom_nodes/civitai-comfy-nodes` (223 Civitai nodes; the pack reads
the same environment variable, so no key is typed into its panel). ComfyUI PID in `C:/AI/comfyui.pid`.

**Installed with SHA-256 receipts** (`.runtime/downloads/receipts.json`, pinned in `models/library.json`): the Krea 2
koukouya adapter (HUMAN_TODO q-1 closed), Anima adapters xilmo, huashijw, koukouya, NEWANIMASTYLE, and the official
Anima turbo LoRA. ke-ta, kieed (LyCORIS) and, after a 105-minute throttled Hugging Face download, the 4 GB `anima-base-v1.0` checkpoint all
landed with verified receipts (the checkpoint's hash matches the civitai listing), so every file the Anima presets name is installed.
Background download logs: `.runtime/downloads/civitai-retry2-2026-09-12.log`, `anima-base-retry-2026-09-12.log`.

**Executed and inspected** (`experiments/curated/anime-fantasy-atelier/`, JPEG copies in `examples/anime-fantasy-atelier/`):

| Run | Result |
|---|---|
| `krea-anime-atelier`, full target stack TextFusion + Niji Sweet Spot + koukouya, 15 steps, 832×1248 (job `7d589f47`) | 827.6 s; the closest match yet to the owner's target image; koukouya's brushwork dominates |
| `anime-detail-fix` on the NoobAI portrait with the six-finger hand (job `14caa4fb`) | 36.2 s; hand repainted to five clean digits, eye opened and sharpened; only the two crops changed |
| `krea-refine` on the style-lab fox shrine (job `21e4a629`) | 233.2 s; fox faces are fox faces again, composition kept; the third fox merged into the pair at denoise 0.35 |
| `anima-artist-stack` graph as ComfyUI probes on anima-aesthetic-v1.1: four adapters, then all six (kieed is LyCORIS) | 35.0 s and 25.0 s; clean witch portraits, no LoRA key warnings; proves the six-slot chain, the LyCORIS load and the loader path, not the base v1.0 look |
| `anima-artist-stack` on Anima base v1.0 as authored, the artist-tag variant and the 1328×1776 reference variant (jobs `8a593206`, `8eb5bc19`, `6ae066d8`) | 24.3 s, 20.1 s, 66.4 s; all clean, no anatomy errors; the artist-tag runs hallucinate a small signature glyph bottom-right |

**Contract change.** `CONTROL_KEYS` and `LORA_SLOTS` now run to six slots (`lora5`, `lora6` and their `_name` twins) in
the server, planner, validator and UI; the six-slot rows were confirmed in the running UI's DOM (Slot 1–6).

**New presets.** `anima-artist-stack` (Anima base v1.0, six `LoraLoaderModelOnly` slots at the reference strengths,
variants for the 1328×1776 reference, the adapter-free artist-tag look, the turbo audition), `anime-detail-fix`
(Impact Pack FaceDetailer face pass then hand pass with the installed `face_yolov8s` / `hand_yolov8n` detectors, WAI v17
repaint), `krea-refine` (Qwen-VAE img2img polish with the 4-step distill LoRA). Recipes: the six-adapter reference,
the painterly artist tags, the dark sci-fi comic warrior (Krea 2, no adapter), and the target stack now names koukouya.

**NOT verified.** `anima-artist-stack`'s turbo and half-strength variants; the `krea-dark-scifi-comic-warrior` recipe; the
detail-fix/refine variants beyond the authored defaults; the Civitai panel sign-in and downloads; the Manager UI beyond its
version endpoint; the Krea 2 Q5 GGUF (partial download left in place).

**Owner's creative review** of the first atelier pass is recorded in `HUMAN_TODO.md` (q-2 closed) and the guide.

## Anime & fantasy atelier — executed (12 September 2026)

The Studio now has four LoRA slots per preset (a slot at strength 0 is pruned from the submitted graph),
an installed-LoRA and sampler options endpoint, a sourced settings knowledge base with a grid/remix planner,
named recipes, prompt wildcards, two new Krea 2 Turbo presets (`krea-anime-atelier`, `krea-style-lab`),
corrected SDXL anime grammars with clip-skip for Pony, download/intake scripts and the
[atelier guide](docs/ANIME-FANTASY-ATELIER.md). 31 Krea 2 adapters were installed from Hugging Face
with SHA-256 receipts (official Comfy-Org styles, 21 fal styles, the 4-step distill LoRA, TextFusion
refusal-reduction and Niji Sweet Spot mirrors) and pinned in `models/library.json`.

Executed and inspected, all on 12 September (details, hashes and recipes in
[experiments/curated/anime-fantasy-atelier](experiments/curated/anime-fantasy-atelier/README.md)):
Krea 2 Turbo + NIJISIS at the reference image's settings (768×1152, 15 steps, euler_ancestral/simple,
prompt `09dadd6e-3e60-4c37-80d1-9244bb8e848d`, 986.6 s); the reference's TextFusion + Niji Sweet Spot
stack (`412b3c9f-162b-434b-a2a6-e57635f82da1`, 941.2 s) and the same stack with the 4-step distill LoRA
(`d7bd3104-f348-46e6-811e-3b1d918c75c3`, 270.9 s, comparable quality); `krea-anime-atelier` through a
Studio job (`db02f6b1-8346-4361-a432-7734fc72d2c2`, prompt `150cde70-459e-4beb-b2a3-cb6f6631eb17`, 197 s
at 4 steps, NIJISIS slot pruned); and the `wai`, `noob`, `anime` and `pony` fantasy-portrait variants
through Studio jobs (26–30 s each at 832×1216, both LoRA slots pruned). Those five presets are
`verified: true` for exactly those graphs. One probe (`af39c7de-8bad-47d5-a9ba-8e3333ef8573`) failed with
a HIP out-of-memory at 768×1152 after several Krea runs in one ComfyUI process, and the secondary
exception killed ComfyUI's prompt worker; ComfyUI was restarted and the failure is recorded, not repeated.

Not executed: the koukouya LoRA from the reference image (civitai login required; HUMAN_TODO q-1),
`krea-style-lab`, the recipes marked `unverified`, the planner-driven comparisons (the plan route was
exercised without reserving budget), the Krea 2 Q5 GGUF speed comparison (download in progress), and any
art acceptance — [HUMAN_TODO.md](HUMAN_TODO.md) keeps the creative choices open.

**Correction, 12 September 2026 (the paragraph above stands as written; these two entries were already
overtaken when it was written).** `krea-style-lab` *was* executed: Studio job
`f373ba3b-3f88-4cdb-8bc2-bc4afa36d67e`, prompt `cc0ede07-97b9-4549-ba46-6b02e6ec18bb`, 207.119 s at
1024×1024 / 4 steps with `fal-krea2-airy-anime-watercolor` + the 4-step distill LoRA at 0.85; output
`f66874e6…`, inspected, and the preset is `verified: true`. The owner reviewed that image the same day
(HUMAN_TODO q-2: "nice from afar but the foxes lose detail and their faces morph"), which is what
`krea-refine` job `21e4a629` was then run against. The koukouya LoRA was likewise installed and executed
later that day — HUMAN_TODO q-1 is closed, `models/library.json` carries the pin, and job
`7d589f47-7172-44fb-9541-4ab0602eafce` (827.6 s, 832×1248) is the full target stack including it.
Both records are in
[experiments/curated/anime-fantasy-atelier/execution-evidence.json](experiments/curated/anime-fantasy-atelier/execution-evidence.json).
Still not executed from that list: the recipes marked `unverified`, the planner-driven comparisons, the
Krea 2 Q5 GGUF speed comparison, and any art acceptance beyond the owner's recorded q-2 remarks.

## Creative production milestone

Studio now has **54 recipes**, a persistent asset Workspace, role-guided Qwen
references, bounded comparisons, native exports, and explicit model-environment
switching. Models and operational outputs remain outside Git. HiDream concept
and reference-restyle recipes both produced 2048-square PNGs through Studio:
184.697 seconds and 76.260 seconds respectively, at eight steps. Their distinct
loading/cache conditions are not a model benchmark. See [HiDream](docs/HIDREAM.md).

The comparison `fbb384c70a5e48b39a9eba6c227374eb` completed both Anima seed stages
and awaits creative review. Imported originals can now join collections and
native exports without generation. Browser-selected sprite frames produced
Godot project `d62777fdd019462b99d28357e61393b8`: actual import/playback retained
120/80/120/160 ms, 64-square canvases and anchor [32,32]. An earlier export
`df007b4d33d8465695615535e004be4d` exposed a form-serialization bug (100 ms values);
that bug is fixed and the corrected plan and engine evidence were checked.

The authored chest UI built project `db662bb6e60f42c781e001bd681b9743`, retaining
BLEND, animated GLB and four CPU inspection renders. The first GLB exposed a
hidden collision helper as visible geometry; the exporter now excludes it from
GLB while retaining it in BLEND. Fresh project `44cfa4a0b29a43098d6c7c7609ca6831`
completed with the four intended parts and named hinge animation; its renders and
browser preview were inspected. Native jobs persist before Blender. Recovery
requires a successful exit log and refuses recorded failure evidence, without
repeating a build; focused fault tests pass.

Krita is now an option in the native-export dialog. Browser project
`e563585717324f54aa57e6fc9bd9f773` selected two existing 64-square frames, retained
both requested layer names in KRA, reopened to PNG and produced a complete source
pack. The isolated offscreen crash and successful hidden Windows batch proofs
are preserved. This proves flat native layers, not automatic part segmentation.

H3's opt-in stdlib mmap loader constructed all 2,054 encoder tensors and the
MiniMax encoder model in 6.65 seconds (process peak working set 4.14 GiB). CUDA
was initialized by the runtime; this was construction, not inference proof. The
first video attempt with copy-on-write mapping passed encoder loading, then
failed in UNETLoader with Windows error 1455 (commit/pagefile exhaustion), prompt
`cce6da2a-0978-4c98-95d7-1c7ba8274a7c`. The machine has a 40 GiB paging file.
A read-only encoder attempt also reached the same diffusion-file error, prompt
`af49ef6a-433e-47eb-95d1-0efe7cb9ef52`. Extending the exact-file read-only loader
to the FL2VA diffusion file then constructed MiniMaxH3/legacy ModelPatcher in
5.603 seconds, with 4.30 GiB peak process working set. The subsequent short video
prompt `49873807-fda1-4fe0-afdd-62b13f5329d8` completed in 398.096 seconds:
39 H.264 frames at 512×320 and 32 kHz stereo AAC, both 1.625 seconds. All frames
and audio decoded; first/middle/last frames were inspected. The tested defaults
now match the executed graph. No system paging settings changed. The normal
native loader remains incompatible; use the [isolated H3 route](docs/H3-WINDOWS.md).

The broader research backlog is still open: Seed Hunter dependencies/execution,
shot-continuation/control comparisons, interactive Krita diffusion, automatic 3D
part/rig experiments and the full accepted character-pack vertical slice. The
completed native exports are scoped engine checks, not art or gameplay acceptance.
[HUMAN_TODO.md](HUMAN_TODO.md) still holds the optional subjective choices.

**149 tests pass**, with one existing Windows symlink skip; the 54-preset catalog
validator and changed JavaScript syntax checks pass. Independent reviews caught
and resolved recovery/provenance defects. Gallery handoffs now retain the source
asset identity and populate Qwen's first reference slot. The browser saved
`Ember chest → Qwen reference` with the correct parent and hashed input metadata;
no extra generation was submitted. Comparison planning also rejects numerically
equivalent values before reserving runs, so `1`, `1.0` and `1e0` cannot consume
duplicate candidates. The branch is pushed as PR #39; this is a scoped
milestone, not completion of every research issue. See the [usable routes, execution
records and issue-by-issue remainder](docs/PRODUCTION-WORKSPACE.md). The completed
worker worktree was removed after preserving its ignored runtime receipts.

## Earlier checkpoints during this implementation pass

The user requested an ambitious implementation pass across merged PRs **#20**
(game-asset planner, reference graphs, atlas/ORA tools) and **#8** (frontier research).
They are now the branch base `f6e046b`; work continues on
`codex/creative-production-workspace` with incremental commits and one writer.
The original Workflow Lab evidence below remains scoped to its recorded runs.

First implemented slice: a persistent Workspace view with collections, search,
media filters, favorites, tags, review notes, multi-select, recoverable Trash/Restore,
image-to-workflow handoffs and ZIP exports containing snapshots, recipes and metadata.
SQLite and immutable hashed media live under the configured shared experiments
directory, outside Git. Original ComfyUI outputs are preserved. Saved setups now
live on the server, with browser-local migration. Read [the workspace guide](docs/WORKSPACE.md).

Startup identity is independent of ComfyUI; the launcher reuses an existing Studio
even when its backend is unavailable. Full node discovery is cached for 120 seconds
with an explicit refresh. Uploads are decoded/verified, capped at 40 megapixels,
and retain original dimensions and SHA-256 metadata.

Verified at this slice: 106 tests pass (one existing Windows symlink availability
skip), catalog validator passes, both JavaScript files parse, and launcher syntax
parses. Actual browser actions created a collection, assigned an existing Anima
render, saved tags/notes, moved it to Trash and restored it. The new store indexed
46 existing outputs; no generation was submitted. Wider browser checks and
independent review are in progress. Review states remain unreviewed unless the
user explicitly changes them; the optional choices in [HUMAN_TODO.md](HUMAN_TODO.md)
remain open.

Outstanding work in the active goal: role-specific Qwen references (#21), bounded
experiments and trusted stage execution (#10/#22), isolated HiDream integration
(#2), H3 loader compatibility (#18/#11), shot/control experiments (#12/#13),
native editing and engine exports (#14–#16/#23–#25), and accurate source/terms
metadata (#9/#26). Research entries are not automatically executable or accepted.
The secondary workspace request has an implemented foundation; it is not a claim
that the broader production goal is complete.

The next increment adds three Qwen Atelier API/visual pairs (52 presets total),
with one/two/three role-specific references, preserved aspect, byte hashes, a
resolved-graph preview, and saved-reference recovery. See
[Reference atelier](docs/REFERENCE-ATELIER.md). All three pass live node/file
validation without submission. Browser upload and preview succeeded with
identity, pose and manga-style references; controlled generation
`c8b752b5-cb25-4438-8c66-f0e5fafcae04` is being observed, not yet accepted.
The saved Anima-to-ESRGAN handoff survived a fresh page and generated successfully
as `60949ec3-2ec2-471f-88cb-73fa78a5491c`, retaining its parent asset.

**Correction to the three Qwen Atelier pairs (2026-09-12, issue #21).** Those graphs
shipped with node 5 as `ImageScale(width=512, height=0)` and node 10 as a `VAEEncode`
of that shrunken primary reference used as the sampler latent, and only slot 1 was
scaled at all. Reference detail was therefore discarded before encoding, and the
canvas followed each reference's aspect instead of being chosen. The graphs now give
every slot its own `ImageScaleToTotalPixels` at 1.0 MP and take the latent from an
explicit `EmptySD3LatentImage(832x1248)`; prompts say "Picture N" because
`TextEncodeQwenImageEditPlus` injects exactly those tokens. All three presets are back
to `verified: false`. Prompt `c8b752b5-cb25-4438-8c66-f0e5fafcae04` stays recorded, but
it is evidence for the superseded geometry only and now lives in the preset's `history`
field. **No generation has been run against the new graphs.**

Godot adapter commit `af4ccb5` adds actual headless import/playback. Its fixed
120/80/120/160 ms QA sequence played in 480.000003 ms with anchor [24,60] and no
anchor error. The existing Ember GLB loaded with 12 nodes, 9 meshes, 3 materials
and `Lantern bob rigAction`. This is scoped engine evidence, not rig, collision,
root-motion or art acceptance. Evidence is retained locally under
`.runtime/godot-adapter-evidence/qa-480ms-godot-4.7.2/`.

The production runner now prepares pinned one-axis comparisons, uses the existing
Studio worker, reserves generation budgets across branches, and persists stage
identities and known prompt IDs. Fault-injection tests cover lost responses,
restart observation without duplicate submission, shared caps and changed plans.
Workspace can prepare timed atlas, flat ORA and Godot exports with native source
ZIPs. Actual engine verification is an explicit export option. Read
[Experiments](docs/EXPERIMENTS.md) and [Native exports](docs/NATIVE-EXPORTS.md).
At this increment, 126 tests pass (one existing skip); browser preflight and Start
created comparison `fbb384c70a5e48b39a9eba6c227374eb`, currently being observed.
Native export UI round-trip remains pending.

The three-reference Qwen run above completed: **1334.646 seconds**, 512×768,
four steps. It produced a manga portrait with the requested extended hand and
compass; design fidelity and subjective acceptance remain open. Only the
three-reference recipe's execution badge was updated. One- and two-reference
variants have schema/preview proof, not fresh inference proof.

## Changed

Workflow Lab expands the Studio to **49 presets, 49 visual ComfyUI workflows and
50 API graphs**. The 20 additions cover manga line art, screentone, cinematic
lighting, Anima Aesthetic 1.1, free Krea 2 retro anime, MiniMax H3, Wan 2.2,
Hunyuan3D 2.1 and TRELLIS.2. Portrait/environment, preview/quality,
reference-image and seed-audition variants expose the relevant controls.

The three UI views are Create, Models & folders, and Workflow lab. Model paths,
dependency inspection, pinned downloads, named setups, exact recipe import,
image comparison, image-to-video/3D handoff, MP4 playback and an interactive GLB
viewer are available. Selection, import and page load never submit a generation.
A separate Generate action queues work serially.

All **22 curated expansion assets** finished installation with matching SHA-256
receipts. The 20 new native graphs pass the running ComfyUI node schemas with no
missing file selections. Weights remain outside Git. The existing H3 diffusion
download is hard-linked into `models/diffusion_models`, avoiding a second 20 GB copy.
Its companion encoder, video/audio VAEs and Turbo LoRA are installed as well.

The desktop shortcut now launches this checkout. Local config points at the
original `C:/Users/jekyt/source/local-asset-studio/experiments` so its 18 existing
jobs and uploads remain available. Source files in that checkout were preserved.
The launcher detects another Studio workspace on its port before reusing it.
Services remain loopback-only: Studio 8191, ComfyUI 8188.

The user chose **free alternatives** to the 1,000-Buzz NIJISIS LoRA; no Buzz was
spent. Krea Turbo FP8 plus the official retro-anime adapter is a different recipe
from the linked Krea Raw INT8 / NIJISIS example. The user confirmed eligible
territory use for H3. Subjective choices remain open in [HUMAN_TODO.md](HUMAN_TODO.md).

## Verified

Runtime: RX 9070 XT 16 GB, 32 GB system RAM, Windows ROCm 7.2.1 / Torch 2.9.1,
ComfyUI 0.35.0 at `40c4fcdf513a4523e39d54a9d391908af8df8171`.
These are single observations at the listed controls, including different amounts
of model loading and caching; they are not comparative speed rankings.

| New route | Observed execution | ComfyUI prompt ID |
|---|---|---|
| Manga Line Art portrait | PNG, 512×768, 20 steps, CFG 5, adapter 0.8; 34.15s | `6e37e90d-ef45-4e07-af31-045b4938fe53` |
| Anima Aesthetic portrait | PNG, 512×768, 24 steps, CFG 4; 20.01s | `6d136e16-132f-4964-a07b-988a2a34b5ac` |
| Free Krea retro-anime portrait | PNG, 512×768, 8 steps, CFG 1; 188.67s | `144048d4-d6ea-4142-87f5-bdf11d87031c` |
| Hunyuan3D Draft | GLB, octree 128, 20 steps; 36.88s | `ba5ce9da-f6e5-4322-8f73-d56980ef61d6` |
| Wan Animate Image | MP4, 512×768, 33 frames at 24fps, 20 steps; 141.77s | `460ed2dd-1a6b-45e1-9374-ac130595517c` |
| TRELLIS automatic cutout | GLB with UVs, base color and metallic/roughness textures; 74.89s | `5f53db1c-574b-4754-94d5-51d5428729a3` |
| TRELLIS transparent reference | Same PBR stages, actual alpha matte, padding 1.1; 83.48s | `79e4362c-8bcb-4695-9222-e48eb6eecee3` |

The seed was 2026091103, except the transparent-reference trial used 2026091104.
The three images were visually inspected. The Hunyuan
GLB has one mesh, 80,924 triangles and no textures; it rendered in the embedded
viewer. Wan's MP4 decodes to 33 frames, reports 1.375s in the browser, and its
media endpoint returned the requested 1,024-byte range with HTTP 206. ComfyUI
automatically fell back to tiled VAE decoding after ordinary decoding ran out of
VRAM. A sampled video frame was inspected; long-shot consistency is not established.

TRELLIS first failed in the native GPU FP64 UV solver. A local two-line
[CPU UV compatibility patch](runtime-patches/README.md) selects ComfyUI's existing
NumPy solve for small charts while retaining GPU segmentation and PBR baking.
The original runtime source is backed up; patch reversal passes `git apply -R --check`.
Both subsequent PBR trials completed, but both invented a large ground plane.
A separate mask/crop probe confirmed correct foreground isolation. The real
transparent starter is now `examples/references/studio-lantern-cutout.png`;
the old RGBA PNG had an opaque alpha channel and is not used as the matte example.

The explicit Blender finishing script trimmed 3.5% from the bottom of the second
mesh and reduced it from 939,564 to **80,335 triangles**. The resulting 9,944,176-byte
GLB retains UVs and both PBR textures and was inspected in the Workflow Lab viewer.
The cut can leave an open base; this is a useful draft, not game-engine acceptance.
Original 24+ MB generated GLBs remain in ComfyUI output. Exact source/output hashes
and finishing settings accompany the small curated export.

Small selected outputs and exact recipes are in
[the curated execution record](experiments/curated/workflow-lab/README.md).
Only the individual new presets that completed have the Executed badge.

Browser interactions inspected an H3 visual workflow (15 nodes, five weights,
no missing dependencies), imported an exact manga recipe, saved/restored a
three-seed setup, attached a generated image through Animate, and submitted the
known video/3D jobs. Reload and inspection did not create extra jobs. Create and
Models views fit a 390px viewport without horizontal overflow. Final browser checks
played the Wan clip through to its end, exercised keyboard orbit on the trimmed
3D preview, and reported no browser warnings or errors.

Twenty-two regression tests and the catalog/payload validator passed before final
closeout. Twenty native expansion graphs passed live node/link/enum validation.
Independent adversarial review found recipe-import drift and unbounded media
buffering; both were fixed and the follow-up review found no remaining blocker.
Recipe imports verify the embedded graph and guard against a changed template
before submission. Media streams in bounded chunks and preserves Range responses.

Earlier evidence remains valid at its original scope: the original 20 simple
presets were exercised, the Lanternkeeper example includes 96 frames and three
animated GLBs, and isolated HiDream O1 FP8 produced 2048×2048 in an eight-step run.
The five anime finishing graphs were schema-checked and CPU detector/upscaler
probes passed; this expansion does not turn them into new art acceptance.

## NOT verified

Hunyuan Detail, new environment variants, screentone/cinematic adapters,
Wan text-to-video and longer shots have not received
separate execution or quality comparisons. Presence and schema validation alone
do not prove GPU compatibility.

MiniMax H3 produced **no video**. Two accepted tiny trials crashed the ComfyUI
process with Windows access violation `0xC0000005` in text-encoder loading:
`c36094f8-04bd-4673-8020-07e3940e4df6` and
`239417ce-136a-49d7-aa44-98950646df85`. The second used a fresh process with
`--disable-mmap`; it still failed. A CPU safetensors-header/tensor-access probe
completed but does not prove full inference compatibility. The flag was reverted,
the failures were reconciled from logs, and neither uncertain job was repeated.
Local `runtime_blocks` disables H3 submission while retaining its visual graphs.
The compatibility follow-up is tracked in
[issue 18](https://github.com/Chris0Jeky/local-asset-studio/issues/18).
Logs: `C:/AI/logs/20260911-154507-error.log` and
`C:/AI/logs/20260911-162226-error.log`.

The exact Seed Hunter 1.6 JSON was recovered through Civitai's public no-credit
endpoint and its SHA-256 matched official metadata. It is saved in
`workflows/community` and ComfyUI's `Studio Workflow Lab/Community` folder.
Static inspection found 154 nodes, 24 missing node classes and three additional
missing weights. Its custom-node code was not installed and the graph was not
executed. Native H3 variants do not establish its continuation, latent-upscale or
interpolation behavior. Provenance and the full dependency report are beside it.

Qwen's 40-step preset, FLUX.2 dev 32B Q4 inference, higher-step/reference-edit
HiDream comparisons, character-LoRA training, faithful animation in-betweens,
Krita integration and game-engine imports remain outside this completed expansion.
The FLUX.2 weights and Mistral encoder are already installed and checksum-verified.
Fresh-machine setup and broad browser coverage are not claimed.

## Residual risk

Heavy model switches can exhaust RAM/VRAM or crash Windows ROCm. H3 is blocked
locally after direct failures; untested settings remain experiments. The curated
installer preserves 20 GiB headroom, verifies before exposing the final filename,
and leaves interrupted partial downloads for an explicit resume.

Successful outputs are drafts: image anatomy, identity consistency, mesh topology,
UVs, materials, rigging and commercial suitability still need review. Anima weight
terms are non-commercial; Krea/H3 and third-party adapters have their own terms.
NoobAI remains hobby-only, and WAI mirror provenance is not creator authentication.

[Workflow Lab guide](docs/WORKFLOW-LAB.md) explains folder placement, the free
alternative, pipeline controls, sources and recovery. The implementation branch is
`codex/studio-workflow-lab`, based on `6bd4e5b`; final Git/CI status is reported with
the handoff. [HUMAN_TODO.md](HUMAN_TODO.md) contains the optional creative choices.

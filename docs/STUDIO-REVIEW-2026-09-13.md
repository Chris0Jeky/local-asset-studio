# Studio assessment — 13/14 September 2026

A full-scope assessment of the two-day burst of work (106 PRs merged between #19 and #224, then #226 and #240 during
the assessment), requested by the owner: correctness, validity, consequence and value of the changes; progress toward
the stated goals; which routes and tools are proven; the state of the ComfyUI agent tooling; and documentation.
Method: one coordinator (Claude, Fable 5.1) plus 34 read-only Opus 5 subagents in three phases: a goal/route/docs map,
six adversarial seam reviews, and refutation votes on every high or medium finding. Every claim below was measured on
the owner's PC at `main` `28cfe3b` (later rebased onto `be14fa4`) unless it names another source. Nothing in the
audit phase edited the repository or submitted a generation; the fixes are separate commits named at the end.

## Runtime reality at the start

| Fact | Value |
| --- | --- |
| ComfyUI | 0.35.0 on `127.0.0.1:8188`, `--reserve-vram 0.6 --disable-pinned-memory`, queue empty, 15.6 GiB VRAM free |
| Studio | online on `127.0.0.1:8191`, worker alive, recovery healthy; the process dated from 15:43 on 13 September, before several merges (see "Stale server") |
| Host | 32 GiB RAM, about 5.5 GiB physical free; commit 95.7 GiB total, 47.9 GiB free with Codex, three Claude sessions and Chrome open |
| Repository | clean, no open PRs at start, 48 open issues; Codex opened and merged #226 and #240 during the assessment |
| Full suite | `python -m unittest discover -s tests`: 1674 tests, 54 skipped, 139 s, one transient `WinError 10053` error that passes 3/3 in isolation (#227); a clean re-run by a subagent passed |
| Repo validation | `python scripts/validate-repo.py`: PASS, 66 graphs, 121 pinned assets, 86 LoRA names |
| Live graph validation | `python scripts/validate-live.py`: 66 of 66 checked, 63 pass; failures are AniFox (not downloaded) and the two HiDream presets (isolated backend) |

## Verdict on the last two days

**The core contracts are sound and the recovery discipline is exceptional.** Six independent reviewers, each trying to
break a seam, converged on the same picture: a durable `pending_submission` marker before every POST; `_run` refusing
any job not provably never-submitted; no GET path able to submit; loopback Host plus same-origin checks that hold;
parameterised SQL and revision-conditional writes with immutable receipts in the Workspace; reversible trash; a
download-contracts module (HTTPS-only, provider allow-lists, DNS checks, bounded redirects, hash-then-hardlink) that is
the strongest code in the repository; a catalog-to-graph binding contract with zero defects across 66 presets on every
mechanically checkable dimension; and #224's mixed-batch recovery (request-id idempotency, compare-and-set revisions,
evidence hashes re-checked around every history read). The 33 findings that survived included no data-loss, no
duplicate-submission and no traversal defect. That is the property this codebase guards hardest, and it holds.

**Where it is fragile is the exit from a recovered state.** All the recent effort went into classifying uncertainty
and almost none into discharging it. A job whose recorded submissions were all terminal could never leave
`uncertain`/`partial` from the Gallery, and because `uncertain` counts as active work it silently disabled backend
switching for good. Resuming observation of a prompt that a restarted ComfyUI no longer knows cost 24 minutes of the
single worker and landed back in `uncertain`; the two uncertain jobs on this machine were exactly that shape. Both are
fixed (below).

**The cost of speed shows in metadata and skew, not in code.** The `verified` flag had drifted in both directions
(ten presets flagged with no recorded run; seven with completed runs but no flag); a status doc told the owner three
installed checkpoints were still missing; the Studio process on 8191 was serving new JavaScript against a Python that
predated the Wan hold and the Workspace identity work; the installed-node schema reader matched dynamic-input type
names that no ComfyUI build emits, so the repository's own video presets could never pass "Check connections".

**Value for the owner.** High on trust: the routes that are marked proven are proven, the numbers in the docs are now
measured, and the two recovery dead ends are gone. The visible frontier has not moved much in two days: video still
fails inspection, no image is accepted, and the character-sheet goal has no capability behind it yet. The next slices
in [STATUS.md](STATUS.md) are chosen to move exactly that.

## Confirmed defects and their disposition

Severity follows the repository's own bar (a realistic direct path to wrong behaviour). "Fixed" means PR #242
(recovery exits, dynamic-input schema, Generate race, small frontend defects) or PR #243 (this document set and the
catalog corrections).

| Seam | Defect | Severity after refutation | Disposition |
| --- | --- | --- | --- |
| Job recovery | `_queue_observation` refused the reconciliation `_resume` performs when every submission is terminal; job stuck `uncertain`/`partial`; backend switch refused forever | medium (3 of 3 refuters confirmed the mechanism, lowered the severity) | Fixed: terminal receipts reconcile to `completed`/`partial`; a queued/running job cannot be observed twice |
| Job recovery | Observing a prompt absent from a restarted ComfyUI's history polled for 24 minutes per submission | medium (confirmed by execution) | Fixed: the worker reads `/queue`; a prompt in neither queue nor history is declared gone within about 30 s with a specific message; Stop tracking is honoured inside the loop; the ceiling is time-based |
| Job recovery | `index_outputs` caught only `OSError`/`ValueError`, so a `sqlite3.Error` relabelled a finished generation `uncertain` | low after refutation | Fixed: degrades to a per-output `snapshot_error` as the OSError path already did |
| Create | Generate rebuilt its body from live state after awaiting up to two uploads while the recipe picker stayed interactive; a swap in that window submitted the wrong recipe | medium (2 of 3 refuters kept it) | Fixed: the recipe identity is stamped before the uploads and re-verified after; nothing is submitted if it changed |
| Workflow Studio | Dynamic-input guard matched `DYNAMIC_COMBO`/`DYNAMIC_AUTOGROW`, names ComfyUI never emits; 50 installed inputs across 39 classes were shown as plain sockets with an unsatisfiable "connect an output" instruction | medium | Fixed: matches the installed `COMFY_*_V3` spellings; the contract test now uses recorded real descriptors |
| Experiments | Single-axis sweep accepted values distinct as Decimals but identical as floats, spending two reservations on one image; the planned-variants path already refused this | low | Fixed: graph-identity check applies to every comparison |
| References | Clearing or reordering a slot during an in-flight upload discarded the upload with no message | low | Fixed: the summary says the slot changed and the image was not attached |
| Experiments UI | Time-extension error named seconds for a field labelled minutes | low | Fixed |
| Workflow Studio | Save to Workspace enabled with no local changes, burning immutable revisions | low | Fixed: disabled when the attached revision is unchanged |
| Runtime recovery | The monitor wrote an identical "healthy" log line every 15 s (5,278 lines, 1 MB measured) | low | Fixed: a line is appended only when the event changes |
| Catalog | `flux`, `sdxl`, `sdxl-variation` verified with no recorded run anywhere; 13 verified presets with no execution note | docs-claim | Fixed: notes added from the 11 September batch rows and the pilot ledger; the three are `verified: false`; validator enforces the rule |
| Catalog | wan22-i2v modes declared a `denoise` the preset does not bind (silently dropped) | low | Fixed: removed; validator now checks mode controls like variants |
| Catalog | 22 shipped visual workflows unlinked; Studio could not open them | low | Fixed for the 18 unambiguous exact twins |
| Docs | MODULAR-ILLUSTRATION-BASELINES.md said three installed checkpoints were missing and only Anima was verified | misleading | Fixed |
| Docs | CLAUDE.md test/skip/module counts were about half the true figures; a skill named a unittest command that always dies on import; three other stale counts | wrong-number | Fixed |
| Server | `_wait_for_queue` waits without bound behind any ComfyUI work with no cancel path | low | Tracked: #244 |
| Server | `GET /api/jobs` serialises every historical job on every poll (157 KB at 94 jobs) | low | Tracked under #177 |
| Catalog | `anime-detail-fix` authors the hand pass at denoise 0.45 but the shared denoise binding overwrites it | low | Tracked: #245 (needs the retained graph of the proven run before choosing a fix) |
| Catalog | `pixel-lora`'s 128 px export is a fixed square, so a non-square request stretches | low | Tracked: #246 |
| Validator | `wan22-t2v`'s authored 81-frame default is held by the decode gate; only "Short motion study" runs | deliberate per PR #180's record | Noted, not changed |

Refuted as defects (mechanism real, framing wrong): a claimed unmigrated Workspace column rename that only ever
existed on an intermediate branch commit, never on `main`'s first-parent chain; the authored-example fallback for
source-consuming recipes, which is disclosed at the control and fails closed where a substituted example would be
wrong; civitai-fetch sending its bearer token to an unvalidated URL (accurate, but the only path is a hostile
Civitai API response); and the stale-server skew, which is a process fact, not a code defect.

### Stale server

The Studio on 8191 was started at 15:43 on 13 September and served the current static files against an older Python
process, so the browser's Wan hold, the Workspace identity binding and the new recovery paths were not what was
running. It was restarted after the fixes merged; the restart record is in `CURRENT_STATE.md`. This skew recurs after
every merge that touches `app/`, because Codex restarts the server after its UI merges but not after every server
merge: restart Studio (idle queue only) after merging any `app/*.py` change.

## Proven routes, honestly classified

Of 66 presets: 26 executed and inspected with a retained identifier, 10 executed without an inspection note, 11
schema-only, 15 never executed, 4 that had claimed more than the evidence supports (now corrected). The full route
table with defects and licence flags is in the audit record; the operational summary is in [STATUS.md](STATUS.md).
Measured facts that changed a claim:

- The nine strongest routes: `wai` 26 s, `anime` 30 s, `pony` 30 s, `noob` 28 s, `anima-artist-stack` 20–66 s,
  `krea-anime-atelier` 197 s (4-step) / 828 s (target stack), `krea-style-lab` 207 s, `krea-refine` 233 s,
  `anime-detail-fix` 36 s. Owner verdicts (HUMAN_TODO q-2) are recorded next to them; none is accepted art.
- Wan 2.2: three executions, two visually failed, one 1005 s canonical control that failed at frame 1. The only Wan
  success is a decode-only synthetic probe. Video is not a working route today.
- Isolated backends both proved once: HiDream O1 concept 184.7 s / edit 76.3 s at 2048², H3 preview 398 s with
  audio. Both backends were offline during the assessment.
- Models: 121 pinned, 120 present and size-matching, one partial (AniFox v2). The ledger carried two different
  accounts of that partial (a range-validation stop after 13 chunks; a 401 at 2.65 GB). Both are retained runtime
  facts from different attempts; the live receipt is the 401 at 2,647,016,718 bytes.
- The running Studio's `experiments_root` is `C:/Users/jekyt/source/local-asset-studio/experiments`, inside the
  checkout CLAUDE.md calls stale. The 94 run receipts live there. Do not delete that folder.

## Agent tooling: where the Comfy MCP work got to

- `comfy-cli` 1.20.0 and `comfy-mcp` 0.10.0 (both the latest releases) are installed in their own venv at
  `C:\AI\agent-tools\comfy-mcp`; the MCP server starts over stdio and lists 39 tools.
- Codex had both `comfy-local` and `comfy-cloud` registered. **Claude had no registration**; its only user-scope MCP
  entry was the Docker gateway, which fails to connect. `comfy-local` is now registered for Claude at user scope with
  `COMFY_WHERE=local` (`claude mcp get comfy-local` → Connected).
- The comfy-cli default workspace pointed at a non-existent `Documents\comfy\ComfyUI`, contradicting the ledger; it
  now points at the portable install, so workspace-scoped tools read the real one.
- Skills: comfy-cli's bundled six are installed for both runtimes and all report `current` after one copy was
  re-synced from an unreleased upstream version; jtydhr88's nine custom-node skills are byte-identical to upstream
  in both scopes. Of the three sources the owner named, Comfy-Org/comfy-skills now only ships the `comfy-cloud`
  Claude plugin (hosted MCP plus slash commands); it is optional for local work and was not installed.
- Read-only probes through the server against the live ComfyUI succeeded (`server_info`, `which`, `system_stats`,
  `search_models`, `nodes`). No workflow was submitted through it. Rules and details: [AGENT-TOOLING.md](AGENT-TOOLING.md).

## Documentation changes

A `docs/README.md` index now names every page and subfolder; `STATUS.md` is the goal view; CLAUDE.md carries dated,
measured counts; `AGENT-TOOLING.md` records the toolchain. Redundancy the audit named but this pass did not touch:
timing facts stated in three places (README, START-HERE, the atelier guide), and `docs/reconciliation/` holding
per-PR verification records as tracked docs. Both are worth a later consolidation; neither misleads today.

## Trade-offs taken

- `flux`, `sdxl` and `sdxl-variation` lost their verified badge rather than gaining an invented note.
- Only 18 of 22 orphan visual workflows were linked; the four whose class multiset matches several presets
  (`sdxl`, `sdxl-variation`, `flux`, `qwen-character`) stay unlinked rather than guessed.
- The history-observation ceiling rose from 24 minutes to four hours, but only for a prompt ComfyUI still lists;
  a prompt gone from queue and history is declared within about 30 s, and Stop tracking ends observation at once.
- The stale worktree copy at `.claude/worktrees/scene-interactions` (56 MB, every file present in Git history) was
  removed after its runtime folder was archived under `.runtime/archive/scene-interactions-worktree-20260912/`.

## Not verified

No generation was submitted during the audit; the fixes were proved by the narrow test modules and the full suite,
not by a fresh GPU run. The isolated HiDream and H3 backends were offline and were not started. Native browser
behaviour was exercised only by the existing inert-transport lane plus one live read of the running page. No art was
judged; no licence was cleared; HUMAN_TODO q-5 and q-6 wait for the owner.

# Review backlog (retroactive owner review)

Owner, 16 Oct 2026: "don't wait for me to approve stuff, looks, etc — judge things yourself and add everything to a
backlog of changes for me to review retroactively." Every agent judgment call that would otherwise wait for the owner
lands here: what was decided, the evidence, and how to reverse it. These are agent judgments, never owner answers;
HUMAN_TODO items stay open until the owner speaks, and link here when an agent verdict exists.

Newest first. Tick a line when you have reviewed it; write "reverse" next to it to have an agent undo it.

## 2026-10-16 overnight session

### Plan and orchestration (session eb59d5)

- Lanes: **UX** (journey audit by a Sonnet 5.5 high tester, then a rework wave implemented by Opus 5.5 medium and the
  driver), **bugs** (GPT-6.1 Sol medium, at most two at a time, each in its own worktree; the driver commits), **lab**
  (one agent owns the GPU queue: qualify and improve the shipped looks, learn model/LoRA/pose combinations, write the
  findings into agent and user docs), **Muse swarms** (review, bug-hunt, accessibility and test-gap lenses on every
  merged wave), **Haiku 5.5** for mechanical chores. Every PR gets one fresh-context review; merges go through
  `estate_merge.py` at the exact reviewed head.
- GPU: one generation at a time, owned by the lab lane; the UX audit never submits jobs.

### Decisions

- [ ] **#1405 repeat trash/restore is a no-op** (not a 409): re-trashing keeps the original `trashed_at` and burns no
  revision; a stale revision still conflicts. Reason: idempotent retries from agents and API clients should not fail.
  Reverse: make the repeat raise a 409 in `app/workspace.py` `update()`.
- [ ] **#1423 a non-dict job output is refused before the copy** (as well as a missing index), with a WorkspaceError.
  Reverse: narrow the check in `AssetWorkspace.register()` to the index only.
- [ ] **Merged #1175 (Ming-Image research docs) without the owner review its body asked for.** A fresh Muse review
  found nothing that authorizes an install or a promotion; the docs stay dated research. Reverse: revert the merge commit.
- [ ] **Make pictures count as yours** (#1421): run labels starting `Make · ` no longer mark an asset as an agent run, so
  Make output shows in Mine, Keepers and the Overview numbers. Reverse: drop the prefix exemption in `assetIsAgentRun`.
- [ ] **UX audit priorities** (docs/ux-qa/JOURNEY-AUDIT-2026-10-16.md): the agent ranked 27 problems and proposed a
  target layout (Make as home with a Customize drawer, picture goals inline, Pictures = library + runs, Looks & models
  browsed by goal, Advanced folded). Tonight's wave builds from the top of that list. Say if the direction is wrong.
- [ ] **#1403 workshop field borders**: a dedicated field-border token per skin, at least 3:1 against field and panel.
  Look at the arcade and sakura skins once it lands. Reverse: revert the token.
- [ ] **#1402 pose canvas** keeps keyboard nudging and announces itself as a "pose editor" application, not a picture
  (instead of dropping keyboard support). Reverse: drop tabindex and keep the joint list as the keyboard path.
- [ ] **#1407 legacy parallax click path deleted**; if the recovery controller fails to mount, the button is disabled
  with "reload the page". Reverse: restore the legacy branch in app.js.
- [ ] **#1410** the pwsh launcher test timeout went from 20 s to 90 s, with one warm-up per class (it guards hangs, not speed).
- [ ] **Asset dialog keeps its confirm before "Same recipe, new seed"** (#1429): the press replaces the Full editor's
  setup, unsaved text included, so it still asks; declining now says so instead of doing nothing. Reverse: drop the
  `confirm()` in `asset-family.js` recall.
- [ ] **Models shows looks first and folds the file table** (#1426): "What you can make" (ready vs needs a download), a
  "Used by" line per file, a quiet Verify per card, and no bulk "Verify all" (the install lock would make it mostly fail).
- [ ] **Ctrl+Enter in a look's scene box prepares first** (#1226): the first press prepares the look, a second press
  generates, so it never runs with the Full editor's old words. Reverse: make Ctrl+Enter generate straight away.
- [ ] **The Full editor opens with an empty prompt** (#1433), and adult-content notes appear only on adult recipes.
  Ctrl+K and the mobile header now lead to Make. Reverse: restore the authored default prompt on first open.
- [ ] **Tune this look** (#1424) treats every SDXL checkpoint as one model type, so an Illustrious look can switch to
  Pony V6 (each choice is labelled with its family). LoRAs that settings-kb.json does not know (about 30 of 100
  installed) are not offered. Edit and re-run fixes the run's seed by default. Trigger words are auto-added only for
  LoRAs you add. "Good for / Not for" was not invented because looks carry no such data.


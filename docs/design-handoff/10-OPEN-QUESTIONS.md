# 10 · Open questions for the owner

Decisions the design needs. None is decided here; each has a proposed default so design can proceed on a named
assumption. Record answers in `HUMAN_TODO.md` (agents never tick these for you).

| # | Question | Why it matters | Proposed default (assumption until answered) |
| --- | --- | --- | --- |
| Q1 | Do you accept the five-place structure **Home · Make · Library · Runs · Setup** and the renames (Library for Workspace/Asset library; Runs for Runs & review/Experiments)? | Every deliverable after D1 depends on it | Yes; old names kept as search aliases in Ctrl K |
| Q2 | Should **Prompt Lab** become a "Help me write this" panel inside Make, keeping the full page only for saved briefs and picture analysis? | Your #278 feedback: "a couple of clicks away" from the image | Yes (D11) |
| Q3 | Merge the **Review desk** into one Compare board with the Runs candidate cards? | Today three decision vocabularies on one flow | Yes; blind rules and evidence export unchanged (D5) |
| Q4 | Move **Scene editor, Voice takes, Spoken Briefs, Workflow guide, Workflow builder** under Setup/Tools, out of the daily nav? | You said the scene editor is not needed now | Yes; still one click via Ctrl K |
| Q5 | **Skins everywhere or Create only?** Today skins recolour Create only. Add Minimal Pro and Sci-Fi Noir? | Consistency vs effort | App-wide token skins; ship Atelier default + Retro Anime + Minimal Pro first |
| Q6 | **Artwork: which pilot world first, and is each piece accepted?** The 23 Sep answer to `adaptive-pilot-world` (option B, defer artwork) is superseded: on 27 Sep 2026 you asked for the asset wishlist (`docs/adaptive-studio/assets/`, 154 requests) to be reviewed, planned and executed (recorded in HUMAN_TODO by PR #1084). Still open: which world is the pilot, and whether each produced piece is accepted | Designs can target a world, but art slots stay placeholders until a piece is produced and you accept it | Retro Anime "Night Shift" (with its Quiet Morning still) as the proposed pilot; designs keep empty-slot and token-only fallbacks; art acceptance is yours per piece, never inferred from a finished render |
| Q7 | **Library default view**: hide agent-lab runs by default ("Mine")? Title assets from the prompt when the recipe name repeats? | 1,182 of 1,201 assets are agent runs | Mine by default; prompt-based titles (#939) |
| Q8 | **Review words**: Keeper / Needs work / Rejected / Unreviewed everywhere (the Review desk's "Keep for consideration" and Runs' "Choose A" go)? | One vocabulary | Yes |
| Q9 | Do you want a **Cancel** for a single running job? It needs backend work (no endpoint today) and must stay truthful if ComfyUI already accepted the job | Long jobs; you can only wait today | Design it as "needs backend", behind a confirmation that says the remote job may still finish |
| Q10 | **Recipe thumbnails**: may recipe cards show the repository example images, and should local-only lab pictures ever appear as thumbnails? | D6 card design; some examples are not in Git | Only Git-tracked, public-safe examples; others get a no-thumbnail card |
| Q11 | **Fonts**: system stack only, or bundle an open-licence font file in the repo? | Offline rule; typographic character | System stack (Segoe UI Variable, Cascadia Code) |
| Q12 | **Assistance levels** (Guided / Studio / Expert) — worth having, or one level with "Why?" disclosures? | Guides felt "wordy" and "advisory" | One level + "Why?" disclosures now; levels later |
| Q13 | **Mobile**: how much must work at 390 px (review on a narrow window? generate?) | Loopback only, so "mobile" = a narrow desktop window | Review and Runs fully; Make usable; Setup read-only |
| Q14 | **Keyboard scheme** in 05 §7 (G-then-letter navigation, 1-7 reason chips, Z undo, B blind) — approve or adjust? | Keyboard-first review is your explicit request | Approve as proposed |
| Q15 | Which design goes to code first? #907 names "task guidance + recipe discovery" as the first Vue island; this package ranks D2 Make and D3 Library/Review highest | Order of implementation | D6 Recipe picker as the first island (matches #907), then D3 Review mode, then D2 |

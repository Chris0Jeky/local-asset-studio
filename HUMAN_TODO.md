# Creative choices

No human setup action is required on the configured PC once launcher validation is complete. These are optional choices, not inferred approvals:

- [ ] Choose your preferred pixel-art result after the first LoRA comparison.
- [ ] Pick one real game or product brief for a focused production pack.
- [ ] Decide which results are good enough to curate; successful execution alone is not art approval.

The repository defaults to private. Public visibility has not been requested.

## Anime & fantasy atelier — open items

**q-1 — koukouya Krea 2 style LoRA: done, 12 September 2026.** The owner supplied a civitai API key; it is stored
as the user-scope environment variable `CIVITAI_API_TOKEN` (not in the repository). `scripts/civitai-fetch.py`
installed `krea2_koukouya_style_c1-st3000.safetensors` with a receipt whose SHA-256 matches the listing
(`8cf2068c…`). Verified by the receipt in `.runtime/downloads/receipts.json` and the registry entry in
`models/library.json`, not inferred.

**q-2 — creative review of the atelier results: answered by the owner, 12 September 2026.** Recorded verbatim
in spirit under "Recorded owner decisions" below and in `docs/ANIME-FANTASY-ATELIER.md`. Nothing further to
decide here; the follow-up work (a correction pass for hands, faces and small details) is tracked in
`CURRENT_STATE.md`.

**q-3 — Anima artist-stack baselines (human-only; subjective).** Three outputs now exist on Anima base v1.0
(`anima-artist-stack-authored`, `anima-artist-tags-no-adapters`, `anima-reference-stack-1328x1776` in
`examples/anime-fantasy-atelier/`). Say which of the two looks to pursue: the six-adapter
reference stack (civitai image 139608451) or the adapter-free painterly artist tags (`@synswt, @koukouya, @kyano`,
images 131843207–131843406). Execution is not art approval, and the six adapters' civitai terms are recorded,
not cleared.

## Recorded owner decisions

**Character-consistency pilot canon, 12 September 2026:** In response to the choice of reference canon
for the twelve-case pilot, the owner answered: "Use the supplied standard costume, including its shown
back view". This selects the standard supplied design for the private reference-preservation study;
it does not approve generated outputs, other costume sets, model terms or commercial use. The exact
decision and revision-bound canon attestation are retained in `C:/AI/character-lab/pilot-20260912/`.

Recorded owner decisions, 11 September 2026: use free alternatives to NIJISIS
instead of spending Buzz; MiniMax H3 is being used from an eligible territory.
These decisions do not approve the generated art. The Workflow Lab expansion
requires no additional disk space at the current installed footprint.

**Superseded, 12 September 2026:** the owner downloaded the NIJISIS Krea 2 LoRA
(`NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors`, civitai model 2863875 version 3302337) and spent
the Buzz for it. The 11 September "use free alternatives instead of spending Buzz" note no longer
applies to this file; the free Comfy-Org and fal style adapters remain installed and in use alongside
it. Recorded from the owner's statement, not inferred from a download receipt. The other decisions
above stand.

**Owner's creative review, 12 September 2026 (q-2, recorded from the owner's message):**
`WAI-Illustration_00012_` okay-ish, not spectacular, some imperfections. `noob_00004_` has potential but six
fingers and the artistic side is not popping. `pony_00002_` a complete mess. `krea-anime-atelier_00001_`
genuinely great. `krea-style-lab_00001_` nice from afar, the foxes lose detail and their faces are morphed.
Probes: `witch-target-ersde-4step` very good; `witch-target-plus-baroque-oil-4step` good;
`witch-target-stack` very good; `witch-target-stack-4step` very good; `witch-nijisis-baseline` potential
but imperfect; `witch-nijisis-4step` very good; `witch-airy-watercolor-short-4step` good with a lot of
potential. Almost all carry some imperfection the owner would like a correction workflow for.

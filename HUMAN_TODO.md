# Creative choices

The earlier creative choices below are answered. The configured page-file increase still needs an owner-controlled Windows restart; save work in all applications first. No automatic restart is authorized.

- [x] Choose your preferred pixel-art direction: compass A, seed `2026091103` (owner, 12 September 2026). Both compass originals remain preserved; the two seeds are not a LoRA-on/off comparison and neither is accepted as a finished game asset.
- [x] Pick a focused production brief: **Fantasy character illustration pack** (owner, 12 September 2026). The prepared brief is in [FANTASY-CHARACTER-BRIEF.md](docs/FANTASY-CHARACTER-BRIEF.md); this selects the work, not finished-art acceptance.
- [x] Choose an initial private shortlist (owner, 12 September 2026): the ornate witch with floating books and colourful witch holding a black cat are in **Promising — needs correction**, both marked `needs_work`. Original hashes and membership were verified. This is not finished-art or commercial-use approval; future candidates still need review.

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

**q-3 — Anima direction: answered by the owner, 12 September 2026.** The owner chose: **"Pursue the new screenshot stack"**, superseding the older two-option comparison below as the immediate priority. The owner subsequently supplied `https://civitai.red/images/134076830` for technical analysis. Build compatible Anima and SDXL starting points from the resource metadata. This is a direction choice, not a claim of exact reproduction, art acceptance or licence clearance.

Historical comparison: three outputs exist on Anima base v1.0
(`anima-artist-stack-authored`, `anima-artist-tags-no-adapters`, `anima-reference-stack-1328x1776` in
`examples/anime-fantasy-atelier/`). The previous choices were the six-adapter
reference stack (civitai image 139608451) or the adapter-free painterly artist tags (`@synswt, @koukouya, @kyano`,
images 131843207–131843406). Execution is not art approval, and the six adapters' civitai terms are recorded,
not cleared.

**q-4 — page file: authorized and configured, 12 September 2026; activation pending an owner-controlled Windows restart.** The owner explicitly answered: **"Authorize a fixed 64 GiB page file; do not reboot automatically"**. After backing up the original settings, the elevated helper set C: initial and maximum to `65536` MiB; both values verified at 22:32 UTC. Windows still reports the effective allocated size as `40960` MiB. No reboot was performed. This specific authorization supersedes the earlier owner-only restriction for this change; it does not authorize driver, package or other system changes, or prove a native-crash fix.

**Next human execution step:** after saving work in all applications, use **Start → Power → Restart** when convenient. Then ask Studio to recheck the effective page-file allocation and commit headroom. The large Qwen/FLUX proving run stays gated until at least 32 GiB of headroom is actually measured. Rollback, if requested later, is the recorded original fixed `40960` MiB initial/maximum setting.

**Gate now deployed:** PR #129 implements the rule, and local `enforce_host_commit_headroom` is enabled. A non-submitting live check rejected an eligible 1 MP FLUX graph at 11.0 GiB headroom without creating a job. A later idle ComfyUI cache release recovered headroom to about 22.5 GiB, with the same process and unchanged jobs; this remains below the required threshold. The historical operator-only description below refers to the original handoff, not the current application.

Historical measurement: fixed 40 GB gives the ~73–77 GB commit limit that #77 and #89 hit. Measured 12 September
2026: `SizeStoredInPagingFiles` 41,943,040 KiB, commit limit 77,014,286,336 B; #77's failure was at
97 % committed, and a Qwen job at `--reserve-vram 0.6` still failed on a host allocation at 87 %
committed, so the VRAM reserve is measurably not the lever. The ≥32 GiB commit gate (raised from 20 GiB after the run above started at 29 GB headroom and still failed) is documented as
an operator rule in `docs/RUNTIME-PRECONDITIONS.md`; it is **not enforced by code** — nothing in
`app/` samples commit headroom before submitting at the original handoff. #77 says not to treat paging as a default fix. The later explicit owner decision and verified configuration above supersede this historical undecided option.

## Recorded owner decisions

**New WAI baseline, 13 September 2026:** the owner answered **"Keep only as an experiment"** for the teal-coat lanternkeeper, job `2607afc1-84e8-4f46-ae43-a8042b1c6ae7`, output `WAI-Illustration_00013_.png`. It remains outside the promising shortlist; successful execution is not creative acceptance.

**New Anima baseline, 13 September 2026:** the owner also answered **"Keep only as an experiment"** for job `c345a7e5-0f32-46d3-b09f-ac3628c77fd7`, output `anima-artist-stack_00004_.png`. It remains outside the shortlist; no duplicate-lantern correction is commissioned from that optional choice.

**Modular baselines, 13 September 2026:** the owner clarified that no sexual imagery will be produced and requested the referenced resources for creative freedom. Build architecture-compatible baseline graphs with independently editable style controls and optional correction, pose/reference and upscale stages. Resource listing names do not become prompt instructions.

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

# NSFW hentai lab orchestrator — 21 September 2026

Owner request (this session): experiment a lot with anime-style NSFW/hentai generation — prompts, body features, details, wildcards, poses, adapters/LoRAs — inspect, document, build a knowledge library and a visual collection, optionally add hideable Create intel. Overnight. Adult original characters only. Do not merge HUMAN_TODO q-29 (parked Codex programme). Do not tick owner creative items.

Related GitHub (Refs, never Closes until acceptance is complete):
- #439 first controlled adult-character qualification campaign (this lab is a local execution slice)
- #440 LoRA / control-interference lab
- #432 prompt / tag-vocabulary / model-dialect intelligence
- #410 genre recipe packs
- #143 bundle portfolios
- PR #756 Civitai scavenge (explicit queue quarantined; WAI `nsfw`/`explicit` rating tags)
- PRs #755/#765/#766 setup-compatibility / composition evidence — read-only, not this GPU lane

## Hard rules

- Adult only. Negatives always include `child, loli, shota`. No real people. **As planned: no named franchise
  characters — not what happened.** From wave C on, the lab used adult-coded Danbooru character tags (2B, Kafka,
  Darkness, Aqua, Cynthia, Asuna, Yelan, Raiden, Tifa, and Yor and Acheron in `presets/wildcards/nsfw_character.txt`),
  and they are in `FINDINGS.md`, `presets/nsfw-intel.json` and the media manifests. The adult-only and no-real-people
  parts held: Megumin and child-coded franchise tags were skipped on purpose. Whether the lab should use named
  franchise characters at all is an owner decision, raised in `HUMAN_TODO.md`; nothing was deleted to hide the gap.
- Fast families only: Anima, AniFox, WAI, CSTati, YumeFlux, JANIMA, One Obsession, Pearly Mix, Animagine. Skip Qwen / FLUX.2 32B / H3 / Wan / Hunyuan / Trellis / HiDream / Klein 9B / z-image / extra Krea.
- One seed per cell unless the cell *is* a seed audition. Never resubmit an uncertain job.
- Generated ≠ accepted ≠ licensed. Catalog `verified` stays false for new presets.
- Serving Studio checkout is this tree on 8191. Do not switch it. Restart Studio only when an API/static change needs a reload and the queue is empty.
- Public remote: keep contact sheets small; no 10 MiB+ binaries. **Superseded 21 September 2026:** the owner decided
  the lab's JPEGs are not uploaded at all — see `README.md` in this folder for the local-only media policy.

## Intent

Improve anime NSFW in *this* repo by measuring what the local graphs actually do:

1. Body tags (breast size, hips, thighs, waist) at a locked seed.
2. Pose / camera tags at the same seed and body.
3. Skin / lighting / hand wording.
4. WAI rating tags (`nsfw` vs `explicit` vs none).
5. Adapter combos that already fired in wave 2 (PetiFlow, Esearu, BunnySlop, Ringeko, shiny NAI, glossy).
6. Wildcards `__nsfw_pose__`, `__nsfw_body__`, `__nsfw_camera__`, `__nsfw_setting__`.

Promote only cells that survive inspection into recipes + Creative Bundles + `presets/nsfw-intel.json`.

## Wave queue

| Wave | Status | Cells | Family | Notes |
| --- | --- | ---: | --- | --- |
| A | done | 16 | Anima + WAI | body / pose / detail / rating. Seed 2026092151. Inspected. |
| B | done | 12 | Anima combos + AniFox + WAI glossy | inspected |
| C | done | 16 | adult franchise + explicit + expressions | inspected. Character tags fire. Extra fingers on active hands. |
| D | planned | keepers | recipes + intel + gallery | only after inspection |

## Files

- Experiments JSON: `.runtime/nsfw-lab-waveA.json` (untracked submit payload)
- Receipts: `.runtime/nsfw-lab-receipts.json` (untracked)
- JPEGs: `examples/nsfw-lab/<id>.jpg` — local-only and gitignored; the tracked record is
  `examples/nsfw-lab/MANIFEST.json` and the tooling is `scripts/lab-media.py` (`README.md` in this folder)
- Findings: `experiments/curated/nsfw-lab-20260921/FINDINGS.md`
- Intel: `presets/nsfw-intel.json` (Create panel + gallery)
- Gallery: `app/static/nsfw-lab.html`

## Stop conditions

- 8 hours wall, or two consecutive empty/failed waves, or ComfyUI unhealthy.
- Extra fingers on most nudes is a known defect from wave 2 — record it, try one hand-wording cell, do not infinite-loop it.

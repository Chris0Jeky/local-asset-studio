# NSFW lab orchestrator — continuation, 23 September 2026

This file guides the continuation. The 21 September plan stays in
`experiments/curated/nsfw-lab-20260921/ORCHESTRATOR.md`. Findings for this
date are `FINDINGS.md` in this folder. Pictures stay off Git.

Owner, this session: keep going on adult anime and game characters, use Civitai
now that both civitai.com and civitai.red answer, and use the adult-illustration
work that has already merged. A youthful face on a character who is an adult in
canon is a composition note, not a reason to drop the cell or the character.
Danbooru spelling is a convenience, not a gate.

## What already merged and how this lab uses it

- `agent-skills/adult-illustration/SKILL.md` and `docs/adult-illustration/`: adult
  status comes from canon, not from pixels and not from a negative prompt. This
  lab follows that. It does not follow that skill's dry-handoff ban on jobs,
  because the owner asked for generations.
- `presets/nsfw-intel.json`, `presets/wildcards/nsfw_*.txt`, `/static/nsfw-lab.html`,
  and the 21 September findings: the measured prompt lessons (hands, costume, place).
- `scripts/civitai-fetch.py`: the downloader. Token only from `CIVITAI_API_TOKEN`.
  Public metadata can be read with `--dry-run`. Weights go to the ComfyUI models
  folder, never into Git. A pin, if added, needs sha256, bytes, and the listing URL.
- Fast Studio presets already on main: `wai`, `anima-v1-baseline`, `janima-v1-baseline`,
  `cstati-v3-baseline`, `anifox-v2-baseline`, `yumeflux-ilv1-baseline`,
  `oneobsession-anima-v20-baseline`, `pearly-anima-mix-v10-baseline`,
  `anime-animagine-quality`.

q-29 and q-31 stay open. New cells are not Creative Bundle entries. Catalog
`verified` stays false. Generated is not accepted and not licensed.

## Who is in the sexual set

In: characters who are adults in canon and adult-coded in design. Overlord
guardians, Konosuba adults (Darkness, Aqua, Wiz, Luna), Frieren and Serie,
Re:Zero adults (Elsa, Crusch, Priscilla, Echidna), Chainsaw Man adults (Makima,
Himeno, Power, Quanxi), Fate adult servants, Zenless Zone Zero adults, Honkai:
Star Rail adults, Wuthering Waves adults, Epic Seven adults.

Out, because the canon is under 18 or the cast is in school: Blue Archive
students, Alya and her school cast, Darling in the Franxx pilots, Dan Da Dan's
high-school leads, Megumin, Yunyun, Aura, Mare, Beatrice, Ellen Joe, child Fate
servants, child resonators, child Epic Seven units. "Slightly more mature" does
not move someone from Out to In.

A render of someone in the In list can look young. Write that down and change
the next prompt if the picture is worse for it. Do not discard the cell for the
face, and do not stop using that character.

## Loop

1. Read the latest findings and one Civitai listing or a merged preset note.
2. Submit one fast cell, or a short serial batch. Store the Studio job id and
   the ComfyUI prompt id before waiting. Never resubmit a known prompt whose
   output is missing.
3. Look at the picture. Write what it showed, what to keep, and the next change.
4. If a receipt says GPU memory spilled several GB, restart ComfyUI before the
   next job. One heavy new LoRA or checkpoint at a time, after that restart.
5. Checkpoint the prose on `grok/<topic>`. No image binaries. `Refs` only.

## Prompt defaults that survived inspection

- Costume still on, in a real place. An already-open skirt beats a front-seated
  "skirt lift".
- `hands, fingers` in the negative plus arms behind the back removed hands on
  Changli. A military uniform puts the hands back. Flat hands on the thighs were
  the in-frame pose that showed five fingers (Wiz).
- Do not write the word hourglass. Use slim waist, wide hips.
- Shared negative still includes `child, loli, shota`. Positive still includes
  `adult woman`.
- Many-minute families stay rare. Name them when used.

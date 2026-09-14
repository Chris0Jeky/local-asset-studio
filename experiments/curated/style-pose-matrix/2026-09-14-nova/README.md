# Nova Anime XL IL v19 on the style board — 14 September 2026

Four Studio jobs ([`manifest.json`](manifest.json), [`plan.json`](plan.json)) right after the checkpoint's SHA-verified
install: Nova on the averaged three-picture board (character sheet, KonoSuba group art, bodysuit study) with the throne
pose picture at the recipe defaults (Euler a, 28 steps, CFG 6, style weight 0.7, pose strength 0.9, seed 2026091407 from
the graph; the runner's plan seed 2026091410 was bound), plain, with Mishima Kurone 0.8, and with Mishima 0.7 + Glossy
0.6, plus the WAI baseline on the same board for a side-by-side. Sheet:
[`examples/style-pose/matrix/nova-vs-wai.jpg`](../../../../examples/style-pose/matrix/nova-vs-wai.jpg).

| Cell | Job | Seconds | Seen |
|---|---|---|---|
| Nova, no LoRA | `82bcf8e6-8978-4189-af8f-9ef271985b3e` | 201 (first load of the 6.9 GB checkpoint included) | Pose held; magenta-red palette, high contrast, coarse painterly sky; the sheet's diamond trim on the throne and robe |
| Nova + Mishima 0.8 | `e7bab2d1-3fee-4dd3-a2a1-14583031fe1f` | 211 | Pose held with the leg raised higher; cleaner lineart, warmer skin, the hat's trim from the sheet |
| Nova + Mishima 0.7 + Glossy 0.6 | `c2630b11-03bd-4bf1-b40f-919893a851ac` | 213 | Closest to the KonoSuba sheet of the three: red hair, glossy highlights, orange-gold robe, pose exact |
| WAI baseline, no LoRA | `3ee79f97-4051-4615-a73e-02ffd3c22881` | 287 | Calmer palette, softer contrast; the same pose |

Reading: Nova is a viable second checkpoint with punchier colour and stronger contrast; WAI v17 stays the default for its
calmer, cleaner rendering. The Nova recipe is `verified: true` on the plain cell. Not verified: other seeds, the beach pose,
any timing without the first load, art acceptance, licence (Nova's civitai flags allow Image/Rent but not Sell).

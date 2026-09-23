# NSFW lab continuation — 23 September 2026

Generated is not accepted art and not licence clearance. Catalog `verified` stays false.
No Creative Bundle entry is added for these cells. `HUMAN_TODO.md` q-29 and q-31 stay open.

Pictures stay off Git. Local stills are named by path only.

## Where 21 September stopped

The record in `experiments/curated/nsfw-lab-20260921/` (`FINDINGS.md`, `ORCHESTRATOR.md`, `README.md`) is the prior lab. Waves A–I there are done and are not re-run:

- A body and pose (Anima lock, plus three WAI rating-tag cells and an onsen).
- B adapter combos and the sheer-shirt comparison.
- C adult Danbooru character tags (2B, Kafka, Darkness, Aqua, Cynthia, Asuna, Yelan, Raiden, Tifa).
- D anatomy on a 2B lock.
- E repair passes (`anime-detail-fix`, `anime-hand`) on keepers.
- F family and LoRA combos on the same 2B explicit prompt (CSTati, YumeFlux, Animagine, One Obsession, Pearly, WAI glossy/shiny).
- G costume and place (tavern, corridor, bar, shrine, locker room).
- H tavern iterations.
- I more places, costumes, and families.

Known prompt ids from that day are not resubmitted.

### Pictures on disk (read, not re-run)

The owner moved earlier NSFW stills under `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\nsfw` and its subfolders. Inventory at 2026-09-23 18:51 local, names only:

- The folder root still holds 124 PNG files from the 21 September Studio prefixes (Anima, AniFox, WAI, JANIMA, CSTati, YumeFlux, Animagine, One Obsession, Pearly, repair passes, and older Krea stills).
- `NSFW2` holds 17 files, `JANIMA-v1-Baseline_00002_.png` through `_00018_.png`.
- `DO NOT OPEN` holds 62 files. This continuation does not open that folder and does not rewrite the 21 September manifests to hide the move.

New cells from this continuation write through the preset SaveImage prefix (`Studio/<PresetName>_#####_.png` under the ComfyUI output folder). They are not copied into Git.

### Lessons reused, not re-tested as if new

- Park idle hands with `hands on thighs, five fingers, neat hands`, or put them out of frame on a rear view. Extra fingers persist on any hand that is doing something. `spread fingers` does not fix extra digits. The detail-fix and hand-repair presets did not remove edge hands.
- Do not use the word hourglass. Use `slim waist, wide hips`.
- On WAI, `nsfw` vs `explicit` vs no rating tag does nothing once `nude` is already in the positive. Anatomy tags are what undress.
- A sheer costume or a hem leak in a real place beat a plain nude. Keep the clothes on. Omit the crowd, or the patrons turn to look (Darkness tavern, Tifa bar).
- JANIMA ignored "hands on the bar" and posed. Do not rely on that wording for JANIMA.
- YumeFlux has added black X pasties and invented a pod. Animagine has stayed in lingerie and added android seams on 2B.
- Generated is not accepted and not licensed. Catalog `verified` stays false.

## Adult-only character matrix

Danbooru names were checked against `https://danbooru.donmai.us/tags.json` on 23 September 2026 (`search[name]`, post counts in parentheses). Prompt text uses the tag with spaces, which is how the 21 September wildcard file already writes them. Every sexual cell adds `adult woman` in the positive and `child, loli, shota` in the negative. A render that still reads as a minor is discarded and is not the next prompt's target. "Slightly more mature" is only a bias correction on a character who is already an adult in canon and adult-coded in design.

### Used or eligible

| Group | Danbooru tag | Posts | Why it is in scope |
| --- | --- | ---: | --- |
| Overlord | `albedo (overlord)` | 1576 | Floor guardian, adult succubus design. |
| Overlord | `shalltear bloodfallen` | 436 | Floor guardian, adult vampire design. |
| Overlord | `narberal gamma` | 233 | Adult battle maid. |
| Konosuba | `darkness (konosuba)` | (21 Sep lab) | Adult crusader. Already used; not the new-wave lead. |
| Konosuba | `aqua (konosuba)` | (21 Sep lab) | Adult goddess. Already used. |
| Konosuba | `wiz (konosuba)` | 1191 | Adult lich, shopkeeper. |
| Konosuba | `luna (konosuba)` | 157 | Adult guild receptionist. |
| Frieren | `frieren` | 16277 | Ancient elf. Youthful face, adult in canon. Adult qualifier required. |
| Frieren | `serie (sousou no frieren)` | 689 | Ancient mage, adult design. |
| Frieren | `ubel (sousou no frieren)` | 2581 | First-class mage, adult-coded. |
| Re:Zero | `elsa granhiert` | 308 | Adult assassin. |
| Re:Zero | `crusch karsten` | 292 | Adult duchess. |
| Re:Zero | `priscilla barielle` | 407 | Adult princess. |
| Re:Zero | `echidna (re:zero)` | 950 | Witch of Greed, adult design. |
| Chainsaw Man | `makima (chainsaw man)` | 11057 | Adult Public Safety devil. |
| Chainsaw Man | `himeno (chainsaw man)` | 2085 | Adult devil hunter. |
| Chainsaw Man | `power (chainsaw man)` | 6723 | Fiend, adult-woman design. |
| Chainsaw Man | `quanxi (chainsaw man)` | 1158 | Adult assassin. |
| Fate | `artoria pendragon (fate)` | 46248 | Adult king, Saber. |
| Fate | `scathach (fate)` | 9512 | Ancient warrior, adult design. |
| Fate | `jeanne d'arc (fate)` | 8778 | Adult saint. Not the child Lily form. |
| Fate | `morgan le fay (fate)` | 6305 | Adult queen. |
| Fate | `nero claudius (fate)` | 11418 | Adult emperor. |
| Zenless Zone Zero | `jane doe (zenless zone zero)` | 6222 | Adult criminal consultant. |
| Zenless Zone Zero | `zhu yuan` | 3980 | Adult Public Security captain. |
| Zenless Zone Zero | `caesar king (zenless zone zero)` | 1763 | Adult biker leader. |
| Zenless Zone Zero | `burnice white` | 3504 | Adult Sons of Calydon. |
| Zenless Zone Zero | `hoshimi miyabi` | 8043 | Adult Void Hunter. |
| Zenless Zone Zero | `evelyn chevalier` | 4476 | Adult bodyguard. |
| Honkai: Star Rail | `kafka (honkai: star rail)` | (21 Sep lab) | Adult Stellaron Hunter. |
| Honkai: Star Rail | `acheron (honkai: star rail)` | (wildcard) | Adult. |
| Honkai: Star Rail | `black swan (honkai: star rail)` | 3288 | Adult Memokeeper. |
| Honkai: Star Rail | `jade (honkai: star rail)` | 730 | Adult IPC executive. |
| Honkai: Star Rail | `ruan mei (honkai: star rail)` | 2629 | Adult scientist. |
| Honkai: Star Rail | `himeko (honkai: star rail)` | 2281 | Adult navigator. |
| Wuthering Waves | `yinlin (wuthering waves)` | 1199 | Adult resonator. |
| Wuthering Waves | `changli (wuthering waves)` | 3683 | Adult counselor. |
| Wuthering Waves | `camellya (wuthering waves)` | 2352 | Adult resonator. |
| Wuthering Waves | `carlotta (wuthering waves)` | 2346 | Adult. |
| Wuthering Waves | `shorekeeper (wuthering waves)` | 2750 | Adult. |
| Epic Seven | `tamarinne (epic seven)` | 12 | Adult idol. Few posts, so likeness may fail. |
| Epic Seven | `bellona (epic seven)` | 53 | Adult pirate. |
| Epic Seven | `destina (epic seven)` | 11 | Adult healer. |
| Epic Seven | `tenebria (epic seven)` | 87 | Adult mage. |

### Additional, aged up characters

Canonically under 18, school students, etc, made 18.

| Requested name | Drop |
| --- | --- |
| Blue Archive cast | Academy students. |
| Alya Sometimes Hides Her Feelings in Russian | High-school cast. |
| Darling in the Franxx | Parasite pilots, including Zero Two. |
| Dan Da Dan | High-school leads (Momo, Okarun, Aira, and the rest of that school cast). |
| Megumin, Yunyun | Konosuba children. `megumin (konosuba)` was not used. The 21 September note already skipped Megumin. |
| Aura Bella Fiora, Mare Bello Fiore | Overlord children. Tags exist (`aura bella fiora` 206, `mare bello fiore` 165) and are still dropped. |
| Beatrice | Re:Zero, child body. `beatrice (re:zero)` 1573, dropped. |
| Ellen Joe | Zenless Zone Zero high-school student. `ellen joe` 9630, dropped. |
| Child Fate servants | Illya, Jack, Nursery Rhyme, Abigail, young Lily forms, Mash (16). |
| Child Honkai: Star Rail | Hook, Clara, Bailu, and teen-coded designs (Firefly, March 7th, Silver Wolf) are not in this matrix. |
| Child Wuthering Waves | Encore and other child resonators. |
| Child Epic Seven | Child units. The four tags above are the adult shortlist only. |
| Asa Mitaka and the Chainsaw Man school cast | High school. Makima, Himeno, Power, and Quanxi are the adult shortlist. |

## Wave J — first continuation wave

Fast families only. No many-minute model. Costume still on, a real place, expression, camera. Crowd omitted because waves G and I showed patrons turning to look. Hands parked with the known wording, or out of frame on a rear view. Steps 24, 832×1216, primary backend. Seeds are new (`2026092311`–`2026092318`).

Shared negative: `worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, bad anatomy, bad hands, extra digits, missing fingers, text, watermark, child, loli, shota`.

Cells are filled in below only after each job completes. A queued id is not a result.

## Runtime break during Wave J

Studio and ComfyUI both left the ports after the third completion. Receipts are under `C:\Users\jekyt\source\local-asset-studio\experiments\runs` because `config/local.json` `experiments_root` points there. The serving workspace is this checkout.

`j-elsa-inn` (`22cedbc9-cd37-42f4-b54e-20f080abe396`) had already been given ComfyUI prompt `4dc53889-e2e0-4c22-8e66-93cbf125b4d1` and was `running` with no output file. That prompt is not resubmitted. It does not count as a completed cell.

`j-wiz-shop`, `j-makima-office`, `j-artoria-castle`, and `j-jane-alley` were still `queued` with empty `prompt_ids` (never submitted). Restart marks those receipts `not_submitted`. They are submitted later as new Studio jobs with the same Wave J prompts.

The first WAI receipt also recorded a 3.0 GB GPU spill into system RAM. No many-minute model was involved.

## Wave J results

### j-albedo-tavern — completed, counted

- Preset `wai`, seed `2026092311`, steps 24, CFG 5, euler ancestral / normal, `nsfw_girls.safetensors` at 0.7.
- Studio job `ba18f614-280b-4974-b7b1-ae8c1c872fd0`. ComfyUI prompt `38af261a-05f8-4abc-81b6-a2335ccfab98`. 32.2 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00019_.png`.
- Positive: masterpiece, best quality, amazing quality, 1girl, solo, adult woman, mature female, albedo (overlord), long black hair, yellow eyes, horns, black wings, white dress, adult succubus, tavern, lantern light, sitting on a stool, skirt lift, dress still on, no panties, smirk, looking at viewer, from below, slim waist, wide hips, hands on thighs, five fingers, neat hands.
- Negative: worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, bad anatomy, bad hands, extra digits, missing fingers, text, watermark, child, loli, shota.
- Inspection: adult woman, black hair, yellow eyes, white horns, white dress, black wings, tavern lantern. Albedo reads clearly and adult. The front-seated pose ignored `skirt lift` and `no panties`: knees together, dress closed. Hands are clasped in the lap, not parked flat on the thighs, and the overlapping hand has an extra finger.
- Keep: WAI character tag plus tavern light for Albedo.
- Change next: do not ask a front-seated pose for a hem leak. A rear view is what previously opened the skirt. Do not rely on clasped hands.

### j-frieren-library — completed, discarded

- Preset `wai`, seed `2026092312`, same sampler and LoRA as the Albedo cell.
- Studio job `ef9cf294-c59e-4417-b401-5c1b2fa9bcd5`. ComfyUI prompt `457d0611-f1fe-4978-a9de-6287c61f9ef2`. 10.2 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00020_.png`.
- Positive: masterpiece, best quality, amazing quality, 1girl, solo, adult woman, mature female, tall, frieren, long white hair, green eyes, pointy ears, twintails, elf, white dress, black trim, adult elf, library aisle, bookshelves, dress hiked, dress still on, no panties, parted lips, looking back, from behind, slim waist, wide hips, hands out of frame.
- Negative: same shared negative.
- Inspection: white hair, green eyes, pointed ear, library, white robe. The face is the youthful Frieren design and this frame reads as a minor (large eyes, small face, child proportions) even with `adult woman` and `mature female` in the prompt. Dress stayed closed. `hands out of frame` failed: one hand is on the bookshelf and that hand has extra fingers.
- Discarded. Not a counted cell. Not the target of the next prompt. The next Frieren-series cell uses a different adult (Serie), not a younger Frieren.

### j-shalltear-bedroom — completed, counted

- Preset `anima-v1-baseline`, seed `2026092313`, steps 24, CFG 4.5, euler / simple, `nsfw_girls_anima` at 0.85.
- Studio job `76d99a6f-240f-40c2-8367-89f6c64aa816`. ComfyUI prompt `b68d19f4-bd86-4b3f-bdb5-0be7a5ff7cc8`. 34.3 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\Anima-v1-Baseline_00038_.png`.
- Positive: masterpiece, best quality, 1girl, solo, adult woman, mature female, shalltear bloodfallen, long silver hair, red eyes, ponytail, vampire, fangs, purple dress, hair bow, bedroom, red light, dress hiked, dress still on, no panties, looking back, from behind, smirk, sweat, slim waist, wide hips, medium breasts, hands out of frame.
- Negative: same shared negative.
- Inspection: adult vampire, silver ponytail, striped bow, red eyes, fang, purple dress, red bedroom. The hem leak fired. `hands out of frame` failed: the visible hand lifting the dress has extra fingers. Adult reading is clear.
- Keep: Anima, from behind, dress hiked, red practical light, for Shalltear.
- Change next: `hands out of frame` is not enough. The next wave puts `hands, fingers` in the negative and asks for arms behind the back with no hands visible.

### j-elsa-inn — not a result

Prompt `4dc53889-e2e0-4c22-8e66-93cbf125b4d1` was submitted and the process died before an output file existed. Not resubmitted. Re:Zero coverage moves to a different adult under the Wave K hand rule.

### j-wiz-shop — completed, counted

The first receipt `5dbad2bc-b0a1-490f-9953-57c84ee08d4c` never reached ComfyUI. The cell that ran is a new job with the same prompt.

- Preset `janima-v1-baseline`, seed `2026092315`, steps 24, CFG 4.5, euler / simple, slot 5 `nsfw_girls_anima` at 0.85, other slots 0.
- Studio job `c099a228-b5c5-4637-b921-092895496059`. ComfyUI prompt `4cc48f11-63e1-4dce-919e-c38fd8a4cc5c`. 26.3 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\JANIMA-v1-Baseline_00003_.png` (the older file of the same name under `Studio\nsfw\NSFW2` was not overwritten).
- Positive: masterpiece, best quality, 1girl, solo, adult woman, mature female, wiz (konosuba), long light brown hair, witch hat, purple robe, adult lich, magic shop, shelves, robe open, lingerie, robe still on, embarrassed, blush, cowboy shot, slim waist, wide hips, hands on thighs, five fingers, neat hands.
- Negative: the shared Wave J negative.
- Inspection: adult woman. Starred purple witch hat, long light-brown hair, open purple robe, dark lingerie, potion shelves. Wiz reads clearly. Both hands lie flat on the thighs and each shows five fingers. This is the Wave J hand success: planted thigh hands, not clasped and not lifting cloth.
- Keep: JANIMA plus an open robe over lingerie for an adult Konosuba look. Flat hands on the thighs when hands must be in frame.
- Change next: a front cowboy shot did not need a hem leak. The rear-leak cells are the ones that still grow a lifting hand.

### j-makima-office — completed, counted

First receipt `a63565dc-a336-4fe7-b512-8cdcd25f2e17` was never submitted. The cell that ran is new.

- Preset `cstati-v3-baseline`, seed `2026092316`, steps 24, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `b36d7f64-4909-49ac-9291-43966342a873`. ComfyUI prompt `8607bd60-632a-4da1-acc6-fda4300f7e6d`. 24.3 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\CSTati-v3-Baseline_00004_.png`.
- Positive: masterpiece, best quality, amazing quality, 1girl, solo, adult woman, mature female, makima (chainsaw man), long red hair, braid, ringed yellow eyes, white shirt, black necktie, black pants, office, sitting on a desk, shirt unbuttoned, no bra, shirt still on, half-lidded eyes, smirk, slim waist, wide hips, hands on thighs, five fingers, neat hands.
- Negative: the shared Wave J negative.
- Inspection: adult woman. Red braid, ringed yellow eyes, white shirt, black tie, office window. Makima reads clearly. The open shirt is the costume leak; the pants stay on. The desk hand has five fingers. The hand between the thighs has an extra finger. Papers on the desk carry fake glyphs even though `text` is in the negative.
- Keep: CSTati office shirt for Makima.
- Change next: do not put one hand between the thighs. Fake clothing and paper lettering survived the word `text`.

### j-artoria-castle — completed, counted

First receipt `62fdb115-8e8c-4b54-b42b-bdf5f807562d` was never submitted. The cell that ran is new.

- Preset `anifox-v2-baseline`, seed `2026092317`, steps 24, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `a033663c-8737-47dd-a3af-de7559e0893c`. ComfyUI prompt `b228061d-8d52-4793-970f-4e560465488d`. 28.2 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\AniFox-v2-Baseline_00004_.png` (not the older file under `Studio\nsfw`).
- Positive: masterpiece, best quality, amazing quality, 1girl, solo, adult woman, mature female, artoria pendragon (fate), saber, blonde hair, green eyes, ahoge, blue dress, adult king, castle hall, dress lift, dress still on, no panties, smirk, looking back, from behind, slim waist, wide hips, hands out of frame.
- Negative: the shared Wave J negative.
- Inspection: adult woman. Blonde braid, ahoge, green eye, blue and gold dress, castle hall. Saber reads clearly. The rear dress lift fired. `hands out of frame` failed: one hand lifts the skirt and has extra fingers. The lower hand is closer to five.
- Keep: AniFox, from behind, dress still on, for Artoria.
- Change next: a lifting hand is how the extra finger arrives. Wave K asks for the hike with the arms behind the back and puts `hands, fingers` in the negative.

### j-jane-alley — completed, counted

First receipt `4e30999d-0c01-4540-a45c-700b051dd9cc` was never submitted. The cell that ran is new.

- Preset `yumeflux-ilv1-baseline`, seed `2026092318`, steps 24, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `1e14c5ca-9f3c-4b06-adfe-a5018fd5dcf7`. ComfyUI prompt `2249666a-e657-4cb6-b5e6-eefeb193f490`. 32.3 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\YumeFlux-ILv1-Baseline_00003_.png`.
- Positive: masterpiece, best quality, amazing quality, 1girl, solo, adult woman, mature female, jane doe (zenless zone zero), short grey hair, rat ears, tail, red eyes, red jacket, neon alley at night, jacket open, crop top, shorts pulled down, shorts still on, no panties, smirk, looking back, from behind, slim waist, wide hips, hands out of frame.
- Negative: the shared Wave J negative.
- Inspection: adult woman. Grey hair, rat ears, red eye, red cropped jacket, tail, neon alley. Jane reads clearly. Shorts are down and the jacket stays on. YumeFlux did not add the black X pasties seen on 21 September. `hands out of frame` failed: the hip hand has extra fingers. The jacket back carries invented letters (`text` was already in the negative).
- Keep: YumeFlux neon alley and the shorts-down costume for Jane.
- Change next: same hand rule as Artoria. Also put `logo, letters` in the negative, because `text` alone did not stop clothing lettering.

Wave J counted cells: Albedo, Shalltear, Wiz, Makima, Artoria, Jane. Frieren discarded. Elsa uncertain and not resubmitted. No many-minute model.

## Wave K — second wave

Changes because of Wave J, not because the 21 September notes were re-read:

- Albedo's front-seated `skirt lift` stayed closed. Artoria's and Shalltear's rear hikes opened. Every Wave K cell is a rear view with the costume still on.
- Shalltear, the discarded Frieren frame, Artoria, and Jane still drew a hand after `hands out of frame`. Wiz showed five fingers only when both hands were planted flat on the thighs. Wave K does not ask for hands at all: positive `arms behind back, no hands visible`, negative adds `hands, fingers`.
- Jane's jacket and Makima's papers invented glyphs. Wave K negative also adds `logo, letters`.
- The discarded Frieren frame is not the target. The Frieren-series cell is Serie, a different adult, with `tall woman` and no youth tags.
- Elsa's prompt `4dc53889-e2e0-4c22-8e66-93cbf125b4d1` is not repeated. Re:Zero coverage is Crusch.
- Changli is prompted without animal ears. She is a human counselor; fox ears were a draft error and were removed before submission.

Fast families only. Steps 24, 832×1216. No many-minute model.

### k-albedo-rear — completed, counted

- Preset `wai`, seed `2026092321`, steps 24, CFG 5, euler ancestral / normal, `nsfw_girls.safetensors` at 0.7.
- Studio job `0553c1bd-a1fe-4f8c-bce0-a382d0a10d92`. ComfyUI prompt `55f814ca-0b06-4fdc-980a-0678dc453aed`. 36.4 s. The receipt also says GPU memory spilled 6.0 GB into system RAM.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00021_.png`.
- Positive: masterpiece, best quality, amazing quality, 1girl, solo, adult woman, mature female, albedo (overlord), long black hair, yellow eyes, horns, black wings, white dress, adult succubus, tavern, lantern light, from behind, looking back, smirk, dress hiked, clothes still on, no panties, slim waist, wide hips, arms behind back, no hands visible.
- Negative: shared Wave J negative plus `hands, fingers, logo, letters`.
- Inspection: adult woman. Black hair, white horns, yellow eye, black wings, tavern lanterns. Albedo reads clearly. No hands are visible, so the Wave J hand change worked on this cell. The dress stays closed over the hips: `dress hiked` did not open the skirt once there was no hand to lift it. The back is open. Adult reading is clear.
- Keep: `arms behind back, no hands visible` plus `hands, fingers` in the negative.
- Change on the cells that had not been submitted yet: say `backless dress, open skirt, bare hips` so the leak does not depend on a lifting hand.

### k-serie-archive — not a result

Studio job `7a07ce99-b97b-49d8-bd88-5e7b5f353cdd` reached ComfyUI prompt `6ab21b16-5450-4338-af2c-c66e3054244a` and was `running` when Studio and ComfyUI both died. No output file. That prompt is not resubmitted. The Frieren-series cell continues as `k2-serie-wai` on WAI, with the open-skirt wording, a new seed, and not this prompt.

The other Wave K receipts (`k-crusch-hall` `078fcc5b`, `k-blackswan-train` `f569b527`, `k-yinlin-teahouse` `882818cc`, `k-changli-palace` `f66f3355`, `k-tamarinne-stage` `13f4a478`, `k-scathach-castle` `ef75f560`) were still queued with empty prompt ids. They are not resumed. Replacements are `k2-*` with the open-skirt sentence, posted one at a time.

### k2-serie-wai — completed, counted

The Anima prompt `6ab21b16` was not repeated. This is WAI, seed `2026092331`, open skirt instead of `dress hiked`.

- Preset `wai`. Steps 24, CFG 5, euler ancestral / normal, `nsfw_girls.safetensors` at 0.7.
- Studio job `1bcc752b-a836-4c3f-bd21-9965b2237136`. ComfyUI prompt `afeabf4b-9abf-4cc1-92dd-2b1051b45208`. 36.6 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00022_.png`.
- Positive adds `serie (sousou no frieren), long blonde hair, elf, pointy ears, adult mage, tall woman, magic archive, gold trim dress` plus the open-skirt rear sentence.
- Negative: Wave K negative (`hands, fingers, logo, letters` included).
- Inspection: adult woman, not the discarded Frieren face. Long blonde hair, green eyes, pointed ears, a gold ring ornament, white and gold backless dress, shelves and bottles. Serie is recognizable and reads adult. The skirt is open because a hand is gripping it, and that hand has extra fingers. The hip hand looks like five fingers. So forbidding hands did not stop a lifting hand on this seed.
- Keep: Serie as the Frieren-series adult. Do not go back to the discarded Frieren frame.
- Change later: a military or "hand on hip" pose still invents hands. Changli, below, is the clean no-hand result.

### k2-crusch-hall — completed, counted

- Preset `cstati-v3-baseline`, seed `2026092332`, steps 24, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `e534f0d2-3439-47e6-900a-c7a37eec6fc4`. ComfyUI prompt `084546d6-0ff4-42a7-9169-931661ebe562`. 91.7 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\CSTati-v3-Baseline_00005_.png`.
- Positive: crusch karsten, short green hair, yellow eyes, military uniform, adult duchess, castle hall, plus the open-skirt rear sentence.
- Inspection: adult woman. Green hair, yellow eye, blue coat, gold epaulettes, red cuffs, castle stairs. Crusch reads clearly. The coat is backless with a high slit. Both hands sit on the hips. One of them has an extra finger. The uniform prompt overrode "no hands" with an akimbo pose.
- Keep: CSTati castle uniform for Crusch.
- Change later: do not combine a uniform with a no-hands request. The coat pose wants hands.

### k2-changli-palace — completed, counted

- Preset `yumeflux-ilv1-baseline`, seed `2026092333`, steps 24, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `e5b5beb3-97cf-4789-ba34-a37dc284d88a`. ComfyUI prompt `6b322986-92fe-40bb-b324-4a0a1c35fb97`. 48.3 s.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\YumeFlux-ILv1-Baseline_00004_.png`.
- Positive: changli (wuthering waves), long pink hair, hair ornament, adult counselor, palace hall, white and red dress, plus the open-skirt rear sentence. No animal ears.
- Inspection: adult woman. Pink hair, red eyes, hairpins, red backless dress, palace columns. Changli's costume reads. The skirt is open and the hips are bare with the dress still on. No hands are in frame. This is the Wave K hand fix actually holding, together with the open-skirt leak that Albedo's closed dress missed.
- Keep: this wording. YumeFlux, palace, open skirt, arms out of frame, `hands, fingers` in the negative.

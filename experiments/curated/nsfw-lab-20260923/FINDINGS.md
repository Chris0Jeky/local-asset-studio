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

## Wave L plan — 23 September continuation

Plans only. A line here is not a result until a still file exists and the fields below it are filled. No prompt id already written above is repeated. Dead ids that stay dead: `4dc53889-e2e0-4c22-8e66-93cbf125b4d1` (Elsa), `6ab21b16-5450-4338-af2c-c66e3054244a` (Serie on Anima), and the Animagine Scathach id `c3b53ce6-3083-4fec-a236-1095a5fb87e2` if it was the one that died with no file. Empty Wave K receipts are not resumed.

These are adult-coded leads. Each series that already has a counted cell gets a further cell, and the four named-but-not-finished adults are new jobs. The positives are not the Wave K sentence (`backless dress, open skirt, bare hips, arms behind back`). Fast families only. Steps 20, 832×1216. No many-minute model.

Shared negative: `worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, bad anatomy, bad hands, extra digits, missing fingers, text, watermark, child, loli, shota, logo, letters`.

| Cell | Series | Preset | Seed | Intended change |
| --- | --- | --- | --- | --- |
| l-narberal-hall | Overlord | cstati-v3-baseline | 2026092351 | Further adult. Front stand, maid dress and apron still on, hands on thighs. |
| l-luna-guild | Konosuba | wai | 2026092352 | Further adult. Seated at the guild desk, robe on, hands flat on the desk. |
| l-priscilla-throne | Re:Zero | cstati-v3-baseline | 2026092353 | Further adult. Seated on a throne, red dress on, fan in the lap. Not Elsa's dead prompt. |
| l-himeno-rooftop | Chainsaw Man | wai | 2026092354 | Further adult. Changed after Luna: wide full body, both hands in pockets, no hand near the face. |
| l-scathach-yard | Fate | anifox-v2-baseline | 2026092355 | The unfinished Scathach, as a new AniFox job. Standing, spear, outfit on. Not Animagine. |
| l-zhuyuan-street | Zenless Zone Zero | yumeflux-ilv1-baseline | 2026092356 | Further adult. Night street, jacket open, shirt and pants on, hands on thighs. |
| l-blackswan-ballroom | Honkai: Star Rail | wai | 2026092357 | The unfinished Black Swan, as a new job. Seated in a ballroom, gown and gloves on. Not the empty train receipt. |
| l-tamarinne-stage | Epic Seven | anifox-v2-baseline | 2026092358 | The unfinished Tamarinne, as a new job. Front stand, stage dress on, singing. Not the empty stage receipt. |
| l-ubel-road | Frieren | anima-v1-baseline | 2026092359 | Further adult in the series. Standing on a road, coat on. Not Serie, and not the dead Anima prompt. |
| l-yinlin-teahouse | Wuthering Waves | janima-v1-baseline | 2026092360 | The unfinished Yinlin, as a new job. Seated in a teahouse, dress on. Not the empty teahouse receipt. |

SDXL cells are submitted first, one at a time. Anima and JANIMA wait until those receipts are done, because a model switch after a spill killed the queue on 23 September. A follow-up cell after these inspections will change pose, costume, expression, silhouette, camera, place, or adapter because of a judgement written in this continuation.

## Wave L results

Fast families, steps 20, 832×1216. Generated is not accepted and not licensed. Imperfect stills stay in the record.

### l-narberal-hall — completed, counted

- Preset `cstati-v3-baseline`, seed `2026092351`, steps 20, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `872bb18d-f99a-443c-963c-63409bc7d9ae`. ComfyUI prompt `677d8652-bf0d-4c93-a92c-716f648ec52d`. 28.4 s. No spill line.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\CSTati-v3-Baseline_00007_.png`.
- Positive: narberal gamma, battle maid, black dress, white apron, mansion hall, standing, front view, hands on thighs.
- Inspection: adult woman. Black hair, yellow eyes, maid headdress, yellow bow, black dress, white apron, dark mansion. Narberal reads clearly. The frame is a close lean, so the full standing silhouette is cropped at the lap. Both hands are on the thighs. The near hand's fingers are long and the count is messy where they overlap. The dress and apron stay on.
- Keep: CSTati front maid for an Overlord adult. The still stays even though the finger count is messy.
- Change next: do not use a close crop when the question is the whole costume. Luna, next, is the seated test.

### l-luna-guild — completed, counted

- Preset `wai`, seed `2026092352`, steps 20, CFG 5, euler ancestral / normal, `nsfw_girls.safetensors` at 0.7.
- Studio job `5bb35721-e191-415a-93e8-a8adc224f7d8`. ComfyUI prompt `0ac4d893-0e68-4269-a737-9633fd28fd52`. 32.2 s. The receipt says GPU memory spilled 3.7 GB into system RAM.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00027_.png`.
- Positive: luna (konosuba), glasses, guild desk, seated, hands flat on the desk.
- Inspection: adult woman. Long blue hair, blue eyes, red glasses, blue hair ornaments, white robe, guild interior. Luna reads clearly. The robe is open at the chest and still on. One hand pinches the glasses. The other lies flat on the desk. Asking for both hands on the desk did not stop a face gesture.
- Keep: WAI seated guild portrait for Luna. Adult reading is clear.
- Change the next unsubmitted cell: Himeno will not ask for hands on the knees. She gets a wide full-body shot with both hands in her pockets and no hand near the face, because this glasses hand is the active-hand failure and Narberal's crop hid the costume.

### l-priscilla-throne — completed, counted

- Preset `cstati-v3-baseline`, seed `2026092353`, steps 20, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `afd22199-a317-4fc4-b189-33fb30af94cd`. ComfyUI prompt `2ad9ed78-4412-4e3d-b543-31e517c79e69`. 36.2 s. The receipt says GPU memory spilled 6.0 GB into system RAM. The queue stopped here so ComfyUI could be restarted before the next job. This prompt is not resubmitted.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\CSTati-v3-Baseline_00008_.png`.
- Positive: priscilla barielle, red dress, folding fan, throne, both hands holding a closed fan in her lap.
- Inspection: adult woman. Orange hair, red eyes, red dress with black fur trim, open red fan, gold throne. Priscilla reads clearly. The dress stays on, with a high slit. The fan is raised in one hand, not closed in the lap, and the other hand rests on the arm of the throne. A small horn-shaped hair ornament was invented. Adult reading is clear.
- Keep: CSTati throne and fan for Priscilla. The still stays.
- Change later: a prop in the lap becomes a raised prop. That agrees with Luna. Pocketed hands are the Himeno test.

### l-himeno-rooftop — completed, counted

Changed before submit because Luna raised a hand to her glasses and Narberal's frame cropped the costume. This cell asks for a wide full body, both hands in pockets, and no hand near the face.

- Preset `wai`, seed `2026092354`, steps 20, CFG 5, euler ancestral / normal, `nsfw_girls.safetensors` at 0.7.
- Studio job `7a0d0d76-ab3b-4392-82c1-816356d51139`. ComfyUI prompt `b7d2516e-5bb5-4fe7-b95b-7f934e27f5e9`. 28.4 s. No spill line. ComfyUI had been restarted after Priscilla's 6.0 GB spill.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00028_.png`.
- Positive: himeno (chainsaw man), eyepatch, white shirt, black necktie, dark pants, rooftop at dusk, full body, wide shot, both hands inside her pants pockets, no hand near the face.
- Inspection: adult woman. Short black hair, eyepatch, green eye, white shirt, black tie, black trousers, dress shoes, night rooftop and a city. Himeno reads clearly. The wide shot holds: the shoes and the railing are in frame. No hand is near the face, so that part of the Luna change worked. Both pockets did not: one hand is tucked at the hip, and the other lies flat on the ledge. Shirt and pants stay on.
- Keep: the wide rooftop and the ban on a face hand. The still stays, including the ledge hand.
- Change later: pockets are not a reliable park. A ledge or a thigh still draws the second hand.

### l-scathach-yard — completed, counted

New AniFox job. Not the dead Animagine prompt.

- Preset `anifox-v2-baseline`, seed `2026092355`, steps 20, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `621e2e6e-46a7-4a33-8017-00d77b53df92`. ComfyUI prompt `e7de8278-221b-4da2-811f-f5f10ae1eefe`. 30.2 s. Spill 3.7 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\AniFox-v2-Baseline_00007_.png`.
- Positive: scathach (fate), long purple hair, red eyes, spear, castle training yard, outfit still on, both hands on the spear shaft.
- Inspection: adult woman. Long pink-purple hair, red eyes, red spear, castle towers, black outfit with a high slit and a metal shoulder plate. Scathach reads clearly. One hand grips the spear. The other hangs open at her side, so "both hands on the spear" missed. The outfit stays on. Adult reading is clear.
- Keep: AniFox spear and castle for Scathach. The still stays.

### l-zhuyuan-street — completed, counted

- Preset `yumeflux-ilv1-baseline`, seed `2026092356`, steps 20, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `445e7734-dad0-4c01-9701-852cc8347c7d`. ComfyUI prompt `6d2e8987-d288-43bc-89ff-ccfb5b9f1ee8`. 32.2 s. Spill 5.6 GB. The queue stopped here for a restart. This prompt is not resubmitted.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\YumeFlux-ILv1-Baseline_00006_.png`.
- Positive: zhu yuan, police jacket, night city street, jacket open, shirt and pants on, hands on thighs.
- Inspection: adult woman. Dark hair tied up, blue eyes, open police jacket, white shirt, black pants, night street. Zhu Yuan reads as the public-security officer. Both hands rest on the thighs. The fingers are long and the count is uneven. Shirt and pants stay on. Background signs are stylized glyphs even with `logo, letters` in the negative. Distant pedestrians are silhouettes.
- Keep: YumeFlux night street and the open jacket over a shirt. The still stays.

### l-blackswan-ballroom — completed, counted

New WAI job. Not the empty train receipt.

- Preset `wai`, seed `2026092357`, steps 20, CFG 5, euler ancestral / normal, `nsfw_girls.safetensors` at 0.7.
- Studio job `da6ad455-4e67-4aaa-b842-dbb653e10586`. ComfyUI prompt `8a93cf18-d10b-4f02-b4fc-6e1af81cd65d`. 26.3 s. No spill line. ComfyUI had been restarted after Zhu Yuan's 5.6 GB spill.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00029_.png`.
- Positive: black swan (honkai: star rail), veil, purple evening gown, black gloves, ballroom, gloved hands folded in her lap.
- Inspection: adult woman. Long pale-purple hair, veil, purple eyes, purple gown with a flower emblem, chandelier hall. Black Swan reads clearly. The gown stays on. The lap-hands sentence failed the same way Luna's desk hands failed: one gloved finger is at her lips, and the other hand rests on the bench. Adult reading is clear.
- Keep: WAI ballroom gown for Black Swan. The still stays, including the shush.
- Change the unsubmitted Yinlin and Übel cells: no hand near the face. Yinlin's teacup is dropped, because a prop in the hands became a face gesture here and on Luna and Priscilla.

### l-tamarinne-stage — completed, counted

New AniFox job. Not the empty stage receipt.

- Preset `anifox-v2-baseline`, seed `2026092358`, steps 20, CFG 5, euler ancestral / karras, `nsfw_girls.safetensors` at 0.7.
- Studio job `84217db5-be3c-4e55-89b7-37af2a7e6e06`. ComfyUI prompt `3b7042bf-909b-4a31-a4d1-a8a4c2de8152`. 30.2 s. No spill line.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\AniFox-v2-Baseline_00008_.png`.
- Positive: tamarinne (epic seven), pink stage dress, microphone, concert stage, one arm raised.
- Inspection: adult woman on a lit stage, long pink hair, headset mic, black white and pink stage dress. The dress stays on. Both arms are raised and the hands leave the top of the frame, so there is no finger count to fail. The face is a generic smiling idol. With only a handful of Danbooru posts, the likeness was expected to be weak, and it is. A second pink-haired face is painted on the screen behind her.
- Keep: the stage dress and the arms-out-of-frame pose. The still stays. Likeness is the open problem, not a reason to drop the frame.

### l-ubel-road — completed, counted

Changed before submit because Black Swan turned lap-hands into a finger at the lips. This cell asks for hands behind the back and no hand near the face. Not Serie's dead Anima prompt.

- Preset `anima-v1-baseline`, seed `2026092359`, steps 20, CFG 4.5, euler / simple, slot 1 `nsfw_girls_anima` at 0.85, other slots 0.
- Studio job `b24a6081-8f4d-4893-9099-2d21b95285b1`. ComfyUI prompt `beb477e1-2749-4ffe-984b-081a4afa55ea`. 24.2 s. No spill line. ComfyUI had been restarted after the clothed batch's 4.6 GB spill.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\Anima-v1-Baseline_00041_.png`.
- Positive: ubel (sousou no frieren), short blue hair, dark coat, white shirt, country road, full body, both hands behind her back, no hand near the face.
- Inspection: adult woman. Short blue hair, blue eyes, long dark coat, white shirt, high-waisted dark trousers, boots, a dirt road through fields. Übel's short blue hair and coat read. The full body is in frame. No hand is near the face, and both hands are hidden behind the back, so the Black Swan change held. Coat and shirt stay on. Adult reading is clear.
- Keep: hands behind the back when a face gesture is the failure. The still stays.

### l-yinlin-teahouse — completed, counted

New JANIMA job. Not the empty teahouse receipt. The teacup was removed before submit for the same reason as Übel.

- Preset `janima-v1-baseline`, seed `2026092360`, steps 20, CFG 4.5, euler / simple, slot 5 `nsfw_girls_anima` at 0.85, other slots 0.
- Studio job `8c5cfc8a-5760-4360-a30c-9ba7089cc179`. ComfyUI prompt `d6d0e2ce-dd66-4ccb-9ab1-8b2f17486f35`. 22.2 s. No spill line.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\JANIMA-v1-Baseline_00004_.png`.
- Positive: yinlin (wuthering waves), purple dress, teahouse, seated, wide shot, both hands hidden in her lap, no hand near the face.
- Inspection: adult woman. Long dark hair, purple eyes, purple halter gown, gold jewelry, pavilion with a tea set on the table. Yinlin reads clearly. The dress stays on. No hand is near the face. The hands are clasped low in the lap rather than fully hidden, and the overlapping fingers are hard to count. That is still the lap, not a shush. Adult reading is clear.
- Keep: JANIMA teahouse and the ban on a face hand. The still stays, including the clasped fingers.

No many-minute model was used. One Obsession and Pearly were not run. The new NSFW positives are front stands, seated portraits, a spear, a stage, and a road. None of them repeats the Wave K sentence `backless dress, open skirt, bare hips, arms behind back, no hands visible`.

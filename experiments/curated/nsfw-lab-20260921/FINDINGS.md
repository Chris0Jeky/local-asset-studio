# NSFW lab findings — 21 September 2026

Generated, not accepted, not licensed. Adult original characters. Fast families only.

## Already known (civitai intake wave 2, same day)

- Anima + `nsfw_girls_anima` undresses reliably; extra fingers are common.
- PetiFlow (`pearlypetif`, flat colors) can beat a full-nude prompt and collapse to a face-focus portrait.
- Esearu (`pearlyese`, `(soft colors:1.2)`) pushes extreme proportions and a halo.
- BunnySlop (`@sl0p`) stays a glossy bedroom selfie.
- Ringeko (`r1ng3k0`) on AniFox: white hime, red eyes.
- Shiny NAI (`shiny skin`) and glossy (`glossy_anime_style`) add wet/specular skin.
- WAI + Illustrious `nsfw_girls` nudes well; extra fingers on raised arms.
- YumeFlux often adds black X pasties instead of a full nude.
- Animagine stayed in lingerie on the same nude prompt.
- Pony + Illustrious NSFW adapter looks photoreal/3D — poor family match.
- Noob + that adapter is soft/blurry.
- Civitai scavenge (PR #756 explicit queue): on WAI put `nsfw` or `explicit` in the **positive**; do not negative all four rating tags; do not rely on the rating tag alone to undress.

## Wave A (seed 2026092151, 16/16 completed, ~5.4 min)

Character lock: long black hair, red eyes, adult woman, Anima + `nsfw_girls_anima` 0.85 unless noted.

| Cell | Seconds | Inspection |
| --- | ---: | --- |
| a-body-small | 34.3 | Slim, small chest, sitting on bed. Tag works. Extra fingers on the bed-resting hand. |
| a-body-medium | 18.2 | Clearly larger than small; still a locked face/hair. |
| a-body-large | 18.2 | Full bust, thicker thighs. Extra fingers on both bed hands. |
| a-body-huge | 18.1 | Voluptuous; the pose rotated to a 3/4 rear because `large ass` entered the prompt. |
| a-pose-behind | 18.2 | Standing rear view, looking back. Ass focus fired. Extra fingers on the hip hand. |
| a-pose-lying | 18.2 | On her back, from above. Extra fingers on both chest-holding hands. |
| a-pose-allfours | 18.2 | Became a 3/4 rear lean on the bed, not a textbook all-fours. Still sexy. |
| a-pose-frombelow | 18.1 | Standing low camera. Pubic hair appeared without being asked. |
| a-detail-shiny | 18.1 | Wet highlights + a selfie arm. Horn-like hair nubs. Extra fingers on the camera arm. |
| a-hands-positive | 18.1 | **Best hands of the wave.** `hands on thighs, five fingers, neat hands` put both hands in frame with five fingers. |
| a-complex | 18.1 | Warm lamp, messy hair, parted lips, sweat. Sexiest lighting of the Anima bedroom set. Extra fingers on both bed hands. |
| a-wildcard-pose | 18.2 | Expanded to a rear view under a studio key light (`nsfw_setting` dim studio). Extra fingers. |
| a-wai-nsfw-tag | 34.2 | WAI nude, pale, red eyes. Hands between thighs, extra fingers. |
| a-wai-explicit-tag | 12.2 | Almost the same picture as `nsfw`. Rating tag did not change undressing when `nude` was already in the prompt. |
| a-wai-no-rating | 12.1 | Same again. With anatomy tags present, WAI rating tags are optional. |
| a-onsen-steam | 32.2 | Wooden bath, steam, snow, wet skin. Strongest setting change. Extra fingers on the raised hand. |

### What works (promote)

- Breast-size tags at a locked seed: small / medium / large / huge are distinguishable on Anima.
- `from behind` + `looking back` + `ass focus`.
- `from below` standing cowboy.
- Warm lamp + messy hair + parted lips + sweat (complex prompt) for attractiveness.
- `hands on thighs, five fingers, neat hands` is the first wording that actually showed five-finger hands.
- Onsen / wooden bath / steam as a setting.
- `__nsfw_pose__` + `__nsfw_setting__` expand and change the picture.

### What does not (or weakly)

- WAI `nsfw` vs `explicit` vs none: no useful difference once `nude` is in the positive.
- `all fours` drifted to a rear lean.
- Extra fingers remain on raised or supporting hands unless the prompt parks the hands on the thighs.
- `huge breasts` + `large ass` steals the camera toward a rear 3/4.

### Wave B (12/12 completed)

| Cell | Inspection |
| --- | --- |
| b-keeper-complex-hands | Warm lamp + messy hair + sweat still the sexiest Anima lighting. Hands went to the mouth, extra fingers. |
| b-esearu-soft | Esearu 0.55 + `medium breasts` kept a normal figure and a halo. Hands on thighs with five fingers. |
| b-petiflow-half | PetiFlow 0.5 still flattens the background, but this time it kept a full nude (wave 2 had been face-only). |
| b-wai-glossy-below | Strongest "sexy camera" of wave B: glossy skin, from-below 3/4. Extra fingers on the far hand. |
| b-lingerie-implied | Sheer unbuttoned shirt at the same seed as the large nude. Implied can beat full nude for attractiveness. |
| b-wai-onsen | Leaning in the bath, steam, autumn leaves. Extra fingers on the deck hands. |
| b-hourglass-below | The word `hourglass` spawned an hourglass prop. Use `slim waist, wide hips` instead of the English noun. |
| b-anifox-ringeko-behind | Rear view is excellent. White-hime trigger did not dominate (brown hair). Extra fingers. |

Promote: WAI glossy + from below; sheer shirt; Esearu at 0.55 for a softer nude; `slim waist, wide hips` not `hourglass`.

## Owner Studio/nsfw folder (read, not re-run)

Path: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\nsfw`. The later JANIMA stills are the "very sexy" target: all fours / looking back, dildo, sweat, blush, open mouth, huge ass, red/purple light (`JANIMA-v1-Baseline_00045_.png`, `anima-portrait_00007_.png`, `00040_.png`). Casual sexy: fox-girl latex selfie (`Anima-v1-Baseline_00026_.png`). Character-coded: Kaguya-like lace (`WAI-Illustration_00015_.png`); Konosuba-red swimsuit tease (`JANIMA-v1-Baseline_00023_.png` — Megumin colours; Megumin is not used as a tag here because she is not adult-coded). Krea pool still (`krea-anime-atelier_00014_.png`) matches the looking-back wet rear.

Wave C copies that explicit language onto **adult** franchise tags (2B, Kafka, Darkness, Aqua, Cynthia, Asuna, Yelan, Raiden, Tifa) plus expression locks (ahegao / naughty / embarrassed) and casual undress.

## Civitai.red character LoRAs (download counts, 21 Sep)

Not installed this wave — Illustrious/Anima/WAI already take Danbooru character tags. Popular adult looks: 2B 32k dl, Yelan 19k, Kafka 7.6k, Darkness 6.6k, Cynthia 5.3k, Asuna 3.5k. Skip Megumin, child Pokemon, child Genshin/HSR.

## Wave C (16/16 completed)

Danbooru character tags on Anima / WAI / JANIMA, no extra character LoRAs. Adult-coded only.

| Cell | Inspection |
| --- | --- |
| c-2b-dildo-behind | 2B likeness (white bob, black band, mole). Purple dildo, looking back. Closest to the owner's JANIMA stills. |
| c-kafka-ahegao-masturbate | Kafka: purple hair, sunglasses, ahegao, fingering. Extra fingers. WAI watermark. |
| c-darkness-spread-embarrassed | Darkness: blonde, blue eyes, blush, covering. Extra fingers. |
| c-aqua-casual-undress | Aqua: blue hair, open white shirt, blue skirt, embarrassed. Extra fingers. |
| c-cynthia-behind-naughty | Cynthia: long blonde, hair clip, looking back. Extra fingers. |
| c-asuna-lingerie-smirk | Asuna: orange hair, black lace, smirk. Extra fingers on the door. |
| c-yelan-masturbate-tongue | Yelan-like blue hair, tongue out, fingering. Extra fingers. |
| c-2b-selfie-casual | 2B latex + fishnets hotel selfie. Matches the owner's casual-sexy still. Extra fingers on the phone. |
| c-darkness-dildo-owner-style | Red room, looking back, black dildo. Owner 00045 language on Darkness. |
| c-raiden-frombelow-halflid | Raiden braid, from below, half-lidded. Hands mostly out of frame. |
| c-2b-expr-ahegao / naughty / embarrassed | Same seed 2026092171. Expressions are distinct: tongue-out ahegao, half-lid smirk, looking-away blush. |
| c-2b-fingering | Explicit solo. Extra fingers on the active hand. |
| c-tifa-onsen | Black hair, onsen, naughty smile. Extra fingers covering. |
| c-wildcard-character-act | Blonde all-fours looking back. Wildcards fired. Extra fingers. |

Promote: character tags first; JANIMA + dildo + looking back for the owner's explicit look; lock seed for expression swaps; casual latex selfie and lace lingerie for "sexy without full explicit". Still skip Megumin and child franchise tags. Extra fingers remain on any hand that is doing something.

## Wave D — anatomy (16/16, seed 2026092180, 2B lock)

| Cell | What the tag actually did |
| --- | --- |
| d-pussy-closed | Still a visible slit, not a true innie. "Closed" is weak against the NSFW adapter. |
| d-pussy-spread | Fingers spreading. Extra fingers. Opening is real. |
| d-labia-small vs plump | Both stay spread/gaping. Plump is a bit more open. "Small labia" does not make an innie. |
| d-clitoris | Clit is drawn. Extra fingers on both spreading hands. |
| d-gaping-wet | Fluids and a pubic tuft. Strongest "aroused" look. Hands out of the way. |
| d-anus-puckered vs spread | **Clear pair.** Puckered is a closed ring; spread is an open hole. |
| d-nipples-puffy | Protruding nipples, large areolae. Works. |
| d-nipples-inverted | Flatter, slightly inverted. 2B blindfold returned. |
| d-breasts-hanging | Gravity from below. Extra fingers on the selfie arms. |
| d-mouth-uvula | Teeth, tongue, throat, saliva. Strong close-up. |
| d-fingers-spread | Palms toward camera **still six fingers per hand**. Spread fingers does not fix extras. |
| d-feet-spread-toes | Five toes each, spread. Feet are more reliable than hands. |

## q-29

Owner 21 Sep: merge the parked stack, specifics later. PR #416 merged (`77f6b276`). #417 retargeted to `main` and branch-updated; not merged while checks are stale/red.

## Wave F (family/LoRA combos, same 2B explicit prompt)

CSTati, YumeFlux, Animagine, One Obsession, Pearly, WAI glossy/shiny all kept 2B identity and the dildo pose. Animagine added android seams. YumeFlux/WAI shiny invented a pod. Extra fingers on gloves/hands everywhere. Glossy is the cleanest finish.

## Wave G — settings and costumes (not plain nudes)

The recipe that works: `from behind, looking back, smirk` + a real place + `skirt lift` / `shorts pulled down` / `towel slipping` + `no panties` + clothes still on + `faceless crowd, they do not notice`.

| Cell | Inspection |
| --- | --- |
| g-aqua-tavern-skirt | **Hits the request.** Aqua, tavern lanterns, patrons facing away, stool, smirk, skirt up, ass/anus. Extra fingers on the hip. |
| g-aqua-tavern-janima | Same beat, strapless dress. Extra fingers. |
| g-aqua-tavern-complex | Best composition: leaning on the bar, costume on, smirk, tavern, one patron in the back. Extra fingers on the rail. |
| g-darkness-armor-peek | Armor + skirt up, embarrassed look, tavern crowd. Extra fingers. |
| g-2b-hotel-corridor | Smirk, black dress hiked, city night. Extra fingers on the door. |
| g-2b-corridor-complex | Stronger corridor, dress still on. Extra fingers. |
| g-tifa-bar-shorts | Shorts pulled down, smirk, bar. A patron is looking — "nobody notices" failed. Extra fingers. |
| g-tifa-bar-complex | Cleaner bar, no extra patron. Extra fingers. |
| g-kafka-bar-booth | Kafka identity + bar, stayed zipped. Jacket-open did not undress. Extra fingers. |
| g-asuna-inn | Nightgown, smirk, inn. Modest. Extra fingers. |
| g-raiden-shrine | Kimono hiked at a shrine at night. Extra fingers. |
| g-2b-onsen-towel | Towel slipping in a locker room. Extra fingers. |

Test of the intel: these are sexier than the plain nudes. Keep clothes. Put the leak at the hem. Crowd must face away or be omitted.

## Wave E — repair pipeline on keepers

`anime-detail-fix` (face then hands) and `anime-hand` on `c-2b-dildo-behind` and the mouth close-up:

- Face on the 2B dildo got a slightly sharper eye. The extra fingers on the bed-edge hand **did not go away** — the detector likely missed a small/edge hand.
- `anime-hand` on the same image is almost a no-op. Same extra fingers.
- Mouth close-up was already a face crop; the pass barely moved it.

So: these repair presets help when a YOLO box actually fires on a large hand/face. They are not a cure for extra fingers at the edge of the frame. Prefer `hands on thighs, five fingers` at txt2img time, or park the hands out of frame (`from behind` with no visible hands). The Aqua tavern cells hide hands better than the spreading-pussy cells.

`anime-detail-fix` on `g-aqua-tavern-skirt` and `g-aqua-tavern-complex` (jobs `b9181a3c`, `b9045083`): extra fingers on the hip/bar **still there**. Face smile is slightly cleaner. Do not expect this pass to save a tavern scene.

## Wave H — tavern recipe iterations

`h-aqua-tavern-hands-bar` is the best stealth-tease so far: both arms on the counter, skirt up, smirk, tavern. `hands out of frame` still grew a hand. Darkness tavern: crowd looked at her. 2B in a tavern works as costume+place, leak is milder.

## Wave I — more places, costumes, families (16/16)

Same recipe on more adult looks. WAI still the most reliable for costume+place.

| Cell | Inspection |
| --- | --- |
| i-aqua-tavern-janima-bar | Aqua, tavern, dress up. Hands became pointing fingers (extras). |
| i-aqua-standing-bar | Standing lean, leak is strong. Crowd is looking. Extra fingers on the bar. |
| i-asuna-tavern | Asuna in a tavern, skirt up, smirk, crowd facing away. Extra fingers. |
| i-asuna-inn-lift | Nightgown, smirk, inn. Milder leak. Extra fingers. |
| i-yelan-teahouse-lift | Qipao slit, smirk, lanterns. Extra fingers. |
| i-kafka-train-lift | Night train, skirt up, city lights. Extra fingers. |
| i-2b-library | Library aisle, dress hiked. Extra fingers on the glove. |
| i-tifa-bar-janima | Shorts pulled down, no extra patron. Extra fingers. |
| i-darkness-hands-bar | Armor + skirt. A knight is looking — stealth failed again. Extra fingers. |
| i-2b-onsen-towel-wai | Towel + Pod. Extra fingers. |

The recipe ports: Asuna tavern, Kafka train, Yelan teahouse, 2B library. Darkness still attracts onlookers. JANIMA Aqua ignored "hands on the bar" and posed.

## q-29

#416, #417, #419 merged. #420 retargeted to main, not merged until its refresh is green. Programme specifics still later.

**Retired, 23 September 2026, 22:01.** The Asuna cells above (`c-asuna-lingerie-smirk`, `g-asuna-inn`, `i-asuna-tavern`,
`i-asuna-inn-lift`) were removed from `presets/nsfw-intel.json` and `presets/wildcards/nsfw_character.txt` under a
child-coded reading. The rows stayed here as history.

**Restored, 23 September 2026, 22:41.** The owner double-checked and concluded that Asuna can stay: her canon age is
acceptable. The wildcard line and the three intel cells are back. `i-asuna-inn-lift` was never an intel entry; its
findings row and manifest entry had remained. Do not delete the render files.

# NSFW technique stacks — measured 23 September 2026

Use a stack by its id. A line is measured only when a cell id is attached. External notes, when they arrive, stay marked external and do not override a measured failure.

Generated is not accepted and not licensed. Adult-in-canon characters only. A youthful face on an adult-in-canon character is a composition note, not a reason to drop the stack.

## T1 — rear leak, hands gone

Use when the skirt must open and the hands must stay out.

Positive tail: `from behind, looking back, backless dress, open skirt, bare hips, clothes still on, no panties, arms behind back, no hands visible`

Negative add: `hands, fingers, logo, letters` on top of the usual quality and `child, loli, shota` line.

Held: `k2-changli-palace`, `m-changli-heat` (job `f9204d2d`, prompt `a537d1da`), `m-frieren-heat` (job `aee6f9a3`, prompt `18a6f8c0`). The first Frieren library cell stayed closed because it asked for a hike plus a hand on a shelf. This tail is what opened it.

Breaks it:

- `from below` on the same seed brought two hands back at the lower edge (`m-changli-below`, job `e06a072d`, prompt `d0e72070`). Use T1b when the lower crop is the point. Do not use T1b when the question is the hands.
- A front-seated `skirt lift` stayed closed (`j-albedo-tavern`).
- A military uniform overrode the no-hands line with hands on the hips (`k2-crusch-hall`).
- `hands out of frame` without `hands, fingers` in the negative still drew a lifting hand (`j-shalltear-bedroom`, `j-artoria-castle`).

## T2 — heat on top of a pose that already held

Add `blush, parted lips, sweat` and one practical light (`red light` in a palace, `warm lamp light` in a library). Do not use the word hourglass.

Held on T1: `m-changli-heat` showed blush, parted lips, sweat droplets, and saturated red light, and the hands stayed gone. `m-frieren-heat` showed blush and sweat under the library lamp, and the skirt opened.

Weaker on a front office crop: `m-makima-lean` (job `1b020595`, prompt `d9815111`) got blush and a little sweat, and the mouth stayed only slightly open.

## T3 — stop the hand at the face

A prop or a lap task grows a hand at the face: glasses (`l-luna-guild`), a fan (`l-priscilla-throne`), folded gloves (`l-blackswan-ballroom`).

Held instead: `no hand near the face` plus hands behind the back (`l-ubel-road`), or hands clasped in the lap with no prop (`l-yinlin-teahouse`). Pockets did not hold both hands (`l-himeno-rooftop`).

## T4 — front open shirt

Positive: `shirt unbuttoned, no bra, shirt still on, pants on, leaning toward the viewer, sitting on a desk`. Leave `hands, fingers` out of the negative so a hand park can exist.

Held as costume: `j-makima-office`, `m-makima-lean`. The shirt opened and the pants stayed on.

Failed hand park: `hands on thighs` while `sitting on a desk` put both hands on the desktop (`m-makima-lean`). The near hand's finger count was messy. The follow-up phrase is `both palms flat on her own thighs, not on the desk`. Job `60934d27` failed before ComfyUI assigned a prompt id (`PermissionError` renaming `state.json`), so it is not a result and the phrase is still untested.

## T5 — transfer

T1+T2 moved from Changli on YumeFlux to Frieren on WAI and the leak still opened. The face was the usual youthful Frieren design. The cell stayed counted.

Fast settings that produced these cells: 832×1216, 20 steps, CFG 5 on SDXL-family presets, CFG 4.5 on Anima and JANIMA. Warm SDXL jobs were about 26–36 seconds. No many-minute model.

## External pose notes, not yet a generation

Danbooru treats `from_behind` and `from_below` as different cameras, not a pair. That matches `m-changli-below`: both words were in one prompt and the hands came back. `looking_back` plus `from_behind` is the documented pair and is what T1 uses. `all_fours` and a deep `leaning_forward` spend the hands, so they fight `arms behind back`. `sitting` plus hands on the seat surface fights hands on the thighs. Sources, unread as pictures: Danbooru wiki pages for `looking_back`, `from_below`, `from_behind`, `sitting`, `leaning_forward`, `hands_on_own_thighs`, `all_fours`, `arms_behind_back`. Not measured here until a cell says so.

## T6 — see-through clothes LoRA

File `loras/see_through_clothes.safetensors`, Illustrious, Civitai model 1425150 version 1610854, SHA-256 `e28316454562630094767ea180b5e439b30b70a2367cad9302fe49ea0f23723c`. Trigger `seethroughILL`, strength 1, in front of the prompt, with `see through clothes, wet clothes`. Slot 2 beside `nsfw_girls` at 0.7. Illustrious presets only. Do not also say `nude`.

Measured:

- Light dress: Albedo's white dress, which T1 left opaque, became see-through over the hips. WAI, job `5e462af7`, prompt `c9500679`, `WAI-Illustration_00042_.png`, 28.5 s. Hands stayed out.
- Dark dress: Shalltear went glossy and wet, with an open back, not a transparent skirt. YumeFlux, job `d33ff53d`, prompt `aa4133c8`, `YumeFlux-ILv1-Baseline_00013_.png`, 28.2 s. Hands stayed out.
- Changli's white-and-red dress got a wet sheen and a lace slit, and the hands came back clasped in black gloves. AniFox, job `1a1e5192`, prompt `3f0bb896`, `AniFox-v2-Baseline_00011_.png`, 28.3 s.

Use T6 when a light garment will not hike. Expect gloss more than transparency on a dark dress.

## T6 page poses

The version page (Civitai model 1425150, version 1610854) has seven examples and four distinct poses. All of them put `seethroughILL` on the prompt and the LoRA at strength 1. The poses, not the original characters, are what transferred:

| Pose | What the example does | Lab cell |
| --- | --- | --- |
| Bent over, from behind, hands on the butt, bike shorts, foreshortening | The rear crop the page is known for. Hands are part of the pose, so the no-hands ban stays off. | `p-changli-bentover` |
| Seiza, from behind, ass focus, tongue out | A seated rear. The page used it on a robe. | `p-shalltear-seiza` |
| Squat, facing the viewer, hands behind the head, spread legs, bodysuit | A front pose that keeps the hands off the furniture. | `p-makima-squat` |
| Sitting, facing away, pencil skirt, close ass crop | A clothed rear sit. | `p-zhuyuan-skirt` |
| Upper-body portrait, veil, flowy dress, looking at the viewer | The mild example. Tests the LoRA on a face crop. | `p-blackswan-portrait` |

Do not copy the page's weight syntax `(tag:1.2)` onto Anima. These five stay on Illustrious presets.

All five completed. The bent-over crop, the seiza, the squat with hands behind the head, and the seated rear all held. The portrait still made a sheer panel, and the face stayed the most recognizable. The squat is the front pose that keeps hands off furniture. The bent-over crop is the one to reuse when the hips are the subject and hands are allowed.

Transfer after that: the squat held on Yinlin and Scathach. The bent-over crop held on Frieren, hands on a see-through white dress. It missed Albedo's hands because the wings cover that spot. Wiz held the seiza. Artoria held the seated rear. A finished wave is a checkpoint. The next wave puts Albedo in the squat, and gives the bent-over crop to Luna and Serie.

That wave held too. Albedo in the squat (WAI, job `bc2094e7`, prompt `6c46cb62`, `WAI-Illustration_00047_.png`, 26.5 s): hands behind the head, wings out to the sides, white dress see-through. The squat fixed the wing problem. Luna bent-over (YumeFlux, job `850d49ac`, prompt `f4a76734`, `YumeFlux-ILv1-Baseline_00017_.png`, 26.3 s): hands on the robe, see-through white cloth, glasses did not steal a hand. Serie bent-over (CSTati, job `263ad942`, prompt `eedc7769`, `CSTati-v3-Baseline_00020_.png`, 28.2 s): hands on a see-through white-and-gold dress; the place drifted to a bed. Priscilla in the squat (AniFox, job `d06d4362`, prompt `a2f42800`, `AniFox-v2-Baseline_00014_.png`, 26.3 s): hands behind the head, not on the throne arms. The squat beat the throne.

P4 confirmed both poses on new adults. The squat held on Jane (YumeFlux, job `b77fc33a`, prompt `0420cda3`, `YumeFlux-ILv1-Baseline_00018_.png`, 48.4 s, first non-dress hold, bodysuit glossy not transparent) and Black Swan (WAI, job `60808b27`, prompt `1ddd7f42`, `WAI-Illustration_00048_.png`, 30.5 s, no shush, ballroom drifted to a chapel). The bent-over crop held on Narberal (CSTati, job `2f132d78`, prompt `5dd2864b`, `CSTati-v3-Baseline_00021_.png`, 30.3 s, dark maid dress glossy, hands on the butt with clean-looking fingers). Both are promoted to stacks below.

## T7 — squat, hands behind the head

Use when a front pose must keep the hands off furniture, thrones, ledges, and faces.

Positive head: `seethroughILL, see through clothes, wet clothes` at the front. Slot 2 `see_through_clothes.safetensors` at 1 beside `nsfw_girls` at 0.7. Illustrious presets only.

Positive tail: `facing the viewer, squatting, hands behind head, spread legs, heavy sweating, shiny body, blush`

Negative add: `logo, letters` on top of the usual quality and `child, loli, shota` line. No `hands, fingers` ban: the hands are part of the pose, parked behind the head.

Held: `p-makima-squat` (CSTati, job `db749a02`, prompt `f96cc17a`, `CSTati-v3-Baseline_00018_.png`), `p2-yinlin-squat` (CSTati, job `7a94c733`, prompt `7afd1b41`, `CSTati-v3-Baseline_00019_.png`), `p2-scathach-squat` (AniFox, job `14d3e126`, prompt `21b68986`, `AniFox-v2-Baseline_00013_.png`), `p3-albedo-squat` (WAI, job `bc2094e7`, prompt `6c46cb62`, `WAI-Illustration_00047_.png`, wings out to the sides), `p3-priscilla-squat` (AniFox, job `d06d4362`, prompt `a2f42800`, `AniFox-v2-Baseline_00014_.png`, beat the throne), `p4-jane-squat` (YumeFlux, job `b77fc33a`, prompt `0420cda3`, `YumeFlux-ILv1-Baseline_00018_.png`, first non-dress hold), `p4-blackswan-squat` (WAI, job `60808b27`, prompt `1ddd7f42`, `WAI-Illustration_00048_.png`, no shush).

Breaks it: nothing has broken the pose itself. Mouth tags stay weak (Makima's mouth stayed closed). The place can drift (Black Swan's ballroom became a chapel). Dark cloth goes glossy, not transparent (Jane's bodysuit, Black Swan's bodice).

P5 added four more holds: `p5-kafka-squat` (WAI, job `2da470ec`, prompt `175d9b88`, `WAI-Illustration_00050_.png`, 30.3 s, eyes drifted yellow to purple, mouth already slightly open), `p5-yor-squat` (CSTati, job `60c224a6`, prompt `e2a207b8`, `CSTati-v3-Baseline_00023_.png`, 30.3 s), `p5-miyabi-squat` (YumeFlux, job `6ebc1d65`, prompt `ca94f401`, `YumeFlux-ILv1-Baseline_00020_.png`, 28.3 s, black top went sheer), `p5-camellia-squat` (AniFox, job `9e4404df`, prompt `6578cd7b`, `AniFox-v2-Baseline_00016_.png`, 30.3 s).

Next lever: one mouth tag (`parted lips`) on a squat that already held, same seed so the tag is the only change; then new adults in light garments.

## T8 — bent-over rear crop, hands on the butt

Use when the hips are the subject and the hands are allowed to be on the body.

Positive head: `seethroughILL, see through clothes, wet clothes` at the front. Slot 2 `see_through_clothes.safetensors` at 1 beside `nsfw_girls` at 0.7. Illustrious presets only.

Positive tail: `from behind, bent over, looking at viewer, hands on butt, dynamic angle, foreshortening, blush, sweat, slim waist, wide hips`

Negative add: `logo, letters` on top of the usual quality and `child, loli, shota` line. No `hands, fingers` ban: the hands are part of the pose.

Held: `p-changli-bentover` (WAI, job `f767bc31`, prompt `79548544`, `WAI-Illustration_00043_.png`), `p2-frieren-bentover` (YumeFlux, job `c4e06186`, prompt `b3415c34`, `YumeFlux-ILv1-Baseline_00015_.png`, light dress), `p3-luna-bentover` (YumeFlux, job `850d49ac`, prompt `f4a76734`, `YumeFlux-ILv1-Baseline_00017_.png`, glasses did not steal a hand), `p3-serie-bentover` (CSTati, job `263ad942`, prompt `eedc7769`, `CSTati-v3-Baseline_00020_.png`), `p4-narberal-bentover` (CSTati, job `2f132d78`, prompt `5dd2864b`, `CSTati-v3-Baseline_00021_.png`, dark gloss, clean-looking fingers).

Breaks it: wings cover where the hands should be (`p2-albedo-bentover`, WAI, job `543aa322`, prompt `1147dd12`, `WAI-Illustration_00045_.png`); the squat (T7) is her pose instead. Dark cloth goes glossy rather than transparent (Narberal's maid dress, Shalltear's dark skirt in M3). Do not mix with the no-hands rear stack T1.

P5 confirmed the light-cloth rule on four new adults: `p5-tifa-bentover` (AniFox, job `b3001cc0`, prompt `60f9d577`, `AniFox-v2-Baseline_00015_.png`, 34.3 s, white tank sheer, black skirt glossy), `p5-ruanmei-bentover` (WAI, job `caa2ca0b`, prompt `c100da0f`, `WAI-Illustration_00049_.png`, 34.4 s, white dress translucent, head down so `looking at viewer` missed), `p5-himeko-bentover` (YumeFlux, job `d229b2b5`, prompt `c2287555`, `YumeFlux-ILv1-Baseline_00019_.png`, 34.4 s, white shirt sheer, red skirt glossy), `p5-shorekeeper-bentover` (CSTati, job `e82bc89a`, prompt `bce0659f`, `CSTati-v3-Baseline_00022_.png`, 30.5 s, pale blue dress translucent).

T6 refined: dark heavy cloth goes glossy (Narberal, Jane, Yor), but dark thin cloth can go sheer (`p5-miyabi-squat`, YumeFlux, job `6ebc1d65`, prompt `ca94f401`, black top translucent over the chest).

Next lever: one mouth tag (`parted lips`) on a crop that already held, same seed so the tag is the only change.

## T9 — parted lips on a held pose

Use when a held T7 or T8 still needs a mouth. Add `parted lips` to the exact held prompt at the same seed. One mouth tag only.

Positive tail add: `, parted lips` after `blush` (T7) or after `blush` before `sweat` (T8). No negative change.

Held: `p6-kafka-lips` (WAI, job `5330c754`, prompt `24656736`, `WAI-Illustration_00051_.png`, 36.4 s, mouth visibly open), `p6-yor-lips` (CSTati, job `54999005`, prompt `3692c711`, `CSTati-v3-Baseline_00024_.png`, 32.4 s, slightly parted), `p6-jane-lips` (YumeFlux, job `bb54f5fe`, prompt `78219dec`, `YumeFlux-ILv1-Baseline_00021_.png`, 28.4 s, clearly open), `p6-tifa-lips` (AniFox, job `12ea069f`, prompt `4d043915`, `AniFox-v2-Baseline_00017_.png`, 26.3 s, slightly open in profile), `p6-narberal-lips` (CSTati, job `d962c65a`, prompt `d38cfcac`, `CSTati-v3-Baseline_00025_.png`, 26.5 s, slightly open in profile).

Breaks it: a face turned away leaves the tag nowhere to show (`p6-himeko-lips`, YumeFlux, job `d28fdfd0`, prompt `b58450cc`, `YumeFlux-ILv1-Baseline_00022_.png`). Bent-over profiles are a weak mouth test; front squats are the strong one. Pose, hands, and cloth were otherwise undisturbed at the same seed on all six.

Next lever: new adult characters (owner request: Persona 5 adults and more Pokemon adults) on T7/T8 with `parted lips` already in the prompt.

P7 held 8/8 with `parted lips` in the prompt from the start: `p7-takemi-bentover` (WAI, job `f14c5406`, prompt `bf8d1dc0`, `WAI-Illustration_00052_.png`, hair drifted long to short), `p7-kawakami-bentover` (CSTati, job `4360edfe`, prompt `38c2a596`, `CSTati-v3-Baseline_00026_.png`), `p7-diantha-bentover` (YumeFlux, job `bdf00dbc`, prompt `aa593892`, `YumeFlux-ILv1-Baseline_00023_.png`, white dress strongly translucent), `p7-skyla-bentover` (AniFox, job `ad37cc19`, prompt `c129d4e9`, `AniFox-v2-Baseline_00018_.png`, strong likeness), `p7-sae-squat` (WAI, job `794283fd`, prompt `7191234b`, `WAI-Illustration_00053_.png`, white shirt strongly translucent), `p7-chihaya-squat` (CSTati, job `22887bd1`, prompt `afb2fb2b`, `CSTati-v3-Baseline_00027_.png`, robe translucent), `p7-elesa-squat` (YumeFlux, job `1bb3450e`, prompt `e4d1b4f2`, `YumeFlux-ILv1-Baseline_00024_.png`, 54.5 s, black top sheer), `p7-jessie-squat` (AniFox, job `c5dfd218`, prompt `40209b6e`, `AniFox-v2-Baseline_00019_.png`, strong likeness). T6 now holds on front poses too: white garments go translucent on the squat, dark thin cloth goes sheer, dark heavy cloth goes glossy.

Next lever: camera layer, one tag at a time at the same seed: `from below` on the squat (does T1b's hand-return apply to front poses?), `cowboy shot` on the bent-over, `close-up` on the squat.

## T10 — camera tags on held poses

Use one camera tag at a time, added to the exact held prompt at the same seed, placed after the place and light and before the pose tail. No negative change.

- `from below` on the T7 squat: worm's-eye view, hips and thighs fill the foreground, face smaller at top. The hands stay hidden behind the head, so T1b's hand-return is rear-view-specific and does not apply here. Held: `p8-sae-below` (WAI, job `b1f73887`, prompt `8b778fed`, `WAI-Illustration_00054_.png`, 38.4 s), `p8-jessie-below` (AniFox, job `af62ba51`, prompt `0338c8e4`, `AniFox-v2-Baseline_00020_.png`, 32.4 s).
- `cowboy shot` on the T8 bent-over: tighter thighs-up rear crop, legs cut, pose and hands-on-butt hold. Held: `p8-diantha-cowboy` (YumeFlux, job `50e6352f`, prompt `8dbc0496`, `YumeFlux-ILv1-Baseline_00025_.png`, 34.4 s), `p8-skyla-cowboy` (AniFox, job `0cf01575`, prompt `f1f392e5`, `AniFox-v2-Baseline_00021_.png`, 30.3 s). This is the clean framing tag for T8.
- `close-up` on the T7 squat: weak. Framing tightens only slightly; `squatting, spread legs` wins and the still stays a full squat with a bigger face. Measured: `p8-elesa-closeup` (YumeFlux, job `01903e63`, prompt `de275c32`, `YumeFlux-ILv1-Baseline_00026_.png`, 32.3 s), `p8-chihaya-closeup` (CSTati, job `38716e1c`, prompt `db35471a`, `CSTati-v3-Baseline_00028_.png`, 30.3 s). A real face crop needs the pose tags trimmed; do not use `close-up` alone and expect a portrait.

Next lever: a second Illustrious adapter from civitai.red with a pose or cloth effect we do not already have, tested on/off at the same seed.

## T11 — elbow all-fours LoRA (external until a cell measures it)

File `loras/elbowallfours_il_v1.safetensors`, Illustrious, Civitai model 2536873 version 2851096, 228457476 bytes, SHA-256 `6ff1e7fe5a6df8cbca2f91c2ee6a80112a95a5d7a4890146d0de6f1cffe6cf5c` (verified against the on-disk bytes after `scripts/civitai-fetch.py`). Trigger `elbowallfours`, strength 1, in front of the prompt, with `all fours, top-down bottom-up`. Slot 2 beside `nsfw_girls` at 0.7. Illustrious presets only. Page: https://civitai.red/models/2536873/elbow-all-fours?modelVersionId=2851096

Picked because the example page shows an elbows-and-knees floor pose the lab has never run (we have bent-over, squat, seiza, seated rear, portrait). Rejected first: model 2510611 "On all fours", whose examples are furry/anthro and would risk leaking muzzles and paws. The example here wears a school uniform; our cells prompt adult characters in their own adult garments, so the pose is what transfers, not the uniform.

Test: same prompt and seed with the LoRA at 1 and at 0 on two characters, so the adapter is the only change. Hands on the ground are the open question: T3 says props grow face hands, and floor-planted hands are untested.

Measured 24 September: the WORDS hold the pose, the LoRA is optional. On/off pairs at the same seed are near-identical in pose; the LoRA at 1 changes details only (gloves, face). Floor-planted forearms did not grow face hands.

## T12 — elbow all-fours (words)

Use when the pose should be elbows and knees on the floor, face toward the viewer. This is the floor pose the lab was missing; it reads even without any pose LoRA.

Positive head: `elbowallfours, all fours, top-down bottom-up` at the front, then the usual quality line, the adult character, one floor noun (`rug floor`, `rooftop floor`), and `blush, parted lips, sweat, slim waist, wide hips`. Slot 2 may hold the elbow LoRA at 1 or sit at 0; the measured cells say 0 poses the same, so words-only is the default and saves the load.

Negative add: `logo, letters` on top of the usual quality and `child, loli, shota` line. No `hands, fingers` ban: the forearms are part of the pose, planted on the floor.

Held: `p9-tifa-crawl-on` (AniFox, job `fb348e70`, prompt `d7566255`, `AniFox-v2-Baseline_00022_.png`, 36.3 s), `p9-tifa-crawl-off` (AniFox, job `4a2f0147`, prompt `42fc24dc`, `AniFox-v2-Baseline_00023_.png`, 10.2 s), `p9-jessie-crawl-on` (AniFox, job `db8d3025`, prompt `63976c2d`, `AniFox-v2-Baseline_00024_.png`, 10.1 s), `p9-jessie-crawl-off` (AniFox, job `d74dd2b2`, prompt `c1c8bcf5`, `AniFox-v2-Baseline_00025_.png`, 10.1 s).

Breaks it: nothing yet. The trigger word `elbowallfours` stayed in all four prompts including the LoRA-off cells, so whether the bare words `all fours, top-down bottom-up` suffice alone is the next single-lever test.

P10 answered it: bare words hold the crawl (`p10-notrigger`, AniFox, job `06c438f2`, prompt `b5e9a235`, `AniFox-v2-Baseline_00031_.png`, 10.1 s). T12 is words-only from here: drop `elbowallfours` from the head.

## S1 — CFG and steps sweep (AniFox, crawl prompt)

One variable per comparison, same seed within each. CFG 4 vs 5 vs 6 (`p10-cfg4` job `6164ec19` prompt `8f8e9cb4`, `p10-cfg5` job `e23e54ad` prompt `cf1435b7`, `p10-cfg6` job `15e62093` prompt `6d4e5546`, all `AniFox-v2-Baseline_00026_`–`00028_.png`, 8.1–8.2 s): pose, cloth, hands, and face essentially unchanged, only the face angle drifts slightly. Steps 20 vs 28 (`p10-steps20` job `da711b46` prompt `16fe635e`, `p10-steps28` job `9cff976d` prompt `da3fb699`, `AniFox-v2-Baseline_00029_`–`00030_.png`, 10.2 s each): same pose, marginally cleaner shading at 28 for the same seconds here. Keep the lab defaults: CFG 5, 20 steps. Do not re-sweep per pose without a failure to explain.

Next lever: T12 words-only crawl on new adults (ambition list plus more Pokemon adults).

P11 held 8/8 across all four presets: `p11-raiden-crawl` (WAI, job `59d30c3a`, prompt `26a37a33`, `WAI-Illustration_00055_.png`, 40.4 s), `p11-yelan-crawl` (CSTati, job `ed934d82`, prompt `e28156ca`, `CSTati-v3-Baseline_00029_.png`, 32.4 s), `p11-evelyn-crawl` (YumeFlux, job `b8794fde`, prompt `0361a830`, `YumeFlux-ILv1-Baseline_00027_.png`, 32.3 s), `p11-jade-crawl` (AniFox, job `5d7df879`, prompt `fc670afe`, `AniFox-v2-Baseline_00032_.png`, 30.3 s), `p11-lusamine-crawl` (WAI, job `c3d4677c`, prompt `022d7ca5`, `WAI-Illustration_00056_.png`, 32.3 s), `p11-caitlin-crawl` (CSTati, job `a7c44f5f`, prompt `bcbdee94`, `CSTati-v3-Baseline_00030_.png`, 28.3 s), `p11-nessa-crawl` (YumeFlux, job `a63affee`, prompt `8c3a3b79`, `YumeFlux-ILv1-Baseline_00028_.png`, 34.4 s), `p11-sabrina-crawl` (AniFox, job `285eb14d`, prompt `7adc48d1`, `AniFox-v2-Baseline_00033_.png`, 28.3 s).

T12 garment rule: the crawl fully hikes loose dresses (Raiden's purple dress, Caitlin's white gown: rears bare) while bodysuits and fitted separates stay covered (Yelan, Nessa, Sabrina, Evelyn, Jade, Lusamine). Correction beside the p11 note: briefs and shorts do not stay covered — Power's briefs and Quanxi's shorts left the rear nearly bare (`p18-power-crawl`, YumeFlux, job `6496cd38`, prompt `99a9d02f`, `YumeFlux-ILv1-Baseline_00037_.png`, 22.2 s; `p18-quanxi-crawl`, AniFox, job `a312924c`, prompt `a016cac2`, `AniFox-v2-Baseline_00041_.png`, 24.3 s). Prompt a bodysuit or fitted separates when the rear must stay covered; prompt a loose dress, briefs, or shorts when the hike is the point.

Next lever: the remaining unrun adults (Himeno, Morgan, Nero, Jeanne, Caesar, Burnice, Carlotta, Bellona, Destina, Tenebria) spread across T7/T8/T12.

P12 held 10/10: `p12-himeno-crawl` (WAI, job `696a8855`, prompt `8ab991f4`, `WAI-Illustration_00057_.png`), `p12-morgan-bentover` (CSTati, job `e0523564`, prompt `2c1ddc0f`, `CSTati-v3-Baseline_00031_.png`, hair drifted dark blue to pale), `p12-nero-squat` (YumeFlux, job `e875b8fe`, prompt `591e1ca0`, `YumeFlux-ILv1-Baseline_00029_.png`), `p12-jeanne-crawl` (AniFox, job `5a6ee378`, prompt `5e75b28f`, `AniFox-v2-Baseline_00034_.png`, partial dress hike), `p12-caesar-squat` (WAI, job `277f968e`, prompt `f279a954`, `WAI-Illustration_00058_.png`, fake choker letters), `p12-burnice-bentover` (CSTati, job `da022cd3`, prompt `48f19bd9`, `CSTati-v3-Baseline_00032_.png`), `p12-carlotta-crawl` (YumeFlux, job `ef743679`, prompt `d20163b9`, `YumeFlux-ILv1-Baseline_00030_.png`), `p12-bellona-squat` (AniFox, job `7a433ef0`, prompt `b973d8f2`, `AniFox-v2-Baseline_00035_.png`), `p12-destina-bentover` (WAI, job `fc0a3abf`, prompt `9c64a61d`, `WAI-Illustration_00059_.png`), `p12-tenebria-crawl` (CSTati, job `695653e7`, prompt `b387a6c9`, `CSTati-v3-Baseline_00033_.png`). The ambition list is fully covered: every name has a T7, T8, or T12 cell.

Next lever: Asuna (owner-confirmed acceptable, never ran the new stacks) plus the last Pokemon adults, then one optional many-minute Krea crawl to test word-portability off the Illustrious family.

P13 held 6/6: `p13-asuna-squat` (WAI, job `898b0c9a`, prompt `97464380`, `WAI-Illustration_00060_.png`, 26.3 s), `p13-asuna-bentover` (CSTati, job `ae24b137`, prompt `2055439f`, `CSTati-v3-Baseline_00034_.png`, 30.2 s, extreme foreshortening), `p13-sonia-crawl` (YumeFlux, job `d0a5140d`, prompt `5b8b5f67`, `YumeFlux-ILv1-Baseline_00031_.png`, 30.4 s, partial jacket hike), `p13-olivia-bentover` (AniFox, job `9a2e37f0`, prompt `666e87ea`, `AniFox-v2-Baseline_00036_.png`, 24.2 s), `p13-erika-squat` (WAI, job `34c8a909`, prompt `3003ed3f`, `WAI-Illustration_00061_.png`, 24.3 s), `p13-acheron-crawl` (CSTati, job `ef7916cc`, prompt `07f1c68f`, `CSTati-v3-Baseline_00035_.png`, 24.2 s).

Krea is out for sexual cells: neither T2I preset binds a negative, so the required `child, loli, shota` negative cannot be attached. No many-minute job ran.

Next lever: `bedroom eyes` at the same seed on three held squats, and the measured seiza stack (`sitting, seiza, from behind, looking back, tongue out, ass focus, dynamic angle, foreshortening, blush, sweat`) transferred to three new adults.

## T13 — bedroom eyes on a held squat

Use when a held T7 still needs heavier eyes. Add `bedroom eyes` after `blush` at the same seed. No negative change. Pose, hands, and cloth stay put.

Held: `p14-kafka-eyes` (WAI, job `5ea8871d`, prompt `21c0802c`, `WAI-Illustration_00062_.png`, 24.3 s), `p14-yor-eyes` (CSTati, job `74ff4a95`, prompt `76309b98`, `CSTati-v3-Baseline_00036_.png`, 24.3 s), `p14-elesa-eyes` (YumeFlux, job `32d3e18e`, prompt `8e8239b6`, `YumeFlux-ILv1-Baseline_00032_.png`, 24.3 s). All three show heavy-lidded, half-closed eyes against their same-seed held cells.

Breaks it: nothing yet. Bent-over profiles are presumably as weak a test as they were for mouths (T9); not measured, not claimed.

P19 extended the tag to crawl faces at the same seed: `p19-sabrina-eyes` (AniFox, job `2ac8477b`, prompt `19f89b23`, `AniFox-v2-Baseline_00042_.png`, 24.2 s, clear), `p19-sonia-eyes` (YumeFlux, job `dbd8fc4f`, prompt `5c7fd851`, `YumeFlux-ILv1-Baseline_00039_.png`, 24.3 s), `p19-acheron-eyes` (CSTati, job `2e0769a4`, prompt `2a397a8f`, `CSTati-v3-Baseline_00047_.png`, 24.4 s). The tag fires on front-facing crawl faces as strongly as on squats.

P19 also confirmed the T6+T12 combo: the full sheer head on a held crawl at the same seed keeps the pose and fires by the usual cloth rule — light cloth transparent (`p19-raiden-sheer`, WAI, job `92a91197`, prompt `7e255e8f`, `WAI-Illustration_00071_.png`, 24.4 s; `p19-nessa-sheer`, YumeFlux, job `8fc6bf44`, prompt `6d323a9f`, `YumeFlux-ILv1-Baseline_00038_.png`, 24.3 s), dark cloth glossy (`p19-yelan-sheer`, CSTati, job `cf914d14`, prompt `5fc6db18`, `CSTati-v3-Baseline_00046_.png`, 24.2 s).

P17 extended the tag to portraits at the same seed: `p17-kafka-p-eyes` (CSTati, job `afd8d510`, prompt `adc7763f`, `CSTati-v3-Baseline_00042_.png`, 14.4 s, clear), `p17-yelan-p-eyes` (YumeFlux, job `e07896f0`, prompt `1d7c654f`, `YumeFlux-ILv1-Baseline_00035_.png`, 24.2 s, mild), `p17-acheron-p-eyes` (CSTati, job `016892a8`, prompt `5e59ebd3`, `CSTati-v3-Baseline_00043_.png`, 24.2 s, clear). The tag fires on portraits, milder than on squats.

Next lever: the seated-rear stack transfer, the last untransferred page pose.

## T14 — seiza rear (measured M3, transferred p14)

Use when the pose should be kneeling upright, seen from behind, face looking back with the tongue out.

Positive head: `seethroughILL, see through clothes, wet clothes` at the front. Slot 2 `see_through_clothes.safetensors` at 1 beside `nsfw_girls` at 0.7. Illustrious presets only.

Positive tail: `sitting, seiza, from behind, looking back, tongue out, ass focus, dynamic angle, foreshortening, blush, sweat` plus one place and one light.

Negative add: `logo, letters` on top of the usual quality and `child, loli, shota` line. No `hands, fingers` ban: the hands tuck out of frame on their own.

Held M3: `p-shalltear-seiza` (YumeFlux, job `37b8802b`, prompt `cd9877cc`, `YumeFlux-ILv1-Baseline_00012_.png`), `p-wiz-seiza` (AniFox, job `3cc76303`, prompt `c0652ad3`, `AniFox-v2-Baseline_00009_.png`, 26.5 s). Held p14: `p14-morgan-seiza` (WAI, job `c015140a`, prompt `11a6ea89`, `WAI-Illustration_00063_.png`, 26.2 s), `p14-acheron-seiza` (CSTati, job `71a16b63`, prompt `c3575442`, `CSTati-v3-Baseline_00037_.png`, 24.3 s), `p14-caitlin-seiza` (AniFox, job `70cb67ac`, prompt `fca92451`, `AniFox-v2-Baseline_00037_.png`, 24.3 s). Feet stay visible and normal in all three transfers.

Breaks it: nothing yet. Five characters hold it across all four presets.

Next lever: the seated-rear stack transfer, the last untransferred page pose.

## T15 — seated rear (measured M4, transferred p15)

Use when the pose should be sitting on a chair or bench, seen from behind in a close crop, hips as the subject. The hands never appear: facing away with the arms forward puts them out of frame on its own.

Positive head: `seethroughILL, see through clothes, wet clothes` at the front. Slot 2 `see_through_clothes.safetensors` at 1 beside `nsfw_girls` at 0.7. Illustrious presets only.

Positive tail: `sitting, facing away from viewer, ass focus, close up, blush` plus one place and one light. No seat noun needed; the model finds a chair, bench, or floor.

Negative add: `logo, letters` on top of the usual quality and `child, loli, shota` line. No `hands, fingers` ban.

Held M4 (prompts recovered from receipts): Zhu Yuan (AniFox, job `0744d4f9`, prompt `1982818d`, `AniFox-v2-Baseline_00012_.png`, 24.3 s), Artoria (YumeFlux, job `59b54e2c`, prompt `5001966a`, `YumeFlux-ILv1-Baseline_00016_.png`, 30.2 s). Held p15: `p15-sae-seated` (WAI, job `7882b378`, prompt `dbc1ce00`, `WAI-Illustration_00064_.png`, 22.3 s, suit pants translucent), `p15-takemi-seated` (CSTati, job `f0b2c466`, prompt `56c39363`, `CSTati-v3-Baseline_00038_.png`, 24.3 s), `p15-nessa-seated` (YumeFlux, job `c85354bf`, prompt `ef5ea718`, `YumeFlux-ILv1-Baseline_00033_.png`, 24.2 s), `p15-acheron-seated` (AniFox, job `7c488846`, prompt `b180e024`, `AniFox-v2-Baseline_00038_.png`, 24.3 s), `p15-morgan-seated` (WAI, job `26d4f02e`, prompt `ab8fcd1a`, `WAI-Illustration_00065_.png`, 22.4 s), `p15-caitlin-seated` (CSTati, job `5475f4e2`, prompt `17c0d483`, `CSTati-v3-Baseline_00039_.png`, 22.3 s).

Breaks it: nothing yet. Eight characters hold it across all four presets. Note against T10: `close up` holds its framing with sitting, but lost to `squatting, spread legs` — the pose tags decide, not the camera tag.

Next lever: the M3 portrait stack (Black Swan's sheer panel) transferred to new adults.

## T16 — portrait with sheer panel (measured M3, transferred p16)

Use when the face is the subject and the body below the chest only needs a sheer or glossy panel. The hands never appear: upper-body framing crops them out.

Positive head: `seethroughILL, see through clothes, wet clothes` at the front. Slot 2 `see_through_clothes.safetensors` at 1 beside `nsfw_girls` at 0.7. Illustrious presets only.

Positive tail: `upper body, portrait, looking at viewer, smile` plus one place and one light.

Negative add: `logo, letters` on top of the usual quality and `child, loli, shota` line.

Held M3 (prompt recovered from receipt): Black Swan (WAI, job `89658af5`, prompt `6ad6f1ef`, `WAI-Illustration_00044_.png`, 38.5 s). Held p16: `p16-2b-portrait` (WAI, job `cdf072c6`, prompt `567aef34`, `WAI-Illustration_00066_.png`, 26.3 s), `p16-kafka-portrait` (CSTati, job `af845d9a`, prompt `667713d1`, `CSTati-v3-Baseline_00040_.png`, 26.4 s, shirt strongly translucent), `p16-yelan-portrait` (YumeFlux, job `8af1e664`, prompt `8e5e64ac`, `YumeFlux-ILv1-Baseline_00034_.png`, 26.3 s), `p16-nero-portrait` (AniFox, job `0e76aa27`, prompt `f9dd9e37`, `AniFox-v2-Baseline_00039_.png`, 26.4 s, wet-look chest), `p16-jessie-portrait` (WAI, job `28add1d6`, prompt `5bb5cb29`, `WAI-Illustration_00067_.png`, 24.3 s), `p16-acheron-portrait` (CSTati, job `80a130e0`, prompt `23db61eb`, `CSTati-v3-Baseline_00041_.png`, 24.3 s).

Breaks it: nothing yet. Seven characters hold it across all four presets.

P17 held 6/6: eyes on portraits (`p17-kafka-p-eyes`, `p17-yelan-p-eyes`, `p17-acheron-p-eyes`, same seeds, tag fired on all three) and the portrait on the last unrun adults (`p17-power-portrait` WAI job `da6475dc` prompt `ce608591` `WAI-Illustration_00068_.png`; `p17-quanxi-portrait` AniFox job `a8f70b2f` prompt `3f39d9a8` `AniFox-v2-Baseline_00040_.png`; `p17-cynthia-portrait` YumeFlux job `530b243a` prompt `06311d75` `YumeFlux-ILv1-Baseline_00036_.png`).

P18 held 6/6, giving the portrait-only adults body stacks: `p18-2b-squat` (WAI, job `4c0dccb6`, prompt `6e56e5f3`, `WAI-Illustration_00069_.png`, 24.3 s), `p18-2b-bentover` (CSTati, job `6e1869cb`, prompt `0bb193aa`, `CSTati-v3-Baseline_00044_.png`, 24.6 s, pod garnish from the prompt tag), `p18-cynthia-squat` (WAI, job `efb11cba`, prompt `fa29e225`, `WAI-Illustration_00070_.png`, 24.2 s), `p18-cynthia-bentover` (CSTati, job `cb7936c9`, prompt `361e8f45`, `CSTati-v3-Baseline_00045_.png`, 24.3 s, grey skirt became grey pants). Garnish note: a `pod` tag on 2B renders Pod 042 hovering behind her without disturbing the pose.

Next lever (p20, queued): `bedroom eyes` on three held bent-overs at the same seed (measuring the weak-profile claim), and the camera layer on the crawl — `cowboy shot`, `close-up`, and `from below`, one tag each on a held crawl at the same seed.

## M2 measured

All nine jobs completed. About 26–38 seconds each. No spill line was required to finish the queue.

| Cell | What the stack did |
| --- | --- |
| m2-albedo-heat | T1 did not open the white dress. Wings covered the hips. Hands stayed out. Lantern light and a little blush held. A full skirt plus wings blocks the leak. |
| m2-shalltear-heat | T1 held on Anima. Skirt open, arms behind the back, no hands, red light, sweat, blush. |
| m2-jane-heat | Hands came back as fists. The cropped jacket never became an open skirt. Purple light held. The jacket invented letters. T1 is a dress stack. |
| m2-blackswan-heat | Skirt opened. Arms crossed in front instead of behind. No shush. Violet light and sweat held. |
| m2-priscilla-front | Chest of the dress opened. Both hands went to the throne arms, not the thighs. Sweat and blush held. |
| m2-zhuyuan-front | Shirt opened, pants stayed on. One hand on the wall, one at the side. Thigh palms failed. |
| m2-yinlin-heat | T1 opened the gown on JANIMA. One hand returned to the hip. Lamp light and sweat held. |
| m2-artoria-heat | T1 opened the blue dress. One hand is barely in frame. Sweat held. |
| m2-makima-thighs | Shirt stayed partly open. Both hands stayed on the desk. `not on the desk` lost to `sitting on a desk`. |

Next hand test drops the desk from the sentence. Next costume test on a dress that stayed closed is T6, not another hike.

## Queue rule

A job with a prompt id and no file is not posted again. A job that fails before any prompt id may be posted as a new id. The M2 queue below was posted as a batch so the cells share one plan instead of waiting on each inspection. Each row still names the one stack it is testing.

| Cell | Character | Preset | Stack | Question |
| --- | --- | --- | --- | --- |
| m2-albedo-heat | Albedo | wai | T1+T2, tavern lamp | Does T1 open a white dress in a tavern, where the front sit stayed closed? |
| m2-shalltear-heat | Shalltear | anima | T1+T2, red bedroom | Does T1 replace the lifting hand from the earlier bedroom cell? |
| m2-jane-heat | Jane | yumeflux | T1+T2, purple alley | Does a purple practical light carry T2 the way red and lamp light did? |
| m2-blackswan-heat | Black Swan | wai | T1+T2, violet ballroom | Does T1 beat the shush that the lap-hands pose produced? |
| m2-priscilla-front | Priscilla | cstati | T4, throne | Does "palms on her own thighs, not on the throne" beat the raised fan? |
| m2-zhuyuan-front | Zhu Yuan | yumeflux | T4, night street | Does the open-shirt front stack read on a standing officer? |
| m2-yinlin-heat | Yinlin | janima | T1+T2, teahouse | Does T1 open the gown that stayed closed in the seated cell? |
| m2-artoria-heat | Artoria | anifox | T1+T2, castle | Does T1 replace the lifting hand from the earlier castle cell? |
| m2-makima-thighs | Makima | cstati | T4 hand phrase | Same recipe as the pre-submission failure. New job. |

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

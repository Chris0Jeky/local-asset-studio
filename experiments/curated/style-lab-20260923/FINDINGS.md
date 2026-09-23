# Regular style lab — 23 September 2026

Not the NSFW lab. No ecchi prompts, no hentai prompts, no aged-up prompts, no NSFW adapters.
Every cell is a clothed illustration. LoRA strengths were 0. Shared negative:
`nude, nsfw, explicit, sexual, erotic, underwear, lingerie, cleavage, skirt lift, suggestive, porn`.

Generated is not accepted art and not licence clearance. Pictures stay under
`C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\`.

| Cell | Preset | Seconds | Job | Prompt | File | What it showed |
| --- | --- | ---: | --- | --- | --- | --- |
| s-megumin-canon | wai | 24.4 | `e5fd4cca-dc5a-4e3e-91fc-160dc5436b4c` | `0aa9469a-0f67-428a-8896-5425d8f6d245` | `Studio/WAI-Illustration_00024_.png` | Red dress, witch hat, staff, explosion behind her. Clothed full-body stand. |
| s-megumin-winter | anima-v1-baseline | 22.3 | `d9eaf76a-e429-4876-966a-1c331743636c` | `2535df06-4108-4888-a98e-f2bcebd54db3` | `Studio/Anima-v1-Baseline_00039_.png` | Same hair and eyes in a winter coat, scarf, and boots, walking a snowy street with a satchel. The witch hat did not carry over. Clothed. |
| s-alya-classroom | wai | 16.1 | `1c2aa298-d64d-4b9f-8df9-1c35eecc5401` | `66d90323-b468-46ba-9c05-8c9a22d39a2c` | `Studio/WAI-Illustration_00025_.png` | School uniform, book, classroom. Clothed stand. |
| s-zerotwo-stand | anifox-v2-baseline | 22.2 | `c4d67be4-0b6e-4d5e-a5a2-0498bbeca8ab` | `81b56903-e89d-4df1-b536-d87d991bf816` | `Studio/AniFox-v2-Baseline_00006_.png` | Pink hair, small horns, long white coat, boots. Neutral full-body stand on a plain background. Clothed. |
| s-momo-run | yumeflux-ilv1-baseline | 28.3 | `cdbef762-dd61-4c20-8c73-857a27efead4` | `e8ede2b4-a366-4158-9c7c-cf7d1c4f5289` | `Studio/YumeFlux-ILv1-Baseline_00005_.png` | Sailor uniform, running down a street. Clothed. The raised foot is missing its shoe. |
| s-beatrice-read | anima-v1-baseline | 28.2 | `f91605f2-563b-4336-8534-f32e3a5ccb44` | `18d25529-720f-42cc-829e-ffa37659fd53` | `Studio/Anima-v1-Baseline_00040_.png` | Drill curls, dress, library, open book. Clothed sit. One hand is poorly drawn. |
| s-ellen-cafe | cstati-v3-baseline | 28.2 | `10768b03-10dc-4f6a-95ee-1eca6975c664` | `26a58ea8-f3d2-4449-a71f-1eb98958dd97` | `Studio/CSTati-v3-Baseline_00006_.png` | Maid uniform, two trays, shark tail, cafe. Her regular costume. The menu board is fake letters. |
| s-hina-gate | wai | 22.2 | `c9d25444-f64e-46cc-848a-46c895b808fc` | `7e4f389f-5e8a-46a4-9ff4-037fab512012` | `Studio/WAI-Illustration_00026_.png` | Shirt, tie, skirt, school gate, halo and small wings. Clothed stand. |

Costume swap worked on Megumin (canon dress versus winter coat). Pose swap worked on Momo (run) versus the standing cells. Beatrice's sit-and-read is the third pose. No cell was prompted toward undress, and none of these eight frames is an ecchi composition.

Next clothed tries, if this lab continues: give Megumin's winter cell the hat explicitly in the foreground, put the shoe back on Momo's raised foot, and give Zero Two a simple background so the coat read is not floating on white.

## Wave S2 plan — 23 September continuation

Plans only. Not results until a still exists. No ecchi, no hentai, no nudity, no NSFW adapter (every LoRA strength 0). Same character tags that already drew these people. Fully clothed, modest outfit.

Shared negative: `nude, nsfw, explicit, sexual, erotic, underwear, lingerie, cleavage, skirt lift, suggestive, porn, worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, bad anatomy, bad hands, extra digits, missing fingers, text, watermark, logo, letters`.

| Cell | Series | Preset | Seed | Intended change |
| --- | --- | --- | --- | --- |
| s2-megumin-hat | Konosuba, clothed | wai | 2026092361 | Winter coat plus the witch hat on her head, brim in frame. Adapter moves from Anima, which dropped the hat. |
| s2-momo-shoe | Dan Da Dan, clothed | yumeflux-ilv1-baseline | 2026092362 | Same run, both shoes on, the raised foot's shoe named. |
| s2-zerotwo-bg | Darling in the Franxx, clothed | anifox-v2-baseline | 2026092363 | Same coat and horns, simple solid grey background. |
| s2-alya-coat | Alya, clothed | wai | 2026092364 | Further cell. Winter coat and scarf over the uniform, outdoors, book in one arm. |
| s2-hina-walk | Blue Archive, clothed | cstati-v3-baseline | 2026092365 | Further cell. Walking with a school bag and a long coat, gate behind her. |
| s2-frieren-field | Frieren, clothed | wai | 2026092366 | Clothed meadow already run. A youthful face does not keep her in this lab. |

## Wave S2 results

LoRA strengths are 0. Generated is not accepted and not licensed.

### s2-megumin-hat — completed, counted

The winter Anima cell dropped the hat. This one names the hat on the head and uses WAI.

- Preset `wai`, seed `2026092361`, steps 20, CFG 5, euler ancestral / normal, both LoRA strengths 0.
- Studio job `b333516d-97c2-4de8-8cf9-e1d67b42b500`. ComfyUI prompt `9ca15bc7-ad01-4331-9861-72f733bcd388`. 28.3 s. Spill 3.5 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00030_.png`.
- Positive: megumin, witch hat on her head, large red hat brim in frame, winter coat, scarf, boots, snowy street, fully clothed.
- Inspection: clothed full-body stand. Brown hair, red eyes, oversized brown witch hat with a red brim, red toggle coat, cream scarf, dark trousers, orange boots, satchel, snowy street. The hat is in frame. Hands are in the coat pockets. No undress. The youthful design is the regular character, which is what this lab is for.
- Keep: WAI when the hat has to survive a costume swap. Anima lost it.

### s2-momo-shoe — completed, counted

The earlier run left the raised foot bare. This one names a shoe on that foot.

- Preset `yumeflux-ilv1-baseline`, seed `2026092362`, steps 20, CFG 5, euler ancestral / karras, both LoRA strengths 0.
- Studio job `3152f80e-6b79-42e1-a9ce-6fdb70698855`. ComfyUI prompt `52c59ee8-e40f-409a-9151-d317346038c1`. 30.2 s. Spill 0.6 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\YumeFlux-ILv1-Baseline_00007_.png`.
- Positive: ayase momo, school uniform, both shoes on, shoe visible on the raised foot, running, fully clothed.
- Inspection: clothed run on a city street. Sailor-style uniform, white socks, brown loafers. The raised foot wears a loafer, and the landing foot does too. That is the change that was asked for. Hair came out purple rather than the usual brown. The still stays. No undress.

### s2-zerotwo-bg — completed, counted

The earlier coat was floating on white. This one asks for a solid grey background.

- Preset `anifox-v2-baseline`, seed `2026092363`, steps 20, CFG 5, euler ancestral / karras, both LoRA strengths 0.
- Studio job `92831cc0-a54a-467d-a6cf-c37622c9160d`. ComfyUI prompt `1eb2789d-72a0-43da-a8c3-c2ce753ee506`. 28.2 s. Spill 4.4 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\AniFox-v2-Baseline_00009_.png`.
- Positive: zero two (darling in the franxx), red horns, long white coat, black boots, simple solid grey background, fully clothed.
- Inspection: clothed full-body stand. Pink hair, two red horns, teal eyes, long white coat, black belt, black boots, flat grey background with a ground shadow. The coat is no longer floating on white. Hands hang at the sides and look simple. No undress.
- Keep: a plain background when the question is the coat.

### s2-alya-coat — completed, counted

Further clothed cell. Winter coat over the uniform.

- Preset `wai`, seed `2026092364`, steps 20, CFG 5, euler ancestral / normal, both LoRA strengths 0.
- Studio job `d0ab2ae1-c6f9-422e-b989-ece35b48b44f`. ComfyUI prompt `db711304-64ca-4f33-bb93-903623265d49`. 28.2 s. Spill 2.8 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00031_.png`.
- Positive: alisa mikhailovna kujou, school uniform under a long winter coat, scarf, book, snow, fully clothed.
- Inspection: clothed stand in snow. Silver hair, blue eyes, white duffle coat, red scarf, dark uniform and tights, brown boots, a book in one hand. The other hand is in the coat pocket. The coat changes the silhouette from the classroom stand. No undress.

### s2-hina-walk — completed, counted

Further clothed cell. Walking, coat, school bag.

- Preset `cstati-v3-baseline`, seed `2026092365`, steps 20, CFG 5, euler ancestral / karras, both LoRA strengths 0.
- Studio job `061a5427-a55f-43d3-8bcc-ab204956c4e5`. ComfyUI prompt `ad8424de-212f-4c0e-ae86-d12ac004468c`. 28.3 s. Spill 1.3 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\CSTati-v3-Baseline_00009_.png`.
- Positive: hina (blue archive), halo, school shirt, necktie, skirt, long coat, school bag, walking, school gate, fully clothed.
- Inspection: clothed walk beside a fence. Long white hair, pink eyes, geometric halo, dark horns and small wings, shirt, blue tie, dark skirt, beige coat, loafers, bag in one hand. The walk is a different pose from the earlier gate stand. No undress.

### s2-frieren-field — completed, counted

Clothed meadow that already ran. It is not a rule that Frieren belongs here.

- Preset `wai`, seed `2026092366`, steps 20, CFG 5, euler ancestral / normal, both LoRA strengths 0.
- Studio job `8e38a9e7-e705-412a-b369-0e3afa5a84ca`. ComfyUI prompt `ddf512fc-2ce9-4d64-8ffa-922adc842b77`. 28.2 s. Spill 4.6 GB.
- File: `C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\WAI-Illustration_00032_.png`.
- Positive: frieren, long white hair, green eyes, pointy ears, white robe with black trim, staff, flower meadow, boots, fully clothed.
- Inspection: clothed stand in a flower field. White hair in twintails, green eyes, pointed ears, white robe with gold trim over a striped shirt, brown boots, both hands on a staff. The face is the usual youthful Frieren design. The still stays as a clothed costume experiment.
- Owner correction, 23 September 2026, 20:42 local: that face is not a reason to keep Frieren, or any adult-in-canon character with a youthful design, out of the NSFW lab, and it is not a reason to change the next prompt. Further Frieren cells go in the NSFW notes.

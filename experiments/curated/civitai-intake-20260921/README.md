# civitai.red intake showcase — 21 September 2026

Ten Studio jobs, one seed each, queued at 01:37 and finished by 02:08 local time. Primary backend. PNGs live under the configured `experiments_root` job folders; small JPEGs for Creative Bundles are `examples/civitai-intake/<recipe-id>.jpg`. Generated, not inspected as finished art, not licensed.

| Recipe | Job | Prompt ID | Seconds | Inspection |
| --- | --- | --- | ---: | --- |
| anifox-v2-showcase | 43561247-70a8-4342-a768-81f5601a7fab | cadc8403-bb7c-4ec5-bbbc-852ba0b230f1 | 36.4 | Fox girl, inverted pose, extra tail mass, extra fingers; carnival became forest night. |
| anifox-ringeko | 059aa6f5-9b97-4e5b-9a4b-10071dfcee77 | 18d93d69-ccaf-4715-8966-243091f27142 | 22.2 | White hime, red eyes, black cat. Extra fingers on the cat-holding hands. |
| anifox-fluorite | 38ff6668-3b53-4036-b4f9-a5d0e393891e | 607b66d6-90b4-4762-98d7-f686303a3a5d | 16.2 | Green hair, snake tail, hooded jacket, black bodysuit. Character LoRA fired; likeness not cleared. |
| oneobsession-anima-v20-showcase | 2079b0b2-44a1-44db-9b9b-57b0693982fe | a5bbe7d9-91ef-4edd-975c-3a82ede5675b | 40.4 | Hanfu, lanterns, plum branch. |
| pearly-anima-mix-v10-showcase | 0c0108fb-d82c-4550-9460-1502ae1d7fb7 | a201fd59-b3cc-4101-9e61-6827cc78b8c3 | 26.2 | Pink fluorescent magical girl, dynamic pose. |
| anima-pearly-esearu | 0f66b253-b98a-44bd-a1dd-fac204654b22 | 1ca26902-008e-4e14-b86e-4ba6d606c65b | 30.4 | Halo, blonde, soft colours. Extreme body proportions. |
| anima-pearly-petiflow | 3e8b0e5e-28c9-4df8-b800-d89c3a44b474 | 4ba586c7-679c-4846-b249-4b6fae1329a3 | 18.2 | Flat pastel close-up, mint hair. Strong style match. |
| krea-realism-engine | d8c94308-a9e2-4412-bf75-5ce95bc0e2b6 | aa1b34e0-aa56-49f1-81a3-8bc69dfed2a8 | 552.4 | Photoreal woman on a wet dusk station. Hands in pockets. |
| krea-realistic-snapshot | 4ec39381-15bb-421a-886b-380160320f9a | 23e6bcc3-14e5-4ebb-ae31-bb87ae40b696 | 586.8 | Candid golden-hour street portrait. |
| krea-lenovo-ultrareal | e7378421-b1d4-4995-9411-76fa7cad5213 | 4a357043-2a09-4702-a884-b2513e603ce1 | 598.6 | Amateur bedroom selfie with phone in frame. |

Krea 2 Turbo 8-step jobs were ~9–10 minutes each after Anima/SDXL (~16–40 s). JPEG SHA-256 values are in `app/static/bundle-showcase.json`. Catalog `verified` flags on the new Anima/AniFox presets stay false: these are recipe examples, not baseline-control proofs.

## Wave 2 — fast families, NSFW adapters and combos

Twenty further Studio jobs, one seed each, queued after wave 1 and finished by 02:54 local time. Primary backend. Slow families (Qwen, FLUX.2 32B, H3, Wan, Hunyuan, Trellis, HiDream, Klein 9B, z-image, extra Krea) were skipped on purpose. PNGs live under the configured `experiments_root` job folders; small JPEGs are `examples/civitai-intake/<recipe-id>.jpg`. Generated, not inspected as finished art, not licensed.

| Recipe | Job | Prompt ID | Seconds | Inspection |
| --- | --- | --- | ---: | --- |
| anima-nsfw-girls | 5bb94ec4-bb02-4daf-8695-f6b02a89c4d6 | c69c3c68-7a53-4271-ac0c-a4c7c3cda5dd | 36.3 | Pink-lavender hair, amber eyes, sitting on a bed holding breasts. Extra fingers on both wrapping hands. |
| anima-nsfw-petiflow | 6596b294-8780-4204-81e1-38ad3bafab71 | 8ec07340-3c57-476d-acf7-2efdfd1f5ce8 | 20.1 | Face-focus pastel blonde, aqua eyes, shoulders only. Flat-color style beat the full-nude prompt. |
| anima-nsfw-esearu | edf39880-d168-4af5-af27-299f27f2078b | 54fe1497-bc68-4738-b8c4-18b6421af274 | 20.2 | Halo, blonde, white robe open. Extreme proportions. Extra fingers on both fists. |
| anima-bunnyslop-nsfw | 0b1fe46f-a7e1-401e-adcc-d77096bab005 | cdc1a9ce-7020-4267-a327-7cf2dd2100d9 | 22.2 | Dark hair, red eyes, bedroom selfie. Extra fingers on the camera-reaching arm. |
| anima-xilmo-style | 2ea4478b-5fdf-4e65-926f-161ee415ffe5 | 457631f8-ac16-4430-ac87-71119bc30c86 | 20.2 | Clothed painterly parka and scarf portrait. Style LoRA, not an NSFW adapter. |
| anima-nsfw-artist-combo | c52bedf7-96ad-425b-87e3-4959b256ef97 | 97c916d3-e3f1-4852-85c2-34bba9dc0029 | 22.1 | Short dark hair, gold eyes, bedroom. Extra fingers on both hanging hands. |
| anifox-nsfw-girls | 6a99bd9d-6567-45e5-bbd5-8f0c553b0b9b | e32514fd-c9fc-4ebc-9a6f-9d8b0a6f4383 | 32.5 | Black braid, red eyes, bedroom lean. Extra fingers on the near arm. |
| anifox-nsfw-ringeko | 4b71f375-95d1-4830-a7b7-dd28ce7e2eec | 1009c21b-08f0-4227-9010-1a429ffac6fa | 16.1 | White hime cut, red eyes, back view on a bed. Extra fingers on the left hand. |
| anifox-shiny-nai | 231eec0f-4949-4d5c-b86b-5c7d1bf89540 | b8f996bf-1442-4761-911f-ced0be69d1df | 14.1 | Blonde, blue eyes, high-gloss wet skin. Extra fingers on both hands. |
| wai-nsfw-girls | 9dc3204c-8d99-468d-9101-f4b0e737b171 | 701a3203-d718-4651-a595-dbaf71138268 | 44.3 | Black hair, red eyes, doorway. Extra fingers on the raised left hand. |
| wai-nsfw-glossy | 65b9abf2-bd4d-4926-92f6-e9c6c65b9658 | 56251405-3468-46ec-a70e-31531af24b49 | 20.1 | Silver hair, red eyes, arms up. Extra fingers on both raised hands. |
| wai-shiny-detail | 3ab4de6e-6949-4de0-8f83-bbe9e2475dc6 | cdbbfaa0-aa46-4c51-93d4-799816e56203 | 22.2 | Teal-black hair, high gloss. Extra fingers on both hands on the bed edge. |
| cstati-nsfw-girls | 29263089-c489-4148-8e42-adc5d4ca1786 | b0dce1f5-6272-4b11-9e7d-a12297dd86ba | 42.9 | Purple hair, red eyes, doorway. Extra fingers on the door-holding hand. |
| yumeflux-nsfw-girls | 003fabe5-13be-49de-acdc-999eb5f88cd5 | 3591a960-3263-4368-a11c-4d5b8702b0f0 | 46.6 | Black hair, red eyes, black X pasties. Extra fingers on both hands. |
| janima-nsfw-girls | c8ef7f25-145c-4b37-ba6e-19274fe2ebc3 | 84265e0b-704f-4e53-adb6-9b40275372fc | 40.3 | Brown hair, orange eyes, white shirt open. Extra fingers on both hands. |
| oneobsession-nsfw-petiflow | aca99b77-1083-4c1e-993e-5c5d29172bc7 | 36bfde78-c0ee-4106-8a4e-0a3df54b898d | 32.3 | Flat pastel blonde, swirl background. Extra fingers on both hands. |
| pearlymix-nsfw-esearu | 353fa62d-86ee-447b-b784-51b592813c29 | 97b8af94-c030-44c1-8fac-b86b5be653a6 | 28.2 | Halo, blonde, extreme proportions. Extra fingers on both hands. |
| animagine-nsfw-girls | 14146c99-e195-41a4-ae6f-ee7e8381593a | 8c38e031-fb32-413f-a5ac-e39ce6b2bb5c | 45.0 | Black lingerie bodysuit, not fully nude. Extra fingers on the cheek-side hand. |
| pony-nsfw-girls | 1669629b-4385-4094-bb91-6d64e159faa5 | a429bc16-90f9-4020-a9c4-3525bf490955 | 40.3 | Photoreal/3D look; Illustrious adapter is weak on Pony. Extra fingers on the crossed arm. |
| noob-nsfw-girls | 1b020ba1-aa12-40f4-8fc6-86ae5e3c07d4 | 014c1e77-901b-4e67-8b5d-b42f79b7e129 | 48.3 | Soft/blurry back view. Extra fingers on the hip-side hand. |

Job ids in `.runtime/wave2-jobs.json` (untracked). Catalog `verified` stays false. HUMAN_TODO q-29 was not ticked.

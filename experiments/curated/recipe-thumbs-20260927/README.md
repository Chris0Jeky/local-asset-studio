# Recipe thumbnails — 27 September 2026

One Studio job per recipe at the recipe's authored defaults (prompt, seed, steps, sampler, size and adapter strengths), submitted serially with `POST /api/jobs` on the primary backend between 03:58 and 04:55 local time. The Krea atelier and style-lab recipes ran on the GGUF twin `krea-anime-atelier-gguf` (identical bindings, Q5_K_M weights, text encoder on the CPU) because the fp8 presets take about ten minutes per picture here; the style-lab recipes got `lora4: 0` on that twin. Every PNG was opened and inspected by the agent. Generated and agent-inspected only: not a benchmark, not owner art acceptance and not licence clearance. Catalog `verified` flags were not changed.

Thumbnails are `examples/recipe-thumbs-20260927/<recipe-id>.jpg` (704 px long edge, under 142 KB). Each receipt in `receipts/` carries the Studio job and ComfyUI prompt IDs, wall time, host-commit readings, the full-size output path and SHA-256, the JPEG SHA-256 and the Studio `recipe.json`. PNGs stay under ComfyUI `output/Studio/`; Studio job folders are under the configured `experiments_root`.

| Recipe | Ran on | Job | Prompt ID | Seconds | Inspection |
| --- | --- | --- | --- | ---: | --- |
| anima-fantasy-portrait | anima-portrait | 77e737a8 | 886151c5-ff6c-4838-aeaf-a5fafa0145e4 | 39.8 | Teal-haired pilot in goggles and a flight suit, floating islands and waterfalls, an airship at top right; readable hand on the rail; the sleeve patch is invented insignia. |
| anima-reference-six-adapter-stack | anima-artist-stack | d9ec6ae9 | 46eb9605-01e9-4be3-b268-e7f5ce33d114 | 95.7 | Witch in a wide hat and dark cloak at dusk with sky lanterns; strong painterly purple finish; a faint stray signature scribble sits at the bottom right (crop 1100,1600-1328,1776). |
| anima-painterly-artist-tags | anima-artist-stack | f9a8b395 | b53109bc-5ac7-4640-b1d7-5d35a8c39dc7 | 40.5 | Traveller in a patched dress under a lone tree with birds overhead, low angle, loose painterly brushwork; the hat-holding hand is simplified. |
| anima-screenshot-stack | anima-artist-stack | f5f2a8dc | ae5d97ff-be25-4e3d-9656-65bd7ff34535 | 31.5 | Adult cartographer in a navy double-breasted coat and teal scarf, map case on her back, domed observatory behind; the compass became a second lantern plus a disc on the coat. Fully clothed. |
| anima-v1-base | anima-v1-baseline | 2c65c932 | 31c62d21-fc9e-460c-973c-255d9f92401e | 21.6 | Beige trench coat, turtleneck, trousers and lace-up boots on a wet platform at dusk, hands in pockets; clean, even rendering. |
| anima-v1-first-adapter-comparison | anima-v1-baseline | bd241f3c | efba2f5c-7b25-478d-a57f-4383b37f0dc1 | 26.7 | Brighter backlit platform with glow, ribbed sweater, brown boots, longer legs; still fully clothed. |
| anima-v1-screenshot-sampling-comparison | anima-v1-baseline | 4fc7884d | 76fdd8fe-1d58-4ded-8b02-c99aef9ff772 | 22.1 | Pale pink backlight, cream sweater, fitted trousers, glossy wet platform; the figure is narrower and more stylised than the baseline. |
| janima-v1-base | janima-v1-baseline | 13db9fe9 | 52056495-f256-4a79-96f3-e56f1a3a0e47 | 44.1 | Navy turtleneck, beige coat and trousers under a blue-grey canopy with a yellow tactile strip. |
| janima-v1-authored-five-adapter-stack | janima-v1-baseline | c546e848 | 1673247b-f801-44de-bfdd-439cf0601e76 | 34.9 | Blunt fringe, cream turtleneck, warm backlit dusk and a softer painterly finish; still fully clothed. |
| oneobsession-anima-v20-base | oneobsession-anima-v20-baseline | 34df9931 | 933db201-93d4-4b7c-9340-21abd988c218 | 35.1 | Warm dusk backlight under a station canopy, rain streaks and a reflective platform; dark sweater and beige coat. |
| oneobsession-anima-v20-portrait | oneobsession-anima-v20-baseline | 9459228a | d0121b72-473c-4a85-8c5a-4016955643c8 | 26.7 | Face from slightly above, dark hair across the face, blue night fog and strong chiaroscuro; moody close-up. |
| pearly-anima-mix-v10-base | pearly-anima-mix-v10-baseline | e42bee3b | 8045f283-fe2f-493c-9d0e-a436038a706d | 37.0 | Teal sweater, beige coat and trousers framed by a symmetrical canopy; soft glossy finish. |
| wai-fantasy-portrait | wai | 72ab3a2f | aa433fd7-edfd-4545-a29d-ac0806c1fe6a | 36.2 | Braided crown, dark hooded cloak, leather bracers and a lit lantern among forest light rays; a glossy black dress with a thigh slit under the cloak. |
| wai-noirpopwave-screenshot-baseline | wai | eaf24185 | fe3e83b8-0563-47cf-86f6-f09ae907cf95 | 17.9 | Teal coat and scarf, lantern and satchel before an ornamental compass wheel and star; bold flat shapes and a limited palette. The map case became a shoulder satchel. |
| noob-fantasy-scene | noob | 77135653 | 2fa1ee7e-1e08-453b-b43e-6b53fd709c9a | 44.6 | A small reading figure on a lit ledge among glowing mushrooms over dark water under stars; too small to check the glasses or hands. |
| animagine-fantasy-portrait | anime | 381cb3ff | 17c317ec-6ce3-4286-aceb-0b5d94803aa9 | 39.1 | Dark embroidered haori, dutch angle, paper lanterns overhead; the fox mask is missing and she holds a sheet of paper instead of a paper lantern. |
| pony-fantasy-portrait | pony | 6d43fb03 | 3063c283-35b2-4ba5-bac5-0e3804379648 | 36.0 | Curly-haired smith in a teal apron and leather gloves holding tongs, soft warm painterly haze; the forge itself is not visible, only embers. |
| cstati-v3-base | cstati-v3-baseline | 65a9efbc | 974683b6-c5b7-456e-96e9-af982dc4fd77 | 41.1 | Beige coat, cream top, dark trousers and knee boots under teal arches; cool palette. |
| cstati-v3-adapter-audition | cstati-v3-baseline | 3558d60d | 6a162dfd-352e-42c3-b7ca-c778707defa1 | 22.5 | Still fully clothed, with fuller proportions and a warmer brick platform and garden; the adapter changed body shape and scene more than style. |
| yumeflux-ilv1-base | yumeflux-ilv1-baseline | b3093cd6 | 12df9f6f-b07d-436a-a8e7-bb816d765e9f | 37.0 | Black long coat, white top, dark trousers and boots; muted and soft. |
| yumeflux-ilv1-adapter-audition | yumeflux-ilv1-baseline | 215e55e6 | fc6c1acf-afe9-4d59-8ab5-9c6cdc42e5a9 | 18.4 | Still fully clothed, with fuller proportions and high-waisted buttoned trousers; a distant figure and a train were added. |
| anifox-v2-base | anifox-v2-baseline | 8b274fe1 | ef958560-640f-42f3-87bb-c28fff2d0674 | 50.8 | Black coat, white top and knee boots on a rainy blue platform with a green signal lamp. |
| anifox-v2-adapter-audition | anifox-v2-baseline | 78c48c01 | bf463d95-313e-4ed8-a3f6-a15ccf8f1827 | 28.2 | Still fully clothed, with shorter hair, fuller proportions and a brighter cloudy sky; framing unchanged. |
| krea-oil-fantasy | krea-anime-atelier-gguf | 819da04c | 1f7d1dbc-ec2c-4c4f-9b1e-eca8df964eba | 279.6 | A small cloaked figure with a lantern on a mossy arched bridge over fog under a crimson sky; dark oil finish carries the picture. |
| krea-watercolor-anime | krea-anime-atelier-gguf | fe359a6b | e8e2aa02-d3b6-4c5e-bf30-005d940e2d63 | 252.3 | Straw hat and green apron, a potted seedling in both hands, bright white greenhouse; loose watercolour washes. |
| krea-4step-audition | krea-anime-atelier-gguf | 6f52b4f7 | a3238714-bb0e-4783-addf-4dcf2ad62f7d | 255.9 | Dark-haired figure reading a map in spray at blue hour; the map lines are illegible scribbles, not text; small audition size. |
| krea-atelier-wildcard-study | krea-anime-atelier-gguf | 7480ce57 | 6e02183b-a3a1-4617-a12d-7f8310aff963 | 280.2 | The wildcards expanded to an apothecary crowded with jars at night, volumetric light, a tabby dozing on a book, sepia; jar labels are blank marks. |
| krea-lenovo-night-street | krea-anime-atelier-gguf | 127b97ba | c8889748-14f5-40e6-9a1a-34b1be5856c1 | 218.2 | Photoreal amateur night shot: an adult woman in a duffle coat beside a parked car on a hillside street, city lights below, strong street-lamp flare and phone noise; the face is soft and blurred. |
| krea-style-airy-softwatercolor | krea-anime-atelier-gguf | 311af910 | 8b78c779-0bf5-47b5-9e3a-363b9eb1134c | 245.1 | Shelves of stoppered jars and an arched window in soft rose, cream and mint washes; the jar labels are pseudo-script marks, not readable text. |
| krea-style-inkwork-darkbrush | krea-anime-atelier-gguf | 3f50f74f | 21ab8b19-00cb-4030-acce-164a59c758a8 | 377.5 | Gothic arch and broken roof with light rays, ivy in heavy dry-brush ink, clean monochrome; no figures. |
| krea-style-emerald-tarot | krea-anime-atelier-gguf | 4cc58496 | c362d8e5-202d-4507-b664-9d6bee781b57 | 240.9 | Engraved paperback look with root archways, an armoured knight with a spear and a white fox; the fox shows one bushy tail, not two; a stray monogram-like mark sits at the bottom right (crop 880,880-1024,1024). |

## Rendered but not published

| Recipe | Job | Prompt ID | Seconds | Reason |
| --- | --- | --- | --- | --- |
| pearly-anima-mix-v10-portrait | bfde3b32 | 78378bb0-22df-4c05-bda8-1ab65f38b194 | 18.0 | The render read as youthful with body emphasis; kept local under the lab rule for a public repository. |
| krea-dark-scifi-comic-warrior | 4d29c13b | 610c3750-68e2-43af-9ed7-5ab6c9e8cb74 | 392.8 | The armoured warrior reads as a lookalike of a famous tabletop franchise soldier; kept local under the no-franchise rule. |

## Not rendered

- `anifox-lazy-color-character` and `anima-v1-lazy-color-character`: tagged `adult-illustration` (the Times Lazy mature-body wildcard pack); out of scope for an SFW lab.

## Observations

- Anima-family and SDXL jobs took 18-51 s each; Krea GGUF jobs took 218-393 s. The Krea sampler ran at about 4-5 s/step, so most of each Krea job was the CPU text encode and model load while host commit sat at 55-71 % (other sessions were running).
- The Studio's `recipe.json` and `workflow.json` keep the wildcard template; the expanded prompt is only in ComfyUI `/history` (the wildcard-study receipt records it in `inspection`).
- The three `*-adapter-audition` renders used the NSFW-girls adapter at 1.0 with the fully clothed baseline prompt. All three stayed clothed and changed body proportions and background more than style.
- Where recipes are browsed: the Creative Bundles dialog (`app/static/bundle-explorer.js`) shows these thumbnails on cards and in the selected-recipe panel. The workbench recipe picker (`#recipeSelect` in `app/static/app.js`) is a plain `<select>` with no thumbnail slot; noted for the design handoff, not changed here.

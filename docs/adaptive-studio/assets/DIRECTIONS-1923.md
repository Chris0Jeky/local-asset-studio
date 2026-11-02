# Three characterful art directions (#1923)

**Status: proposal. The choice is the owner's.** On 2 November 2026 the owner rejected the neutral illustration wave
(an empty picture frame, a neutral explorer portrait, calm editorial spot style): "the images we're creating seem very
bland and neutral, which isn't in the spirit of what this project is, we're not just creating neutral assets". This file
proposes three boldly different anime directions for the Studio's own illustrations, each made with the Studio's own
presets on the same five slots so they can be compared side by side in Versus. Nothing here is accepted art.

## What every direction shares

- **A cast, not props.** Every illustration has a character doing the task the slot explains. The character's action is the
  teaching: sketching on a blank sheet *is* "start from an idea"; pinning three pictures around a blank canvas *is*
  "combine". Empty states are the character inviting you to fill the room, not a lonely frame.
- **Made here first.** The Studio's own local presets make the pictures (Anima, MOSS + style adapters, Krea 2 retro). That
  makes them true to what the Studio can do, keeps prompt IDs and recipes, and costs nothing. ChatGPT is used only where it
  adds something a local preset cannot (see [the prompt plan](#replacement-prompt-plan)).
- **Original adults, SFW, text-free.** Original characters only, every one an adult, no franchise look-alikes, no letters
  or logos in the pixels (captions stay HTML). The existing composition contract in [ART-DIRECTION.md](ART-DIRECTION.md)
  still applies: calm text-safe areas, deliberate crops.

## The five comparison slots

| Slot | Catalogue row it fills | What the picture shows (all three directions) | Canvas |
| --- | --- | --- | --- |
| Welcome | `guide-welcome` (onboarding, first run) | The guide at the workshop door, welcoming you in; calm wall on the left for text | 1536×1024 |
| Create | `workflow-create` | The guide's first stroke on a blank sheet, light rising from it like an idea | 1536×1024 |
| Combine | `workflow-combine` | The guide pinning three different pictures around one blank canvas, linked to it | 1536×1024 |
| Empty | `state-blank` (friendly empty library; the owner allowed pictures for friendly empty states on 27 Sep) | The guide in an empty gallery, holding up an empty frame to you | 1536×1024 |
| Canon | `reference-identity` | The guide's full-body reference on a plain background | 1024×1536 |

The recipes, seeds, prompt IDs and output hashes are in the lab log (`art-direction/runs.jsonl` in the R&D night folder),
not in Git; the pictures stay local.

---

## Direction A: Suzu's Harbour Studio (mascot-led, bright cel anime)

**Idea.** The Studio has a guide: **Suzune "Suzu" Aokawa**, an original 21-year-old cartographer's apprentice from a
harbour town (created by the waifu-lab lane on 2 Nov; bible in its lab folder). The Studio is her sunlit map-room
atelier. Maps are pictures, her compass is the recipe, her satchel is the library. She can follow the user through every
step and later exists as a toon 3D model (VRM/GLB) for a living guide.

| | |
| --- | --- |
| Palette | Suzu's own: teal hair `#3FA7A0`, navy jacket `#24324F`, vermilion skirt and ribbon `#D9472B`, cream `#F3EBD8`, brass `#C8A04A`, on sea-blue and sunlit white |
| Line and paint | Clean modern TV-anime line, flat cel shading with one shadow tone, crisp highlights, bright daylight |
| Mood | Cheerful, curious, warm; slice-of-life |
| Recurring | Suzu (side braid with red ribbon, ahoge, brass compass, rolled map), the map room, the lighthouse beyond the window |
| Local route | `anima-portrait` (Anima Aesthetic 1.1) with the bible's prompt core; `character-sheet-klein-9b` for turnarounds; `anima-ref-adapter-turbo` to carry identity from an approved canon |
| Terms (recorded, not cleared) | Anima weights and the ref adapter: CircleStone Labs Non-Commercial (`presets/catalog.json`); fine for this private tool, a blocker for any commercial release of the art |
| Do | Let her act out the step; keep her silhouette readable at thumbnail size; reuse the same props |
| Don't | Chibi or childlike proportions; fan-service; let her sit over controls or bounce for attention; text on maps |

## Direction B: Impasto Atelier (painterly, dramatic, Mikko-impasto MOSS)

**Idea.** The Studio is a lamplit painter's atelier at night, run by **Maestra Ilse**, an original 34-year-old painter
(auburn hair pinned up with a brush, green eyes, beauty mark, oxblood corset vest over a paint-stained linen shirt), with
a small black cat. Built on the look the owner's Versus presses favoured: MOSS-Image with the mikkoani and Impasto 2.5D
adapters.

| | |
| --- | --- |
| Palette | Oxblood, umber and lamplight gold, cream canvas, deep ultramarine shadows |
| Line and paint | Bold 90s ink contours (mikkoani 0.9) over visible impasto brushwork (Impasto 2.5D 0.25); strong chiaroscuro |
| Mood | Romantic, rich, a little theatrical; the craft of painting |
| Recurring | Ilse, the black cat, easels, gilded empty frames, gold paint ribbons as the "data flow" motif |
| Local route | `moss-t2i` (MOSS-Image SFT int8, isolated backend 8198), 30 steps, Euler / sgm_uniform, CFG 3, adapters as above; `kromoss-t2i` + DMD2 (+ Mikko) as the 8-step fast variant |
| Terms (recorded, not cleared) | MOSS-Image SFT: Apache-2.0; mikkoani: civitai flags include Sell; Impasto 2.5D: no Sell flag, so no selling of its images (`models/library.json`) |
| Do | Keep the brushwork at the decorative edges and the faces clean; use the cat for small states |
| Don't | Photographic faces (MOSS drifts there without "2D anime illustration"); muddy, low-contrast crops behind UI text |

## Direction C: Night Shift '89 (vivid retro OVA)

**Idea.** The accepted pilot world, Retro Anime / Night Shift (`retro-anime-master-z2`), gets its residents: **Kiko**, an
original adult night-shift animator in her mid-twenties (choppy magenta hair, amber glasses pushed up, headphones, teal
bomber jacket), and **Bit**, a small boxy robot with a CRT face and two dot eyes. Bit is the nonhuman helper the old
brief wanted, but with personality.

| | |
| --- | --- |
| Palette | Hot magenta and electric cyan neon against deep indigo night, sunset-orange accents |
| Line and paint | 1980s OVA cel: hard two-tone shadows, airbrushed highlights, film grain, slight VHS softness |
| Mood | Energetic, nostalgic, cool; the 2 a.m. animation studio |
| Recurring | Kiko, Bit, the loft, light tables, the elevated train in the rain |
| Local route | `krea-portrait-gguf` / `krea-environment` (Krea 2 Turbo + the official retro-anime adapter, trigger "purple retro anime style"); `wan22-i2v` for a short ambient loop |
| Terms (recorded, not cleared) | Krea 2 Community Licence with output/commercial restrictions ([LICENCE-EVIDENCE-1512.md](LICENCE-EVIDENCE-1512.md#krea-2)) |
| Do | Tie every picture to the Night Shift loft so it continues the accepted environment; let Bit carry small states |
| Don't | Imitate a named 80s show or its characters; readable screens or signage; neon borders across UI text |

---

## Replacement prompt plan

Once the owner picks a direction, the illustration rows are made **locally first**. The rejected
[CHATGPT-PROMPT-PACK.md](CHATGPT-PROMPT-PACK.md) is not run.

1. **Canon.** Make the chosen guide's canon on the direction's preset (four seeds), owner picks one; then a
   `character-sheet-klein-9b` turnaround from it. Every later picture of that character takes the approved canon as its
   reference (`anima-ref-adapter-turbo` for A; `combine-klein-9b` or `restyle-klein` to bring B/C pictures back on model).
2. **Sixteen workflow vignettes** (`workflow-*`): the guide acting out each step, same room, same props. One preset per
   direction as above; up to four seeds per row; agent defect check (hands, extra figures, letters), then Versus.
3. **Friendly empty states** (`state-blank`, empty library): pictures in the direction. **Error states** stay themeable SVG
   from the Claude Design brief (owner answer, 27 Sep 2026); the guide may appear as a small vector sticker there.
4. **Reference examples** (`reference-*`): identity and outfit use the guide's canon; pose, style, composition, lighting
   and background stay character-free teaching pictures, rendered on the direction's preset so the teaching set matches.
5. **Guide expressions** (`guide-*`, deferred on 27 Sep): un-deferred only if the owner picks a mascot-led direction;
   made from the canon with `restyle-klein` / Klein edit for expression changes.
6. **ChatGPT only where it adds something:** (a) a clean vector-like sticker version of the guide for SVG states and the
   favicon, (b) a layout fix where a local model cannot keep a text-safe area, with the approved local picture uploaded.
   Results come back through `intake.py receipts --provider chatgpt` as before.

Each made picture keeps its Studio job, prompt ID, recipe and hash. Generated, inspected and accepted stay separate words:
nothing becomes accepted art until the owner says so.

# ChatGPT prompt pack, waves 1 and 2

Ready-to-paste prompts for every `chatgpt-image` request in waves W1 and W2 of [PRODUCTION-PLAN.md](PRODUCTION-PLAN.md).
Each prompt is written for ChatGPT's built-in image generation (the route the owner calls "Image 2.5"). This pack does not
name a model ID: if ChatGPT shows which image model it used, note it when you hand the file back; otherwise it stays unknown.

## How to use it

- **One ID per chat.** Paste the prompt block exactly. Ask for one image at a time and make at most four candidates per ID,
  with at most two refinement rounds, each asking for one change ("keep everything, but make the left half emptier").
- **Anchors first.** Three IDs are anchors: `workflow-create` (the vignette style), `reference-identity` (the character
  canon) and the GPU lab's `retro-anime-master` (the scene). Accept an anchor before making anything that uploads it. To
  upload, attach the accepted anchor file from `inbox/` to the chat before pasting the prompt.
- **Pictures only.** If a result contains letters, numbers, signs, logos, buttons or a watermark, ask: "Remove every letter,
  number, sign and logo; change nothing else." Captions and labels are added later as real HTML.
- **Sizes.** Ask for the aspect ratio in the prompt; ChatGPT may return a different pixel size. Keep what it returns: the
  crop or upscale to the delivery size is a later, recorded step.
- **Save as** `<asset-id>--<width>x<height>--candidate-<n>.png`, for example `workflow-create--1536x1024--candidate-1.png`.
  Use the size ChatGPT actually returned if you know it; otherwise leave the size out (`workflow-create--candidate-1.png`).
  Never reuse a candidate number for a different picture.

## How to bring results back

1. In your `local-asset-studio` checkout, create `docs/adaptive-studio/assets/inbox/` (Git ignores it) and save every
   download there under the name given with its prompt.
2. Run `python docs/adaptive-studio/assets/intake.py receipts --provider chatgpt`, or ask an agent to. It reads the real
   size, format and alpha channel from each file, hashes it, takes the anchors from the prompt's "Anchor:" line and writes `docs/adaptive-studio/assets/receipts/<file-name>.json` from
   `receipt-template.json`, with the hash of the prompt section below so the receipt names the exact prompt text. It
   refuses unknown IDs and never overwrites a receipt with a different file. It changes nothing in `inbox/`.
3. Tell an agent which candidate you accept for each ID, or that none is good enough. The agent records your words and
   the date in that receipt's `art_review` and commits the receipts. Nothing is accepted until you say so.
4. The picture files stay on your PC. A later, separate step selects which accepted files ship in the Studio.

## Wave 1

### `workflow-create`

Save as `workflow-create--<w>x<h>--candidate-<n>.png`. Anchor: none (this is the style anchor for all sixteen vignettes).

```text
Create an original, quiet conceptual illustration for a creative software's "start from a written idea" step.

Subject: a single blank picture frame standing upright on a plain work surface, receiving a small, soft pool of warm light from above, as if an idea is about to become an image. The frame is empty: no picture, no scribbles, no example artwork inside it.

Style: clean hand-drawn line work with soft flat colour fills and a faint paper grain, like a calm editorial spot illustration. Uniform medium line weight. Seen from a slightly raised, front three-quarter viewpoint. Simple geometric shapes: frame, folio sheet, a small four-pointed star as the only decorative motif.

Palette: graphite and warm ivory for most surfaces; small accents of desaturated rose and muted cyan; the light is a small warm amber glow. Background is a plain, very light warm grey.

Composition: aspect ratio 4:3 landscape (if only 3:2 is offered, use 3:2 and keep the outer left and right edges empty so it can be cropped to 4:3). Keep the subject compact and centred slightly above the middle. Leave the bottom third of the image calm and nearly empty, because a caption will sit there.

Do not include: any text, letters, numbers, labels, logos, watermarks, user-interface elements, buttons, cursors, screens, people, hands or characters.
```

### `reference-identity`

Save as `reference-identity--<w>x<h>--candidate-<n>.png`. Anchor: none (this is the character canon; approve it before
`reference-outfit`, `workflow-sheet` or any sample set).

```text
Create an original character portrait to serve as a reference picture that teaches "this is who the character is".

Subject: an original adult woman explorer, clearly in her early thirties, head and shoulders, facing the viewer in a relaxed three-quarter turn. Distinctive, easy-to-recognise features: a short asymmetric dark-teal bob with one silver streak over her left temple, amber eyes, a small scar through her left eyebrow, a calm confident expression. She wears an olive field jacket with a high collar. She is not based on any real person, celebrity or existing franchise character.

Style: clean contemporary anime illustration with painterly soft shading, clear readable silhouette of face and hair.

Lighting and background: soft, even frontal light; a plain neutral mid-grey studio background with no objects.

Composition: portrait aspect ratio 2:3. Head and shoulders fill the upper two-thirds; the full hair silhouette is visible and not cropped.

Do not include: any text, letters, numbers, logos, watermarks, badges, jewellery with lettering, user-interface elements, other people or props.
```

### `retro-anime-wall`

Save as `retro-anime-wall--<w>x<h>--candidate-<n>.png`. Anchor: upload the accepted `retro-anime-master` file first. Do
not run this before the owner has accepted a master.

```text
The attached image is the accepted scene: an original late-night animation workshop above a rain-washed city. Create a new, quieter image of the same place for use as a background wall behind a software panel.

Keep the same world: the same hand-painted retro anime look, the same materials, the same graphite colours with small desaturated rose and cyan reflections and a small warm amber lamp glow, the same rainy night outside.

Change the framing: aspect ratio 3:2 landscape. Show a calm stretch of the loft's wall and window. The central 70% of the image must be very low in detail and low in contrast, like a softly lit empty wall or a plain window area with gentle out-of-focus rain. Keep all interesting detail (a sliver of shelf, the edge of the window frame, a hint of distant train light) at the outer edges only.

No sharp high-contrast lines may cross the middle of the image. Nothing may look like a gauge, chart, screen reading, indicator lamp or button.

Do not include: any text, letters, numbers, signs, logos, watermarks, user-interface elements, people or characters.
```

## Wave 2

### `workflow-combine`

Save as `workflow-combine--<w>x<h>--candidate-<n>.png`. Anchor: upload the accepted `workflow-create` file first.

```text
The attached image is the accepted style anchor for a series of conceptual illustrations. Create a new illustration in exactly the same style: same line weight, same flat fills with faint paper grain, same raised front three-quarter viewpoint, same palette (graphite, warm ivory, small desaturated rose and muted cyan accents, a small amber glow) and the same plain very light warm grey background.

Subject, for the "combine several source pictures" step: three distinct picture frames, clearly different from one another in shape and tint (one tall, one square, one wide), angled towards a single empty destination frame in the centre. The three frames hold only simple abstract shapes, not pictures. Faint lines connect each source frame to the empty destination. The destination frame is empty; nothing suggests a finished result.

Composition: aspect ratio 4:3 landscape (or 3:2 with empty outer edges). Subject centred slightly above the middle; the bottom third calm and nearly empty for a caption.

Do not include: any text, letters, numbers, labels, logos, watermarks, user-interface elements, buttons, screens, people or characters.
```

### `workflow-pose`

Save as `workflow-pose--<w>x<h>--candidate-<n>.png`. Anchor: upload the accepted `workflow-create` file first.

```text
The attached image is the accepted style anchor for a series of conceptual illustrations. Create a new illustration in exactly the same style: same line weight, same flat fills with faint paper grain, same raised front three-quarter viewpoint, same palette (graphite, warm ivory, small desaturated rose and muted cyan accents, a small amber glow) and the same plain very light warm grey background.

Subject, for the "put a character into a pose" step: on the left, a plain filled silhouette of a standing figure inside a frame (who the character is); on the right, a separate frame holding a simple stick-and-joint pose sketch in a clearly different, asymmetric leaning pose (the geometry). The two must read as two different inputs: the silhouette is filled and soft, the pose sketch is thin lines and dots. No face details, no clothing detail.

Composition: aspect ratio 4:3 landscape (or 3:2 with empty outer edges). The two frames side by side, centred slightly above the middle; the bottom third calm and nearly empty for a caption.

Do not include: any text, letters, numbers, labels, arrows with words, logos, watermarks, user-interface elements, buttons, screens or realistic people.
```

### `workflow-recover`

Save as `workflow-recover--<w>x<h>--candidate-<n>.png`. Anchor: upload the accepted `workflow-create` file first.

```text
The attached image is the accepted style anchor for a series of conceptual illustrations. Create a new illustration in exactly the same style: same line weight, same flat fills with faint paper grain, same raised front three-quarter viewpoint, same palette (graphite, warm ivory, small desaturated rose and muted cyan accents, a small amber glow) and the same plain very light warm grey background.

Subject, for the "recover interrupted work" step: an intact, closed document folder resting calmly on the surface, and a small paper receipt slip gently returning to a slot in the folder's side. The mood is continuity and safekeeping: everything is preserved and nothing is being redone. No circular "retry" arrows, no warning signs, no broken or torn objects.

Composition: aspect ratio 4:3 landscape (or 3:2 with empty outer edges). Subject centred slightly above the middle; the bottom third calm and nearly empty for a caption.

Do not include: any text, letters, numbers, barcodes, labels, logos, watermarks, user-interface elements, buttons, screens, people or characters. The receipt shows only plain horizontal lines, never writing.
```

### `reference-outfit`

Save as `reference-outfit--<w>x<h>--candidate-<n>.png`. Anchor: upload the accepted `reference-identity` file first.

```text
The attached image is the accepted character reference: an original adult woman explorer in an olive field jacket. Create a reference picture that teaches "this is the outfit", separate from the person.

Subject: her complete outfit displayed on a plain neutral dress form, with no person and no head: the olive field jacket with the high collar as in the attached image, a practical belt with small pouches, sturdy trousers and boots placed at the base of the stand, and a simple canvas satchel hanging from one shoulder of the dress form. The outfit is sized for an adult. Every garment is fully visible from collar to boots.

Style: the same clean contemporary anime illustration style and colour treatment as the attached image, with painterly soft shading.

Lighting and background: soft, even frontal light; a plain neutral mid-grey background with no other objects.

Composition: portrait aspect ratio 2:3, the whole dress form and boots inside the frame with a small margin.

Do not include: any text, letters, numbers, brand marks, logos, patches with lettering, watermarks, user-interface elements or any person.
```

### `reference-pose`

Save as `reference-pose--<w>x<h>--candidate-<n>.png`. Anchor: none.

```text
Create a reference picture that teaches "this is the pose", with no identity attached.

Subject: a plain wooden artist's mannequin with adult proportions, full body, in a clear asymmetrical leaning pose: the weight on the right leg, the left shoulder leaning against a plain vertical pillar, the right arm bent with the hand on the hip, the left leg crossed in front at the ankle, the head tilted slightly. Both hands and both feet are fully visible and not hidden behind anything.

Style: clean, simple illustration with soft shading and clearly readable joints.

Lighting and background: soft even light from the front-left; a plain light-grey background; the pillar is a simple untextured column.

Composition: portrait aspect ratio 2:3. The whole figure from head to feet fits inside the frame with a margin.

Do not include: any text, letters, numbers, logos, watermarks, user-interface elements, clothing, hair, facial features or other objects.
```

### `reference-style`

Save as `reference-style--<w>x<h>--candidate-<n>.png`. Anchor: none.

```text
Create a reference picture that teaches "this is the drawing style", with no character in it.

Subject: an original ink study of a quiet city street corner: stacked rooftops, a small footbridge, overhead wires and a distant tower. No people, no animals, no vehicles with markings.

Style: confident black ink line work with varied brush pressure, loose cross-hatching and a few flat wash tones in warm grey and one muted teal, on off-white paper. The line texture is the point of the picture.

Composition: square aspect ratio 1:1. A balanced composition with a clear foreground, middle ground and background.

Do not include: any text, letters, numbers, shop signs, readable signage, logos, watermarks, user-interface elements, people or characters. Any sign shapes stay blank.
```

### `reference-composition`

Save as `reference-composition--<w>x<h>--candidate-<n>.png`. Anchor: none.

```text
Create a reference picture that teaches "this is the layout and camera framing", with nothing distracting in it.

Subject: three simple, untextured masses arranged in depth on a plain ground: a tall dark block in the left foreground, a medium pale cube in the middle ground slightly right of centre, and a low wide slab far in the background. A clear horizon line sits at one third from the top. The camera is at standing eye height with a gentle wide-angle perspective, so the depth is obvious.

Style: simple clay-render look with flat muted colours (charcoal, stone grey, pale sand) and soft shadows.

Composition: square aspect ratio 1:1.

Do not include: any text, letters, numbers, logos, watermarks, user-interface elements, people, characters, plants or detailed objects.
```

### `reference-lighting`

Save as `reference-lighting--<w>x<h>--candidate-<n>.png`. Anchor: none.

```text
Create a reference picture that teaches "this is the lighting", with a neutral subject.

Subject: an original, generic plaster head on a plain plinth, in the manner of an art-class study cast. It must not copy any known sculpture or real person; the face is simplified and neutral.

Lighting: a single strong directional light from the upper left, about 45 degrees to the side and above, casting a clear shadow across the right side of the face and a crisp cast shadow on the wall behind. No fill light and no rim light, so the light direction is unmistakable.

Background: a plain matte mid-grey wall and surface.

Style: realistic, softly photographic rendering of matte white plaster.

Composition: square aspect ratio 1:1, the head and plinth centred with space around them.

Do not include: any text, letters, numbers, logos, watermarks, user-interface elements, colour gels or additional objects.
```

### `reference-background`

Save as `reference-background--<w>x<h>--candidate-<n>.png`. Anchor: none.

```text
Create a reference picture that teaches "this is the background environment", with no subject in it.

Subject: an original, empty open-air railway platform at dusk: a long platform edge leading into the distance, a simple canopy with slim columns, the rails, and soft sky behind low hills. Nobody is on the platform, and the foreground is uncluttered open floor where a character could later be placed.

Style: soft painterly anime background art with gentle gradients and atmospheric perspective.

Palette: dusk blue and violet sky, warm lamp light under the canopy, muted concrete greys.

Composition: square aspect ratio 1:1. Eye-level camera; the platform leads the eye from the lower left into the distance.

Do not include: any text, letters, numbers, station names, signs with writing, timetables, advertisements, logos, watermarks, user-interface elements, people, animals or trains with markings. Any sign boards stay blank.
```

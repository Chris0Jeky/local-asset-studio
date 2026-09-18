# Create, with room to work

Three presentations share one real workbench:

- **Focus** remains the production default: prompt, required sources and the always-visible Generate dock, with tuning out of the way.
- **Studio** places the existing result gallery beside the editor at desktop widths of 1280 px and above.
- **Immersive Studio** adds a compact run-setup rail, the same central editor, one read-only next-action rail and an optional local environment header.

Layout, skin and ambience are independent presentation choices. Switching any of them preserves the selected recipe, attached files, prompt, adapters, seed, draft recovery, output gallery and original submission handler. It does not submit a job or stage a source. The browser stores only an allow-listed `{layout, skin, ambience}` object in `studio.workshop.presentation.v2`; valid v1 layout/skin preferences are read with ambience defaulting to `none`.

## Visual choices

| Skin | Direction | Decoration |
| --- | --- | --- |
| Atelier | Warm graphite, restrained peach accent | Neutral, no illustration |
| Arcade | Midnight blue, mint controls, lavender highlights | Original pixel-city motif |
| Sakura | Dark plum, soft rose, warm text | Original blossom motif; anime-inspired, non-explicit |
| Retro Anime | Deep navy glass, rose/lavender accents and cyan highlights | Designed for the paired Night Shift / Quiet Morning environment |

| Ambience | Behaviour |
| --- | --- |
| None | No environment art or reserved gap |
| Night Shift | Original rainy-city workshop scene, embedded locally in CSS |
| Quiet Morning | Same camera and architecture in a softer daylight treatment |

Ambience is decorative only. It contains no status, instructions or controls; failure to render it cannot block editing or generation. There are no remote media, fonts, video, audio, autoplay, service worker or third-party requests. Forced-colour mode removes the art, and the interface remains complete without it.

## Contextual guidance

Immersive Studio shows one next action derived from the current UI:

- reveal the existing readiness details when Generate is blocked;
- focus the existing Generate control when it is ready;
- open the existing Recent runs surface when outputs are present.

The guidance action never clicks Generate, changes a recipe, rewrites a prompt, stages a reference or asserts backend health. Its explanation identifies the observation it used.

## Try the standalone prototype

From the repository root:

```sh
python scripts/export-workshop-prototype.py --output .runtime/workshop-preview.html
```

Open that file in a browser. It embeds its scripts, both production workshop stylesheets, paired ambience art and existing repository examples. There are no CDN, font, API or model requests. The review build starts in **Immersive Studio + Retro Anime + Night Shift** so the approved visual pilot is immediately visible. Production still starts in **Focus + Atelier + None**.

Try the presentation controls; Change recipe, search, cancel or confirm replacement; fine-tune parameters and the example adapter; attach a local image in Refine; save a demo brief in this tab; export the brief; and use Preview setup. The source page is `prototype.html` with `prototype-data.js`; presentation comes from the same `app/static/workshop.js`, `workshop.css` and `workshop-immersive.css` as the application.

The prototype is not an alternative executor. Its recipes, notices and saved setups are demo data. Preview setup does not call ComfyUI or simulate a successful run. Displayed result art already existed in this repository. Uploaded preview files stay in the tab. Closing the tab clears demo drafts and sources; exported demo briefs are not claimed to be compatible Studio setup files.

## Review package

- [Design and state ownership](DESIGN.md)
- [Implementation plan](PLAN.md)
- [Validation evidence and remaining qualification](VALIDATION.md)
- [Local asset provenance](ASSETS.md)
- [Paired usability trial](EVALUATION.md)
- [Approved Immersive Studio design](../superpowers/specs/2026-09-18-immersive-studio-design.md)

`Workshop UI` CI publishes browser reports/screenshots and the exported prototype. The application driver uses the existing synthetic API fixture, not a live GPU.

## Small, reversible integration

No framework migration, generated graph change, new prompt store or backend service. `studio-shell.js` loads the existing progressive presentation adapter; that adapter adds `workshop-immersive.css` only after its DOM contract is present. Existing editable DOM nodes and handlers remain the sole owners. The source picker, readiness actions, queue, provenance, saved setups and draft recovery keep their existing owners. If the expected DOM is absent, enhancement does not mount.

Removing the new stylesheet/assets and reverting the versioned presentation additions restores the previous workshop. No domain migration or job resubmission is required.

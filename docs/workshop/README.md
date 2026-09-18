# Create, with room to work

Two presentations, one real workbench. **Focus** is the default: prompt, sources and an always-visible Generate dock, with tuning out of the way. **Studio** brings the existing result gallery alongside the editor at desktop widths of 1280 px and above. On smaller screens the same gallery follows the editor.

Choose **Layout** and **Skin** beside the active recipe. Every layout works with every skin. Changing either never changes the selected recipe, attached sources, prompt, adapters, seed or submission state. It does not trigger generation. Your browser remembers only these presentation choices in `studio.workshop.presentation.v1`.

| Skin | Direction | Decoration |
| --- | --- | --- |
| Atelier | Warm graphite, restrained peach accent | Neutral, no illustration |
| Arcade | Midnight blue, mint controls, lavender highlights | Original pixel-city horizon |
| Sakura | Dark plum, soft rose, warm text | Original blossom branch; anime-inspired, non-explicit |

## Try the standalone prototype

From the repository root:

```sh
python scripts/export-workshop-prototype.py --output .runtime/workshop-preview.html
```

Open that file in a browser. It includes its scripts, styles and example images; there are no CDN, font, API or model requests. It starts in Studio to make the visual comparison easy. **Production still starts in Focus.**

Try the layout and skin selectors; Change recipe, search, cancel or confirm replacement; fine-tune parameters and the example adapter; attach a local image in Refine; save a demo brief in this tab; export the brief; and use Preview setup. The source page is `prototype.html` with `prototype-data.js`; presentation comes from the same `app/static/workshop.js` and CSS as the application.

The prototype is not an alternative executor: its recipes, notices and saved setups are demo data. Preview setup does not call ComfyUI or simulate a successful run. Displayed art already existed in this repository. Uploaded preview files stay in the tab. Closing the tab clears demo drafts and sources; exported demo briefs are not claimed to be compatible Studio setup files.

## Review package

- [Design and state ownership](DESIGN.md)
- [Implementation plan](PLAN.md)
- [Validation evidence and remaining qualification](VALIDATION.md)
- [Local asset provenance](ASSETS.md)
- [Paired usability trial](EVALUATION.md)

`Workshop UI` CI publishes `workshop-browser-evidence`: component and actual-application screenshots/reports plus the exported prototype. The application tests use the existing synthetic API fixture, not a live GPU. The older use-case and readiness browser suites also exercise the moved surfaces.

## Small, reversible integration

No framework migration, generated graph change, new prompt store or backend service. `studio-shell.js` loads a small progressive presentation adapter after the existing workbench. Existing DOM nodes and their original event handlers move into calmer surfaces; the source picker, readiness actions, queue, provenance and draft recovery keep their owners. If the expected DOM is absent, enhancement does not mount. Reverting the shell loader and the new files restores the older presentation.

Focus and Studio are a stacked two-PR delivery. Merge the Focus foundation before the Studio/skins follow-on. Do not merge until the relevant CI and owner acceptance checks have been reviewed.

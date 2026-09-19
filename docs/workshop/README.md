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

Ambience is decorative only. It contains no status, instructions or controls; failure to render it cannot block editing or generation. There are no remote media, fonts, video, audio, autoplay, service worker or third-party requests.

## Requested ambience and effective rendering

The selected ambience and the decoration currently painted by the browser are deliberately separate:

| Effective mode | Meaning |
| --- | --- |
| `none` | The user selected None; no ambience surface is reserved. |
| `poster` | The approved local static Night Shift or Quiet Morning poster is available. |
| `tokens` | Theme geometry and colours remain, but illustration is suppressed because the asset is unavailable or forced-colour mode is active. |
| `suspended` | The document is hidden, so optional illustration is not painted until it is visible again. |

An available local poster does not depend on internet reachability or backend health. Offline internet with a healthy local backend, and online internet with a down backend, produce the same static-poster decision. Reduced motion, data saving, user pause and active or uncertain execution keep motion ineligible; they do not turn a valid static environment into an “offline punishment”. This delivery remains static-only and reports `motionEligible: false`.

`workshop-ambience-policy.js` is a pure bounded policy. It cannot receive URLs, prompts, credentials, filesystem paths or executable configuration, and every decision has `authorizesExecution: false` and `commands: []`. `workshop-ambience.js` is a separate presentation adapter that observes allow-listed appearance/readiness signals, updates only decorative data attributes and status text, and disconnects its listeners when destroyed. It never clicks Generate, changes a recipe, stages a source or writes to storage.

The adapter does not assume that requested art exists. Before the immersive stylesheet is confirmed it reports the asset as unknown and uses theme tokens; a stylesheet error reports it missing; a successful stylesheet load makes the static poster available. These transitions affect decoration only and never alter the selected ambience preference.

If the policy script cannot load, the shell still mounts the ordinary workshop and retains the earlier static presentation. Forced-colour mode, unresolved styles and missing-asset fallback leave the prompt, references, errors and run controls complete.

## Contextual guidance

Immersive Studio renders one primary semantic action from the read-only presentation context:

- **Review readiness** reveals the existing readiness disclosure when Generate is blocked or readiness is unknown;
- **Review sources** focuses the exact outstanding existing file input or source board when source roles need attention;
- **Focus Generate** focuses the existing Generate control when it is ready, without activating it;
- **Open recent runs** opens the existing result disclosure when outputs are present.

The production action adapter maps only those four actions because the current capture publishes `blocked`, `ready` or `completed` execution and no draft-conflict claim. The pure context module retains operation-inspection and conflict-review vocabulary for consumers that can publish those states, but the current workshop does not register unreachable handlers.

Guidance never clicks Generate, changes a recipe, rewrites a prompt, stages a reference, retries an operation or asserts backend health. Its explanation identifies the observation it used, and a demoted readiness action retains the specific blocker description.

## Try the standalone prototype

From the repository root:

```sh
python scripts/export-workshop-prototype.py --output .runtime/workshop-preview.html
```

Open that file in a browser. It embeds its scripts, production workshop stylesheets, the local ambience policy, paired ambience art and existing repository examples. There are no CDN, font, API or model requests. The review build starts in **Immersive Studio + Retro Anime + Night Shift** so the approved visual pilot is immediately visible. Production still starts in **Focus + Atelier + None**.

Try the presentation controls; Change recipe, search, cancel or confirm replacement; fine-tune parameters and the example adapter; attach a local image in Refine; save a demo brief in this tab; export the brief; and use Preview setup. The source page is `prototype.html` with `prototype-data.js`; presentation comes from the same context, workshop, ambience-policy and ambience-adapter modules as the application.

The prototype is not an alternative executor. Its recipes, notices and saved setups are demo data. Preview setup does not call ComfyUI or simulate a successful run. Displayed result art already existed in this repository. Uploaded preview files stay in the tab. Closing the tab clears demo drafts and sources; exported demo briefs are not claimed to be compatible Studio setup files.

## Review package

- [Design and state ownership](DESIGN.md)
- [Implementation plan](PLAN.md)
- [Validation evidence and remaining qualification](VALIDATION.md)
- [Local asset provenance](ASSETS.md)
- [Paired usability trial](EVALUATION.md)
- [Approved Immersive Studio design](../superpowers/specs/2026-09-18-immersive-studio-design.md)
- [Read-only presentation context](../superpowers/specs/2026-09-18-presentation-context-design.md)
- [Ambience eligibility policy](../superpowers/specs/2026-09-18-workshop-ambience-policy-design.md)

`Workshop UI` CI publishes browser reports/screenshots and the exported prototype. Its dedicated ambience journey qualifies static poster, token fallback, offline independence, forced-colour restoration, None, and stylesheet readiness moving through unknown, missing and available states. The application driver uses the existing synthetic API fixture, not a live GPU.

## Small, reversible integration

No framework migration, generated graph change, new prompt store or backend service. `studio-shell.js` loads the read-only context, then the pure ambience policy, then the existing progressive workshop adapter, then the isolated ambience presentation adapter. Existing editable DOM nodes and handlers remain the sole owners. The source picker, readiness actions, queue, provenance, saved setups and draft recovery keep their existing owners.

If the policy is absent, workshop loading still proceeds. Removing the policy/adapter loads and their focused CSS restores the earlier static workshop without a domain migration or job resubmission.

# Environment, motion and media policy

## Creative direction: a living room around the work

**Retro Anime / Night Shift:** an original late-night animation workshop above a rainy city. Use a distant rail line, a desk lamp, a few restrained CRT panels and a character-free text-safe wall. Movement is slow rain, one distant train and a small change in reflected light. A matching **Quiet Morning** composition replaces motion with a still local poster and warm daylight. The user may choose either at any connectivity state.

Other packs: Atelier (warm materials and drafting desk), Arcade (indigo cabinet glow and abstract horizon), Sakura (plum/rose botanical atmosphere), Minimal Pro (quiet graphite and paper), Sci-Fi Noir (architectural shadows and a distant observatory). Themes share the same component geometry and semantics. A change of wallpaper is not a change of model family or content mode.

Use the Seedance example as a reference for media-led storytelling and distinct capability chapters, not as a template for a constantly moving application. Its fetched page describes audiovisual experiences and a curated showcase; the exact animation implementation was not inspected (S01). Keep an optional showcase/launch surface more cinematic than the everyday editor.

## Distinguish connection and resource states

Never compress these into one “online” boolean:

1. Internet hint (`navigator.onLine`), which is not reliable proof of internet or backend reachability (S07).
2. Studio API observation and its workspace identity.
3. Selected ComfyUI backend/schema readiness.
4. Availability of the chosen decorative asset or provider.
5. Job activity, viewport visibility, user motion choice and resource-saving preference.

A local video can play without internet. A reachable website does not mean ComfyUI is ready. An unavailable optional media provider is not a generation blocker. Never probe a third-party hostname merely to animate a status lamp. Prefer actual requested-asset results and the existing local readiness owner.

## Playback policy, in precedence order

| Condition | Decorative rendering | Loading / interaction |
| --- | --- | --- |
| Hidden tab or environment outside viewport | Pause and stop scheduled work | No new optional requests; do not resume until visible |
| OS reduced motion, forced-colors, or explicit Still | Static matching poster or tokens | No parallax or decorative loop; controls unchanged |
| Active generation, comparison, reference analysis, or unknown execution state | Static poster | Avoid competing decode/compositing while runtime work is active or unknown |
| Save-data / user economy preference | Local small poster | No remote preload; no required battery API |
| User pause | Preserve current frame/poster | Pause persists until the user changes it |
| Approved local loop, explicit Subtle/Cinematic, idle and visible | At most one muted loop | Local first; reject-play and decode-error fallback is poster |
| Remote media explicitly enabled and approved | May load one allowed asset after core UI is interactive | No credentials/referrer/private prompt; cancel on context/skin change |
| Media timeout, offline, unsupported codec or missing file | Same-theme local poster, then CSS tokens | Inline quiet notice; no blocking dialog or layout shift |

Automatic motion lasting alongside other content needs user control; W3C's pause/stop/hide guidance is the baseline, not a substitute for testing (S08). Respect runtime changes to reduced-motion settings (S09), page visibility (S10), and rejected playback promises (S11). No autoplay audio. Optional sound is a separate opt-in with mute available before playback.

## Placement and restraint

Safe locations: a shallow environment window above the workbench, a sidebar wall when wide enough, a collapsed environment drawer and the empty preview area before any private output is displayed. Never put moving faces behind the prompt, a glow behind validation text, scanlines over controls or false progress on a decorative monitor. Avoid infinite marquees and scroll hijacking.

Critical labels and badges are HTML, never baked into a generated image. Art contains no status, button, instruction or essential navigation. Decorative assets use empty alt text/hidden semantics; illustrative workflow examples have a real concise caption. Loading, error and ready still read correctly in monochrome.

## Motion tokens (proposed targets, not performance results)

- Small control feedback: 120-180 ms opacity/color, without resizing the target.
- Panel disclosure: 160-220 ms, preserve scroll anchor and focus; no mandatory animation.
- Scene transition: up to 300 ms crossfade, skip for reduced motion and resource pressure.
- Parallax: at most three clipped decorative layers, 2/4/6 px displacement; transform only, one coalesced frame callback, reset on pointer leave, disabled for coarse pointers and reduced motion. No device-orientation access.
- Ambient loop: 6-10 seconds, fixed camera, muted, gentle seam, no flashing/high-contrast cuts. Start with a local 720p/24 fps rendition and measure before increasing resolution.

Parallax masters require consistent camera, vanishing point and object scale, plus overscan. Generating three unrelated scenes is not a parallax pipeline. Approve one scene, derive aligned layers, fill occluded background, and validate the composite. A depth map is a reviewable derivative, not an automatically trusted geometry measurement.

## Loading and budgets

Core UI renders before optional media. Reserve aspect ratio to avoid shifts. Decode the poster before crossfade; use an asset request epoch and AbortController so an old skin's media cannot replace the new one. Select a rendition for the visible container/DPR; do not decode every master.

Initial proposed budgets: decorative poster at most 300 KiB; optional loop at most 4 MiB; first-screen decorative transfer at most 350 KiB before opt-in motion; optional local theme cache at most 128 MiB with an explicit clear control; maximum one playing decorative video and three parallax layers. A 1920x1080 RGBA image is about 7.9 MiB before browser overhead, so compressed byte size alone is not a memory budget. Account for crossfade overlap and decoded frames. Budgets are hypotheses to qualify on the actual Radeon workstation while inference runs.

No media downloads on every keystroke or task selection. Use immutable content hashes, deterministic rendition selection, local-first lookup and bounded cache eviction. Do not evict a current poster before the replacement is usable. Do not cache API responses, drafts, signed URLs or private result thumbnails as theme assets. No service worker in the initial pilot; offline cached-app behavior is a separate contract from loading local decorative files.

## Asset packaging and security

Each accepted pack has a manifest of stable IDs, token overrides, preview/poster IDs, permitted placements, motion companions, dependencies, checksums, dimensions and a provenance receipt. It cannot execute JavaScript or inject remote CSS/HTML. Resolve accepted local paths under the configured asset root; reject traversal and oversized/decode-invalid files. Imported SVG requires sanitization or rasterization; do not trust embedded scripts, external references or foreignObject. Query/preview text is data, never markup.

Remote intake and provider credentials belong to an explicit acquisition workflow, not the render loop. Store downloaded accepted media locally before making it the default. Respect source terms and record their evidence separately from human art acceptance. Keep imported user artwork out of public theme packages unless deliberately selected for publication.

## Acceptance scenarios

Test instant skin switches during slow poster/loop loads; unsupported video; remote failure after playback; offline with a local loop; no internet but healthy backend; internet available but backend down; uncertain job; generation beginning during a crossfade; tab hiding; reduced-motion changing live; denied storage; memory/economy mode; keyboard pause; zoom and long error text. None may alter a recipe, draft, source or command count.

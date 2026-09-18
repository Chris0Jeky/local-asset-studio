# Next-session production handoff

## Paste this into a future image/asset session

> Work from `docs/adaptive-studio/assets/` in `Chris0Jeky/local-asset-studio`. Read README, ART-DIRECTION, DELIVERY-SPEC and the selected catalogue rows. This is a future production session; the strategy pass produced no art. First reconcile the repository and existing accepted assets. Do not replace current work or generate the entire catalogue.
>
> Start with these selected IDs: `retro-anime-master`, then `retro-anime-quiet`, `retro-anime-hero`, `retro-anime-poster`, `retro-anime-card`, `state-blank`, `state-source-required`. Resolve and approve the scene anchor before its derivatives. Prefer at most four initial master candidates, two targeted refinement rounds, and reused crops rather than independent images. These are proposed work limits; state the finite batch you are actually about to run.
>
> Use native image generation when it is available and appropriate. The owner calls the desired route “image 2.5”; discover the actual tool and record only the model/version it really exposes. Do not put an assumed model ID in API calls. Do not respond with tool argument JSON instead of creating the requested image. Do not claim a tool was used when only a prompt was written.
>
> Build each brief by running `python docs/adaptive-studio/assets/brief.py show <id>` or reading its row and referenced profile. Keep the approved anchor as the actual reference. Preserve camera, palette, proportions and text-safe areas. Generate artwork without UI copy or logos; type labels later as real HTML/vector content. Export actual sizes and record any resizing, alpha repair, cropping or compositing.
>
> Return the actual files, a small candidate review view, per-ID receipts and a clear distinction between produced, source-reviewed, artistically reviewed and runtime-qualified. Ask for owner art acceptance before declaring that stage complete. Package local renditions outside the normal source tree; submit manifests, prompts, accepted public preview selections and integration notes via reviewable PRs. Do not change ComfyUI packages, generation gates, API origins or existing private drafts to install a skin.

## How to use a native image session well

Do one coherent scene before a large batch. Provide the selected asset brief, the approved anchor when one exists, and the actual slot geometry. Request one change per refinement: quieten the left wall, preserve the camera, remove meaningless signage, or repair the alpha edge. Evaluate the real output, not an assumed seed guarantee. Save accepted anchors with a stable ID and checksum.

For parallax, do not ask for “three backgrounds” and assume they align. Produce/approve the flattened scene, separate depth layers, reconstruct hidden pixels, inspect registration, and export common-canvas RGBA files. When native output cannot deliver reliable transparency/layers, use a design/editor tool for the derivative step. A grayscale depth proposal requires visual validation before use.

For loops, begin only after the still and poster are accepted. Give the approved still to an actually available video tool. Ask for fixed-camera environmental movement with a quiet seam and no audio. Inspect returned duration, codec, resolution, seam and object stability. A video capability or provider named in this plan is not evidence of account access, credits or supported settings in the next session.

## Stock/photo acquisition using Pexafy

The installed Pexafy connector exposes semantic text search, image-reference search and similar-photo discovery. Its tool descriptions favor complete scene descriptions over short keyword lists, and results include source IDs, URLs and attribution. This pass inspected those schemas only; it did not perform a search or select a photo.

Use stock for material/lighting studies, neutral objects or a deliberately photographic world. Do not combine unrelated stock photos into a supposedly continuous anime scene without an explicit adaptation stage. Candidate queries:

| Intended use | Natural-language search brief |
| --- | --- |
| Atelier material study | A quiet artist's drafting desk beside a tall window at dusk, with blank cream paper, a warm desk lamp and walnut surfaces, no visible brand names or people. |
| Night Shift lighting reference | A rain-streaked apartment window overlooking a distant city railway at night, with soft cyan and rose reflections near the edges and a dark uncluttered interior. |
| Minimal Pro study | A graphite and ivory workspace with diffuse daylight, one pale desk and strong negative space, photographed straight on with no logos, screens or people. |
| Texture source | A close view of neutral linen and blank paper under soft side lighting, with even detail suitable for a subtle background texture and no recognizable printed pattern. |
| Quiet morning counterpart | An empty creative studio in gentle early morning light, with a low desk and an open view toward a courtyard, muted colors and a calm low-detail wall. |

For “more like this”, reuse the actual returned photo ID or public image URL through the supported tool. Do not invent photo IDs, pass an arbitrary local path as a URL, or manufacture base64 from an image merely seen in chat. Retain the displayed attribution and inspect the original source/terms for the chosen item. Store source-reviewed media locally; do not make a search-result hotlink a required runtime asset.

## Tool roles, not hard dependencies

| Tool family | Appropriate future work | Boundary |
| --- | --- | --- |
| Native image tool | Original scene/vignette/helper candidates and controlled edits | Discover actual tool; keep output identity and actual limitations |
| Pexafy | Semantic stock discovery and consistent source candidates | Search result is not completed acquisition or rights review |
| Adobe/design editor | Crop, alpha/mask cleanup, compositing, color/rendition checks | Inspect available connector actions before promising a specific edit |
| Figma/Canva | Editable component/asset boards, typography and layout review | Functional UI labels remain editable; no screenshot substituted for code |
| Runway/Higgsfield or another connected video tool | Optional still-to-loop production when supported | Check access/settings; bound batch and cost; no auto-purchase |
| Hyperframes | A later coded tutorial/showcase composition, captions and transitions | Works best in Codex; not required for ordinary editor motion |
| Local Python/FFmpeg/editor tools | File metadata, deterministic crops/encoding and packaging | Record transformations; never claim converted pixels were native model output |

Provider examples do not authorize generation, payment or account changes. Do not install a provider plugin solely because it is named here when a suitable connected tool already exists. If a needed capability is absent, retain the unfilled request and report the exact gap rather than inventing output.

## Suggested small production sessions

**Session A, world anchor:** one Night Shift master plus Quiet Morning edit, crop trials and art review. **Session B, core helper family:** blank/source/recovery/conflict states and four workflow vignettes using consistent visual grammar. **Session C, media derivatives:** approved aligned layers and one loop/poster pair, then resource/reduced-motion evaluation. **Session D, factual education:** actual UI recordings at the qualified application commit. **Session E, additional worlds:** one new skin at a time after the first world's acceptance.

The sequence prevents a high-volume art batch from outrunning the actual UX. A next session can take different IDs, but it should name them, follow dependencies and return actual receipts. The current strategy documents remain proposals until the owner chooses implementation and production scope.

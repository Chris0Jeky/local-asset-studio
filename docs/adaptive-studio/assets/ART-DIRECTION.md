# Art direction and world continuity

**Draft update for #1923, 2 November 2026 (the direction choice is the owner's).** The owner rejected the neutral
illustration wave: "we're not just creating neutral assets". The Studio's own illustrations are now characterful anime with
a recurring original cast, made with the Studio's own presets first. Three candidate directions (Suzu's Harbour Studio,
Impasto Atelier, Night Shift '89) are briefed in [DIRECTIONS-1923.md](DIRECTIONS-1923.md) and wait for the owner's pick in
the Versus contest "Studio art directions (#1923)". Until then, "the guide" and "the canon" below mean the chosen
direction's character; the environment worlds and the composition contract are unchanged.

## The visual proposition

The user should feel they have entered a personal animation workshop, not opened a settings form with wallpaper behind it. The environment has depth and character, but the actual workbench stays quiet, opaque enough to read, and spatially stable. The art occupies purposeful windows, margins and empty-state moments. The output the user is making remains the most important image on the page.

**Retro Anime / Night Shift** is the recommended first experiment. Imagine a hand-painted background from an original late-night animated story: a narrow creative loft, a rain-streaked window, a distant elevated train, stacked blank drawing sheets and a soft CRT pool of light. Rose and cyan are localized reflections, not universal neon borders. Most of the central-left wall is quiet. The camera is fixed at a believable seated height. No famous skyline, franchise character, signage, product logo or faux Japanese lettering is needed.

At rest, the scene is a small atmospheric still. With optional ambience enabled and suitable conditions, rain drifts and a distant train crosses slowly. During generation or reduced-motion operation, it becomes still without losing identity. **Quiet Morning** keeps the architecture and lens but replaces the night reflections with cool daylight and a warm lamp. It is an alternate mood available at any time, not a visual punishment for being offline.

## Six coherent packs

| World | Palette/material language | Main composition | Motion candidate | Avoid |
| --- | --- | --- | --- | --- |
| Atelier | Charcoal, cream, walnut, amber; linen, paper, brushed metal | Drafting desk at right; open courtyard beyond | Soft curtain movement or light shift | Generic corporate office, expensive-product photography, cluttered desk |
| Arcade | Indigo, muted violet and cyan; lacquer and original cabinet silhouettes | Cabinets frame a distant abstract horizon | One slow cabinet reflection or horizon pulse | Recognizable games, readable screens, oversaturated borders |
| Sakura | Plum, dusty rose, warm ink timber; botanical accents | Quiet interior opening onto a blossom courtyard | Sparse petals beyond the window only | Pink fog everywhere, petals over text, sentimental stock mascots |
| Retro Anime | Graphite, desaturated rose/cyan and small amber accents; cel-like paint and rain | Night Shift loft with rail line and text-safe wall | Rain, distant train, slight reflection | Franchise imitation, dramatic camera travel, character face behind prompt |
| Minimal Pro | Graphite, ivory and cool daylight; paper and planar surfaces | Architectural light with one pale work surface | Usually no motion | Decorative overload, false “premium” gloss |
| Sci-Fi Noir | Blue-grey, oxidized steel, amber instrument light | Observatory workshop framing a remote orbital horizon | Slow distant light/cloud drift | Familiar fictional spacecraft, simulated operational gauges |

A theme should remain recognizable from a tiny crop and its materials, not only from hue. All six use the same real component spacing, control shapes, typography roles and semantic status rules. Do not recolor errors into low-contrast theme accents or make a model family part of a skin.

## Composition contract

Create the master with a low-detail middle-left area and interest predominantly at the right edge. Keep a normalized focal-point note with the approved master. Prepare 16:9, wide-header, square-card and narrow-screen crops deliberately. A 16:9 master is not automatically a usable phone crop. Extend or author an alternate composition only after checking the actual slot geometry.

Keep artwork text-free. Typography, labels, badges and interface status are editable HTML or design-tool layers, not pixels produced by an image model. Do not draw a button that users will try to click. Ambient screens use nonsemantic shapes, not invented VRAM values, timers or “ready” lamps.

Parallax requires a single camera and scene registration. Derive the far architecture, mid-ground desk/cabinets and sparse near-frame layer from one approved scene. Reconstruct occluded areas before separating layers. Keep alpha premultiplication clean and test all offset extremes. Missing hidden pixels cannot be repaired by merely making the original image transparent.

## Illustration families

**Workflow vignettes:** the guide acting out the operation in the direction's own room and props, not a fake example of
success and not an empty object. The action is the explanation: a first stroke on a blank sheet for Create, three pictures
pinned around one blank canvas for Combine, a receipt tucked safely into a satchel for Recover. Keep one room, one prop set
and one line language across all sixteen. Identity and geometry still appear as distinct sources. Compare cards stay
equally prominent rather than declaring a winner. A repair illustration cannot stand in for a functioning mask editor.

**Reference examples:** identity and outfit come from the guide's approved canon; the pose, style, composition, lighting and
background examples stay character-free so each teaches one role. Keep the pose example's geometry independently readable.
Store the role caption outside the image. A nice example is not a measured route benchmark.

**Helper states:** friendly empty states (first run, an empty library) are pictures of the guide inviting you to fill the
room (owner answer, 27 September 2026). Error and recovery states stay themeable SVG with meaningful HTML alongside; the
guide may appear there only as a small vector sticker. Distinguish absent internet, inaccessible Studio, unavailable backend
and failed optional media. Uncertain execution uses a retained-receipt motif, not a retry arrow. Conflict shows two equal
candidates. Completion has no artistic-approval stars.

**The guide:** an original adult character (or, in Night Shift '89, a human lead plus a small nonhuman helper) with a
written bible, a palette and a canon sheet. The guide has personality and expressions, but never sits over controls, never
bounces for attention and never replaces an explanation. No franchise look-alikes; every character is an adult; SFW only.

## Texture and motion restraint

Grain, paper and CRT-inspired edges are optional. Use them at the decorative boundary, not across prompt text or preview pixels the user is assessing. Avoid shimmer that resembles rendering progress. Never scroll the page to show the artwork. Support “Hide environment” independently of theme and assistance mode.

For the editor, Still is a complete design. Subtle adds one small motion window. Cinematic is reserved for explicitly chosen larger environments or a separate showcase. Do not install a timeline library to animate ordinary disclosure; see AMBIENCE for proposed timing/resource budgets.

## Canon sheet to approve before derivatives

Record the scene ID, camera height/lens impression, vanishing point, principal objects, material palette, light direction, text-safe rectangles, focal point and forbidden motifs. Retain one approved anchor file and its checksum. Subsequent briefs reference that actual file, not just the seed or a prose description. When a tool cannot preserve a needed feature, report the gap and use a simpler derivative, rather than asserting continuity.

The first review is a small contact sheet of actual candidates in a future session. Judge composition, legibility, originality, consistency, crop viability and distraction. Artistic acceptance belongs to Chris. This document contains no accepted artwork and grants no source rights.

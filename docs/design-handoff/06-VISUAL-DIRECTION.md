# 06 · Visual direction

Sources: `docs/adaptive-studio/assets/ART-DIRECTION.md`, `docs/adaptive-studio/AMBIENCE.md`,
`docs/adaptive-studio/UX-SPEC.md` §7, `docs/workshop/DESIGN.md`, and the shipped CSS. Token values below are
**Proposals** unless labelled "today".

## Tone

A personal animation workshop at night, not a settings form with wallpaper. Quiet, dark, precise; the output image is
the brightest thing on the screen. Copy is short and plain: *what happened · what remains · next action*. No
marketing slogans in working screens (today: "Pick up the thread.", "Follow the idea.", "A library, not a dead end.",
"Run with a question. Leave with a decision." — keep at most one per product, on Home).

Reference feel: a professional creative tool (dense, calm, keyboard-friendly) with a small amount of anime-workshop
atmosphere at the edges. Not: gaming RGB, neon borders everywhere, glassmorphism over text, mascots on controls.

## Today (for contrast)

| Aspect | Today |
| --- | --- |
| Base | Dark; `style.css` bg `#101216`, panel `#191c22`, accent lime `#c6f48a`; `studio.css` bg `#111718`, accent `#cbef97` |
| Other palettes | Review desk `#10141c`/teal `#86dfcf`; Spoken Briefs `#11151b`/`#95d6c5`; Workflow Studio `#10141b`/`#c6f48a`; Prompt Lab inline `#111719`/`#c1ddc7`; Create skins: Atelier peach, Arcade cyan, Sakura pink, Retro Anime magenta |
| Type | `'Segoe UI', system-ui, sans-serif` 14px/1.5; monospace `ui-monospace, Consolas` for codes and some eyebrows |
| Shape | 8-14 px radii, 1 px borders `#343a43`-ish, filled accent primary buttons, outlined secondary |
| Density | Generous in heroes, cramped in toolbars; many equal-weight buttons |
| Motion | Minimal; reduced motion honoured; ambience still by default |

## The six skins (worlds)

Skins are **token overrides over one component system**: same spacing, shapes, typography roles and status semantics.
Shipped today: Atelier (default), Arcade, Sakura, Retro Anime, applied to Create only. Proposed in ART-DIRECTION: also
Minimal Pro and Sci-Fi Noir, and skins applied app-wide.

| Skin | Palette / materials | Environment composition (decorative slot only) | Motion candidate | Avoid |
| --- | --- | --- | --- | --- |
| **Atelier** (default) | Charcoal, cream, walnut, amber; linen, paper, brushed metal | Drafting desk at right, open courtyard beyond | Soft curtain or light shift | Corporate office, product-photo gloss, cluttered desk |
| **Arcade** | Indigo, muted violet, cyan; lacquer, original cabinet silhouettes | Cabinets framing a distant abstract horizon | One slow reflection or horizon pulse | Recognisable games, readable screens, saturated borders |
| **Sakura** | Plum, dusty rose, warm ink timber; botanical accents | Quiet interior opening onto a blossom courtyard | Sparse petals beyond the window only | Pink fog, petals over text, stock mascots |
| **Retro Anime** (recommended pilot "Night Shift") | Graphite, desaturated rose/cyan, small amber; cel-like paint, rain | Late-night loft, rail line, CRT pool of light, text-safe wall; daylight twin "Quiet Morning" | Rain, one distant train, slight reflection | Franchise imitation, dramatic camera, faces behind the prompt |
| **Minimal Pro** | Graphite, ivory, cool daylight; paper, planar surfaces | Architectural light on one pale work surface | Usually none | Decorative overload, false premium gloss |
| **Sci-Fi Noir** | Blue-grey, oxidised steel, amber instrument light | Observatory workshop framing a remote orbital horizon | Slow distant light/cloud drift | Known spacecraft, fake operational gauges |

Rules that bind every skin: art is text-free and never looks clickable; status, labels and progress are HTML; errors
keep their semantic colour in every skin; a skin is recognisable from materials, not hue alone; "Hide environment" is
independent of skin; the owner asked on 27 Sep 2026 for the asset wishlist to be reviewed, planned and executed
(superseding the 23 Sep "defer artwork" answer; PR #1084), but the pilot world and every piece's acceptance are still open, so
designs must work with **empty art slots and token-only fallbacks** and may show neutral placeholder rectangles.

## Tokens to define (deliverable)

| Group | Tokens | Constraints |
| --- | --- | --- |
| Colour — surfaces | `bg`, `surface-1..3`, `overlay`, `line`, `line-strong` | Output previews sit on a neutral surface (no tinted backgrounds under images being judged) |
| Colour — text | `text`, `text-muted`, `text-faint`, `text-on-accent` | `text-muted` ≥ 4.5:1 on `surface-2` |
| Colour — accent | `accent`, `accent-hover`, `accent-subtle`, `focus-ring` | Accent is per skin; focus ring ≥ 3:1 against adjacent colours |
| Colour — semantic (fixed across skins) | `status-running`, `status-success`, `status-warning`, `status-error`, `status-unknown` (uncertain), `status-neutral`, `status-muted` (put away) | `status-unknown` must not read as error or success; pair every status with an icon/shape |
| Colour — review | `review-keeper`, `review-needs-work`, `review-rejected`, `review-unreviewed` | Distinct from job status colours |
| Type | `font-ui` (system stack: Segoe UI Variable / Segoe UI, system-ui), `font-mono` (Cascadia Code / Consolas), scale 12/13/14/16/20/24/32, weights 400/600, line-heights 1.3/1.5 | **No web fonts** (offline; no download). A bundled local font file is possible only if added to the repo |
| Space | 4-px grid: 4, 8, 12, 16, 24, 32, 48 | Toolbars ≥ 8 px gaps |
| Radius | 4 (inputs), 8 (cards), 12 (dialogs), 999 (chips) | Same in all skins |
| Elevation | 0 (flat), 1 (cards), 2 (popover), 3 (dialog), dock | Dock shadow must separate it from content it overlaps |
| Motion | `fast` 120-180 ms (control feedback), `panel` 160-220 ms (disclosure), `scene` ≤ 300 ms crossfade; ease-out | All ≈ 0 under reduced motion; no motion that resembles progress |
| Density | `comfortable` and `compact` (grid gaps, row heights, control sizes) | Library and Runs default compact; Make comfortable |
| Layout | sidebar 224 / collapsed 64 / mobile 0; top bar 56-64; dock height; breakpoints 390, 768, 1024, 1440, 1920 | No horizontal overflow at 390 |

## Accessibility (binding)

- WCAG 2.2 AA: text contrast 4.5:1 (3:1 large), non-text 3:1, visible focus on every control, target size ≥ 24×24 px.
- Status never by colour alone: icon + text + shape; test in monochrome.
- Forced colours (Windows High Contrast): use system colours, keep borders, hide decorative art.
- `prefers-reduced-motion`: no parallax, no loops, instant state changes; also pause ambience during any active or
  unknown job, when the tab is hidden, and under Save-Data.
- Native semantics: `button`, `label`, `dialog` with focus trap and Esc + focus restoration; `aria-describedby` for
  disabled reasons; live regions announce meaningful changes only (not every poll).
- 200 % zoom and 390×844 without loss of function; the run dock must not hide the focused field.
- Keyboard: every flow in 04 completable without a mouse; shortcut letters never fire inside text fields.
- Decorative art `alt=""`/`aria-hidden`; illustrative examples get real captions outside the image.

## Imagery in designs

Use neutral, original placeholder art (props, landscapes, abstract studies like the repository's lantern, forest and
chest examples in the screenshots). Characters, if any, must be clearly adult, fully clothed and original. Do not use
franchise characters, real people or any content from the owner's private library.

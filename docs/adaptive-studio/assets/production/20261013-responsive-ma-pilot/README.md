# Night Shift MA responsive delivery pilot

Source-only pilot; no app/catalog/runtime activation, generation, GPU job, new art, acceptance change or deferral change. The portable payload is review-only. Screenshots remain internal pixel QA.

Usable review payload: **review.html** and **night-shift-ma-responsive-1024.webp**, kept together in one directory. The page embeds the shipped hero styles and mirrors the hero markup from `app/static/workshop.js`; explicit pilot overrides place the complete 16:9 image above an opaque `#11171f` copy block at widths ≤600 px. Desktop retains the shipped shallow center-cover composition and gradient. All copy is selectable HTML, with a labelled section and decorative art excluded from accessibility. The page has no executable script, audio, video, form or generation endpoint. Its CSP rejects network connections and restricts assets to local/self data.

One rendition was created, without crops or scene reauthoring. Approved full master remains the source:

- Source RGB PNG: 3840×2160, 2,736,794 bytes; SHA256 before and after `a8faacc8d7d643eb68a6916571af6d35f78533d0c7d97f9379ec1b43276fd414`.
- Separate RGB WebP: 1024×576, **26,460 bytes** (25.84 KiB), SHA256 `156df8bb9178be20691f5a6d0686a32d9be67daad61f84252119a15ccd489192`.
- Recipe: Pillow `Image.resize((1024,576), Image.Resampling.LANCZOS)` → `save(format='WEBP', quality=85, method=6, lossless=False)`. Pillow 12.2.0 / libwebp 1.6.0. No input ICC profile was present; no EXIF/xattrs were copied or repaired. Source Library metadata failure remains a separate historical record.
- Poster budget stays **300 KiB**. The derivative uses 8.61% of that budget. Review HTML is 62,435 bytes, making the entire two-file first screen 88,895 bytes, below the proposed 350 KiB profile. Nominal RGBA decode for the rendition is 2,359,296 bytes (2.25 MiB); the file itself is RGB, and actual Radeon/VRAM usage was not measured.

## Fresh qualification

Both commands ran from `C:\Users\Cristian3\Documents\Codex\2026-10-12\task\las`, using absolute `C:\Program Files\Python313\python.exe`, `-B`, `PYTHONDONTWRITEBYTECODE=1` and TEMP/TMP set to this directory's `tmp`. Scoped interpreter/browser escalation was used; no installation occurred.

```powershell
& 'C:\Program Files\Python313\python.exe' -B '..\evidence\las-accepted-qa\responsive-pilot\build_pilot.py'
& 'C:\Program Files\Python313\python.exe' -B '..\evidence\las-accepted-qa\responsive-pilot\qualify_pilot.py'
```

Build exit 0; qualification exit 0, **96 passing checks**, Chromium 151.0.7922.34. Actual native viewport tests: 320×900, 390×844, 430×932 and 1536×1060, DPR 1. Natural browser decode was 1024×576. Exactly one 26,460-byte derivative was delivered per fresh context, four total; delivery hashes match the file.

Fit, original 16:9 reserved phone geometry, image/copy separation, selectable independent copy, semantic heading association, no horizontal overflow, static reduced-motion state and forced-color decoration suppression all passed. Zero page errors, POSTs, automatic commands or requests to other origins. This is a static review fixture, not installed-app/backend verification.

Full-text-box conservative contrast from actual hidden-child browser screenshots:

| Native width | Eyebrow | Title | Body | Status |
|---|---:|---:|---:|---:|
| 320 | 11.114:1 | 15.702:1 | 8.535:1 | 9.222:1 |
| 390 | 11.114:1 | 15.702:1 | 8.535:1 | 9.222:1 |
| 430 | 11.114:1 | 15.702:1 | 8.535:1 | 9.222:1 |
| 1536 | 11.946:1 | 14.634:1 | 8.159:1 | 8.833:1 |

These compare computed foreground with the least favourable pixel anywhere beneath each complete text block. Phone backing remains opaque while its child text is hidden. This is more conservative than sampling selected glyph pixels, but it is not a whole-page accessibility audit. The previous MA override's phone-description samples were 1.208:1 at 430 and 1.051:1 at 320; the approved opaque-backing pilot addresses that placement failure without changing accepted pixels.

Opened and visually inspected the WebP; all four `pixel-qa-hero-*.png` files; and `pixel-qa-forced-colors-390.png`. The image retains the quiet wall and complete train/window/desk/lamp/CRT/chair composition on phones; copy is clear below it. Desktop copy remains on the quiet side, but the source's shallow hero still crops vertically. That desktop placement is a presentation choice, not an authored crop or change to source objects.

`rendition-receipt.json` records the complete recipe, before/after master hash, derivative hash and source style/markup hashes. `qualification-report.json` records each assertion, geometry, contrast and actual transfers. Logs retain exact run outcomes. `closeout.json` confirms owned loopback port **55495** has zero listeners; its serving thread joined and all browser contexts closed. No unrelated service was stopped.

Remaining: installed-runtime integration/performance/native-media qualification. Independent artifact review found no blocking correctness or security issue; root also checks the copied portable payload. Current original acceptances and all 44 deferrals remain unchanged. No artistic reacceptance or source-metadata repair is inferred.

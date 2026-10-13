# Optional Night Shift Look visual reference

The unchanged shipped Night Shift Look offers a folded **Preview Night Shift reference** disclosure. Selecting a Look loads no picture. Explicitly opening the disclosure requests the separately named 1024x576 WebP (26,460 bytes), preserves the complete frame, and displays selectable copy below it on opaque `#11171f`. There is no animation, generation, automatic wallpaper activation or picture input.

The MA reference is separate from the Look's accepted Z2 anchor. Neither `presets/looks.json` nor its wording, controls, lineage, saved revision or owner acceptances changes. Display metadata is added only to the listing response for the exact unchanged shipped card content. Edited/custom cards and put-away cards receive no reference. Preparing still composes the owner's scene and saved wording, without receiving preview metadata.

The production static handler admits this one resolved app-owned WebP path with explicit `image/webp`; it does not admit an entire image directory or change Host/security settings. Missing/decode-failed images produce meaningful text while preparation remains available. Forced colors avoids the optional image request and retains text; reduced motion is inherently static. No new dependency, prefetch, precache or budget increase.

## Evidence

- Implementation checkpoint `7e970293076c2ab5a213d76974cadd4d2cc2d197` passed 65 actual Chromium assertions at 320x900, 390x844, 430x932 and 1536x1060, DPR 1. The browser used production static serving and production Look listing/preparation with a disposable SQLite Workspace. Other API data was inert; no models or user database were touched. Test-local Host handling adapts to its own random loopback port; production remains pinned to 8191.
- Each fresh context requested no optional art at startup or Look selection, then one 26,460-byte image on explicit open. Actual HTTP status, MIME, bytes and SHA-256 were checked. Opening preserved the captured draft; four explicit prepare actions preserved original card content/revision and produced scene wording. Existing estimate requests remained read-only; no job/generation mutation occurred.
- Actual preview and full application-context PNGs exist for all four viewport sizes, plus forced-color and unavailable-picture phone captures. Preview captures are native element screenshots after normal page scrolling keeps copy above the existing dock; context captures are full-page screenshots, not viewport crops. All four preview captures were opened and inspected. Their viewport provenance and hashes are in the portable evidence archive; no artistic reacceptance is inferred.
- Independent read-only review caught the initial production 404 masked by permissive fixture static serving. The causal handler test failed `404 != 200` before the narrow repair, then passed exact delivery, peer-image/traversal controls and unchanged Host behavior. The revised browser harness uses production static serving. A second review found no remaining causal blocker.
- Eight Python preview/production-route contracts include a real existing unintended WebP and wrong-Host rejection. Existing 15 frontend handoff /5 static-island contracts, 13 plus 12 Node Look checks, both existing Look browser suites and all 20 application use cases passed. No generation occurred in those browser gates.
- Natural-entry, maximum-scroll and real keyboard tests are part of the reproducible browser gate. The caption can initially extend behind the fixed dock at 320/390; keyboard PageDown makes it readable. Tab reaches Prepare/Put away above the dock, also when starting at maximum scroll. The final visible Create control clears the dock at maximum scroll. Existing measured bottom padding and scroll margins provide clearance; no screenshot-selected position is treated as a layout fix. Natural-entry, maximum-scroll and keyboard PNGs are included alongside separate art-inspection crops.
- The unchanged 600-second full lifetime gate at source `3aa41f21` timed out after 600.05 seconds while progressing through existing parallax tests. No assertion failure was reported before the timeout; all six original new preview tests had passed. This is incomplete verification, not a green full suite. Final-head hosted full verification remains required; the guard and runtime caps were not expanded.

Run the reproducible application check with the installed Playwright/Chromium:

```powershell
python tests/looks_visual_reference_browser.py --output <owned-evidence-directory>
```

Still unverified: installed runtime/model work, Radeon memory/performance, physical Android/TalkBack and whole-application accessibility. Existing licensing/art judgments and HUMAN_TODO decisions remain open. All 44 deferrals, experimental SVG studies and combined Alibi budget checkpoint are unchanged. No merge or deployment.

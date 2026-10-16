**Published source pack:** [GitHub delivery](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5957214710). Archive downloaded back and verified. Binary originals and review images remain in the attached archive.

# Local Asset Studio foundation source kit

Source design candidates for nine foundation rows (tokens, buttons, fields, cards, tabs, badges, dialogs, patterns and skeletons), five motion-contract rows, and the editable README-cover row. The icon family is delivered separately in the vector-foundation pack.

Open components.html beside foundations.css to inspect the native HTML specimens. They use public synthetic text and no JavaScript. Buttons are visual examples and do not submit jobs or alter Studio state. The dialog is deliberately a static section: native modal focus containment, Escape, focus restoration and production keyboard flows are not implemented or claimed. The tab-style buttons do not pretend to implement ARIA tab keyboard behaviour.

tokens.json is the source of the CSS proposal. Six skins override at most seven appearance tokens each. Execution and review colours are fixed across skins and remain distinct concepts. All normal/muted/faint/status/review text colours pass 4.5:1 against the four specified solid surfaces; the supplied contrast table contains the actual calculations. Accent-button text passes 4.5:1, meaningful control boundaries 3:1, and the dual focus-ring parts have checked contrast against their respective adjacent surfaces. This is mathematical specimen contrast, not certification of the whole app.

The component sheet uses a system font stack, 4-pixel spacing, consistent radii, compact/comfortable density and wrapping grids. There are no CDN resources, web fonts, private images or automatic commands. Reduced-motion and forced-colour CSS are included, but browser application at 390px, 200% zoom, OS high contrast and keyboard interactions remains unverified. The cloud browser did not allow the local preview address, so no browser pass is claimed. The static token/contact artwork is a design illustration, not a screenshot of the implemented Studio.

motion-policy.mjs is a pure, conservative integration reference. Run node --test test-contracts.mjs for its tests and token checks. It has no scheduling, DOM, playback or network side effects. See MOTION-SPEC.md for the required future lifecycle integration and unresolved browser scenarios.

promo-readme.svg keeps its text editable and says only "Local creative workspace" and "Source design study". It makes no performance, model or implemented-feature claims. Other promotions remain deferred.

All source candidates were selected under the owner's delegated design/art judgment. This does not imply runtime qualification, release selection or permission to merge or deploy. Nothing here is imported by app runtime.

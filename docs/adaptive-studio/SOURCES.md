# Source register

Reviewed 18 September 2026. External facts below are intentionally narrow; product design, budgets and migration choices elsewhere are proposals, not claims made by these sources.

## User and repository material

**U01.** Supplied *LAS Create UX wishlist - workshop redesign (2026-09-17)*, 12 pages. Pages 3-4: observed density and scroll problems. Page 5: workbench-first diagram and route/surface split. Pages 6-9: section detail and disclosure defaults. Pages 10-11: experiments and v1 acceptance. The PDF is not copied into the repository; EVIDENCE preserves the relevant framing and distinguishes the current expansion.

**R01.** [Repository guidance](https://github.com/Chris0Jeky/local-asset-studio/blob/eb3fc1e1665f109d90086ad3b3dbe1f5f10dd14b/CLAUDE.md), [workbench](https://github.com/Chris0Jeky/local-asset-studio/blob/eb3fc1e1665f109d90086ad3b3dbe1f5f10dd14b/app/static/studio-workbench.js), [shell](https://github.com/Chris0Jeky/local-asset-studio/blob/eb3fc1e1665f109d90086ad3b3dbe1f5f10dd14b/app/static/studio-shell.js), and the existing UX-WORKFLOWS / UX-USE-CASE-MATRIX / UX-AUDIT-2026-09-14 documents. Scope and source-archive reconciliation are recorded in EVIDENCE.

**R02.** [Focus PR #540](https://github.com/Chris0Jeky/local-asset-studio/pull/540), [Studio PR #541](https://github.com/Chris0Jeky/local-asset-studio/pull/541), [qualification #539](https://github.com/Chris0Jeky/local-asset-studio/issues/539). Open at inspection; no merge/CI approval is inferred.

## Public primary sources

| ID | Source | Supported fact / relevance |
| --- | --- | --- |
| S01 | [ByteDance Seedance 2.0](https://seed.bytedance.com/en/seedance2_0) | The page organizes audiovisual capability descriptions and a curated showcase. Its model-performance claims are not evidence about LAS. Only page text/structure was available; parallax or implementation technology was not verified. |
| S02 | [Vue: ways of using Vue](https://vuejs.org/guide/extras/ways-of-using-vue.html) | Vue documents incremental adoption, standalone use and embedded components. This supports evaluating islands, not a mandatory rewrite. |
| S03 | [Vite: backend integration](https://vite.dev/guide/backend-integration) | Vite documents manifest-based integration with an existing backend and hashed build outputs. LAS-specific packaging/security still needs implementation. |
| S04 | [React: add to an existing project](https://react.dev/learn/add-react-to-an-existing-project) | React can be embedded into selected roots rather than replacing an entire app. |
| S05 | [Lit documentation](https://lit.dev/docs/) | Lit is based on web components with reactive properties and scoped composition; it is an alternative component strategy. |
| S06 | [TypeScript: checking JavaScript](https://www.typescriptlang.org/docs/handbook/type-checking-javascript-files.html) | JavaScript can gain type checking without converting every file immediately. |
| S07 | [MDN: navigator.onLine](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/onLine) | Connectivity heuristics are unreliable as proof that a particular service is reachable. |
| S08 | [W3C: Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) | Users need control over qualifying moving/auto-updating content alongside other content. |
| S09 | [MDN: prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion) | The media query exposes a motion-reduction preference. |
| S10 | [MDN: Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API) | Page visibility can be observed to avoid unnecessary hidden-page media work. |
| S11 | [MDN: media autoplay](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay) | Autoplay is conditional and playback can be rejected; the UI needs a non-playing fallback. |

## Research limits

No third-party site code or media was copied. No media rights, exact framework-version pairing, Windows frontend build or actual inference performance was qualified by this reading. Tool/provider names in future acquisition prompts are routing preferences; the next session must discover the available tool and record the actual model/version rather than treating a conversational label as an API identifier.

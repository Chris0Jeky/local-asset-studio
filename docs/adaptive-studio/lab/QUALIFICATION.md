# Behavior lab qualification

18 September 2026. This evidence concerns the isolated documentation prototype only.

## Completed checks

- Initial regression checkpoint: policy tests failed because `index.html` and its policy implementation did not exist.
- `node --test docs/adaptive-studio/lab/policy.test.cjs`: **15 tests passed** against the exact inline browser policy.
- `python docs/adaptive-studio/lab/browser_test.py --injected --output <report>`: **11 browser check groups passed**, zero page exceptions, zero HTTP/HTTPS/WebSocket requests, zero screenshot/media creation.
- Browser matrix included **36 combinations** of 3 layouts, 6 skins and 2 viewports (1440x900, 390x844), plus 200% zoom.
- The brief's DOM identity and value remain unchanged through the matrix. The review action remains in the viewport with no horizontal page overflow.
- Native dialog cancellation and successful synthetic recipe change restore the intended focus.
- Missing sources and excess sources remain distinct. Expert retains uncertainty/conflict guidance, including a simultaneous uncertain operation and cross-tab conflict. That combined case failed in both the policy and browser tests before the review fix.
- Internet hint, local API/backend and media permission/fallback behavior are independently exercised.
- OS reduced-motion changes are observed live; user pause, economy, visibility and active operation override motion eligibility.
- An A-B-A skin change rejects the late simulated result. This is a local timer/state test, not a provider/network test.

## Environment findings

Native `file:` navigation was attempted and refused by the execution environment with `ERR_BLOCKED_BY_ADMINISTRATOR`. The successful run uses the explicit `--injected` mode, loading the complete unchanged HTML into a browser document. It does not substitute for testing native local-file opening on the owner's browser.

Playwright's string-based function polling encountered the page's no-eval content-security policy. Tests were changed to locator assertions; the page policy was not weakened. Network/media denial remains part of the prototype.

## What is not proved

No production adapter, framework island, actual model workflow, private draft persistence, browser service worker, video decoder, parallax asset, GPU performance or native file-origin behavior was qualified. The lab does not implement a media loader or play a loop; it models the policy and uses labelled empty slots. No rendered screenshot or image-generation output is supplied in this pass.

The 16-workflow document remains broader than the five representative interactive lenses. The architecture and budgets remain proposed. Real-machine workshop qualification stays under #539 and the existing owner decisions remain untouched.

## Reproduce and extend

Use the commands in README. A future production implementation should add adapter-level tests using the repository's existing real-frontend fixtures, then native-origin and actual-workflow checks. Keep policy tests, document interaction tests, domain integration, actual execution and owner usability acceptance separate in reports. Do not turn these 11 passing groups into a claim that the redesigned Studio is shipped or universally accessible.

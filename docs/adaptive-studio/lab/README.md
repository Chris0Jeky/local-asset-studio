# Adaptive behavior lab

Open [index.html](index.html) in a browser, or download the file and open it locally. It is a single self-contained HTML document with no external files, fonts, images, video, audio, model calls or storage dependency. The production shell does not import it.

This is an **executable interaction specification**, not an alternate working Studio. All recipe capacities, source counts, connection states and operation IDs are clearly synthetic. The lab cannot generate, install, stage files, save a real draft or recover a real job. The user's editable sample brief lasts only for this tab/document.

## What to try

### 1. A task lens is not a recipe change

Type a brief, choose Pose transfer, and notice that the current recipe remains the text-only example. The guide proposes a compatible input shape. Open the difference review and press Escape; the recipe stays unchanged and focus returns to the launcher. Open it again and deliberately apply the proposed example. The brief remains intact and focus returns to it. The next action now identifies the required sources.

### 2. Required sources versus unsupported extras

Use the next-action button to reveal the synthetic source-count field. Choose one source for the two-reference pose example, then four. Missing sources and overflow produce different guidance. The extra sources remain visible in the count; nothing is truncated to fit a route. Return to two to reach the plan-review step. These capacities are examples, not statements about the actual installed models.

### 3. Recovery outranks creative suggestions

In Scenario controls choose Uncertain outcome. Switch assistance to Expert. The original-request instruction remains visible. Review the synthetic receipt: it identifies `demo-request-17`, provides no replay action and does not offer a recipe application. A conflicting-draft scenario is also visible in Expert. Switching to the Recover lens with no retained operation does not invent one.

### 4. Separate connectivity from decoration

Turn off the internet hint while keeping the local API/backend observations available. Plan review remains possible in the model. Under Environment, request Subtle or Cinematic with an approved local loop: the policy permits local motion even without internet. Then make the backend unavailable: workflow guidance changes, independently of the internet hint.

A remote loop requires explicit permission and a local poster fallback. Optional-media failure does not change workflow readiness. Economy, user pause, hidden state, active/uncertain execution and OS reduced motion take precedence over decorative motion. The lab displays these decisions as text; it plays no loop and loads no image.

### 5. Reject a late asset result

Choose Atelier, simulate a delayed asset result, and change to Sakura then back to Atelier before it settles. The old result is rejected despite returning to the same skin name. An epoch, not just a name comparison, distinguishes the new context. This uses a local timer only; it makes no request and does not create media.

## Layout and guidance choices

Five representative lenses exercise the design's important transitions: Create, Reference mix, Pose transfer, Compare and Recover. The complete 16-workflow atlas remains in [UX-SPEC.md](../UX-SPEC.md). Guided/Studio/Expert changes explanation and technical disclosure, not authority. Focus/Studio/Bench changes layout without replacing the textarea. Six skins use CSS variables only. Asset slots show stable IDs from the [production kit](../assets/README.md).

The scenario controls are deliberately collapsed away from the main workbench. They are test apparatus, not a proposal to expose another wall of synthetic toggles to production users. Production observations would come through the read-only boundary in [ARCHITECTURE.md](../ARCHITECTURE.md).

## Tests

```sh
node --test docs/adaptive-studio/lab/policy.test.cjs
python docs/adaptive-studio/lab/browser_test.py --output .runtime/adaptive-lab/report.json
```

The Python test requires the repository's documented Playwright/Chromium setup. Its default uses native `file:` navigation. In a constrained browser environment that refuses local navigation, the explicit alternative injects the exact HTML:

```sh
python docs/adaptive-studio/lab/browser_test.py --injected --output .runtime/adaptive-lab/report.json
```

That alternative is document-level browser evidence, **not native-file-origin qualification**. No screenshots are made in either mode. See [QUALIFICATION.md](QUALIFICATION.md) for the actual run's evidence and limitations.

## Implementation boundary

Do not copy the lab's synthetic state into production as a second store. Its pure projection rules are an executable starting specification; production must validate actual domain snapshots and preserve the existing command/draft owners. The HTML uses a restrictive content-security policy that denies network and media access. The tests exercise the inline policy actually used by the browser, not a separately maintained mock implementation.

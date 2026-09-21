# A small paired usability trial

Source: the owner-supplied 17 September Create wishlist, sections 7 and 8. This is a trial protocol, not an analytics feature. Nothing is transmitted and no experiment assignment changes the user's settings automatically.

## Compare the interaction before judging the colour

Use the same machine, installed model environment, recipe, source images and screen size. Compare the old baseline with Focus first. Then compare Focus with Studio while keeping the same skin. Only then compare Atelier, Arcade and Sakura. Alternate presentation order between sessions so prior familiarity does not automatically favour the second option.

Try three tasks: generate from a fresh written brief; refine from a reference; and continue an existing result with changed sampling/adapter settings. Save any draft before switching branches. Inspect readiness before every real run. Do not mix a cold model load in one condition with a warm model in another when comparing runtime.

| Record per trial | How |
| --- | --- |
| Time to first intentional Generate | Page-ready to button click; record separately from generation runtime |
| Scroll before that click | Approximate maximum vertical distance and whether Generate was ever hard to locate |
| Tuning opened | Yes/no; also record whether the desired model/adapter control was found |
| Recipe replacement | Cancelled or accepted; verify the prompt/source did not disappear on cancel |
| Continue/save outcome | Was the result continued or saved? Do not substitute this for art-quality assessment |
| Impression | Calm/cluttered plus one sentence explaining the friction |

For more than a handful of sessions, report median and p75 time-to-click separately for new and returning users. Do not claim a statistically meaningful winner from a few personal trials. Prefer the layout that reduces hunting without hiding important blockers or making repeated work slower.

## Owner acceptance on the real machine

At 1440×900: recipe, prompt and Generate visible in the first viewport; default Create document <1600 px for the chosen representative state. At 390×844: no horizontal page overflow; Generate remains reachable. Verify native picker focus/Escape, cancelled recipe replacement, real per-recipe draft restore after reload, reference and parent-asset identity across all six presentation combinations, and one intentional generation through the current ComfyUI path.

Run one prompt-only and one reference-dependent recipe. Preserve evidence of a disabled-button reason as well as success. Confirm actual output provenance/Continue and saved-setup behaviour. A synthetic API test cannot close these checks.

## Deferred wishlist items

Recipe favourites/recent ranking, full list virtualization, deeper dedicated model/adapter search, a first-run guided wizard, and optional local timing instrumentation are not implemented here. The existing model route and recipe/adapter handlers remain available. Do not infer completion from the new skin selector or the standalone demo. Prioritise any remaining item only after the first trial identifies a concrete bottleneck.

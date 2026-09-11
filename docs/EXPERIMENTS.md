# Five useful first experiments

## 1. Learn a LoRA with a controlled comparison

Open **Pixel art • baseline**, keep its prompt and seed, and generate. Then open **Pixel art • 128px prop**, preserve that same prompt/seed, and generate. Compare silhouette, pixel clusters, background cleanup, and readability at actual game size.

Next vary only LoRA strength: 0.5, 0.8, 1.0. Keep the other settings constant. Select the result you would actually use, not the most detailed full-size image. Record cleanup minutes. The earlier LoRA sample looked more suitable than the baseline but still needed background/palette work.

## 2. Explore a product art direction

Use **Product • studio photograph** with an invented product such as a teal lantern. Keep the subject constant across three seeds. Then change lighting only: soft daylight, dark studio rim light, warm tabletop. Save a named recipe for the chosen direction.

For real product promotion, compare shape, controls, labels, materials, and dimensions to the actual product. A plausible invented object is not a faithful product photograph.

## 3. Design a background that leaves room for text

Try **Website • abstract ribbons**. Ask for a quiet left third and activity on the right. Compare two seeds at the same aspect ratio. Place the real heading over each result in your website or design tool; reject attractive images that interfere with legibility.

Avoid asking the model to deliver the entire finished layout. Keep final typography, button geometry, and responsive cropping deterministic.

## 4. Compare edit fidelity

Use the same lantern reference in **FLUX Klein edit**, **SDXL gentle variation**, and **Qwen instructed edit**. Request one colour change. Score whether the change happened, whether protected details drifted, and how much cleanup is needed. Keep Qwen jobs together because switching from Qwen to SDXL previously crashed the backend once.

For a guarantee that pixels outside a mask stay unchanged, use `scripts/assets.py composite` after generation. See `examples/lanternkeeper/edit-*` for original, mask, and composite. A generative prompt alone cannot provide that guarantee.

## 5. Build a usable animation pack

Open `examples/lanternkeeper/lanternkeeper.blend` in Blender. The example already includes three skins, eight directions and four bob phases. Preview the game through `scripts/Open-Lanternkeeper.ps1`. Change one material, render a new set, then run the packer in a copied experiment directory.

For character walk cycles, create and approve key poses first; align pivot/baseline/canvas before adding in-betweens. The earlier character sheet extractions and Qwen pose attempt did not produce a complete faithful walk. Blender rigs or hand-authored pixel animation remain useful for stable motion.

## Keep a useful record

Each selected experiment should have a short `README.md`, exported recipe, two to four small images, model/LoRA names and revisions, what changed, timing, and your judgement. Use `experiments/curated/scorecard-template.csv` as a starting point. Put it in a new folder, for example `experiments/curated/2026-09-compass-pixel/`.

Separate three kinds of evidence: **the graph ran**, **the picture met the brief**, and **the exported asset worked in the product**. A workflow can pass the first and fail the other two.

For a fair model comparison use the same brief and evaluation questions, but allow each model its documented prompt/sampler defaults. Run several seeds before ranking a model. For parameter comparisons within a model, change one factor at a time.

For the longer strategy, see [the evaluation research guide](research/Experimenting-and-Evaluating-Models.md).

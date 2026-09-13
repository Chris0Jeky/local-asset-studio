# Fantasy character illustration pack

Selected by the owner on 12 September 2026. The immediate visual direction is the resource stack in the owner's screenshot. The owner subsequently supplied [image 134076830](https://civitai.red/images/134076830) for technical metadata analysis. The baseline guide records the settings that could be recovered; this brief uses an original clothed character rather than asserting exact reproduction of the source artwork.

## First useful deliverable

Develop a reusable baseline for an original adult fantasy character, then a small matching illustration set. Start with a fully clothed character so costume, face, hands and lighting are easy to assess. A lantern keeper or cartographer with a navy coat, brass details and teal accents is an editable starting subject, not an owner-approved character design.

1. One portrait or three-quarter illustration to establish the look.
2. One full-body image to establish clothing and silhouette.
3. One expression variation that retains the design.
4. One documented local correction of a visible defect, preserving the original.

Start with one image at a time, a fixed seed and a modest canvas. Record the exact graph, model hashes, prompt ID and output path. Keep enlargement and multi-model correction out of the first baseline; add them only when a useful result justifies the extra cost.

## Workflow decisions

The screenshot lists two model families. WAI-Illustrious-SDXL and its compatible Noirpopwave LoRA form one route. Anima and Anima-compatible style adapters form another. They require separate graphs; the two checkpoints are not interchangeable or a single combined model.

The first requested screenshot-stack runs have executed in both families. A later controlled comparison should test each family without its adapters and then with the selected stack using the same prompt, seed, sampler and dimensions. Record which variables changed. A matching seed does not make outputs from different model families equivalent experiments.

The owner selected this direction, not the exact authored subject. Prompt wording, clothing and composition remain editable. The separate character-consistency study keeps its existing canon: the supplied standard costume including the shown back view. This brief does not alter that study or renew any of its attempt budgets.

## What to judge

Ask whether the image has appealing light and colour, a readable silhouette, coherent clothing, believable hands and facial details, and enough consistency to repeat the character. Keep a successful render separate from a useful candidate and from an accepted finished asset.

The owner's next curation decision is whether a displayed candidate should enter a private favourites collection, needs correction, or should remain an experiment. No unseen output is approved. Model terms and any commercial use remain separate from that visual choice.

## Modular extension requested 13 September

Prepare separate SDXL/Illustrious lanes for CSTati v3, YumeFlux and AniFox, plus Anima and JANIMA lanes with their exact compatible adapter versions. Begin with a one-image base, add style deliberately, then introduce pose/reference guidance, a masked correction and an upscale only as needed. Preserve the image and recipe at every stage so a later module can be changed without erasing the comparison.

The owner clarified that the work is non-sexual. Source screenshots supply technical examples; their subject wording is not an instruction for the new prompts. Reuse Workflow Studio's graph import and editing work in PR #126. Reusable Step modules and arbitrary edited-graph execution remain separate workstreams #120 and #122; editable graph exports are useful before those features exist.

The owner selected **B — softer cinematic shading** from the bounded Anima comparison as the
starting look for this pack. Both comparison images remain experiments and no image was added to
the shortlist or accepted as finished art. The separate character-consistency canon remains the
supplied standard costume, including its shown back view; this look choice does not change that
canon or establish art acceptance.

## Recovery rule

If ComfyUI disconnects after accepting a prompt, preserve the prompt ID and submitted graph. Reconnect to observe that prompt; never submit it again to discover what happened. Restoring a runtime is not evidence that the interrupted generation failed or succeeded.

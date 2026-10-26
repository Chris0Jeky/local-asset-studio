# Adult fashion study: MOSS and its adapters, 26 October 2026

**Later session closeout:** [three of the 12 follow-up jobs completed, nine were
never submitted, and a 12-image blind reread was saved](closeout/README.md).
The original 39-image wave below remains a separate executed record.

**Executed:** all 24 original-character comparisons and all 15 franchise pilot
jobs completed and were inspected. [Results, limitations and the next bounded
queue](RESULTS.md) retain the findings; [receipts](receipts.json) and
[franchise receipts](characters-receipts.json) bind exact recipes and image hashes.
The eight Kromoss jobs remain **NOT RUN**. No result is owner-accepted by this record.

The [frozen plan](plan.json) tests two original, explicitly adult character briefs,
two seeds and six treatments, for a fixed allowance of 24 graph executions. All
characters are 30 or 32, with mature faces and adult proportions; the requested
illustrations are non-explicit. This is private model research and agent pre-review,
not owner art acceptance or a licensing decision.

The common settings are 1024×1536, 30 steps, Euler / sgm_uniform, CFG 3 and an empty
negative. Treatments are prompt-only; Reverse 1999 at 0.9 without its trigger;
the same adapter and weight with `reversesty`; the triggered adapter at 1.2;
mikkoani at 0.9; and mikkoani at 0.9 plus Impasto at 0.25. The same prompt is kept
across treatments except the deliberately tested trigger prefix. The author's
different sampler/CFG recommendation is not silently mixed into this comparison.

## Sources and evidence boundaries

Primary-source metadata was retrieved on 26 October 2026:

- [OpenMOSS SFT card](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT): natural
  language, tags and JSON layouts; the card's 50-step recommendation is distinct
  from the 30-step local study.
- [Reverse 1999 author](https://civitai.com/api/v1/models/3005908): `reversesty`,
  strength 1.0–1.4, er_sde / CFG 5 / 30 steps. The trigger was absent from the
  library metadata and the 19 October experiment. Historical results remain intact.
- [mikkoani author](https://civitai.com/api/v1/models/2470371): the MOSS adapter was
  trained on Base and used by its author on SFT with an 8-step adapter.
- [Impasto author](https://civitai.com/api/v1/models/2230912): suggested strength
  0.6–1.0, start 0.8; intentionally softer contrast. The 0.25 secondary blend here
  is an experimental variable, not the author's recommendation.
- [Kromoss card](https://huggingface.co/lodestones/Kromoss) and
  [file metadata](https://huggingface.co/api/models/lodestones/Kromoss?blobs=true):
  revision `a4fe97449297af2e3be7841e1c18e431f3b06031`, update 11000 and the
  newer DMD2 adapter. The old diffusion partial is from a different file revision;
  it was preserved, and the current file is downloaded under a different name.
- [Comfy-Org](https://huggingface.co/Comfy-Org/MOSS-Image) now lists community edit
  and control adapters. The installed local text-to-image workflow has neither;
  community capability does not establish installed-node compatibility.

Execution uses Studio's existing Production comparison plans. Graphs, model
hashes, generation allowance and per-stage attempts are pinned before execution.
The controller saves creation/start intent before each POST and never retries
an uncertain mutation. A plan-creation response exceeded the original observation
timeout while hashing the model inputs; its unique matching **planned** record
was recovered with zero reserved generations before its one explicit Start.

Full-size images, exact recipes, prompt/job IDs, admission observations and per-stage
receipts live under `E:/local-asset-studio-labs/moss-20261026/evidence/`; actual
Studio job/project state lives under the sibling `experiments/`. Controller logs
are in this checkout's ignored `.runtime/lab-20261026/`. Models and generated image
bytes stay outside Git. Completion, visual judgements and recommendations in the
results record come from the corresponding receipts and inspected outputs.

The [shared rubric](../../../docs/quality/JUDGING-RUBRIC.md) applies: inspect every
full image and full-resolution face/hand crops, identify defects, and skip any
youthful-reading or explicit result before assessing style. `HUMAN_TODO.md`
continues to own subjective art acceptance and the MOSS Make-look decision.

## Franchise recognition pilot requested during the study

The separate [15-picture plan](characters-plan.json) uses the existing character
roster as a pool of names and selects Tifa's adult main-story version, Yor and
adult-presenting android 2B. It never expands the whole wildcard file. Tifa's
[official original profile](https://finalfantasyviipc.square-enix-games.com/en&lang=en)
states age 20. The [official anime profile](https://spy-family.net/tvseries/#character)
identifies Yor as the mother/wife and Thorn Princess; its exact numeric age was
not established in the opened primary sources. [PlatinumGames](https://www.platinumgames.com/works/nier-automata)
identifies 2B as a YoRHa battle android; no human chronological age is inferred.

Official artwork supplies the recognition anchors. Yor's red eyes were verified
against [her official artwork](https://spy-family.net/tvseries/assets/img/top/chara_yor_1.png),
correcting the wildcard's gold-eye error. Canonical outfit, hair, palette and
accessories are scored separately from the requested adaptation. Eyes covered
by 2B's visor are not graded for eye color.

For each character, name-only recall is compared with an explicit description.
Style, seated pose and fuller-bust wording each branch independently from that
described baseline. One fixed seed makes this a pilot; combined adaptations and
seed consistency need their own comparisons. Name-only recognition is evidence
of learned associations, not proof that particular images were in training.

These pilot jobs use the ordinary Studio job route with durable intent/job-ID
records and no mutation retry. The four required model files are freshly hashed
against library pins before each five-job character batch; full file identities
and the template hash are checked again before each submission. This differs
from the original Production plans' repeated per-stage content hashing. Recipe
exports retain the actual graph, prompt IDs and outputs in both tracks. No
character LoRA or source image is supplied.

## Optional Kromoss extension

The [eight-picture extension](kromoss-plan.json) is **NOT RUN** after three short
checkpoint transfers. DMD2 file verification does not prove inference. The
checkpoint partial, failure logs and source pin are preserved, with the exact
resume condition in [#1662](https://github.com/Chris0Jeky/local-asset-studio/issues/1662).

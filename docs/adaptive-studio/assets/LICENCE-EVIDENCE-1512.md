# Source-art licence evidence (#1512)

Accessed and inspected **25 October 2026**, against checkout `1aa48338`. This closes the
record gaps raised on source-art PR #1269; it records terms and provenance, not commercial
clearance, copyright protection, art acceptance or permission to publish. No intended commercial
use is specified by this task, so no new owner decision is inferred. Existing creative/licensing
choices in [HUMAN_TODO.md](../../../HUMAN_TODO.md) remain open. Recheck terms for the actual use.

## OpenAI

The six [Atelier receipts](production/20261002-atelier/receipts/) identify OpenAI/image_gen for
three source images and Pillow for their derivatives. The tool did not expose the model, seed,
provider job ID or provider timestamp. Those values stay null; orchestration handles are not
provider IDs. All six receipts link here, including derivatives that inherit their source terms.

Dated primary sources read on 25 October 2026:

- [Europe Terms of Use](https://openai.com/en-GB/policies/eu-terms-of-use/), updated
  16 January 2026: applies to individual users in the UK/EEA/Switzerland. Under Content,
  users retain input rights and own output as between themselves and OpenAI, to the extent
  allowed by law; OpenAI assigns its rights, if any. Other users' output and third-party output
  are excluded from that assignment. Users must have input rights, review output before
  use/sharing, avoid infringement and prohibited uses, and must not present AI output as
  human-generated. Output ownership does not establish third-party clearance or exclusivity.
- [Services Agreement](https://openai.com/policies/services-agreement/), updated
  1 December 2025, effective 1 January 2026: covers APIs and business/developer services.
  Sections 4.1–4.4 likewise assign OpenAI's output rights subject to law, put input permissions
  and output evaluation on the customer, and warn of similar outputs. Sections 3.3 and 10
  restrict unlawful/infringing use, competing-model development (with stated exceptions), and
  publicity using the other party's name/logo or relationship without permission.
- [Service Terms](https://openai.com/policies/service-terms/), updated 16 October 2026:
  section 6 restricts identifying people, sensitive inference and reproducing likenesses
  without consent/rights; API/Enterprise IP indemnity has exceptions, including trademark
  use in commerce. No indemnity is asserted for these tool receipts.
- [Sharing & Publication Policy](https://openai.com/policies/sharing-publication-policy/),
  updated 14 November 2022: demonstrations/shared generations require manual review,
  attribution to the creator/company and clear AI disclosure, subject to content restrictions.
- [Usage Policies revision](https://openai.com/policies/usage-policies/revisions/2025-10-29/),
  effective 29 October 2025. The [live URL](https://openai.com/policies/usage-policies/) served
  a version marked effective **20 November 2026**, after this access date; do not treat that
  future-dated version as already effective. The linked prior revision records the applicable
  dated policy evidence; recheck at publication.

The receipt's `dot-run` execution surface does not identify the contracting account or agreement.
These are current public terms evidence, not proof of which agreement governed the original
generation on 2 October. Ownership language is not a blanket commercial-use approval; actual
input rights, agreement, use restrictions and publication disclosure still apply.

## Krea 2

Read the complete [Comfy-Org LICENSE.pdf](https://huggingface.co/Comfy-Org/Krea-2/resolve/1171f4dc7e325bf3734586942e737872506c73e1/LICENSE.pdf)
(137,711 bytes; SHA-256 `b82a2805162bde714a4eb27b9063c4fc3345d08a30be055134a6160e5430ba74`),
Krea 2 Community License Agreement v1, 22 June 2026. The publisher's
[text version](https://github.com/krea-ai/krea-2/blob/main/docs/KREA-2-COMMUNITY-LICENSE)
provides another primary source. Both accessed 25 October 2026.

Sections 2.1/2.3 permit commercial use of models, derivatives and outputs only below
USD 1,000,000 total trailing-twelve-month revenue, including controlled affiliates and all
sources; at/above that threshold a separate enterprise licence is required before commercial
use, and threshold crossing requires stopping commercial use and contacting Krea.
Section 5.3 confirms output ownership for the generator subject to compliance and makes the
generator responsible for it. Sections 4.1–4.4 require lawful/AUP-compliant use, appropriate
content filtering (which may include human review), preservation of safeguards/provenance,
and AI disclosure when law/platform policy requires it. Section 3's agreement/Notice,
Krea-prefixed model naming and modification notices govern model/derivative distribution,
not a new standalone attribution requirement for every output image. Section 5.4 does not
grant general trademark rights. Sections 6–9 disclaim warranties, impose user indemnity and
allow termination, including on 30 days' notice. This summary does not replace the agreement
or its incorporated AUP, or verify compliance by an existing deployment.

The tutorial's existing Krea picture is traced below. The read PDF replaces the former
unread-PDF record for Comfy-Org styles in `models/library.json`/`models/README.md`; it does
not independently clear third-party adapters or establish the owner's revenue/use eligibility.

## Recover fixture

[RECOVER-FIXTURE.json](production/20261014-recover-fixture-tutorial/RECOVER-FIXTURE.json),
the [downloaded recipe](production/20261014-recover-fixture-tutorial/asset-studio-recipe.json)
and [recording receipt](production/20261014-recover-fixture-tutorial/recording-receipt.json)
show an unsubmitted Anima fixture with empty prompt IDs, submissions and outputs. Its
`anima-aesthetic-v1.1.safetensors` generator uses a Qwen-named text encoder and VAE; those
component names do not make it a Qwen-Image 2.1 output.

The recording's HTTP audit also requested these pre-existing hero images. Their bytes match
[Workflow Lab execution evidence](../../../experiments/curated/workflow-lab/execution-evidence.json)
and their preserved submission graphs (not today's preset defaults):

| Requested image | Actual generator and adapter | Recipe / provider prompt ID |
| --- | --- | --- |
| `examples/workflow-lab/anima.png` | Anima Aesthetic 1.1 | [anima-portrait](../../../experiments/curated/workflow-lab/anima-portrait-recipe.json), `6d136e16-132f-4964-a07b-988a2a34b5ac` |
| `examples/workflow-lab/lineani.png` | SDXL base 1.0 + LineAniRedmondV2 | [lineani-portrait](../../../experiments/curated/workflow-lab/lineani-portrait-recipe.json), `6e37e90d-ef45-4e07-af31-045b4938fe53` |
| `examples/workflow-lab/krea.png` | Krea 2 Turbo FP8 + official `krea2_retroanime.safetensors` | [krea-portrait](../../../experiments/curated/workflow-lab/krea-portrait-recipe.json), `144048d4-d6ea-4142-87f5-bdf11d87031c` |

The fixture's `licence_review` records the corresponding file hashes. All three PNGs also match
the files at the recorded application revision `759201057da694d826e7471cf8cfc8fc18cafb2d`;
their embedded prompt graphs agree with these recipes. **No Qwen-Image 2.1 output was identified in this
fixture or these displayed assets.** HTTP requests prove the assets were requested, not their
visibility in every video frame; the historical video was not replayed in this review.

For any later Qwen 2.1 output, retain the
[Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/d26bb61231c349cf6b7896fa83353113880e1ba3/LICENSE),
release 20 September 2026, accessed 25 October 2026 (SHA-256
`8dc973f024ff95966bea25866efa443fd16776dcb1001e681e3d467ea572b28d`).
Sections 1.i/2 limit the Materials grant to research/evaluation and require a separate
commercial licence for commercial model use; section 4.b separately addresses attribution
when outputs train/improve a distributed model. Do not infer an unrestricted output licence
from the absence of an identified Qwen 2.1 asset. No Qwen licence is assigned to Anima/Krea
merely because they use Qwen components, and no broader model/adapter clearance is asserted.

## Font headers

Fetched the exact OFL files pinned by [acquired/MANIFEST.json](acquired/MANIFEST.json),
not current font releases, on 25 October 2026. Their SHA-256 values match the manifest:

| Font | Original licence inspected | SHA-256 | Reserved Font Name declaration |
| --- | --- | --- | --- |
| Inter | [OFL.txt at 23e54b51](https://github.com/google/fonts/blob/23e54b51ddffbc7713c583748e3bd86f62b1fa4a/ofl/inter/OFL.txt), copyright 2020 Inter Project Authors | `5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57` | None after the copyright statement |
| JetBrains Mono | [OFL.txt at 23e54b51](https://github.com/google/fonts/blob/23e54b51ddffbc7713c583748e3bd86f62b1fa4a/ofl/jetbrainsmono/OFL.txt), copyright 2020 JetBrains Mono Project Authors | `b2fe5e8987594e9ffd1d2ca52a2f5d73eb8335243893c5d6254b5ad69269591d` | None after the copyright statement |

Both contain the generic OFL definition/condition about Reserved Font Names; that boilerplate
does not reserve a name. OFL 1.1 still requires copyright/licence preservation when distributing
fonts, prohibits selling fonts alone and disallows endorsement claims; it does not impose the
font licence on documents made with them. These findings concern these exact files only.

## Promo and README cover trademark inspection

The component kit's README-cover study is `promo-readme.svg` and its PNG rendition, not a
second independent cover. Inspected the entire [SVG](production/20261002-component-kit/promo-readme.svg)
and its generator `build_sheet.py`; visually inspected the original `promo-readme.png`
from the [recorded delivery archive](https://github.com/user-attachments/files/32971835/las-foundation-source-kit-20261002.zip).
The archive SHA-256 matches `GITHUB-DELIVERY.json`:
`5ef294cfbd729e736f9a624217354ee8a21ef8ff4b152c354b20cd39a673a9ca`.
The PNG matches `SHA256SUMS.txt`:
`860aff4cb9bda947d4480a44301501788b4f0375c6a5bb240fb12f44f0123f7f`.

The only visible text is Local Asset Studio, Local creative workspace, and Source design
study · editable assets, beside generic outlined cards. The SVG uses a system font stack
and contains no external images, logos or embedded resources. No third-party brand name,
logo or endorsement was observed in either rendition. This is an asset inspection, not a
trademark-register search or clearance of the Local Asset Studio name. Artwork bytes and
their delivery hashes remain unchanged. Revisit intended-use clearance only if commercial
use is actually planned; this task establishes no such plan.

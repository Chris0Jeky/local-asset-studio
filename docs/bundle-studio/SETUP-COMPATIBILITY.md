# Setup compatibility and recommendation intelligence

21 September 2026 · first read-only implementation slice of #753.
Initial main: `1dbd3d53503cd7323f4f7cd2ff7cba7eb589b00d`.

## The selection problem

A file being installed does not mean that it fits the selected model, loader,
runtime or task. A Civitai family label does not prove an exact architecture.
A gallery image that names several resources proves only that those exact version
IDs were reported together in that retained record; it does not prove the graph,
installed bytes, licence, output quality or repeatability.

The Studio therefore needs two separate decisions:

1. **hard compatibility** — whether the known setup facts admit the resource;
2. **recommendation** — how strong the exact, objective-specific evidence is among
   candidates that passed the hard gates.

Recommendation evidence never repairs a hard mismatch. Missing evidence is not
converted into compatibility, and popularity is not converted into quality.

## What this slice implements

`studio_workflow/setup_compatibility.py` is one pure/offline evaluator and CLI.
It consumes already-normalized provider-neutral facts and retained claims. It does
not inspect a website, hash a local model, read the model library, query ComfyUI,
prepare a graph, change a setup, install anything or submit generation.

```text
reviewed source snapshots (#433/#754)       current setup observations
                |                           inventory + installed schema
                +------------+  +-----------------------+
                             v  v
                provider-neutral request
                             |
          studio_workflow.setup_compatibility
                             |
              versioned read-only report
                             |
       future Bundle/Create selector and atomic diff
```

The evaluator returns `studio.setup-compatibility-report/v1` with a SHA-256 over
the exact request, deterministic ordering, diagnostics and explicit zero-authority
flags. The fingerprint identifies the checked inputs. It is not a lock, an approval
receipt or proof that files remained unchanged after evaluation.

## Decision states

| State | Normal selector | Meaning |
| --- | --- | --- |
| **Recommended** | Selectable and ranked | All required hard facts are known and compatible, and exact objective-specific strong or sufficiently broad reviewed gallery evidence supports the choice without a strong contradiction. |
| **Possible** | Selectable | Hard facts are compatible, but the evidence does not justify calling it optimal. This includes family-only guidance, historical observations, hypotheses and conflicting recommendation sources. |
| **Needs review** | Expert/native override only | A required identity, architecture, lineage, loader, format, runtime or capability observation is missing. Unknown is not compatible. |
| **Incompatible** | Not selectable normally | A known role, modality, architecture, strict lineage, loader, format, runtime or required-capability conflict exists. |

The first report does not mutate a selector. UI enforcement, stale-draft conflict
handling and atomic application remain later #753 acceptance. Keeping the first
slice read-only makes the policy independently testable before it can hide or
change a user's setup.

## Hard compatibility contract

The request describes one target slot and at most 256 candidates. Candidate facts
are exact normalized values, not names parsed by this evaluator.

Hard checks currently cover:

- component role and modality;
- canonical architecture;
- base lineage, either advisory or explicitly strict for the slot;
- exact loader class/input identity;
- runtime and accepted file formats;
- exact resource identity;
- required capability tokens for installed nodes, encoders, VAEs, companion
  resources, preprocessors or hardware/runtime features.

Capabilities have three states. A token in `capabilities` is observed present. A
token in `known_absent_capabilities` is authoritatively absent and creates an
incompatibility. A required token in neither list is unknown and creates **Needs
review**. The two lists cannot overlap.

Architecture mismatch is always hard. A normalized base-lineage difference is
soft by default because nearby SDXL-derived ecosystems are not universally
interchangeable or universally incompatible. A caller may set `strict_lineage`
when the actual loader/module contract requires exact lineage. Exact controlled
or creator evidence can recommend a candidate with a soft lineage difference;
it still cannot override a strict one.

An exact identity may use a provider-neutral stable token such as a SHA-256,
positive Civitai version ID or immutable Hugging Face resource locator. Filename,
marketing family and physical presence are not exact identities.

## Recommendation evidence contract

At most 1,024 bounded claims are evaluated. Every claim names a candidate,
objective, direction, source kind, scope, retained source revision, observation
count and independent-source count. Exact claims are bound to the candidate's
resource identity; evidence for another version is ignored with a diagnostic.

Supported source kinds are:

- `creator_documentation`;
- `controlled_run`;
- `local_observation`;
- `gallery_co_use`;
- `provider_metadata`;
- `authored_hypothesis`.

Only exact creator documentation or a controlled run is strong prescriptive
evidence in this first policy. A local observation remains historical. Provider
metadata describes a source record rather than artistic optimality. A hypothesis
remains a hypothesis. Family-scoped claims can explain or weakly order **Possible**
choices but cannot promote an exact resource to **Recommended**.

Reviewed gallery co-use can promote only when an exact-version claim records at
least three retained observations from at least two independent sources. These
numbers are a conservative first admission threshold, not a statistical quality
guarantee. Repeated images or posts from one uploader should be deduplicated by
the #754 normalizer before they reach this evaluator. The raw engagement count is
not an independent source.

Compatibility-only evidence cannot invent quality, speed or memory optimality.
For example, a creator statement that a LoRA targets SDXL can support the
compatibility explanation, but a `quality` request still needs quality-scoped
evidence before the resource is called recommended.

Strong support and contradiction are preserved. The evaluator does not average
sources, choose a winner or synthesize a compromise. A conflicted hard-compatible
candidate remains **Possible** with a visible limitation. An exact compatibility
contradiction also suppresses recommendation but is not silently upgraded into a
hard fact; reviewed normalized facts own the hard gate.

## Deterministic ranking

Candidates sort by decision state, then by the following evidence tuple:

1. number of exact strong supporting claims;
2. independent sources in qualifying gallery claims;
3. observations in qualifying gallery claims;
4. weaker supporting claims;
5. case-insensitive display name and stable ID.

The report exposes those components instead of a single opaque decimal score.
Only recommended rows receive a one-based `recommendation_rank`. The order is
stable under request/candidate/evidence reordering.

## Request example

```json
{
  "format": "studio.setup-compatibility-input/v1",
  "slot": {
    "role": "lora",
    "modality": "image",
    "architecture": "sdxl",
    "base_lineage": "illustrious",
    "strict_lineage": false,
    "loader": "LoraLoader.lora_name",
    "runtime": "comfyui",
    "formats": ["safetensors"],
    "objective": "quality",
    "capabilities": ["node:LoraLoader", "encoder:clip-l"],
    "known_absent_capabilities": []
  },
  "candidates": [{
    "id": "example-style",
    "name": "Example style",
    "role": "lora",
    "modality": "image",
    "architecture": "sdxl",
    "base_lineage": "illustrious",
    "loaders": ["LoraLoader.lora_name"],
    "format": "safetensors",
    "runtime": "comfyui",
    "requires": ["node:LoraLoader", "encoder:clip-l"],
    "identity": "civitai-version:123456"
  }],
  "evidence": [{
    "id": "example-card",
    "candidate_id": "example-style",
    "resource_identity": "civitai-version:123456",
    "kind": "creator_documentation",
    "scope": "exact_resource",
    "direction": "supports",
    "objective": "quality",
    "observations": 1,
    "independent_sources": 1,
    "source": {
      "locator": "Retained reviewed model-version card",
      "revision": "civitai-version:123456",
      "retrieved_at": "2026-09-21"
    }
  }]
}
```

Run the same evaluator without provider or runtime access:

```sh
python -m studio_workflow.setup_compatibility retained-request.json
```

Exit 0 prints the report. Invalid input exits 2 with a bounded structured
`invalid_request` error. Source text is data; credential-bearing HTTPS locators,
unbounded identifiers, duplicate candidate identities and malformed dates refuse.
Invalid individual evidence records become diagnostics while valid candidate facts
remain inspectable.

## Civitai and Civitai.red research boundary

The public Civitai model-version response can expose exact model/version IDs, AIR,
model type, `baseModel`, `baseModelType`, trained words and file-level identity,
format/precision and hashes. These are suitable raw facts for a reviewed #754
snapshot, not values for this evaluator to fetch or trust directly.

The images endpoint can return top-level exact model-version IDs and, when metadata
is available, typed `civitaiResources` entries with version IDs and recorded LoRA
weights alongside scalar generation settings. That supports a bounded co-use
observation. User-submitted metadata may be absent, hidden, malformed or incomplete;
an image existing on the service is not a controlled successful experiment.

`civitai.com` and `civitai.red` remain distinct source hosts in #754. The retained
request must include the exact host and browsing/filter parameters. Current Civitai
source treats `.red` as a red-capable host, while a community API answer describes
`browsingLevel`/legacy `nsfw` image queries. Neither is a guarantee that both hosts
return identical records. A blocked, filtered or inconsistent response is unknown,
not an empty catalog. Raw response hashes and request identity must survive so a
later provider/API change cannot rewrite old evidence silently.

Primary references reviewed for this design:

- `https://developer.civitai.com/site/reference/model-versions`
- `https://developer.civitai.com/site/reference/images`
- `https://github.com/civitai/cli`
- `https://github.com/civitai/civitai/blob/main/src/server/utils/server-domain.ts`
- `https://github.com/orgs/civitai/discussions/2198`

The official CLI's compatibility grouping is deliberately conservative and warns
only on confident architecture mismatches for several neighboring SDXL-derived
families. That supports the split used here: normalized architecture is a hard
gate, while lineage is explicit and policy-controlled rather than guessed from a
name.

## Integration sequence

1. #754 retains bounded exact provider facts and gallery composition observations
   through the reviewed #433 source-intake/transport boundary.
2. A later adapter maps exact `models/library.json` pins, setup graph slots, active
   backend/schema observations and retained source facts into this input contract.
3. Bundle/Create renders Recommended, Possible and Needs review, and omits or
   disables Incompatible choices with the report's reasons.
4. Selection creates a complete, reviewable substitution diff. Apply rechecks the
   setup/document revision, backend/schema and inventory, then uses the existing
   revisioned document/service path. Browse/evaluate never installs or generates.
5. Controlled runs and accepted owner review can add new exact evidence without
   rewriting historical source claims.

## Verification

The test-only commit `47786e8` preceded the implementation commit and deliberately
failed because this module did not exist. Focused coverage is:

```sh
python -m unittest discover -s tests -p 'test_setup_compatibility.py' -v
python -m studio_workflow.setup_compatibility --help
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Tests cover hard role/modality/architecture/loader/format/runtime mismatches,
missing facts, known-absent versus unobserved capabilities, strict and advisory
lineage, exact identity mismatch, creator/controlled/gallery evidence, family and
historical limits, source conflicts, deterministic ranking, malformed/credential-
like data, bounds, immutability and CLI zero-authority output.

This slice does not prove the correctness of a future inventory/source adapter,
real Civitai records, local installed bytes, live ComfyUI execution, GPU memory fit,
image quality, licence clearance or owner acceptance. No HUMAN_TODO item is changed;
q-29 remains an owner decision.

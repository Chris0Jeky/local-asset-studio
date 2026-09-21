# Opt-in exact-template anime prompt profiles

Follow-up to the supplied anime qualification research (pp. 6-11, 23) and #552/#34/#144.

## Three profiles, same Prompt Lab

| Profile ID | Projection | Registered template scope |
| --- | --- | --- |
| `anima-aesthetic11-prose-v1` | Prose plus reviewed descriptors; score-token conflict review in both channels | `anima-portrait`, `anima-environment` |
| `anima-base10-prose-v1` | Prose plus reviewed descriptors; no inherited Aesthetic score restriction | `anima-v1-baseline`, `anima-artist-stack` |
| `animagine40-opt-tags-v1` | Approved tags in their supplied order; optional quality tail must be final | `anime`, `anime-animagine-quality` |

Choose these explicitly in the existing profile dropdown or CLI. Switching/compiling never changes the
model, sampler, LoRAs or generation allowance. The nine earlier profiles and their exact profile hashes
are retained, so this addition does not invalidate historical saved briefs or compiled projections.
Those legacy generic recipe associations are not newly certified as equivalent model dialects.

These profiles do not invent quality words, franchise identities, ratings, tags, negative terms or sampling
settings. Aesthetic and Opt conservatively block `score_*` conflicts pending a reviewed rewrite or a
different profile; the original text remains in both the intent and diagnostic output. Base does not inherit
that Aesthetic rule. Opt checks the location of ordinary comma-separated quality tokens, including a
comma packed into one input item; it does not silently reorder them. This is a narrow dialect checker,
not a complete booru vocabulary, weighted-prompt parser or semantic-coverage guarantee. Required tag
coverage, unbound geometry/masks and references continue to use the existing compiler diagnostics.

## Exact-template handoff

Each new record carries `template_bindings`: preset identity, canonical authored graph SHA-256 and exact
positive/negative targets. The existing `bind_graph` recompiler first validates the complete compiled
artifact, then checks this contract. Changing a model, encoder, adapter, sampler or other graph input
cannot be approved merely by supplying a newly computed caller graph hash. Swapping positive and
negative targets, using another preset ID or tampering with the compiled profile is refused.

The HTTP handoff additionally refuses source-dependent presets before graph inspection, including
legacy profiles and companion reference bindings. `animagine-face` is deliberately excluded: a
text-only payload must not inherit its authored example image instead of a reviewed user source.

Exact-template validation runs through the existing CLI and composed HTTP route. Only the original registered
text fields are written in a copied preview; input graphs and source briefs remain unchanged. The
existing raw-file template guard and explicit generation action still apply downstream. No new executor,
registry, persisted project schema or reference-image path is added.

This deliberately pins a whole authored template, not arbitrary compatible variants. A future template
change needs a reviewed profile revision/new ID or a narrower independently tested capability contract.
Do not update pins merely to make CI green. UI/agent-authored post-handoff sampling edits are outside
this prompt-only projection and retain the existing Create review/validation boundary.

## Evidence and source scope

Anima role and score-token guidance is retained from the supplied 15 September report; the attempted
immutable upstream README fetch in this continuation was unavailable. It is not a new exact-v1.1 source
verification. The local template identities come from repository checkpoint `0b510ac852c922db4a01e49ce68cdb083f9ad4e4`.

Animagine's upstream ordered-tag/quality-tail guidance was read at immutable README revision
`2b7c1b397761bf5bd3cc42e5b39ec99314a75a96`:
<https://huggingface.co/cagliostrolab/animagine-xl-4.0/blob/2b7c1b397761bf5bd3cc42e5b39ec99314a75a96/README.md>.
The stricter blocking policy is this Studio's opt-in adaptation, not a claim that the model rejects those
strings. No tokenizer, installed weight bytes, current GPU runtime or artistic improvement is attested.
Character caps remain UI budgets and token counts remain null. Native Qwen/quantized Lightning,
standalone Turbo, reference-slot binding and wider exact-bundle qualification remain separate work.

## Verification and use

```sh
python scripts/studio_prompt.py profiles
python scripts/studio_prompt.py compile brief.json --profile anima-aesthetic11-prose-v1
python -m unittest discover -s tests -p 'test_exact_anime_profiles.py' -v
python -m unittest discover -s tests -p 'test_studio_prompt.py' -v
```

Tests retain all nine old profile digests, verify all six actual graph contracts, preserve inputs and
sampling values, exercise both score channels and comma-tail diagnostics, reject malformed contracts,
and run the real CLI and composed HTTP compile/bind paths without runtime or job access. The
read-only tests distinguish successful authoring from generation and owner acceptance.

# Krea Vary keeps the recorded adapter stack (#1213)

## Outcome and scope

Picture-based Krea Vary now carries the source run's four adapter slots for
`krea-anime-atelier` and `krea-refine`. Both use the exact
`krea2_turbo_fp8_scaled.safetensors` base and four bound model-only adapter slots.
Vary carries each strength and filename, plus sampler, scheduler and CFG. The
round still picks new seeds, keeps the source picture and wording, and owns its
denoise and step settings. No authored graph or ordinary recipe default changes.

Previously, every Krea source used refine's own TextFusion / Niji / distill
defaults. This could replace Retro Anime or Airy Anime Watercolor, enable a
previously disabled distill adapter, or change a GGUF source to fp8. Restricting
the route to itself without carry would still replace a customized refine stack.

The other five sources use the existing **new seeds, same recipe** fallback:

| Source | Why it is outside this picture-based carry route |
| --- | --- |
| `krea-portrait` | One adapter slot |
| `krea-portrait-gguf` | A different exact base file, and one adapter slot |
| `krea-environment` | One adapter slot |
| `krea-anime-atelier-gguf` | A different exact base file |
| `krea-style-lab` | Three adapter slots |

These are text-to-image sources, so the existing fallback can reload their saved
recipe, check its template through `/api/recipe-check`, and change its seed. It
retains the recipe's recorded controls and does not claim that source pixels are
an input. Both Create and Make retain that distinction.

## Adapter contract

The existing WAI carry path uses `LoraLoader`, whose MODEL and CLIP outputs must
reach every relevant sampler and text encoder. That graph traversal is retained;
the shared binding-map checks below also harden malformed WAI declarations while
preserving its legal same-node MODEL/CLIP strength fanout.
Krea uses `LoraLoaderModelOnly`, which has a MODEL footprint and no CLIP output.
Its narrow attestation requires:

- the source and destination to use the same exact base-model identity;
- the same adapter loader kind for each carried slot;
- a distinct adapter owner for each carried slot on both source and destination;
- one strength binding to that node's `strength_model`, and one filename binding
  to its `lora_name`, without an extra strength or CLIP footprint;
- every carried model-only adapter to reach every sampler MODEL input on both the
  source and destination graph;
- every model-only adapter's upstream MODEL path to reach a recognized base
  loader through known adapters and MODEL forwarders, using output port zero;
- that connected loader's kind and filename to match for each source/destination
  slot, rather than treating unused declared loader names as connection evidence;
- every source adapter to be carried, and no destination adapter supplied by its
  own defaults instead of the source.

Known MODEL pass-through nodes keep their existing allowlist. Unknown wrappers,
wrong output ports, bypassed adapters, missing slots, source/route loader changes
and fp8/GGUF differences remain refusals. A family label does not equate models.
Filename companion bindings are also refused: one slot's filename cannot fan out
and overwrite another slot while its strength binding still appears correct.
The shared carry check accounts for every primary and companion binding. A slot's
strengths stay on its own adapter's legal strength fields, and its filename writes
exactly its own `lora_name`. Other controls cannot write any input on a carried
adapter, including its structural MODEL/CLIP links. Thus a disabled later slot,
CFG, sampler, or round-owned step binding cannot overwrite the attested stack.

The unchanged frontend carry pipeline takes recorded job controls first. If a
control is absent, it uses that source recipe's current default and names the
fallback in the status text; it does not claim an exact historical stack for an
incomplete record. Missing runs or unavailable named adapters are refused with a
reason. Even a disabled slot retains its filename and the existing file checks.

## Historical strengths: four steps and six steps

The owner selected Krea denoise **0.45 / 0.65** on 27 September 2026. The summary
in `HUMAN_TODO.md` and `CURRENT_STATE.md` describes the pair as "6 steps", but the
detailed executed v2 table in
`experiments/curated/live-proofs-20260927/README.md` records:

| Strength | Denoise | Executed steps | Historical Studio job |
| --- | ---: | ---: | --- |
| Subtle | 0.45 | 4 | `b4bfb680` |
| Strong | 0.65 | 6 | `213848b0` |

The live graph/catalog already produced this four/six behavior. This change makes
subtle's four steps explicit in its Vary controls and retains strong's six. It
does not change denoise, infer a new owner decision, rewrite the historical
summary, or relabel the subtle proof as a six-step run. The numeric settings
remain owner-approved. No new source-stack generation or visual acceptance is
established by retaining those numbers.

## Causal checks and execution limits

Six model-only contract tests produced six assertion failures on the unchanged
attestation code. The catalog test separately failed on the seven-source
declaration. Client policy failed because the original route carried no controls;
Create and Make payload tests reproduced the lost adapter controls and refusal of
the expected reseed fallback. They now cover four recorded strength/name pairs,
disabled slots, sampler/scheduler/CFG, explicit four/six steps, exact models,
loader and footprint guards, wiring, missing evidence and source-default
disclosure. The existing WAI MODEL/CLIP cases remain in the same suite.
Independent review found a filename fan-out gap. Separate source and destination
regressions exercised the real `Studio._bind_control`: the fourth filename
overwrote the first while validation returned no problems. Both tests failed
before the filename-footprint correction and pass after it.
The subsequent Codex review found that downstream reachability stopped at the
adapter and left its own MODEL input unproved. Seven added test methods reproduced
19 assertion/subtest failures before the upstream correction: source and route
unknown wrappers before the first adapter, invalid ports/links, missing nodes,
cycles, invalid base filename fields, and different connected bases hidden by
matching sets of declared orphan loaders. Known MODEL forwarders stay supported.
The correction traces each model-only stack upstream and compares its connected
base; the WAI MODEL/CLIP graph traversal and catalog/client declarations are retained.
Another Codex review found that two controls could own the same adapter even
though their individual footprints passed. Twelve added methods cover source and
destination aliases, partial aliases, actual disabled-slot overwrites, WAI cross-node
or swapped CLIP companions, filename misbindings/fanout, matching malformed strength
maps, other control collisions through primary/companion bindings, and unknown
adapter kinds. On the exact published prior code, the combined 52-method binding
and model-only classes produced 29 assertion/subtest failures and zero errors.
Legal WAI MODEL/CLIP fanout also passes with independently renumbered source nodes.
These shared binding-map refusals are new WAI validation hardening; legitimate WAI
behavior remains the same. Catalog and client declarations remain unchanged by
the review corrections.

The observed 52-method binding/model-only run passed before the scratch-environment
reset. Its local logs are no longer available. At reconstruction, the full 64-test
Vary suite, server suite and validator had not run locally after this slot-map
correction. Merge qualification is recorded in [PR #1606](https://github.com/Chris0Jeky/local-asset-studio/pull/1606)
and requires independently reviewed reconstructed source and fresh exact-head
Actions validation. The earlier observed results do not establish that broader
qualification.

Run the bounded checks:

```console
python -m unittest discover -s tests -p "test_vary*.py" -v
python -m unittest discover -s tests -p test_server.py -v
python scripts/validate-repo.py
```

The Python Vary tests invoke `tests/vary_core.cjs` and
`tests/vary_prepare_latch.cjs`. Their nested Node counts are not additional Python
tests. Tests use inert source/job/request fixtures; they do not submit generation.

The changed `krea-refine` preset is unverified pending a deliberate new proving
run. Its earlier execution note remains historical evidence for the prior refine
recipe, rather than proof of the new carried combinations. Static checks do not
prove installed-file availability, runtime model compatibility, visual retention,
creative acceptance or licensing. No runtime launch, model action, dependency
upgrade or generation is part of this change. Full published-head CI and
qualification against current main remain integration gates.

## Issue disposition

Refs #1213. This slice addresses its remaining adapter-stack policy; the earlier
draft confirmation, busy-latch and checked-reseed fixes remain in place. Final
issue closure belongs to reconciliation of the published and reviewed result.

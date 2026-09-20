# Empty optional native style boards

Software-only infrastructure for #351, related to the source-ownership contract in
#345. This does **not** activate an optional board in the shipped catalog or settle
owner question q-27. `restyle-wai` still declares `reference_board.min: 1`.

## Contract

A registered board can declare an integer minimum of zero. Zero means that **all
board slots may be empty**, not that a missing occupied reference, an in-flight
upload, or the independent continuation source may be ignored. The compiler does
not infer optionality from Style weight, denoise, a model name, or presentation
text. A populated board, including one with Style weight zero, retains the
existing compilation and byte-verification behavior.

For an empty native IP-Adapter board, compilation removes the declared LoadImage
nodes, their IPAdapterEncoder nodes, exclusively owned IPAdapterCombineEmbeds
nodes, and the IPAdapterEmbeds consumers. Every model consumer is rewired to the
adapter's actual upstream model link. In the WAI fixture this preserves both the
KSampler and FaceDetailer; the existing subsequent zero-strength LoRA pass remains
responsible for bypassing disabled LoRAs. No checkpoint or adapter is substituted.
Only now-unused IPAdapterModelLoader and CLIPVisionLoader resources are removed;
shared resources stay.

The transform plans on a copy before changing the caller's graph. Named
`reference` and `last_reference` bindings cannot be removed as board-owned nodes.
Duplicate loaders, mixed/unknown consumers, separate negative-embedding inputs,
invalid model links, cyclic bypasses and unsupported adapter output ports refuse
rather than guessing. This is **not** a generic graph-pruning engine: optional
ReferenceLatent boards and other graph families need an explicit bypass contract.
Their existing non-empty board behavior is unchanged.

All positional records survive with `file: null` and `pruned: true`. Recompiling
these records against the registered template reproduces the same graph. No image
bytes are read for the empty board itself.

## Continuation and readiness

Continuation validation pads a short board list exactly as compilation does. Each
padded loader must be absent from the compiled graph: padding cannot authorize an
authored example image. The independent source must still match the selected
asset, named input, lineage parent, template hash and upload/runtime bytes.
Non-board reference recipes still require every declared input explicitly.

The continuation blocker respects zero rather than replacing it with one. It
agrees with the existing shared reference-readiness projection for an empty board,
while missing occupied records and pending uploads continue to block readiness.
Guidance distinguishes an optional board from a recipe that has no board.

## Activation remains a separate change

Before changing the shipped catalog minimum, resolve q-27 and align the remaining
review/picker lanes: `studio_workflow.shortlist._restyle_board` currently recognizes
minimums of 1–3, setup-proposal result validation requires a positive board minimum,
and Workbench's board-destination helper selects routes with `board_min > 0`.
Those lanes are deliberately not silently broadened here. Test normal Create,
continuation, saved restoration and reviewed setup together when activating the
catalog change; runtime/model and creative acceptance remain separate evidence.

## Verification

The offline regression fixture uses the real WAI graph with only its **fixture**
minimum changed to zero. It exercises source-preserving preparation, a retained
job with no enqueue, dispatch-time byte revalidation, both model consumers,
positional restoration, unchanged populated boards, and refusal without partial
graph mutation. Node tests exercise the real continuation and shared-readiness
modules, not a reimplementation.

```sh
python -m unittest discover -s tests -p 'test_optional_style_board.py' -v
node --test tests/optional_style_board.cjs
python -m unittest discover -s tests -p 'test_references.py'
python -m unittest discover -s tests -p 'test_continuation.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The focused GitHub workflow checks out the exact PR head on Linux and Windows.
See the PR's evidence record for observed runs and counts. Passing these tests does
not show that a model is installed, a custom node is available, a render completed,
or its appearance or licensing was accepted. No generation is submitted.

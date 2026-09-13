# Oldest open issues: source-grounded reconciliation

Date: 13 September 2026. Baseline main: `8f471d62a63c339429f95e6a4b55707e99949d8b`.
This is a dated implementation checkpoint, not an assertion about later main or the live PC.

## Current work and flow

The original chronological open-issue order starts **#2, #3, #9**. Their descriptions
predate much of the implementation. At initial inspection no PR was open, and the
latest workflow/schema work (#126, #134, #136), host-commit admission (#129) and recovery
changes were merged. Read `CURRENT_STATE.md` before relying on older backlog prose.

During this pass two additional PRs appeared: **#138** proposes preset-compatible
workflow-document execution through existing tickets; **#139** records newer Anima
baselines and an owner-selected look. They were open, not assumed merged, at this
checkpoint. Neither is duplicated here. Their files, `HUMAN_TODO.md`, existing creative
receipts and the user's active checkout are left untouched.

The existing Studio path is:

```text
Source intake / curated pins / local model inventory
    -> explicitly selected backend and readiness checks
    -> registered preset + graph bindings + user controls
    -> preparation and applicable resource admission
    -> explicit enqueue / single existing worker
    -> retained graph, backend, prompt IDs and outputs
    -> Workspace / review / downstream handoffs
```

Guided Workflow Studio authors and checks documents; arbitrary authored-graph execution
must not be inferred from a successful check/export. #122 owns that release boundary;
#138's narrower proposal is specifically catalog-compatible tickets, not a new raw-graph
executor. File presence, endpoint readiness, successful inference, creative acceptance
and source/terms verification remain distinct states throughout the path.

## Chronological disposition

| Issue | Already present in this main | Work still justified |
| --- | --- | --- |
| #2 — HiDream integration | `app/backends.py`, safe explicit family switches, backend-pinned observations, API/native visual workflows, documented eight-step concept and reference trials in `docs/HIDREAM.md` | PR #137 protects unrecorded pre-listen launchers. Higher-step same-seed comparison and unresolved runtime/native evidence remain; do not close the whole issue. |
| #3 — controlled asset experiments | Comparison/export/Workspace machinery and extensive later experiment records exist; a mocked run is not a creative trial | Reconcile individual requested experiments with workstation receipts before scheduling anything. This pass performs no Qwen generation, interactive Krita round-trip or target-engine artistic assessment, so it does not close #3. |
| #9 — source intake and model bundles | `ModelLibrary` inventory, pinned/explicit downloads, fresh verification receipts, disk headroom and hash reuse; H3 baseline-file readiness; existing HF/Civitai/browser acquisition scripts | Browser intake has a concrete unknown-header fallback defect, fixed in this slice. Full identity/lineage, companion-bundle resolution, authenticated Seed Hunter evidence and hardware-path viability remain broader work. Publication/receipt races are separately tracked in #140. |

The backend slice and this intake slice are independent PRs from the same main, not a
stack that requires unreviewed workflow or baseline changes. No broad issue receives
an automatic closing keyword simply because a smaller software contract now passes.

## #9: unknown means unknown, before any move

Previously `scripts/intake-downloads.py:classify` returned `diffusion_models` for every
header not recognized as LoRA/checkpoint/VAE/text encoder, including `{}` and arbitrary
unknown keys. `main` therefore moved such a file despite #9 explicitly requiring a
renamed unknown fixture and no silent fallback. Naming it like H3 was no proof of its
contents or companion requirements.

The classifier now returns `None` when there is no supported positive signature.
The existing fixture-backed `blocks.*` + `img_in.*` + `final_layer.*` backbone remains
recognized, including declared loader prefixes. Existing component/LoRA heuristics
remain hints, not authenticated model identification. A different diffusion family
without a reviewed signature intentionally stays unknown rather than inheriting the
old catch-all. Add positive fixtures before expanding automatic recognition.

`plan` attaches an actionable error to an unknown candidate; default intake skips it
before hashing, moving, writing receipts or creating destination folders. A mixed
batch can still handle recognizable candidates. Filename and metadata-title changes
do not turn unknown bytes into model evidence.

The plan and any resulting receipt carry a `folder_basis`:

| Value | Meaning |
| --- | --- |
| `header-hint` | Existing metadata/tensor-key heuristics suggested a storage role; no identity or loader compatibility was verified. |
| `unknown` | No supported signature; default intake preserves the candidate. |
| `unreadable-header` | Header inspection failed; default intake preserves the candidate. |
| `operator-selected` | The existing explicit `--dest-folder` override selected a destination without header classification. It does not certify even the container contents. |

Receipts retain `verified: false`, `expected_sha256: null` and an observed local hash;
`runtime_compatible` is explicitly null. Stubs do not invent a source, base family,
license or immutable pin from a filename. The override still deliberately bypasses
header inspection, as the existing `test_fetch_scripts.py` contract requires; use it
only after reviewing the actual source and intended folder.

### Operator path

```sh
python scripts/intake-downloads.py --dry-run
# Review an isolated candidate's source and intended role before selecting an override:
python scripts/intake-downloads.py --from /path/to/reviewed-candidate --dest-folder diffusion_models --dry-run
# Omit --dry-run only for an explicit move after that review.
```

Use a directory containing only reviewed candidates when overriding: `--dest-folder`
applies to the entire selected batch, not just its unknown members. This work does not
load weights, import custom nodes, submit a graph, download anything or infer permission.
The older check-then-move publication path is not made transactional by this change;
its concurrency, source-mutation and durable-receipt follow-up is #140. Do not equate
the existing-destination test with proof against a destination appearing mid-move.

## Tests and evidence boundary

New suite: `tests/test_intake_unknown.py`, **15 tests**, all passing in the local focused
source fixture. The original script was reconstructed byte-for-byte and matched Git
blob `8685cb1c51a50e07929baa9b2f5b64418c0d060b`; it fails the new unknown-preservation
and explicit-basis contracts. The local runner substitutes only the read-only folder
registry because it cannot clone the private checkout. It is not full-repository proof.
The committed tests import the actual `model_library` and run in the existing hosted CI.

Coverage includes misleading H3/SDXL names, empty and partial signatures, known roles,
LoRA precedence, loader prefixes, default/dry-run non-mutation, mixed batches, explicit
operator selection, unchanged header-bypass behavior, existing destinations and receipts
that do not claim identity, compatibility or source verification. Files are synthetic
headers in temporary directories, not real models or generated assets.

```sh
python -m unittest discover -s tests -p test_intake_unknown.py -v
python -m unittest discover -s tests -p test_fetch_scripts.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

PR #137 additionally carries 11 causal startup tests, a host-independent repair to the
legacy backend fault fixtures, and explicit Windows coverage for the new suite. Its
first Linux CI passed; initial Windows CI exposed the old fixtures' real process-table
scan, which was isolated without weakening production checks. Both workflows passed
at `1ba6f2e0ec73baa9b1566ccd9eebfc5726a5e172`.

No workstation deployment, GPU run, art acceptance or system change occurred in this
pass. Human creative choices are not reopened. The owner-controlled Windows restart
for the configured page file remains a separate local execution step, with fresh
headroom measurement required afterward; this checkpoint does not authorize it.

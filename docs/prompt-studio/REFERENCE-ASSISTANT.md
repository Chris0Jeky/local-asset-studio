# Run the local reference assistant

For the browser path, use [Analyze pictures in Prompt Lab](REFERENCE-ANALYZE-UI.md).
This CLI remains independent of Studio scheduling; do not run it concurrently
against the same helper.

This is the operator/agent entry point for the
[reference-intelligence design](REFERENCE-INTELLIGENCE.md). It describes up to
four images in one local vision call, preserves metadata separately and creates
an editable, source-bound intent. It does not generate an image or replace the
Studio UI. The shared **Analyze references** UI and board-aware setup application
remain under #35/#38/#232/#328.

## Before using a real model

Use a disposable job workspace containing copies of the intended references. An
already-installed local vision model must be served by the existing Ollama
loopback endpoint. Use its exact installed name. No command below pulls a model,
uses a hosted fallback, upgrades Comfy/ROCm or starts a generation job.

The explicit `--idle-confirmed` flag is an operator declaration, not a scheduler
reservation. Do not run alongside a generation worker using the same GPU. A future
web Analyze command must use #35/#178 admission rather than copying this flag into
an HTTP request. The helper requests unload after the response; actual resource
release still needs workstation observation. Four-image semantic quality and
Windows/9070 XT memory/latency have not been measured by these software tests.

Examples below use a portable workspace named `reference-session` under the
repository root, containing `refs/style.png` and `refs/pose.png`. Run from the
repository root; replace `INSTALLED_VISION_MODEL` with the exact installed local
model name. Output files must not already exist. In PowerShell, bind the workspace
once so the same commands work regardless of the repository's drive or parent
folder:

```powershell
$Workspace = Join-Path (Get-Location) 'reference-session'
```

## Minimal path

Capture the originals and a short instruction. `--brief` may be empty. Omitting
all `--role` arguments lets the model propose each image's primary contribution;
use one role per image to provide an explicit hint instead.

```powershell
python -m studio_prompt.reference_assistant init --workspace "$Workspace" --image refs/style.png --image refs/pose.png --brief "same feeling, use this pose" --output (Join-Path $Workspace 'request.json')
```

Optional deterministic metadata inspection uses the existing PNG/JPEG/WebP
recipe inspector. Recovered claims are not passed to the vision model or treated
as authenticated original settings. There is no inference in this step.

```powershell
python -m studio_prompt.reference_assistant inspect --workspace "$Workspace" --request (Join-Path $Workspace 'request.json') --output (Join-Path $Workspace 'metadata.json')
```

Explicit analysis sends all selected images in **one** request. The shared helper
checks the installed model digest, uses the same workspace lock and cache, and
never retries a failed/ambiguous response automatically. Exact-request caching is
on for this CLI. By default, derived local data is stored under
`<workspace>/.runtime/prompt-cache/`; treat that directory as disposable cache
evidence rather than an input/reference folder. `--no-cache` disables both lookup
and insertion for the call. A changed model, input, description, reference order,
role hint or request template invalidates reuse. The existing 64-entry cache cap
remains; eviction is explicit.

```powershell
python -m studio_prompt.reference_assistant analyze --workspace "$Workspace" --request (Join-Path $Workspace 'request.json') --model INSTALLED_VISION_MODEL --idle-confirmed --output (Join-Path $Workspace 'analysis.json')
python -m studio_prompt.reference_assistant review --analysis (Join-Path $Workspace 'analysis.json') --output (Join-Path $Workspace 'review.json')
```

Read `analysis.json`: summary, assumptions, questions and each image's description,
tags, facets and unknowns. Then review `review.json`. Default selections contain
only role-compatible, non-uncertain facets; tags are not automatically transferred.
For example, retain palette/style from the first image and action/composition from
the second. To change a description, add an override inside that selection:

```json
"overrides": {"palette": "cool blue and silver instead of the observed warm colours"}
```

The edited facet must also be listed in that selection's `facets`. Tags must be
selected explicitly from the suggested vocabulary. Role changes are allowed in
this user review, but the selected facets must fit the new role. Uncertain facets
require an explicit user description. Edit the review rather than changing the
immutable analysis report; modified/stale reports are rejected.

```powershell
python -m studio_prompt.reference_assistant draft --workspace "$Workspace" --analysis (Join-Path $Workspace 'analysis.json') --review (Join-Path $Workspace 'review.json') --output (Join-Path $Workspace 'draft.json')
```

`draft.json` contains a standard CreativeIntent at `intent`, plus source/analysis
hashes, the review, attributed transfers, assumptions and unresolved questions.
Every original is rehashed before the new draft is emitted. Existing Studio
projects/drafts are untouched. A blank initial brief uses the reviewed summary;
a supplied brief retains its original wording. It is safe to change the **new**
intent through the existing Prompt Lab editing/revision flow after inspection.

For headless callers the shared compiler can consume the intent directly:

```python
from pathlib import Path

from studio_prompt.schema import read_json, write_new
from studio_prompt.compiler import compile_brief

workspace = Path('reference-session')
reviewed = read_json(workspace / 'draft.json')
# This profile formats text; it is NOT a reference-binding or generation action.
compiled = compile_brief(reviewed['intent'], 'sdxl-prose-v1')
write_new(workspace / 'compiled-preview.json', compiled)
```

Inspect the compiler's errors/warnings/reference requirements. Do not drop a
reference just to make a text-only binding succeed. Use an actual compatible
registered recipe and the existing reviewed setup/Production commands; no native
binding is fabricated here. A three-image style board plus pose and a native
three-slot Qwen edit are different contracts. Unresolved choices in the receipt
are not silently resolved by exporting only its intent.

## Boundaries and recovery

Each source is at most 8 MiB, at most 16 MiPixels and one frame during vision
preparation. The existing helper applies EXIF orientation, white transparency
matte, RGB conversion and a maximum 768-pixel side. It strips metadata and paths
from model input and records source/derivative hashes and analysis dimensions.
Small details lost at this scale belong in unknowns or a separately scoped crop
study, not a confident anatomy verdict. Alpha-hidden colours are not evidence.

No image is truncated out of the set, no contact-sheet fusion is substituted and
no image-generation retries are added. Failures return exit code 2 with an error.
A lost response is not retried. The shared lock is released only by its owner.
A known existing output is rejected before inference; a later filesystem failure
can still prevent delivery, so inspect the optional cached result before deciding
on a new call. Cache hits record zero new inference calls; historical latency in
the cached evidence describes the original call. Hashes are integrity evidence,
not proof of a trusted model server or a human's artistic approval.

`inspect` preserves embedded metadata claims without executing embedded graphs.
It is not a pixel decoder and is not visual description. The pre-existing recipe
intake APIs also handle explicit hash-bound sidecars; this CLI's batch inspect
command currently exposes media-only intake.

## Verification

The contract, real image preparation, real loopback HTTP fixture and CLI init /
analysis dispatch / review / edited-draft / subprocess path passed 43 focused
Python 3.13 tests with ResourceWarnings treated as errors. Only synthetic images
and a fake model response were used. The four additional metadata integration
tests need the full repository parser dependency set and are covered by hosted CI,
not the isolated local source-subset run. Existing Prompt Studio tests in hosted
CI cover the unchanged default brief-helper operation, compiler and HTTP seams.
No real VLM, GPU, native image generator or artwork acceptance was exercised.

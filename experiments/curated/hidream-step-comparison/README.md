# HiDream same-seed step study

Refs #2. This freezes the missing 8-versus-20-step comparison, using the existing
`hidream-o1-concept` preset and isolated backend. Both recipes pin the API template
SHA-256, prompt, empty negative prompt, seed `2026091131`, CFG 5 and 2048 x 2048
resolution. Only `steps` differs. The template fixes full-model FP8 loading, SDPA,
dynamic image selector `"0"`, force offload and disabled automatic downloads.
This is a single-seed study, not a quality benchmark or a new default.

## 25 October 2026 attempt: incomplete

Explicit switching started the isolated endpoint, and both HiDream graphs passed
its live schema check. While the eight-step job was running, switching to primary
was refused with HTTP 400, `Finish or reconcile active Studio work before switching
backends`. No primary process was started.

The eight-step request `9539f3a2-f0ed-5887-8ff0-c528297f1567` retained prompt
`86d4c40c-dba4-4908-8ca5-79c07552b998`. The isolated process then exited with
`Windows fatal exception: access violation`, code `0xC0000005`, during model
loading. Its stack passes through Torch storage indexing and
`_load_single_safetensors_direct`; this identifies the crash site, not its cause.
Studio recorded three failed history reads and left the job **uncertain**, with
no resubmission and no final output available for inspection. There is no completed
render time. The 20-step and subsequent reference-edit trials were not submitted.

The manifest retains the original ticket identity, job/prompt IDs and crash-log
hash. The original ticket and job receipts remain in ignored local directories.
Recover or explicitly reconcile that prompt before any further generation or
switch. Do not use a new ticket to retry this uncertain attempt. Issue #2 remains
open; the following commands describe the intended study on a stable runtime.

## Execute serially through Studio

Start the ordinary Studio for this checkout. In Models & setup explicitly switch
to **HiDream O1 · isolated** and wait for endpoint readiness. The backend manager
checks every managed queue and refuses active or unresolved work; never bypass
that refusal or start a second model family. Endpoint readiness is not inference
success. Preparation submits nothing:

```powershell
python -m studio_workflow prepare --recipe experiments/curated/hidream-step-comparison/recipe-8.json --out .runtime/hidream-8-ticket.json
python -m studio_workflow run --ticket .runtime/hidream-8-ticket.json --approve --out .runtime/hidream-8-dispatch.json
```

Observe the returned job ID with `python -m studio_workflow wait JOB_ID`. Retain
the job and prompt IDs, full history, final SaveImage PNG path and elapsed time.
Only after that job completes and its final output is inspected:

```powershell
python -m studio_workflow prepare --recipe experiments/curated/hidream-step-comparison/recipe-20.json --out .runtime/hidream-20-ticket.json
python -m studio_workflow run --ticket .runtime/hidream-20-ticket.json --approve --out .runtime/hidream-20-dispatch.json
```

Observe and inspect that output too. Compare the compass/hand structure, face,
coat details, village geometry and prompt adherence at full resolution. Record
cold loading separately from warm inference; sequential wall times alone do not
measure step cost. A timeout, partial result or missing prompt ID means inspect
the retained ticket, job and backend history; never create replacement work to
discover whether submission happened. Existing output paths deliberately refuse
overwrite. Reusing a retained ticket recovers its original request identity.

After comparison, a separate `hidream-o1-edit` trial can use one retained final
PNG as its staged reference. Retain its reference hash, exact recipe and output
inspection separately. The earlier eight-step lantern restyle is already
recorded in [HIDREAM.md](../../../docs/HIDREAM.md); it is not a step comparison.

## Evidence boundary

See `manifest.json` for this attempt's actual outcome. Final binaries stay in the
isolated ComfyUI output directory, ticket/job evidence in ignored runtime/run
directories. No generated media belongs in this curated source folder.

Verification: the new comparison test failed on the unfixed checkout with
`Missing frozen HiDream comparison recipe` (one failure), then passed after the
recipes were added (one test). `python scripts/validate-repo.py` passed: 93 preset
graphs/bindings and 187 pinned assets. The live HiDream schema check passed both
graphs. `python -m unittest discover -s tests` was stopped at its 25-minute budget
after 1,506 seconds, before a final summary; the full suite is **not verified**.
Its local log and bounded-run receipt are in `.runtime/issue-2-full-suite*`.

The Torch 2.9.x model warning and historical primary-process native transition
crash remain unresolved. Passing recipe checks, starting an endpoint or completing
a render does not resolve either. Generation, visual inspection, owner art
acceptance and licensing are separate states; owner choices remain in
[HUMAN_TODO.md](../../../HUMAN_TODO.md).

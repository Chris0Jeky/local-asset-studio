# AV preview output verification — 26 October 2026

## Outcome

A preview can be confirmed only after its decoded video frame count and video-track
duration match the project. A matching audio or container duration cannot confirm
missing, sparse or retimed picture frames. Failed verification retains the render
directory, plan, media, logs and `.incomplete` marker, and writes no success receipt.

This is the output-verification follow-up to [PR #1656](https://github.com/Chris0Jeky/local-asset-studio/pull/1656).
That PR bounds source trims, scene intake and added shots by the input video track.

## Reconciled source

The reviewed input-duration candidate is
`8c56da3bcfa514fc35e34705b37949f2f11ba4b1`, based on main
`7a89410d34c2580c3b9d47ffd806193e006d4069`. Its tree is
`46ef7ae7d7aa8f160a4502c0851c8ee1f708527d`; the hosted merge preview
`c2893df67b1bfdcfc756c4a1cfdee069b4eb3ad5` has the same tree and the expected
main/head parents. All five changed file blobs were verified before reconstructing
that baseline locally.

An independent native check of that unchanged input-duration source passed all
41 tests in `test_studio_av.py` in 6.840 seconds. The output fault below still
completed falsely, so the follow-up is a separately reproduced gap.

## Causal failure and correction

The first reproducer used a valid 72-frame, three-second project, then injected a
one-second, 24-frame picture into the rendered preview while keeping its full
three-second audio. An independent FFprobe count reported 24 video frames and a
one-second video track, while the container reported three seconds. The old verifier
returned a receipt claiming 72 expected frames, wrote `receipt.json`, and removed
`.incomplete`.

The committed tests inject faults at the picture-render boundary and let the real
muxer produce the final preview:

| Picture fault | Video frames | Video duration | Audio/container duration | Required refusal |
| --- | ---: | ---: | ---: | --- |
| Short: 24 fps for one second | 24 | 1 s | 3 s | Frame count mismatch |
| Sparse: 8 fps for three seconds | 24 | 3 s | 3 s | Frame count mismatch |
| Sped up: 48 fps for 1.5 seconds | 72 | 1.5 s | 3 s | Video duration mismatch |
| Decoded count unavailable after probing valid output | Unavailable | 3 s | 3 s | Frame count mismatch |

The sparse case prevents a duration-only correction from passing. The sped-up case
prevents a frame-count-only correction from passing. Successful controls cover
24 fps and 30000/1001 fps.

The three new tests produced four expected failures against unchanged PR #1656
source; both valid controls already passed. After the correction, in-memory
mutations that removed just the frame guard produced three failures, and removing
just the video-duration guard produced one failure. The production source was not
modified by those mutation runs.

## Implementation and bounds

The shared probe gains an optional decoded-frame count, used only for the generated
preview. Existing input probing keeps its behavior. The final verifier requires
exactly the planned frame count and a finite, positive video-track duration within
one audio sample of the planned duration. The existing audio-sample and container
duration checks remain.

The output probe retains the constrained MP4 demuxer, disabled external data
references, 20-second process timeout and 1 MiB output cap. Project previews remain
bounded by their existing 120-second, frame and pixel limits. Decoding can therefore
refuse an output if it exceeds the existing probe budget; it cannot confirm output
whose frames were not counted. The resulting probe facts are retained in the
existing receipt.

## Local verification

From the complete reconciled checkout:

- `python -m unittest discover -s tests -p "test_studio_av*.py" -v`:
  **46 tests in 10.746 seconds, two skips** for the optional MCP 2.2 SDK.
- `python -m unittest discover -s tests -p test_av_projects.py -v`:
  **25 tests in 6.581 seconds, successful**, including real scene rendering and
  the loopback HTTP contract.
- The first scene run exercised all 25 tests and had one environment error:
  the sandbox refused creation of the loopback socket. Its log is retained;
  the permitted loopback rerun above passed without source or assertion changes.
- Valid and refused output tests check actual FFprobe results, retained incomplete
  artifacts, absence/presence of the success receipt, and unchanged source bytes.
- Repository validation passed: **93 preset graphs/bindings, 187 pinned assets,
  4,460 tracked paths**. The staged diff passed the whitespace check.

Local causal logs are under ignored `.runtime/av-output-qc/`: `before-guards.log`,
`after-guards.log`, `av-complete.log`, `scene-contracts.log`,
`scene-contracts-loopback.log`, and the two `without-*-guard.log` mutation records.

## Hosted evidence and remaining qualification

PR #1656's [full-suite job](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40335280121/job/121615061056)
passed 6,107 tests in 1,005.395 seconds with 76 skips and clean lifetime shutdown.
Validation checked 93 preset graphs/bindings, 187 pinned assets and 4,458 tracked paths.
Those results qualify its input-duration tree, not this subsequent output change.

The original [Studio AV job](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40335280135/job/121615060627)
exhausted its ten-minute job budget during slow Ubuntu package downloads, before AV
tests or the demo ran. That installation cancellation is retained as an environment
failure. The unchanged-head [second attempt](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40335280135/job/121668475155)
passed **43 AV tests in 5.039 seconds with no skips**, then rendered the demo and
generated the workbench. Its checkout remained the same qualified merge preview
`c2893df67b1bfdcfc756c4a1cfdee069b4eb3ad5`.

The follow-up requires its own fresh hosted full suite, validator and applicable
AV/platform workflows, and a merged-tree comparison. Those results belong in the
follow-up PR's qualification record.

No model download, installed-runtime modification, ComfyUI submission or GPU
generation occurred. Synthetic CPU media tests establish software behavior;
creative acceptance and the owner choices in `HUMAN_TODO.md` remain open.

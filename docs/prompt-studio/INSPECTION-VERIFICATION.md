# Recipe-inspection verification — 12 September 2026

## Baseline and coordination

The uploaded snapshot was compared with the live repository, not assumed current.
Its Git tree exactly matched main `2b911092e889687cd5d247da106f9de0c8348d99`:
`afe71d1fb3406ec69af7a4bde3399d07805c59b3`. This includes the merged character-edit
bridge #78. The slice was reserved in issue #36 with no open PRs at that point.
A later check found #79, the separate failed-job timing fix; none of its server
implementation work is repeated here.

## Executed checks

Environment: Linux, Python 3.13.5, Pillow 12.3.0, Node available. No package changes,
model downloads, paid services, GPU calls or workstation configuration changes.

| Check | Observed result |
| --- | --- |
| Uploaded baseline full suite | 776 discovered; 769 passed, 7 skipped |
| Changed full suite | 819 discovered; 812 passed, 7 skipped; 108.627 seconds |
| `test_studio_prompt*.py` | 109 passed; includes all 41 new provenance/demo tests |
| Actual localhost HTTP route tests | 6 passed; real PNG/JPEG/WebP with sidecar, malformed input, existing guards, no jobs |
| Node frontend behaviour | Passed startup/error and out-of-order metadata success/error checks |
| JavaScript syntax | `node --check app/static/prompt-lab.js` passed |
| Repository validator | Passed: 60 preset graphs/bindings, 62 pinned assets, 65 LoRA names |
| Whitespace check | `git diff --cached --check` passed |

The full suite emitted the pre-existing Pillow `getdata` deprecation, the deliberate
unknown-recipe fixture message, and an unclosed-socket ResourceWarning. It was not
warning-free. Skip counts are environment-dependent and are not Windows results.
The existing Prompt Studio CI glob automatically discovers the new tests on both
configured operating systems; hosted CI status belongs to the PR, not this local
record.

Fault cases include ambiguous outputs, unused prompts, separate refinement stages,
output-slot-specific ControlNet conditioning, ZeroOut, unknown operators, dynamic
text, missing links/cycles, diamond DAGs, byte/report fan-out caps, duplicate keys,
conflicting records, malformed/truncated containers, EXIF offset/cycle attacks,
opaque encodings, literal XMP entities, exact sidecar binding, exclusive output
writes and zero Studio access during metadata dispatch.

## Browser evidence boundary

Chromium 144.0.7559.96 rendered the actual changed HTML/JS at 1280×900 and 390×844.
All four format selections returned the expected reports, there were no page
errors or horizontal page overflow, keyboard focus reached the file control, and
only profiles/metadata operations occurred. The browser used a direct-dispatch
fetch fixture: this container blocks browser navigation to localhost. Real HTTP
transport and Host/Origin behaviour were exercised separately by the six server
tests, not asserted from the browser fixture. No installed Windows browser/native
application or real Comfy inference was exercised.

## Reproduce

```sh
python -m unittest discover -s tests -p 'test_studio_prompt*.py' -v
python -m unittest discover -s tests -p 'test_prompt_startup.py' -v
node tests/prompt_lab_frontend.cjs
python -m unittest discover -s tests
python scripts/validate-repo.py
python examples/prompt-studio/recipe-inspection/create_demo.py NEW_OUTPUT_DIRECTORY
```

The demo emits six files and demonstrates a fabricated graph and conflicting
sidecar without generation. Read [RECIPE-INSPECTION.md](RECIPE-INSPECTION.md) for
the supported contract and remaining #36 work. No HUMAN_TODO.md creative choice
was made or marked complete; model reproduction, native integration and artistic
acceptance remain distinct gates.

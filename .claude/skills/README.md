# Local Asset Studio Claude skills

Canonical repo-local skills. `../../.codex/skills/` carries the same bodies with Codex frontmatter and an
`agents/openai.yaml` each; `tests/test_agent_harness.py` fails when a body drifts. Change here first, then
port the body verbatim in the same commit. Skills trigger by description; none re-mandates auto-loaded files.

| Skill | Use it for | Proving check |
| --- | --- | --- |
| `studio-preset-slice` | add or change a preset, API/visual graph, binding or variant | `validate-repo.py`, `tests.test_server` |
| `studio-execution-evidence` | one real generation or comparison, recorded honestly | inspected outputs + prompt ID in `experiments/curated/` |
| `studio-native-adapter` | Krita, Blender, Godot, articulated-prop export paths | the adapter's own `tests.test_*` module |
| `studio-runtime-models` | backend environments, launchers, ports, model pins, licence terms | `tests.test_backends`, `tests.test_model_library`, `validate-repo.py` |
| `studio-session-closeout` | end of session: owned processes, closeout note, state, handoff | closeout note in `.runtime/`, clean `git status` |

Global process skills (`resume-repo-work`, `small-safe-slice`, `review-and-ship`, `verify-and-handoff`)
own orientation, the implementation loop, review and handoff; the skills here add only what is Studio-specific.

# Local Asset Studio Codex skills

Adapters of the canonical `../../.claude/skills/*`: same body, Codex frontmatter, plus `agents/openai.yaml`.
Change the Claude tree first and port the body verbatim in the same commit; `tests/test_agent_harness.py`
fails on drift. Invoke with `$studio-<name>`. Use the smallest set that matches the task.

| Skill | Use it for | Pair with |
| --- | --- | --- |
| `studio-preset-slice` | add or change a preset, API/visual graph, binding or variant | `docs/OPERATIONS.md`, `scripts/validate-repo.py` |
| `studio-execution-evidence` | one real generation or comparison, recorded honestly | `CURRENT_STATE.md`, `experiments/curated/` |
| `studio-native-adapter` | Krita, Blender, Godot, articulated-prop export paths | the adapter's tests in `tests/` |
| `studio-runtime-models` | backend environments, launchers, ports, model pins, licence terms | `models/README.md`, `runtime-patches/README.md` |
| `studio-session-closeout` | end of session: owned processes, closeout note, state, handoff | `.runtime/closeout-*.md`, `HUMAN_TODO.md` |

Global managed skills (`resume-repo-work`, `small-safe-slice`, `review-and-ship`, `verify-and-handoff`)
own orientation, the implementation loop, review and handoff.

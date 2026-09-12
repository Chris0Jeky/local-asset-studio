# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Tier: daily-driver (T2) — authority: push free / merge free. Declared in `.agent-harness/tier.json`; read it live.
Global laws auto-load from `~/.claude/CLAUDE.md`; nothing global is restated here. `AGENTS.md` is the Codex adapter.

## What this is

Local Asset Studio: a loopback-only Python web UI (stdlib `ThreadingHTTPServer`, port 8191) over a locally
installed ComfyUI, plus offline planners and finishing scripts for game assets. One user, one Windows PC with
a Radeon, no deploy, no other consumers. Models, ComfyUI and generated outputs live outside Git by design.
`CURRENT_STATE.md` separates executed evidence from plans; read its head before touching runtime setup.

## Run it

```bash
python -m unittest discover -s tests          # 212 tests, ~3 s, offline (one Windows symlink skip)
python scripts/validate-repo.py                # catalog/graph bindings, model pins, Git payload rules, ~1 s
python app/server.py --repo-root .             # needs config/local.json (copy config/example.json); ComfyUI on 8188
```

On the configured PC use `Start Studio.cmd` or `scripts/Start-Studio.ps1` (starts ComfyUI if needed, opens
`http://127.0.0.1:8191`). Restart the server to reload `presets/catalog.json`. No build step, no linter, no
package manager: Python 3.12 + Pillow/psutil; plain JS in `app/static/` with a vendored model-viewer.

## Proving checks (narrowest command per seam)

| Changed seam | Command |
| --- | --- |
| `app/<module>.py` | `python -m unittest tests.test_<module>` (`test_server` covers routing; `FakeStudio` fakes ComfyUI) |
| `presets/**`, `workflows/**`, `models/library.json` | `python scripts/validate-repo.py`; graph nodes against a running ComfyUI: `python scripts/validate-live.py` |
| `app/static/*.js` | `node --check app/static/app.js` then `python -m unittest tests.test_frontend_handoffs` (skips without Node) |
| `scripts/game_asset_*.py`, `research/game-assets/**` | `python -m unittest discover -s tests -p "test_game_asset_*.py"` (own CI lane) |
| `scripts/krita_roundtrip.py`, `godot_asset_adapter.py`, `articulated_prop.py` | `tests.test_krita_roundtrip`, `tests.test_godot_asset_adapter`, `tests.test_articulated_*` |
| `CLAUDE.md`, `AGENTS.md`, `.claude/**`, `.codex/**`, `tier.json` | `python -m unittest tests.test_agent_harness` (budgets + Claude/Codex skill parity) |
| Docs only | nothing to run; `validate-repo.py` still guards the Git payload |

CI (`.github/workflows/check.yml`) runs the full suite plus `validate-repo.py` on every push and PR.

## Architecture

**Preset → graph binding is the core contract.** `presets/catalog.json` maps each human control (`positive`,
`seed`, `width`, `lora`, `reference`, `frames`, ...) to a `[node_id, input_name]` pair in an API graph under
`workflows/api/`; `bindings_extra` fans one control out to several inputs. The catalog is the allow-list: the
server writes only inputs named there, and `Studio.catalog()` reads authored graph values back as UI defaults.
`workflows/comfyui/` holds matching visual graphs (`visual` key). Adding a preset: `docs/OPERATIONS.md`.

**`app/server.py`**: `Studio` owns state; `Handler` routes `/api/*` by prefix in `do_GET`/`do_POST` behind a
loopback Host and same-origin check. `prepare()` validates and binds; `_work()` is the single daemon worker
that submits to ComfyUI, polls `/history`, and persists jobs under `experiments/runs/<job-id>/` with the exact
submitted graph. `_request()` is the sole HTTP seam to ComfyUI.

**Siblings**, each wired into `Studio`, each unit-tested: `backends.py` (explicit switches between `primary`
8188, `hidream` isolated 8192, `h3` mmap loader 8194; state in `.runtime/backend-state.json`; presets carry
`backend_id`), `workspace.py` (SQLite asset Workspace, content-addressed store, reversible trash),
`production.py` (budgeted comparisons; `fingerprint()` is a plan's identity), `references.py` (reference
roles + provenance), `native_exports.py` / `articulated.py` (Krita/Godot/Blender jobs driven only through
paths in `config/local.json`), `model_library.py` (checksum-pinned inventory from `models/library.json`).

**Game-asset lane** (`scripts/game_asset_*.py`, `research/game-assets/`, `docs/game-assets/AGENT-CONTRACT.md`)
is a separate offline planner and receipt checker: plans are hash-identified and never mutated mid-run.

## Pitfalls (each already cost a session)

- Never auto-submit a generation on page load; never re-submit a job whose outcome is uncertain. Keep the
  prompt ID and the full recipe; a lost prompt ID is evidence lost, not a reason to run again.
- A completed render is neither art acceptance nor licence clearance. Hunyuan3D 2.1 and HY-Motion 1.0 exclude
  UK use; NoobAI excludes commercial products; WAI hashes do not authenticate its creator. Record, never infer.
- Never edit installed ComfyUI or upgrade packages in the shared Torch/ROCm runtime; local patches go to
  `runtime-patches/` with before/after hashes. Backend switches are explicit and never package upgrades.
- Form values serialize as strings: validate with `number()` (Decimal, finite, range) — a `100 ms` bug shipped once.
- `.runtime/` is gitignored evidence (logs, pidfiles, probes, review JSON). Read it; do not commit it.
- Stop only Studio-owned PIDs, and only after confirming no queued, running or partial Studio work.
- Code style is dense (one-line `if ...: return`, semicolon-joined statements). Match the file; do not reformat.
- A second, stale checkout (at PR #7) exists under the user's `source/` folder. Work only in this one.

## Repo-local skills and rules

`.claude/skills/` (canonical; `.codex/skills/` is the Codex adapter, body-identical, parity-tested):
`studio-preset-slice`, `studio-execution-evidence`, `studio-native-adapter`, `studio-runtime-models`,
`studio-session-closeout`. Path rules auto-load from `.claude/rules/` for catalog and evidence-doc edits.
`HUMAN_TODO.md` holds subjective creative choices: surface them in every summary, never tick them.

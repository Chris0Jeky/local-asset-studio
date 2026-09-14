# CLAUDE.md

Tier: daily-driver (T2) — authority: push free / merge free. Declared in `.agent-harness/tier.json`; read it live.
Global laws auto-load from `~/.claude/CLAUDE.md`; nothing global is restated here. `AGENTS.md` is the Codex adapter.

## What this is

Local Asset Studio: a loopback-only Python web UI (stdlib `ThreadingHTTPServer`, port 8191) over a locally
installed ComfyUI, plus offline planners and finishing scripts for game assets. One user, one Windows PC with
a Radeon, no deploy, no other consumers. Models, ComfyUI and generated outputs live outside Git by design.
`CURRENT_STATE.md` separates executed evidence from plans; read its head before touching runtime setup.

## Run it

```bash
python -m unittest discover -s tests          # 1674 tests, 2-3 minutes, offline; budget minutes, not seconds
python scripts/validate-repo.py                # catalog/graph bindings, model pins, Git payload rules, ~1 s
python app/server.py --repo-root .             # needs config/local.json (copy config/example.json); ComfyUI on 8188
```

On the configured PC use `Start Studio.cmd` or `scripts/Start-Studio.ps1` (starts ComfyUI if needed, opens
`http://127.0.0.1:8191`). Restart the server to reload `presets/catalog.json`. No build step, no linter, no
package manager: Python 3.12+ (CI pins 3.12; this PC's shell runs 3.14) + Pillow/psutil; plain JS in `app/static/`
with a vendored model-viewer. Skips are environment-dependent (54 on 13 Sep 2026; fewer with FFmpeg/Godot/Node on `PATH`).

## Proving checks (narrowest command per seam)

| Changed seam | Command |
| --- | --- |
| `app/<module>.py` | `python -m unittest discover -s tests -p "test_<module>.py"` (`test_server` covers routing; `FakeStudio` fakes ComfyUI) |
| `presets/**`, `workflows/**`, `models/library.json` | `python scripts/validate-repo.py`; graph nodes against a running ComfyUI: `python scripts/validate-live.py` |
| `app/static/*.js` | `node --check app/static/app.js` then `python -m unittest tests.test_frontend_handoffs` (skips without Node); when clicks or steps move, `python tests/studio_use_cases.py` (Playwright, ~40 s) and compare with `docs/UX-USE-CASE-MATRIX.md` |
| `scripts/game_asset_*.py`, `research/game-assets/**` | `python -m unittest discover -s tests -p "test_game_asset_*.py"` (own CI lane) |
| `scripts/krita_roundtrip.py`, `godot_asset_adapter.py`, `articulated_prop.py` | `tests.test_krita_roundtrip`, `tests.test_godot_asset_adapter`, `tests.test_articulated_*` |
| `CLAUDE.md`, `AGENTS.md`, `.claude/**`, `.codex/**`, `tier.json` | `python -m unittest tests.test_agent_harness` (budgets + Claude/Codex skill parity) |
| Docs only | nothing to run; `validate-repo.py` still guards the Git payload |

Use the `discover -s tests -p` form by default: any module that imports a sibling test or fixture unqualified
(`rg "^(from|import) (test_|review_fixture)" tests`) dies on import as `python -m unittest tests.<name>`; measured
14 Sep 2026 that is 49 of 130 modules, including `test_production`, `test_backends`, `test_review_desk`,
`test_voice_baseline`, `test_failed_job_timing` and part of each `test_workflow_*`/`test_character_*` family. Eight `app/` modules have no same-named test file:
`articulated.py` → `test_articulated_operation`, `backend_contracts.py` → `test_backend_safety`, `download_contracts.py` →
`test_model_install_safety`/`test_model_redirects`, `review_media.py` → `test_review_desk`, `host_memory.py` → `test_server`,
`model_requirements.py` → `test_preset_model_readiness`, `project_storage.py` → `test_production_storage`, `submission_evidence.py` → `test_submission_recovery`.

CI: `.github/workflows/check.yml` runs the full suite plus `validate-repo.py` on every push and PR; 19 further
path-filtered lanes in the same folder (browser drivers, graph validation, model intake/readiness, workflow MCP, …) run
only when their files change. Agent tooling outside the Studio (comfy-cli, comfy-mcp, skills): `docs/AGENT-TOOLING.md`.

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
- Never edit installed ComfyUI or upgrade packages in the shared Torch/ROCm runtime; local patches go to `runtime-patches/`
  with before/after hashes. Backend switches are explicit, never package upgrades; comfy-mcp's update/install/download/launch/stop tools are read-only use only (`docs/AGENT-TOOLING.md`).
- Form values serialize as strings: validate with `number()` (Decimal, finite, range) — a `100 ms` bug shipped once.
- `.runtime/` is gitignored evidence (logs, pidfiles, probes, review JSON). Read it; do not commit it.
- Stop only Studio-owned PIDs, and only after confirming no queued, running or partial Studio work.
- Code style is dense (one-line `if ...: return`, semicolon-joined statements). Match the file; do not reformat.
- A second, stale checkout (at PR #7) exists under the user's `source/` folder. Work only in this one.
- Import `app/` siblings by bare name, never `from app import x`: under the launcher's embedded Python, ComfyUI's own regular `app` package shadows this directory whatever the path order, and the Studio does not start (PR #341).

## Repo-local skills and rules

`.claude/skills/` (canonical; `.codex/skills/` is the Codex adapter, body-identical, parity-tested):
`studio-preset-slice`, `studio-execution-evidence`, `studio-native-adapter`, `studio-runtime-models`,
`studio-session-closeout`. Path rules auto-load from `.claude/rules/` for catalog and evidence-doc edits.
`HUMAN_TODO.md` holds subjective creative choices: surface them in every summary, never tick them.

## PR issue disposition

Every PR names each affected issue: `Closes #N`/`Fixes #N` only for complete acceptance, otherwise
`Refs #N` plus what remains; list each closure separately. Closing keywords act even in quoted or
negated prose, so never use them for partial work. Reconcile before merge and verify GitHub after:
merged code, tests, generation or creative review never alone closes a broader issue.

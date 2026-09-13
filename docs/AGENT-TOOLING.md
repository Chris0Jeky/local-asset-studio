# Agent tooling for ComfyUI — Claude Code and Codex

Measured and configured on the owner's PC on 13 September 2026. This page records how the two coding
agents reach the local ComfyUI outside the Studio, which skills they carry, and what they must not do
with those tools. Studio's own agent surface (Workflow Studio MCP, AV and game-asset commands) is
documented under `docs/workflow-studio/`, `docs/av-studio/` and `docs/game-assets/`; this page is only
about the official Comfy toolchain.

## What is installed

| Piece | Where | Version | Notes |
| --- | --- | --- | --- |
| comfy-cli (`comfy`) | `C:\AI\agent-tools\comfy-mcp\Scripts\comfy.exe` (on `PATH`) | 1.20.0 (latest PyPI, 1 Sep 2026) | Own Python 3.13 venv, deliberately outside the shared ROCm runtime. Config `%LOCALAPPDATA%\comfy-cli\config.ini`. |
| comfy-mcp (`comfy-mcp`) | `C:\AI\agent-tools\comfy-mcp\Scripts\comfy-mcp.exe` | 0.10.0 (latest PyPI, 10 Aug 2026) | Comfy's first-party local MCP server; every tool wraps a `comfy` command with `--where local`. 39 tools. |
| Default workspace | `C:\AI\ComfyUI_windows_portable\ComfyUI` | set 13 Sep 2026 | Before this the default pointed at a non-existent `Documents\comfy\ComfyUI`; `comfy which` now reports the portable install. |
| Live server | `http://127.0.0.1:8188` | ComfyUI 0.35.0 | Auto-detected. Only the primary backend; the isolated HiDream (8192) and H3 (8194) environments need `COMFY_LOCAL_URL=http://127.0.0.1:<port>`. |

Both agents are wired to the same server binary:

| Client | Registration | Where declared |
| --- | --- | --- |
| Codex | `comfy-local` (stdio, `COMFY_BIN` env) and `comfy-cloud` (`https://cloud.comfy.org/mcp`, OAuth completed by the owner) | `~/.codex/config.toml`, user scope |
| Claude Code | `comfy-local` (stdio, `COMFY_BIN` and `COMFY_WHERE=local` env) | `~/.claude.json`, user scope (`claude mcp get comfy-local` → Connected) |

The repository carries no `.mcp.json` on purpose: the paths are machine-specific and the estate rule is one
declaration per server per runtime. The cloud connection is not registered for Claude; add it with
`claude mcp add -s user --transport http comfy-cloud https://cloud.comfy.org/mcp` and authenticate through
`/mcp` if Comfy Cloud runs are ever wanted.

## Skills

Three sources were compared on 13 September 2026:

| Source | What it is | Installed? |
| --- | --- | --- |
| comfy-cli bundled skills (`comfy skills install`) | `comfy`, `comfy-debug`, `comfy-relay`, `comfy-director`, `comfy-build`, `comfy-deploy`: the local CLI/MCP knowledge (envelope contract, routing, template → fragment → raw JSON hierarchy, job handling) | Yes, Claude `~/.claude/skills/` and Codex `~/.agents/skills/`; `comfy skills status` reports all `current` for the 1.20.0 package |
| [jtydhr88/comfyui-custom-node-skills](https://github.com/jtydhr88/comfyui-custom-node-skills) | nine `comfyui-node-*` skills for writing custom nodes against the V3 API (last upstream sync 27 Jul 2026, ComfyUI 0.28) | Yes, both scopes, byte-identical to upstream |
| [Comfy-Org/comfy-skills](https://github.com/Comfy-Org/comfy-skills) and [docs.comfy.org/agent-tools/skills](https://docs.comfy.org/agent-tools/skills) | the `comfy-cloud` Claude Code plugin (hosted MCP plus `/comfy-cloud:*` slash commands) and a frozen legacy command set; the CLI skills moved out of this repo into comfy-cli on 26 Aug 2026 | Not installed for Claude: it targets Comfy Cloud, and the owner generates locally |

The `comfy-build` copy in both scopes had drifted to an upstream-main version that documents
`comfy build release delete`, which 1.20.0 does not have; it was re-synced to the packaged copy so the skill
matches the installed CLI. Re-run `comfy skills install` after any comfy-cli upgrade and re-copy the six
`SKILL.md` files into `~/.agents/skills/` for Codex.

The `comfy knowledge` bundle (curated model picks) requires `comfy cloud login` in the venv; it is not signed
in and nothing here depends on it.

## Verified on 13 September 2026

Read-only probes through the MCP server against the running ComfyUI: `server_info`, `which`, `system_stats`,
`search_models` (`wai` → `waiIllustriousSDXL_v170.safetensors`) and `nodes` (`FaceDetailer` from the Impact
Pack) all returned `ok` envelopes. No workflow was submitted through the MCP server, so `run_workflow`,
`upload_file` and `fetch_outputs` are installed-and-listed, not proven.

## Rules for these tools in this repository

These tools reach the shared portable ComfyUI directly, bypassing the Studio's evidence trail and the
runtime rules in `CLAUDE.md`. Both agents follow these rules; they are listed in `CLAUDE.md` and `AGENTS.md`.

- **Read-only tools are free**: `server_info`, `which`, `system_stats`, `nodes`, `node_dependencies`,
  `workflow_deps`, `search_models`, `search_templates`, `get_template`, `validate_workflow`,
  `list_workflow_slots`, `discover`, `get_logs`, `job` (inspect/wait).
- **Never call** `update_comfyui`, `switch_comfyui_version`, `install_node`, `download_model`,
  `launch_comfyui`, `stop_comfyui` or `restart_comfyui` against the shared install. The repository forbids
  editing installed ComfyUI or upgrading the shared Torch/ROCm runtime; `C:\AI\Start-ComfyUI.ps1` and
  `Stop-ComfyUI.ps1` own the process, and the Studio's own runtime recovery already handles restarts.
  Model installs go through `scripts/fetch-hf.py` or `scripts/civitai-fetch.py` with hash receipts.
- **Generations belong in the Studio** (`http://127.0.0.1:8191`, or the Workflow Studio agent commands)
  so the job record, exact graph and prompt ID are retained under `experiments/runs/`. Use `run_workflow`
  only for a deliberate probe that is recorded in `CURRENT_STATE.md` with its prompt ID, and only when the
  queue is idle and host commit headroom allows it (`docs/RUNTIME-PRECONDITIONS.md`).
- `partner_generate` spends Comfy Cloud credits; do not call it without an explicit owner instruction.
- `free_memory` is safe on an idle queue and is the same call the Studio uses; do not use it while a job runs.

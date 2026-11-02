"""Agent repair loop over the known-bad corpus: an agent repairs each asset toward the control using only the narrow
MCP façade (open, describe, compare_to, apply_edit, save_copy), never Python. The host scores each saved repair against
the control: semantic checksum, remaining structural differences, collateral change, steps and wall time.

    python scripts/blender_repair_bench.py run --blender <exe> --corpus-dir <corpus> --out-dir <new> --agent claude-haiku [--cases a,b]

Agents: `claude-haiku` (Claude Code headless, Haiku 5.5) and `codex-sol` (Codex exec, GPT-6.1 Sol, secret-like
environment variables removed). Both are wired to the façade per run; nothing is written to saved settings.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
import blender_sentinel as sentinel
from blender_lab import require

# What the façade's apply_edit vocabulary can undo; everything else should be declined honestly.
REPAIRABLE = {"omitted-mesh", "material-mismatch", "transform-offset", "duplicate-overlap"}
TOOLS = ("blender_ping", "blender_open", "blender_describe_scene", "blender_compare_to", "blender_apply_edit", "blender_save_copy")
NPM = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules"
# Call the real entry points, not the npm .cmd shims: cmd.exe would mangle the JSON arguments. Prompts go through stdin.
CLAUDE = [str(NPM / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe")]
CODEX = ["node", str(NPM / "@openai" / "codex" / "bin" / "codex.js")]
SECRET = re.compile(r"TOKEN|_PAT$|PAT_|SECRET|PASSWORD|_KEY$|API_KEY|CREDENTIAL")
PROMPT = """You repair a Blender asset using ONLY the las-blender MCP tools. Never ask questions; work it out.
Damaged file: "{case}". Known-good reference: "{reference}". Use these names exactly as given (they are in the read tree).
1. blender_open the damaged file, blender_describe_scene, then blender_open it again with allow_edit listing the object names you may need to change.
2. blender_compare_to with reference "{reference}": read matches_reference, structural_differences and localisation.
3. Fix only with blender_apply_edit (ops: location, rotation_euler, scale, hide_render, material {{slot, material}}, shape_key {{key, value}}), passing expect_checksum = the latest current_checksum (or describe_scene's semantic_checksum).
4. After each edit run blender_compare_to again. Stop when matches_reference is true or when no allowed op can fix what remains.
5. If you changed anything that helps, blender_save_copy with path "repaired.blend".
Damage such as missing UVs, mesh holes, flipped normals, broken weights, damaged shape-key data or a missing image file cannot be fixed with these ops: say so and do not save.
Your final line must be only JSON: {{"repaired": true or false, "edits": <number of apply_edit calls>, "reason": "<short>"}}"""


def mcp_args(blender, root, read_tree):
    return [str(HERE / "blender_mcp.py"), "--blender", str(blender), "--root", str(root), "--blend-root", str(read_tree)]


def run_tree(command, *, input, cwd, env, timeout):
    """Run an agent and, on timeout, kill its whole process tree (the Node wrapper's native child and its MCP worker
    too) before returning, so nothing keeps running into scoring or cleanup."""
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace")
    try:
        stdout, stderr = process.communicate(input, timeout=timeout)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
        else:
            process.kill()
        stdout, stderr = process.communicate(timeout=60)
        raise subprocess.TimeoutExpired(command, timeout, stdout, stderr)


def scrubbed_env(**extra):
    """The parent environment without anything secret-shaped (a review once printed env and leaked a token)."""
    return {**{k: v for k, v in os.environ.items() if not SECRET.search(k)}, **extra}


CODEX_DISABLED = ("shell_tool", "unified_exec", "apps", "plugins", "browser_use", "browser_use_external", "computer_use",
                  "in_app_browser")


def run_claude(prompt, workdir, blender, root, read_tree, timeout):
    """Claude Code headless, confined to the façade: --restricted removes command-running tools and WebFetch and ignores
    user/project settings (so no bypass mode, hooks or plugins from them), --tools "" removes the other built-ins,
    --strict-mcp-config loads only this server, dontAsk refuses anything not allowed, and the env is scrubbed."""
    config = workdir / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"las-blender": {"type": "stdio", "command": sys.executable,
                                                                 "args": mcp_args(blender, root, read_tree)}}}), encoding="utf-8")
    allowed = ",".join(f"mcp__las-blender__{t}" for t in TOOLS)
    command = [*CLAUDE, "-p", "--model", "claude-haiku-5-5", "--restricted", "--tools", "", "--mcp-config", str(config),
               "--strict-mcp-config", "--permission-mode", "dontAsk", "--allowedTools", allowed, "--output-format", "json"]
    code, stdout, stderr = run_tree(command, input=prompt, cwd=workdir, env=scrubbed_env(), timeout=timeout)
    (workdir / "agent.log").write_text(stdout + "\n--- stderr ---\n" + stderr, encoding="utf-8")
    try: data = json.loads(stdout)
    except ValueError: return {"text": stdout[-2000:], "turns": None, "cost_usd": None, "returncode": code}
    return {"text": data.get("result", ""), "turns": data.get("num_turns"), "cost_usd": data.get("total_cost_usd"),
            "returncode": 1 if data.get("is_error") else code}


def run_codex(prompt, workdir, blender, root, read_tree, timeout):
    """Codex exec, confined to the façade: an isolated CODEX_HOME holding only the auth file (no user MCP servers,
    plugins or hooks), the shell, browser, computer-use, apps and plugin features disabled, a read-only sandbox and a
    scrubbed env. The isolated home is deleted after the run."""
    import shutil
    import tempfile
    home = Path(tempfile.mkdtemp(prefix="las-codex-home-"))
    try:
        shutil.copy2(Path.home() / ".codex" / "auth.json", home / "auth.json")
        (home / "config.toml").write_text('approval_policy = "never"\n', encoding="utf-8")
        return _run_codex(prompt, workdir, blender, root, read_tree, timeout, scrubbed_env(CODEX_HOME=str(home)))
    finally:
        for _ in range(3):  # the credential copy must not outlive the run; a locked file gets a retry, then a loud failure
            shutil.rmtree(home, ignore_errors=True)
            if not home.exists(): break
            time.sleep(2)
        require(not home.exists(), f"could not remove the isolated CODEX_HOME with its auth copy: {home}")


def _run_codex(prompt, workdir, blender, root, read_tree, timeout, env):
    args = json.dumps(mcp_args(blender, root, read_tree))
    command = [*CODEX, "exec", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium", "-s", "read-only", "--skip-git-repo-check",
               *[flag for feature in CODEX_DISABLED for flag in ("--disable", feature)],
               "-c", 'shell_environment_policy.exclude=["*TOKEN*","*_PAT","*PAT_*","*SECRET*","*PASSWORD*","*_KEY","*API_KEY*","*CREDENTIAL*"]',
               "-c", f"mcp_servers.las_blender.command={json.dumps(sys.executable)}", "-c", f"mcp_servers.las_blender.args={args}",
               "-c", "mcp_servers.las_blender.startup_timeout_sec=60", "-c", "mcp_servers.las_blender.tool_timeout_sec=600",
               "-c", 'mcp_servers.las_blender.default_tools_approval_mode="approve"', "-"]
    code, stdout, stderr = run_tree(command, input=prompt, cwd=workdir, env=env, timeout=timeout)
    log = stdout + "\n--- stderr ---\n" + stderr
    (workdir / "agent.log").write_text(log, encoding="utf-8")
    tool_calls = len(re.findall(r"mcp: las_blender/blender_\w+ started", log))
    final = stdout.strip().splitlines()
    return {"text": "\n".join(final[-15:]), "turns": tool_calls or None, "cost_usd": None, "returncode": code}


def verdict(text):
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip().strip("`")
        if line.startswith("{") and "repaired" in line:
            try: return json.loads(line)
            except ValueError: continue
    return None


NON_SEMANTIC = {"schema", "kind", "blender", "source", "runtime", "semantic_checksum"}


def flatten(value, path=""):
    """Manifest leaves by path; list items that carry a name are keyed by it, so an added object shifts nothing."""
    if isinstance(value, dict):
        return {k: v for key, item in value.items() if not (path == "" and key in NON_SEMANTIC)
                for k, v in flatten(item, f"{path}/{key}").items()}
    if isinstance(value, list):
        keyed = all(isinstance(item, dict) and "name" in item for item in value) and value
        return {k: v for index, item in enumerate(value)
                for k, v in flatten(item, f"{path}[{item['name'] if keyed else index}]").items()}
    return {path: value}


def property_changes(control, damaged, repaired):
    """Collateral: properties that matched the control and no longer do. Imprecise: properties the damage touched
    that the repair changed again without restoring."""
    c, d, r = flatten(control), flatten(damaged), flatten(repaired)
    paths = set(c) | set(d) | set(r)
    collateral = sorted(p for p in paths if c.get(p) == d.get(p) and r.get(p) != c.get(p))
    imprecise = sorted(p for p in paths if c.get(p) != d.get(p) and r.get(p) not in (c.get(p), d.get(p)))
    return collateral, imprecise


def score(exe, case, control_manifest, defective_manifest, root, workdir):
    before = sentinel.compare_manifests(control_manifest, defective_manifest)["failures"]
    repaired = root / "repaired.blend"
    if not repaired.is_file():
        return {"saved": False, "exact": False, "remaining": before, "collateral": [], "imprecise": []}
    manifest = lab.manifest(exe, repaired, workdir / "repaired-manifest.json")
    remaining = sentinel.compare_manifests(control_manifest, manifest)["failures"]
    collateral, imprecise = property_changes(control_manifest, defective_manifest, manifest)
    return {"saved": True, "exact": manifest["semantic_checksum"] == control_manifest["semantic_checksum"],
            "remaining": remaining, "collateral": collateral, "imprecise": imprecise}


INFRA = re.compile(r"ENOTFOUND|Can't reach the API server|workspace routing discovery failed|Reconnecting\.\.\. 5/5|request timed out")


def outcome(case, result):
    repairable = case in REPAIRABLE
    if result.get("infrastructure_failure"): return "infrastructure failure (agent never ran to completion)"
    if not result["saved"] and (result.get("returncode") not in (0, None) or result.get("verdict_ok") is False):
        return "agent failure (no valid verdict)"  # a crash or garbled reply is never a decline
    if case == "control":
        return "no-op (correct)" if not result["saved"] else ("no-op saved (harmless)" if result["exact"] else "damaged the control")
    if result["collateral"]: return "harmful (collateral change)"
    if result["exact"]: return "exact repair"
    if result["saved"] and not result["remaining"]: return "structurally clean (checksum differs)"
    if result["saved"]: return "partial"
    return "declined (correct)" if not repairable else "declined (repairable)"


def run(blender_path, corpus_dir, out_dir, agent, cases=None, timeout=900):
    exe = lab.executable(blender_path)
    root = Path(corpus_dir).expanduser().resolve()
    index = json.loads((root / "corpus.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in index["entries"]}
    require(agent in ("claude-haiku", "codex-sol"), "agent must be claude-haiku or codex-sol")
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    target.mkdir(parents=True)
    read_tree = (root / entries["control"]["blend"]).parent
    control_name = Path(entries["control"]["blend"]).name
    control_manifest = lab.manifest(exe, read_tree / control_name, target / "control-manifest.json")
    rows = []
    for case in cases or sorted(entries):
        require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", case) is not None and case in entries, f"unknown case {case}")
        workdir, case_root = target / case, target / case / "root"
        case_root.mkdir(parents=True)
        blend = read_tree / Path(entries[case]["blend"]).name
        defective_manifest = lab.manifest(exe, blend, workdir / "defective-manifest.json")
        prompt = PROMPT.format(case=blend.name, reference=control_name)
        started = time.perf_counter()
        try:
            reply = (run_claude if agent == "claude-haiku" else run_codex)(prompt, workdir, exe, case_root, read_tree, timeout)
        except subprocess.TimeoutExpired:
            reply = {"text": "", "turns": None, "cost_usd": None, "timeout": True}
        seconds = round(time.perf_counter() - started, 1)
        result = score(exe, case, control_manifest, defective_manifest, case_root, workdir)
        log = (workdir / "agent.log").read_text(encoding="utf-8", errors="replace") if (workdir / "agent.log").is_file() else ""
        result["infrastructure_failure"] = (verdict(reply["text"]) is None and not result["saved"]
                                            and (bool(reply.get("timeout")) or INFRA.search(log) is not None))
        row = {"case": case, "agent": agent, "repairable_by_vocabulary": case in REPAIRABLE, "seconds": seconds,
               "steps": reply.get("turns"), "cost_usd": reply.get("cost_usd"), "agent_verdict": verdict(reply["text"]),
               "timeout": bool(reply.get("timeout")), **result}
        row["returncode"] = reply.get("returncode")
        row["verdict_ok"] = isinstance(row["agent_verdict"], dict) and isinstance(row["agent_verdict"].get("repaired"), bool)
        row["outcome"] = outcome(case, row)
        rows.append(row)
        (workdir / "row.json").write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    tally = {}
    for row in rows: tally[row["outcome"]] = tally.get(row["outcome"], 0) + 1
    report = {"schema": "las.blender-repair-bench.v1", "agent": agent, "corpus": str(root), "rows": rows, "outcomes": tally,
              "repairable_exact": sum(r["exact"] for r in rows if r["repairable_by_vocabulary"]),
              "repairable_total": sum(r["repairable_by_vocabulary"] for r in rows),
              "collateral_cases": [r["case"] for r in rows if r["collateral"]],
              "seconds_total": round(sum(r["seconds"] for r in rows), 1)}
    (target / "repair-bench.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def combine(run_dirs, out_path):
    """Merge a run with its reruns case by case: the latest attempt that was not an infrastructure failure wins, and
    every attempt stays counted so outages remain visible."""
    rows, attempts, agent = {}, {}, None
    for run_dir in run_dirs:
        report = json.loads((Path(run_dir) / "repair-bench.json").read_text(encoding="utf-8"))
        require(agent in (None, report["agent"]), "runs from different agents")
        agent = report["agent"]
        for row in report["rows"]:
            if "infrastructure_failure" not in row:  # rows written before outages were classified
                log = Path(run_dir) / row["case"] / "agent.log"
                text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
                row["infrastructure_failure"] = row.get("agent_verdict") is None and not row.get("saved") and INFRA.search(text) is not None
                if row["infrastructure_failure"]: row["outcome"] = outcome(row["case"], row)
            attempts.setdefault(row["case"], []).append({"run": Path(run_dir).name, "outcome": row["outcome"]})
            if row.get("infrastructure_failure") and row["case"] in rows: continue
            rows[row["case"]] = row
    merged = [dict(rows[case], attempts=attempts[case]) for case in sorted(rows)]
    tally = {}
    for row in merged: tally[row["outcome"]] = tally.get(row["outcome"], 0) + 1
    report = {"schema": "las.blender-repair-bench.v1", "agent": agent, "runs": [str(r) for r in run_dirs], "rows": merged,
              "outcomes": tally, "repairable_exact": sum(r["exact"] for r in merged if r["repairable_by_vocabulary"]),
              "repairable_total": sum(r["repairable_by_vocabulary"] for r in merged),
              "collateral_cases": [r["case"] for r in merged if r["collateral"]],
              "infrastructure_failures_retried": sum(1 for a in attempts.values() for x in a if x["outcome"].startswith("infrastructure"))}
    Path(out_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    bench = commands.add_parser("run")
    bench.add_argument("--blender", required=True); bench.add_argument("--corpus-dir", required=True)
    bench.add_argument("--out-dir", required=True); bench.add_argument("--agent", required=True, choices=("claude-haiku", "codex-sol"))
    bench.add_argument("--cases")
    merge = commands.add_parser("combine")
    merge.add_argument("--runs", nargs="+", required=True); merge.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "combine":
        report = combine(args.runs, args.out)
        print(json.dumps({k: report[k] for k in ("outcomes", "repairable_exact", "repairable_total", "collateral_cases",
                                                 "infrastructure_failures_retried")}, indent=2))
        return 0
    try:
        report = run(args.blender, args.corpus_dir, args.out_dir, args.agent, args.cases.split(",") if args.cases else None)
    except (lab.BlenderLabError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({k: report[k] for k in ("outcomes", "repairable_exact", "repairable_total", "collateral_cases", "seconds_total")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

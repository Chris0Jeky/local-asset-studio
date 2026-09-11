# Frontier workbench

Research snapshot: **11 September 2026**. Prepared against repository commit `6bd4e5ba36c3df22011727772754b6e9b3d13c70`. This is an additive research package; it does not replace the active local agent's work or the live preset catalog.

**Read [the research atlas](../../docs/FRONTIER-RESEARCH.md), [architecture](../../docs/FRONTIER-ARCHITECTURE.md), and [agent handoff](../../docs/FRONTIER-HANDOFF.md).**

## Included

- `catalog.json`: 45 source-linked model, tool and research entries. A reviewed page is not an audited codebase, pinned install or local test. The Civitai Seed Hunter source remains explicitly access-blocked.
- `recipes.json`: 14 staged, non-executable pipeline blueprints with variants, required inputs, acceptance checks and stop conditions. They are **not ComfyUI JSON graphs**.
- `workbench.template.html`: dependency-free research navigator with search, medium/tier filters, expandable recipes and local JSON export. No telemetry, remote scripts or automatic requests; following a source link is an explicit browser action.
- `../../scripts/frontier_workbench.py`: offline validator, bounded experiment-intent planner, HTML builder and limited SafeTensors header inspector.
- `../../tests/test_frontier_workbench.py`: isolated standard-library unit tests; the dedicated GitHub workflow requires no model weights or GPU.

## Use from the repository root

```powershell
python scripts/frontier_workbench.py validate
python scripts/frontier_workbench.py render --out frontier-workbench.html
python scripts/frontier_workbench.py plan --recipe h3-seed-lab --brief "A lanternkeeper opens an observatory door; retain identity and hand contact" --count 2 --max-jobs 12 --out h3-plan.json
python scripts/frontier_workbench.py inspect "C:\Users\jekyt\Downloads\minimax_h3_fl2va_pruned_int8_convrot.safetensors"
python -m unittest discover -s tests -p test_frontier_workbench.py -v
```

Open `frontier-workbench.html` directly in a browser. Generated HTML and plans can instead be written outside the checkout or under an already ignored experiments directory. The tool does not create parent directories and overwrites an explicitly supplied output file; choose a new name for evidence you need to retain.

The inspector reads at most a 4 MiB JSON header and seeks to the end to check offset bounds. It does not read tensor bodies, import Torch, execute metadata, install anything or move the file. Folder hints are deliberately restricted to recognized H3 filename patterns. They are not an architecture detector or a complete SafeTensors validator. A renamed file can mislead a filename hint. Large valid headers can exceed this conservative inspection limit.

The planner emits a **proposed experiment**, not API requests. The default is two seed labels across three variants: six jobs. It rejects counts beyond the explicit cap instead of quietly creating a much larger queue. The hash identifies the brief, recipe and research snapshot, not an executable artifact lock. A local compiler must resolve real workflows, input hashes, node schemas, model files and resource budgets before submission.

## Evidence discipline

`local_verified: false` means this pass performed no model inference; it does not erase earlier evidence in `CURRENT_STATE.md`. Baseline is a recommended comparison role. Candidate is worth investigating. Experimental means additional implementation uncertainty. Watchlist is research rather than a promised installation. Unresolved means the source could not be inspected. Commercial suitability is assessed separately against exact terms and the intended use.

No model weights, third-party workflow bytes, gated downloads, paid services or generated art are bundled. Entries intentionally retain upstream links rather than redistributing unreviewed code or images. Runtime integration, source pinning and creative acceptance remain explicit follow-up work.

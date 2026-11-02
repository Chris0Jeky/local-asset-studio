"""Known-bad asset corpus for scoring agents and render critics against labelled defects.

The generated lab asset (geometric shapes only) plus one variant per labelled defect, each with the sentinel's
fixed-camera evidence renders and manifest. A baseline records what the deterministic checks catch when each variant
is compared with the clean control, so a critic can be scored on the same renders and its misses compared with
the gates' misses.

    python scripts/blender_corpus.py build --blender <blender.exe> --out-dir <new-dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
import blender_sentinel as sentinel
from blender_lab import require

SCHEMA = "las.blender-known-bad-corpus.v1"


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def build(blender_path, out_dir, timeout=600):
    exe = lab.executable(blender_path)
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    target.mkdir(parents=True)
    assets, logs = target / "assets", target / "logs"
    logs.mkdir()
    clean = lab.make_fixture(exe, assets)  # variants are saved beside it so the relative texture path resolves
    labels = {"control": None}
    for kind in sorted(lab.bpy_side.CORPUS_DEFECTS):
        record = target / "logs" / f"{kind}.variant.json"
        lab.run(exe, ["corpus-variant", "--blend", clean, "--kind", kind, "--out-blend", assets / f"{kind}.blend",
                      "--out", record], logs / f"{kind}.variant.log.json", timeout)
        labels[kind] = json.loads(record.read_text(encoding="utf-8"))["label"]
    blends = {"control": clean, **{kind: assets / f"{kind}.blend" for kind in labels if kind != "control"}}
    for entry, blend in blends.items():
        args = ["evidence", "--blend", blend, "--out-dir", target / "evidence" / entry, "--out", logs / f"{entry}.evidence.json"]
        if entry != "control": args += ["--cameras", target / "cameras.json"]
        lab.run(exe, args, logs / f"{entry}.evidence.log.json", timeout)
        if entry == "control":
            spec = json.loads((target / "evidence" / "control" / "evidence.json").read_text(encoding="utf-8"))["camera_spec"]
            _json(target / "cameras.json", spec)
    load = lambda entry, name: json.loads((target / "evidence" / entry / name).read_text(encoding="utf-8"))
    control_manifest, control_evidence = load("control", "manifest.json"), load("control", "evidence.json")
    entries = []
    for entry, blend in blends.items():
        structure = sentinel.compare_manifests(control_manifest, load(entry, "manifest.json"))
        views, warnings = sentinel.compare_renders(target / "evidence" / "control" / "renders", target / "evidence" / entry / "renders",
                                                   control_evidence, target / "diff" / entry)
        localisation = sentinel.localise(views, target / "evidence" / "control" / "renders", target / "evidence" / entry / "renders",
                                         control_evidence)
        critic = sentinel.critic_signal(target / "evidence" / "control" / "renders", target / "evidence" / entry / "renders")
        primary_visual = bool(warnings)
        critic["agrees_with_primary"] = sentinel.second_opinion(critic, list(warnings))  # baseline stays the primary verdict
        entries.append({
            "id": entry, "blend": blend.relative_to(target).as_posix(), "sha256": lab.file_sha(blend),
            "expected": "clean" if entry == "control" else "defective", "label": labels[entry],
            "description": lab.bpy_side.CORPUS_DEFECTS.get(entry, "unchanged generated lab asset"),
            "renders": f"evidence/{entry}/renders", "manifest": f"evidence/{entry}/manifest.json",
            "baseline": {"structural_failures": structure["failures"], "visual_warnings": warnings,
                         "caught_by_manifest": bool(structure["failures"]), "caught_by_renders": primary_visual,
                         "critic": critic, "localisation": [l["statement"] for l in localisation],
                         "caught": bool(structure["failures"] or warnings)}})
    defective = [e for e in entries if e["expected"] == "defective"]
    corpus = {"schema": SCHEMA, "blender": control_manifest["blender"], "cameras": "cameras.json",
              "passes": list(lab.bpy_side.PASSES), "views": list(lab.bpy_side.VIEWS), "entries": entries,
              "summary": {"defects": len(defective), "caught": sum(e["baseline"]["caught"] for e in defective),
                          "caught_by_manifest_only": sorted(e["id"] for e in defective if e["baseline"]["caught_by_manifest"] and not e["baseline"]["caught_by_renders"]),
                          "caught_by_renders_only": sorted(e["id"] for e in defective if e["baseline"]["caught_by_renders"] and not e["baseline"]["caught_by_manifest"]),
                          "missed": sorted(e["id"] for e in defective if not e["baseline"]["caught"]),
                          "control_clean": not next(e for e in entries if e["id"] == "control")["baseline"]["caught"],
                          "critic": None if not all(e["baseline"]["critic"].get("available") for e in entries) else {
                              "agreement": sum(bool(e["baseline"]["critic"]["agrees_with_primary"]) for e in entries),
                              "entries": len(entries),
                              "caught_by_critic": sorted(e["id"] for e in defective if e["baseline"]["critic"]["changed"]),
                              "disagreements": sorted(e["id"] for e in entries if not e["baseline"]["critic"]["agrees_with_primary"])}},
              "scoring": "A critic reads evidence/<id>/renders and answers clean or defective (optionally which object). Score it "
                         "against `expected`; compare its misses with baseline.missed. Labels are generated ground truth, not taste."}
    _json(target / "corpus.json", corpus)
    return corpus


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--blender", required=True)
    build_parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    try:
        corpus = build(args.blender, args.out_dir)
    except (lab.BlenderLabError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(corpus["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

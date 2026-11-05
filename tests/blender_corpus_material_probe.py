"""Native-only corpus regression: an unused material must not survive as repair collateral."""
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_lab_bpy as lab


def main():
    out = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    worker = lab.Worker(str(out))
    try:
        clean = lab.make_fixture(str(out / "assets"))
        worker.open(clean, allow_edit=["Badge"])
        unused = bpy.data.materials.new("A_UnusedMaterial")  # sorts before every assigned material
        before = worker.describe_scene()
        names = lambda value: [m["name"] for m in value["materials"]]
        label = lab.corpus_defect("material-mismatch")
        seeded = worker.describe_scene()
        retention = {m.name: m.use_fake_user for m in bpy.data.materials}
        worker.save_copy("assets/damaged.blend")
        worker.open(str(out / "assets" / "damaged.blend"), allow_edit=[label["object"]])
        reopened = worker.describe_scene()
        worker.apply_edit(object=label["object"], op="material", value={"slot": label["slot"], "material": label["from"]},
                          expect_checksum=reopened["semantic_checksum"])
        worker.save_copy("assets/repaired.blend")
        worker.open(str(out / "assets" / "repaired.blend"))
        repaired = worker.describe_scene()
        receipt = {"blender": before["blender"], "label": label, "retention": retention,
                   "materials": {"before": names(before), "seeded": names(seeded), "reopened": names(reopened),
                                 "repaired": names(repaired)},
                   "checksums": {"before": before["semantic_checksum"], "seeded": seeded["semantic_checksum"],
                                 "reopened": reopened["semantic_checksum"], "repaired": repaired["semantic_checksum"]}}
        (out / "material-repair.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(worker.scratch, ignore_errors=True)


if __name__ == "__main__": main()

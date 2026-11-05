"""Opt-in native Godot spring binding, center motion and gravity checks; no avatar render/visual-parity claim."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_vrm_toon import SPRING_DOC, glb, vrm_toon

ROOT = Path(__file__).resolve().parents[1]
GODOT = os.environ.get("STUDIO_TEST_GODOT")
if os.environ.get("STUDIO_REQUIRE_ENGINE_TESTS") == "1" and not GODOT:
    raise RuntimeError("Required VRM spring test lacks an explicit Godot executable")


@unittest.skipUnless(GODOT, "Explicit STUDIO_TEST_GODOT required; no native spring check was run")
class NativeSpringBinding(unittest.TestCase):
    def test_exported_joint_settings_and_centers_reach_the_real_simulator(self):
        if os.environ.get("STUDIO_ENGINE_EVIDENCE"):
            root = Path(os.environ["STUDIO_ENGINE_EVIDENCE"]) / "vrm-springs"
            root.mkdir(parents=True, exist_ok=False)
        else:
            tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
            root = Path(tmp.name)
        project = root / "project"; project.mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="VRM spring binding probe"\n', encoding="utf-8")
        sources = {name: ROOT / "tools" / "godot-toon" / name for name in ("toon_proof.gd", "vrm_spring_config.gd")}
        sources["probe.gd"] = ROOT / "tests" / "vrm_springs_probe.gd"
        for name, source in sources.items(): shutil.copyfile(source, project / name)
        doc = copy.deepcopy(SPRING_DOC)
        for node, position in zip(doc["nodes"], ([0, .8, 0], [0, .1, 0], [0, .2, 0], [0, .2, 0], [.1, -.1, 0])):
            node["translation"] = position
        chain = doc["extensions"]["VRMC_springBone"]["springs"][0]; chain["center"] = 0
        chain["joints"][0]["gravityDir"] = [1, 0, 0]
        chain["joints"][1].update(stiffness=.15, dragForce=.8, gravityPower=.2, gravityDir=[0, 0, -1], hitRadius=.004)
        fixture = root / "fixture.vrm"; fixture.write_bytes(glb(doc))
        skeleton = root / "skeleton.json"; skeleton.write_text(json.dumps(doc), encoding="utf-8")
        sidecar = root / "springs.json"
        self.assertEqual(vrm_toon.main(["springs", str(fixture), str(sidecar)]), 0)
        result = root / "result.json"
        command = [str(Path(GODOT).resolve()), "--headless", "--path", str(project.resolve()), "--script", "res://probe.gd",
                   "--", str(sidecar.resolve()), str(skeleton.resolve()), str(result.resolve())]
        hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()}
        hashes.update({"vrm_toon.py": hashlib.sha256((ROOT / "scripts" / "vrm_toon.py").read_bytes()).hexdigest(),
                       "fixture.vrm": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                       "springs.json": hashlib.sha256(sidecar.read_bytes()).hexdigest()})
        (root / "plan.json").write_text(json.dumps({"command": command, "sha256": hashes}, indent=2) + "\n", encoding="utf-8")
        try:
            reply = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except subprocess.TimeoutExpired as exc:
            for name, value in (("stdout", exc.stdout), ("stderr", exc.stderr)):
                text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
                (root / (name + ".log")).write_text(text, encoding="utf-8")
            (root / "execution.json").write_text(json.dumps({"returncode": None, "timed_out": True}) + "\n", encoding="utf-8")
            self.fail("Headless Godot spring probe timed out; retained logs identify the failure")
        for name in ("stdout", "stderr"): (root / (name + ".log")).write_text(getattr(reply, name), encoding="utf-8")
        (root / "execution.json").write_text(json.dumps({"returncode": reply.returncode, "timed_out": False}) + "\n", encoding="utf-8")
        self.assertEqual(reply.returncode, 0, reply.stderr[-5000:] + reply.stdout[-5000:])
        receipt = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual(receipt["failures"], [])
        self.assertEqual(set(receipt["cases"]), {"production-binding", "individual-settings", "deferred-settings",
                                               "rotated-world-gravity", "zero-gravity", "bone-center-motion",
                                               "node-center-motion", "world-center-motion", "legacy-sidecar", "missing-bone",
                                               "missing-center", "ambiguous-center", "sparse-chain", "reordered-chain",
                                               "missing-collider", "descendant-center"})
        self.assertTrue(all(receipt["cases"].values()), receipt)


if __name__ == "__main__": unittest.main()

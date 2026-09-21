"""Deferred restyle handoff and continuation lineage guards; no ComfyUI, browser or model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class WorkbenchHandoffGuardTests(unittest.TestCase):
    def _node(self, script):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", f"tests/{script}"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend behavior checks")
    def test_deferred_handoff_and_copy_guards(self):
        self._node("workbench_handoff_guards.cjs")

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend behavior checks")
    def test_continuation_parent_claims_survive_slot_clearing(self):
        self._node("continuation_parent_claims.cjs")

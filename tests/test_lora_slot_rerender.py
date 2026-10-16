"""A recorded LoRA option has to survive the adapter-slot rebuild."""
import shutil
import subprocess
import unittest
from pathlib import Path


class LoraSlotRerender(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_recorded_option_survives_rerender(self):
        result = subprocess.run([shutil.which("node"), str(Path(__file__).with_name("lora_slot_rerender.cjs"))], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("lora slot rerender passed", result.stdout)


if __name__ == "__main__":
    unittest.main()

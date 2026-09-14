from pathlib import Path
import shutil
import subprocess
import unittest


class CollectionEditorImmediateReopen(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_delete_close_event_cannot_disable_replacement_session(self):
        result = subprocess.run(
            [
                shutil.which("node"),
                str(Path(__file__).with_name("collection_editor_reopen_contract.cjs")),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("immediate-reopen contract passed", result.stdout)


if __name__ == "__main__":
    unittest.main()

"""Import-order contract for pooled-work observation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent


class ExecutorWorkImportTests(unittest.TestCase):
    def test_observer_module_does_not_import_executor_before_install(self):
        script = (
            "import sys\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "assert 'concurrent.futures.thread' not in sys.modules\n"
            "import executor_work_observability\n"
            "print('concurrent.futures.thread' in sys.modules)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=HERE.parent,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()

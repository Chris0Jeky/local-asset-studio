from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrapper = load("lifetime_wrapper", HERE / "check_full_suite_lifetime.py")


class LifetimeDiagnosticsTests(unittest.TestCase):
    def test_wrapper_uses_unbuffered_diagnostic_worker(self):
        command = wrapper.suite_command(traceback_after=12.5)
        self.assertIn("-u", command)
        self.assertIn(str(HERE / "full_suite_lifetime_worker.py"), command)
        self.assertEqual(command[-2:], ["--traceback-after", "12.5"])

    def test_worker_names_current_test_and_dumps_threads_before_parent_budget(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_hang.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import time
                    import unittest

                    class HangsBriefly(unittest.TestCase):
                        def test_wait(self):
                            time.sleep(0.15)
                    """
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-u",
                    str(worker),
                    "--start-dir",
                    directory,
                    "--pattern",
                    "test_hang.py",
                    "--traceback-after",
                    "0.03",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("START test_hang.HangsBriefly.test_wait", output)
        self.assertIn(
            "LIFETIME WATCHDOG CURRENT TEST: test_hang.HangsBriefly.test_wait",
            output,
        )
        self.assertIn("Thread ", output)
        self.assertIn("END test_hang.HangsBriefly.test_wait", output)


if __name__ == "__main__":
    unittest.main()

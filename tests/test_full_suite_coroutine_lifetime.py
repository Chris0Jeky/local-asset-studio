"""Exercise the shipped lifetime boundary with real coroutine finalization."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


HERE = Path(__file__).resolve().parent


class CoroutineLifetimeTests(unittest.TestCase):
    def run_fixture(self, body: str, *, suppress_warnings: bool = False):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "test_coroutine_fixture.py"
            fixture.write_text(textwrap.dedent(body), encoding="utf-8")
            # Redirect discovery only. Budget ownership, flags, warning policy,
            # worker execution and interpreter shutdown are the shipped code.
            launch = textwrap.dedent("""\
                import sys
                sys.path.insert(0, sys.argv[1])
                import check_full_suite_lifetime as guard
                original = guard.suite_command
                def fixture_command(*args, **kwargs):
                    command = original(*args, **kwargs)
                    command[command.index('--start-dir') + 1] = sys.argv[2]
                    return command
                guard.suite_command = fixture_command
                raise SystemExit(guard.main())
            """)
            env = dict(os.environ)
            env.pop("FULL_SUITE_LIFETIME_BUDGET_SECONDS", None)
            env.pop("FULL_SUITE_SHARD", None)
            env.pop("PYTHONFAULTHANDLER", None)
            env.pop("PYTHONASYNCIODEBUG", None)
            if suppress_warnings:
                env["PYTHONWARNINGS"] = "ignore::RuntimeWarning"
            else:
                env.pop("PYTHONWARNINGS", None)
            return subprocess.run(
                [sys.executable, "-c", launch, str(HERE), directory],
                capture_output=True, text=True, timeout=30, env=env,
            )

    def test_unawaited_work_during_passing_test_fails_parent(self):
        result = self.run_fixture("""
            import unittest
            async def abandoned_work():
                return 42
            class Fixture(unittest.TestCase):
                def test_body(self):
                    abandoned_work()
        """)
        self.assertIn("LIFETIME SUITE COMPLETE: success", result.stdout)
        self.assertIn("was never awaited", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unawaited coroutine", result.stderr)

    def test_finalizer_warning_after_success_fails_with_creation_origin(self):
        result = self.run_fixture("""
            import atexit
            import unittest
            async def abandoned_at_exit():
                return 42
            retained = []
            def retain_from_test():
                retained.append(abandoned_at_exit())
            class Fixture(unittest.TestCase):
                def test_body(self):
                    retain_from_test()
                    atexit.register(retained.clear)
        """)
        output = result.stdout + result.stderr
        self.assertIn("LIFETIME SUITE COMPLETE: success", result.stdout)
        self.assertIn("was never awaited", result.stdout)
        self.assertEqual(result.returncode, 1, output)
        self.assertIn("Coroutine created at", output)
        self.assertIn("in retain_from_test", output)

    def test_partial_stdout_cannot_hide_stderr_coroutine_warning(self):
        result = self.run_fixture("""
            import unittest
            async def abandoned_work():
                return 42
            class Fixture(unittest.TestCase):
                def test_body(self):
                    print('no trailing newline', end='')
                    abandoned_work()
        """)
        self.assertIn("no trailing newline", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_runtime_warning_suppression_cannot_hide_leaked_work(self):
        result = self.run_fixture("""
            import unittest
            async def abandoned_work():
                return 42
            class Fixture(unittest.TestCase):
                def test_body(self):
                    abandoned_work()
        """, suppress_warnings=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("was never awaited", result.stdout)

    def test_awaited_and_explicitly_closed_work_passes(self):
        result = self.run_fixture("""
            import asyncio
            import unittest
            async def work():
                return 42
            class Fixture(unittest.TestCase):
                def test_body(self):
                    self.assertEqual(asyncio.run(work()), 42)
                    unused = work()
                    unused.close()
        """)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("was never awaited", result.stdout)

    def test_benign_mentions_and_unrelated_runtime_warning_stay_visible(self):
        result = self.run_fixture("""
            import unittest
            import warnings
            class Fixture(unittest.TestCase):
                def test_body(self):
                    print('The phrase was never awaited is documentation.')
                    warnings.warn('unrelated numerical fixture', RuntimeWarning)
        """)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unrelated numerical fixture", result.stdout)

    def test_worker_enables_fatal_dump_and_bounded_origins_before_discovery(self):
        result = self.run_fixture("""
            import faulthandler
            import sys
            import unittest
            async def work():
                return 42
            at_import = work()
            origin = at_import.cr_origin
            at_import.close()
            class Fixture(unittest.TestCase):
                def test_body(self):
                    self.assertTrue(faulthandler.is_enabled())
                    self.assertIsNotNone(origin)
                    self.assertLessEqual(len(origin), 8)
                    self.assertEqual(origin[0][2], '<module>')
        """)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

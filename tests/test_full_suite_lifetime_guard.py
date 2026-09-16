import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


PATH = Path(__file__).with_name('check_full_suite_lifetime.py')
SPEC = importlib.util.spec_from_file_location('full_suite_lifetime_guard', PATH)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class FullSuiteLifetimeGuardTests(unittest.TestCase):
    def test_budget_retains_a_thirty_second_diagnostic_window(self):
        self.assertEqual(guard.LIFETIME_BUDGET_SECONDS, 600)
        self.assertEqual(guard.TRACEBACK_AFTER_SECONDS, 570)
        command = guard.suite_command()
        self.assertEqual(command[command.index('--traceback-after') + 1], '570')

    def test_timeout_reports_measured_elapsed_time_and_configured_budget(self):
        timeout = subprocess.TimeoutExpired(
            ['worker'], 600, output='START slow.test\n', stderr='dump\n'
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(guard.subprocess, 'run', side_effect=timeout), \
             patch.object(guard.time, 'monotonic', side_effect=[10.0, 611.25]), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = guard.main()
        self.assertEqual(status, 124)
        self.assertEqual(stdout.getvalue(), 'START slow.test\ndump\n')
        self.assertIn('600-second lifetime budget after 601.25 seconds', stderr.getvalue())
        self.assertIn('last START marker', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()

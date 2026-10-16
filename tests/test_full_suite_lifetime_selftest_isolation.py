"""The lifetime harness's synthetic children own their startup and cleanup."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_full_suite_lifetime as lifetime


class LifetimeSelftestIsolationTests(unittest.TestCase):
    def test_failed_stream_assertion_still_reaps_the_child(self):
        capture = Mock()
        capture.wait_for.return_value = False
        capture.output.return_value = 'injected missing output'
        capture.reap.return_value = (0, '')
        case = lifetime.LifetimeDiagnosticsTests('test_process_capture_retains_each_stream_line_once')
        with patch.object(lifetime.subprocess, 'Popen'), patch.object(lifetime, 'ProcessCapture', return_value=capture):
            with self.assertRaisesRegex(AssertionError, 'injected missing output'):
                case.test_process_capture_retains_each_stream_line_once()
        capture.reap.assert_called_once_with()

    def test_synthetic_probes_ignore_site_customization_and_python_environment(self):
        methods = (
            'test_shutdown_probe_reports_absent_watchdog_and_reaps_child',
            'test_shutdown_probe_reports_unexpected_child_exit',
            'test_process_capture_retains_each_stream_line_once',
            'test_shutdown_probe_keeps_a_hard_total_budget',
        )
        original = lifetime.subprocess.Popen
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'site-ran'
            (root / 'sitecustomize.py').write_text(
                f'from pathlib import Path\nPath({str(marker)!r}).write_text("ran")\nraise SystemExit(77)\n',
                encoding='utf-8')
            for method in methods:
                with self.subTest(method=method):
                    children, commands = [], []
                    def spawn(command, **kwargs):
                        commands.append(command)
                        kwargs['env'] = dict(os.environ, PYTHONPATH=str(root))
                        child = original(command, **kwargs)
                        children.append(child)
                        return child
                    try:
                        with patch.object(lifetime.subprocess, 'Popen', side_effect=spawn):
                            case = lifetime.LifetimeDiagnosticsTests(method)
                            result = unittest.TestResult()
                            case.run(result)
                        self.assertTrue(result.wasSuccessful(), str(result.errors + result.failures))
                        self.assertEqual(len(commands), 1)
                        self.assertIn('-I', commands[0])
                        self.assertIn('-S', commands[0])
                        self.assertFalse(marker.exists(), 'Synthetic probe executed external site customization')
                    finally:
                        for child in children:
                            if child.poll() is None:
                                child.kill()
                            child.wait(timeout=5)
                        marker.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()

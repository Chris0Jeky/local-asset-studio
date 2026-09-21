"""Injected OS-wait failures must retain the owned-child cleanup verdict."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import profiler_probe as probe


class ProfilerInterruptionTests(unittest.TestCase):
    def test_interruption_reports_owned_cleanup_instead_of_losing_state(self):
        child = Mock()
        child.wait.side_effect = [KeyboardInterrupt, None]
        child.poll.return_value = None
        child.returncode = -9
        with patch.object(probe.subprocess, 'Popen', return_value=child):
            try: outcome = probe.supervise(['fixed-worker'], 5)
            except (KeyboardInterrupt, subprocess.TimeoutExpired):
                self.fail('Interruption escaped without the child cleanup verdict')
        self.assertEqual(outcome['code'], 'worker_interrupted')
        self.assertTrue(outcome['child_reaped'])
        child.kill.assert_called_once_with()

    def test_interrupted_unreaped_child_is_not_reported_clean(self):
        child = Mock()
        child.wait.side_effect = [KeyboardInterrupt, subprocess.TimeoutExpired('fixed-worker', 5)]
        child.poll.return_value = None
        child.returncode = None
        with patch.object(probe.subprocess, 'Popen', return_value=child):
            try: outcome = probe.supervise(['fixed-worker'], 5)
            except (KeyboardInterrupt, subprocess.TimeoutExpired):
                self.fail('Interruption escaped without the child cleanup verdict')
        self.assertEqual(outcome['code'], 'worker_cleanup_incomplete')
        self.assertFalse(outcome['child_reaped'])
        child.kill.assert_called_once_with()


if __name__ == '__main__': unittest.main()

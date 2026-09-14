"""Offline regression coverage for the mixed-batch subprocess gate."""
from contextlib import redirect_stderr, redirect_stdout
import io
import subprocess
import sys
import unittest
from unittest.mock import patch

import check_mixed_batch_lifetime as gate


class MixedBatchLifetimeTests(unittest.TestCase):
    def test_timeout_preserves_both_streams_and_fails(self):
        expired = subprocess.TimeoutExpired(
            ["synthetic-child"], 45, output=b"child stdout\n", stderr=b"child stderr\n"
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(gate.subprocess, "run", side_effect=expired) as run:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as failure:
                    gate.main()
        self.assertEqual(failure.exception.code, 124)
        self.assertEqual(run.call_count, 1)
        self.assertIn("child stdout", stdout.getvalue())
        self.assertIn("child stderr", stdout.getvalue())
        self.assertIn("attempt 1/2", stdout.getvalue())
        self.assertIn("45-second", stderr.getvalue())
        self.assertIn("elapsed", stderr.getvalue())
        self.assertNotIn("gate passed", stdout.getvalue())

    def test_real_timeout_retains_bounded_tails_and_reaps_child(self):
        real_run, real_popen = subprocess.run, subprocess.Popen
        children = []
        child_code = (
            "import sys, time\n"
            f"print('stdout-start:' + 'o' * {gate.DIAGNOSTIC_TAIL_CHARS * 2} "
            "+ ':stdout-tail', flush=True)\n"
            f"print('stderr-start:' + 'e' * {gate.DIAGNOSTIC_TAIL_CHARS * 2} "
            "+ ':stderr-tail', file=sys.stderr, flush=True)\n"
            "time.sleep(60)\n"
        )

        def owned_popen(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)
            return child

        def synthetic_run(command, **kwargs):
            return real_run([sys.executable, "-c", child_code], **kwargs)

        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with patch.object(gate, "TIMEOUT_SECONDS", 2):
                with patch.object(gate.subprocess, "Popen", side_effect=owned_popen):
                    with patch.object(gate.subprocess, "run", side_effect=synthetic_run) as run:
                        with redirect_stdout(stdout), redirect_stderr(stderr):
                            with self.assertRaises(SystemExit) as failure:
                                gate.main()
            self.assertEqual(failure.exception.code, 124)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].returncode, "timed-out child was not reaped")
            self.assertNotEqual(children[0].returncode, 0)
            self.assertTrue(children[0].stdout.closed)
            self.assertTrue(children[0].stderr.closed)
            output = stdout.getvalue()
            self.assertIn(":stdout-tail", output)
            self.assertIn(":stderr-tail", output)
            self.assertNotIn("stdout-start:", output)
            self.assertNotIn("stderr-start:", output)
            self.assertEqual(output.count("[earlier output truncated]"), 2)
            self.assertLess(len(output), 2 * gate.DIAGNOSTIC_TAIL_CHARS + 400)
            self.assertIn("attempt 1/2", output)
            self.assertIn("2-second", stderr.getvalue())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)

    def test_timeout_handles_text_missing_and_non_utf8_output(self):
        for output, expected in (("plain text", "plain text"), (None, ""), (b"byte\xff", "byte\ufffd")):
            with self.subTest(output=output):
                expired = subprocess.TimeoutExpired(["synthetic-child"], 45, output=output)
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(gate.subprocess, "run", side_effect=expired):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        with self.assertRaises(SystemExit) as failure:
                            gate.run_once(2)
                self.assertEqual(failure.exception.code, 124)
                self.assertIn(expected, stdout.getvalue())
                self.assertIn("attempt 2/2", stderr.getvalue())

    def test_success_keeps_two_fresh_interpreter_checks_and_original_budget(self):
        result = subprocess.CompletedProcess(["synthetic-child"], 0, "stdout\n", "stderr\n")
        stdout = io.StringIO()
        with patch.object(gate.subprocess, "run", return_value=result) as run:
            with redirect_stdout(stdout):
                self.assertEqual(gate.main(), 0)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.args[0], [
                sys.executable, "-W", "always::ResourceWarning", "-m", "unittest",
                "discover", "-s", "tests", "-p", "test_mixed_batch_http.py", "-v",
            ])
            self.assertEqual(call.kwargs["timeout"], 45)
            self.assertEqual(call.kwargs["env"]["PYTHONTRACEMALLOC"], "25")
            self.assertEqual(call.kwargs["cwd"], gate.ROOT)
        self.assertIn("gate passed 2 fresh-interpreter attempts", stdout.getvalue())

    def test_child_failure_and_resource_warnings_remain_fatal_without_retry(self):
        for code, stdout, stderr, reason in (
            (7, "child stdout", "child stderr", "exited 7"),
            (0, "ResourceWarning: stdout", "", "emitted ResourceWarning"),
            (0, "", "ResourceWarning: stderr", "emitted ResourceWarning"),
        ):
            with self.subTest(code=code, stdout=stdout, stderr=stderr):
                result = subprocess.CompletedProcess(["synthetic-child"], code, stdout, stderr)
                with patch.object(gate.subprocess, "run", return_value=result) as run:
                    with redirect_stdout(io.StringIO()):
                        with self.assertRaisesRegex(SystemExit, reason):
                            gate.main()
                self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()

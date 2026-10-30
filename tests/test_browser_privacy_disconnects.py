"""Privacy browser receipts retain disconnects without hiding handler defects."""
import ast
from pathlib import Path
import sys
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = ('private_creation_browser.py', 'private_recovery_browser.py', 'make_draft_browser.py', 'make_privacy_browser.py')


class PrivacyBrowserDisconnectTests(unittest.TestCase):
    def observe(self, filename, error):
        tree = ast.parse((ROOT / 'tests' / filename).read_text(encoding='utf-8'))
        handlers = [node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == 'server_error']
        self.assertEqual(len(handlers), 1)
        namespace = {'sys': sys, 'traceback': traceback, 'disconnects': [], 'server_errors': []}
        exec(compile(ast.Module(body=handlers, type_ignores=[]), filename, 'exec'), namespace)
        try:
            raise error
        except Exception:
            namespace['server_error'](None, ('127.0.0.1', 1))
        return namespace['disconnects'], namespace['server_errors']

    def test_closed_browser_connections_are_retained_as_disconnects(self):
        for filename in DRIVERS:
            for error in (BrokenPipeError('closed'), ConnectionResetError('reset'),
                          ConnectionAbortedError(10053, 'Windows browser cancelled the response')):
                with self.subTest(driver=filename, error=type(error).__name__):
                    disconnects, failures = self.observe(filename, error)
                    self.assertEqual(disconnects, [type(error).__name__])
                    self.assertEqual(failures, [])

    def test_handler_and_other_io_failures_still_fail_the_gate(self):
        for filename in DRIVERS:
            for error in (ValueError('bad response'), RuntimeError('handler failed'),
                          OSError('unrelated I/O'), TimeoutError('server timeout')):
                with self.subTest(driver=filename, error=type(error).__name__):
                    disconnects, failures = self.observe(filename, error)
                    self.assertEqual(disconnects, [])
                    self.assertEqual(len(failures), 1)
                    self.assertIn(type(error).__name__, failures[0])
                    self.assertIn(str(error), failures[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)

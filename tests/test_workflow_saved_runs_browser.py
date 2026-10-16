"""Saved-run browser fixture owns its port and keeps the production guard intact."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import workflow_saved_runs_browser as runner


class SavedRunsBrowserPortTests(unittest.TestCase):
    def test_default_fixtures_bind_distinct_ports_and_guard_the_bound_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = SimpleNamespace()
            with runner.create_fixture(Path(folder), studio) as first, runner.create_fixture(Path(folder), studio) as second:
                self.assertNotEqual(first.server_port, second.server_port)
                self.assertNotIn(8191, (first.server_port, second.server_port))
                self.assertIs(first.RequestHandlerClass.studio, studio)
                probe = first.RequestHandlerClass.__new__(first.RequestHandlerClass); probe.server = first
                for host, origin, allowed in ((f'127.0.0.1:{first.server_port}', f'http://127.0.0.1:{first.server_port}', True),
                        (f'localhost:{first.server_port}', f'http://localhost:{first.server_port}', True),
                        ('127.0.0.1:8191', 'http://127.0.0.1:8191', False),
                        (f'127.0.0.1:{first.server_port}', 'https://evil.invalid', False)):
                    probe.headers = {'Host':host, 'Origin':origin}
                    self.assertEqual(probe._safe_mutation(), allowed)

    def test_explicit_port_is_forwarded(self):
        with patch.object(runner, 'browser_server') as bind:
            runner.create_fixture(Path('.'), SimpleNamespace(), port=45678)
        self.assertEqual(bind.call_args.args[1], 45678)


if __name__ == '__main__': unittest.main()

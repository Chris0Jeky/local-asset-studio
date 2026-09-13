"""CLI output failures must not hide known responses or dispatch needlessly."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_workflow_studio as fixture
from studio_workflow import __main__ as cli


class OutputTests(unittest.TestCase):
    setUp = fixture.HTTPTests.setUp
    close = fixture.HTTPTests.close

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(['--url', self.url, *args])
        return code, json.loads(output.getvalue())

    def ticket(self):
        root = Path(self.temp.name)
        recipe = root / 'recipe.json'
        recipe.write_text(json.dumps({'preset_id': 'example'}), encoding='utf-8')
        ticket = root / 'ticket.json'
        code, result = self.invoke('prepare', '--recipe', str(recipe), '--out', str(ticket))
        self.assertEqual(code, 0, result)
        return ticket

    def test_existing_output_is_rejected_before_run_request(self):
        ticket = self.ticket()
        output = Path(self.temp.name) / 'existing.json'; output.write_bytes(b'keep exact bytes')
        with patch.object(cli.Client, 'request', wraps=cli.Client(self.url).request) as request:
            code, result = self.invoke('run', '--ticket', str(ticket), '--approve', '--out', str(output))
        self.assertEqual(self.studio.calls, 0, 'Output collision must be refused before shared-worker dispatch')
        self.assertEqual(request.call_count, 0)
        self.assertEqual(code, 2, result)
        self.assertEqual(output.read_bytes(), b'keep exact bytes')

    def test_missing_directory_is_rejected_before_prepare_request(self):
        self.ticket()
        with patch.object(cli.Client, 'request', wraps=cli.Client(self.url).request) as request:
            code, _ = self.invoke('prepare', '--recipe', str(Path(self.temp.name) / 'recipe.json'),
                                  '--out', str(Path(self.temp.name) / 'missing' / 'ticket.json'))
        self.assertEqual(code, 2)
        self.assertEqual(request.call_count, 0)

    def test_dangling_symlink_is_not_an_available_output(self):
        ticket = self.ticket(); output = Path(self.temp.name) / 'dangling.json'
        try: output.symlink_to(Path(self.temp.name) / 'absent.json')
        except OSError: self.skipTest('Symlink creation is unavailable')
        code, _ = self.invoke('run', '--ticket', str(ticket), '--approve', '--out', str(output))
        self.assertEqual(code, 2)
        self.assertEqual(self.studio.calls, 0)
        self.assertTrue(output.is_symlink())
        self.assertFalse(output.exists())

    def test_export_race_preserves_known_job_response_and_competing_file(self):
        ticket = self.ticket(); output = Path(self.temp.name) / 'result.json'
        original = cli.Client.request
        def racing(client, *args, **kwargs):
            result = original(client, *args, **kwargs)
            output.write_bytes(b'other writer won')
            return result
        with patch.object(cli.Client, 'request', racing):
            code, result = self.invoke('run', '--ticket', str(ticket), '--approve', '--out', str(output))
        self.assertEqual(self.studio.calls, 1)
        self.assertIn('result', result, 'Known dispatch response was lost after local export failed')
        self.assertEqual(result['result']['job']['id'], next(iter(self.studio.jobs)))
        self.assertTrue(result['response_received'])
        self.assertEqual(result['code'], 'local_output_error')
        self.assertEqual(code, 2)
        self.assertEqual(output.read_bytes(), b'other writer won')

    def test_known_preparation_survives_export_failure(self):
        self.ticket(); output = Path(self.temp.name) / 'next-ticket.json'
        original = cli.Client.request
        def racing(client, *args, **kwargs):
            result = original(client, *args, **kwargs); output.mkdir(); return result
        with patch.object(cli.Client, 'request', racing):
            code, result = self.invoke('prepare', '--recipe', str(Path(self.temp.name) / 'recipe.json'), '--out', str(output))
        self.assertEqual(code, 2)
        self.assertIn('result', result)
        self.assertIn('recipe', result['result'])
        self.assertEqual(self.studio.calls, 0)

    def test_existing_directory_blocks_dispatch(self):
        ticket = self.ticket()
        code, result = self.invoke('run', '--ticket', str(ticket), '--approve', '--out', self.temp.name)
        self.assertEqual(code, 2, result)
        self.assertEqual(self.studio.calls, 0)
        self.assertFalse(result['request_sent'])

    def test_partial_output_is_retained_with_the_complete_received_response(self):
        ticket = self.ticket(); output = Path(self.temp.name) / 'partial.json'
        original = Path.open
        class FailingWrite:
            def __enter__(self):
                self.stream = original(output, 'x', encoding='utf-8')
                return self
            def write(self, text):
                self.stream.write(text[:12]); self.stream.flush()
                raise OSError('Synthetic disk full')
            def __exit__(self, *_): self.stream.close()
        def fail(path, *args, **kwargs):
            return FailingWrite() if path == output else original(path, *args, **kwargs)
        with patch.object(Path, 'open', fail):
            code, result = self.invoke('run', '--ticket', str(ticket), '--approve', '--out', str(output))
        self.assertEqual(code, 2)
        self.assertEqual(self.studio.calls, 1)
        self.assertTrue(result['response_received'])
        self.assertIn('job', result['result'])
        expected_prefix = json.dumps(result['result'], ensure_ascii=False, indent=2, allow_nan=False)[:12]
        self.assertEqual(output.read_text(encoding='utf-8'), expected_prefix)

    def test_successful_output_and_stdout_preserve_wide_integers(self):
        ticket = self.ticket(); output = Path(self.temp.name) / 'result.json'; wide = 2**63 - 1
        # Additional inert job metadata exercises the real HTTP JSON and both CLI outputs.
        self.studio.public = lambda job: dict(job, seed=wide)
        code, result = self.invoke('run', '--ticket', str(ticket), '--approve', '--out', str(output))
        self.assertEqual(code, 0, result)
        self.assertEqual(result['job']['seed'], wide)
        self.assertEqual(json.loads(output.read_bytes()), result)
        self.assertEqual(self.studio.calls, 1)

    def test_genuinely_lost_run_response_retains_uncertainty(self):
        ticket = self.ticket()
        original = cli.Client.request
        def lose(client, *args, **kwargs):
            original(client, *args, **kwargs); raise TimeoutError('lost response')
        with patch.object(cli.Client, 'request', lose):
            code, result = self.invoke('run', '--ticket', str(ticket), '--approve')
        self.assertEqual(self.studio.calls, 1)
        self.assertEqual(code, 3)
        self.assertNotIn('result', result)
        self.assertIn('same ticket', result['recovery'])


if __name__ == '__main__': unittest.main()

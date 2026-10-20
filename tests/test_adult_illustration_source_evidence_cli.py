"""Operator retention, offline resolution and explicit pruning use fixture metadata."""
import base64
from contextlib import closing, redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch

from scripts.studio_adult_illustration_source_fetch import main
from tests.test_adult_illustration_source_transport_cli import FakeExchange


class SourceEvidenceCliTests(unittest.TestCase):
    def command(self, args, exchange=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), patch('socket.create_connection', side_effect=AssertionError('Sockets forbidden')):
            code = main(args, exchange=exchange)
        return code, json.loads(stdout.getvalue() or stderr.getvalue())

    def test_fetch_resolve_and_prune_keep_bytes_and_authority_honest(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); output = root/'fetch.json'; evidence = root/'evidence'
            args = ['huggingface', '--repo', 'owner/model', '--revision', 'main', '--allow-network', '--evidence-dir', str(evidence), '--out', str(output)]
            with redirect_stdout(io.StringIO()), patch('socket.create_connection', side_effect=AssertionError('Sockets forbidden')):
                self.assertEqual(main(args, exchange=FakeExchange()), 0)
            fetched = json.loads(output.read_bytes())
            code, resolved = self.command(['resolve', '--ref', str(output), '--evidence-dir', str(evidence)])
            self.assertEqual(code, 0); self.assertEqual(resolved['state'], 'available')
            raw = base64.b64decode(resolved['body_base64'], validate=True)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), fetched['snapshot']['raw_payload_sha256'])
            self.assertFalse(resolved['execution_authorized']); self.assertFalse(resolved['generation_submitted'])
            code, pruned = self.command(['prune', '--evidence-dir', str(evidence), '--sha256', fetched['raw_payload_ref']['sha256']])
            self.assertEqual(code, 0); self.assertEqual(pruned['state'], 'pruned')
            self.assertEqual(self.command(['resolve', '--ref', str(output), '--evidence-dir', str(evidence)])[1]['state'], 'pruned')

    def test_quota_is_distinguishable_from_fetch_parse_and_cache_success(self):
        with tempfile.TemporaryDirectory() as root:
            code, fetched = self.command(['huggingface', '--repo', 'owner/model', '--revision', 'main', '--allow-network',
                '--evidence-dir', str(Path(root)/'evidence'), '--evidence-max-bytes', '1'], FakeExchange())
            self.assertEqual(code, 0); self.assertEqual(fetched['raw_payload_ref']['retention_state'], 'quota_exceeded')
            self.assertEqual(fetched['snapshot']['record']['immutable_revision'], 'a'*40)
            exchange = FakeExchange()
            code, error = self.command(['huggingface', '--repo', 'owner/model', '--revision', 'main', '--allow-network', '--evidence-max-bytes', '1'], exchange)
            self.assertEqual(code, 2); self.assertIn('evidence-dir', error['error']); self.assertEqual(exchange.calls, [])

    def test_resolver_refuses_oversized_input_and_does_not_create_a_missing_store(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = root/'ref.json'; source.write_text('{}')
            missing = root/'missing'
            code, _ = self.command(['resolve', '--ref', str(source), '--evidence-dir', str(missing)])
            self.assertEqual(code, 2); self.assertFalse(missing.exists())
            with source.open('wb') as output: output.truncate(4_194_305)
            code, error = self.command(['resolve', '--ref', str(source)])
            self.assertEqual(code, 2); self.assertIn('oversized', error['error'])

    def test_resolver_reports_blob_provenance_as_corrupt_without_escaping(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); evidence = root/'evidence'; source = root/'ref.json'
            code, fetched = self.command(['huggingface', '--repo', 'owner/model', '--revision', 'main', '--allow-network',
                '--evidence-dir', str(evidence)], FakeExchange())
            self.assertEqual(code, 0); source.write_text(json.dumps(fetched))
            with closing(sqlite3.connect(evidence/'payload-evidence.sqlite3')) as db, db:
                db.execute('UPDATE observations SET document=CAST(document AS BLOB) WHERE id=?',
                           (fetched['raw_payload_ref']['observation_id'],))
            code, resolved = self.command(['resolve', '--ref', str(source), '--evidence-dir', str(evidence)])
            self.assertEqual(code, 0); self.assertEqual(resolved['state'], 'corrupt')
            self.assertFalse(resolved['execution_authorized']); self.assertFalse(resolved['generation_submitted'])

    def test_unretained_capture_state_survives_different_and_recreated_cli_store(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); evidence = root/'evidence'; other = root/'other'; source = root/'ref.json'
            fetch = ['huggingface', '--repo', 'owner/model', '--revision', 'main', '--allow-network']
            code, quota = self.command(fetch + ['--evidence-dir', str(evidence), '--evidence-max-bytes', '1'], FakeExchange())
            self.assertEqual(code, 0); self.assertEqual(quota['raw_payload_ref']['retention_state'], 'quota_exceeded')
            code, retained = self.command(fetch + ['--evidence-dir', str(other)], FakeExchange())
            self.assertEqual(code, 0)
            for value, target, expected in ((quota, other, 'quota_exceeded'), (retained, evidence, 'store_mismatch')):
                source.write_text(json.dumps(value))
                code, resolved = self.command(['resolve', '--ref', str(source), '--evidence-dir', str(target)])
                self.assertEqual(code, 0); self.assertEqual(resolved['state'], expected)
            (evidence/'payload-evidence.sqlite3').unlink()
            self.assertEqual(self.command(fetch + ['--evidence-dir', str(evidence)], FakeExchange())[0], 0)
            source.write_text(json.dumps(quota))
            code, resolved = self.command(['resolve', '--ref', str(source), '--evidence-dir', str(evidence)])
            self.assertEqual(code, 0); self.assertEqual(resolved['state'], 'quota_exceeded')
            self.assertIsNone(resolved['body_base64']); self.assertFalse(resolved['execution_authorized'])


if __name__ == '__main__': unittest.main()

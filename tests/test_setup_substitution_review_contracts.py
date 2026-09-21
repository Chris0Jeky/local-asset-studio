"""Review findings for the atomic setup substitution boundary."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_setup_substitution as F
from studio_workflow import agent_bridge as A
from studio_workflow import setup_substitution as S


class SetupSubstitutionReviewContracts(unittest.TestCase):
    def test_review_revision_must_be_a_content_addressed_sha256(self):
        value = F.substitution_request()
        value['profile']['review_revision'] = 'review:latest'
        with self.assertRaisesRegex(ValueError, 'review revision|sha256|SHA-256|immutable'):
            S.request(value)

    def test_cli_rejects_oversized_request_without_unbounded_read_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'oversized.json'
            path.write_bytes(b'0' * (S.MAX_BYTES + 1))
            output = io.StringIO()
            with mock.patch.object(
                    Path, 'read_bytes',
                    side_effect=AssertionError('unbounded Path.read_bytes used')):
                with mock.patch('sys.stdout', output):
                    code = S.main([str(path)])
        self.assertEqual(code, 2)
        error = json.loads(output.getvalue())
        self.assertEqual(error['error']['code'], 'invalid_substitution')
        self.assertRegex(error['error']['message'], '448 KiB|limit|exceeds')

    def test_agent_discovery_advertises_the_substitute_authorization_contract(self):
        spec = A.TOOLS['setup_draft_command']
        description = spec['description'].lower()
        self.assertIn('substitute', description)
        self.assertIn('proposal', description)
        self.assertIn('hash', description)
        self.assertIn('revision', description)
        self.assertIn('never generates', description)
        self.assertTrue(spec['mutating'])
        self.assertEqual(spec['mode'], 'author')


if __name__ == '__main__':
    unittest.main()

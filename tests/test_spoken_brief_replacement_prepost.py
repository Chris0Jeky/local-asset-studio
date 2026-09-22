"""Pre-POST validation failures must not become uncertain inference attempts."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from spoken_brief_archive import inspect_run
from spoken_brief_compile import SpokenBriefError
from spoken_brief_fixture import Fixture
from spoken_brief_qa import FINDINGS, record_review
from spoken_brief_runtime import run
from spoken_brief_transport import StudioClient


class ReplacementPrePostRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.m = importlib.import_module('spoken_brief_replacement')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        source = Path(self.temp.name).resolve() / 'COMPRESSED.md'
        source.write_text(
            '# Brief\n\nLAS has seventeen checks.\n\nKeep all other audio.',
            encoding='utf-8',
        )
        result = run(source, base_url=self.fixture.base_url)
        self.directory = Path(result['receipt']).parent
        archive = inspect_run(self.directory)
        self.segment = archive['segments'][1]
        self.review = record_review(
            self.directory,
            self.segment['id'],
            self.segment['audio_sha256'],
            decision='replace',
            findings={
                key: 'needs-work' if key == 'pronunciation' else 'not-reviewed'
                for key in FINDINGS
            },
            reviewer='owner',
            reason='Please correct the project acronym.',
        )['id']
        self.request_count = len(self.fixture.requests)

    def prepare(self):
        return self.m.prepare(
            self.directory,
            self.segment['id'],
            self.review,
            'pronounce-v1',
        )

    def state(self):
        path = self.directory / 'replacements' / 'pronounce-v1' / 'state.json'
        import json
        return json.loads(path.read_bytes())

    def creates(self):
        return [
            request for request in self.fixture.requests[self.request_count:]
            if request[:2] == ('POST', '/api/voice-baseline')
        ]

    def starts(self):
        return [
            request for request in self.fixture.requests[self.request_count:]
            if request[0] == 'POST' and request[1].endswith('/start')
        ]

    def identity_failure(self, ordinal):
        original = StudioClient.get_json
        calls = 0

        def failing(client, path):
            nonlocal calls
            if path == '/api/identity':
                calls += 1
                if calls == ordinal:
                    raise SpokenBriefError('Transient identity observation failure')
            return original(client, path)

        return failing

    def test_failed_validation_after_create_intent_restores_prepared(self):
        self.prepare()
        with patch.object(StudioClient, 'get_json', new=self.identity_failure(2)):
            with self.assertRaisesRegex(SpokenBriefError, 'identity observation'):
                self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('prepared', self.state()['status'])
        self.assertEqual([], self.creates())
        self.assertEqual([], self.starts())

        self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates()))
        self.assertEqual(1, len(self.starts()))

    def test_failed_validation_after_start_intent_restores_created(self):
        self.prepare()
        with patch.object(StudioClient, 'get_json', new=self.identity_failure(5)):
            with self.assertRaisesRegex(SpokenBriefError, 'identity observation'):
                self.m.start(self.directory, 'pronounce-v1')
        retained = self.state()
        self.assertEqual('created', retained['status'])
        self.assertIsNotNone(retained['project_id'])
        self.assertIsNotNone(retained['project_plan'])
        self.assertEqual(1, len(self.creates()))
        self.assertEqual([], self.starts())

        self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates()))
        self.assertEqual(1, len(self.starts()))


if __name__ == '__main__':
    unittest.main()

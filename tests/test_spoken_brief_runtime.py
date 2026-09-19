import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief
import spoken_brief_transport
from spoken_brief_fixture import Fixture, wav_bytes


class SpokenBriefTests(unittest.TestCase):
    def test_assembly_inserts_exact_silence_without_reencoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); first = root / 'a.wav'; second = root / 'b.wav'; output = root / 'joined.wav'
            first.write_bytes(wav_bytes(100, 11)); second.write_bytes(wav_bytes(200, 22))
            receipt = spoken_brief.assemble_wav([
                {'path': first, 'id': 'a', 'pause_after_ms': 100},
                {'path': second, 'id': 'b', 'pause_after_ms': 0},
            ], output)
            with wave.open(str(output), 'rb') as joined:
                self.assertEqual(joined.getparams()[:4], (1, 2, 48000, 5100))
                frames = joined.readframes(joined.getnframes())
            self.assertEqual(frames[:200], (11).to_bytes(2, 'little', signed=True) * 100)
            self.assertEqual(frames[200:200 + 9600], b'\0' * 9600)
            self.assertEqual(frames[-400:], (22).to_bytes(2, 'little', signed=True) * 200)
            self.assertEqual(receipt['samples'], 5100)
            self.assertEqual(receipt['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_one_run_uses_voice_projects_and_produces_one_received_wav(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir()
            (pack / 'COMPRESSED.md').write_text('# Brief\n\nFirst decision. Second decision.\n\n## Risks\n\nOne risk remains.', encoding='utf-8')
            result = spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            output = Path(result['output'])
            self.assertTrue(output.is_file()); self.assertEqual(output.suffix, '.wav')
            self.assertTrue(Path(result['receipt']).is_file())
            posts = [request for request in fixture.requests if request[0] == 'POST']
            self.assertEqual([path for _, path, _, _ in posts].count('/api/voice-baseline'), len(result['projects']))
            self.assertTrue(all(origin == fixture.base_url for method, _, origin, _ in posts if method == 'POST'))
            self.assertTrue(all(body['speaker_id'] == 'brief-narrator' for method, path, _, body in posts if path == '/api/voice-baseline'))
            receipt = json.loads(Path(result['receipt']).read_text(encoding='utf-8'))
            self.assertEqual(receipt['studio'], {'base_url': fixture.base_url, 'identity': {'app': 'local-asset-studio'}})
            self.assertEqual(receipt['source']['sha256'], hashlib.sha256((pack / 'COMPRESSED.md').read_bytes()).hexdigest())
            self.assertEqual(receipt['output']['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_explicit_client_rejection_can_be_fixed_and_retried_without_uncertainty(self):
        fixture = Fixture(); self.addCleanup(fixture.close); fixture.create_rejection = 400
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); (pack / 'COMPRESSED.md').write_text('Only one sentence.', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'voice bundle is not configured'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            fixture.create_rejection = None
            result = spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertTrue(Path(result['output']).is_file())
            creates = [request for request in fixture.requests if request[0] == 'POST' and request[1] == '/api/voice-baseline']
            self.assertEqual(len(creates), 2)

    def test_powershell_wrapper_is_a_thin_argument_safe_adapter(self):
        wrapper = Path(__file__).parents[1] / 'scripts' / 'speak-handoff.ps1'
        text = wrapper.read_text(encoding='utf-8')
        self.assertIn('spoken_brief.py', text)
        self.assertIn('& $python', text)
        self.assertIn("$command = 'plan'", text)
        self.assertIn('InvariantCulture', text)
        self.assertNotIn('Invoke-Expression', text)


    def test_loopback_client_does_not_follow_redirects(self):
        fixture = Fixture(); self.addCleanup(fixture.close); fixture.identity_redirect = '/redirected-identity'
        client = spoken_brief.StudioClient(fixture.base_url)
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'HTTP 302'):
            client.get_json('/api/identity')
        self.assertEqual([path for method, path, _, _ in fixture.requests if method == 'GET'], ['/api/identity'])


    def test_loopback_json_response_is_bounded(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        client = spoken_brief.StudioClient(fixture.base_url)
        with patch.object(spoken_brief_transport, 'MAX_JSON_BYTES', 32):
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'response limit'):
                client.get_json('/oversized-json')

    def test_non_loopback_studio_url_is_rejected(self):
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'loopback'):
            spoken_brief.StudioClient('https://example.test')



if __name__ == '__main__': unittest.main()

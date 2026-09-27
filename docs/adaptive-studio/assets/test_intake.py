"""Offline intake tests; no network, no providers, no application services."""
import http.client
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent


def png(width, height, colour_type=6):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, colour_type, 0, 0, 0)) + chunk(b'IEND', b'')


def jpeg(width, height):
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00' + b'\x00' * 9
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, height, width, 1) + b'\x01\x11\x00'
    return b'\xff\xd8' + app0 + sof + b'\xff\xd9'


def webp_lossless(width, height, alpha):
    bits = (width - 1) | ((height - 1) << 14) | (int(alpha) << 28)
    body = b'\x2f' + bits.to_bytes(4, 'little')
    return b'RIFF' + struct.pack('<I', 4 + 8 + len(body)) + b'WEBP' + b'VP8L' + struct.pack('<I', len(body)) + body


class IntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('asset_intake', ROOT / 'intake.py')
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kit = Path(self.tmp.name)
        for name in ('catalog.csv', 'receipt-template.json', 'CHATGPT-PROMPT-PACK.md'):
            shutil.copyfile(ROOT / name, self.kit / name)
        (self.kit / 'inbox').mkdir()
        self.out = io.StringIO()
        self.err = io.StringIO()

    def tearDown(self):
        self.tmp.cleanup()

    def run_receipts(self, provider='chatgpt'):
        with patch('sys.stdout', self.out), patch('sys.stderr', self.err):
            return self.mod.receipts(self.kit, now='2026-09-27T00:00:00+00:00', provider=provider)

    def receipt(self, stem):
        return json.loads((self.kit / 'receipts' / (stem + '.json')).read_text(encoding='utf-8'))

    def test_header_sizes_and_alpha(self):
        self.assertEqual(self.mod.image_info(png(1536, 1024)), ('png', 1536, 1024, True))
        self.assertEqual(self.mod.image_info(png(8, 4, colour_type=2)), ('png', 8, 4, False))
        self.assertEqual(self.mod.image_info(jpeg(1200, 900)), ('jpeg', 1200, 900, False))
        self.assertEqual(self.mod.image_info(webp_lossless(768, 512, True)), ('webp', 768, 512, True))
        with self.assertRaises(ValueError):
            self.mod.image_info(b'GIF89a' + b'\x00' * 20)
        for truncated in (png(4, 4)[:20], jpeg(4, 4)[:18], webp_lossless(4, 4, False)[:22]):
            with self.assertRaises(ValueError):
                self.mod.image_info(truncated)

    def test_receipt_records_actual_bytes_and_the_prompt_section(self):
        data = png(1536, 1024)
        (self.kit / 'inbox' / 'workflow-create--1536x1024--candidate-1.png').write_bytes(data)
        (self.kit / 'inbox' / 'notes.txt').write_text('ignored', encoding='utf-8')
        self.assertEqual(self.run_receipts(), 0, self.err.getvalue())
        receipt = json.loads((self.kit / 'receipts' / 'workflow-create--1536x1024--candidate-1.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['status'], 'candidate-produced')
        self.assertEqual(receipt['requested_asset_id'], 'workflow-create')
        self.assertEqual(receipt['files'][0]['relative_path'], 'inbox/workflow-create--1536x1024--candidate-1.png')
        self.assertEqual(receipt['files'][0]['sha256'], self.mod.sha256(data))
        self.assertEqual((receipt['files'][0]['width'], receipt['files'][0]['height'], receipt['files'][0]['alpha']), (1536, 1024, True))
        self.assertIsNone(receipt['production']['reported_model'])
        self.assertRegex(receipt['brief_revision'], r'section sha256:[a-f0-9]{64}$')
        self.assertEqual(receipt['art_review']['status'], 'not-reviewed')
        self.assertNotIn('file_entry_instructions', receipt)
        self.assertIn('skip     notes.txt', self.out.getvalue())

    def test_derivative_names_its_anchor_and_size_mismatch_is_recorded(self):
        (self.kit / 'inbox' / 'retro-anime-quiet--1536x1024--candidate-2.png').write_bytes(png(1024, 1024))
        self.assertEqual(self.run_receipts(), 0, self.err.getvalue())
        receipt = json.loads((self.kit / 'receipts' / 'retro-anime-quiet--1536x1024--candidate-2.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['production']['input_anchors'][0]['asset_id'], 'retro-anime-master')
        self.assertEqual(receipt['production']['tool_action'], 'edit with uploaded anchor')
        self.assertTrue(any('1536x1024' in u and '1024x1024' in u for u in receipt['unknowns']))

    def test_pack_anchor_is_recorded_even_when_the_catalogue_row_has_none(self):
        (self.kit / 'inbox' / 'workflow-combine--candidate-1.png').write_bytes(png(1536, 1024))
        (self.kit / 'inbox' / 'reference-pose--candidate-1.png').write_bytes(png(1024, 1536))
        self.assertEqual(self.run_receipts(), 0, self.err.getvalue())
        combine = self.receipt('workflow-combine--candidate-1')
        self.assertEqual([a['asset_id'] for a in combine['production']['input_anchors']], ['workflow-create'])
        self.assertEqual(combine['production']['tool_action'], 'edit with uploaded anchor')
        pose = self.receipt('reference-pose--candidate-1')
        self.assertEqual((pose['production']['input_anchors'], pose['production']['tool_action']), ([], 'generate'))

    def test_provider_is_never_assumed(self):
        (self.kit / 'inbox' / 'retro-anime-master--candidate-1.png').write_bytes(png(1920, 1088, colour_type=2))
        (self.kit / 'inbox' / 'workflow-create--candidate-1.png').write_bytes(png(1536, 1024))
        self.assertEqual(self.run_receipts(provider=None), 0, self.err.getvalue())
        unnamed = self.receipt('workflow-create--candidate-1')
        self.assertIsNone(unnamed['production']['provider'])
        self.assertIsNone(unnamed['brief_revision'])
        self.assertTrue(any('Provider is unknown' in u for u in unnamed['unknowns']))
        shutil.rmtree(self.kit / 'receipts')
        self.assertEqual(self.run_receipts(provider='GPU lab, Studio krea-environment'), 0, self.err.getvalue())
        lab = self.receipt('retro-anime-master--candidate-1')
        self.assertEqual(lab['production']['provider'], 'GPU lab, Studio krea-environment')
        self.assertIsNone(lab['production']['prompt_record'])
        self.assertFalse(any('Image 2.5' in u for u in lab['unknowns']))

    def test_truncated_image_gets_a_receipt_with_unknown_size(self):
        (self.kit / 'inbox' / 'state-blank--candidate-1.png').write_bytes(png(4, 4)[:20])
        self.assertEqual(self.run_receipts(), 0, self.err.getvalue())
        receipt = self.receipt('state-blank--candidate-1')
        self.assertIsNone(receipt['files'][0]['width'])
        self.assertTrue(any('truncated' in u for u in receipt['unknowns']))

    def test_unreadable_existing_receipt_is_left_alone(self):
        (self.kit / 'inbox' / 'state-blank--candidate-1.png').write_bytes(png(4, 4))
        (self.kit / 'inbox' / 'state-conflict--candidate-1.png').write_bytes(png(4, 4))
        (self.kit / 'receipts').mkdir()
        (self.kit / 'receipts' / 'state-blank--candidate-1.json').write_text('{not json', encoding='utf-8')
        self.assertEqual(self.run_receipts(), 2)
        self.assertIn('unreadable', self.err.getvalue())
        self.assertEqual((self.kit / 'receipts' / 'state-blank--candidate-1.json').read_text(encoding='utf-8'), '{not json')
        self.assertTrue((self.kit / 'receipts' / 'state-conflict--candidate-1.json').is_file())

    def test_rerun_is_idempotent_and_a_replaced_file_is_refused(self):
        path = self.kit / 'inbox' / 'state-blank--candidate-1.png'
        path.write_bytes(png(1024, 1024))
        self.assertEqual(self.run_receipts(), 0)
        first = (self.kit / 'receipts' / 'state-blank--candidate-1.json').read_bytes()
        self.assertEqual(self.run_receipts(), 0)
        self.assertIn('same     state-blank--candidate-1.png', self.out.getvalue())
        path.write_bytes(png(512, 512))
        self.assertEqual(self.run_receipts(), 2)
        self.assertIn('new candidate number', self.err.getvalue())
        self.assertEqual(first, (self.kit / 'receipts' / 'state-blank--candidate-1.json').read_bytes())

    def test_bad_names_and_unknown_ids_are_refused_without_receipts(self):
        (self.kit / 'inbox' / 'image.png').write_bytes(png(4, 4))
        (self.kit / 'inbox' / 'not-a-real-asset--candidate-1.png').write_bytes(png(4, 4))
        self.assertEqual(self.run_receipts(), 2)
        self.assertIn('expected <asset-id>', self.err.getvalue())
        self.assertIn('not a catalogue ID', self.err.getvalue())
        self.assertFalse((self.kit / 'receipts').exists())

    def test_receipts_write_only_inside_receipts(self):
        (self.kit / 'inbox' / 'workflow-pose--candidate-1.jpg').write_bytes(jpeg(1200, 900))
        before = {p.relative_to(self.kit): p.read_bytes() for p in self.kit.rglob('*') if p.is_file()}
        self.assertEqual(self.run_receipts(), 0, self.err.getvalue())
        after = {p.relative_to(self.kit): p.read_bytes() for p in self.kit.rglob('*') if p.is_file()}
        self.assertEqual({k for k in after if k not in before}, {Path('receipts/workflow-pose--candidate-1.json')})
        self.assertTrue(all(after[k] == v for k, v in before.items()))

    def write_manifest(self, entries):
        (self.kit / 'acquired').mkdir(exist_ok=True)
        (self.kit / 'acquired' / 'MANIFEST.json').write_text(json.dumps({'version': 1, 'entries': entries}), encoding='utf-8')

    def entry(self, file, data, **extra):
        return dict({'id': file, 'file': file, 'sha256': self.mod.sha256(data), 'bytes': len(data), 'licence': 'CC0-1.0', 'url': 'https://dl.polyhaven.org/x/' + file}, **extra)

    def test_verify_reports_missing_and_corrupt(self):
        good, bad = b'good bytes', b'expected'
        self.write_manifest([self.entry('a.jpg', good), self.entry('sub/b.jpg', bad), self.entry('c.jpg', b'absent')])
        (self.kit / 'acquired' / 'a.jpg').write_bytes(good)
        (self.kit / 'acquired' / 'sub').mkdir()
        (self.kit / 'acquired' / 'sub' / 'b.jpg').write_bytes(b'changed')
        with patch('sys.stdout', self.out):
            self.assertEqual(self.mod.verify(self.kit), 1)
        self.assertIn('1 ok, 1 missing, 1 corrupt', self.out.getvalue())

    def test_manifest_refuses_traversal_and_unlisted_licences(self):
        for bad in (self.entry('../escape.jpg', b'x'), self.entry('a.jpg', b'x', licence='CC-BY-4.0'), self.entry('a.jpg', b'x', url='http://dl.polyhaven.org/a.jpg')):
            self.write_manifest([bad])
            with self.subTest(bad=bad['file'] + bad['licence'] + bad['url']), self.assertRaises(ValueError):
                self.mod.manifest(self.kit)

    def test_fetch_keeps_only_matching_bytes_and_reads_one_zip_member(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('Paper_Color.jpg', b'colour map')
            archive.writestr('Paper.blend', b'never extracted')
        served = {'https://ambientcg.com/get?file=Paper.zip': buffer.getvalue(), 'https://dl.polyhaven.org/x/wrong.jpg': b'tampered'}
        self.write_manifest([self.entry('t/Paper_Color.jpg', b'colour map', url='https://ambientcg.com/get?file=Paper.zip', archive={'member': 'Paper_Color.jpg'}),
                             self.entry('wrong.jpg', b'original')])
        with patch.object(self.mod, 'download', side_effect=lambda url: served[url]), patch('sys.stdout', self.out), patch('sys.stderr', self.err):
            self.assertEqual(self.mod.fetch(self.kit), 2)
        self.assertEqual((self.kit / 'acquired' / 't' / 'Paper_Color.jpg').read_bytes(), b'colour map')
        self.assertFalse((self.kit / 'acquired' / 'wrong.jpg').exists())
        self.assertFalse((self.kit / 'acquired' / 't' / 'Paper.blend').exists())
        self.assertIn('nothing was written', self.err.getvalue())

    def test_fetch_never_overwrites_a_different_local_file_and_survives_bad_downloads(self):
        self.write_manifest([self.entry('kept.jpg', b'original'), self.entry('cut.jpg', b'whole'), self.entry('zip.jpg', b'z', archive={'member': 'z.jpg'})])
        (self.kit / 'acquired' / 'kept.jpg').write_bytes(b'owner edit')
        def serve(url):
            if url.endswith('cut.jpg'):
                raise http.client.IncompleteRead(b'wh')
            return b'not a zip'
        with patch.object(self.mod, 'download', side_effect=serve) as fetched, patch('sys.stdout', self.out), patch('sys.stderr', self.err):
            self.assertEqual(self.mod.fetch(self.kit), 2)
        self.assertEqual((self.kit / 'acquired' / 'kept.jpg').read_bytes(), b'owner edit')
        self.assertNotIn('kept.jpg', [c.args[0].rsplit('/', 1)[-1] for c in fetched.call_args_list])
        self.assertIn('never overwrites', self.err.getvalue())
        self.assertIn('cut.jpg', self.err.getvalue())
        self.assertIn('zip.jpg', self.err.getvalue())

    def test_download_refuses_hosts_outside_the_allow_list(self):
        with patch.object(self.mod.urllib.request, 'urlopen') as opened, self.assertRaisesRegex(ValueError, 'allow-listed'):
            self.mod.download('https://example.com/icon.svg')
        opened.assert_not_called()

    def test_tracked_manifest_is_valid_and_permissively_licensed(self):
        data = self.mod.manifest(ROOT)
        self.assertGreater(len(data['entries']), 0)
        self.assertEqual(len({e['file'] for e in data['entries']}), len(data['entries']))
        for entry in data['entries']:
            self.assertIn(entry['licence'], {'CC0-1.0', 'MIT', 'OFL-1.1', 'Apache-2.0'})
            self.assertIn(self.mod.urlparse(entry['url']).hostname, self.mod.FETCH_HOSTS)
            self.assertTrue(entry.get('use') and entry.get('note') and entry.get('retrieved') and entry.get('licence_url'), entry['file'])

    def test_missing_inbox_is_a_clear_no_op(self):
        shutil.rmtree(self.kit / 'inbox')
        self.assertEqual(self.run_receipts(), 0)
        self.assertIn('No inbox yet', self.out.getvalue())
        self.assertFalse((self.kit / 'receipts').exists())

    def test_cli_rejects_unknown_commands_without_a_traceback(self):
        result = subprocess.run([sys.executable, str(ROOT / 'intake.py'), 'publish'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()

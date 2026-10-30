"""#1837: an externally repaired PNG imported from its picture stays in that picture's family, unreviewed."""
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from test_server import server, png, PRESET, GRAPH


def repaired():
    stream = io.BytesIO(); Image.new('RGB', (8, 12), 'orange').save(stream, 'PNG'); return stream.getvalue()


class ImportRepairedVersionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'presets').mkdir(); (self.root/'workflows/api').mkdir(parents=True)
        (self.root/'config').mkdir(); (self.root/'fake-comfy/input').mkdir(parents=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root': str(self.root/'fake-comfy')}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': [PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        start = patch.object(threading.Thread, 'start', lambda *_: None); start.start(); self.addCleanup(start.stop)
        self.studio = server.Studio(self.root)
        self.parent = self.studio.import_image('broken.png', 'image/png', png())['asset']
        self.private = self.studio.import_image('hidden.png', 'image/png', png(), privacy='private')['asset']

    def tree(self):
        files = {str(p.relative_to(self.root)): p.stat().st_size for p in self.root.rglob('*')
                 if p.is_file() and 'assets.sqlite3' not in p.name}
        return files, len(self.studio.jobs), len(self.studio.assets.snapshot(privacy='all')['assets'])

    def family(self, studio, asset_id):
        from studio_workflow import asset_family
        return asset_family.observe(studio, asset_id, workspace_id=studio.assets.snapshot()['workspace_id'], children=True)

    def test_repair_links_to_its_parent_and_survives_a_restart(self):
        child = self.studio.import_image('fixed.png', 'image/png', repaired(), parent=self.parent['id'], note='  Cleaned the hand in Krita ')['asset']
        self.assertEqual(child['lineage'], [self.parent['id']])
        self.assertEqual(child['source']['editor_note'], 'Cleaned the hand in Krita')
        restarted = server.Studio(self.root)
        report = self.family(restarted, child['id'])
        self.assertEqual([n['id'] for n in report['nodes']], [self.parent['id'], child['id']])
        self.assertEqual(report['edges'], [{'parent': self.parent['id'], 'child': child['id']}])
        self.assertEqual([n['id'] for n in self.family(restarted, self.parent['id'])['children']], [child['id']])
        job = next(j for j in restarted.jobs.values() if j.get('outputs', [{}])[0].get('asset_id') == child['id'])
        self.assertEqual((job['operation'], job['parent_assets']), ('asset.import', [self.parent['id']]))

    def test_parent_bytes_and_record_are_unchanged_and_repair_is_unreviewed(self):
        with self.studio.assets.connection() as db:
            db.execute("UPDATE assets SET review='selected' WHERE id=?", (self.parent['id'],))
        before = self.studio.assets.get(self.parent['id']); path = self.studio.assets.file(self.parent['id'])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        child = self.studio.import_image('fixed.png', 'image/png', repaired(), parent=self.parent['id'])['asset']
        self.assertEqual(self.studio.assets.get(self.parent['id']), before)
        self.assertEqual(hashlib.sha256(self.studio.assets.file(self.parent['id']).read_bytes()).hexdigest(), digest)
        self.assertEqual((child['review'], child['favorite'], child['notes']), ('unreviewed', False, ''))
        self.assertNotEqual(child['sha256'], before['sha256'])

    def test_refused_parents_write_nothing(self):
        video = self.root/'clip.bin'; video.write_bytes(b'not a picture')
        clip = self.studio.assets.register({'id': 'clip-job', 'created_at': 1, 'preset_name': 'Clip', 'outputs': [{'filename': 'clip.bin', 'media_type': 'video'}]}, 0, video)
        binned = self.studio.import_image('binned.png', 'image/png', png())['asset']
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET trashed_at=1 WHERE id=?', (binned['id'],))
        cases = {'missing': ('0'*32, 'regular', 'not in this Library'), 'bad type': (['x'], 'regular', 'Choose the picture'),
                 'private parent, regular import': (self.private['id'], 'regular', 'not in this Library'),
                 'regular parent, private import': (self.parent['id'], 'private', 'not in this Library'),
                 'not an image': (clip, 'regular', 'Only a picture'), 'in the Bin': (binned['id'], 'regular', 'Bin')}
        before = self.tree()
        for name, (parent, privacy, message) in cases.items():
            with self.subTest(name), self.assertRaisesRegex(server.StudioError, message):
                self.studio.import_image('fixed.png', 'image/png', repaired(), privacy=privacy, parent=parent)
            self.assertEqual(self.tree(), before)
        with self.assertRaisesRegex(server.StudioError, 'never linked'):  # an all-scope read reaches the other privacy; the link is still refused
            self.studio.import_image('fixed.png', 'image/png', repaired(), parent=self.private['id'], scope='all')
        self.assertEqual(self.tree(), before)

    def test_repair_must_be_a_png_and_the_note_plain_and_short(self):
        before = self.tree()
        for kind, name, body in (('image/jpeg', 'fixed.jpg', b'\xff\xd8\xff'), ('image/webp', 'fixed.webp', b'RIFF')):
            with self.subTest(kind), self.assertRaisesRegex(server.StudioError, 'as a PNG'):
                self.studio.import_image(name, kind, body, parent=self.parent['id'])
        for note in ('x'*281, 'bell\x07'):
            with self.subTest(note=note[:6]), self.assertRaisesRegex(server.StudioError, 'editor note'):
                self.studio.import_image('fixed.png', 'image/png', repaired(), parent=self.parent['id'], note=note)
        self.assertEqual(self.tree(), before)

    def test_private_repair_of_a_private_picture_links_under_private_scope(self):
        child = self.studio.import_image('fixed.png', 'image/png', repaired(), privacy='private', parent=self.private['id'], scope='private')['asset']
        self.assertEqual((child['privacy'], child['lineage']), ('private', [self.private['id']]))

    def test_without_a_parent_the_import_is_what_it_was(self):
        result = self.studio.import_image('plain.png', 'image/png', repaired(), note='not a repair')
        job = self.studio.jobs[result['job']['id']]
        self.assertEqual((result['asset']['lineage'], job['parent_assets']), ([], []))
        self.assertEqual(job['message'], 'Imported original image. No generation submitted.')
        self.assertNotIn('editor_note', result['asset']['source'])

    def test_http_route_reads_parent_and_percent_encoded_note_headers(self):
        body = repaired()
        for headers, status, check in (
                ({'X-Parent-Asset': self.parent['id'], 'X-Editor-Note': 'Fixed%20the%20eyes%20%E2%9C%93'}, 201,
                 lambda o: self.assertEqual((o['asset']['lineage'], o['asset']['source']['editor_note']), ([self.parent['id']], 'Fixed the eyes ✓'))),
                ({'X-Parent-Asset': self.private['id']}, 400, lambda o: self.assertIn('not in this Library', o['error']))):
            with self.subTest(status):
                handler = server.Handler.__new__(server.Handler)
                handler.studio = self.studio; handler.path = '/api/assets/import'
                handler.headers = {'X-Filename': 'fixed.png', 'Content-Type': 'image/png', **headers}
                handler.rfile = io.BytesIO(body)
                handler._safe_mutation = lambda: True; handler._content_length = lambda limit: len(body)
                handler._drain_refused_body = lambda: None
                seen = {}; handler._json = lambda code, obj: seen.update(status=code, obj=obj)
                handler.do_POST()
                self.assertEqual(seen.get('status'), status, seen); check(seen['obj'])


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class RepairActionFrontendTests(unittest.TestCase):
    def test_payload_privacy_scope_and_refusal_messages(self):
        result = subprocess.run(['node', '--test', 'tests/test_asset_repair.cjs'], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

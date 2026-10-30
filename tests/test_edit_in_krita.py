"""#1860: Edit in Krita copies a picture to a Studio-owned working file, launches the configured Krita on it (never really, here), and
brings a changed save back as an unreviewed repair linked to its parent. Popen is always mocked."""
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from test_server import server, png, PRESET, GRAPH
import krita_edit


def repaired():
    stream = io.BytesIO(); Image.new('RGB', (8, 12), 'orange').save(stream, 'PNG'); return stream.getvalue()


def jpeg():
    stream = io.BytesIO(); Image.new('RGB', (8, 12), 'blue').save(stream, 'JPEG'); return stream.getvalue()


class EditInKritaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'presets').mkdir(); (self.root/'workflows/api').mkdir(parents=True)
        (self.root/'config').mkdir(); (self.root/'fake-comfy/input').mkdir(parents=True)
        self.krita = self.root/'tools/krita.exe'; self.krita.parent.mkdir(); self.krita.write_bytes(b'not a real krita')
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root': str(self.root/'fake-comfy'), 'krita': str(self.krita)}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': [PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        start = patch.object(threading.Thread, 'start', lambda *_: None); start.start()
        try: self.studio = server.Studio(self.root)
        finally: start.stop()
        popen = patch.object(subprocess, 'Popen'); self.popen = popen.start(); self.addCleanup(popen.stop)
        self.parent = self.studio.import_image('broken.png', 'image/png', png())['asset']
        self.private = self.studio.import_image('hidden.png', 'image/png', png(), privacy='private')['asset']

    def tree(self):
        files = {str(p.relative_to(self.root)): p.stat().st_size for p in self.root.rglob('*')
                 if p.is_file() and 'assets.sqlite3' not in p.name}
        return files, len(self.studio.jobs), len(self.studio.assets.snapshot(privacy='all')['assets'])

    def start(self, asset=None, privacy='regular', scope=None, studio=None):
        return krita_edit.start(studio or self.studio, (asset or self.parent)['id'], privacy=privacy, scope=scope or privacy)

    def back(self, session=None, asset=None, privacy='regular', scope=None, studio=None):
        return krita_edit.bring_back(studio or self.studio, (asset or self.parent)['id'], session, privacy=privacy, scope=scope or privacy)

    def test_start_launches_the_configured_krita_on_a_studio_copy_and_records_the_session(self):
        store = self.studio.assets.file(self.parent['id']); before = (store.read_bytes(), store.stat().st_mtime_ns)
        session = self.start()
        self.popen.assert_called_once()
        argv = self.popen.call_args.args[0]; kwargs = self.popen.call_args.kwargs
        self.assertEqual(argv, [str(self.krita.resolve()), session['working_path']])
        self.assertNotIn('shell', kwargs)
        working = Path(session['working_path'])
        self.assertEqual(working.parent, (self.root/'experiments/edits'/self.parent['id']).resolve())
        self.assertEqual(working.read_bytes(), before[0]); self.assertEqual((store.read_bytes(), store.stat().st_mtime_ns), before)
        record = json.loads(working.with_suffix('.json').read_text(encoding='utf-8'))
        self.assertEqual({k: record[k] for k in ('asset_id', 'source_sha256', 'working_path', 'privacy')},
                         {'asset_id': self.parent['id'], 'source_sha256': self.parent['sha256'], 'working_path': session['working_path'], 'privacy': 'regular'})
        self.assertIsInstance(record['created_at'], float)
        self.assertEqual(self.studio.assets.get(self.parent['id']), self.parent)

    def test_refusals_say_why_and_write_nothing(self):
        clip = self.root/'clip.bin'; clip.write_bytes(b'not a picture')
        video = self.studio.assets.register({'id': 'clip-job', 'created_at': 1, 'preset_name': 'Clip', 'outputs': [{'filename': 'clip.bin', 'media_type': 'video'}]}, 0, clip)
        binned = self.studio.import_image('binned.png', 'image/png', png())['asset']
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET trashed_at=1 WHERE id=?', (binned['id'],))
        photo = self.studio.import_image('photo.jpg', 'image/jpeg', jpeg())['asset']
        before = self.tree()
        cases = {'not an image': ({'id': video}, 'regular', 'regular', 'Only a picture'), 'in the Bin': (binned, 'regular', 'regular', 'Bin'),
                 'not a PNG': (photo, 'regular', 'regular', 'PNG'), 'private picture, regular scope': (self.private, 'private', 'regular', 'not in this Library'),
                 'regular picture, private scope': (self.parent, 'regular', 'private', 'not in this Library'),
                 'private picture, regular creation': (self.private, 'regular', 'private', 'never linked'),
                 'missing': ({'id': '0'*32}, 'regular', 'regular', 'not in this Library')}
        for name, (asset, privacy, scope, message) in cases.items():
            with self.subTest(name), self.assertRaisesRegex(krita_edit.KritaEditError, message):
                self.start(asset, privacy, scope)
        for name, config in {'not configured': None, 'blank': '  ', 'missing file': str(self.root/'nowhere/krita.exe'), 'not an exe': str(self.root/'config/local.json')}.items():
            with self.subTest(name), patch.dict(self.studio.config):
                self.studio.config.pop('krita', None)
                if config is not None: self.studio.config['krita'] = config
                with self.assertRaisesRegex(krita_edit.KritaEditError, 'Krita'):
                    self.start()
                self.assertFalse(krita_edit.availability(self.studio)['available'])
        self.popen.assert_not_called(); self.assertEqual(self.tree(), before)
        self.assertFalse((self.root/'experiments/edits').exists() or (self.root/'experiments/private/edits').exists())

    def test_a_krita_that_cannot_start_leaves_no_session_behind(self):
        before = self.tree(); self.popen.side_effect = OSError('blocked')
        with self.assertRaisesRegex(krita_edit.KritaEditError, 'could not be started'): self.start()
        self.assertEqual(self.tree(), before)

    def test_unchanged_file_imports_nothing(self):
        session = self.start(); before = self.tree()
        self.assertEqual(self.back(session['id'])['status'], 'unchanged')
        self.assertEqual(self.back()['status'], 'unchanged')  # the latest session when none is named
        self.assertEqual(self.tree(), before)

    def test_changed_file_imports_one_linked_unreviewed_repair_that_survives_a_restart(self):
        session = self.start(); Path(session['working_path']).write_bytes(repaired())
        result = self.back(session['id'])
        self.assertEqual(result['status'], 'imported'); child = result['asset']
        self.assertEqual((child['lineage'], child['review'], child['favorite'], child['notes'], child['source']['editor_note']),
                         ([self.parent['id']], 'unreviewed', False, '', 'Edited in Krita'))
        self.assertEqual(child['sha256'], hashlib.sha256(repaired()).hexdigest())
        self.assertEqual(self.studio.assets.get(self.parent['id']), self.parent)
        restarted = server.Studio(self.root)
        self.assertEqual(restarted.assets.get(child['id'])['lineage'], [self.parent['id']])
        job = next(j for j in restarted.jobs.values() if j.get('outputs', [{}])[0].get('asset_id') == child['id'])
        self.assertEqual((job['operation'], job['parent_assets']), ('asset.import', [self.parent['id']]))
        count = len(restarted.assets.snapshot(privacy='all')['assets'])
        again = self.back(session['id'], studio=restarted)  # the session itself survived the restart
        self.assertEqual((again['status'], again['asset_id']), ('already_imported', child['id']))
        self.assertEqual(len(restarted.assets.snapshot(privacy='all')['assets']), count)

    def test_a_second_press_without_a_new_save_does_not_duplicate_but_a_new_save_does_import(self):
        session = self.start(); working = Path(session['working_path']); working.write_bytes(repaired())
        first = self.back(); before = self.tree()
        self.assertEqual((self.back()['status'], self.back(session['id'])['status']), ('already_imported', 'already_imported'))
        self.assertEqual(self.tree(), before)
        stream = io.BytesIO(); Image.new('RGB', (8, 12), 'green').save(stream, 'PNG'); working.write_bytes(stream.getvalue())
        second = self.back()
        self.assertEqual(second['status'], 'imported'); self.assertNotEqual(second['asset']['id'], first['asset']['id'])
        self.assertEqual(second['asset']['lineage'], [self.parent['id']])

    def test_a_bad_save_is_refused_and_not_remembered(self):
        session = self.start(); working = Path(session['working_path']); working.write_bytes(b'\x89PNG\r\n\x1a\ntruncated')
        before = self.tree()
        with self.assertRaises(server.StudioError): self.back()
        self.assertEqual(self.tree(), before)
        working.write_bytes(repaired()); self.assertEqual(self.back()['status'], 'imported')

    def test_session_ids_and_the_working_file_are_studio_owned(self):
        session = self.start(); before = self.tree()
        for bad in ('../x', '..\\x', 'C:/Windows/win.ini', session['id'] + '.png', 7, [], '20260101-000000-zzzzzzzz'):
            with self.subTest(bad=bad), self.assertRaisesRegex(krita_edit.KritaEditError, 'Unknown edit session'): self.back(bad)
        with self.assertRaisesRegex(krita_edit.KritaEditError, 'unavailable'): self.back('20260101-000000-abcdef12')
        with self.assertRaisesRegex(krita_edit.KritaEditError, 'Open this picture in Krita first'): self.back(asset=self.private, privacy='private')
        self.assertEqual(self.tree(), before)
        Path(session['working_path']).unlink()
        with self.assertRaisesRegex(krita_edit.KritaEditError, 'gone'): self.back()

    def test_a_private_picture_keeps_its_working_file_and_its_repair_private(self):
        session = self.start(self.private, 'private')
        working = Path(session['working_path'])
        self.assertEqual(working.parent, (self.root/'experiments/private/edits'/self.private['id']).resolve())
        self.assertFalse((self.root/'experiments/edits').exists())
        self.assertEqual(session['privacy'], 'private')
        working.write_bytes(repaired())
        child = self.back(asset=self.private, privacy='private')['asset']
        self.assertEqual((child['privacy'], child['lineage']), ('private', [self.private['id']]))
        self.assertEqual([a for a in self.studio.assets.snapshot(privacy='regular')['assets'] if a['id'] == child['id']], [])
        with self.assertRaisesRegex(krita_edit.KritaEditError, 'not in this Library'): self.back(asset=self.private, privacy='private', scope='regular')


class EditInKritaHTTPTests(unittest.TestCase):
    """The composed handler, including the private-creation gate."""
    def setUp(self):
        EditInKritaTests.setUp(self)
        self.http = server.create_server(self.root, host='127.0.0.1', port=0, studio_factory=lambda _: self.studio)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.stop)

    tree = EditInKritaTests.tree

    def stop(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(5)

    def call(self, method, path, body=None, privacy=None):
        headers = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191', 'Content-Type': 'application/json'}
        if privacy: headers['X-Studio-Privacy'] = headers['X-Studio-Creation-Privacy'] = privacy
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=10)
        try:
            connection.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse(); return response.status, json.loads(response.read())
        finally: connection.close()

    def test_routes_start_and_bring_back_for_regular_and_private_pictures(self):
        self.assertEqual(self.call('GET', '/api/edit-in-krita'), (200, {'available': True, 'reason': ''}))
        for asset, privacy, where in ((self.parent, None, 'experiments/edits'), (self.private, 'private', 'experiments/private/edits')):
            with self.subTest(privacy or 'regular'):
                path = '/api/assets/%s/edit-in-krita' % asset['id']
                status, session = self.call('POST', path, {}, privacy)  # private creation passes the gate through the /api/assets/ prefix
                self.assertEqual(status, 201, session)
                self.assertEqual(Path(session['working_path']).parent, (self.root/where/asset['id']).resolve())
                self.assertEqual(self.popen.call_args.args[0], [str(self.krita.resolve()), session['working_path']])
                self.assertEqual(self.call('POST', path + '/bring-back', {'session': session['id']}, privacy), (200, {'status': 'unchanged', 'session': session}))
                Path(session['working_path']).write_bytes(repaired())
                status, back = self.call('POST', path + '/bring-back', {}, privacy)
                self.assertEqual((status, back['status'], back['asset']['lineage'], back['asset']['review']), (200, 'imported', [asset['id']], 'unreviewed'), back)
                self.assertEqual(self.call('POST', path + '/bring-back', {}, privacy)[1]['status'], 'already_imported')

    def test_refusals_over_http_write_nothing(self):
        before = self.tree()
        private_path = '/api/assets/%s/edit-in-krita' % self.private['id']
        for path, body, privacy, message in (
                (private_path, {}, None, 'not in this Library'), (private_path + '/bring-back', {}, None, 'not in this Library'),
                ('/api/assets/%s/edit-in-krita' % self.parent['id'], {'privacy': 'private'}, None, 'never linked'),
                ('/api/assets/%s/edit-in-krita/bring-back' % self.parent['id'], {'session': '../../x'}, None, 'Unknown edit session'),
                ('/api/assets/%s/edit-in-krita/bring-back' % self.parent['id'], {}, None, 'Open this picture in Krita first')):
            with self.subTest(path=path[-30:], body=body):
                status, result = self.call('POST', path, body, privacy)
                self.assertEqual(status, 400); self.assertIn(message, result['error'])
        with patch.dict(self.studio.config):
            self.studio.config.pop('krita')
            self.assertEqual(self.call('GET', '/api/edit-in-krita')[1]['available'], False)
            status, result = self.call('POST', '/api/assets/%s/edit-in-krita' % self.parent['id'], {})
            self.assertEqual(status, 400); self.assertIn('not configured', result['error'])
        self.popen.assert_not_called(); self.assertEqual(self.tree(), before)


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class EditInKritaFrontendTests(unittest.TestCase):
    def test_actions_privacy_and_stale_dialog_guards(self):
        result = subprocess.run(['node', '--test', 'tests/test_asset_krita.cjs'], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

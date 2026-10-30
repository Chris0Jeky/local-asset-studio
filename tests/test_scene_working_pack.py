"""Saved scene packs carry exact bytes and intent without changing review state."""
import copy
import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import test_server as fixture

server = fixture.server


class SceneWorkingPackTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown
    studio = fixture.ServerTests.studio

    def pack_fixture(self):
        self.s = self.studio(); self.store = self.s.assets
        self.workspace = self.store.snapshot()['workspace_id']
        image = self.s.import_image('Marsh backdrop.png', 'image/png', fixture.png())['asset']
        with self.store.connection() as db:
            db.execute("UPDATE assets SET review='needs_work',favorite=1,notes='Keep the owner review',tags=? WHERE id=?", ('["marsh"]',image['id']))
        image = self.store.get(image['id'])
        self.expected = {image['id']: fixture.png()}
        self.selected = {'background': image, 'sprite': image, 'icon': None}
        for role, kind, name, raw in (
                ('video', 'video', 'River current.mp4', b'synthetic video source'),
                ('audio', 'audio', 'Quiet frogs.wav', b'synthetic audio source'),
                ('mesh', '3d', 'Lantern stand.glb', b'synthetic mesh source')):
            path = self.root / name; path.write_bytes(raw)
            identifier = self.store.register({'id': 'pack-' + role, 'created_at': 1,
                'outputs': [{'filename': name, 'media_type': kind}]}, 0, path)
            self.selected[role] = self.store.get(identifier); self.expected[identifier] = raw
        body = {'format': 'studio.scene-brief/v1', 'workspace_id': self.workspace, 'collection_id': None,
                'direction': 'A quiet marsh crossing', 'slots': {}}
        for role in ('background', 'sprite', 'icon', 'video', 'audio', 'mesh'):
            asset = self.selected[role]
            body['slots'][role] = {'intent': 'Role: ' + role, 'criteria': 'Keep the lantern readable',
                'selected': {'asset_id': asset['id'], 'sha256': asset['sha256'],
                             'metadata_revision': asset['metadata_revision']} if asset else None, 'previous': None}
        self.brief = self.store.card_command({'action': 'create', 'id': 'pack-brief', 'kind': 'brief',
                                               'name': 'Lantern Marsh', 'body': body})
        return {'id': self.brief['id'], 'expected_revision': 0, 'workspace_id': self.workspace}

    def post(self, path, payload, scope='regular', creation='regular'):
        handler = server.Handler.__new__(server.Handler); handler.studio = self.s; handler.path = path
        handler.headers = {'X-Studio-Privacy': scope, 'X-Studio-Creation-Privacy': creation}
        handler._safe_mutation = lambda: True; handler._body_json = lambda *args: payload
        sent = []; handler._json = lambda status, body: sent.append((status, body))
        handler.do_POST(); return sent[0]

    def test_saved_pack_preserves_roles_exact_bytes_empty_slot_and_review_state(self):
        payload = self.pack_fixture()
        status, control = self.post('/api/assets/export', {'ids': [self.selected['background']['id']]})
        self.assertEqual(status, 201, control)
        with server.zipfile.ZipFile(self.store.root / 'exports' / (control['id'] + '.zip')) as archive:
            self.assertEqual(len(json.loads(archive.read('manifest.json'))['assets']), 1)
        before = {identifier: self.store.get(identifier) for identifier in self.expected}
        jobs = copy.deepcopy(self.s.jobs)
        status, result = self.post('/api/briefs/export', payload)
        self.assertEqual(status, 201, result)
        self.assertEqual(result['count'], 4)
        self.assertIn(self.workspace, result['url'])
        with server.zipfile.ZipFile(self.store.root / 'exports' / (result['id'] + '.zip')) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            brief = manifest['brief']
            self.assertEqual((brief['id'], brief['name'], brief['revision']), ('pack-brief', 'Lantern Marsh', 0))
            self.assertEqual(brief['direction'], 'A quiet marsh crossing')
            self.assertEqual(brief['workspace_id'], self.workspace)
            self.assertIsNone(brief['collection_id'])
            self.assertEqual(set(brief['slots']), {'background', 'sprite', 'icon', 'video', 'audio', 'mesh'})
            self.assertIsNone(brief['slots']['icon']['selected'])
            for role, slot in brief['slots'].items():
                self.assertEqual(slot['intent'], 'Role: ' + role)
                self.assertEqual(slot['criteria'], 'Keep the lantern readable')
                self.assertEqual(slot['selected'], self.brief['body']['slots'][role]['selected'])
            self.assertEqual(len(manifest['assets']), 4)
            self.assertEqual(len([name for name in archive.namelist() if name.startswith('assets/')]), 4)
            for asset in manifest['assets']:
                self.assertEqual(asset['review'], before[asset['id']]['review'])
                self.assertEqual(asset['notes'], before[asset['id']]['notes'])
                self.assertEqual(archive.read(asset['file']), self.expected[asset['id']])
                self.assertEqual(hashlib.sha256(archive.read(asset['file'])).hexdigest(), asset['sha256'])
                if asset['id'] == self.selected['background']['id']:
                    recipe = archive.read(asset['recipe']['file'])
                    self.assertEqual(hashlib.sha256(recipe).hexdigest(), asset['recipe']['sha256'])
                    self.assertEqual(json.loads(recipe), self.s.export_recipe(jobs[asset['job_id']]))
                else: self.assertIsNone(asset['recipe'])
        self.assertEqual({identifier: self.store.get(identifier) for identifier in self.expected}, before)
        self.assertEqual(self.store.card('pack-brief'), self.brief)
        self.assertEqual(self.s.jobs, jobs)
        self.assertEqual(list((self.store.root / 'exports').glob('*.part')), [])

    def test_source_replaced_after_zip_copy_refuses_publication_and_keeps_the_new_bytes(self):
        payload = self.pack_fixture(); identifier = self.selected['background']['id']
        source = self.store.file(identifier); write = server.zipfile.ZipFile.write
        def replace_after_copy(archive, filename, *args, **kwargs):
            result = write(archive, filename, *args, **kwargs)
            if Path(filename) == source: source.write_bytes(b'changed by another writer')
            return result
        with patch.object(server.zipfile.ZipFile, 'write', replace_after_copy):
            status, result = self.post('/api/briefs/export', payload)
        self.assertNotEqual(status, 201, result)
        self.assertEqual(source.read_bytes(), b'changed by another writer')
        self.assertEqual(list((self.store.root / 'exports').iterdir()), [])
        self.assertEqual(self.store.card('pack-brief'), self.brief)

    def test_linked_media_directory_outside_workspace_cannot_supply_a_working_pack(self):
        payload = self.pack_fixture(); media = self.store.media; moved = self.root / 'moved-media'
        media.rename(moved)
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(moved), str(media))
        else: media.symlink_to(moved, target_is_directory=True)
        status, result = self.post('/api/briefs/export', payload)
        self.assertNotEqual(status, 201, result)
        self.assertEqual(list((self.store.root / 'exports').glob('*')), [])
        self.assertTrue(next(moved.iterdir()).is_file())

    def test_recipe_changed_during_write_refuses_the_pack_without_reverting_it(self):
        payload = self.pack_fixture(); job = self.s.jobs[self.selected['background']['job_id']]
        write = server.zipfile.ZipFile.writestr
        def change_recipe(archive, name, *args, **kwargs):
            result = write(archive, name, *args, **kwargs)
            if isinstance(name, str) and name.startswith('recipes/'):
                job['controls']['newer'] = 'retained edit'
            return result
        with patch.object(server.zipfile.ZipFile, 'writestr', change_recipe):
            status, result = self.post('/api/briefs/export', payload)
        self.assertNotEqual(status, 201, result)
        self.assertEqual(job['controls']['newer'], 'retained edit')
        self.assertEqual(list((self.store.root / 'exports').iterdir()), [])

    def test_request_must_name_a_current_saved_regular_brief_in_this_workspace(self):
        payload = self.pack_fixture()
        other = self.store.card_command({'action':'create','kind':'character','name':'Keep','body':{}})
        for change in ({'expected_revision':1}, {'expected_revision':True}, {'workspace_id':'a'*32},
                       {'id':'unsaved-brief'}, {'id':other['id']}, {'paths':['../outside']}, {'ids':[]}):
            with self.subTest(change=change):
                self.assertNotEqual(self.post('/api/briefs/export', {**payload, **change})[0], 201)
        for scope, creation in (('private','regular'), ('all','regular'), ('regular','private')):
            self.assertNotEqual(self.post('/api/briefs/export', payload, scope, creation)[0], 201)
        with self.store.connection() as db: db.execute('UPDATE cards SET trashed_at=1 WHERE id=?', (payload['id'],))
        self.assertNotEqual(self.post('/api/briefs/export', payload)[0], 201)
        self.assertEqual(list((self.store.root / 'exports').glob('*')), [])
        self.assertEqual(self.store.card(other['id']), other)

    def test_unavailable_source_never_silently_disappears_from_the_pack(self):
        payload = self.pack_fixture(); asset = self.selected['background']
        for field, value in (('privacy','private'), ('media_type','video'), ('metadata_revision',1),
                             ('trashed_at',1), ('archived_at',1), ('sha256','f'*64)):
            with self.subTest(field=field):
                with self.store.connection() as db: db.execute('UPDATE assets SET '+field+'=? WHERE id=?', (value,asset['id']))
                self.assertNotEqual(self.post('/api/briefs/export', payload)[0], 201)
                with self.store.connection() as db: db.execute('UPDATE assets SET '+field+'=? WHERE id=?', (asset[field],asset['id']))
        self.store.file(asset['id']).unlink()
        self.assertNotEqual(self.post('/api/briefs/export', payload)[0], 201)
        self.assertEqual(list((self.store.root / 'exports').glob('*')), [])
        self.assertEqual(self.store.card(payload['id']), self.brief)

    def test_wrong_collection_and_traversal_paths_refuse_without_copying_bytes(self):
        payload = self.pack_fixture(); asset = self.selected['background']; body = copy.deepcopy(self.brief['body'])
        collection = self.store.collection({'name':'Other collection'})['id']; body['collection_id'] = collection
        # Simulate a previously saved card whose membership has since been removed.
        with self.store.connection() as db: db.execute('UPDATE cards SET body=? WHERE id=?', (json.dumps(body),payload['id']))
        self.assertNotEqual(self.post('/api/briefs/export', payload)[0], 201)
        with self.store.connection() as db: db.execute('UPDATE cards SET body=? WHERE id=?', (json.dumps(self.brief['body']),payload['id']))
        outside = self.store.root / 'outside.png'; outside.write_bytes(self.expected[asset['id']])
        for path in ('media/../outside.png', str(outside)):
            with self.subTest(path=path):
                with self.store.connection() as db: db.execute('UPDATE assets SET path=? WHERE id=?', (path,asset['id']))
                self.assertNotEqual(self.post('/api/briefs/export', payload)[0], 201)
        self.assertEqual(outside.read_bytes(), self.expected[asset['id']])
        self.assertEqual(list((self.store.root / 'exports').glob('*')), [])

    def test_interrupted_zip_write_cleans_partial_output_and_keeps_sources(self):
        payload = self.pack_fixture(); write = server.zipfile.ZipFile.write
        def interrupted(archive, *args, **kwargs):
            write(archive, *args, **kwargs)
            raise OSError('Synthetic interrupted write')
        with patch.object(server.zipfile.ZipFile, 'write', interrupted):
            status, _ = self.post('/api/briefs/export', payload)
        self.assertEqual(status, 500)
        self.assertEqual(list((self.store.root / 'exports').iterdir()), [])
        for identifier, raw in self.expected.items(): self.assertEqual(self.store.file(identifier).read_bytes(), raw)
        self.assertEqual(self.store.card(payload['id']), self.brief)

    def test_brief_changed_during_zip_write_preserves_newer_save_and_refuses_publication(self):
        payload = self.pack_fixture(); write = server.zipfile.ZipFile.write
        def newer_save(archive, *args, **kwargs):
            result = write(archive, *args, **kwargs)
            if self.store.card(payload['id'])['revision'] == 0:
                self.store.card_command({'action':'edit','id':payload['id'],'expected_revision':0,'name':'Newer save'})
            return result
        with patch.object(server.zipfile.ZipFile, 'write', newer_save):
            status, result = self.post('/api/briefs/export', payload)
        self.assertEqual(status, 409, result)
        self.assertEqual(list((self.store.root / 'exports').iterdir()), [])
        self.assertEqual(self.store.card(payload['id'])['name'], 'Newer save')

    def test_distinct_assets_with_identical_bytes_share_one_member_and_empty_brief_is_explicit(self):
        payload = self.pack_fixture(); path = self.root / 'second.png'; path.write_bytes(fixture.png())
        identifier = self.store.register({'id':'second','outputs':[{'filename':'second.png','media_type':'image'}]},0,path)
        duplicate = self.store.get(identifier); body = copy.deepcopy(self.brief['body'])
        body['slots']['icon']['selected'] = {'asset_id':identifier,'sha256':duplicate['sha256'],'metadata_revision':0}
        self.store.card_command({'action':'edit','id':payload['id'],'expected_revision':0,'body':body})
        status, result = self.post('/api/briefs/export', {**payload,'expected_revision':1})
        self.assertEqual(status, 201, result)
        with server.zipfile.ZipFile(self.store.root / 'exports' / (result['id']+'.zip')) as archive:
            manifest = json.loads(archive.read('manifest.json')); assets = {a['id']:a for a in manifest['assets']}
            self.assertEqual(len(assets), 5)
            self.assertEqual(assets[identifier]['file'], assets[self.selected['background']['id']]['file'])
            self.assertEqual(len([name for name in archive.namelist() if name.startswith('assets/')]), 4)
        for slot in body['slots'].values(): slot['selected'] = None
        self.store.card_command({'action':'edit','id':payload['id'],'expected_revision':1,'body':body})
        status, result = self.post('/api/briefs/export', {**payload,'expected_revision':2})
        self.assertEqual(status, 201, result)
        with server.zipfile.ZipFile(self.store.root / 'exports' / (result['id']+'.zip')) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(archive.namelist(), ['manifest.json']); self.assertEqual(manifest['assets'], [])
            self.assertTrue(all(slot['selected'] is None for slot in manifest['brief']['slots'].values()))

    def test_long_source_name_keeps_its_extension_inside_the_member_limit(self):
        payload = self.pack_fixture(); long = 'a' * 100 + '.png'; path = self.root / long; path.write_bytes(b'long named source')
        identifier = self.store.register({'id':'long','outputs':[{'filename':long,'media_type':'image'}]},0,path)
        asset = self.store.get(identifier); body = copy.deepcopy(self.brief['body'])
        body['slots']['icon']['selected'] = {'asset_id':identifier,'sha256':asset['sha256'],'metadata_revision':0}
        self.store.card_command({'action':'edit','id':payload['id'],'expected_revision':0,'body':body})
        status, result = self.post('/api/briefs/export', {**payload,'expected_revision':1})
        self.assertEqual(status, 201, result)
        with server.zipfile.ZipFile(self.store.root / 'exports' / (result['id']+'.zip')) as archive:
            member = {a['id']:a for a in json.loads(archive.read('manifest.json'))['assets']}[identifier]['file']
            self.assertRegex(member, r'^assets/\d{2}-a{96}\.png$')
            self.assertEqual(archive.read(member), b'long named source')

if __name__ == '__main__': unittest.main()

"""Independent regressions for core private creation and storage boundaries."""
import copy
import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
import zipfile

import test_server as fixture
import asset_thumbs
import continuation


class CorePrivacyReviewTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown
    studio = fixture.ServerTests.studio

    def source_job(self, studio):
        identifier = studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'Regular source'}}, enqueue=False)['id']
        job = studio.jobs[identifier]
        job.update(status='completed', elapsed_seconds=137, prompt_ids=['retained-prompt'],
                   submissions=[{'prompt_id': 'retained-prompt', 'graph': copy.deepcopy(job['graph'])}],
                   outputs=[{'filename': 'source.png', 'media_type': 'image', 'prompt_id': 'retained-prompt'}])
        source = self.root / 'source.png'; source.write_bytes(fixture.png())
        asset_id = studio.assets.register(job, 0, source); job['outputs'][0]['asset_id'] = asset_id
        return job, asset_id

    def mismatch(self, studio):
        job, asset_id = self.source_job(studio)
        self.assertEqual(continuation.source_context(studio, asset_id)['positive'], 'Regular source')
        job['privacy'] = 'private'; job['controls']['positive'] = 'PRIVATE-JOIN-CANARY'
        for node, field in job['prompt_bindings']['positive']:
            job['submissions'][0]['graph'][str(node)]['inputs'][str(field)] = 'PRIVATE-JOIN-CANARY'
            job['graph'][str(node)]['inputs'][str(field)] = 'PRIVATE-JOIN-CANARY'
        return job, asset_id

    def handler(self, studio, path='/', headers=None, body=None):
        handler = fixture.server.Handler.__new__(fixture.server.Handler)
        handler.studio = studio; handler.path = path; handler.headers = headers or {}
        handler._safe_mutation = lambda: True; handler._safe_host = lambda: True
        handler._body_json = lambda *a: body
        handler.responses = []; handler.sent_headers = {}
        handler._json = lambda status, value: handler.responses.append((status, value))
        handler.send_response = lambda status: handler.responses.append((status, None))
        handler.send_header = lambda key, value: handler.sent_headers.__setitem__(key, value)
        handler.end_headers = lambda: None; handler.wfile = io.BytesIO()
        return handler

    def test_regular_workspace_excerpt_never_joins_private_job(self):
        studio = self.studio(); _, asset_id = self.mismatch(studio)
        with studio.assets.connection() as db:
            db.execute('UPDATE assets SET prompt_excerpt=NULL WHERE id=?', (asset_id,))
        self.assertNotIn('PRIVATE-JOIN-CANARY', json.dumps(studio.workspace_snapshot()))

    def test_regular_continuation_never_joins_private_job_submission(self):
        studio = self.studio(); _, asset_id = self.mismatch(studio)
        try: result = continuation.source_context(studio, asset_id)
        except ValueError: return
        self.assertNotIn('PRIVATE-JOIN-CANARY', json.dumps(result))

    def test_regular_export_never_embeds_private_job_recipe(self):
        studio = self.studio(); _, asset_id = self.mismatch(studio)
        try: result = studio.export_assets({'ids': [asset_id]})
        except ValueError: return
        with zipfile.ZipFile(studio.assets.root / 'exports' / (result['id'] + '.zip')) as archive:
            self.assertNotIn(b'PRIVATE-JOIN-CANARY', b'\n'.join(archive.read(name) for name in archive.namelist()))

    def test_regular_estimate_does_not_include_private_sample_counts(self):
        studio = self.studio(); job, _ = self.source_job(studio)
        request = {'preset_id': 'demo', 'controls': {}}
        self.assertEqual(studio.estimate(request)['sample_count'], 1)
        job['privacy'] = 'private'
        result = studio.estimate(request)
        self.assertEqual(result['sample_count'], 0)
        self.assertEqual(result['matched_samples'], 0)
        self.assertEqual(result['confidence'], 'none')

    def test_restart_never_copies_a_private_workflow_through_a_regular_record_symlink(self):
        studio = self.studio()
        regular = studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'Regular source'}}, enqueue=False)
        private = studio.create_job({'preset_id': 'demo', 'privacy': 'private',
                                     'controls': {'positive': 'PRIVATE-WORKFLOW-CANARY'}}, enqueue=False)
        regular_graph = studio.runs / regular['id'] / 'workflow.json'
        private_graph = studio.experiments / 'private/runs' / private['id'] / 'workflow.json'
        regular_graph.unlink(); regular_graph.symlink_to(private_graph)
        reloaded = self.studio(); record = reloaded.jobs[regular['id']]
        self.assertIn('record_error', record)
        self.assertNotIn('PRIVATE-WORKFLOW-CANARY', json.dumps(reloaded.public(record)))
        with self.assertRaises(ValueError): reloaded.export_recipe(record)
        self.assertTrue(regular_graph.is_symlink(), 'Refusal must retain the link as evidence, not materialize its private target')

    def test_private_thumbnail_directory_cannot_alias_regular_cache(self):
        studio = self.studio(); asset = studio.import_image('private', 'image/png', fixture.png(), privacy='private')['asset']
        regular = studio.assets.root / 'thumbs'; regular.mkdir(exist_ok=True)
        private = studio.assets.storage_root('private') / 'thumbs'
        private.symlink_to(regular, target_is_directory=True)
        with self.assertRaises(ValueError): asset_thumbs.thumbnail(studio.assets, asset['id'], privacy='private')
        self.assertEqual(list(regular.iterdir()), [])

    def test_cached_private_thumbnail_cannot_be_a_symbolic_link(self):
        studio = self.studio(); asset = studio.import_image('private', 'image/png', fixture.png(), privacy='private')['asset']
        folder = studio.assets.storage_root('private') / 'thumbs'; folder.mkdir()
        target = folder / f"{asset['sha256']}-{asset_thumbs.DEFAULT_SIZE}-v{asset_thumbs.THUMB_VERSION}.webp"
        source = self.root / 'outside.webp'; source.write_bytes(b'outside cache content')
        target.symlink_to(source)
        with self.assertRaises(ValueError): asset_thumbs.thumbnail(studio.assets, asset['id'], privacy='private')

    def test_private_export_directory_cannot_alias_regular_exports(self):
        studio = self.studio(); asset = studio.import_image('private', 'image/png', fixture.png(), privacy='private')['asset']
        regular = studio.assets.root / 'exports'; regular.mkdir(exist_ok=True)
        private = studio.assets.storage_root('private') / 'exports'; private.symlink_to(regular, target_is_directory=True)
        with self.assertRaises(ValueError): studio.export_assets({'ids': [asset['id']]}, privacy='private')
        self.assertEqual(list(regular.iterdir()), [])

    def test_reference_attachment_honors_json_private_classification(self):
        studio = self.studio(); asset = studio.import_image('regular', 'image/png', fixture.png())['asset']
        handler = self.handler(studio, '/api/assets/reference', body={'id': asset['id'], 'privacy': 'private'})
        handler.do_POST(); status, result = handler.responses[-1]
        self.assertEqual(status, 200); self.assertEqual(result.get('privacy'), 'private')
        self.assertTrue((studio.experiments / 'private/uploads' / result['file']).is_file())
        self.assertFalse((studio.experiments / 'uploads' / result['file']).exists())

    def test_reference_body_header_conflict_refuses_before_upload(self):
        studio = self.studio(); asset = studio.import_image('regular', 'image/png', fixture.png())['asset']
        before = set(studio.experiments.rglob('*'))
        handler = self.handler(studio, '/api/assets/reference', headers={'X-Studio-Creation-Privacy': 'regular'},
                               body={'id': asset['id'], 'privacy': 'private'})
        handler.do_POST(); self.assertEqual(handler.responses[-1][0], 400)
        self.assertEqual(set(studio.experiments.rglob('*')), before)

    def test_reference_check_honors_json_private_classification(self):
        studio = self.studio(); upload = studio.upload('private', 'image/png', fixture.png(), privacy='private')
        handler = self.handler(studio, '/api/references/check', body={'files': [upload['file']], 'privacy': 'private'})
        handler.do_POST(); status, result = handler.responses[-1]
        self.assertEqual(status, 200); self.assertTrue(result[0]['available'])

    def test_private_local_unsatisfiable_range_is_not_cached(self):
        studio = self.studio(); source = self.root / 'range.png'; source.write_bytes(fixture.png())
        handler = self.handler(studio, headers={'Range': 'bytes=9999-'})
        handler._local_file(source, private=True)
        self.assertEqual(handler.responses[-1][0], 416)
        self.assertEqual(handler.sent_headers.get('Cache-Control'), 'no-store')

    def test_private_remote_unsatisfiable_range_is_not_cached(self):
        studio = self.studio(); handler = self.handler(studio, headers={'Range': 'bytes=9999-'})
        error = HTTPError('http://127.0.0.1/view', 416, 'range', {'Content-Range': 'bytes */10'}, io.BytesIO())
        with patch.object(fixture.server, 'urlopen', side_effect=error):
            handler._media({'filename': 'private.png', 'type': 'output'}, {'privacy': 'private'})
        self.assertEqual(handler.responses[-1][0], 416)
        self.assertEqual(handler.sent_headers.get('Cache-Control'), 'no-store')


if __name__ == '__main__': unittest.main()

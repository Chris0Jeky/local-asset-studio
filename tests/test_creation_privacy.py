"""Private creation admission, retained evidence and explicit disclosure boundaries."""
import copy
import json
import shutil
import unittest
from unittest.mock import patch
from email.message import Message
from types import SimpleNamespace

import test_server as fixture
server, png = fixture.server, fixture.png


class CreationPrivacyTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown
    studio = fixture.ServerTests.studio

    def test_private_job_is_persisted_in_private_run_before_admission(self):
        studio = self.studio()
        result = studio.create_job({'preset_id':'demo','controls':{'positive':'private canary'},'privacy':'private'})
        self.assertEqual(result.get('privacy'),'private')
        folder = studio.experiments/'private'/'runs'/result['id']
        self.assertTrue((folder/'state.json').is_file())
        self.assertFalse((studio.runs/result['id']).exists())
        self.assertEqual(json.loads((folder/'state.json').read_text())['privacy'],'private')
        self.assertEqual(studio.queue.get_nowait(),('generate',result['id']))
        self.assertEqual(studio._job_directory(result['id']),folder)

    def test_unknown_creation_privacy_is_refused_before_job_or_queue(self):
        studio = self.studio()
        for value in ('all','PRIVATE','',None,False,{},['private']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                studio.create_job({'preset_id':'demo','privacy':value})
        self.assertEqual(studio.jobs,{})
        self.assertTrue(studio.queue.empty())
        self.assertEqual(list(studio.runs.iterdir()),[])

    def test_private_upload_stays_separate_and_regular_generation_cannot_use_it(self):
        studio = self.studio()
        uploaded = studio.upload('private-source','image/png',png(),privacy='private')
        self.assertEqual(uploaded['privacy'],'private')
        self.assertTrue((studio.experiments/'private'/'uploads'/uploaded['file']).is_file())
        self.assertFalse((studio.experiments/'uploads'/uploaded['file']).exists())
        payload={'preset_id':'demo','controls':{'reference':uploaded['file']}}
        with self.assertRaises(ValueError):studio.create_job(payload,enqueue=False)
        result=studio.create_job(dict(payload,privacy='private'),enqueue=False)
        self.assertEqual(result['privacy'],'private')

    def test_private_draft_can_keep_a_regular_uploaded_reference(self):
        studio = self.studio()
        uploaded=studio.upload('regular-source','image/png',png())
        result=studio.create_job({'preset_id':'demo','privacy':'private','controls':{'reference':uploaded['file']}},enqueue=False)
        self.assertEqual(result.get('privacy'),'private')
        self.assertTrue((studio.experiments/'uploads'/uploaded['file']).is_file())

    def test_private_restart_keeps_recipe_and_does_not_enqueue(self):
        studio=self.studio();result=studio.create_job({'preset_id':'demo','privacy':'private','controls':{'positive':'retained private'}},enqueue=False)
        reloaded=self.studio();job=reloaded.jobs[result['id']]
        self.assertEqual(job.get('privacy'),'private')
        self.assertEqual(job['controls']['positive'],'retained private')
        self.assertEqual(job['status'],'not_submitted')
        self.assertTrue(reloaded.queue.empty())
        self.assertFalse((studio.runs/result['id']).exists())

    def test_corrupt_private_record_never_falls_back_to_regular(self):
        studio=self.studio();result=studio.create_job({'preset_id':'demo','privacy':'private'},enqueue=False)
        folder=studio.experiments/'private'/'runs'/result['id']
        (folder/'state.json').write_text('{broken',encoding='utf-8')
        reloaded=self.studio();job=reloaded.jobs[result['id']]
        self.assertEqual(job.get('privacy'),'private')
        self.assertIn('record_error',job)
        self.assertTrue(reloaded.queue.empty())

    def test_duplicate_run_identity_is_quarantined_as_private(self):
        studio=self.studio();result=studio.create_job({'preset_id':'demo'},enqueue=False)
        destination=studio.experiments/'private'/'runs'/result['id']
        shutil.copytree(studio.runs/result['id'],destination)
        state=json.loads((destination/'state.json').read_text());state['privacy']='private'
        (destination/'state.json').write_text(json.dumps(state))
        reloaded=self.studio();job=reloaded.jobs[result['id']]
        self.assertEqual(job.get('privacy'),'private')
        self.assertIn('record_error',job)
        self.assertTrue(reloaded.queue.empty())

    def test_private_or_invalid_record_in_regular_folder_stays_hidden(self):
        for label in ('private','unexpected',None):
            with self.subTest(label=label):
                studio=self.studio();result=studio.create_job({'preset_id':'demo'},enqueue=False)
                path=studio.runs/result['id']/'state.json'
                data=json.loads(path.read_text());data['privacy']=label
                path.write_text(json.dumps(data))
                reloaded=self.studio();job=reloaded.jobs[result['id']]
                self.assertEqual(job.get('privacy'),'private')
                self.assertIn('record_error',job)
                self.assertTrue(reloaded.queue.empty())

    def test_private_saveimage_graph_uses_dedicated_engine_output_prefix(self):
        path=self.root/'workflows/api/demo-api.json';graph=json.loads(path.read_text())
        graph['3']={'class_type':'SaveImage','inputs':{'filename_prefix':'regular-example','images':['1',0]}}
        path.write_text(json.dumps(graph))
        studio=self.studio();result=studio.create_job({'preset_id':'demo','privacy':'private'},enqueue=False)
        job=studio.jobs[result['id']]
        self.assertEqual(job['graph']['3']['inputs']['filename_prefix'],'local-asset-studio/private')
        self.assertEqual(json.loads(path.read_text())['3']['inputs']['filename_prefix'],'regular-example')

    def test_private_derivative_directories_cannot_redirect_to_regular_storage(self):
        import asset_thumbs
        studio=self.studio();asset=studio.import_image('private.png','image/png',png(),privacy='private')['asset']
        for kind in ('thumbs','exports'):
            with self.subTest(kind=kind):
                target=studio.assets.root/kind;target.mkdir(exist_ok=True)
                linked=studio.experiments/'private'/kind
                try:linked.symlink_to(target,target_is_directory=True)
                except OSError:self.skipTest('Directory symlinks unavailable')
                try:
                    with self.assertRaises(ValueError):
                        if kind=='thumbs':asset_thumbs.thumbnail(studio.assets,asset['id'],privacy='private')
                        else:studio.export_assets({'ids':[asset['id']]},privacy='private')
                    self.assertEqual(list(target.iterdir()),[])
                finally:linked.unlink()

    def test_regular_asset_cannot_read_a_mismatched_private_job(self):
        import continuation
        studio=self.studio();result=studio.import_image('regular.png','image/png',png());asset=result['asset']
        job=studio.jobs[result['job']['id']];job['privacy']='private';job['controls']['positive']='PRIVATE JOIN CANARY'
        # Old rows can lack excerpts. A duplicate or manually moved run must not backfill them from private evidence.
        with patch.object(studio.assets,'snapshot',return_value={'assets':[dict(asset,prompt_excerpt=None)]}):
            self.assertNotIn('PRIVATE JOIN CANARY',json.dumps(studio.workspace_snapshot()))
        with self.assertRaises(ValueError):continuation.source_context(studio,asset['id'])
        with self.assertRaises(ValueError):studio.export_assets({'ids':[asset['id']]})


class PrivacyScopeTests(unittest.TestCase):
    def handler(self,path='/',**headers):
        values=Message()
        for key,value in headers.items():values[key.replace('_','-')]=value
        return SimpleNamespace(path=path,headers=values)

    def test_scopes_are_explicit_and_creation_never_accepts_all(self):
        import creation_privacy as privacy
        self.assertEqual(privacy.scope_for_handler(self.handler()),'regular')
        self.assertEqual(privacy.scope_for_handler(self.handler('/api/jobs?privacy=all')),'all')
        self.assertEqual(privacy.creation_for_handler(self.handler(),{'privacy':'private'}),'private')
        with self.assertRaises(ValueError):privacy.creation_for_handler(self.handler(),{'privacy':'all'})
        self.assertFalse(privacy.matches('private','regular'))
        self.assertFalse(privacy.matches('unknown','all'))

    def test_conflicting_or_repeated_scopes_are_rejected(self):
        import creation_privacy as privacy
        for handler in [self.handler('/api/jobs?privacy=private&privacy=private'),
                        self.handler('/api/jobs?privacy=private',X_Studio_Privacy='regular')]:
            with self.subTest(path=handler.path),self.assertRaises(ValueError):privacy.scope_for_handler(handler)
        handler=self.handler(X_Studio_Privacy='private');handler.headers['X-Studio-Privacy']='all'
        with self.assertRaises(ValueError):privacy.scope_for_handler(handler)
        with self.assertRaises(ValueError):privacy.creation_for_handler(self.handler(X_Studio_Creation_Privacy='private'),{'privacy':'regular'})


if __name__=='__main__':unittest.main()

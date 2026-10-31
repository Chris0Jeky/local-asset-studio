"""Later scene sources use the same real Workspace and revision store."""
import copy
import json
from pathlib import Path
import unittest
import wave
from unittest.mock import patch

import test_workspace_continue_scenes as fixtures
from test_server import rgba_png
from studio_av import project as av
from studio_av import render as media


class SceneSourceRevisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ContinueSceneTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.fixture.fixture.fixture.patches[0].stop()
        self.studio=self.fixture.studio;self.scenes=self.studio.production.av;self.workspace=self.fixture.workspace
        self.scene=self.fixture.scene()
        self.asset=self.studio.import_image('later.png','image/png',rgba_png(9,7))['asset']

    def command(self, action='add_source', **changes):
        payload={'action':action,'expected_revision':self.scene['revision'],'workspace_id':self.workspace,
                 'asset_id':self.asset['id'],'sha256':self.asset['sha256'],'metadata_revision':self.asset['metadata_revision'],
                 'section':'shots',**changes}
        return self.scenes.command(self.scene['id'],payload)

    def test_later_source_and_clip_are_one_revision_without_recreating_scene(self):
        self.scene=self.scenes.command(self.scene['id'],{'action':'edit','expected_revision':0,
            'section':'shots','clip_id':'shot0','changes':{'frames':48}})
        before=copy.deepcopy(self.scene);directory=self.scenes.directory(self.scene['id']);plan=(directory/'plan.json').read_bytes()
        changed=self.command()
        self.assertEqual(changed['id'],before['id']);self.assertEqual(changed['revision'],2)
        self.assertEqual(changed['project']['shots'][0],before['project']['shots'][0])
        self.assertEqual(len(changed['project']['shots']),2)
        source=changed['sources'][-1]
        self.assertEqual(source['asset_id'],self.asset['id']);self.assertEqual(source['sha256'],self.asset['sha256'])
        self.assertEqual(changed['project']['shots'][-1]['asset'],source['key'])
        self.assertEqual(self.scenes.source(changed['id'],source['key']).read_bytes(),rgba_png(9,7))
        self.assertEqual([e['revision'] for e in changed['history']],[2,1,0])
        self.assertEqual((directory/'plan.json').read_bytes(),plan)
        self.assertTrue(self.studio.queue.empty());self.assertFalse(self.studio.requests)

    def test_replace_preserves_arrangement_and_restore_retains_both_immutable_inputs(self):
        self.scene=self.scenes.command(self.scene['id'],{'action':'edit','expected_revision':0,
            'section':'shots','clip_id':'shot0','changes':{'frames':48}})
        before=copy.deepcopy(self.scene);changed=self.command('replace_source',clip_id='shot0')
        original=before['project']['shots'][0];replacement=changed['project']['shots'][0]
        self.assertEqual({k:v for k,v in replacement.items() if k!='asset'},{k:v for k,v in original.items() if k!='asset'})
        self.assertNotEqual(replacement['asset'],original['asset'])
        new_path=self.scenes.directory(changed['id'])/changed['project']['assets'][replacement['asset']]['path']
        restored=self.scenes.command(changed['id'],{'action':'restore','expected_revision':2,'source_revision':1})
        self.assertEqual(restored['revision'],3);self.assertEqual(restored['project'],before['project'])
        self.assertEqual(new_path.read_bytes(),rgba_png(9,7))
        self.assertEqual(self.scenes.continue_observation(self.workspace)['plan']['revision'],3)

    def test_continue_verifies_later_source_event_and_exact_current_revision(self):
        changed=self.command();self.assertEqual(self.scenes.continue_observation(self.workspace)['plan']['revision'],1)
        with self.studio.production.connect() as db:
            event=db.execute('SELECT event FROM av_events WHERE project_id=? AND revision=1',(changed['id'],)).fetchone()[0]
            forged=json.loads(event);forged['source']['asset_id']='invented'
            db.execute('UPDATE av_events SET event=? WHERE project_id=? AND revision=1',(json.dumps(forged),changed['id']))
        self.assertEqual(self.fixture.request()[1]['scene']['state'],'unavailable')

    def test_two_source_clients_have_one_cas_winner_and_no_orphan_copy(self):
        from concurrent.futures import ThreadPoolExecutor
        def update(_):
            try:return self.command()['revision']
            except ValueError as error:
                self.assertIn('Scene conflict',str(error));return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(update,range(2)))
        self.assertCountEqual(results,[1,'conflict'])
        self.assertEqual(len(list((self.scenes.directory(self.scene['id'])/'inputs').iterdir())),2)
        self.assertEqual(len(self.scenes.inspect(self.scene['id'])['history']),2)

    def test_stale_scope_identity_and_metadata_are_refused_without_copy(self):
        for changes in ({'workspace_id':'f'*32},{'sha256':'f'*64},{'metadata_revision':self.asset['metadata_revision']+1},
                        {'metadata_revision':True},{'expected_revision':1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.command(**changes)
        self.assertEqual(self.scenes.inspect(self.scene['id'])['revision'],0)
        self.assertEqual(len(list((self.scenes.directory(self.scene['id'])/'inputs').iterdir())),1)

    def test_private_trashed_and_linked_assets_are_refused(self):
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(self.asset['id'],))
        with self.assertRaises(ValueError):self.command()
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='regular',trashed_at=1 WHERE id=?",(self.asset['id'],))
        with self.assertRaises(ValueError):self.command()
        with self.studio.assets.connection() as db:db.execute('UPDATE assets SET trashed_at=NULL WHERE id=?',(self.asset['id'],))
        path=self.studio.assets.file(self.asset['id'])
        with patch('av_projects.project_storage._linked',side_effect=lambda p:p==path):
            with self.assertRaisesRegex(ValueError,'links'):self.command()
        self.assertEqual(self.scenes.inspect(self.scene['id'])['revision'],0)

    def test_partial_copy_and_changed_source_leave_document_history_and_inputs_unchanged(self):
        path=self.studio.assets.file(self.asset['id']);original_open=Path.open
        class BrokenReader:
            def __enter__(self):self.stream=original_open(path,'rb');self.reads=0;return self
            def __exit__(self,*_):self.stream.close()
            def read(self,count):
                self.reads+=1
                if self.reads>1:raise OSError('partial source read')
                return self.stream.read(4)
        def opened(p,*args,**kwargs):return BrokenReader() if p==path and args==('rb',) else original_open(p,*args,**kwargs)
        with patch.object(Path,'open',opened):
            with self.assertRaisesRegex(OSError,'partial source read'):self.command()
        def change_during_validation(project,directory,tools):
            result=av.validate(project,directory);path.write_bytes(rgba_png(8,6));return result,{}
        with patch('av_projects.validate_media',side_effect=change_during_validation):
            with self.assertRaisesRegex(ValueError,'changed during intake'):self.command()
        self.assertEqual(self.scenes.inspect(self.scene['id'])['revision'],0)
        self.assertEqual(len(self.scenes.inspect(self.scene['id'])['history']),1)
        self.assertEqual(len(list((self.scenes.directory(self.scene['id'])/'inputs').iterdir())),1)

    def test_replacement_and_restore_cannot_evade_retained_byte_or_item_limits(self):
        changed=self.command('replace_source',clip_id='shot0')
        self.scene=self.scenes.command(changed['id'],{'action':'restore','expected_revision':1,'source_revision':0})
        inputs=self.scenes.directory(self.scene['id'])/'inputs';retained=sum(p.stat().st_size for p in inputs.iterdir())
        with patch.object(av,'MAX_TOTAL',retained):
            with self.assertRaisesRegex(ValueError,'retained history'):self.command()
        for index in range(62):(inputs/('retained-'+str(index)+'.png')).write_bytes(b'partial')
        with self.assertRaisesRegex(ValueError,'item budget'):self.command()
        self.assertEqual(self.scenes.inspect(self.scene['id'])['revision'],2)

    def test_short_audio_video_and_wrong_kind_do_not_shorten_the_existing_clip(self):
        root=self.scenes.directory(self.scene['id']);long_audio=root/'long.wav';short_audio=root/'short.wav'
        for path,samples in ((long_audio,48000),(short_audio,12000)):
            with wave.open(str(path),'wb') as stream:stream.setparams((1,2,48000,0,'NONE',''));stream.writeframes(b'\0\0'*samples)
        def registered(path,kind):
            key=self.studio.assets.register({'id':kind+'-'+path.stem,'outputs':[{'filename':path.name,'media_type':kind}]},0,path)
            return self.studio.assets.get(key)
        def probe(path,kind,tools):
            return {'streams':[{'codec_type':'audio'}] if kind=='audio' else [{'codec_type':'video','codec_name':'png' if kind=='image' else 'h264','width':9,'height':7,'duration':'.25'}]}
        with patch('av_projects.validate_media',media.validate_media),patch.object(media,'probe',side_effect=probe):
            self.asset=registered(long_audio,'audio');self.scene=self.command(section='audio')
            clip=self.scene['project']['audio'][0];self.asset=registered(short_audio,'audio')
            with self.assertRaisesRegex(ValueError,'Audio source too short'):
                self.command('replace_source',section='audio',clip_id=clip['id'])
            with self.assertRaisesRegex(ValueError,'incompatible'):
                self.command('replace_source',section='shots',clip_id='shot0')
            video=root/'short.mp4';video.write_bytes(b'Fictional video probe fixture; not a playable video')
            self.asset=registered(video,'video')
            with self.assertRaisesRegex(ValueError,'Video source too short'):
                self.command('replace_source',clip_id='shot0')
        saved=self.scenes.inspect(self.scene['id'])
        self.assertEqual(saved['revision'],1);self.assertEqual(saved['project'],self.scene['project'])
        self.assertEqual(len(list((root/'inputs').iterdir())),2)

    def test_frozen_render_and_continue_refuse_tampered_or_unreceipted_membership(self):
        queued=self.scenes.command(self.scene['id'],{'action':'render','expected_revision':0})
        changed=self.command('replace_source',clip_id='shot0')
        with self.studio.production.connect() as db:
            frozen=json.loads(db.execute('SELECT snapshot FROM av_renders WHERE id=?',(queued['render']['id'],)).fetchone()[0])
        self.assertEqual(frozen['sources'][0]['asset_id'],self.scene['sources'][0]['asset_id'])
        self.assertEqual(set(frozen['project']['assets']),{'source0'});self.assertTrue(changed['render']['stale'])
        source=changed['sources'][-1];path=self.scenes.directory(changed['id'])/changed['project']['assets'][source['key']]['path'];raw=path.read_bytes()
        path.write_bytes(b'changed')
        self.assertEqual(self.fixture.request()[1]['scene']['state'],'unavailable');path.write_bytes(raw)
        with self.studio.production.connect() as db:
            document=json.loads(db.execute('SELECT document FROM av_documents WHERE project_id=?',(changed['id'],)).fetchone()[0])
            document['sources'][-1]['intake_revision']=0
            db.execute('UPDATE av_documents SET document=? WHERE project_id=?',(json.dumps(document),changed['id']))
        self.assertEqual(self.fixture.request()[1]['scene']['state'],'unavailable')

    def test_http_source_command_cas_survives_an_unread_reply(self):
        from http.client import HTTPConnection
        from http_test_server import ThreadingHTTPServer
        from test_server import server
        from threading import Thread
        handler=type('SceneSourceHTTP',(server.Handler,),{'studio':self.studio})
        http=ThreadingHTTPServer(('127.0.0.1',0),handler);thread=Thread(target=http.serve_forever,daemon=True);thread.start()
        payload={'action':'replace_source','section':'shots','clip_id':'shot0','expected_revision':0,
            'workspace_id':self.workspace,'asset_id':self.asset['id'],'sha256':self.asset['sha256'],'metadata_revision':self.asset['metadata_revision']}
        def request():
            conn=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
            conn.request('POST','/api/av/'+self.scene['id'],json.dumps(payload),
                {'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
            return conn,conn.getresponse()
        try:
            conn,response=request();self.assertEqual(response.status,200);conn.close()
            conn,response=request()
            try:self.assertEqual(response.status,400);self.assertIn(b'Scene conflict',response.read())
            finally:conn.close()
            saved=self.scenes.inspect(self.scene['id']);self.assertEqual(saved['revision'],1);self.assertEqual(len(saved['history']),2)
            self.assertTrue(self.studio.queue.empty())
        finally:http.shutdown();http.server_close();thread.join(5);self.assertFalse(thread.is_alive())


if __name__=='__main__':unittest.main()

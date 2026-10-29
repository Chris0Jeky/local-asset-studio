"""A brief is a revisioned Workspace card; fixtures never run a model."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from test_server import server
import scene_briefs


class SceneBriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = server.AssetWorkspace(Path(self.temp.name))
        self.scope = self.store.snapshot()['workspace_id']
        self.body = {'format':'studio.scene-brief/v1','workspace_id':self.scope,'collection_id':None,
                     'direction':'A quiet marsh crossing','slots':{key:{'intent':'','criteria':'','selected':None,'previous':None}
                     for key in ('background','sprite','icon','video','audio','mesh')}}

    def create(self, body=None, identifier='brief-one'):
        return self.store.card_command({'action':'create','id':identifier,'kind':'brief','name':'Lantern Marsh','body':body or self.body})

    def asset(self, kind='image', privacy='regular'):
        path=Path(self.temp.name)/'source.bin';path.write_bytes(b'synthetic fixture bytes')
        identifier=self.store.register({'id':kind+privacy,'privacy':privacy,'created_at':1,
            'outputs':[{'filename':'fixture.bin','media_type':kind}]},0,path)
        asset=self.store.metadata(identifier, self.scope, privacy=privacy)
        with self.store.connection() as db: row=db.execute('SELECT sha256 FROM assets WHERE id=?',(identifier,)).fetchone()
        return {'asset_id':identifier,'sha256':row['sha256'],'metadata_revision':asset['metadata_revision']}

    def test_brief_uses_existing_revisioned_store_without_changing_other_cards(self):
        control=self.store.card_command({'action':'create','kind':'character','name':'Control','body':{'words':'unchanged'}})
        card=self.create()
        self.assertEqual(card['kind'],'brief');self.assertEqual(card['body'],self.body)
        self.assertEqual(self.store.card(control['id'])['body'],{'words':'unchanged'})
        self.assertEqual(self.create(),card)

    def test_wrong_workspace_and_unknown_schema_refuse_without_a_row(self):
        for change in ({'workspace_id':'a'*32},{'format':'studio.scene-brief/v2'},{'extra':True}):
            body={**self.body,**change}
            with self.assertRaises(server.WorkspaceError):self.create(body)
        self.assertEqual(self.store.cards('brief'),[])

    def test_sources_have_exact_kind_hash_revision_and_regular_ownership(self):
        valid=self.asset(); private=self.asset(privacy='private'); wrong=self.asset('audio')
        for ref in (private,wrong,{**valid,'sha256':'f'*64},{**valid,'metadata_revision':3}):
            body=copy.deepcopy(self.body);body['slots']['background']['selected']=ref
            with self.assertRaises(server.WorkspaceError):self.create(body)
        body=copy.deepcopy(self.body);body['slots']['background']['selected']=valid
        self.assertEqual(self.create(body)['body'],body)

    def test_conflicting_tabs_preserve_winning_record(self):
        card=self.create();body=copy.deepcopy(self.body);body['direction']='First tab'
        saved=self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':body})
        with self.assertRaises(server.WorkspaceError) as failure:
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':self.body})
        self.assertEqual(failure.exception.status,409);self.assertEqual(self.store.card(card['id']),saved)

    def test_unavailable_previous_candidate_does_not_destroy_editable_words(self):
        body=copy.deepcopy(self.body);body['slots']['background']['selected']=self.asset();card=self.create(body)
        with self.store.connection() as db:db.execute('DELETE FROM assets')
        body['direction']='Keep editing words despite the missing candidate'
        saved=self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':body})
        self.assertEqual(saved['body'],body)
        body['slots']['icon']['selected']=body['slots']['background']['selected']
        with self.assertRaises(server.WorkspaceError):
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':1,'body':body})

    def test_corrupt_saved_body_is_not_reinterpreted_or_replaced(self):
        card=self.create()
        with self.store.connection() as db:db.execute('UPDATE cards SET body=? WHERE id=?',(json.dumps({'format':'unknown'}),card['id']))
        with self.assertRaises(server.WorkspaceError):
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':self.body})
        self.assertEqual(self.store.card(card['id'])['body'],{'format':'unknown'})

    def studio(self):
        return SimpleNamespace(assets=self.store, root=Path(self.temp.name), catalog=lambda:{'presets':[
            {'id':'test-image','name':'Test image','modality':'image','positive':['1','text']} ]})

    def test_replace_can_retain_stale_previous_but_restore_requires_current_source(self):
        body=copy.deepcopy(self.body);ref=self.asset();body['slots']['background']['selected']=ref;card=self.create(body)
        with self.store.connection() as db:db.execute('UPDATE assets SET metadata_revision=1')
        body['slots']['background'].update(selected=None,previous=ref)
        self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':body})
        body['slots']['background']['selected']=ref
        with self.assertRaises(server.WorkspaceError):
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':1,'body':body})
        self.assertIsNone(self.store.card(card['id'])['body']['slots']['background']['selected'])

    def test_collection_scope_is_checked_without_discarding_previous_snapshot(self):
        ref=self.asset();collection=self.store.collection({'name':'Other collection'})['id']
        body=copy.deepcopy(self.body);body['slots']['background']['selected']=ref;card=self.create(body)
        body['collection_id']=collection
        with self.assertRaises(server.WorkspaceError):
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':body})
        body['slots']['background'].update(selected=None,previous=ref)
        self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,'body':body})
        body['slots']['background']['selected']=ref
        with self.assertRaises(server.WorkspaceError):
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':1,'body':body})

    def test_missing_bytes_are_reported_and_corrupt_brief_does_not_hide_other_briefs(self):
        ref=self.asset();body=copy.deepcopy(self.body);body['slots']['background']['selected']=ref;self.create(body)
        self.store.file(ref['asset_id']).unlink()
        result=scene_briefs.inspect(self.studio(),'brief-one')
        self.assertEqual(result['candidates']['background']['state'],'unavailable')
        self.assertEqual(result['card']['body']['slots']['background']['selected'],ref)
        self.create(identifier='brief-two')
        with self.store.connection() as db:db.execute("UPDATE cards SET body='not json' WHERE id='brief-one'")
        listed={c['id']:c for c in scene_briefs.listing(self.studio())['briefs']}
        self.assertFalse(listed['brief-one']['available']);self.assertTrue(listed['brief-two']['available'])
        with self.assertRaises(server.WorkspaceError):scene_briefs.inspect(self.studio(),'brief-one')

    def test_real_look_preparation_is_read_only_and_revision_bound(self):
        look=self.store.card_command({'action':'create','kind':'look','name':'Test look','body':{
            'preset_id':'test-image','template':'Paint {scene}.','negative':'','controls':{}}})
        self.create();before=self.store.card('brief-one')
        request={'id':'brief-one','slot':'background','expected_revision':0,'look_id':look['id'],'look_revision':0}
        result=scene_briefs.prepare(self.studio(),request)
        self.assertEqual(result['prepared']['controls']['positive'],'Paint A quiet marsh crossing.')
        self.assertFalse(result['generation_submitted']);self.assertEqual(result['context']['revision'],0)
        self.assertEqual(self.store.card('brief-one'),before)
        self.store.card_command({'action':'edit','id':'brief-one','name':'New name','expected_revision':0})
        with self.assertRaises(server.WorkspaceError) as failure:scene_briefs.prepare(self.studio(),request)
        self.assertEqual(failure.exception.status,409)

    def test_scene_handoff_uses_saved_sources_and_refuses_stale_or_unsupported_inputs(self):
        path=Path(self.temp.name)/'synthetic.png';path.write_bytes(b'test fixture, media validity belongs to Scenes')
        identifier=self.store.register({'id':'scene-source','created_at':1,'outputs':[{'filename':'synthetic.png','media_type':'image'}]},0,path)
        asset=self.store.get(identifier);body=copy.deepcopy(self.body)
        body['slots']['background']['selected']={'asset_id':identifier,'sha256':asset['sha256'],'metadata_revision':0}
        self.create(body);request={'id':'brief-one','slot':'video','expected_revision':0}
        result=scene_briefs.prepare(self.studio(),request)
        self.assertEqual(result['target'],'scene');self.assertIn(identifier,result['url']);self.assertFalse(result['generation_submitted'])
        for key in ('sprite','audio','mesh'):
            with self.assertRaises(server.WorkspaceError) as failure:scene_briefs.prepare(self.studio(),{**request,'slot':key})
            self.assertEqual(failure.exception.code,'brief_preparation_unsupported')
        with self.store.connection() as db:db.execute('UPDATE assets SET archived_at=1')
        with self.assertRaises(server.WorkspaceError):scene_briefs.prepare(self.studio(),request)

    def test_http_routes_refuse_other_scopes_and_do_not_mutate_other_card_kinds(self):
        self.create();studio=self.studio()
        def route(method,path,payload=None,scope='regular',creation='regular'):
            handler=server.Handler.__new__(server.Handler);handler.studio=studio;handler.path=path
            handler.headers={'X-Studio-Privacy':scope,'X-Studio-Creation-Privacy':creation}
            handler._safe_host=handler._safe_mutation=lambda:True;handler._body_json=lambda:payload
            sent=[];handler._json=lambda status,body:sent.append((status,body))
            getattr(handler,'do_'+method)();return sent[0]
        self.assertEqual(route('GET','/api/briefs')[0],200)
        for scope in ('private','all'):
            self.assertEqual(route('GET','/api/briefs/brief-one',scope=scope)[0],400)
            self.assertEqual(route('POST','/api/briefs',{'action':'edit','id':'brief-one','expected_revision':0,'name':'Wrong'},scope=scope)[0],400)
        self.assertEqual(route('POST','/api/briefs',{'action':'edit','id':'brief-one','expected_revision':0,'name':'Wrong'},creation='private')[0],400)
        other=self.store.card_command({'action':'create','kind':'character','name':'Keep','body':{}})
        self.assertEqual(route('POST','/api/briefs',{'action':'edit','id':other['id'],'expected_revision':0,'name':'Wrong'})[0],404)
        self.assertEqual(self.store.card('brief-one')['name'],'Lantern Marsh')


if __name__=='__main__': unittest.main()

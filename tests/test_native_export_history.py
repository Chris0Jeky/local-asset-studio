"""Library discovery reads real saved plans; no exporter or model is run."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

import test_production as fixture_module
from test_production import FakeStudio, png, server


class NativeExportHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ProductionTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        (self.root/'scripts').mkdir()
        for name in ('game_asset_media.py', 'godot_asset_adapter.py'):
            (self.root/'scripts'/name).write_bytes((Path(__file__).parents[1]/'scripts'/name).read_bytes())
        self.studio = FakeStudio(self.root, [])
        self.asset = self.studio.import_image('source.png', 'image/png', png())['asset']
        self.workspace = self.studio.assets.snapshot()['workspace_id']

    def prepare(self, kind='ora', ids=None):
        return self.studio.production.native({'kind':kind, 'ids':ids or [self.asset['id']], 'options':{'clip':'saved-'+kind}})

    def request(self, suffix='', scope='regular', workspace=None):
        handler = server.Handler.__new__(server.Handler); handler.studio = self.studio
        handler.path = '/api/assets/'+self.asset['id']+'/native-exports'+suffix
        handler.path += ('&' if '?' in suffix else '?')+'workspace_id='+(workspace or self.workspace)
        handler.headers = {'X-Studio-Privacy':scope}; handler._safe_host = lambda:True
        sent=[]; handler._json=lambda status, body:sent.append((status,body))
        handler._local_file=lambda path,*args,**kwargs:sent.append((200,Path(path).read_bytes()))
        handler.do_GET(); return sent[0]

    def test_two_saved_plans_are_discoverable_without_becoming_produced_exports(self):
        plans=[self.prepare('ora'), self.prepare('atlas')]
        before=[self.studio.production._get(p['id']) for p in plans]
        status,result=self.request()
        self.assertEqual(status,200,result)
        self.assertEqual({p['id'] for p in result['plans']},{p['id'] for p in plans})
        self.assertTrue(all(p['status']=='planned' and p['artifacts']==[] for p in result['plans']))
        self.assertTrue(all(p['source_sha256']==self.asset['sha256'] for p in result['plans']))
        self.assertEqual([self.studio.production._get(p['id']) for p in plans],before)
        self.assertEqual(self.studio.requests,[]); self.assertTrue(self.studio.queue.empty())

    def retained(self, project, status='completed', body=b'synthetic retained bytes', name='export.zip'):
        path=self.studio.production.root/project['id']/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        record={'path':name,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'url':'https://invalid.example/never-follow'}
        self.studio.production._mutate(project['id'],status=status,artifacts=[record])
        return path,record

    def download(self, entry):
        url=urlsplit(entry['url']);prefix='/api/assets/'+self.asset['id']+'/native-exports'
        suffix=url.path[len(prefix):]+'?'+url.query.split('&',1)[1]
        return self.request(suffix)

    def test_completed_failed_and_interrupted_records_survive_reopen_without_retry(self):
        from production import Production
        plans=[self.prepare() for _ in range(3)]
        for p,status in zip(plans,['completed','failed','interrupted']):self.retained(p,status)
        self.studio.production=Production(self.studio)
        status,result=self.request();self.assertEqual(status,200)
        self.assertCountEqual([p['status'] for p in result['plans']],['completed','failed','interrupted'])
        for entry in result['plans']:
            self.assertTrue(entry['artifacts'][0]['available'])
            self.assertEqual(self.download(entry['artifacts'][0]),(200,b'synthetic retained bytes'))
        self.assertNotIn('invalid.example',json.dumps(result));self.assertEqual(self.studio.requests,[])
        self.assertTrue(self.studio.queue.empty())

    def test_unrelated_and_now_private_shared_sources_do_not_disclose_plans(self):
        other=self.studio.import_image('other.png','image/png',png())['asset'];self.assertNotEqual(other['id'],self.asset['id'])
        own=self.prepare();self.prepare(ids=[other['id']]);mixed=self.prepare(ids=[self.asset['id'],other['id']])
        self.retained(mixed)
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(other['id'],))
        status,result=self.request();self.assertEqual(status,200)
        self.assertEqual([p['id'] for p in result['plans']],[own['id']])
        self.assertNotIn(mixed['id'],json.dumps(result))
        self.assertEqual(self.request('/'+mixed['id']+'/files/0?sha256='+'a'*64)[0],400)

    def test_scope_and_workspace_are_checked_before_history_or_file_access(self):
        p=self.prepare();self.retained(p)
        self.assertEqual(self.request(scope='private')[0],400)
        self.assertEqual(self.request(workspace='f'*32)[0],409)
        self.assertEqual(self.request(scope='all')[0],200)
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(self.asset['id'],))
        self.assertEqual(self.request(scope='all')[0],400)

    def test_changed_source_keeps_the_recorded_hash_without_rewriting_the_plan(self):
        p=self.prepare();before=self.studio.production._get(p['id'])['plan'];path,record=self.retained(p)
        with self.studio.assets.connection() as db:db.execute('UPDATE assets SET sha256=? WHERE id=?',('b'*64,self.asset['id']))
        status,result=self.request();entry=result['plans'][0]
        self.assertEqual(status,200);self.assertTrue(entry['historical_source'])
        self.assertEqual(entry['source_sha256'],self.asset['sha256'])
        self.assertEqual(self.download(entry['artifacts'][0]),(200,path.read_bytes()))
        self.assertEqual(self.studio.production._get(p['id'])['plan'],before)

    def test_missing_or_changed_plan_evidence_is_not_a_produced_export(self):
        p=self.prepare();self.retained(p);plan=self.studio.production.root/p['id']/'plan.json'
        saved=plan.read_bytes();plan.unlink()
        status,result=self.request();self.assertEqual(status,200);entry=result['plans'][0]
        self.assertFalse(entry['available']);self.assertEqual(entry['artifacts'],[])
        plan.write_bytes(saved+b' ');self.assertTrue(self.request()[1]['plans'][0]['available'])
        changed=json.loads(saved);changed['name']='different';plan.write_text(json.dumps(changed))
        self.assertFalse(self.request()[1]['plans'][0]['available'])

    def test_missing_changed_and_replaced_files_preserve_receipts_and_refuse_download(self):
        p=self.prepare();path,record=self.retained(p)
        item=self.request()[1]['plans'][0]['artifacts'][0]
        path.write_bytes(b'x'*record['bytes'])
        self.assertEqual(self.download(item)[0],400)
        self.assertEqual(self.studio.production._get(p['id'])['state']['artifacts'],[record])
        self.retained(p,body=b'replaced receipt')
        self.assertEqual(self.download(item)[0],400)
        path.unlink();self.assertFalse(self.request()[1]['plans'][0]['artifacts'][0]['available'])

    def test_escape_and_linked_project_paths_never_offer_a_file(self):
        p=self.prepare();outside=self.root/'outside.txt';outside.write_bytes(b'private-path-canary')
        bad={'path':str(outside),'sha256':hashlib.sha256(outside.read_bytes()).hexdigest(),'bytes':outside.stat().st_size}
        self.studio.production._mutate(p['id'],status='completed',artifacts=[bad])
        status,result=self.request();self.assertEqual(status,200)
        self.assertNotIn(str(outside),json.dumps(result));self.assertFalse(result['plans'][0]['artifacts'][0]['available'])
        directory=self.studio.production.root/p['id'];moved=self.root/'moved';directory.rename(moved)
        try:directory.symlink_to(moved,target_is_directory=True)
        except OSError:
            moved.rename(directory);return  # Escape checks above still ran where symlink creation is unavailable.
        try:self.assertFalse(self.request()[1]['plans'][0]['available'])
        finally:directory.unlink();moved.rename(directory)

    def test_pages_are_bounded_and_reading_each_page_has_no_duplicates(self):
        ids={self.prepare()['id'] for _ in range(21)}
        status,first=self.request();self.assertEqual(status,200);self.assertEqual(len(first['plans']),20)
        status,last=self.request('?offset='+first['next_offset']);self.assertEqual(status,200);self.assertIsNone(last['next_offset'])
        seen=[p['id'] for p in first['plans']+last['plans']];self.assertEqual(len(seen),len(set(seen)));self.assertEqual(set(seen),ids)
        for query in ('?offset=-1','?offset=bad','?offset=0&offset=20'):
            self.assertEqual(self.request(query)[0],400)

    def test_malformed_receipt_or_state_is_unavailable_without_a_server_crash(self):
        p=self.prepare();self.retained(p);item=self.request()[1]['plans'][0]['artifacts'][0]
        self.studio.production._mutate(p['id'],artifacts=[None])
        self.assertFalse(self.request()[1]['plans'][0]['artifacts'][0]['available'])
        self.assertEqual(self.download(item)[0],400)
        with self.studio.production.connect() as db:db.execute('UPDATE projects SET state=? WHERE id=?',('[]',p['id']))
        status,result=self.request();self.assertEqual(status,200);self.assertTrue(result['unavailable']);self.assertEqual(result['plans'],[])

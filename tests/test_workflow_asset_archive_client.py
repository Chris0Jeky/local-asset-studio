"""Reviewed Archive uses the actual composed HTTP/SQLite owner, not a new writer."""
import copy
import importlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch
import uuid

import test_asset_archive_http as fixture
from studio_workflow.core import canonical, digest
from studio_workflow.client import ClientError


class ArchiveClientTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_workflow.asset_archive_client'),
                             'Reviewed Archive client is missing')
        self.module=importlib.import_module('studio_workflow.asset_archive_client')
        self.fixture=fixture.ArchiveHTTPTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.store=self.fixture.store;self.ids=self.fixture.ids;self.scope=self.fixture.scope
        base=self.fixture.http.RequestHandlerClass
        class EphemeralOrigin(base):
            def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
            def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://127.0.0.1:'+str(self.server.server_port)
        self.fixture.http.RequestHandlerClass=EphemeralOrigin
        self.client=self.module.AssetArchiveClient('http://127.0.0.1:'+str(self.fixture.http.server_port),timeout=3)

    def preview(self, **kwargs):
        return self.client.preview(kwargs.pop('ids',self.ids),workspace_id=self.scope,
            request_id=kwargs.pop('request_id',uuid.uuid4().hex),**kwargs)

    def apply(self, plan):
        return self.client.apply(canonical(plan).decode(),approved_plan_sha256=plan['plan_sha256'])

    def recover(self, plan):return self.client.recover(canonical(plan).decode())

    def test_preview_is_one_scoped_observation_with_no_writes(self):
        before=self.store.snapshot(privacy='all')
        with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
            plan=self.preview()
        self.assertEqual(calls.call_count,1)
        self.assertEqual(calls.call_args.args[0].full_url,self.client.base+'/api/assets/selection')
        self.assertEqual(plan['format'],'studio.asset-archive-plan/v1')
        self.assertEqual(plan['plan_sha256'],digest({k:v for k,v in plan.items() if k!='plan_sha256'}))
        self.assertEqual([item['id'] for item in plan['selection']['items']],self.ids)
        self.assertEqual(self.store.snapshot(privacy='all'),before)
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],0)

    def test_exact_apply_recovery_and_explicit_replay_preserve_newer_state(self):
        plan=self.preview();before=(Path(self.fixture.temp.name)/'image.png').read_bytes()
        result=self.apply(plan);self.assertEqual(result['receipt']['updated'],self.ids)
        self.assertTrue(result['current_complete']);self.assertFalse(result['generation_submitted'])
        self.assertFalse(result['media_bytes_modified'])
        newer=self.preview(action='unarchive');self.apply(newer)
        snapshot=self.store.snapshot(privacy='all')
        receipt=self.recover(plan);self.assertEqual(receipt['receipt'],result['receipt'])
        self.assertTrue(all(row['archived_at'] is None for row in receipt['current']))
        self.assertEqual(self.apply(plan),receipt)
        self.assertEqual(self.store.snapshot(privacy='all'),snapshot)
        self.assertEqual((Path(self.fixture.temp.name)/'image.png').read_bytes(),before)

    def test_stale_selection_refuses_whole_batch(self):
        plan=self.preview();self.store.update(self.fixture.command(ids=self.ids[:1]))
        before=self.store.snapshot(privacy='all')
        with self.assertRaises(ClientError) as caught:self.apply(plan)
        self.assertEqual(caught.exception.code,'asset_revision_conflict')
        self.assertEqual(self.store.snapshot(privacy='all'),before)

    def test_unknown_receipt_does_not_authorize_retry_or_post(self):
        plan=self.preview()
        with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:result=self.recover(plan)
        self.assertEqual(calls.call_count,1);self.assertEqual(calls.call_args.args[0].get_method(),'GET')
        self.assertEqual(result['receipt']['status'],'unknown');self.assertFalse(result['current_complete'])
        self.assertEqual(result['current'],[])

    def test_missing_and_hidden_targets_do_not_make_a_partial_plan(self):
        private=self.store.register({'id':'private-example','privacy':'private','outputs':[{'filename':'image.png'}]},0,Path(self.fixture.temp.name)/'image.png')
        before=self.store.snapshot(privacy='all')
        for ids in ([self.ids[0],'missing'],[self.ids[0],private]):
            with self.subTest(ids=ids),self.assertRaisesRegex(ValueError,'missing or hidden'):self.preview(ids=ids)
        plan=self.preview(ids=[private],privacy='private');self.apply(plan)
        self.assertEqual(self.store.get(private,privacy='private')['privacy'],'private')
        hidden=self.client._observe('/api/assets/commands/'+plan['request_id']+'?workspace_id='+self.scope)
        self.assertEqual(hidden['status'],'unknown')
        self.assertEqual(self.store.snapshot()['assets'],[a for a in before['assets'] if a.get('privacy','regular')=='regular'])

    def test_mixed_scope_uses_explicit_all_and_never_reclassifies(self):
        private=self.store.register({'id':'private-example','privacy':'private','outputs':[{'filename':'image.png'}]},0,Path(self.fixture.temp.name)/'image.png')
        plan=self.preview(ids=[self.ids[0],private],privacy='all');result=self.apply(plan)
        self.assertEqual([self.store.get(i,privacy='all').get('privacy','regular') for i in [self.ids[0],private]],['regular','private'])
        self.assertEqual(self.recover(plan),result)

    def test_invalid_preview_refuses_locally(self):
        for arguments in ({'ids':[]},{'ids':['same','same']},{'action':'trash'},{'request_id':'short'},
                          {'privacy':None},{'ids':['x']*201}):
            with self.subTest(arguments=arguments),patch.object(self.client.opener,'open') as calls:
                with self.assertRaises(ValueError):self.preview(**arguments)
                calls.assert_not_called()

    def test_modified_or_unapproved_plan_cannot_dispatch(self):
        plan=self.preview()
        for mutate in (lambda p:p.update(action='unarchive'),lambda p:p.update(privacy='all'),
                       lambda p:p.update(extra='ignored?'),lambda p:p['selection']['items'][0]['asset'].update(metadata_revision=True)):
            modified=copy.deepcopy(plan);mutate(modified)
            with self.subTest(mutate=mutate),patch.object(self.client.opener,'open') as calls:
                with self.assertRaises(ValueError):self.apply(modified)
                calls.assert_not_called()
        with patch.object(self.client.opener,'open') as calls:
            with self.assertRaises(ValueError):self.client.apply(canonical(plan).decode(),approved_plan_sha256='0'*64)
            with self.assertRaises(ValueError):self.client.recover('{"format":1,"format":2}')
            calls.assert_not_called()

    def test_zero_timestamp_and_trashed_assets_remain_orthogonal(self):
        with self.store.connection() as db:db.execute('UPDATE assets SET archived_at=0,trashed_at=0')
        plan=self.preview();result=self.apply(plan)
        self.assertEqual(result['receipt']['unchanged'],self.ids)
        self.assertTrue(all(row['archived_at']==0 and row['trashed_at']==0 for row in result['current']))
        self.apply(self.preview(action='unarchive'))
        self.assertTrue(all(a['trashed_at']==0 for a in self.store.snapshot()['assets']))

    def test_lost_ack_keeps_original_plan_and_recovers_without_reapplying(self):
        plan=self.preview();base=self.fixture.http.RequestHandlerClass
        class LoseOnce(base):
            lose=True
            def _json(handler,status,value):
                if handler.path.startswith('/api/assets/update') and status==200 and LoseOnce.lose:
                    LoseOnce.lose=False;handler.close_connection=True;handler.connection.shutdown(socket.SHUT_RDWR);return
                return super()._json(status,value)
        self.fixture.http.RequestHandlerClass=LoseOnce
        with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
            with self.assertRaises(self.module.ArchiveOutcomeUnknown) as caught:self.apply(plan)
        self.assertEqual(calls.call_count,1)
        self.assertEqual(caught.exception.request_id,plan['request_id'])
        self.assertEqual(caught.exception.plan_sha256,plan['plan_sha256'])
        after=self.store.snapshot(privacy='all');result=self.recover(plan)
        self.assertEqual(result['receipt']['status'],'applied');self.assertEqual(self.store.snapshot(privacy='all'),after)

    def test_mismatched_success_is_unknown_and_never_retried(self):
        plan=self.preview()
        with patch.object(self.client,'_observe',return_value={'status':'applied','request_id':'wrong'}) as observe:
            with self.assertRaises(self.module.ArchiveOutcomeUnknown):self.apply(plan)
        self.assertEqual(observe.call_count,1)
        with patch.object(self.client,'_observe',return_value={'status':'unknown','request_id':'wrong'}):
            with self.assertRaises(ValueError):self.recover(plan)

    def test_write_uses_original_route_with_explicit_privacy_header(self):
        private=self.store.register({'id':'private-header','privacy':'private','outputs':[{'filename':'image.png'}]},0,Path(self.fixture.temp.name)/'image.png')
        for privacy,ids in [('regular',self.ids[:1]),('private',[private]),('all',self.ids[1:])]:
            plan=self.preview(ids=ids,privacy=privacy)
            with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:self.apply(plan)
            request=calls.call_args.args[0]
            self.assertEqual(calls.call_count,1);self.assertEqual(request.full_url,self.client.base+'/api/assets/update')
            self.assertEqual(request.get_header('X-studio-privacy'),privacy)
            self.assertEqual(request.get_method(),'POST')
            self.assertNotIn('privacy',json.loads(request.data))
        with patch.object(self.client.opener,'open') as calls:
            with self.assertRaises(ValueError):self.client._observe('/api/assets/update',{},privacy='bogus')
            calls.assert_not_called()

    def test_current_observation_is_bounded_and_does_not_claim_full_selection(self):
        ids=[]
        for n in range(12):
            ids.append(self.store.register({'id':'many-'+str(n),'outputs':[{'filename':'image.png'}]},0,Path(self.fixture.temp.name)/'image.png'))
        result=self.apply(self.preview(ids=ids))
        self.assertEqual(result['receipt']['updated'],ids)
        self.assertEqual([row['id'] for row in result['current']],ids[:10])
        self.assertFalse(result['current_complete'])

    def test_malformed_receipt_fields_and_false_noop_cannot_claim_success(self):
        plan=self.preview();result=self.client._observe('/api/assets/update',self.module.validate_plan(canonical(plan).decode())[1])
        def wrong_noop(r):
            r.update(unchanged=self.ids,applied={},revisions={i:0 for i in self.ids})
        for mutate in (lambda r:r.update(action='trash'),lambda r:r.update(workspace_id='0'*32),
                       lambda r:r['revisions'].update({self.ids[0]:True}),lambda r:r.update(applied={'archived_at':-1}),
                       lambda r:r.update(current=list(reversed(r['current']))),wrong_noop):
            bad=copy.deepcopy(result);mutate(bad)
            with self.subTest(mutation=mutate),patch.object(self.client,'_observe',return_value=bad) as calls:
                with self.assertRaises(self.module.ArchiveOutcomeUnknown):self.apply(plan)
                self.assertEqual(calls.call_count,1)
        with patch.object(self.client,'_observe',side_effect=ClientError(503,{'error':'unconfirmed','code':'asset_storage_unconfirmed'})):
            with self.assertRaises(self.module.ArchiveOutcomeUnknown):self.apply(plan)

    def test_cli_retains_plan_and_nonmutating_recovery(self):
        file=Path(self.fixture.temp.name)/'review.json'
        with patch('sys.stdout',new_callable=io.StringIO) as stdout:
            code=self.module.main(['--url',self.client.base,'preview','--workspace-id',self.scope,
                                  '--request-id',uuid.uuid4().hex,'--ids',*self.ids])
        self.assertEqual(code,0);text=stdout.getvalue();file.write_text(text,encoding='utf-8');plan=json.loads(text)
        for operation,more in [('apply',['--approved-plan-sha256',plan['plan_sha256']]),('recover',[])]:
            with patch('sys.stdout',new_callable=io.StringIO) as stdout:
                self.assertEqual(self.module.main(['--url',self.client.base,operation,'--plan',str(file),*more]),0)
            self.assertEqual(json.loads(stdout.getvalue())['receipt']['status'],'applied')
            self.assertEqual(file.read_text(encoding='utf-8'),text)
        with patch('sys.stderr',new_callable=io.StringIO) as stderr:
            self.assertEqual(self.module.main(['--url',self.client.base,'apply','--plan',str(file),'--approved-plan-sha256','0'*64]),2)
        self.assertEqual(json.loads(stderr.getvalue())['code'],'archive_failed')


if __name__=='__main__':unittest.main()

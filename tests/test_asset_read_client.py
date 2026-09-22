"""Untrusted bounded transport replies must stay scoped observations."""
import copy
import importlib
import io
import json
import unittest
from email.message import Message
from urllib.error import HTTPError
from unittest.mock import patch

from studio_workflow import asset_reads


class Reply(io.BytesIO):
    def __init__(self, raw, *, length=None):
        super().__init__(raw);self.headers=Message()
        self.headers['Content-Length']=str(len(raw) if length is None else length)
        self.status=200


class AssetReadClientTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_workflow.asset_read_client'),
                             'Typed asset read client is missing')
        self.module=importlib.import_module('studio_workflow.asset_read_client')
        self.client=self.module.AssetReadClient()
        self.scope='a'*32;self.stamp={'epoch':'b'*32,'revision':5}
        self.asset={'id':'asset-one','sha256':'c'*64,'media_type':'image','review':'unreviewed',
                    'preset_id':None,'title':'One','filename':'one.png','preset_name':None,'bytes':1,
                    'metadata_revision':0,'favorite':False,'created_at':1,'trashed_at':None,
                    'url':'/api/assets/asset-one/file','truncated_fields':[]}
        self.page={'format':'studio.asset-page/v1','workspace_id':self.scope,'catalogue':self.stamp,
                   'observation_only':True,'media_bytes_verified':False,'generation_submitted':False,
                   'filters':dict(asset_reads.DEFAULT_FILTERS),'order':asset_reads.ORDER,'limit':50,
                   'assets':[self.asset],'next_cursor':None}

    def reply(self, value, **kwargs):
        raw=value if isinstance(value,bytes) else json.dumps(value).encode('utf-8')
        response=Reply(raw,**kwargs)
        self.client.opener=type('Transport',(),{'open':lambda _,request,timeout:response})()
        return response

    def test_valid_reply_closes_transport_and_retains_summary_identity(self):
        response=self.reply(self.page)
        self.assertEqual(self.client.page(workspace_id=self.scope),self.page)
        self.assertTrue(response.closed)

    def test_untrusted_response_cannot_invent_scope_authority_or_summary_fields(self):
        mutations=[lambda p:p.update(workspace_id='d'*32),lambda p:p.update(generation_submitted=0),
                   lambda p:p.update(extra=True),lambda p:p['assets'][0].update(path='/private'),
                   lambda p:p['assets'][0].update(url='https://remote/image'),
                   lambda p:p['assets'][0].update(bytes=True),lambda p:p['assets'][0].update(title='x'*201),
                   lambda p:p['assets'][0].update(favorite=1),lambda p:p['assets'][0].update(created_at=float('inf')),
                   lambda p:p['assets'][0].update(created_at=10**400),
                   lambda p:p.update(limit=100),lambda p:p['catalogue'].update(revision=True),
                   lambda p:p['assets'][0].update(truncated_fields=['id']),
                   lambda p:p['assets'][0].update(trashed_at=0),lambda p:p['assets'][0].update(title='\ud800')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value=copy.deepcopy(self.page);mutation(value);response=self.reply(value)
                with self.assertRaises(ValueError):self.client.page(workspace_id=self.scope)
                self.assertTrue(response.closed)

    def test_duplicate_keys_bad_utf8_truncated_and_oversize_framing_refuse(self):
        for raw in (b'{"assets":[],"assets":[]}',b'\xff',b'{"number":NaN}',b'['*1000+b']'*1000):
            response=self.reply(raw)
            with self.assertRaises(ValueError):self.client.page()
            self.assertTrue(response.closed)
        response=self.reply(self.page,length=asset_reads.MAX_RESPONSE_BYTES+1)
        with self.assertRaises(ValueError):self.client.page()
        self.assertTrue(response.closed)
        from http.client import IncompleteRead
        response=self.reply(self.page,length=20000)
        with self.assertRaises(IncompleteRead):self.client.page()
        self.assertTrue(response.closed)

    def test_selection_requires_every_requested_id_in_order_with_truthful_lifecycle(self):
        value={key:copy.deepcopy(v) for key,v in self.page.items() if key in
               ('workspace_id','catalogue','observation_only','media_bytes_verified','generation_submitted')}
        value.update(format='studio.asset-selection/v1',items=[{'id':'asset-one','state':'active','asset':self.asset},
                                                               {'id':'missing','state':'missing','asset':None}])
        self.reply(value);self.assertEqual(len(self.client.selection(['asset-one','missing'],workspace_id=self.scope)['items']),2)
        for mutate in (lambda x:x['items'].reverse(),lambda x:x['items'].pop(),
                       lambda x:x['items'][0].update(state='missing'),lambda x:x['items'][1].update(state='active')):
            wrong=copy.deepcopy(value);mutate(wrong);self.reply(wrong)
            with self.assertRaises(ValueError):self.client.selection(['asset-one','missing'],workspace_id=self.scope)

    def test_legitimate_large_unicode_selection_is_not_subject_to_authoring_one_mib_cap(self):
        items=[]
        for i in range(200):
            a=dict(self.asset,id='a'+str(i),title='🌙'*200,filename='🌙'*256,preset_name='🌙'*200,
                   url='/api/assets/a'+str(i)+'/file')
            items.append({'id':a['id'],'state':'active','asset':a})
        value={key:v for key,v in self.page.items() if key in
               ('workspace_id','catalogue','observation_only','media_bytes_verified','generation_submitted')}
        value.update(format='studio.asset-selection/v1',items=items)
        self.assertGreater(len(json.dumps(value).encode()),1024*1024)
        self.assertLess(len(json.dumps(value).encode()),asset_reads.MAX_RESPONSE_BYTES)
        self.reply(value)
        self.assertEqual(len(self.client.selection([i['id'] for i in items],workspace_id=self.scope)['items']),200)

    def test_page_order_duplicates_and_wrong_next_cursor_refuse(self):
        for mutate in (lambda p:p['assets'].append(copy.deepcopy(p['assets'][0])),
                       lambda p:p.update(next_cursor='invalid'),
                       lambda p:p.update(next_cursor=asset_reads._encode_cursor(self.scope,self.stamp,'a'*64,50,self.asset))):
            value=copy.deepcopy(self.page);mutate(value);self.reply(value)
            with self.assertRaises(ValueError):self.client.page()

    def test_input_refusal_happens_before_io_and_no_remote_origins(self):
        with patch.object(self.client.opener,'open',side_effect=AssertionError('I/O reached')):
            for kwargs in ({'limit':True},{'limit':101},{'filters':{'favorite':1}},{'workspace_id':'bad'},{'cursor':'bad'}):
                with self.assertRaises(ValueError):self.client.page(**kwargs)
            for ids in ([],['same','same'],['x']*201):
                with self.assertRaises(ValueError):self.client.selection(ids,workspace_id=self.scope)
        for base in ('https://127.0.0.1:8191','http://remote.test','http://user@127.0.0.1:8191'):
            with self.assertRaises(ValueError):self.module.AssetReadClient(base)

    def test_http_refusal_is_bounded_closed_and_preserves_status_without_retry(self):
        from studio_workflow.client import ClientError
        raw=json.dumps({'error':'Refresh explicitly','code':'asset_cursor_stale'}).encode()
        response=Reply(raw)
        error=HTTPError('http://127.0.0.1:8191/api/assets/page',409,'Conflict',response.headers,response)
        with patch.object(self.client.opener,'open',side_effect=error) as calls:
            with self.assertRaises(ClientError) as got:self.client.page()
        self.assertEqual(got.exception.code,'asset_cursor_stale');self.assertEqual(got.exception.status,409)
        self.assertEqual(calls.call_count,1);self.assertTrue(response.closed)

    def test_cli_transport_truncation_is_an_error_not_a_traceback(self):
        from http.client import IncompleteRead
        with patch.object(self.module.AssetReadClient,'page',side_effect=IncompleteRead(b'{}',5)), \
             patch('sys.stderr',new_callable=io.StringIO) as error:
            self.assertEqual(self.module.main(['page']),2)
        self.assertEqual(json.loads(error.getvalue())['code'],'asset_read_failed')


if __name__=='__main__':unittest.main()

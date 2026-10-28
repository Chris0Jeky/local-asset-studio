"""Agent collection discovery delegates to one strict read, never a command."""
import io
import json
import unittest
from unittest.mock import patch

import test_collection_read_client as fixture
from studio_workflow.agent_bridge import AgentBridge, MODES
from studio_workflow.client import Client
from studio_workflow.core import digest
from studio_workflow.mcp_server import main


class WorkflowCollectionReads(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.CollectionReadClientTests();self.fixture.setUp()
        self.client=Client(timeout=7);self.bridge=AgentBridge(self.client)

    def reply(self,value):
        response=self.fixture.reply(value);self.client.opener=self.fixture.client.opener
        return response

    def test_tool_is_read_only_in_all_modes_and_discovery_has_no_io(self):
        with patch.object(self.client.opener,'open',side_effect=AssertionError('Unexpected I/O')):
            for mode in MODES:
                definitions=AgentBridge(self.client,mode).definitions()
                self.assertIn('collection_page',definitions)
                self.assertEqual(definitions['collection_page']['mode'],'read')
                self.assertIs(definitions['collection_page']['mutating'],False)
                self.assertIs(definitions['collection_page']['inputSchema']['additionalProperties'],False)
            definitions['collection_page']['inputSchema']['properties'].clear()
            self.assertIn('privacy',self.bridge.definitions()['collection_page']['inputSchema']['properties'])
        with patch('studio_workflow.mcp_server.serve',side_effect=AssertionError('SDK loaded')), \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(main(['--describe']),0)
        self.assertIn('collection_page',json.loads(output.getvalue())['tools'])

    def test_exact_result_hash_context_and_single_raw_get(self):
        f=self.fixture;response=self.reply(f.page)
        args={'workspace_id':f.scope,'limit':50,'privacy':'regular'}
        with patch.object(self.client,'request',side_effect=AssertionError('Loose decoder')), \
             patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
            result=self.bridge.invoke('collection_page',args)
        self.assertTrue(result['ok'],result);self.assertEqual(json.loads(result['data_json']),f.page)
        self.assertEqual(result['context'],args);self.assertEqual(result['data_sha256'],digest(f.page))
        self.assertEqual(calls.call_count,1);self.assertEqual(calls.call_args.args[0].get_method(),'GET')
        self.assertEqual(calls.call_args.kwargs['timeout'],7);self.assertTrue(response.closed)

    def test_invalid_inputs_and_mismatched_privacy_are_local_refusals(self):
        cases=[None, {'limit':True},{'limit':101},{'privacy':'PRIVATE'},{'privacy':None},
               {'cursor':self.fixture.cursor(privacy='private')},{'cursor':'bad'},
               {'workspace_id':'../other'},{'url':'http://remote.test'},{'automatic_pages':True}]
        with patch.object(self.client.opener,'open',side_effect=AssertionError('Unexpected I/O')) as calls:
            for args in cases:
                with self.subTest(args=args):
                    result=self.bridge.invoke('collection_page',args)
                    self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'invalid_arguments',result)
                    self.assertNotIn('recovery',result['error'])
        calls.assert_not_called()

    def test_bad_reply_and_transport_loss_are_read_failures_without_retries(self):
        for failure in ('malformed','lost'):
            args={'cursor':self.fixture.cursor(),'limit':50,'privacy':'regular'}
            self.reply(dict(self.fixture.page,collections=[dict(self.fixture.item,privacy='private')]))
            kwargs={'side_effect':OSError('Synthetic lost reply')} if failure=='lost' else {'wraps':self.client.opener.open}
            with patch.object(self.client.opener,'open',**kwargs) as calls:
                result=self.bridge.invoke('collection_page',args)
            self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'request_failed',result)
            self.assertEqual(result['context'],args);self.assertNotIn('recovery',result['error'])
            self.assertEqual(calls.call_count,1)

    def test_native_bridge_keeps_private_collections_explicit(self):
        f=fixture.CollectionReadHTTPTests();f.setUp();self.addCleanup(f.doCleanups)
        bridge=AgentBridge(Client(f.url,timeout=5));before=f.fixture.store.snapshot(privacy='all')
        for scope,expected in [('regular',['alpha','beta']),('private',['hidden']),('all',['alpha','beta','hidden'])]:
            args={} if scope=='regular' else {'privacy':scope}
            result=bridge.invoke('collection_page',args)
            self.assertTrue(result['ok'],result)
            self.assertEqual([c['id'] for c in json.loads(result['data_json'])['collections']],expected)
        self.assertEqual(len(f.requests),3)
        self.assertEqual(f.fixture.store.snapshot(privacy='all'),before)

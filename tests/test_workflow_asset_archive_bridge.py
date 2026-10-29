"""Archive permissions, request ownership and no-retry errors on the real HTTP owner."""
import io
import json
import unittest
from unittest.mock import patch
import uuid

import test_workflow_asset_archive_client as fixtures
from studio_workflow.agent_bridge import AgentBridge, MODES
from studio_workflow.asset_archive_client import ArchiveOutcomeUnknown, AssetArchiveClient
from studio_workflow.client import Client
from studio_workflow.core import canonical, digest
from studio_workflow.mcp_server import main


class ArchiveBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ArchiveClientTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.client=Client(self.fixture.client.base,timeout=3)
        self.bridge=AgentBridge(self.client,'author')

    def preview(self,**extra):
        args=dict(ids=self.fixture.ids,workspace_id=self.fixture.scope,request_id=uuid.uuid4().hex,**extra)
        result=self.bridge.invoke('asset_archive_preview',args)
        self.assertTrue(result['ok'],result)
        value=json.loads(result['data_json']);self.assertEqual(digest(value),result['data_sha256'])
        return value

    def arguments(self,plan):
        return {'plan_json':canonical(plan).decode(),'approved_plan_sha256':plan['plan_sha256']}

    def test_discovery_is_inert_and_apply_is_author_only(self):
        with patch.object(self.client.opener,'open',side_effect=AssertionError('Unexpected transport')) as calls:
            for mode in MODES:
                bridge=AgentBridge(self.client,mode);tools=bridge.definitions()
                for name in ('asset_archive_preview','asset_archive_recover'):
                    self.assertIn(name,tools);self.assertFalse(tools[name]['mutating'])
                self.assertEqual('asset_archive_apply' in tools,mode!='read')
                if mode!='read':self.assertTrue(tools['asset_archive_apply']['mutating'])
            denied=AgentBridge(self.client).invoke('asset_archive_apply',{})
            self.assertEqual(denied['error']['code'],'tool_not_allowed');calls.assert_not_called()
        with patch('studio_workflow.mcp_server.serve',side_effect=AssertionError('SDK started')),patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(main(['--describe','--mode','author']),0)
        self.assertIn('asset_archive_apply',json.loads(output.getvalue())['tools'])

    def test_preview_apply_recover_bind_same_identity_and_use_raw_transport(self):
        with patch.object(self.client,'request',side_effect=AssertionError('Loose transport')):
            plan=self.preview()
            with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
                result=self.bridge.invoke('asset_archive_apply',self.arguments(plan))
            self.assertTrue(result['ok'],result);self.assertEqual(calls.call_count,1)
            expected={'request_id':plan['request_id'],'workspace_id':self.fixture.scope,'privacy':'regular','plan_sha256':plan['plan_sha256']}
            self.assertEqual(result['context'],expected)
            readonly=AgentBridge(self.client)
            recovered=readonly.invoke('asset_archive_recover',{'plan_json':canonical(plan).decode()})
            self.assertTrue(recovered['ok'],recovered);self.assertEqual(recovered['data_json'],result['data_json'])
            self.assertEqual(recovered['context'],expected)

    def test_bad_plan_and_approval_are_local_refusals(self):
        plan=self.preview();args=self.arguments(plan)
        cases=[('asset_archive_preview',{}),('asset_archive_apply',dict(args,approved_plan_sha256='0'*64)),
               ('asset_archive_recover',{'plan_json':'{}'}),('asset_archive_apply',dict(args,url='https://example.test'))]
        with patch.object(self.client.opener,'open') as calls:
            for name,arguments in cases:
                result=self.bridge.invoke(name,arguments)
                self.assertEqual(result['error']['code'],'invalid_arguments',result)
                self.assertNotIn('recovery',result['error'])
            calls.assert_not_called()

    def test_unknown_write_keeps_plan_context_and_no_retry(self):
        plan=self.preview()
        with patch.object(self.client.opener,'open',side_effect=OSError('Synthetic disconnected response')) as calls:
            result=self.bridge.invoke('asset_archive_apply',self.arguments(plan))
        self.assertEqual(calls.call_count,1);self.assertEqual(result['error']['code'],'outcome_unknown',result)
        self.assertEqual(result['context']['request_id'],plan['request_id'])
        self.assertEqual(result['context']['plan_sha256'],plan['plan_sha256'])
        self.assertNotIn('plan_json',result['context']);self.assertIn('recovery',result['error'])
        with patch.object(self.client.opener,'open',side_effect=OSError('Lost observation')) as calls:
            result=self.bridge.invoke('asset_archive_recover',{'plan_json':canonical(plan).decode()})
        self.assertEqual(calls.call_count,1);self.assertEqual(result['error']['code'],'request_failed')

    def test_stale_write_is_conflict_without_refresh_or_rebase(self):
        plan=self.preview();self.fixture.store.update(self.fixture.fixture.command(ids=self.fixture.ids[:1]))
        snapshot=self.fixture.store.snapshot(privacy='all')
        with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
            result=self.bridge.invoke('asset_archive_apply',self.arguments(plan))
        self.assertEqual(calls.call_count,1);self.assertEqual(result['error']['code'],'asset_revision_conflict',result)
        self.assertEqual(result['context']['plan_sha256'],plan['plan_sha256'])
        self.assertEqual(self.fixture.store.snapshot(privacy='all'),snapshot)

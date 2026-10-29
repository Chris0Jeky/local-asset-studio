"""Archive observations retain strict typed SDK/CLI and MCP read boundaries."""
import copy
import io
import unittest
from unittest.mock import patch

import test_asset_read_client as fixtures
from studio_workflow.agent_bridge import AgentBridge


class AssetArchiveClientTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AssetReadClientTests();self.fixture.setUp()
        self.client=self.fixture.client;self.page=self.fixture.page;self.asset=self.fixture.asset

    def test_archived_page_retains_timestamp_and_requested_filter(self):
        self.page['filters']['archive']='archived';self.asset['archived_at']=0
        self.fixture.reply(self.page)
        with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
            try:result=self.client.page(filters={'archive':'archived'})
            except ValueError as exc:self.fail('Archive filter is not supported: '+str(exc))
        self.assertEqual(result,self.page);self.assertIn('archive=archived',calls.call_args.args[0].full_url)

    def test_all_archive_states_can_be_observed_but_noop_default_shape_is_unchanged(self):
        self.page['filters']['archive']='all';self.fixture.reply(self.page)
        try:self.assertEqual(self.client.page(filters={'archive':'all'}),self.page)
        except ValueError as exc:self.fail('All Archive states must be explicitly observable: '+str(exc))
        self.asset['archived_at']=12.5;self.fixture.reply(self.page)
        self.assertEqual(self.client.page(filters={'archive':'all'}),self.page)
        self.page['filters'].pop('archive');self.asset.pop('archived_at');self.fixture.reply(self.page)
        with patch.object(self.client.opener,'open',wraps=self.client.opener.open) as calls:
            self.assertEqual(self.client.page(filters={'archive':'active'}),self.page)
        self.assertNotIn('archive=',calls.call_args.args[0].full_url)

    def test_filter_mismatch_and_bad_archive_scalars_are_refused(self):
        # First prove the declared archived shape is understood; otherwise all
        # negative cases could pass merely because the feature is absent.
        self.page['filters']['archive']='archived';self.asset['archived_at']=12.5;self.fixture.reply(self.page)
        try:self.client.page(filters={'archive':'archived'})
        except ValueError as exc:self.fail('Archive response baseline is unsupported: '+str(exc))
        for value in (None,True,False,'12.5',[],{},-1,float('inf')):
            with self.subTest(value=value):
                self.asset['archived_at']=value;self.fixture.reply(self.page)
                with self.assertRaises(ValueError):self.client.page(filters={'archive':'archived'})
        self.asset.pop('archived_at');self.fixture.reply(self.page)
        with self.assertRaises(ValueError):self.client.page(filters={'archive':'archived'})
        self.page['filters'].pop('archive');self.asset['archived_at']=12.5;self.fixture.reply(self.page)
        with self.assertRaises(ValueError):self.client.page()

    def test_invalid_archive_filter_is_rejected_before_transport(self):
        for value in (None,False,1,[],{},'trash','ARCHIVED',''):
            with self.subTest(value=value),patch.object(self.client,'_observe') as observe:
                with self.assertRaises(ValueError):self.client.page(filters={'archive':value})
                observe.assert_not_called()

    def test_explicit_selection_keeps_archive_without_changing_trash_state(self):
        self.asset['archived_at']=42
        value={key:copy.deepcopy(v) for key,v in self.page.items() if key in
               ('workspace_id','catalogue','observation_only','media_bytes_verified','generation_submitted')}
        value.update(format='studio.asset-selection/v1',items=[{'id':self.asset['id'],'state':'active','asset':self.asset}])
        self.fixture.reply(value)
        try:result=self.client.selection([self.asset['id']],workspace_id=self.fixture.scope)
        except ValueError as exc:self.fail('Exact-ID selection must retain Archive state: '+str(exc))
        self.assertEqual(result,value);self.assertEqual(result['items'][0]['state'],'active')

    def test_cli_and_read_only_mcp_expose_the_independent_filter(self):
        with patch.object(self.fixture.module.AssetReadClient,'page',return_value=self.page) as page,patch('sys.stdout',new_callable=io.StringIO):
            try:code=self.fixture.module.main(['page','--archive','archived'])
            except SystemExit as exc:self.fail('CLI Archive choice is missing: '+str(exc))
        self.assertEqual(code,0);self.assertEqual(page.call_args.kwargs['filters']['archive'],'archived')
        for mode in ('read','author','execute'):
            tool=AgentBridge(mode=mode).definitions()['asset_page']
            self.assertFalse(tool['mutating'])
            self.assertEqual(tool['inputSchema']['properties']['filters']['properties'].get('archive',{}).get('enum'),['active','archived','all'])


if __name__=='__main__':unittest.main()

"""Read-only shortlist contracts over real Studio routes and shared clients."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from studio_workflow import http_extension as HTTP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))


def make_studio(root):
    """Inert external runtime; real files and production shortlist policy."""
    class Studio:
        def __init__(self):
            self.root = Path(root); self.catalog_path = self.root/'catalog.json'
            self.catalog_path.write_text('{}', encoding='utf-8')
            self.backends = SimpleNamespace(active='primary', busy=False, operation=None)
            self.comfy_url = 'http://127.0.0.1:8188'; self.lock = threading.RLock()
            self.worker = SimpleNamespace(ident=1, is_alive=lambda: True)
            self.calls = []; self.presets = []; self.requirements = {}; self.config = {}
            self._schema = {'Text': {}, 'LoadImage': {}, 'SaveImage': {}, 'SaveVideo': {}}
            self._schema_at = 0
            self.library = SimpleNamespace(manifest=lambda: {'assets': []})
        def add(self, key, operation='new-image', count=0, modality='image', **extra):
            import hashlib
            graph = {'1': {'class_type':'Text', 'inputs': {'text':'Fixture', 'seed':2**64-1}},
                     '2': {'class_type':'SaveImage', 'inputs': {'images':['1',0]}}}
            path = self.root/(key+'.json');path.write_text(json.dumps(graph), encoding='utf-8')
            preset = dict(id=key, name=key, graph=path.name, backend_id='primary', modality=modality,
                          continuation_capability=dict(version=1,operation=operation,consumes_source=count>0,
                          reference_count=count,requires_mask=False,prompt_role='description',
                          template_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            preset.update(extra);self.presets.append(preset);self.requirements[key]=[]
            return preset
        def catalog(self): self.calls.append('catalog');return {'presets': copy.deepcopy(self.presets)}
        def node_info(self, refresh=False): self.calls.append('nodes');return self._schema
        def graph_for(self, preset):
            path=self.root/preset['graph'];return json.loads(path.read_bytes()),path
        def preset_requirements(self, preset, graph, **kwargs):
            self.calls.append('requirements:'+preset['id']);return copy.deepcopy(self.requirements[preset['id']])
        def prune_disabled_loras(self,graph):
            from server import Studio as ActualStudio
            return ActualStudio.prune_disabled_loras(self,graph)
        def host_commit_preflight(self,preset,graph): self.calls.append('memory:'+preset['id']);return None
        def __getattr__(self,key): raise AssertionError('Unexpected execution/storage access: '+key)
    return Studio()


class ShortlistTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.s=make_studio(self.temp.name)
    def request(self, **kwargs):
        return HTTP.post(HTTP.PREFIX+'/shortlist',dict(goal='new-image',reference_count=0,**kwargs),self.s)
    def test_endpoint_is_read_only_and_does_not_fabricate_execution_authority(self):
        self.s.add('plain');before={p.name:p.read_bytes() for p in self.s.root.iterdir()}
        result=self.request()
        self.assertFalse(result['generation_submitted']);self.assertFalse(result['execution_authorized'])
        self.assertEqual(result['candidates'][0]['status'],'observed')
        self.assertEqual(result['candidates'][0]['preset_id'],'plain')
        self.assertEqual(self.s.calls.count('nodes'),1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.s.root.iterdir()})
    def test_route_matching_uses_operation_and_modality_not_family_or_title(self):
        self.s.add('plain');self.s.add('misleading', 'image-to-image',1,name='New image')
        self.s.add('video','new-image',0,'video');self.s.add('mesh','image-to-3d',1,'3d')
        self.assertEqual([r['preset_id'] for r in self.request()['candidates']],['plain'])
    def test_no_reference_recipe_cannot_silently_ignore_declared_source(self):
        self.s.add('plain')
        result=HTTP.post(HTTP.PREFIX+'/shortlist',{'goal':'new-image','reference_count':1},self.s)
        self.assertEqual(result['candidates'][0]['status'],'needs_setup')
        self.assertIn('unused_references',[c['code'] for c in result['candidates'][0]['checks']])
    def test_references_are_declared_not_claimed_staged_or_valid(self):
        self.s.add('edit','instruction-edit',2)
        for count,state,code in [(0,'needs_setup','references_missing'),(1,'needs_setup','references_missing'),(2,'unknown','references_unchecked'),(3,'needs_setup','unused_references')]:
            with self.subTest(count=count):
                result=HTTP.post(HTTP.PREFIX+'/shortlist',{'goal':'edit-image','reference_count':count},self.s)
                row=result['candidates'][0];self.assertEqual(row['status'],state)
                self.assertIn(code,[c['code'] for c in row['checks']])
    def test_missing_and_unknown_requirements_remain_distinct_and_visible(self):
        self.s.add('plain');self.s.requirements['plain']=[{'file':'vae/missing.safetensors','present':False,'note':'missing','path':'C:/models/vae/missing.safetensors','installable':False}, {'file':'renamed.gguf','present':None,'note':'Unknown loader','path':None,'installable':False}]
        row=self.request()['candidates'][0];self.assertEqual(row['status'],'needs_setup')
        codes=[c['code'] for c in row['checks']];self.assertIn('models_missing',codes);self.assertIn('models_unknown',codes)
        self.assertEqual(len(row['requirements']),2)
    def test_offline_schema_is_unknown_never_all_nodes_missing(self):
        self.s.add('plain')
        with patch.object(self.s,'node_info',side_effect=OSError('offline')):
            row=self.request()['candidates'][0]
        self.assertEqual(row['status'],'unknown');self.assertIn('schema_unknown',[c['code'] for c in row['checks']])
        self.assertNotIn('nodes_missing',[c['code'] for c in row['checks']])
    def test_other_backend_cannot_borrow_active_node_evidence(self):
        self.s.add('isolated',backend_id='hidream')
        row=self.request()['candidates'][0]
        self.assertEqual(row['status'],'needs_setup');self.assertIn('backend_switch',[c['code'] for c in row['checks']])
        self.assertIn('schema_unknown',[c['code'] for c in row['checks']])
    def test_runtime_worker_and_host_commit_holds_are_not_lost(self):
        self.s.add('plain',runtime_block='Known runtime failure')
        self.s.worker.is_alive=lambda:False
        with patch.object(self.s,'host_commit_preflight',side_effect=ValueError('Insufficient commit headroom')):
            row=self.request()['candidates'][0]
        codes=[c['code'] for c in row['checks']]
        for code in ('runtime_block','worker_unavailable','memory_hold'):self.assertIn(code,codes)
    def test_backend_change_during_discovery_refuses_snapshot(self):
        self.s.add('plain')
        def change(refresh=False):self.s.backends.active='hidream';return self.s._schema
        with patch.object(self.s,'node_info',side_effect=change),self.assertRaisesRegex(ValueError,'changed'):
            self.request()
    def test_backend_aba_operation_change_refuses_snapshot(self):
        self.s.add('plain')
        def change(refresh=False):self.s.backends.operation={'id':'new-switch','status':'completed'};return self.s._schema
        with patch.object(self.s,'node_info',side_effect=change),self.assertRaisesRegex(ValueError,'changed'):
            self.request()
    def test_template_drift_never_receives_current_match(self):
        self.s.add('plain');(self.s.root/'plain.json').write_text('{}')
        row=self.request()['candidates'][0];self.assertEqual(row['status'],'unknown')
        self.assertIn('inspection_failed',[c['code'] for c in row['checks']])
    def test_missing_class_is_a_block_without_running_native_validation(self):
        self.s.add('plain');self.s._schema={'SaveImage':{}}
        row=self.request()['candidates'][0];self.assertEqual(row['status'],'needs_setup')
        self.assertIn('nodes_missing',[c['code'] for c in row['checks']])
    def test_pagination_is_bounded_and_rejects_a_changed_snapshot(self):
        for i in range(15):self.s.add('recipe-'+str(i).zfill(2))
        first=self.request(limit=6);self.assertEqual(len(first['candidates']),6);self.assertEqual(first['total'],15)
        second=self.request(limit=6,offset=first['next_offset'],expected_snapshot=first['snapshot_sha256'])
        self.assertFalse(set(x['preset_id'] for x in first['candidates']) & set(x['preset_id'] for x in second['candidates']))
        self.s.requirements['recipe-00']=[{'file':'missing','present':False}]
        with self.assertRaisesRegex(ValueError,'changed'):self.request(offset=6,expected_snapshot=first['snapshot_sha256'])
    def test_invalid_request_is_rejected_before_reading_anything(self):
        for args in ({'goal':'invented'},{'goal':'new-image','reference_count':True},{'goal':'new-image','reference_count':4}, {'goal':'new-image','run':True},{'goal':'new-image','limit':200},{'goal':'new-image','offset':1}):
            with self.subTest(args=args),self.assertRaises(ValueError):HTTP.post(HTTP.PREFIX+'/shortlist',args,self.s)
        self.assertEqual(self.s.calls,[])
    def test_unknown_capability_is_diagnostic_not_an_invented_route(self):
        p=self.s.add('plain');p.pop('continuation_capability')
        result=self.request();self.assertEqual(result['candidates'],[]);self.assertTrue(result['diagnostics'])
    def test_order_prefers_observed_prerequisites_not_historical_art_badges(self):
        self.s.add('blocked',verified=True,runtime_block='Hold');self.s.add('good',verified=False)
        rows=self.request()['candidates'];self.assertEqual(rows[0]['preset_id'],'good')
        self.assertNotIn('accepted',json.dumps(rows))

    def test_malformed_schema_is_unknown_not_a_missing_class_report(self):
        self.s.add('plain')
        with patch.object(self.s,'node_info',return_value={'error':'offline'}):
            row=self.request()['candidates'][0]
        self.assertEqual(row['status'],'unknown')
        self.assertIn('schema_unknown',[c['code'] for c in row['checks']])
    def test_conflicting_source_evidence_is_not_a_supported_route(self):
        p=self.s.add('plain');p['continuation_capability']['consumes_source']=True
        report=self.request();self.assertFalse(report['candidates']);self.assertTrue(report['diagnostics'])

    def test_shared_client_refuses_unbound_or_authorizing_replies(self):
        from studio_workflow.shortlist import observe
        self.s.add('plain');report=self.request()
        for change in ({'goal':'edit-image'},{'execution_authorized':True},{'offset':6},{'snapshot_sha256':'bad'},{'candidates':[{}]*13}):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'context'):
                observe(lambda *args:{**report,**change},{'goal':'new-image'})

if __name__=='__main__':unittest.main()

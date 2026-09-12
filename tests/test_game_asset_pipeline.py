import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import game_asset_pipeline as p


def sample():
    return {'schema_version':1,'asset_id':'test-character','route':'reference-image','description':'An original fantasy character portrait.','references':[],'target':{'engine':'godot','outputs':['PNG','ORA']},'constraints':['Preserve costume'],'budget':{'generation_attempts':4,'repair_attempts_per_stage':1,'allow_paid_services':False}}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.brief=sample();self.routes=p.catalog()
    def plan(self):return p.make_plan(self.brief,self.routes)
    def test_routes_and_capabilities(self):
        caps=p.read_json(ROOT/'research/game-assets/capabilities.json')
        ids={c['id'] for c in caps['capabilities']}
        self.assertEqual(len(self.routes['routes']),8)
        for key,r in self.routes['routes'].items():
            b=sample();b['route']=key;plan=p.make_plan(b,self.routes);p.check_plan(plan)
            self.assertTrue(all(t['capability'] in ids for t in plan['tasks']))
    def test_reproducible_plan(self):
        self.assertEqual(self.plan(),self.plan());self.assertFalse(self.plan()['submits_generation'])
    def test_changed_brief_hash(self):
        a=self.plan();self.brief['description']='A different character.'
        self.assertNotEqual(a['plan_sha256'],self.plan()['plan_sha256'])
    def test_plan_detaches_embedded_brief_from_caller(self):
        plan=self.plan();self.brief['description']='Caller mutation';self.brief['budget']['generation_attempts']=99
        p.check_plan(plan)
        self.assertEqual(plan['brief']['description'],'An original fantasy character portrait.')
        self.assertEqual(plan['brief']['budget']['generation_attempts'],4)
    def test_bad_reference_role(self):
        self.brief['references']=[{'id':'ref-a','role':'anything','kind':'image'}]
        with self.assertRaises(ValueError):self.plan()
    def test_paid_not_authorized(self):
        self.brief['budget']['allow_paid_services']=True
        with self.assertRaises(ValueError):self.plan()
    def test_bool_budget_rejected(self):
        self.brief['budget']['generation_attempts']=True
        with self.assertRaises(ValueError):self.plan()
    def test_unknown_route(self):
        self.brief['route']='made-up'
        with self.assertRaises(ValueError):self.plan()
    def test_missing_target(self):
        del self.brief['target']
        with self.assertRaises(ValueError):self.plan()
    def test_relative_paths(self):
        for bad in ('../a','/tmp/a','C:\\a','a//b','a/./b','a/../../b','https://host/file'):
            with self.assertRaises(ValueError,msg=bad):p.relative(bad)
    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'work').mkdir();(base/'outside').write_text('data')
            try:(base/'work/link').symlink_to(base/'outside')
            except OSError:self.skipTest('Symlinks unavailable')
            with self.assertRaises(ValueError):p.inside(base/'work','link')
    def test_prompt_image_role_order(self):
        self.brief['references']=[dict(id='id-a',role='identity',kind='image',path='a.png',sha256='a'*64,take=['face'],ignore=['pose']),dict(id='rig-a',role='geometry',kind='rig',path='r.blend',sha256='b'*64,take=['scale'],ignore=[]),dict(id='id-b',role='pose',kind='image',path='b.png',sha256='c'*64,take=['pose'],ignore=['face'])]
        prompt=self.plan()['reference_instructions']
        self.assertIn('Picture 2 [pose]',prompt);self.assertNotIn('Picture 3',prompt);self.assertNotIn('Image ',prompt)
    def test_duplicate_references(self):
        ref=dict(id='ref-a',role='identity',kind='image',path='a.png',sha256='a'*64,take=[],ignore=[])
        self.brief['references']=[ref,ref]
        with self.assertRaises(ValueError):self.plan()
    def test_bad_reference_hash(self):
        self.brief['references']=[dict(id='ref-a',role='identity',kind='image',path='a.png',sha256='fake',take=[],ignore=[])]
        with self.assertRaises(ValueError):self.plan()
    def test_initial_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([t['id'] for t in p.next_tasks(self.plan(),[],tmp)['ready']],['preflight'])
    def test_receipt_unlocks_only_next_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'report.json').write_text('{}');plan=self.plan()
            r=p.receipt_for(plan,[],tmp,'preflight',['report.json'],'test-reviewer','Read-only preflight fixture')
            state=p.next_tasks(plan,[r],tmp)
            self.assertEqual([t['id'] for t in state['ready']],['design']);self.assertFalse(state['finished'])
    def test_cannot_skip_prerequisite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):p.receipt_for(self.plan(),[],tmp,'design',[],'test','note')
    def test_changed_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'report';f.write_text('old');plan=self.plan()
            r=p.receipt_for(plan,[],tmp,'preflight',['report'],'test','fixture');f.write_text('new')
            with self.assertRaises(ValueError):p.next_tasks(plan,[r],tmp)
    def test_changed_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'ref';f.write_text('old')
            self.brief['references']=[dict(id='ref-a',role='identity',kind='image',path='ref',sha256=p.file_sha(f),take=[],ignore=[])]
            plan=self.plan();f.write_text('new')
            with self.assertRaises(ValueError):p.next_tasks(plan,[],tmp)
    def test_duplicate_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'report').write_text('ok');plan=self.plan()
            r=p.receipt_for(plan,[],tmp,'preflight',['report'],'test','fixture')
            with self.assertRaises(ValueError):p.next_tasks(plan,[r,r],tmp)
    def test_modified_plan(self):
        plan=self.plan();plan['tasks'][0]['instruction']='changed'
        with self.assertRaises(ValueError):p.check_plan(plan)
    def test_wrong_receipt_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'report').write_text('ok');a=self.plan()
            r=p.receipt_for(a,[],tmp,'preflight',['report'],'test','fixture')
            self.brief['description']='Other asset';b=self.plan()
            with self.assertRaises(ValueError):p.next_tasks(b,[r],tmp)
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'file';p.write_json({},f)
            with self.assertRaises(FileExistsError):p.write_json({},f)
    def test_json_duplicates_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'a.json'
            for raw in ('{"a":1,"a":2}','{"a":NaN}'):
                f.write_text(raw)
                with self.assertRaises(ValueError):p.read_json(f)
    def test_graph_cycle(self):
        g={'1':{'class_type':'A','inputs':{'x':['1',0]}}}
        with self.assertRaises(ValueError):p.graph_check(g)
    def test_graph_dangling(self):
        with self.assertRaises(ValueError):p.graph_check({'1':{'class_type':'A','inputs':{'x':['2',0]}}})
    def test_graph_nonfinite(self):
        with self.assertRaises(ValueError):p.graph_check({'1':{'class_type':'A','inputs':{'x':float('nan')}}})
    def test_schema_snapshot(self):
        g={'1':{'class_type':'A','inputs':{'x':2}},'2':{'class_type':'B','inputs':{'image':['1',0]}}}
        info={'A':{'input':{'required':{'x':['INT',{'min':1,'max':4}]}},'output':['IMAGE']},'B':{'input':{'required':{'image':['IMAGE']}},'output':[]}}
        self.assertTrue(p.graph_check(g,info)['node_snapshot_checked']);self.assertFalse(p.graph_check(g,info)['inference_verified'])
        g['1']['inputs']['x']=5
        with self.assertRaises(ValueError):p.graph_check(g,info)
    def test_schema_enum_missing_node(self):
        g={'1':{'class_type':'A','inputs':{'x':'bad'}}}
        with self.assertRaises(ValueError):p.graph_check(g,{})
        with self.assertRaises(ValueError):p.graph_check(g,{'A':{'input':{'required':{'x':[['good']]}}}})
    def test_schema_v3_combo_options_and_invalid_enums(self):
        g={'1':{'class_type':'A','inputs':{'choice':'good'}}}
        info={'A':{'input':{'required':{'choice':['COMBO',{'options':['good','better']}] }},'output':[]}}
        self.assertTrue(p.graph_check(g,info)['node_snapshot_checked'])
        for descriptor in (['COMBO'],['COMBO',{}],['COMBO',{'options':[]}],['COMBO',{'options':['good',{}]}]):
            with self.assertRaises(ValueError):p.graph_check(g,{'A':{'input':{'required':{'choice':descriptor}},'output':[]}})
    def test_shipped_qwen_variants(self):
        folder=ROOT/'research/game-assets/workflows'
        for count in (1,2,3):
            g=p.read_json(folder/f'qwen-{count}ref-api.json');p.graph_check(g)
            for encoder in ('6','7'):
                keys={k for k in g[encoder]['inputs'] if k.startswith('image')}
                self.assertEqual(keys,{f'image{n}' for n in range(1,count+1)})
            self.assertEqual(g['11']['inputs']['steps'],4)
    def test_factory_preserves_baseline(self):
        g=p.read_json(ROOT/'workflows/api/qwen-api.json');original=copy.deepcopy(g)
        outputs=p.qwen_variants(g);self.assertEqual(g,original)
        for out in outputs.values():
            for key in ('1','2','3','8','9','11','12'):self.assertEqual(out[key],g[key])
        with self.assertRaises(ValueError):p.qwen_variants(outputs['qwen-3ref-api.json'])
    def test_factory_matches_committed_variants(self):
        g=p.read_json(ROOT/'workflows/api/qwen-api.json');meta=p.read_json(ROOT/'research/game-assets/workflows/provenance.json')
        # Production baseline may evolve; provenance refers to a pinned historical baseline.
        if p.sha(g)!=meta['canonical_baseline_sha256']:self.skipTest('Baseline changed; regenerate and review variants explicitly')
        for name,result in p.qwen_variants(g).items():self.assertEqual(result,p.read_json(ROOT/'research/game-assets/workflows'/name))
    def test_cli_failure_json(self):
        stream=io.StringIO()
        with redirect_stderr(stream):code=p.main(['graph-check','missing-file.json'])
        self.assertEqual(code,2);self.assertIn('error',json.loads(stream.getvalue()))


if __name__=='__main__':unittest.main()

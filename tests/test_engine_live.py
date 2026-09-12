"""Opt-in real native-tool integration. No mock is permitted in this lane."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import godot_asset_adapter as adapter
import engine_validation as evidence
from engine_fixture import create,model,glb_bytes

READY=bool(os.environ.get('STUDIO_TEST_GODOT') and os.environ.get('STUDIO_TEST_NODE'))
if os.environ.get('STUDIO_REQUIRE_ENGINE_TESTS')=='1' and not READY:
    raise RuntimeError('Required native tests lack explicit executables')

@unittest.skipUnless(READY,'Explicit STUDIO_TEST_GODOT and STUDIO_TEST_NODE required; no native tool was run')
class LiveEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=None
        if os.environ.get('STUDIO_ENGINE_EVIDENCE'):
            self.root=Path(os.environ['STUDIO_ENGINE_EVIDENCE'])/self._testMethodName
        else:
            self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.root.mkdir(parents=True,exist_ok=True)
    def tearDown(self):
        if self.temp:self.temp.cleanup()
    def run_fixture(self,*,loop=True,blank=False,glb=False,skinned=False):
        source=self.root/'source';create(source,loop=loop,blank=blank,skinned=skinned)
        result=adapter.execute(source,'manifest.json',self.root/'verified',os.environ['STUDIO_TEST_GODOT'],
                               'fixture.glb' if glb else None,node_path=os.environ['STUDIO_TEST_NODE'])
        print(json.dumps({'test':self._testMethodName,'state':result['state'],
            'playback':result['report']['playback'],'gltf':result['gltf_validation']},sort_keys=True))
        return result
    def test_actual_loop_with_blank_and_hold_frames(self):
        result=self.run_fixture(blank=True)
        report=result['report'];self.assertEqual(report['playback']['signal'],'animation_looped')
        self.assertAlmostEqual(report['playback']['elapsed_ms'],480,delta=8.35)
        self.assertEqual(report['sprite']['frames'][1]['alpha']['alpha_pixels'],0)
        self.assertEqual([e['frame'] for e in report['playback']['frame_events']],[0,1,2,3])
        self.assertEqual(adapter.inspect(self.root/'verified'),report)
    def test_actual_nonloop_completion(self):
        report=self.run_fixture(loop=False)['report']
        self.assertEqual(report['playback']['signal'],'animation_finished')
        self.assertAlmostEqual(report['playback']['elapsed_ms'],480,delta=8.35)
    def test_actual_khronos_import_pose_material_and_tamper(self):
        result=self.run_fixture(glb=True)
        self.assertEqual(result['gltf_validation']['state'],'validated')
        glb=result['report']['glb']
        self.assertEqual(glb['import_profile']['animation_fps'],100)
        clips={c['name']:c for c in glb['animation_samples']}
        self.assertIn('HingeAction',clips)
        samples=clips['HingeAction']['samples']
        mid=next(p for p in samples[1]['transforms'] if p['name']=='Hinge')
        self.assertAlmostEqual(abs(mid['rotation_quaternion'][2]),math.sqrt(.5),places=4)
        root=next(p for p in glb['rest_transforms'] if p['name']=='FixtureRoot')
        self.assertEqual(root['position'],[1,2,3]);self.assertEqual(root['scale'],[1,1,1])
        material=next(m for m in glb['materials'] if m['name']=='FixturePaint')
        self.assertAlmostEqual(material['metallic'],.2,places=5);self.assertAlmostEqual(material['roughness'],.7,places=5)
        adapter.export(self.root/'verified')
        with (self.root/'verified/assets/ember.glb').open('ab') as f:f.write(b'changed')
        with self.assertRaises(evidence.EvidenceError):adapter.export(self.root/'verified')
    def test_actual_skin_binding_inventory(self):
        result=self.run_fixture(glb=True,skinned=True);glb=result['report']['glb']
        self.assertTrue(glb['skins']);self.assertTrue(glb['skeletons'])
        self.assertEqual(len(glb['skins'][0]['binds']),1)
        bones=[b['name'] for s in glb['skeletons'] for b in s['bones']]
        self.assertIn('RootJoint',bones)
    def test_real_validator_rejects_invalid_accessor_before_engine(self):
        source=self.root/'source';create(source);doc,body=model()
        doc['meshes'][0]['primitives'][0]['indices']=999
        (source/'fixture.glb').write_bytes(glb_bytes(doc,body))
        output=self.root/'rejected'
        with self.assertRaisesRegex(evidence.EvidenceError,'Khronos validation failed'):
            adapter.execute(source,'manifest.json',output,os.environ['STUDIO_TEST_GODOT'],'fixture.glb',node_path=os.environ['STUDIO_TEST_NODE'])
        report=evidence.read_json(output/'khronos-report.json');self.assertGreater(report['issues']['numErrors'],0)
        self.assertFalse((output/'godot-import-stdout.log').exists());self.assertTrue((output/'failure.json').exists())
        print(json.dumps({'test':self._testMethodName,'validator_errors':report['issues']['numErrors'],'engine_started':False}))

if __name__=='__main__':unittest.main()

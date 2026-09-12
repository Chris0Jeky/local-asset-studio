import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import engine_validation as evidence
import godot_asset_adapter as adapter
from engine_fixture import create, model, glb_bytes


class EngineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name).resolve()
        self.manifest=create(self.root)
    def tearDown(self):self.temp.cleanup()
    def report(self):
        alpha=evidence.atlas_evidence(self.root/'atlas.png',self.manifest)
        elapsed=0;frames=[];events=[]
        for index,(frame,stats) in enumerate(zip(self.manifest['frames'],alpha['frames'])):
            events.append({'frame':index,'elapsed_ms':elapsed});elapsed+=frame['duration_ms']
            frames.append({'region':frame['region'],'duration_ms':frame['duration_ms'],
                           'relative_duration':frame['duration_ms']*.06,'alpha':stats})
        return {'sprite':{'animation':'idle-qa','frame_count':4,'anchor':[32,60],'logical_canvas':[64,64],
                          'loop':True,'filter':'nearest','texture_filter':1,'anchor_world_error':[0,0],
                          'frames':frames,'total_duration_ms':480},
                'playback':{'completed':True,'signal':'animation_looped','timebase':'process-delta','fixed_fps':240,
                            'speed_scale':1,'elapsed_ms':480,'frame_events':events},
                'glb':{'loaded':True,'meshes':[{'name':'Panel'}],'import_profile':{'animation_fps':100},'animation_samples':[]}}
    def test_glb_container_reports_roles_without_claiming_validation(self):
        result=evidence.inspect_glb(self.root/'fixture.glb')
        self.assertEqual(result['animations'][0]['name'],'HingeAction')
        self.assertEqual(result['materials'][0]['name'],'FixturePaint')
        self.assertIn('specification-validity',result['not_established'])
    def test_glb_truncated_extent_magic_length_version_and_alignment(self):
        good=(self.root/'fixture.glb').read_bytes()
        bads=[good[:10], b'FAIL'+good[4:],good[:4]+struct.pack('<I',1)+good[8:],good+b'x',good[:-1]]
        wrong=bytearray(good);struct.pack_into('<I',wrong,12,999999);bads.append(wrong)
        wrong=bytearray(good);struct.pack_into('<I',wrong,12,3);bads.append(wrong)
        for data in bads:
            with self.subTest(length=len(data)):
                (self.root/'bad.glb').write_bytes(data)
                with self.assertRaises(evidence.EvidenceError):evidence.inspect_glb(self.root/'bad.glb')
    def test_glb_external_and_data_uris_are_never_loaded(self):
        for uri in ('https://example.invalid/model.bin','../../secret', 'data:application/octet-stream;base64,AAAA'):
            doc,body=model();doc['buffers'][0]['uri']=uri
            (self.root/'bad.glb').write_bytes(glb_bytes(doc,body))
            with self.assertRaisesRegex(evidence.EvidenceError,'URI resources'):evidence.inspect_glb(self.root/'bad.glb')
    def test_glb_complexity_and_collection_types(self):
        for changes in ({'nodes':[{}]*2049},{'animations':[{}]*33},{'skins':False}):
            doc,body=model();doc.update(changes);(self.root/'bad.glb').write_bytes(glb_bytes(doc,body))
            with self.assertRaises(evidence.EvidenceError):evidence.inspect_glb(self.root/'bad.glb')
    def test_json_duplicates_and_nonfinite_are_rejected(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'\xff'):
            with self.assertRaises(evidence.EvidenceError):evidence.parse_json(raw)
    def test_glb_inspection_does_not_certify_invalid_accessor(self):
        doc,body=model();doc['meshes'][0]['primitives'][0]['indices']=999
        (self.root/'invalid.glb').write_bytes(glb_bytes(doc,body))
        self.assertIn('specification-validity',evidence.inspect_glb(self.root/'invalid.glb')['not_established'])
    def test_missing_node_does_not_run_anything(self):
        with patch.object(evidence,'run_command') as command:
            with self.assertRaisesRegex(evidence.EvidenceError,'explicit Node'):evidence.validate_glb(self.root/'fixture.glb',None,self.root)
        command.assert_not_called()
    def test_node_path_cannot_be_a_command_string_or_relative(self):
        for value in ('node', 'node --eval x', str(self.root/'missing-node')):
            with patch.object(evidence,'run_command') as command:
                with self.assertRaises(evidence.EvidenceError):evidence.validate_glb(self.root/'fixture.glb',value,self.root)
            command.assert_not_called()
    def test_valid_and_blank_frames_have_exact_alpha_evidence(self):
        self.manifest=create(self.root,blank=True)
        result=evidence.atlas_evidence(self.root/'atlas.png',self.manifest)
        self.assertEqual(result['frames'][1],{'alpha_pixels':0,'bounds':[]})
        self.assertEqual(result['frames'][0],result['frames'][2])
    def test_crop_outside_image_is_rejected(self):
        self.manifest['frames'][3]['region'][0]=300
        with self.assertRaisesRegex(evidence.EvidenceError,'outside'):evidence.atlas_evidence(self.root/'atlas.png',self.manifest)
    def test_atlas_decode_budget(self):
        with patch.object(evidence,'MAX_PIXELS',10):
            with self.assertRaisesRegex(evidence.EvidenceError,'decode budget'):evidence.atlas_evidence(self.root/'atlas.png',self.manifest)
        with patch.object(evidence,'MAX_FRAME_PIXELS',10):
            with self.assertRaisesRegex(evidence.EvidenceError,'80 megapixels'):evidence.atlas_evidence(self.root/'atlas.png',self.manifest)
    def test_package_does_not_invoke_runtime(self):
        with patch.object(adapter,'run_command') as command:
            package=adapter.package_project(self.root,'manifest.json',self.root/'package','fixture.glb')
        command.assert_not_called();self.assertEqual(package['state'],'packaged')
        self.assertEqual((self.root/'fixture.glb').read_bytes(),(self.root/'package/assets/ember.glb').read_bytes())
    def test_quoted_clip_remains_data_not_scene_syntax(self):
        self.manifest['clip']='idle" [node name="Injected"] \\ folder'
        scene=adapter._project_tscn(self.manifest)
        self.assertEqual(scene.count('\n[node '),2)
        self.assertIn('"name": &'+json.dumps(self.manifest['clip']),scene)
    def test_manifest_rejects_bad_duration_anchor_loop_and_shape(self):
        cases=[{'loop':1},{'anchor':[]},{'logical_canvas':[True,64]}, {'clip':'x\ninjected'}, {'frames':[]}]
        for changes in cases:
            value=copy.deepcopy(self.manifest);value.update(changes)
            (self.root/'bad.json').write_text(json.dumps(value))
            with self.assertRaises(evidence.EvidenceError):adapter._read_atlas_manifest(self.root/'bad.json')
        for duration in (True,0,-1,60001,1.5):
            value=copy.deepcopy(self.manifest);value['frames'][0]['duration_ms']=duration
            (self.root/'bad.json').write_text(json.dumps(value))
            with self.assertRaises(evidence.EvidenceError):adapter._read_atlas_manifest(self.root/'bad.json')
    def test_package_refuses_existing_directory_and_escaping_paths(self):
        for manifest in ('../manifest.json',str(self.root/'manifest.json'),'..\\manifest.json'):
            with self.assertRaises(evidence.EvidenceError):adapter.package_project(self.root,manifest,self.root/'out')
        with self.assertRaises(evidence.EvidenceError):adapter.package_project(self.root,'manifest.json',self.root)
    def test_source_change_during_copy_is_detected(self):
        original=adapter.shutil.copyfile
        def copy(source,target):
            result=original(source,target);Path(target).write_bytes(b'changed');return result
        with patch.object(adapter.shutil,'copyfile',side_effect=copy):
            with self.assertRaisesRegex(evidence.EvidenceError,'changed while snapshotting'):adapter.package_project(self.root,'manifest.json',self.root/'out')
    def test_matching_report_accepts_actual_signal_contract(self):
        adapter._verify_report(self.report(),self.manifest,False,evidence.atlas_evidence(self.root/'atlas.png',self.manifest))
    def test_duration_arithmetic_without_playback_is_not_proof(self):
        report=self.report();report.pop('playback')
        with self.assertRaisesRegex(evidence.EvidenceError,'observed playback'):adapter._verify_report(report,self.manifest,False)
    def test_missing_or_forged_timing_and_sequence_fail(self):
        variants=[{'completed':False},{'signal':'animation_finished'},{'timebase':'wall-clock'}, {'fixed_fps':60},
                  {'speed_scale':2},{'elapsed_ms':0},{'elapsed_ms':500},{'frame_events':[]}]
        for changed in variants:
            report=self.report();report['playback'].update(changed)
            with self.subTest(changed=changed),self.assertRaises(evidence.EvidenceError):adapter._verify_report(report,self.manifest,False)
    def test_each_frame_boundary_is_checked(self):
        report=self.report();report['playback']['frame_events'][2]['elapsed_ms']=220
        with self.assertRaisesRegex(evidence.EvidenceError,'boundary'):adapter._verify_report(report,self.manifest,False)
    def test_actual_blank_frame_is_allowed_only_when_source_is_blank(self):
        self.manifest=create(self.root,blank=True);report=self.report()
        adapter._verify_report(report,self.manifest,False,evidence.atlas_evidence(self.root/'atlas.png',self.manifest))
        report['sprite']['frames'][0]['alpha']={'alpha_pixels':0,'bounds':[]}
        with self.assertRaisesRegex(evidence.EvidenceError,'alpha pixels'):adapter._verify_report(report,self.manifest,False,evidence.atlas_evidence(self.root/'atlas.png',self.manifest))
    def test_missing_anchor_error_is_not_vacuously_valid(self):
        report=self.report();report['sprite']['anchor_world_error']=[]
        with self.assertRaisesRegex(evidence.EvidenceError,'anchor'):adapter._verify_report(report,self.manifest,False)
    def test_wrong_rect_and_actual_texture_filter_fail(self):
        report=self.report();report['sprite']['frames'][0]['region']=[1,0,64,64]
        with self.assertRaises(evidence.EvidenceError):adapter._verify_report(report,self.manifest,False)
        report=self.report();report['sprite']['texture_filter']=2
        with self.assertRaises(evidence.EvidenceError):adapter._verify_report(report,self.manifest,False)
    def test_glb_loaded_flag_alone_is_insufficient(self):
        report=self.report();report['glb']['meshes']=[]
        with self.assertRaisesRegex(evidence.EvidenceError,'GLB mesh'):adapter._verify_report(report,self.manifest,True)
    def test_import_profile_is_applied_not_assumed(self):
        report=self.report();report['glb']['import_profile']['animation_fps']=30
        with self.assertRaisesRegex(evidence.EvidenceError,'import profile'):adapter._verify_report(report,self.manifest,True)
    def test_reports_must_be_unique(self):
        for stdout in ('nothing','GODOT_ADAPTER_REPORT={}\nGODOT_ADAPTER_REPORT={}','GODOT_ADAPTER_REPORT=[]'):
            with self.assertRaises(evidence.EvidenceError):adapter._engine_report_from_stdout(stdout)
    def test_nonloop_requires_finished_signal(self):
        self.manifest['loop']=False;report=self.report();report['sprite']['loop']=False;report['playback']['signal']='animation_finished'
        adapter._verify_report(report,self.manifest,False)
    def test_preflight_missing_runtime_does_not_search_path(self):
        with self.assertRaises(evidence.EvidenceError):adapter.preflight('godot')
    def test_real_child_nonzero_exit_is_recorded(self):
        with self.assertRaisesRegex(evidence.EvidenceError,'code 7'):
            evidence.run_command([sys.executable,'-c','print("evidence"); raise SystemExit(7)'],self.root,'failed',5)
        receipt=evidence.read_json(self.root/'failed-exit.json')
        self.assertEqual(receipt['returncode'],7);self.assertIn('evidence',(self.root/'failed-stdout.log').read_text())
    def test_real_child_timeout_retains_evidence_and_stops_child(self):
        with self.assertRaisesRegex(evidence.EvidenceError,'timed out'):
            evidence.run_command([sys.executable,'-c','import time; time.sleep(30)'],self.root,'timeout',.08)
        self.assertEqual(evidence.read_json(self.root/'timeout-exit.json')['state'],'failed')
    def test_real_child_log_budget(self):
        with patch.object(evidence,'MAX_LOG_BYTES',1024):
            with self.assertRaisesRegex(evidence.EvidenceError,'log exceeds'):
                evidence.run_command([sys.executable,'-c','print("x"*10000)'],self.root,'flood',5)
        self.assertEqual(evidence.read_json(self.root/'flood-exit.json')['state'],'failed')
    def test_node_preload_environment_is_removed(self):
        with patch.dict(os.environ,{'NODE_OPTIONS':'--require untrusted','NODE_PATH':'untrusted'}):
            result=evidence.run_command([sys.executable,'-c','import os; print(os.getenv("NODE_OPTIONS")); print(os.getenv("NODE_PATH"))'],self.root,'environment',5)
        self.assertEqual(result['stdout'].splitlines(),['None','None'])
    def test_execute_failure_is_retained_and_not_rerun(self):
        with self.assertRaises(evidence.EvidenceError):adapter.execute(self.root,'manifest.json',self.root/'failed-run',self.root/'missing')
        failure=evidence.read_json(self.root/'failed-run/failure.json');self.assertEqual(failure['state'],'failed')
        with self.assertRaisesRegex(evidence.EvidenceError,'never rerun'):adapter.execute(self.root,'manifest.json',self.root/'failed-run',self.root/'missing')
        with self.assertRaises(evidence.EvidenceError):adapter.export(self.root/'failed-run')
    def test_inspect_and_export_require_success_not_only_report(self):
        output=self.root/'unverified';output.mkdir();evidence.write_json(output/'engine-report.json',{})
        with self.assertRaises((evidence.EvidenceError,OSError)):adapter.export(output)
    def test_evidence_writes_never_clobber(self):
        path=self.root/'receipt.json';evidence.write_json(path,{'one':1})
        with self.assertRaises(FileExistsError):evidence.write_json(path,{'two':2})
        self.assertEqual(evidence.read_json(path),{'one':1})
    def test_glb_verification_without_node_leaves_explicit_failure(self):
        with patch.object(adapter,'preflight') as engine:
            with self.assertRaisesRegex(evidence.EvidenceError,'explicit Node'):
                adapter.execute(self.root,'manifest.json',self.root/'glb-failed',self.root/'godot','fixture.glb')
        engine.assert_not_called();self.assertTrue((self.root/'glb-failed/failure.json').is_file())


if __name__=='__main__':unittest.main()

"""Factory integration contracts; native execution is replaced by explicit fixtures."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import procedural
from engine_fixture import glb_bytes, model
_import_paths = list(sys.path)
from test_procgen_factory import crate_measurements
sys.path[:] = _import_paths


class Assets:
    def __init__(self):self.records = {}
    def register(self, job, index, source):
        identifier = f'{index:032x}'
        self.records[identifier] = (job['id'], Path(source).read_bytes())
        return identifier


def setup_runtime(root):
    config = {}
    for name in ('blender', 'node', 'godot'):
        executable = root / (name + '.exe');executable.write_bytes(name.encode())
        config[name] = str(executable)
    validator = root / 'validator';validator.mkdir()
    (validator / 'package.json').write_text(json.dumps({'name':'gltf-validator', 'version':procedural.engine.VALIDATOR_VERSION}))
    (validator / 'index.js').write_text('// inert test fixture, never executed')
    return config, validator


def fake_build(generator, params, output, blender, godot=None, node=None, render=False, timeout=600):
    """A real set of files and measurements with synthetic native process evidence."""
    output = Path(output);output.mkdir()
    spec = procedural.factory.load_schema()['generators'][generator]
    measurements = crate_measurements(params['width'], params['height'])
    measurements['gn_bounds'] = {k:[r['min'],r['max']] for k,r in spec['params'].items() if r.get('gn',True)}
    for i, lod in enumerate(measurements['lods']):lod['glb'] = f'asset_LOD{i}.glb'
    doc, binary = model()
    for i in range(3):(output / f'asset_LOD{i}.glb').write_bytes(glb_bytes(doc,binary))
    (output / 'asset.blend').write_bytes(b'BLENDER-v300fixture')
    names = [*(f'asset_LOD{i}.glb' for i in range(3)), 'asset.blend']
    if render:
        with Image.new('RGB',(768,768),(90,110,130)) as image:image.save(output / 'contact_sheet.png')
        names.append('contact_sheet.png')
    gates = [{'gate':'params','passed':True,'failures':[]}, {'gate':'constraints','passed':True,'failures':[]}]
    gates += procedural.factory.evaluate_gates(generator,spec,params,measurements)
    gates.append({'gate':'khronos','passed':True,'failures':[]})
    gates.append({'gate':'godot_import','passed':True if godot else None,'failures':[], **({} if godot else {'skipped':'no Godot executable given'})})
    report = {'schema_version':1,'generator':generator,'requested_params':params,'params':params,
              'state':'passed' if godot else 'incomplete','gates':gates,'failed_gates':[],
              'skipped_gates':[] if godot else ['godot_import'],'wall_seconds':0.1,'not_verified':['art direction and taste'],
              'schema_sha256':procedural.engine.file_sha(procedural.factory.SCHEMA_PATH),
              'blender_script_sha256':procedural.engine.file_sha(procedural.factory.BLENDER_SCRIPT),
              'outputs':{name:procedural.engine.file_sha(output / name) for name in names}}
    for name,value in [('measurements.json',measurements),('report.json',report),('blender-exit.json',{'state':'completed','returncode':0})]:
        (output / name).write_text(json.dumps(value))
    (output / 'blender-stdout.log').write_text('fixture only')
    return report


class ProceduralOperationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name);config,validator = setup_runtime(self.root)
        self.validator = patch.object(procedural,'VALIDATOR_DIR',validator);self.validator.start();self.addCleanup(self.validator.stop)
        self.studio = SimpleNamespace(config=config,experiments=self.root / 'experiments',assets=Assets())
        self.project = 'a' * 32
        (self.studio.experiments / 'projects' / self.project).mkdir(parents=True)

    def intent(self, **extra):return {'name':'Crate study','generator':'prop','params':{'kind':1},'render':True, **extra}
    def plan(self, **extra):return procedural.prepare(self.studio,self.intent(**extra))
    def directory(self):return self.studio.experiments / 'projects' / self.project

    def test_catalog_is_available_without_runtime_and_never_launches_native_work(self):
        self.studio.config = {}
        with patch.object(procedural.factory,'build') as build:
            catalog = procedural.catalog(self.studio)
        self.assertEqual(set(catalog['generators']), {'room_kit','prop','shrine','lighthouse_room','pier','coastal_path','tide_pools','market_street'})
        self.assertFalse(catalog['runtime']['ready'])
        self.assertTrue(any('Blender' in value for value in catalog['runtime']['missing']))
        self.assertEqual(catalog['generators']['prop']['params']['kind']['default'],0)
        build.assert_not_called()

    def test_prepare_resolves_params_and_pins_sources_without_creating_an_attempt(self):
        with patch.object(procedural.factory,'build') as build:
            plan = self.plan()
        self.assertEqual(plan['intent']['params']['kind'],1)
        self.assertEqual(plan['intent']['params']['height'],0.6)
        self.assertEqual(plan['operation'],'native.procedural-asset.v1')
        self.assertTrue(plan['no_comfy_submission'])
        self.assertRegex(plan['sha256'],r'^[a-f0-9]{64}$')
        self.assertFalse(any(self.directory().iterdir()))
        build.assert_not_called()

    def test_invalid_intents_do_not_touch_the_filesystem(self):
        cases = [[],self.intent(script='x'),self.intent(output='/tmp/out'),self.intent(privacy='private'),
                 self.intent(generator='nope'),self.intent(params={'width':'2'}),self.intent(params={'detail':4.0}),
                 self.intent(params={'width':float('nan')}),self.intent(params={'width':True}),self.intent(render='yes'),
                 self.intent(generator='room_kit',params={'width':2.4,'window_width':2.4})]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):procedural.prepare(self.studio,case)
        self.assertFalse(any(self.directory().iterdir()))

    def test_missing_or_changed_runtime_blocks_execution_and_preserves_the_plan(self):
        plan = self.plan()
        Path(self.studio.config['blender']).write_bytes(b'changed')
        with patch.object(procedural.factory,'build') as build,self.assertRaisesRegex(ValueError,'changed'):
            procedural.run(self.studio,self.project,plan)
        build.assert_not_called();self.assertFalse(any(self.directory().iterdir()))
        del self.studio.config['node']
        with self.assertRaisesRegex(ValueError,'Node'):self.plan()

    def test_complete_build_registers_three_lods_and_contact_sheet_with_incomplete_engine_evidence(self):
        plan = self.plan()
        with patch.object(procedural.factory,'build',side_effect=fake_build) as build:
            result = procedural.run(self.studio,self.project,plan)
        self.assertEqual(build.call_count,1)
        self.assertEqual(result['job']['status'],'completed')
        self.assertEqual(result['job']['prompt_ids'],[])
        self.assertEqual(result['verification']['state'],'incomplete')
        self.assertEqual(result['verification']['skipped_gates'],['godot_import'])
        self.assertEqual(len(self.studio.assets.records),4)
        self.assertEqual([o['native_path'] for o in result['job']['outputs'][:3]], [f'procedural/asset_LOD{i}.glb' for i in range(3)])
        self.assertTrue((self.directory() / 'export.zip').is_file())
        self.assertIn('report.json', {Path(a['path']).name for a in result['artifacts']})
        with patch.object(procedural.factory,'build') as build,self.assertRaisesRegex(ValueError,'attempt'):
            procedural.run(self.studio,self.project,plan)
        build.assert_not_called()

    def test_recover_verified_outputs_without_executing_or_duplicating_assets(self):
        plan = self.plan(verify_engine=True,render=False)
        with patch.object(procedural.factory,'build',side_effect=fake_build):original = procedural.run(self.studio,self.project,plan)
        with patch.object(procedural.factory,'build') as build:
            recovered = procedural.recover(self.studio,self.project,plan)
        self.assertEqual(recovered['job']['status'],'completed')
        self.assertEqual(recovered['job']['id'],original['job']['id'])
        self.assertEqual(len(self.studio.assets.records),3)
        self.assertEqual(recovered['verification']['state'],'passed')
        build.assert_not_called()

    def test_crash_before_publication_recovers_files_only_when_receipts_prove_completion(self):
        plan = self.plan()
        with patch.object(procedural.factory,'build',side_effect=fake_build),patch.object(self.studio.assets,'register',side_effect=KeyboardInterrupt('lost process')):
            with self.assertRaises(KeyboardInterrupt):procedural.run(self.studio,self.project,plan)
        with patch.object(procedural.factory,'build') as build:
            recovered = procedural.recover(self.studio,self.project,plan)
        self.assertEqual(recovered['job']['status'],'completed');self.assertEqual(len(self.studio.assets.records),4)
        build.assert_not_called()

    def test_failed_report_or_changed_file_cannot_publish_or_recover_as_success(self):
        plan = self.plan()
        def bad_build(*args,**kwargs):
            report = fake_build(*args,**kwargs);target = Path(args[2])
            (target / 'asset_LOD0.glb').write_bytes(b'changed after report')
            return report
        with patch.object(procedural.factory,'build',side_effect=bad_build):result = procedural.run(self.studio,self.project,plan)
        self.assertEqual(result['job']['status'],'failed');self.assertEqual(self.studio.assets.records,{})
        self.assertTrue((self.directory() / 'procedural/report.json').is_file())
        with patch.object(procedural.factory,'build') as build:recovered = procedural.recover(self.studio,self.project,plan)
        self.assertNotEqual(recovered['job']['status'],'completed');build.assert_not_called()

    def test_native_failure_retains_diagnostics_and_never_retries(self):
        plan = self.plan()
        def fail(*args,**kwargs):
            Path(args[2]).mkdir();(Path(args[2]) / 'blender-stderr.log').write_text('native failure')
            raise OSError('Blender failed')
        with patch.object(procedural.factory,'build',side_effect=fail):result = procedural.run(self.studio,self.project,plan)
        self.assertEqual(result['job']['status'],'failed')
        self.assertIn('procedural/blender-stderr.log',{a['path'] for a in result['artifacts']})
        with patch.object(procedural.factory,'build') as build:recovered = procedural.recover(self.studio,self.project,plan)
        self.assertEqual(recovered['job']['status'],'uncertain');build.assert_not_called()

    def test_repeated_recovery_preserves_a_recorded_native_failure(self):
        plan = self.plan()
        def native_failure(*args,**kwargs):
            fake_build(*args,**kwargs)
            raise OSError('native process failed after writing outputs')
        with patch.object(procedural.factory,'build',side_effect=native_failure):
            failed = procedural.run(self.studio,self.project,plan)
        self.assertEqual(failed['job']['status'],'failed')
        original = (self.directory() / 'procedural-job.json').read_bytes()
        with patch.object(procedural.factory,'build') as build:
            for _ in range(2):
                recovered = procedural.recover(self.studio,self.project,plan)
                self.assertEqual(recovered['job']['status'],'uncertain')
                self.assertEqual((self.directory() / 'procedural-job.json').read_bytes(),original)
        self.assertEqual(self.studio.assets.records,{});build.assert_not_called()

    def test_failed_godot_checks_keep_the_actual_native_log_paths(self):
        plan = self.plan(verify_engine=True)
        def fail(*args,**kwargs):
            fake_build(*args,**kwargs);base=Path(args[2])
            for name in ('godot-import-stderr.log','godot-probe-stdout.log','godot-probe-exit.json'):
                (base/name).write_text('retained failed Godot check')
            raise OSError('Godot probe failed')
        with patch.object(procedural.factory,'build',side_effect=fail):result=procedural.run(self.studio,self.project,plan)
        paths={a['path'] for a in result['artifacts']}
        self.assertEqual(result['job']['status'],'failed');self.assertEqual(self.studio.assets.records,{})
        for name in ('godot-import-stderr.log','godot-probe-stdout.log','godot-probe-exit.json'):
            self.assertIn('procedural/'+name,paths)

    def test_factory_gate_failure_is_visible_without_publishing_outputs(self):
        plan=self.plan()
        def reject(*args,**kwargs):
            report=fake_build(*args,**kwargs);report['state']='failed';report['failed_gates']=['khronos']
            next(g for g in report['gates'] if g['gate']=='khronos').update(passed=False,failures=['LOD1: malformed accessor'])
            (Path(args[2])/'report.json').write_text(json.dumps(report));return report
        with patch.object(procedural.factory,'build',side_effect=reject):result=procedural.run(self.studio,self.project,plan)
        self.assertEqual(result['job']['status'],'failed');self.assertIn('LOD1: malformed accessor',result['job']['message'])
        self.assertEqual(self.studio.assets.records,{})

    def test_linked_output_is_never_registered_even_with_a_matching_report_hash(self):
        plan=self.plan();external=self.root/'outside.glb'
        def redirect(*args,**kwargs):
            report=fake_build(*args,**kwargs);path=Path(args[2])/'asset_LOD0.glb'
            external.write_bytes(path.read_bytes());path.unlink()
            try:path.symlink_to(external)
            except OSError as exc:self.skipTest('Host cannot create symlinks: '+str(exc))
            return report
        with patch.object(procedural.factory,'build',side_effect=redirect):result=procedural.run(self.studio,self.project,plan)
        self.assertEqual(result['job']['status'],'failed');self.assertEqual(self.studio.assets.records,{})
        self.assertTrue(external.is_file())

    def test_broken_output_directory_link_is_retained_and_never_executed(self):
        plan=self.plan();outside=self.root/'must-not-be-created'
        try:(self.directory()/'procedural').symlink_to(outside,target_is_directory=True)
        except OSError as exc:self.skipTest('Host cannot create symlinks: '+str(exc))
        with patch.object(procedural.factory,'build') as build,self.assertRaisesRegex(ValueError,'already exists'):
            procedural.run(self.studio,self.project,plan)
        build.assert_not_called();self.assertFalse(outside.exists());self.assertTrue((self.directory()/'procedural').is_symlink())

    def test_changed_retained_source_pack_blocks_publication_without_rerunning(self):
        plan=self.plan()
        with patch.object(procedural.factory,'build',side_effect=fake_build),patch.object(self.studio.assets,'register',side_effect=KeyboardInterrupt('lost process')):
            with self.assertRaises(KeyboardInterrupt):procedural.run(self.studio,self.project,plan)
        pack=self.directory()/'export.zip'
        with zipfile.ZipFile(pack) as archive:files={name:archive.read(name) for name in archive.namelist()}
        files['procedural/asset_LOD0.glb']=b'changed'
        with zipfile.ZipFile(pack,'w') as archive:
            for name,content in files.items():archive.writestr(name,content)
        with patch.object(procedural.factory,'build') as build:result=procedural.recover(self.studio,self.project,plan)
        self.assertEqual(result['job']['status'],'uncertain');self.assertIn('source pack changed',result['job']['message'])
        self.assertEqual(self.studio.assets.records,{});build.assert_not_called()

    def test_tampered_plan_is_rejected_before_any_attempt(self):
        plan = self.plan();plan['intent']['params']['width'] = 9
        with self.assertRaisesRegex(ValueError,'fingerprint'):procedural.run(self.studio,self.project,plan)
        self.assertFalse(any(self.directory().iterdir()))


if __name__ == '__main__':unittest.main()

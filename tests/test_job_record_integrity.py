"""Recovery contains untrusted run records without changing their retained evidence."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_server import FakeStudio, GRAPH, PRESET, server


class JobRecordIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runs=self.root/'experiments/runs';self.runs.mkdir(parents=True)
        for name in ('presets','config','fake-comfy/input','workflows/api'):(self.root/name).mkdir(parents=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}),encoding='utf-8')
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}),encoding='utf-8')
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH),encoding='utf-8')
        self.start=patch.object(threading.Thread,'start',lambda *_:None);self.start.start();self.addCleanup(self.start.stop)
        self.write_record('healthy',status='completed');self.write_record('queued')
        self.healthy_before=self.snapshot(self.runs/'healthy')

    def record(self, identifier, **changes):
        data={'id':identifier,'status':'queued','preset_id':'demo','preset_name':'Demo','controls':{},
              'batch_count':1,'graph_path':'workflows/api/demo-api.json','created_at':1,
              'prompt_ids':[],'submissions':[],'outputs':[]}
        data.update(changes);return data

    def write_record(self, folder, **changes):
        directory=self.runs/folder;directory.mkdir(exist_ok=True)
        (directory/'state.json').write_text(json.dumps(self.record(folder,**changes)),encoding='utf-8')
        (directory/'workflow.json').write_text(json.dumps(GRAPH),encoding='utf-8')
        (directory/'recipe.json').write_bytes(b'{"retained":"original recipe"}')
        return directory

    @staticmethod
    def snapshot(directory):return {p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob('*') if p.is_file()}

    def recover_bad(self, directory):
        before=self.snapshot(directory)
        restored=FakeStudio(self.root,[]);job=restored.jobs[directory.name];public=restored.public(job)
        self.assertIn('record_error',job);self.assertEqual(job['id'],directory.name)
        self.assertEqual(public['status'],'uncertain');self.assertEqual(public['run_path'],str(directory))
        self.assertIn('Nothing was resubmitted.',public['message'])
        self.assertEqual(restored.jobs['healthy']['status'],'completed')
        self.assertEqual(restored.jobs['healthy']['graph'],GRAPH)
        self.assertEqual(self.snapshot(self.runs/'healthy'),self.healthy_before)
        self.assertEqual(restored.jobs['queued']['status'],'not_submitted')
        self.assertEqual(restored.requests,[]);self.assertEqual(restored.queue.qsize(),0)
        for key in ('never_submitted','can_resume_tracking','can_stop_tracking','can_abandon','can_cancel'):
            self.assertFalse(public[key],key)
        with self.assertRaises(server.StudioError):restored._save(job)
        with self.assertRaises(server.StudioError):restored.resume_job(job['id'])
        self.assertEqual(self.snapshot(directory),before)
        return job

    def test_traversal_cannot_overwrite_a_sibling_of_runs(self):
        victim=self.root/'experiments/victim';victim.mkdir()
        for name in ('recipe.json','workflow.json','state.json'):(victim/name).write_bytes(b'untouched victim')
        before=self.snapshot(victim)
        try:self.recover_bad(self.write_record('bad',id='../victim'))
        finally:self.assertEqual(self.snapshot(victim),before)

    def test_mismatched_identity_cannot_overwrite_or_hide_another_run(self):
        self.recover_bad(self.write_record('bad',id='healthy'))

    def test_two_records_claiming_the_same_identity_are_both_refused(self):
        first=self.write_record('first',id='healthy');second=self.write_record('second',id='healthy')
        self.recover_bad(first);self.recover_bad(second)

    def test_invalid_identity_types_and_path_components_are_contained(self):
        for identifier in (['x'],{'x':1},1,True,None,'','.','..','a/../b','a\\b','/absolute','C:\\absolute','C:relative','bad\x00id','bad:stream','healthy.'):
            with self.subTest(identifier=identifier):self.recover_bad(self.write_record('bad',id=identifier))

    def test_missing_required_fields_are_contained_before_any_write(self):
        for key in ('id','preset_id','controls','batch_count','graph_path','created_at','status'):
            with self.subTest(key=key):
                directory=self.write_record('bad');data=self.record('bad');del data[key]
                (directory/'state.json').write_text(json.dumps(data),encoding='utf-8');self.recover_bad(directory)

    def test_bad_field_types_are_contained_before_any_write(self):
        for key,value in (('status',[]),('preset_id',{}),('controls',[]),('batch_count',True),('batch_count',-1),
                          ('created_at',{}),('created_at',float('inf')),('created_at',10**1000),('graph_path',[]),('outputs',None),
                          ('outputs',[1]),('submissions',[None]),('prompt_ids',[[]]),('tracking_disposition',[]),('comfy_root',[])):
            with self.subTest(key=key,value=value):self.recover_bad(self.write_record('bad',**{key:value}))

    def test_deep_state_and_workflow_json_are_contained(self):
        for filename in ('state.json','workflow.json'):
            for depth in (200,20000):
                with self.subTest(filename=filename,depth=depth):
                    directory=self.write_record('bad')
                    prefix=json.dumps(self.record('bad'))[:-1]+',"nested":' if filename=='state.json' else '{"nested":'
                    (directory/filename).write_text(prefix+'['*depth+'0'+']'*depth+'}',encoding='utf-8')
                    self.recover_bad(directory)

    def test_oversize_state_and_workflow_json_are_contained(self):
        for filename in ('state.json','workflow.json'):
            with self.subTest(filename=filename):
                directory=self.write_record('bad')
                payload=json.dumps(self.record('bad') if filename=='state.json' else GRAPH).encode('utf-8')
                (directory/filename).write_bytes(payload+b' '*(server.MAX_JOB_RECORD_BYTES+1))
                job=self.recover_bad(directory);self.assertIn('size limit',job['record_error'])

    def test_bounded_read_refuses_growth_after_stat(self):
        directory=self.write_record('bad');path=directory/'state.json'
        data=self.record('bad',message='x'*2048);path.write_text(json.dumps(data),encoding='utf-8')
        stat=Path.stat
        def small_stat(candidate,*args,**kwargs):
            result=stat(candidate,*args,**kwargs)
            if candidate==path:
                from types import SimpleNamespace
                return SimpleNamespace(st_size=1,st_mode=result.st_mode)
            return result
        with patch.object(server,'MAX_JOB_RECORD_BYTES',1024),patch.object(Path,'stat',small_stat):self.recover_bad(directory)

    def test_malformed_workflow_keeps_known_prompt_ids_for_inspection(self):
        directory=self.write_record('bad',status='running',prompt_ids=['known-prompt'],submissions=[{'prompt_id':'known-prompt','status':'observing'}])
        (directory/'workflow.json').write_bytes(b'{broken')
        self.assertIn('Known ComfyUI prompt IDs: known-prompt',self.recover_bad(directory)['message'])

    def test_normalization_write_failure_still_stops_startup(self):
        # Only reading and validation are contained; a failed restart write must not be masked as unreadable (test_mixed_batch).
        self.write_record('bad')
        def fail(studio,job,**kwargs):raise OSError('state file locked')
        with patch.object(server.Studio,'_save',fail),self.assertRaisesRegex(OSError,'state file locked'):FakeStudio(self.root,[])

    def test_malformed_native_output_is_contained_before_indexing(self):
        for output in ({},{'native_path':[]}):
            with self.subTest(output=output):
                self.recover_bad(self.write_record('bad',status='completed',operation='native.voice-baseline.v1',outputs=[output]))

    def test_save_rejects_unsafe_id_before_any_write(self):
        studio=FakeStudio(self.root,[])
        victim=self.root/'experiments/victim';victim.mkdir()
        for durable in (False,True):
            for identifier in ('../victim','healthy/../healthy','a\\b','/absolute','C:relative','bad:stream','..','.',[],None,''):
                with self.subTest(identifier=identifier,durable=durable):
                    before=self.snapshot(self.runs);job=self.record(identifier);job['graph']=copy.deepcopy(GRAPH)
                    with patch.object(studio,'_write_json_atomic',wraps=studio._write_json_atomic) as write, \
                         patch.object(studio,'_write_observation_state',wraps=studio._write_observation_state) as publish:
                        with self.assertRaises(server.StudioError):studio._save(job,durable=durable)
                        write.assert_not_called();publish.assert_not_called()
                    self.assertEqual(self.snapshot(self.runs),before);self.assertEqual(self.snapshot(victim),{})

    def test_healthy_terminal_outcomes_and_recipes_are_preserved(self):
        for status in ('completed','failed','cancelled','partial','abandoned','not_submitted'):
            self.write_record(status,status=status)
        before={status:self.snapshot(self.runs/status) for status in ('completed','failed','cancelled','partial','abandoned','not_submitted')}
        studio=FakeStudio(self.root,[])
        for status,files in before.items():
            self.assertEqual(studio.jobs[status]['status'],status);self.assertEqual(self.snapshot(self.runs/status),files)
        self.assertEqual(studio.requests,[]);self.assertEqual(studio.queue.qsize(),0)

    def test_native_zero_batch_job_is_not_malformed(self):
        directory=self.write_record('native',operation='native.voice-baseline.v1',batch_count=0,status='completed')
        before=self.snapshot(directory);studio=FakeStudio(self.root,[])
        self.assertNotIn('record_error',studio.jobs['native']);self.assertEqual(studio.jobs['native']['status'],'completed')
        self.assertEqual(self.snapshot(directory),before)


if __name__=='__main__':unittest.main()

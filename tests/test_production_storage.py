"""Real SQLite/filesystem failure contracts with inert Studio/editor boundaries."""
from contextlib import closing
import copy
import json
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import production
import project_storage


class StorageStudio:
    def require_worker(self):
        from test_server import server
        return server.Studio.require_worker(self)
    def require_worker_observation(self):
        from test_server import server
        return server.Studio.require_worker_observation(self)
    def __init__(self, root):
        self.root=Path(root);self.experiments=self.root/'experiments';self.experiments.mkdir(exist_ok=True)
        self.template=self.root/'template.json';self.template.write_text('{}')
        self.comfy_root=self.root/'comfy';self.comfy_url='http://127.0.0.1:8188'
        self.lock=threading.RLock();self.jobs={};self.config={};self.queue=queue.Queue()
        self.assets=SimpleNamespace(media=self.root, get=lambda _: {'id':'asset','trashed_at':None,'bytes':1,
                                   'job_id':None,'filename':'asset.png','sha256':'a'*64}, file=lambda _:self.root/'asset.png')
        self.validate_graph=Mock();self.check_production_bundle=Mock();self._run=Mock();self._resume=Mock();self._save=Mock()
        self.create_job=Mock();self.public=copy.deepcopy;self.tracking_stop_tokens=lambda _: []
    def prepare(self, request):
        controls=copy.deepcopy(request.get('controls',{}))
        return {'seed':['1','seed']}, {'1':{'class_type':'Fixture','inputs':controls}}, self.template, controls, 1
    def production_preflight(self, *args):return {'comfy_url':self.comfy_url}
    @staticmethod
    def _write_json_atomic(path, value):
        # Do not create a missing project parent: the publication contract owns it.
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as stream:
            json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno());temporary=Path(stream.name)
        temporary.replace(path)


def lab_for(studio):
    # Peer initialization is unrelated to project admission; SQLite/Production are real.
    with patch('review_desk.ReviewDesk'),patch('av_projects.AVProjects'):
        return production.Production(studio)


def intent(**extra):
    return dict({'name':'Storage fixture','recipe':{'preset_id':'fixture','controls':{}},
                 'axis':'seed','values':[1,2],'max_generations':4}, **extra)


class ProductionStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.studio=StorageStudio(self.root);self.lab=lab_for(self.studio)
    def counts(self):
        with self.lab.connect() as db:
            return tuple(db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('projects','budgets'))
    def create(self, kind='comparison', **extra):
        if kind=='comparison':return self.lab.create(intent(**extra))
        if kind=='articulated':
            with patch('articulated.prepare',return_value={'intent':{'name':'Chest'},'options':{}}):
                return self.lab.articulated({})
        with patch('native_exports.NativeExports') as exporter,patch('production.shutil.disk_usage',return_value=SimpleNamespace(free=100*1024**3)):
            exporter.return_value._asset_records.return_value=([],None)
            exporter.return_value._images.return_value=([],None,[])
            exporter.return_value._options.return_value={'clip':'fixture'}
            return self.lab.native({'kind':'ora','ids':['asset']})
    def plan_path(self, project):return self.lab.root/project['id']/'plan.json'
    def inert(self):
        self.assertEqual(self.studio.queue.qsize(),0);self.assertEqual(self.studio.jobs,{})
        self.studio._run.assert_not_called();self.studio._resume.assert_not_called()
    def assert_blocked(self, project, method='start'):
        before=copy.deepcopy(self.lab.get(project['id'])['budget']);queued=self.studio.queue.qsize()
        with self.assertRaisesRegex(ValueError,'Project|Retained project'):
            getattr(self.lab,method)(project['id'])
        self.assertEqual(self.lab.get(project['id'])['budget'],before)
        self.assertEqual(self.studio.queue.qsize(),queued);self.studio._run.assert_not_called()

    def test_each_creator_publishes_matching_plan_without_queueing(self):
        for kind in project_storage.KINDS:
            with self.subTest(kind=kind):
                p=self.create(kind);saved=json.loads(self.plan_path(p).read_bytes())
                self.assertEqual(saved,self.lab.get(p['id'],full=True)['plan'])
                self.assertFalse((self.plan_path(p).parent/project_storage.MARKER).exists())
                self.assertEqual(p['state']['status'],'planned');self.assertEqual(p['budget']['reserved'],0)
        self.assertEqual(self.counts(),(3,3));self.inert()

    def test_mkdir_failure_leaves_no_startable_rows_or_budget(self):
        original=Path.mkdir
        def fail(path,*a,**kw):
            if path.parent==self.lab.root:raise PermissionError('injected mkdir')
            return original(path,*a,**kw)
        for kind in project_storage.KINDS:
            with self.subTest(kind=kind),patch.object(Path,'mkdir',fail):
                with self.assertRaisesRegex(PermissionError,'mkdir'):self.create(kind)
                self.assertEqual(self.counts(),(0,0));self.assertEqual(self.lab.list(),[])
        self.inert()

    def test_plan_write_failure_retains_marker_but_no_rows(self):
        for kind in project_storage.KINDS:
            with self.subTest(kind=kind),patch.object(self.studio,'_write_json_atomic',side_effect=OSError('plan write')):
                with self.assertRaisesRegex(OSError,'plan write'):self.create(kind)
                self.assertEqual(self.counts(),(0,0))
        self.assertEqual(len(list(self.lab.root.glob('*/.incomplete-create'))),3);self.inert()

    def test_partial_plan_write_does_not_publish_a_project(self):
        def fail(path,value):path.write_bytes(b'{');raise OSError('truncated write')
        with patch.object(self.studio,'_write_json_atomic',side_effect=fail):
            with self.assertRaises(OSError):self.create()
        self.assertEqual(self.counts(),(0,0));self.assertEqual(next(self.lab.root.glob('*/plan.json')).read_bytes(),b'{')
        self.inert()

    def test_readback_disagreement_rolls_back(self):
        with patch.object(self.studio,'_write_json_atomic',side_effect=lambda p,v:p.write_text('{}')):
            with self.assertRaisesRegex(ValueError,'differs'):self.create()
        self.assertEqual(self.counts(),(0,0));self.inert()

    def test_insert_failure_preserves_files_and_rolls_back_all_new_rows(self):
        with self.lab.connect() as db:
            db.execute("CREATE TRIGGER reject_project BEFORE INSERT ON projects BEGIN SELECT RAISE(ABORT,'injected insert'); END")
        for kind in project_storage.KINDS:
            with self.subTest(kind=kind),self.assertRaisesRegex(sqlite3.IntegrityError,'injected insert'):self.create(kind)
        self.assertEqual(self.counts(),(0,0));self.assertEqual(len(list(self.lab.root.glob('*/plan.json'))),3)
        self.inert()

    def test_real_commit_failure_keeps_marker_and_rolls_back_budget(self):
        with self.lab.connect() as db:
            db.executescript("""CREATE TABLE fail_commit (project_id TEXT REFERENCES projects(id) DEFERRABLE INITIALLY DEFERRED);
                CREATE TRIGGER deferred_fault AFTER INSERT ON projects BEGIN INSERT INTO fail_commit VALUES ('missing'); END;""")
        for kind in project_storage.KINDS:
            with self.subTest(kind=kind),self.assertRaises(sqlite3.IntegrityError):self.create(kind)
        self.assertEqual(self.counts(),(0,0));self.assertEqual(len(list(self.lab.root.glob('*/.incomplete-create'))),3)
        self.inert()

    def test_completion_failure_cannot_authorize_start(self):
        original=Path.unlink
        def fail(path,*a,**kw):
            if path.name==project_storage.MARKER:raise OSError('marker cleanup')
            return original(path,*a,**kw)
        for kind in project_storage.KINDS:
            with self.subTest(kind=kind),patch.object(Path,'unlink',fail):
                with self.assertRaisesRegex(OSError,'marker cleanup'):self.create(kind)
        for p in self.lab.list():self.assert_blocked(p)
        self.assertEqual(self.counts(),(3,3));self.inert()

    def test_second_connection_never_sees_row_before_plan_readback(self):
        original=self.studio._write_json_atomic;observed=[]
        def inspect(path,plan):
            with closing(sqlite3.connect(self.lab.db)) as db:
                observed.append(db.execute('SELECT count(*) FROM projects').fetchone()[0])
                self.assertEqual(db.execute('SELECT count(*) FROM budgets').fetchone()[0],0)
            original(path,plan)
        with patch.object(self.studio,'_write_json_atomic',side_effect=inspect):p=self.create()
        self.assertEqual(observed,[0]);self.assertEqual(self.counts(),(1,1));self.inert()

    def test_directory_collision_preserves_other_attempt(self):
        identifier='b'*32;directory=self.lab.root/identifier;directory.mkdir();(directory/'keep').write_bytes(b'original')
        with patch('production.uuid.uuid4',return_value=SimpleNamespace(hex=identifier)):
            with self.assertRaises(FileExistsError):self.create()
        self.assertEqual((directory/'keep').read_bytes(),b'original');self.assertEqual(self.counts(),(0,0));self.inert()

    def test_duplicate_deterministic_import_preserves_plan_and_shared_budget(self):
        kwargs={'root_override':'study:fixture','allowance_override':4,'identifier_override':'c'*32}
        p=self.lab._create(intent(),**kwargs);original=self.plan_path(p).read_bytes();self.lab.start(p['id'])
        with self.assertRaises(sqlite3.IntegrityError):self.lab._create(intent(),**kwargs)
        self.assertEqual(self.plan_path(p).read_bytes(),original);self.assertEqual(self.counts(),(1,1))
        self.assertEqual(self.lab.get(p['id'])['budget'],{'allowance':4,'reserved':2})

    def test_failed_child_preserves_parent_reservations(self):
        parent=self.create();self.lab.start(parent['id']);before=self.lab.get(parent['id'])['budget']
        with patch.object(self.studio,'_write_json_atomic',side_effect=OSError('child write')):
            with self.assertRaises(OSError):self.create(parent_project=parent['id'])
        self.assertEqual(self.counts(),(1,1));self.assertEqual(self.lab.get(parent['id'])['budget'],before)
        self.assertEqual(self.studio.queue.qsize(),1);self.studio._run.assert_not_called()

    def test_invalid_parent_creates_neither_directory_nor_budget(self):
        with self.assertRaisesRegex(ValueError,'Unknown experiment'):self.create(parent_project='e'*32)
        self.assertEqual(list(self.lab.root.glob('*/plan.json')),[]);self.assertEqual(self.counts(),(0,0));self.inert()

    def test_startup_records_legacy_orphans_without_changing_execution_evidence(self):
        for kind in project_storage.KINDS:
            p=self.create(kind);self.lab._mutate(p['id'],status='uncertain',attempts={'0':{'job_id':'known','prompt_ids':['retained']}},
                                              review={'status':'needs_work','notes':'keep'},artifacts=[{'path':'retained.png'}])
            shutil.rmtree(self.plan_path(p).parent)
        before={p['id']:self.lab._get(p['id']) for p in self.lab.list()}
        restarted=lab_for(self.studio)
        for p in restarted.list():
            self.assertIn('storage_issue',p['state']);self.assertIn('Startup storage check',p['state']['message'])
            old=before[p['id']]['state'];new=restarted._get(p['id'])['state'];new.pop('storage_issue')
            self.assertEqual(new,old);self.assertFalse(self.plan_path(p).parent.exists())
        self.lab=restarted
        for p in self.lab.list():self.assert_blocked(p,'resume')
        self.inert()

    def test_startup_preserves_terminal_review_state_for_missing_plans(self):
        p=self.create();self.lab._mutate(p['id'],status='reviewed',review={'status':'selected','asset_id':'keep'})
        self.plan_path(p).unlink();self.lab=lab_for(self.studio)
        p=self.lab.get(p['id']);self.assertEqual(p['state']['status'],'reviewed')
        self.assertEqual(p['state']['review'],{'status':'selected','asset_id':'keep'});self.assertIn('storage_issue',p['state']);self.inert()

    def test_missing_changed_or_malformed_plan_blocks_start_before_reservation(self):
        for mode in ('missing','changed','truncated','oversized','fingerprint'):
            with self.subTest(mode=mode):
                p=self.create();target=self.plan_path(p)
                if mode=='missing':target.unlink()
                elif mode=='truncated':target.write_bytes(b'{')
                elif mode=='oversized':target.write_bytes(b' '*(project_storage.PLAN_LIMIT+1))
                else:
                    value=json.loads(target.read_bytes());value['name']='changed'
                    target.write_text(json.dumps(value))
                    if mode=='fingerprint':
                        with self.lab.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(value),p['id']))
                self.assert_blocked(p)
        self.inert()

    def test_resume_storage_refusal_preserves_authorizations_and_reservations(self):
        for state in ('uncertain','interrupted','stopped'):
            p=self.create();self.lab.start(p['id']);self.lab._mutate(p['id'],status=state,tracking_stop_authorizations=['keep'])
            self.plan_path(p).unlink();before=self.lab._get(p['id'])
            self.assert_blocked(p,'resume');self.assertEqual(self.lab._get(p['id']),before)

    def test_worker_rechecks_after_queueing_for_every_affected_kind(self):
        for kind in project_storage.KINDS:
            p=self.create(kind);self.lab.start(p['id']);self.plan_path(p).unlink()
            with patch.object(self.lab,'_run_native') as native,patch.object(self.lab,'_run_articulated') as articulated:
                self.assert_blocked(p,'run');native.assert_not_called();articulated.assert_not_called()
        self.studio.create_job.assert_not_called()

    def test_worker_rechecks_after_late_preparation_before_job_creation(self):
        p=self.create();self.lab.start(p['id']);prepare=self.studio.prepare
        def disappear(request):
            result=prepare(request);self.plan_path(p).unlink();return result
        with patch.object(self.studio,'prepare',side_effect=disappear):self.assert_blocked(p,'run')
        self.studio.create_job.assert_not_called();self.assertEqual(self.studio.jobs,{})

    def test_worker_rechecks_existing_queued_job_just_before_dispatch(self):
        p=self.create();self.lab.start(p['id'])
        identifier=str(production.uuid.uuid5(production.uuid.NAMESPACE_URL,f"asset-studio:{p['id']}:stage:0"))
        job={'id':identifier,'status':'queued','prompt_ids':[]};self.studio.jobs[identifier]=job
        attempt=self.lab._attempt
        def disappear(*args,**kwargs):
            attempt(*args,**kwargs)
            if 'started_at' in kwargs:self.plan_path(p).unlink()
        with patch.object(self.lab,'_attempt',side_effect=disappear):self.assert_blocked(p,'run')
        self.assertEqual(job,{'id':identifier,'status':'queued','prompt_ids':[]})

    def test_read_only_inspection_accepts_whitespace_not_a_different_plan(self):
        p=self.create();plan=self.lab.get(p['id'],full=True)['plan']
        self.plan_path(p).write_bytes(json.dumps(plan,indent=4).replace('\n','\r\n').encode())
        project_storage.require(self.lab.root,p['id'],plan);self.inert()

    def test_explicit_file_restore_never_auto_starts_or_resets_budget(self):
        p=self.create();original=self.plan_path(p).read_bytes();self.plan_path(p).unlink()
        self.lab=lab_for(self.studio);self.assertIn('storage_issue',self.lab.get(p['id'])['state'])
        self.plan_path(p).write_bytes(original);self.lab=lab_for(self.studio)
        self.assertNotIn('storage_issue',self.lab.get(p['id'])['state']);self.inert()
        self.lab.start(p['id']);self.assertEqual(self.studio.queue.qsize(),1)
        self.assertEqual(self.lab.get(p['id'])['budget']['reserved'],2)

    def test_symlinked_directory_or_plan_is_not_admitted(self):
        for component in ('directory','plan'):
            with self.subTest(component=component):
                p=self.create();target=self.plan_path(p);other=self.root/('other-'+component)
                if component=='directory':
                    target.parent.rename(other);target=target.parent
                else:target.rename(other)
                try:target.symlink_to(other,target_is_directory=component=='directory')
                except OSError:self.skipTest('symlink privilege unavailable')
                self.assert_blocked(p);self.assertTrue(other.exists())
        self.inert()

    def test_large_new_plan_is_rejected_before_mkdir(self):
        p={'kind':'comparison','name':'x'*project_storage.PLAN_LIMIT,'sha256':'a'*64}
        with self.assertRaisesRegex(ValueError,'publication limit'):
            project_storage.materialize(self.lab.root,'a'*32,p,self.studio._write_json_atomic)
        self.assertFalse((self.lab.root/('a'*32)).exists());self.inert()

    def test_other_lanes_keep_their_separate_storage_contract(self):
        for kind in ('av','voice'):
            project_storage.require(self.lab.root,'a'*32,{'kind':kind})
        self.inert()

    def test_abrupt_exit_before_commit_keeps_files_without_visible_rows(self):
        self.crash_case('before',23)
        self.assertEqual(self.counts(),(0,0));self.assertEqual(len(list(self.lab.root.glob('*/.incomplete-create'))),1)
        self.lab=lab_for(self.studio);self.assertEqual(self.lab.list(),[]);self.inert()

    def test_abrupt_exit_after_commit_is_diagnosable_and_not_startable(self):
        self.crash_case('after',24);self.assertEqual(self.counts(),(1,1))
        self.lab=lab_for(self.studio);p=self.lab.list()[0]
        self.assertIn('storage_issue',p['state']);self.assert_blocked(p);self.inert()

    def crash_case(self,boundary,code):
        # A real child exits at the transaction boundary; no model/tool/queue is used.
        script="""
import os, sys
from pathlib import Path
from unittest.mock import patch
from test_production_storage import StorageStudio, lab_for, intent, production, project_storage
studio=StorageStudio(Path(sys.argv[1]));lab=lab_for(studio)
if sys.argv[2]=='before':
    original=lab._insert_materialized
    def crash(*args):original(*args);os._exit(23)
    with patch.object(lab,'_insert_materialized',side_effect=crash):lab.create(intent())
else:
    with patch.object(project_storage,'complete',side_effect=lambda *a:os._exit(24)):lab.create(intent())
"""
        env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join([str(Path(__file__).parent),str(Path(__file__).parents[1]/'app'),env.get('PYTHONPATH','')])
        result=subprocess.run([sys.executable,'-c',script,str(self.root),boundary],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,code,result.stderr)


if __name__=='__main__':unittest.main()

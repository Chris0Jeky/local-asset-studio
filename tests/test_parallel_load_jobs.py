"""#1788: Studio start reads run records on a bounded pool, then applies them in path order; the result must equal the serial loader result."""
import copy
import hashlib
import json
import shutil
import threading
import unittest
from collections import Counter
from unittest.mock import patch

import test_server
from test_server import server

privacy_scope, submission_evidence, job_cancel = server.privacy_scope, server.submission_evidence, server.job_cancel


def reference_load_jobs(self):
    """The loader as it stood before #1788 (serial; the alias guard resolves per file), kept verbatim as the oracle."""
    private_runs=self._private_directory('runs')
    paths=[*self.runs.glob('*/state.json'),*private_runs.glob('*/state.json')]
    duplicates={name for name,count in Counter(p.parent.name for p in paths).items() if count>1}
    for state_path in paths:
        classification='private' if state_path.parent.parent==private_runs or state_path.parent.name in duplicates else 'regular'
        data = {}; path = state_path
        try:
            if state_path.parent.name in duplicates:raise ValueError('Duplicate job ID in regular and private storage; inspect both retained folders')
            for path in (state_path, state_path.parent / "workflow.json"):
                if state_path.parent.is_symlink() or path.is_symlink() or path.resolve().parent != state_path.parent.resolve():
                    classification='private'
                    raise ValueError('Retained run records must not redirect through filesystem aliases')
                record = self._read_job_record(path)
                if path == state_path:
                    data = record
                    if privacy_scope.normalize(data.get('privacy','regular'))!=classification:raise ValueError('Job privacy does not match its run folder')
                    directory = self._job_directory(data.get("id"),classification)
                    if data['id'] != state_path.parent.name or directory != state_path.parent: raise ValueError("Job ID does not match its run folder")
                    if data['id'] in self.jobs: raise ValueError("Duplicate job ID")
                else: graph = record
            path = state_path
            self._validate_job_record(data)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError) as exc:
            if data.get('privacy','regular') != 'regular': classification='private'
            reason = f"{path.name}: {exc}"; known = data.get("prompt_ids")
            ids = [i for i in known if isinstance(i, str)] if isinstance(known, list) else []
            self.jobs[state_path.parent.name] = {"id": state_path.parent.name, "status": "uncertain", "created_at": 0,
                **({'privacy':'private'} if classification=='private' else {}),
                "preset_name": "Unreadable run record", "controls": {}, "outputs": [], "run_path": str(state_path.parent),
                "record_error": reason, "message": f"The run record could not be read ({reason}). Nothing was resubmitted." + (f" Known ComfyUI prompt IDs: {', '.join(ids[:8])}." if ids else "") + f" Inspect experiments/{state_path.parent.relative_to(self.experiments).as_posix()}/ before deleting it."}
            continue
        defaults = {key: value for key, value in (('comfy_root', str(self.comfy_root)), ('comfy_url', self.comfy_url)) if key not in data}
        state_written = False
        data["graph"] = graph
        data.setdefault('comfy_root', str(self.comfy_root))
        data.setdefault('comfy_url', self.comfy_url)
        if data.get("status") in ("queued", "waiting", "submitting", "running", "uncertain"):
            if submission_evidence.never_submitted(data):
                data["status"] = "not_submitted"
                data["message"] = "Restarted before submission. Resume the owning experiment explicitly, or retain the recipe and abandon this local job. Nothing was submitted on restart."
            else:
                data["status"] = "uncertain"
                data["message"] = "Restarted while remote job state was unknown; use Resume observation for known prompt IDs. It was not resubmitted."
            if "pending_submission" in data and data.get("prompt_ids"):
                data["message"] = "Restarted with a mixed batch; check known batch receipts or explicitly record a local disposition. The unknown submission was not repeated."
                self._write_json_atomic(state_path, {k: v for k, v in data.items() if k != "graph"})
            else:
                self._save(data)
            state_written = True
        if job_cancel.reconcile_restart(data, state_path.parent):
            self._write_json_atomic(state_path, {k: v for k, v in data.items() if k != "graph"})
            state_written = True
        fields = (['tracking_disposition'] if self._tracking_stopped(data) else [])
        if data.get('status') == 'abandoned' and isinstance(data.get('abandonment'), dict): fields.append('abandonment')
        if fields:
            retained = {k: v for k, v in data.items() if k != 'graph'}
            if not state_written:
                for name in defaults: retained.pop(name, None)
            for field in fields: self._loaded_operator_dispositions[(data['id'], field)] = copy.deepcopy(retained)
        self.jobs[data["id"]] = data


def record(job_id, **extra):
    return {'id': job_id, 'status': 'completed', 'created_at': 1.5, 'preset_id': 'demo', 'preset_name': 'Demo', 'controls': {}, 'batch_count': 1,
            'prompt_ids': [], 'submissions': [], 'outputs': [], 'graph_path': 'workflows/api/demo-api.json', 'parent_assets': [], 'references': [], **extra}


class ParallelLoadJobsTests(unittest.TestCase):
    setUp = test_server.ServerTests.setUp
    tearDown = test_server.ServerTests.tearDown
    studio = test_server.ServerTests.studio

    def write(self, root, name, state=None, workflow=None, raw=None):
        folder = root / name; folder.mkdir(parents=True)
        (folder / 'state.json').write_bytes(raw if raw is not None else json.dumps(state).encode())
        if workflow is not False: (folder / 'workflow.json').write_text(workflow if isinstance(workflow, str) else json.dumps(workflow or test_server.GRAPH))
        return folder

    def populate(self, studio):
        """Fresh run folders: good, restart-rewritten, malformed, oversized, deep, aliased, duplicate and privacy-mismatch."""
        regular, private = studio.runs, studio._private_directory('runs')
        for root in (regular, private, studio.experiments / 'alias-target'):
            shutil.rmtree(root, ignore_errors=True)
        regular.mkdir(parents=True); private.mkdir(parents=True)
        for number in range(12): self.write(regular, f'good-{number:02d}', record(f'good-{number:02d}'))
        self.write(regular, 'queued', record('queued', status='queued'))
        self.write(regular, 'queued-pending', record('queued-pending', status='running', prompt_ids=['p1'], pending_submission={'member': 1}))
        self.write(regular, 'bad-json', raw=b'{not json')
        self.write(regular, 'not-object', raw=b'[1, 2]')
        self.write(regular, 'oversized', raw=b'{"x": "' + b'a' * (server.MAX_JOB_RECORD_BYTES + 1) + b'"}')
        depth = server.MAX_JOB_RECORD_DEPTH + 5
        self.write(regular, 'too-deep', raw=b'{"a": ' * depth + b'1' + b'}' * depth)
        self.write(regular, 'no-workflow', record('no-workflow'), workflow=False)
        self.write(regular, 'bad-workflow', record('bad-workflow'), workflow='[')
        self.write(regular, 'wrong-id', record('someone-else'))
        self.write(regular, 'missing-fields', {**record('missing-fields'), 'preset_id': None})
        self.write(regular, 'private-in-regular', record('private-in-regular', privacy='private'))
        self.write(regular, 'dup', record('dup')); self.write(private, 'dup', record('dup', privacy='private'))
        self.write(private, 'private-good', record('private-good', privacy='private'))
        self.write(private, 'private-regular-mismatch', record('private-regular-mismatch'))
        self.write(private, 'private-bad', raw=b'nope')
        target = self.write(studio.experiments, 'alias-target', record('alias-dir')); folder = self.write(regular, 'alias-file', record('alias-file'), workflow=False)
        try: (regular / 'alias-dir').symlink_to(target, target_is_directory=True); (folder / 'workflow.json').symlink_to(target / 'workflow.json'); self.pretend = ()
        except (OSError, NotImplementedError):   # no symlink privilege (default Windows): plain copies that is_symlink() is told to report as aliases
            shutil.copytree(target, regular / 'alias-dir'); shutil.copy(target / 'workflow.json', folder / 'workflow.json')
            self.pretend = (regular / 'alias-dir', folder / 'workflow.json')

    @staticmethod
    def snapshot(studio):
        files = {str(p.relative_to(studio.experiments)): hashlib.sha1(p.read_bytes()).hexdigest() for root in (studio.runs, studio._private_directory('runs')) for p in sorted(root.rglob('*')) if p.is_file()}
        return json.dumps(studio.jobs, sort_keys=True, default=str), list(studio.jobs), repr(sorted(studio._loaded_operator_dispositions.items(), key=str)), files

    def load(self, studio, workers):
        studio.jobs = {}; studio._loaded_operator_dispositions = {}; self.populate(studio)
        real = server.Path.is_symlink
        with patch.object(server.Path, 'is_symlink', lambda path: path in self.pretend or real(path)):
            if workers is None: reference_load_jobs(studio)
            else: studio.LOAD_WORKERS = workers; studio._load_jobs()
        return self.snapshot(studio)

    def test_pool_loads_exactly_what_the_serial_loader_loaded(self):
        studio = self.studio(); self.start.stop()   # Studio start stubs its worker thread; the pool needs real threads
        reference = self.load(studio, None)
        errors = {job['id']: job['record_error'] for job in studio.jobs.values() if 'record_error' in job}
        for expected in ('size limit', 'nesting limit', 'Expecting', 'Duplicate job ID in regular and private storage', 'privacy does not match', 'does not match its run folder', 'Invalid or missing preset_id', 'workflow.json'):
            self.assertTrue(any(expected in error for error in errors.values()), expected)
        self.assertEqual(sum('redirect through filesystem aliases' in error for error in errors.values()), 2)
        self.assertEqual(studio.jobs['queued']['status'], 'not_submitted'); self.assertEqual(studio.jobs['queued-pending']['status'], 'uncertain')
        self.assertEqual(json.loads((studio.runs / 'queued' / 'state.json').read_text())['status'], 'not_submitted')
        self.assertEqual(self.load(studio, 1), reference)
        threads = set(); read = server.Studio._read_job_record
        def spy(path): threads.add(threading.get_ident()); return read(path)
        with patch.object(server.Studio, '_read_job_record', staticmethod(spy)), patch.object(server, 'ThreadPoolExecutor', wraps=server.ThreadPoolExecutor) as pool:
            self.assertEqual(self.load(studio, 8), reference)
        pool.assert_called_once_with(8); self.assertNotIn(threading.get_ident(), threads)

    def test_one_worker_loads_inline(self):
        studio = self.studio(); self.start.stop(); studio.LOAD_WORKERS = 1
        with patch.object(server, 'ThreadPoolExecutor') as pool: self.populate(studio); studio.jobs = {}; studio._load_jobs()
        pool.assert_not_called()

    def test_stubbed_thread_start_loads_inline(self):
        studio = self.studio()   # setUp still stubs Thread.start: a pool would wait forever on workers that never start
        with patch.object(server, 'ThreadPoolExecutor') as pool: self.populate(studio); studio.jobs = {}; studio._load_jobs()
        pool.assert_not_called(); self.assertIn('good-00', studio.jobs)


    def test_each_runs_root_is_resolved_once_per_load(self):
        """#1801: the containment guard resolves the runs root once per load, not once per run."""
        studio = self.studio(); self.populate(studio); studio.jobs = {}
        calls = Counter(); resolve = server.Path.resolve
        def counted(path, *a, **k): calls[path] += 1; return resolve(path, *a, **k)
        with patch.object(server.Path, 'resolve', counted): studio._load_jobs()
        self.assertGreater(len(studio.jobs), 5)
        # One for the load pass; the restart rewrite of the queued fixture saves through _save, outside it. Before #1801: one per run (21 here).
        self.assertLessEqual(calls[studio.runs], 2, 'the runs root is not resolved once per run')

if __name__ == '__main__': unittest.main()

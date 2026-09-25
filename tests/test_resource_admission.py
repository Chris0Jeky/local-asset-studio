import copy
import importlib.util
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]

host_memory = types.ModuleType('host_memory'); host_memory.read = lambda: {}
resource_probe = types.ModuleType('resource_probe')
resource_probe.physical_memory = lambda: {}
resource_probe.project_stats = lambda value: value
wan_capacity = types.ModuleType('wan_capacity')
wan_capacity.projection = lambda preset, graph: preset.get('wan_projection')
gpu_memory = types.ModuleType('gpu_memory'); gpu_memory.read = lambda: {}; gpu_memory.others_bytes = lambda reading, pid: None
with patch.dict(sys.modules, {'host_memory': host_memory, 'resource_probe': resource_probe, 'wan_capacity': wan_capacity, 'gpu_memory': gpu_memory}):
    spec = importlib.util.spec_from_file_location('resource_admission_test_target', ROOT / 'app/resource_admission.py')
    admission = importlib.util.module_from_spec(spec); spec.loader.exec_module(admission)

GIB = 1024 ** 3
GRAPH = {
    '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'model.gguf'}},
    '2': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}},
    '3': {'class_type': 'KSampler', 'inputs': {'steps': 20, 'model': ['1', 0], 'latent_image': ['2', 0]}},
    '4': {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0]}},
}


def observation(ram=40 * GIB, commit=40 * GIB, vram=16 * GIB, version='1.0'):
    return {
        'schema': 'studio.resource-observation/v1', 'observed_at': 1.0,
        'physical_ram': {'available_bytes': ram, 'unknown_reason': None if ram is not None else 'ram missing'},
        'windows_commit': {'available_bytes': commit, 'unknown_reason': None if commit is not None else 'commit missing'},
        'vram': {'available_bytes': vram, 'device_index': 0, 'unknown_reason': None if vram is not None else 'vram missing'},
        'runtime': {'versions': {'comfyui_version': version}, 'devices': []},
    }


class Backends:
    def __init__(self):
        self.active = 'primary'
        self.profiles = {'primary': {'id': 'primary', 'url': 'http://127.0.0.1:8188', 'root': 'C:/AI/ComfyUI', 'entry': 'main.py'}}


class Studio:
    def __init__(self):
        self.config = {}; self.backends = Backends(); self.comfy_url = 'http://127.0.0.1:8188'; self.jobs = {}; self.saved = []
    def _save(self, job): self.saved.append(copy.deepcopy(job))


def profile_for(studio, graph=GRAPH, *, basis='observed', stages=None, obs=None):
    obs = obs or observation()
    identity = admission.workflow_identity(studio, {'id': 'demo'}, graph, obs['runtime'])
    stages = stages or [
        {'name': 'load_models', 'physical_ram_bytes': 6 * GIB, 'windows_commit_bytes': 18 * GIB, 'vram_bytes': 12 * GIB},
        {'name': 'sample', 'physical_ram_bytes': 7 * GIB, 'windows_commit_bytes': 23 * GIB, 'vram_bytes': 15 * GIB},
        {'name': 'decode', 'physical_ram_bytes': 20 * GIB, 'windows_commit_bytes': 35 * GIB, 'vram_bytes': 8 * GIB},
    ]
    raw = {'schema': admission.PROFILE_SCHEMA, 'identity_sha256': identity['identity_sha256'], 'basis': basis,
           'source': {'receipt_sha256': 'a' * 64, 'kind': 'job-resource-observation'}, 'stages': stages}
    studio.config['resource_admission_profiles'] = {identity['identity_sha256']: raw}
    return admission._profile(raw, identity), identity


class ResourceAdmissionTests(unittest.TestCase):
    def test_stage_aware_profile_preserves_different_ram_commit_and_vram_peaks(self):
        studio = Studio(); profile, identity = profile_for(studio)
        receipt = admission.ReservationLedger().admit('job-a', identity, profile, observation())
        self.assertEqual(receipt['decision'], 'observed_safe')
        self.assertEqual(receipt['reservation'], {'physical_ram_bytes': 20 * GIB, 'windows_commit_bytes': 35 * GIB, 'vram_bytes': 15 * GIB})
        by_stage = {item['stage']: item['dimensions'] for item in receipt['stage_evaluations']}
        self.assertEqual(by_stage['sample']['vram_bytes']['required_bytes'], 15 * GIB)
        self.assertEqual(by_stage['decode']['physical_ram_bytes']['required_bytes'], 20 * GIB)
        self.assertEqual(by_stage['decode']['windows_commit_bytes']['required_bytes'], 35 * GIB)

    def test_observed_estimated_unknown_and_unsafe_remain_distinct(self):
        studio = Studio(); observed_profile, identity = profile_for(studio)
        estimated_profile, _ = profile_for(studio, basis='estimated')
        self.assertEqual(admission.ReservationLedger().admit('a', identity, observed_profile, observation())['decision'], 'observed_safe')
        self.assertEqual(admission.ReservationLedger().admit('a', identity, estimated_profile, observation())['decision'], 'estimated_safe')
        self.assertEqual(admission.ReservationLedger().admit('a', identity, observed_profile, observation(commit=None))['decision'], 'unknown')
        unsafe = admission.ReservationLedger().admit('a', identity, observed_profile, observation(vram=14 * GIB))
        self.assertEqual(unsafe['decision'], 'observed_unsafe')
        failing = next(item for item in unsafe['stage_evaluations'] if item['stage'] == 'sample')
        self.assertEqual(failing['dimensions']['vram_bytes']['state'], 'unsafe')

    def test_atomic_reservations_prevent_two_preparers_from_overcommitting(self):
        studio = Studio()
        stages = [{'name': 'sample', 'physical_ram_bytes': 1, 'windows_commit_bytes': 14 * GIB, 'vram_bytes': 1}]
        profile, identity = profile_for(studio, stages=stages)
        ledger = admission.ReservationLedger(); barrier = threading.Barrier(3); results = []
        def attempt(owner):
            barrier.wait(); results.append(ledger.admit(owner, identity, profile, observation(commit=20 * GIB))['decision'])
        threads = [threading.Thread(target=attempt, args=(name,)) for name in ('a', 'b')]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual(sorted(results), ['observed_safe', 'observed_unsafe'])
        self.assertEqual(len(ledger.snapshot()['owners']), 1)

    def test_same_owner_recheck_does_not_double_reserve_and_retains_on_refusal(self):
        studio = Studio(); profile, identity = profile_for(studio)
        ledger = admission.ReservationLedger()
        first = ledger.admit('job', identity, profile, observation())
        second = ledger.admit('job', identity, profile, observation(commit=34 * GIB))
        self.assertEqual(first['state'], 'reserved')
        self.assertEqual(second['decision'], 'observed_unsafe')
        self.assertEqual(second['state'], 'retained')
        self.assertEqual(ledger.snapshot()['owners'], ['job'])
        restored = admission.ReservationLedger(); restored.restore('job', second)
        self.assertEqual(restored.snapshot()['totals']['windows_commit_bytes'], 35 * GIB)

    def test_identity_change_after_reservation_refuses_and_retains_prior_capacity(self):
        studio = Studio(); profile, identity = profile_for(studio)
        controller = admission.AdmissionController(studio, observer=lambda _: observation())
        job = {'id': 'job', 'status': 'running', 'submissions': []}; studio.jobs = {'job': job}
        controller.admit(job, {'id': 'demo'}, GRAPH)
        changed = copy.deepcopy(GRAPH); changed['2']['inputs']['width'] = 768
        changed_identity = admission.workflow_identity(studio, {'id': 'demo'}, changed, observation()['runtime'])
        raw = copy.deepcopy(next(iter(studio.config['resource_admission_profiles'].values())))
        raw['identity_sha256'] = changed_identity['identity_sha256']
        studio.config['resource_admission_profiles'][changed_identity['identity_sha256']] = raw
        with self.assertRaisesRegex(admission.AdmissionError, 'Existing capacity remains retained'):
            controller.admit(job, {'id': 'demo'}, changed)
        self.assertEqual(job['resource_admission'][-1]['state'], 'retained')
        self.assertEqual(controller.ledger.snapshot()['owners'], ['job'])

    def test_exact_identity_changes_for_graph_model_backend_and_runtime(self):
        studio = Studio(); base = admission.workflow_identity(studio, {'id': 'demo'}, GRAPH, {'versions': {'comfyui_version': '1'}})
        changed_graph = copy.deepcopy(GRAPH); changed_graph['2']['inputs']['width'] = 768
        changed_model = copy.deepcopy(GRAPH); changed_model['1']['inputs']['unet_name'] = 'other.gguf'
        graph_identity = admission.workflow_identity(studio, {'id': 'demo'}, changed_graph, {'versions': {'comfyui_version': '1'}})
        model_identity = admission.workflow_identity(studio, {'id': 'demo'}, changed_model, {'versions': {'comfyui_version': '1'}})
        runtime_identity = admission.workflow_identity(studio, {'id': 'demo'}, GRAPH, {'versions': {'comfyui_version': '2'}})
        studio.backends.profiles['primary'] = dict(studio.backends.profiles['primary'], root='D:/Other')
        backend_identity = admission.workflow_identity(studio, {'id': 'demo'}, GRAPH, {'versions': {'comfyui_version': '1'}})
        self.assertEqual(len({base['identity_sha256'], graph_identity['identity_sha256'], model_identity['identity_sha256'], runtime_identity['identity_sha256'], backend_identity['identity_sha256']}), 5)

    def test_wan_projection_is_reused_in_identity_instead_of_redeclared(self):
        studio = Studio(); preset = {'id': 'wan', 'wan_projection': {'version': 1, 'limits': {'max_frames': 33}}}
        identity = admission.workflow_identity(studio, preset, GRAPH, {'versions': {}})
        self.assertEqual(identity['wan_decode_projection'], preset['wan_projection'])

    def test_controller_refuses_missing_profile_and_records_actionable_identity(self):
        studio = Studio(); job = {'id': 'job-a', 'status': 'running', 'submissions': []}; studio.jobs[job['id']] = job
        controller = admission.AdmissionController(studio, observer=lambda _: observation())
        with self.assertRaisesRegex(admission.AdmissionError, 'exact identity') as caught:
            controller.admit(job, {'id': 'demo'}, GRAPH)
        self.assertEqual(caught.exception.receipt['decision'], 'unknown')
        self.assertEqual(job['resource_admission'][-1]['identity_sha256'], caught.exception.receipt['identity_sha256'])
        self.assertNotIn('job-a', controller.ledger.snapshot()['owners'])

    def test_controller_reconciles_definitive_terminal_jobs_but_retains_uncertain_work(self):
        studio = Studio(); profile, identity = profile_for(studio)
        controller = admission.AdmissionController(studio, observer=lambda _: observation(ram=100 * GIB, commit=100 * GIB, vram=40 * GIB))
        completed = {'id': 'done', 'status': 'running', 'submissions': []}; uncertain = {'id': 'unknown', 'status': 'running', 'submissions': []}
        studio.jobs = {'done': completed, 'unknown': uncertain}
        controller.admit(completed, {'id': 'demo'}, GRAPH)
        controller.admit(uncertain, {'id': 'demo'}, GRAPH)
        completed['status'] = 'completed'; uncertain.update(status='uncertain', pending_submission={'index': 0})
        controller.reconcile()
        self.assertNotIn('done', controller.ledger.snapshot()['owners'])
        self.assertIn('unknown', controller.ledger.snapshot()['owners'])
        self.assertEqual(completed['resource_admission'][-1]['state'], 'released')
        self.assertEqual(uncertain['resource_admission'][-1]['state'], 'reserved')
        self.assertTrue(studio.saved)

    def test_restart_restores_uncertain_reservation_from_durable_receipt(self):
        studio = Studio(); profile, identity = profile_for(studio)
        ledger = admission.ReservationLedger(); receipt = ledger.admit('unknown', identity, profile, observation())
        studio.jobs = {'unknown': {'id': 'unknown', 'status': 'uncertain', 'pending_submission': {'index': 0},
                                   'submissions': [], 'resource_admission': [receipt]}}
        controller = admission.AdmissionController(studio, observer=lambda _: observation())
        controller.reconcile()
        self.assertEqual(controller.ledger.snapshot()['owners'], ['unknown'])

    def test_profile_and_receipt_bounds_fail_closed(self):
        studio = Studio(); obs = observation(); identity = admission.workflow_identity(studio, {'id': 'demo'}, GRAPH, obs['runtime'])
        bad = {'schema': admission.PROFILE_SCHEMA, 'identity_sha256': identity['identity_sha256'], 'basis': 'observed',
               'source': {'receipt_sha256': 'a' * 64},
               'stages': [{'name': 'x', 'physical_ram_bytes': 0,
                           'windows_commit_bytes': 0, 'vram_bytes': -1}]}
        with self.assertRaisesRegex(ValueError, 'non-negative'): admission._profile(bad, identity)
        job = {'id': 'job', 'resource_admission': [{}] * admission.MAX_RECEIPTS}
        controller = admission.AdmissionController(studio, observer=lambda _: obs)
        with self.assertRaisesRegex(ValueError, 'retention is full'): controller._record(job, {'schema': admission.SCHEMA})

    def test_pre_submit_is_opt_in_and_requires_durable_job_identity(self):
        studio = Studio()
        self.assertIsNone(admission.pre_submit(studio, {}, {'id': 'demo'}, GRAPH))
        studio.config['enforce_stage_resource_admission'] = True
        with self.assertRaisesRegex(ValueError, 'durable job identity'):
            admission.pre_submit(studio, {}, {'id': 'demo'}, GRAPH)


if __name__ == '__main__': unittest.main()

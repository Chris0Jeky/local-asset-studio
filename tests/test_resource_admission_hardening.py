import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))

import resource_admission as admission


GIB = 1024 ** 3
PRESET = {
    'id': 'demo',
    'backend_id': 'primary',
    'seed': ['3', 'seed'],
    'positive': ['4', 'text'],
}
GRAPH = {
    '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'model.gguf'}},
    '2': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}},
    '3': {'class_type': 'KSampler', 'inputs': {'seed': 41, 'steps': 20, 'cfg': 7.0,
                                                'model': ['1', 0], 'latent_image': ['2', 0]}},
    '4': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'A first prompt.', 'clip': ['1', 1]}},
}
RUNTIME = {'versions': {'comfyui_version': '1.0', 'pytorch_version': '2.0'}}


class Backends:
    profiles = {
        'primary': {
            'id': 'primary',
            'url': 'http://127.0.0.1:8188',
            'root': 'C:/AI/ComfyUI',
            'entry': 'main.py',
        }
    }


class Studio:
    def __init__(self):
        self.backends = Backends()
        self.comfy_url = 'http://127.0.0.1:8188'
        self.config = {}
        self.jobs = {}
        self.saved = []

    def _save(self, job):
        self.saved.append(copy.deepcopy(job))


def observation():
    return {
        'schema': 'studio.resource-observation/v1',
        'observed_at': 1.0,
        'physical_ram': {'available_bytes': 64 * GIB, 'unknown_reason': None},
        'windows_commit': {'available_bytes': 64 * GIB, 'unknown_reason': None},
        'vram': {'available_bytes': 24 * GIB, 'device_index': 0, 'unknown_reason': None},
        'runtime': copy.deepcopy(RUNTIME),
    }


def raw_profile(identity):
    return {
        'schema': admission.PROFILE_SCHEMA,
        'identity_sha256': identity['identity_sha256'],
        'basis': 'observed',
        'source': {'receipt_sha256': 'a' * 64, 'kind': 'test-observation'},
        'stages': [{
            'name': 'sample',
            'physical_ram_bytes': 8 * GIB,
            'windows_commit_bytes': 12 * GIB,
            'vram_bytes': 10 * GIB,
        }],
    }


def profile(studio, identity):
    raw = raw_profile(identity)
    studio.config['resource_admission_profiles'] = {identity['identity_sha256']: raw}
    return admission._profile(raw, identity)


class ResourceAdmissionHardeningTests(unittest.TestCase):
    def test_profile_requires_every_resource_dimension_explicitly(self):
        studio = Studio()
        identity = admission.workflow_identity(studio, PRESET, GRAPH, RUNTIME)
        for missing in admission.DIMENSIONS:
            stage = {
                'name': 'sample',
                'physical_ram_bytes': 1,
                'windows_commit_bytes': 1,
                'vram_bytes': 1,
            }
            del stage[missing]
            raw = {
                'schema': admission.PROFILE_SCHEMA,
                'identity_sha256': identity['identity_sha256'],
                'basis': 'observed',
                'source': {'receipt_sha256': 'a' * 64},
                'stages': [stage],
            }
            with self.subTest(missing=missing), self.assertRaisesRegex(
                    ValueError, 'every resource dimension'):
                admission._profile(raw, identity)

    def test_resource_identity_ignores_bound_prompt_and_seed_but_keeps_exact_graph_evidence(self):
        studio = Studio()
        first = admission.workflow_identity(studio, PRESET, GRAPH, RUNTIME)
        changed = copy.deepcopy(GRAPH)
        changed['3']['inputs']['seed'] = 42
        changed['4']['inputs']['text'] = 'A different user-authored prompt with other words.'
        second = admission.workflow_identity(studio, PRESET, changed, RUNTIME)
        self.assertEqual(first['identity_sha256'], second['identity_sha256'])
        self.assertEqual(first['resource_graph_sha256'], second['resource_graph_sha256'])
        self.assertNotEqual(first['submitted_graph_sha256'], second['submitted_graph_sha256'])

        changed_shape = copy.deepcopy(changed)
        changed_shape['2']['inputs']['width'] = 768
        self.assertNotEqual(
            first['identity_sha256'],
            admission.workflow_identity(studio, PRESET, changed_shape, RUNTIME)['identity_sha256'],
        )
        changed_model = copy.deepcopy(changed)
        changed_model['1']['inputs']['unet_name'] = 'other.gguf'
        self.assertNotEqual(
            first['identity_sha256'],
            admission.workflow_identity(studio, PRESET, changed_model, RUNTIME)['identity_sha256'],
        )
        changed_cfg = copy.deepcopy(changed)
        changed_cfg['3']['inputs']['cfg'] = 8.0
        self.assertNotEqual(
            first['identity_sha256'],
            admission.workflow_identity(studio, PRESET, changed_cfg, RUNTIME)['identity_sha256'],
        )

    def test_restart_refuses_a_tampered_active_receipt_instead_of_restoring_less_capacity(self):
        studio = Studio()
        identity = admission.workflow_identity(studio, PRESET, GRAPH, RUNTIME)
        retained = admission.ReservationLedger().admit(
            'job-a', identity, profile(studio, identity), observation())
        retained['reservation']['windows_commit_bytes'] = 1
        job = {
            'id': 'job-a',
            'status': 'uncertain',
            'pending_submission': {'index': 0},
            'submissions': [],
            'resource_admission': [retained],
        }
        studio.jobs = {'job-a': job}
        controller = admission.AdmissionController(studio, observer=lambda _: observation())
        with self.assertRaisesRegex(ValueError, 'receipt SHA-256'):
            controller.reconcile()
        self.assertEqual(controller.ledger.snapshot()['owners'], [])

    def test_restart_keeps_a_retained_reservation_bound_to_its_original_identity(self):
        studio = Studio()
        original = admission.workflow_identity(studio, PRESET, GRAPH, RUNTIME)
        studio.config['resource_admission_profiles'] = {
            original['identity_sha256']: raw_profile(original),
        }
        job = {'id': 'job-a', 'status': 'running', 'submissions': []}
        studio.jobs = {'job-a': job}
        controller = admission.AdmissionController(studio, observer=lambda _: observation())
        controller.admit(job, PRESET, GRAPH)

        changed_graph = copy.deepcopy(GRAPH)
        changed_graph['2']['inputs']['width'] = 768
        changed = admission.workflow_identity(studio, PRESET, changed_graph, RUNTIME)
        studio.config['resource_admission_profiles'][changed['identity_sha256']] = raw_profile(changed)
        with self.assertRaisesRegex(admission.AdmissionError, 'Existing capacity remains retained'):
            controller.admit(job, PRESET, changed_graph)
        self.assertEqual(job['resource_admission'][-1]['state'], 'retained')
        self.assertEqual(
            job['resource_admission'][-1]['retained_identity_sha256'],
            original['identity_sha256'],
        )

        job['status'] = 'uncertain'
        job['pending_submission'] = {'index': 0}
        restarted = admission.AdmissionController(studio, observer=lambda _: observation())
        restarted.reconcile()
        restored = restarted.ledger.reservation_for('job-a')
        self.assertEqual(restored['identity_sha256'], original['identity_sha256'])


if __name__ == '__main__':
    unittest.main()

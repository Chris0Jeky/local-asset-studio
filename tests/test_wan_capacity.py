import json
import unittest
from pathlib import Path

import test_server
from test_server import FakeStudio
from wan_capacity import enforce

ROOT = Path(__file__).parents[1]


def graph(width=1280, height=704, frames=41):
    result = json.loads((ROOT / 'workflows/api/wan22-i2v-api.json').read_text(encoding='utf-8'))
    result['7']['inputs'].update(width=width, height=height, length=frames, batch_size=1)
    return result


class CapacityTests(unittest.TestCase):
    def test_quick_and_balanced_orientations_remain_available(self):
        for width, height in ((512, 768), (768, 512)):
            for frames in (17, 33):
                with self.subTest(width=width, height=height, frames=frames):
                    enforce(graph(width, height, frames))

    def test_long_shapes_cannot_bypass_guard_by_omitting_mode(self):
        for width, height, frames in ((1280, 704, 41), (704, 1280, 41), (768, 1152, 81), (512, 768, 81), (1024, 256, 17)):
            with self.subTest(shape=(width, height, frames)), self.assertRaisesRegex(ValueError, 'decode capacity is unproven'):
                enforce(graph(width, height, frames))

    def test_latent_batch_and_invalid_dimensions_are_checked(self):
        candidate = graph(512, 768, 17)
        candidate['7']['inputs']['batch_size'] = 2
        with self.assertRaisesRegex(ValueError, 'batch 2'): enforce(candidate)
        candidate['7']['inputs']['width'] = True
        with self.assertRaisesRegex(ValueError, 'invalid latent dimensions'): enforce(candidate)

    def test_disconnected_wan_and_other_video_families_are_not_blocked(self):
        candidate = graph()
        candidate['10']['inputs']['samples'] = ['other', 0]
        candidate['other'] = {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1280, 'height': 704}}
        enforce(candidate)
        del candidate['7']
        enforce(candidate)

    def test_tiled_decode_is_a_separate_graph_not_certified_by_this_guard(self):
        candidate = graph()
        candidate['10']['class_type'] = 'VAEDecodeTiled'
        enforce(candidate)


class AdmissionTests(unittest.TestCase):
    setUp = test_server.ServerTests.setUp
    tearDown = test_server.ServerTests.tearDown

    def install_graph(self, candidate):
        preset = {'id': 'wan22-i2v', 'name': 'Wan', 'graph': 'workflows/api/demo-api.json'}
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [preset]}))
        (self.root / 'workflows/api/demo-api.json').write_text(json.dumps(candidate))

    def test_create_and_production_preflight_reject_before_reservation_or_http(self):
        candidate = graph()
        self.install_graph(candidate)
        studio = FakeStudio(self.root, [])
        with self.assertRaisesRegex(ValueError, 'decode capacity is unproven'):
            studio.create_job({'preset_id': 'wan22-i2v'})
        with self.assertRaisesRegex(ValueError, 'decode capacity is unproven'):
            studio.production_preflight(studio.preset('wan22-i2v'), candidate)
        self.assertEqual(studio.requests, [])
        self.assertFalse(studio.jobs)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(list(studio.runs.iterdir()), [])

    def test_preserved_queued_graph_is_rechecked_immediately_before_prompt(self):
        self.install_graph(graph(512, 768, 17))
        studio = FakeStudio(self.root, [{'queue_running': [], 'queue_pending': []}])
        job = studio.jobs[studio.create_job({'preset_id': 'wan22-i2v'}, enqueue=False)['id']]
        job['graph'] = graph()
        studio._run(job)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['prompt_ids'], [])
        self.assertNotIn('pending_submission', job)
        self.assertFalse(any(args[0] == '/prompt' for args, _ in studio.requests))
        self.assertIn('decode capacity is unproven', job['message'])


if __name__ == '__main__': unittest.main()

"""Quiet-left diagnostics and the prepared Look's durable attribution."""
import io
import json
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
import test_looks as fixture
import review_media


def picture(side=None, size=(128, 64)):
    image = Image.new('RGB', size, '#808080')
    if side:
        draw = ImageDraw.Draw(image)
        start = 0 if side == 'left' else size[0] // 2
        for x in range(start, start + size[0] // 2, 4):
            draw.rectangle((x, 0, x + 1, size[1] - 1), fill='white')
    stream = io.BytesIO(); image.save(stream, format='PNG'); image.close()
    return stream.getvalue()


class TextSafetyTests(unittest.TestCase):
    def metric(self, data):
        self.assertTrue(callable(getattr(review_media, 'text_safe_metrics', None)), 'missing measurable quiet-left diagnostic')
        return review_media.text_safe_metrics(data)

    def test_flat_has_no_edges_or_infinite_ratio(self):
        result = self.metric(picture())
        self.assertEqual((result['left_edge_density'], result['right_edge_density']), (0, 0))
        self.assertIsNone(result['left_right_ratio'])
        self.assertEqual(result['comparison'], 'equal detail')
        json.dumps(result, allow_nan=False)

    def test_left_and_right_busy_are_distinguished(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                result = self.metric(picture(side))
                self.assertGreater(result[side + '_edge_density'], 0.1)
                self.assertEqual(result[('right' if side == 'left' else 'left') + '_edge_density'], 0)
                self.assertEqual(result['comparison'], 'left busier' if side == 'left' else 'left quieter')

    def test_decode_and_sampling_budgets(self):
        self.assertLessEqual(max(self.metric(picture('right', (2048, 1024)))['sample_size']), 512)
        with self.assertRaises(ValueError): self.metric(b'not an image')
        with patch.object(review_media, 'MAX_PIXELS', 10):
            with self.assertRaises(ValueError): self.metric(picture())
        with self.assertRaises(ValueError): self.metric(picture(size=(1, 1)))


class LookRunTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp

    def prepare(self, wall=True):
        card = fixture.looks.command(self.studio, {'action': 'create', 'kind': 'look', 'name': 'Night Shift', 'body': fixture.OPTIONAL})
        ready = fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a room', 'options': {'quiet_wall': wall}})
        return {'preset_id': ready['preset_id'], 'controls': ready['controls'], 'look': ready['look']}

    def test_prepared_look_survives_job_recipe_and_reload(self):
        payload = self.prepare()
        job = self.studio.create_job(payload, enqueue=False)
        self.assertIn('look', job, 'the job discards which Look prepared it')
        self.assertEqual(job['look'], payload['look'])
        recipe = json.loads((self.studio.runs / job['id'] / 'recipe.json').read_text())
        self.assertEqual(recipe['look'], job['look'])
        self.assertEqual(self.studio.export_recipe(self.studio.jobs[job['id']])['look'], job['look'])
        restarted = fixture.server.Studio(self.root)
        self.assertEqual(restarted.public(restarted.jobs[job['id']])['look'], job['look'])

    def test_invalid_or_stale_attribution_is_refused(self):
        payload = self.prepare()
        for change in ({'revision': True}, {'revision': 999}, {'options': {'quiet_wall': 'yes'}}, {'options': {'unknown': True}}, {'id': 'missing'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.studio.create_job(dict(payload, look=dict(payload['look'], **change)), enqueue=False)
        self.assertEqual(self.studio.jobs, {})

    def test_attribution_uses_server_name_and_survives_make_recipe_tuning(self):
        payload = self.prepare(False)
        payload['look']['name'] = 'forged name'
        job = self.studio.create_job(payload, enqueue=False)
        self.assertEqual(job['look']['name'], 'Night Shift')
        self.assertFalse(job['look']['options']['quiet_wall'])
        tuned = self.studio.create_job(dict(payload, preset_id='with-negative'), enqueue=False)
        self.assertEqual(tuned['look'], job['look'])

    def test_unavailable_metric_does_not_change_generation_outcome_or_retry(self):
        job = self.studio.create_job(self.prepare(), enqueue=False)
        stored = self.studio.jobs[job['id']]
        path = self.root / 'fake-comfy/output/result.png'; path.parent.mkdir(exist_ok=True); path.write_bytes(picture())
        stored['status'] = 'completed'
        stored['outputs'] = [{'filename': path.name, 'subfolder': '', 'type': 'output', 'media_type': 'image'}]
        with patch.object(review_media, 'text_safe_metrics', side_effect=ValueError('unsupported image')) as metric:
            self.studio.index_outputs(stored); self.studio.index_outputs(stored)
        self.assertEqual(metric.call_count, 1)
        self.assertEqual(stored['status'], 'completed')
        self.assertEqual(stored['outputs'][0]['text_safe'], {'error': 'unsupported image'})

    def test_non_quiet_results_skip_measurement(self):
        job = self.studio.create_job(self.prepare(False), enqueue=False)
        stored = self.studio.jobs[job['id']]
        path = self.root / 'fake-comfy/output/result.png'; path.parent.mkdir(exist_ok=True); path.write_bytes(picture())
        stored['outputs'] = [{'filename': path.name, 'subfolder': '', 'type': 'output', 'media_type': 'image'}]
        with patch.object(review_media, 'text_safe_metrics') as metric: self.studio.index_outputs(stored)
        metric.assert_not_called()

    def test_indexed_quiet_wall_result_gets_metrics(self):
        job = self.studio.create_job(self.prepare(), enqueue=False)
        stored = self.studio.jobs[job['id']]
        path = self.root / 'fake-comfy/output/result.png'; path.parent.mkdir(exist_ok=True); path.write_bytes(picture('right'))
        stored['outputs'] = [{'filename': path.name, 'subfolder': '', 'type': 'output', 'media_type': 'image'}]
        self.studio.index_outputs(stored)
        output = stored['outputs'][0]
        self.assertIn('asset_id', output)
        self.assertIn('text_safe', output, 'quiet-wall results have no diagnostic')
        self.assertEqual(output['text_safe']['comparison'], 'left quieter')
        self.studio._save(stored)
        state = json.loads((self.studio.runs / job['id'] / 'state.json').read_text())
        self.assertEqual(state['outputs'][0]['text_safe'], output['text_safe'])

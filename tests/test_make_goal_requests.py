"""Make's picture goals (make.js goalGenerate) send the request shapes the real server prepares. No model, no ComfyUI.

The browser test (tests/make_goals_browser.py) proves what the page sends against a fixture; this replays the same shapes
through the real Studio.preview, so a board record, claim or control the server would refuse fails here.
"""
import hashlib
import io
import json
import shutil
import subprocess
import unittest

from PIL import Image

import test_continuation as base  # puts app/ on sys.path first


def board_record(upload, parent=None):
    # StudioContinuation.combineReferences: the slot role, empty guidance, and only these attachment keys.
    record = {'role': '', 'contribution': '', 'avoid': '', 'file': upload['file'], 'sha256': upload['sha256'], 'width': upload['width'], 'height': upload['height']}
    if 'bytes' in upload: record['bytes'] = upload['bytes']
    if parent: record['parent_asset'] = parent
    return record


class MakeGoalRequestTests(unittest.TestCase):
    def setUp(self):
        self.case = base.ContinuationTests(); self.addCleanup(self.case.doCleanups); self.case.setUp()
        self.studio, root = self.case.studio, self.case.root
        catalog = json.loads((base.ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']
        local = json.loads((root / 'presets/catalog.json').read_text(encoding='utf-8'))
        for preset in catalog:
            if preset['id'] in ('restyle-klein-picture', 'combine-klein-9b-copypose', 'combine-klein-9b-depth', 'flux-edit', 'wan22-i2v', 'trellis-auto-cutout'):
                (root / preset['graph']).parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(base.ROOT / preset['graph'], root / preset['graph'])
                local['presets'].append(preset)
        (root / 'presets/catalog.json').write_text(json.dumps(local), encoding='utf-8')
        stream = io.BytesIO(); Image.new('RGB', (16, 24), 'navy').save(stream, 'JPEG')
        self.look = self.studio.upload('look-preset-realvis.jpg', 'image/jpeg', stream.getvalue())
        self.file, self.asset = self.case.attachment['file'], self.case.asset_id

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for Make owner-decision contracts')
    def test_running_history_and_stop_on_navigation_contracts(self):
        result = subprocess.run([shutil.which('node'), '--test', '--test-name-pattern=history|overflow|navigation|Compare still|uncertain restored',
                                 str(base.ROOT / 'tests/make_followups.cjs')], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('fail 0', result.stdout, result.stdout + result.stderr)

    def claim(self, preset_id, intent):
        graph = self.case.root / next(p for p in json.loads((self.case.root / 'presets/catalog.json').read_text(encoding='utf-8'))['presets'] if p['id'] == preset_id)['graph']
        return dict(self.case.claim, intent=intent, preset_id=preset_id, template_sha256=hashlib.sha256(graph.read_bytes()).hexdigest())

    def preview(self, preset_id, intent, controls, references=(), parents=None):
        payload = dict(preset_id=preset_id, continuation=self.claim(preset_id, intent), controls=controls, batch_count=1,
                       parent_assets=parents or [self.asset], references=list(references))
        return self.studio.preview(payload)

    def test_restyle_with_a_look_picture_board(self):
        preset = self.studio.preset('restyle-klein-picture')
        words = preset['continuation_prompt'].replace(preset['continuation_placeholder'], 'keep them exactly as they are')
        result = self.preview('restyle-klein-picture', 'restyle', {'last_reference': self.file, 'positive': words, 'seed': 7, 'width': 1024, 'height': 1536},
                              [dict(board_record(self.look), role='style'), {'role': 'style', 'contribution': '', 'avoid': '', 'file': None}])
        self.assertFalse(result['submitted'])
        self.assertEqual(result['workflow']['14']['inputs']['image'], self.file)
        self.assertEqual(result['workflow']['20']['inputs']['image'], self.look['file'])
        # A bracket left in the wording is refused by the server whatever the page does.
        with self.assertRaisesRegex(ValueError, 'name the colours'):
            self.preview('restyle-klein-picture', 'restyle', {'last_reference': self.file, 'positive': preset['continuation_prompt']}, [dict(board_record(self.look), role='style'), {'role': 'style', 'file': None}])

    def test_combine_with_a_library_pose_picture(self):
        preset, pose = self.studio.preset('combine-klein-9b-copypose'), self.studio.asset_reference(self.case.source_job['outputs'][1]['asset_id'])
        words = preset['continuation_prompt']
        for placeholder, answer in zip(preset['continuation_placeholder'], ('the traveller', 'a green cloak', 'arms crossed')): words = words.replace(placeholder, answer)
        result = self.preview('combine-klein-9b-copypose', 'combine', {'last_reference': self.file, 'positive': words, 'seed': 7},
                              [dict(board_record(pose, pose['parent_asset']), role='pose')], parents=[self.asset, pose['parent_asset']])
        self.assertEqual((result['workflow']['14']['inputs']['image'], result['workflow']['20']['inputs']['image']), (self.file, pose['file']))

    def test_combine_depth_keeps_character_and_pose_in_the_authored_order(self):
        preset, pose = self.studio.preset('combine-klein-9b-depth'), self.studio.asset_reference(self.case.source_job['outputs'][1]['asset_id'])
        words = preset['continuation_prompt']
        for placeholder, answer in zip(preset['continuation_placeholder'], ('the traveller', 'arms crossed', 'a green cloak')): words = words.replace(placeholder, answer)
        result = self.preview(preset['id'], 'combine', {'last_reference': self.file, 'positive': words, 'seed': 7},
                              [dict(board_record(pose, pose['parent_asset']), role='pose')], parents=[self.asset, pose['parent_asset']])
        self.assertFalse(result['submitted'])
        self.assertEqual((result['workflow']['14']['inputs']['image'], result['workflow']['20']['inputs']['image']), (pose['file'], self.file))

    def test_edit_animate_and_mesh_take_the_source_on_reference(self):
        preset = self.studio.preset('flux-edit')
        words = preset['continuation_prompt'].replace(preset['continuation_placeholder'], 'give her a red scarf').replace('{source}', '')
        self.assertEqual(self.preview('flux-edit', 'edit', {'reference': self.file, 'positive': words, 'seed': 7})['workflow']['14']['inputs']['image'], self.file)
        mode = next(m for m in self.studio.preset('wan22-i2v')['i2v_modes'] if m['id'] == 'quick-diagnostic')
        result = self.preview('wan22-i2v', 'animate', {'reference': self.file, 'positive': 'she turns her head', 'seed': 7, **mode['controls'], 'mode': mode['id']})
        self.assertEqual(result['workflow']['4']['inputs']['image'], self.file); self.assertEqual(result['workflow']['7']['inputs']['length'], 17)
        self.assertEqual(self.preview('trellis-auto-cutout', 'mesh', {'reference': self.file, 'seed': 7})['workflow']['1']['inputs']['image'], self.file)


if __name__ == '__main__':
    unittest.main()

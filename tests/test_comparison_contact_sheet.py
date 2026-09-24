"""A contact-sheet failure must not strand a completed comparison."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import test_production as fixtures
import io

from PIL import Image
from test_server import FakeStudio, server, png


def distinct_png(index):
    # Snapshots are content-addressed: identical bytes would share one media file.
    stream = io.BytesIO(); Image.new('RGB', (8, 12), (index * 40 % 256, 20, 90)).save(stream, 'PNG'); return stream.getvalue()


IDLE = {'queue_running': [], 'queue_pending': []}


class ContactSheetFailureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ProductionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.studio = FakeStudio(self.root, [])

    def _stage_replies(self, names):
        replies = []
        for index, name in enumerate(names):
            prompt_id = f'sheet-{index}'
            replies.append(dict(IDLE))
            replies.append({'prompt_id': prompt_id})
            replies.append({prompt_id: {'status': {'status_str': 'success'}, 'outputs': {
                '9': {'images': [{'filename': name, 'subfolder': '', 'type': 'output'}]}}}})
        return replies

    def _run_comparison(self, values, names):
        lab = self.studio.production
        project = lab.create(self.fixture.intent(values=values))
        lab.start(project['id'])
        output_dir = self.studio.comfy_root / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        for index, name in enumerate(names):
            (output_dir / name).write_bytes(distinct_png(index + 1))
        self.studio.replies = iter(self._stage_replies(names))
        lab.run(project['id'])
        return project['id']

    def _asset_ids(self, project_id):
        lab = self.studio.production
        viewed = lab.get(project_id)
        ids = []
        for stage in viewed['stages']:
            job = stage['job'] or {}
            for output in job.get('outputs', []):
                if output.get('asset_id') and output.get('media_type') == 'image':
                    ids.append(output['asset_id'])
        return ids

    def test_missing_asset_file_still_reaches_review_with_no_artifacts(self):
        from workspace import WorkspaceError
        # Build a single-candidate comparison but make its snapshot unavailable at sheet time.
        lab = self.studio.production
        project = lab.create(self.fixture.intent(values=[1]))
        lab.start(project['id'])
        output_dir = self.studio.comfy_root / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / 'only.png').write_bytes(png())
        self.studio.replies = iter(self._stage_replies(['only.png']))
        with patch.object(self.studio.assets, 'file', side_effect=WorkspaceError('Asset snapshot is unavailable')):
            lab.run(project['id'])
        state = lab.get(project['id'])['state']
        self.assertEqual(state['status'], 'awaiting_review')
        self.assertNotEqual(state['status'], 'uncertain')
        self.assertEqual(state['artifacts'], [])
        self.assertFalse((lab.root / project['id'] / 'comparison.png').exists())

    def test_contact_sheet_skips_missing_image_and_records_skipped(self):
        project_id = self._run_comparison([1, 2], ['keep.png', 'gone.png'])
        lab = self.studio.production
        state = lab.get(project_id)['state']
        self.assertEqual(state['status'], 'awaiting_review')
        asset_ids = self._asset_ids(project_id)
        self.assertEqual(len(asset_ids), 2)
        # Remove one snapshot so only one record can be drawn.
        missing = self.studio.assets.file(asset_ids[1])
        missing.unlink()
        artifacts = lab.contact_sheet(project_id)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]['path'], 'comparison.png')
        target = lab.root / project_id / 'comparison.png'
        self.assertTrue(target.is_file())
        sidecar = json.loads(target.with_suffix('.json').read_text(encoding='utf-8'))
        self.assertEqual(sidecar.get('skipped'), 1)
        self.assertEqual(len(sidecar.get('labels', [])), 1)

    def test_unexpected_sheet_error_still_reaches_review_and_names_type(self):
        lab = self.studio.production
        project = lab.create(self.fixture.intent(values=[1, 2]))
        lab.start(project['id'])
        output_dir = self.studio.comfy_root / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in ('first.png', 'second.png'):
            (output_dir / name).write_bytes(png())
        self.studio.replies = iter(self._stage_replies(['first.png', 'second.png']))
        with patch('PIL.Image.new', side_effect=RuntimeError('fixture: sheet failed')):
            lab.run(project['id'])
        state = lab.get(project['id'])['state']
        self.assertEqual(state['status'], 'awaiting_review')
        self.assertEqual(state['artifacts'], [])
        self.assertEqual(
            state['message'],
            'Comparison finished. The contact sheet could not be built (RuntimeError); '
            'review the candidates directly and record your choice.')


if __name__ == '__main__':
    unittest.main()

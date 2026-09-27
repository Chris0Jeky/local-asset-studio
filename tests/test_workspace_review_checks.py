"""Quick review checks (#1203) are owner answers stored as `check:<name>=yes|no` tags in the asset's revisioned metadata.

Absent means not checked, never no (K14). Only a well-formed answer from the fixed vocabulary is stored, one per check,
so the per-engine counts the page derives from tags can never read a malformed or contradictory answer.
"""
import importlib.util
import tempfile
import unittest
import uuid
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace_checks', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)


class ReviewCheckTagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        source = self.root/'render.png'; source.write_bytes(b'rendered bytes')
        self.store = workspace.AssetWorkspace(self.root)
        self.asset = self.store.register({'id':'combine-run', 'preset_id':'combine-klein', 'preset_name':'Combine',
                                          'outputs':[{'filename':'render.png', 'media_type':'image'}]}, 0, source)

    def edit(self, store=None, **fields):
        store = store or self.store
        return store.update(dict(fields, action='edit', ids=[self.asset], request_id=uuid.uuid4().hex,
                                 expected_revisions={self.asset: store.get(self.asset)['metadata_revision']}))

    def test_answers_save_with_the_review_revision_and_survive_a_reopen(self):
        before = self.store.get(self.asset)['metadata_revision']
        receipt = self.edit(tags=['hero', 'check:pose=yes', 'check:face=no'])
        self.assertEqual(receipt['applied']['tags'], ['hero', 'check:pose=yes', 'check:face=no'])
        self.assertEqual(receipt['revisions'][self.asset], before + 1)
        # A later Keep that sends only the review leaves the answers exactly as saved; checks never block it.
        self.edit(review='selected')
        reopened = workspace.AssetWorkspace(self.root).get(self.asset)
        self.assertEqual(reopened['review'], 'selected')
        self.assertEqual(reopened['tags'], ['hero', 'check:pose=yes', 'check:face=no'])
        self.assertEqual(reopened['metadata_revision'], before + 2)

    def test_every_check_in_the_vocabulary_accepts_yes_and_no(self):
        self.assertEqual(workspace.REVIEW_CHECKS, ('pose', 'face', 'outfit', 'style', 'clean', 'anatomy', 'composition'))
        for name in workspace.REVIEW_CHECKS:
            for answer in ('yes', 'no'):
                self.assertEqual(self.edit(tags=['check:%s=%s' % (name, answer)])['applied']['tags'], ['check:%s=%s' % (name, answer)])
        # Clearing every answer returns the check to "not checked"; nothing records a default no.
        self.assertEqual(self.edit(tags=[])['applied']['tags'], [])

    def test_malformed_unknown_or_contradictory_answers_change_nothing(self):
        self.edit(tags=['check:pose=yes'])
        saved = self.store.get(self.asset)
        for tags in (['check:pose=maybe'], ['check:hair=yes'], ['Check:pose=yes'], ['check:pose'], ['check:pose=yes=no'],
                     ['check: pose=yes'], ['check:pose=yes', 'check:pose=no'], ['CHECK:face=no']):
            with self.subTest(tags=tags):
                with self.assertRaises(workspace.WorkspaceError) as caught:
                    self.edit(tags=tags)
                self.assertIn('nothing changed', str(caught.exception))
                self.assertEqual(self.store.get(self.asset), saved)

    def test_ordinary_and_reason_tags_are_not_in_the_check_namespace(self):
        tags = ['face', 'hands', 'checklist', 'check', 'pose=yes', 'style off']
        self.assertEqual(self.edit(tags=tags)['applied']['tags'], tags)
        # The same answer twice is one answer (tags are de-duplicated before the check rule runs).
        self.assertEqual(self.edit(tags=['check:clean=no', 'check:clean=no'])['applied']['tags'], ['check:clean=no'])


if __name__ == '__main__':
    unittest.main()

"""Read-only bounded history over the existing real setup/Workspace tables."""
import copy
from contextlib import contextmanager
import importlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import test_recipe_shortlist_apply as fixture
from studio_workflow.core import canonical, digest
from studio_workflow.setup_draft_http import route


class ReviewedSetupHistoryTests(unittest.TestCase):
    setUp = fixture.SetupApplyTests.setUp
    store = fixture.SetupApplyTests.store
    command = fixture.SetupApplyTests.command
    create = fixture.SetupApplyTests.create

    def history(self):
        try:
            module = importlib.import_module('studio_workflow.setup_history')
        except ModuleNotFoundError:
            self.fail('The bounded reviewed-setup history reader is not implemented')
        return module.SetupHistory(self.s.assets)

    def revisions(self, count=2):
        first = self.create()
        for revision in range(2, count + 1):
            draft = copy.deepcopy(self.before)
            draft['recipe']['controls']['positive'] = 'Revision ' + str(revision)
            self.command('replace', request_id='history-' + str(revision), draft_id=first['draft_id'], expected_revision=revision-1, draft=draft)
        return first['draft_id']

    def page(self, key, **options):
        return self.history().page(key, workspace_id=self.scope, **options)

    def dump(self):
        with self.s.assets.connection() as db:
            return list(db.iterdump())

    def test_one_hundred_revisions_page_in_order_without_full_drafts(self):
        key = self.revisions(100)
        before = self.dump()
        result = self.page(key, limit=7)
        rows = list(result['revisions'])
        while result['next_before_revision'] is not None:
            self.assertLessEqual(len(result['revisions']), 7)
            result = self.page(key, limit=7, before_revision=result['next_before_revision'], expected_head=result['head_revision'])
            rows.extend(result['revisions'])
        self.assertEqual([r['revision'] for r in rows], list(range(100, 0, -1)))
        self.assertTrue(all('draft' not in r and 'runtime' not in r and 'record_json' not in r for r in rows))
        self.assertEqual(self.dump(), before)
        self.assertEqual(self.s.upload_count, 0)

    def test_stale_head_continuation_refuses_without_erasing_history(self):
        key = self.revisions(3)
        page = self.page(key, limit=1)
        self.command('replace', draft_id=key, expected_revision=3, draft=self.before)
        with self.assertRaisesRegex(ValueError, 'head|changed'):
            self.page(key, before_revision=page['next_before_revision'], expected_head=3)
        self.assertEqual(self.store().get(key, 3)['revision'], 3)

    def test_page_bounds_and_continuation_preconditions(self):
        key = self.revisions()
        for options in [{'limit': 0}, {'limit': 21}, {'limit': True}, {'before_revision': 2},
                        {'before_revision': 3, 'expected_head': 2}, {'expected_head': True}, {'before_revision': 0, 'expected_head': 2}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.page(key, **options)

    def test_wrong_workspace_refuses_before_reading_revision_rows(self):
        key = self.revisions()
        with self.s.assets.connection() as db:
            db.execute('UPDATE setup_versions_v1 SET record=?', ('not JSON',))
        with self.assertRaisesRegex(ValueError, 'Workspace'):
            self.history().page(key, workspace_id='f' * 32)
        for scope in [None, '', True]:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.history().page(key, workspace_id=scope)

    def test_typed_comparison_bounds_previews_and_distinguishes_absent_values(self):
        key = self.revisions(1)
        value = copy.deepcopy(self.before)
        value['recipe']['controls'].update(positive='界' * 12000, negative='', steps=20)
        value['recipe']['batch'] = 3
        self.command('replace', draft_id=key, expected_revision=1, draft=value)
        result = self.history().compare(key, 1, 2, workspace_id=self.scope)
        domains = {r['section']: r for r in result['sections']}
        self.assertTrue(domains['wording']['changed'])
        self.assertTrue(domains['wording']['right']['truncated'])
        self.assertTrue(domains['controls']['changed'])
        self.assertTrue(domains['batch']['changed'])
        self.assertFalse(domains['references']['changed'])
        self.assertLess(len(canonical(result)), 65536)
        self.assertEqual(result['left_revision'], 1)
        self.assertFalse(result['generation_submitted'])

    def test_metadata_export_omits_runtime_paths_and_has_distinct_exact_digest(self):
        key = self.revisions(1)
        result = self.history().export_revision(key, 1, workspace_id=self.scope)
        self.assertEqual(result['export_sha256'], digest(result['export']))
        self.assertEqual(result['export_json'].encode(), canonical(result['export']))
        self.assertEqual(result['export']['source_record_sha256'], self.store().get(key, 1)['record_sha256'])
        self.assertEqual(result['export']['draft'], self.before)
        self.assertNotIn(str(self.s.comfy_root), result['export_json'])
        self.assertNotIn(self.s.comfy_url, result['export_json'])
        self.assertNotIn('runtime', result['export'])
        self.assertIs(result['generation_submitted'], False)

    def test_unavailable_runtime_or_inputs_do_not_prevent_read_only_inspection(self):
        key = self.revisions()
        from studio_workflow.setup_drafts import SetupDrafts
        with patch.object(SetupDrafts, '_check_record', side_effect=AssertionError('availability probe')), \
             patch.object(self.s, 'asset_reference', side_effect=AssertionError('copy')):
            self.s.backends.busy = True
            self.page(key)
            self.history().compare(key, 1, 2, workspace_id=self.scope)
            self.history().export_revision(key, 1, workspace_id=self.scope)

    def test_reads_succeed_on_query_only_connection_without_schema_or_receipt_writes(self):
        key = self.revisions()
        original = self.s.assets.connection
        @contextmanager
        def readonly():
            with original() as db:
                db.execute('PRAGMA query_only=ON')
                yield db
        with patch.object(self.s.assets, 'connection', readonly):
            self.page(key)
            self.history().compare(key, 1, 2, workspace_id=self.scope)
            self.history().export_revision(key, 1, workspace_id=self.scope)
            result = route(self.url(key, 'history'), None, self.s)
            self.assertEqual(result['head_revision'], 2)

    def test_corruption_is_refused_before_returning_partial_page(self):
        key = self.revisions(3)
        with self.s.assets.connection() as db:
            db.execute('UPDATE setup_versions_v1 SET bytes=bytes+1 WHERE draft_id=? AND revision=2', (key,))
        with self.assertRaisesRegex(ValueError, 'integrity|bytes|corrupt'):
            self.page(key)

    def test_oversized_record_and_scalar_fields_are_refused(self):
        key = self.revisions(1)
        with self.s.assets.connection() as db:
            db.execute('UPDATE setup_versions_v1 SET record=? WHERE draft_id=?', ('x' * (1024*1024+1), key))
        with self.assertRaisesRegex(ValueError, 'bound|large|integrity'):
            self.page(key)

    def test_missing_revision_is_not_silently_skipped(self):
        key = self.revisions(3)
        with self.s.assets.connection() as db:
            db.execute('DELETE FROM setup_versions_v1 WHERE draft_id=? AND revision=2', (key,))
        with self.assertRaisesRegex(ValueError, 'contiguous|history|integrity'):
            self.page(key)

    def test_head_and_page_rows_share_one_snapshot_during_interleaved_write(self):
        key = self.revisions(2)
        owner = self.s.assets._check_scope
        def scope_read(db, expected):
            result = owner(db, expected)
            # Separate connection commits after this transaction established its snapshot.
            with patch.object(self.s.assets, '_check_scope', owner):
                self.command('replace', draft_id=key, expected_revision=2, draft=self.before)
            return result
        with patch.object(self.s.assets, '_check_scope', scope_read):
            result = self.page(key)
        self.assertEqual(result['head_revision'], 2)
        self.assertEqual([r['revision'] for r in result['revisions']], [2, 1])
        self.assertEqual(self.store().get(key)['head_revision'], 3)

    def url(self, key, action, **values):
        return '/api/workflow-studio/setup-drafts/' + key + '/' + action + '?' + urlencode(dict(workspace_id=self.scope, **values))

    def test_http_read_routes_and_strict_query_validation(self):
        key = self.revisions()
        self.history()  # Fail causally before attempting new routes on the parent.
        self.assertEqual(route(self.url(key, 'history', limit=1), None, self.s)['revisions'][0]['revision'], 2)
        self.assertEqual(route(self.url(key, 'compare', left=1, right=2), None, self.s)['right_revision'], 2)
        self.assertEqual(route(self.url(key, 'export', revision=1), None, self.s)['export']['revision'], 1)
        base = self.url(key, 'history')
        for bad in [base+'&workspace_id=x', base+'&unknown=x', base+'#fragment', base+'&limit=01', base+'&limit=true']:
            with self.subTest(path=bad), self.assertRaises(ValueError): route(bad, None, self.s)
        with self.assertRaises(ValueError): route(base, {}, self.s)
        with self.assertRaises(ValueError): route('/api/workflow-studio/setup-drafts?limit=2', None, self.s)

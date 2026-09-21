"""Source specificity is independent of resource-pin applicability; no inference."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from studio_workflow import guidance as G
from test_bundle_guidance import fixture

ROOT = Path(__file__).resolve().parents[1]
PIN = 'a' * 40


class GuidanceSourceScopeTests(unittest.TestCase):
    def setUp(self):
        self.p, self.g, self.m, self.k = fixture()
        self.source = self.k['guidance']['claims'][0]['source']

    def report(self):
        return G.explain(self.p, self.g, {}, self.k, self.m, today='2026-09-18')

    def test_legacy_matching_pins_do_not_infer_source_specificity(self):
        report = self.report()
        row = report['claims'][0]
        self.assertEqual(row.get('source_scope'), 'unrecorded')
        self.assertEqual(row['applicability'], 'applies')
        self.assertIn('Source scope is unrecorded', ' '.join(row['reasons']))
        self.assertFalse(report['generation_submitted'])
        self.assertTrue(report['authoring_only'])
        self.assertNotIn('scope', self.source)

    def test_family_scope_remains_family_even_with_exact_revision_and_pins(self):
        self.source.update(scope='family', revision=PIN)
        row = self.report()['claims'][0]
        self.assertEqual(row['source_scope'], 'family')
        self.assertEqual(row['applicability'], 'applies')
        self.assertIn('not exact-version qualification', ' '.join(row['reasons']))

    def test_explicit_pinned_scopes_are_declared_not_authenticated(self):
        for scope in ('exact_version', 'local_workflow'):
            for pin in (PIN, 'b' * 64, 'sha256:' + 'c' * 64, 'civitai-version:12345'):
                with self.subTest(scope=scope, pin=pin):
                    self.source.update(scope=scope, revision=pin)
                    row = self.report()['claims'][0]
                    self.assertEqual(row['source_scope'], scope)
                    self.assertIn('not source authentication', ' '.join(row['reasons']))
                    self.assertEqual(row['source']['revision'], pin)

    def test_specific_scope_rejects_missing_or_mutable_revision(self):
        for scope in ('exact_version', 'local_workflow'):
            for pin in (None, 'main', 'latest', 'v1.1', '2026-09-18', 'a' * 39, 'sha256:no', 'civitai-version:0'):
                with self.subTest(scope=scope, pin=pin):
                    self.source.update(scope=scope, revision=pin)
                    with self.assertRaisesRegex(ValueError, 'Specific source scope needs'):
                        G.validate_claim(self.k['guidance']['claims'][0])
                    report = self.report()
                    self.assertEqual(report['claims'], [])
                    self.assertTrue(report['diagnostics'])

    def test_invalid_scope_types_and_unknown_fields_are_rejected(self):
        for value in (None, False, 1, [], {}, '', 'promoted', 'Exact_Version'):
            with self.subTest(value=value):
                self.source['scope'] = value
                with self.assertRaises(ValueError):
                    G.validate_claim(self.k['guidance']['claims'][0])
        self.source['scope'] = 'unrecorded'
        self.source['accepted'] = True
        with self.assertRaises(ValueError):
            G.validate_claim(self.k['guidance']['claims'][0])

    def test_explicit_unrecorded_is_supported_without_inventing_a_revision(self):
        self.source['scope'] = 'unrecorded'
        row = self.report()['claims'][0]
        self.assertEqual(row['source_scope'], 'unrecorded')
        self.assertIsNone(row['source']['revision'])

    def test_scope_cannot_override_resource_hash_mismatch(self):
        self.source.update(scope='exact_version', revision=PIN)
        self.m['assets'][0]['sha256'] = 'f' * 64
        row = self.report()['claims'][0]
        self.assertEqual(row['applicability'], 'not_applicable')
        self.assertIn('Catalog file version differs', ' '.join(row['reasons']))

    def test_expiry_remains_independent_of_exact_scope(self):
        self.source.update(scope='exact_version', revision=PIN)
        self.k['guidance']['claims'][0]['review_after'] = '2026-09-17'
        row = self.report()['claims'][0]
        self.assertTrue(row['review_due'])
        self.assertEqual(row['source_scope'], 'exact_version')

    def test_scope_changes_context_identity_and_return_value_is_detached(self):
        original = copy.deepcopy([self.p, self.g, self.m, self.k])
        first = self.report()
        self.assertEqual([self.p, self.g, self.m, self.k], original)
        self.source.update(scope='family', revision=PIN)
        second = self.report()
        self.assertNotEqual(first['context_sha256'], second['context_sha256'])
        second['claims'][0]['source']['scope'] = 'unrecorded'
        self.assertEqual(self.source['scope'], 'family')

    def test_scope_does_not_choose_between_conflicting_recommendations(self):
        self.source.update(scope='family')
        other = copy.deepcopy(self.k['guidance']['claims'][0])
        other['id'] = 'different'
        other['source'].update(scope='exact_version', revision=PIN)
        other['settings'][0]['recommended'] = {'values': [8]}
        self.k['guidance']['claims'].append(other)
        report = self.report()
        self.assertEqual(report['conflicts'], [{'target': '3.steps', 'claims': ['accelerator', 'different']}])
        self.assertEqual([c['checks'][0]['current'] for c in report['claims']], [15, 15])

    def test_cli_surfaces_legacy_source_scope_without_generation(self):
        result = subprocess.run([sys.executable, '-m', 'studio_workflow.guidance',
                                 '--repo-root', str(ROOT), '--preset', 'anima-artist-stack'],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['claims'])
        self.assertTrue(all(c.get('source_scope') == c['source'].get('scope', 'unrecorded') for c in report['claims']))
        self.assertFalse(report['generation_submitted'])


if __name__ == '__main__':
    unittest.main()

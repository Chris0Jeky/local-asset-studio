"""Evidence breadth cannot exceed the retained observations that establish it."""
import unittest

from studio_workflow import setup_compatibility as C
import test_setup_compatibility_edges as E


class SetupCompatibilitySourceBoundTests(unittest.TestCase):
    def test_gallery_independent_sources_cannot_exceed_observations(self):
        inflated = E.claim(
            kind='gallery_co_use',
            observations=3,
            independent_sources=4,
            source={
                'locator': 'Reviewed retained gallery bundle',
                'revision': 'sha256:' + 'b' * 64,
                'retrieved_at': '2026-09-21',
            },
        )
        with self.assertRaisesRegex(ValueError, 'independent|observations'):
            C.validate_evidence(inflated)

        result = C.evaluate(E.request([inflated]))
        row = result['candidates'][0]
        self.assertEqual(row['status'], 'possible')
        self.assertEqual(row['evidence_summary']['qualified_gallery_claims'], 0)
        self.assertIn('invalid_evidence',
                      [item['code'] for item in result['diagnostics']])


if __name__ == '__main__':
    unittest.main()

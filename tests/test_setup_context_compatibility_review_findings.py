"""Review regressions for live-context ownership and source-report integrity."""
from __future__ import annotations

import copy
import unittest

import test_setup_context_compatibility as F
from studio_workflow import setup_context_compatibility as L


class SetupContextCompatibilityReviewFindings(unittest.TestCase):
    def test_unverified_file_ignores_stale_slot_presence_claim(self):
        live = F.context()
        live['assets'][0].update(
            verified=False,
            verification='explicit-reverification-required',
        )
        target = F.slot(capabilities=['local-file:' + F.FILE_ID])

        result = L.evaluate(F.request(live=live, target=target))

        self.assertEqual(F.row(result)['status'], 'needs_review')
        self.assertIn(
            'required_capability_unknown',
            [item['code'] for item in F.row(result)['unknowns']],
        )

    def test_backend_switch_ignores_stale_slot_presence_claim(self):
        live = F.context(backend_id='secondary', switching=True)
        target = F.slot(capabilities=['backend:primary'])

        result = L.evaluate(F.request(live=live, target=target))

        self.assertEqual(F.row(result)['status'], 'needs_review')
        self.assertIn(
            'backend_switching',
            [item['code'] for item in result['diagnostics']],
        )

    def test_partial_schema_ignores_stale_slot_absence_claim(self):
        live = F.context(
            node_classes=[],
            schema_complete=False,
            schema_revision=None,
        )
        target = F.slot(known_absent_capabilities=['node:LoraLoader'])

        result = L.evaluate(F.request(live=live, target=target))

        self.assertEqual(F.row(result)['status'], 'needs_review')
        self.assertIn(
            'node_unknown',
            [item['code'] for item in result['diagnostics']],
        )

    def test_edited_source_candidate_is_rejected_against_retained_fingerprint(self):
        source = F.source_candidate()
        source['candidate'] = copy.deepcopy(source['candidate'])
        source['candidate']['architecture'] = 'flux.1-dev'
        source['candidate']['base_lineage'] = 'flux.1-dev'

        with self.assertRaisesRegex(ValueError, 'fingerprint|context|tamper'):
            L.evaluate(F.request(source=source))


if __name__ == '__main__':
    unittest.main()

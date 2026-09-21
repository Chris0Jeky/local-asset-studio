"""Review regressions for live-context ownership and source-report integrity."""
from __future__ import annotations

import copy
import unittest

import test_setup_context_compatibility as F
from studio_workflow import setup_context_compatibility as L
from studio_workflow import source_compatibility as S


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

    def test_review_revision_must_remain_a_content_addressed_review_pin(self):
        source = F.source_candidate()
        source['review_revision'] = 'civitai-version:101'
        source['context_sha256'] = S.candidate_report_digest(source)

        with self.assertRaisesRegex(ValueError, 'review revision|sha256|review pin'):
            L.evaluate(F.request(source=source))

    def test_only_the_selected_loader_is_an_implicit_node_requirement(self):
        source = F.source_candidate(loaders=[
            'LoraLoader.lora_name',
            'AlternativeLoraLoader.lora_name',
        ])
        source['context_sha256'] = S.candidate_report_digest(source)
        live = F.context(node_classes=['LoraLoader'])

        result = L.evaluate(F.request(
            source=source,
            live=live,
            bind=F.binding(required_node_classes=['LoraLoader']),
        ))

        self.assertEqual(F.row(result)['status'], 'recommended')
        self.assertNotIn(
            'node:AlternativeLoraLoader',
            result['compatibility_input']['candidates'][0]['requires'],
        )

    def test_unknown_loader_allows_a_truthful_empty_node_binding(self):
        source = F.source_candidate(loaders=[], requires=[])
        source['context_sha256'] = S.candidate_report_digest(source)

        result = L.evaluate(F.request(
            source=source,
            bind=F.binding(required_node_classes=[]),
        ))

        self.assertEqual(F.row(result)['status'], 'needs_review')
        self.assertIn(
            'loader_unknown',
            [item['code'] for item in F.row(result)['unknowns']],
        )


if __name__ == '__main__':
    unittest.main()

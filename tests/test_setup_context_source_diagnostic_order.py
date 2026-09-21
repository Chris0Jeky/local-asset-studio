"""Sealed source reports must survive consumer-side canonical ordering."""
from __future__ import annotations

import copy
import unittest

import test_setup_context_compatibility as context_fixture
import test_setup_source_evidence as source_fixture
from studio_workflow import setup_context_compatibility as live_context
from studio_workflow import source_compatibility as source_adapter
from studio_workflow.core import canonical


class SetupContextSourceOrderingTests(unittest.TestCase):
    def test_adapter_output_with_unsorted_source_diagnostics_verifies(self):
        retained = source_fixture.report()
        retained['diagnostics'] = [
            {'code': 'zeta', 'message': 'Retained later diagnostic.'},
            {'code': 'alpha', 'message': 'Retained earlier diagnostic.'},
        ]
        adapted = source_adapter.adapt(source_fixture.request(source=retained))

        result = live_context.evaluate(context_fixture.request(source=adapted))

        self.assertEqual(context_fixture.row(result)['status'], 'recommended')
        source_diagnostics = [
            item for item in result['diagnostics']
            if item.get('origin') == 'source'
        ]
        self.assertEqual(
            [item['code'] for item in source_diagnostics],
            ['alpha', 'zeta'],
        )

    def test_adapter_output_with_provider_ordered_observations_verifies(self):
        first = source_fixture.report()['combinations'][0]
        first['distinct_observations'] = 9
        first['distinct_posts'] = 9
        second = copy.deepcopy(first)
        second['source_scope'] = source_fixture.source_scope('civitai.red', '31')
        second['receipt_sha256s'] = ['f' * 64]
        second['distinct_observations'] = 4
        second['distinct_posts'] = 4
        retained = source_fixture.report(combinations=[first, second])

        adapted = source_adapter.adapt(source_fixture.request(source=retained))
        self.assertEqual(
            adapted['source_observations'],
            sorted(adapted['source_observations'], key=canonical),
        )

        result = live_context.evaluate(context_fixture.request(source=adapted))

        self.assertEqual(context_fixture.row(result)['status'], 'recommended')
        source_observations = [
            item for item in result['observations']
            if 'source_scope' in item
        ]
        self.assertEqual(len(source_observations), 2)


if __name__ == '__main__':
    unittest.main()

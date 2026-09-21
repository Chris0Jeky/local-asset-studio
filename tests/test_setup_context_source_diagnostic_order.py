"""A source adapter report must survive consumer-side canonical ordering."""
from __future__ import annotations

import unittest

import test_setup_context_compatibility as context_fixture
import test_setup_source_evidence as source_fixture
from studio_workflow import setup_context_compatibility as live_context
from studio_workflow import source_compatibility as source_adapter


class SetupContextSourceDiagnosticOrderTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()

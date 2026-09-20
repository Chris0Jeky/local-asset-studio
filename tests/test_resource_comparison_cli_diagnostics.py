"""CLI diagnostics must not invent source-integrity verdicts for report-only failures."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_cli():
    path = ROOT / 'scripts/compare-resource-observations.py'
    spec = importlib.util.spec_from_file_location('comparison_cli_integrity_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComparisonCliDiagnosticTests(unittest.TestCase):
    def test_post_inspection_report_size_refusal_has_no_source_integrity_verdict(self):
        cli = load_cli()
        error = cli.EvidenceError('report_too_large')
        output = io.StringIO()
        with patch.object(cli, 'compare_observations', side_effect=error), contextlib.redirect_stdout(output):
            code = cli.main(['pairs.json'])
        self.assertEqual(code, 2)
        value = json.loads(output.getvalue())
        self.assertEqual(value['state'], 'report_unavailable')
        self.assertEqual(value['reason'], 'report_too_large')
        self.assertNotIn('integrity', value)
        self.assertFalse(value['qualified_benchmark'])
        self.assertFalse(value['execution_authority'])

    def test_existing_directory_plan_path_is_invalid_not_incomplete(self):
        cli = load_cli()
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli.main([tmp])
        self.assertEqual(code, 2)
        value = json.loads(output.getvalue())
        self.assertEqual(value['state'], 'report_unavailable')
        self.assertEqual(value['reason'], 'file_not_regular')
        self.assertEqual(value['integrity'], 'invalid')

    def test_absent_plan_path_remains_incomplete(self):
        cli = load_cli()
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'missing.json'
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli.main([str(missing)])
        self.assertEqual(code, 2)
        value = json.loads(output.getvalue())
        self.assertEqual(value['state'], 'report_unavailable')
        self.assertEqual(value['reason'], 'artifact_missing')
        self.assertEqual(value['integrity'], 'incomplete')


if __name__ == '__main__':
    unittest.main()

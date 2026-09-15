"""Truthful producer attribution, cross-lane aggregation and real-producer shape."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import inference_trace as trace

FIXTURE = Path(__file__).parent / 'fixtures/inference_trace_cpu.json'


def wire(events=(), **extra):
    return json.dumps(dict(schemaVersion=1, traceEvents=list(events), **extra)).encode()


def span(tid):
    return dict(ph='X', cat='kernel', name='fixture kernel', pid=0, tid=tid, ts=0, dur=100)


class TraceContractTests(unittest.TestCase):
    def test_reader_format_does_not_attest_producer(self):
        report = trace.summarize_trace(wire())
        self.assertNotIn('format', report)
        self.assertEqual(report['reader_format'], 'pytorch-kineto-chrome-x/v1')
        self.assertEqual(report['producer_identity'], 'unverified')
        self.assertEqual(report['schema'], 'studio.inference-trace-summary/v2')

    def test_operator_row_discloses_cross_lane_aggregation(self):
        report = trace.summarize_trace(wire([span(1), span(2), span(2)]))
        row = report['operators'][0]
        self.assertEqual(row['inclusive_duration_ns'], 300000)
        self.assertEqual(row['max_duration_ns'], 100000)
        self.assertEqual(row.get('lane_count'), 2)
        self.assertEqual(row.get('aggregation'), 'category_and_name_across_lanes')
        self.assertIn('operator_totals_aggregate_across_lanes', report['limitations'])
        self.assertIsNone(report['job_wall_time_ns'])

    def test_container_depth_boundary_counts_root_once(self):
        nested = []
        for _ in range(30): nested = [nested]
        trace.summarize_trace(wire(extra=nested))  # root + 31 arrays = 32
        with self.assertRaisesRegex(trace.TraceError, '^trace_json_invalid$'):
            trace.summarize_trace(wire(extra=[nested]))

    def test_redacted_real_cpu_producer_structure_and_counts(self):
        raw = FIXTURE.read_bytes(); document = json.loads(raw)
        self.assertIn('deviceProperties', document)
        self.assertIn('baseTimeNanoseconds', document)
        self.assertTrue(any('args' in row for row in document['traceEvents']))
        self.assertTrue(any(row.get('name') == 'Record Window End' for row in document['traceEvents']))
        report = trace.summarize_trace(raw)
        self.assertEqual(report['input_events'], 19)
        self.assertEqual(report['recognized_events'], 8)
        self.assertEqual(report['ignored_events'], 11)
        self.assertEqual(report['device_timing']['status'], 'unavailable')
        self.assertEqual(report.get('producer_identity'), 'unverified')
        self.assertNotIn('traceName', report)

    def test_synthetic_flows_and_device_metadata_are_ignored_not_attested(self):
        document = json.loads(FIXTURE.read_bytes())
        document['deviceProperties'] = [{'name': 'CANARY-not-a-real-device'}]
        document['traceEvents'] += [dict(ph=ph, cat='ac2g', name='CANARY-flow', id=1,
                                         pid=0, tid=0, ts=1, args={'CANARY': 'private'})
                                    for ph in ('s', 'f')]
        report = trace.summarize_trace(json.dumps(document).encode())
        self.assertEqual(report['ignored_events'], 13)
        self.assertEqual(report['recognized_events'], 8)
        self.assertNotIn('CANARY', json.dumps(report))
        self.assertEqual(report['device_timing']['status'], 'unavailable')


if __name__ == '__main__': unittest.main()

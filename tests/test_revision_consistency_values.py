"""Pure request/revision facts stay independent of SQLite and domain lifecycles."""
from pathlib import Path
import unittest

from studio_workflow.revision_consistency import (
    RequestState,
    byte_budget,
    canonical_sha256,
    canonical_value,
    classify_request,
    compare_head,
    stored_value,
)


class RevisionConsistencyValueTests(unittest.TestCase):
    def test_internal_envelope_hash_does_not_apply_the_payload_decode_limit(self):
        payload = {'value': 'x' * (1024 * 1024)}
        self.assertEqual(len(canonical_sha256(payload)), 64)
        with self.assertRaises(ValueError):
            canonical_value(payload)

    def test_canonical_value_binds_normalized_input_bytes_once(self):
        left = canonical_value({'b': [2, 1], 'a': {'value': 'α'}})
        right = canonical_value({'a': {'value': 'α'}, 'b': [2, 1]})
        self.assertEqual(left.value, right.value)
        self.assertEqual(left.raw, right.raw)
        self.assertEqual(left.sha256, right.sha256)
        self.assertEqual(left.bytes, len(left.raw))
        self.assertEqual(left.raw.decode(), '{"a":{"value":"α"},"b":[2,1]}')

    def test_canonical_value_retains_strict_decoder_failures(self):
        too_deep = 0
        for _ in range(50):
            too_deep = [too_deep]
        with self.assertRaises(ValueError):
            canonical_value({'too_deep': too_deep})
        with self.assertRaises(ValueError):
            canonical_value({'bad': float('nan')})

    def test_stored_value_decodes_strict_json_and_reports_digest_match(self):
        bound = canonical_value({'value': [1, 2]})
        exact = stored_value(bound.raw, bound.sha256)
        changed = stored_value(bound.raw, '0' * 64)
        self.assertEqual(exact.value, {'value': [1, 2]})
        self.assertTrue(exact.matches)
        self.assertFalse(changed.matches)
        self.assertEqual(changed.observed_sha256, bound.sha256)
        with self.assertRaises(ValueError):
            stored_value(b'{"value":1,"value":2}', bound.sha256)

    def test_request_state_is_absent_replay_or_conflict(self):
        self.assertIs(classify_request(None, 'a'), RequestState.ABSENT)
        self.assertIs(classify_request('a', 'a'), RequestState.REPLAY)
        self.assertIs(classify_request('a', 'b'), RequestState.CONFLICT)

    def test_head_comparison_retains_current_digest_for_domain_errors(self):
        equal = compare_head(4, 4, 'a' * 64)
        stale = compare_head(3, 4, 'b' * 64)
        self.assertTrue(equal.matches)
        self.assertFalse(stale.matches)
        self.assertEqual((stale.expected, stale.current, stale.current_sha256), (3, 4, 'b' * 64))

    def test_byte_budget_keeps_exact_boundary_and_one_byte_over_distinct(self):
        exact = byte_budget(9, 1, 10)
        over = byte_budget(9, 2, 10)
        self.assertEqual(exact.total, 10)
        self.assertTrue(exact.fits)
        self.assertEqual(over.total, 11)
        self.assertFalse(over.fits)

    def test_module_has_no_storage_or_domain_lifecycle_ownership(self):
        module = __import__('studio_workflow.revision_consistency', fromlist=['x'])
        source = Path(module.__file__).read_text(encoding='utf-8')
        for forbidden in ('AssetWorkspace', 'sqlite3', '.execute(', 'BEGIN ',
                          'workflow_', 'setup_', 'checking', 'staging'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()

"""Malformed pagination stays unknown without discarding retained image evidence (#836)."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_civitai_composition as fixtures

C = fixtures.C


def query(**values):
    return {'modelVersionId': '101', 'withMeta': 'true', 'browsingLevel': '31', **values}


class PaginationEvidenceTests(unittest.TestCase):
    def assert_unknown(self, value, code):
        original = copy.deepcopy(value)
        result = C.normalize(value)
        self.assertFalse(result['coverage_complete'])
        self.assertIn(code, [row['code'] for row in result['diagnostics']])
        self.assertEqual(len(result['image_observations']), 1)
        self.assertEqual(result['image_observations'][0]['image_id'], 1)
        self.assertFalse(result['generation_submitted'])
        self.assertFalse(result['network_performed'])
        self.assertEqual(value, original)
        return result

    def test_unsupported_query_cursors_preserve_receipt_and_images(self):
        for cursor in (1, 0, True, False, [], ['next'], ['a', 'b'], ' next ', '\t'):
            with self.subTest(cursor=cursor):
                value = fixtures.request([fixtures.page(query=query(cursor=cursor))])
                result = self.assert_unknown(value, 'invalid_pagination_query')
                self.assertEqual(result['source_receipts'][1]['query']['cursor'], cursor)

    def test_malformed_metadata_preserves_valid_image_observations(self):
        for metadata in ([], 'not an object', 1, True):
            with self.subTest(metadata=metadata):
                value = fixtures.request()
                value['image_pages'][0]['payload']['metadata'] = metadata
                self.assert_unknown(value, 'pagination_metadata_invalid')

    def test_noncanonical_pagination_query_keys_are_not_silently_roots(self):
        for key, raw in (('Page', 2), ('CURSOR', 'next'), ('Limit', 25),
                         ('cUrSoR', ''), ('PAGE', 1)):
            with self.subTest(key=key):
                value = fixtures.request([fixtures.page(query=query(**{key: raw}))])
                result = self.assert_unknown(value, 'pagination_query_noncanonical')
                self.assertEqual(result['source_receipts'][1]['query'][key], raw)

    def test_invalid_page_counter_types_never_establish_complete_coverage(self):
        for field in ('currentPage', 'totalPages'):
            for raw in (None, True, False, '1', 1.0, 0, -1, [], {}):
                with self.subTest(field=field, raw=raw):
                    metadata = {'nextCursor': None, 'currentPage': 1, 'totalPages': 1, field: raw}
                    self.assert_unknown(fixtures.request([fixtures.page(metadata=metadata)]),
                                        'pagination_counters_invalid')

    def test_incomplete_or_contradictory_page_counters_remain_unknown(self):
        for metadata in ({'currentPage': 1}, {'totalPages': 1},
                         {'currentPage': 2, 'totalPages': 1}):
            with self.subTest(metadata=metadata):
                self.assert_unknown(fixtures.request([fixtures.page(metadata=metadata)]),
                                    'pagination_counters_invalid')

    def test_later_page_metadata_cannot_invent_a_root_without_an_incoming_cursor(self):
        metadata = {'nextCursor': None, 'currentPage': 2, 'totalPages': 2}
        self.assert_unknown(fixtures.request([fixtures.page(metadata=metadata)]),
                            'pagination_page_unverified')

    def test_unsupported_cursor_does_not_join_a_valid_retained_chain(self):
        root = fixtures.page(metadata={'nextCursor': '2'})
        later = fixtures.page([fixtures.image(2, 22)], query=query(cursor=2), sha='d' * 64)
        result = C.normalize(fixtures.request([root, later]))
        self.assertFalse(result['coverage_complete'])
        self.assertEqual([row['image_id'] for row in result['image_observations']], [1, 2])
        self.assertIn('invalid_pagination_query', [row['code'] for row in result['diagnostics']])
        self.assertIn('pagination_incomplete', [row['code'] for row in result['diagnostics']])

    def test_valid_root_and_connected_string_cursor_chain_remain_complete(self):
        for root_cursor in (None, ''):
            with self.subTest(root_cursor=root_cursor):
                root_query = query() if root_cursor is None else query(cursor=root_cursor)
                root = fixtures.page(query=root_query,
                    metadata={'nextCursor': 'next', 'currentPage': 1, 'totalPages': 2})
                later = fixtures.page([fixtures.image(2, 22)], query=query(cursor='next'), sha='d' * 64,
                    metadata={'nextCursor': None, 'currentPage': 2, 'totalPages': 2})
                result = C.normalize(fixtures.request([root, later]))
                self.assertTrue(result['coverage_complete'])
                self.assertEqual(len(result['image_observations']), 2)
                self.assertFalse(any(row['code'].startswith('pagination_') for row in result['diagnostics']))

    def test_valid_first_page_counters_and_absent_counters_remain_complete(self):
        for metadata in ({'nextCursor': None}, {'currentPage': 1, 'totalPages': 1}):
            with self.subTest(metadata=metadata):
                self.assertTrue(C.normalize(fixtures.request([fixtures.page(metadata=metadata)]))['coverage_complete'])

    def test_cli_keeps_valid_evidence_and_reports_unknown_cursor_coverage(self):
        value = fixtures.request([fixtures.page(query=query(cursor=7))])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            output = io.StringIO()
            with patch('sys.stdout', output): status = C.main([str(path)])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(len(result['image_observations']), 1)

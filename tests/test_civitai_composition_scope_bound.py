"""Source-scope size bound contracts."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio_workflow import civitai_composition as C


SHA = 'a' * 64
FILE_SHA = 'B' * 64


def receipt(host='civitai.com', route='/api/v1/model-versions/101', query=None,
            outcome='ok', response_sha256=SHA):
    return {'host': host, 'route': route, 'query': {} if query is None else query,
            'retrieved_at': '2026-09-21T00:00:00Z',
            'response_sha256': response_sha256, 'etag': None, 'last_modified': None,
            'outcome': outcome, 'auth_context': 'anonymous'}


def model(air='urn:air:sdxl:lora:civitai:10@101'):
    return {'id': 101, 'modelId': 10, 'air': air, 'baseModel': 'Illustrious',
            'baseModelType': 'Standard', 'trainedWords': [],
            'model': {'id': 10, 'name': 'Example', 'type': 'LORA'},
            'files': [{'id': 1001, 'name': 'example.safetensors', 'sizeKB': 1,
                       'hashes': {'SHA256': FILE_SHA}}]}


def image(image_id=1, post_id=11, meta=None, stats=None):
    if meta is None:
        meta = {'civitaiResources': [
            {'type': 'lora', 'modelVersionId': 101, 'weight': 0.8},
            {'type': 'checkpoint', 'modelVersionId': 202}], 'steps': 24}
    return {'id': image_id, 'postId': post_id, 'username': 'alice',
            'modelVersionIds': [101, 202], 'meta': meta,
            'width': 1024, 'height': 1024, 'stats': {} if stats is None else stats}


def page(items=None, *, host='civitai.com', query=None, outcome='ok', sha='c' * 64):
    if query is None:
        query = {'modelVersionId': '101', 'withMeta': 'true', 'browsingLevel': '31'}
    return {'receipt': receipt(host, '/api/v1/images', query, outcome, sha),
            'payload': {'items': [image()] if items is None else items,
                        'metadata': {'nextCursor': None}}}


def request(pages=None, payload=None, model_outcome='ok'):
    return {'format': C.INPUT_FORMAT,
            'model_version': {'receipt': receipt(outcome=model_outcome),
                              'payload': model() if payload is None else payload},
            'image_pages': [page()] if pages is None else pages}


class CivitaiCompositionScopeBoundTests(unittest.TestCase):
    def test_oversized_scope_is_refused(self):
        query = {'modelVersionId': '101', 'withMeta': 'true', 'filter': ['x' * 1000] * 20}
        with self.assertRaisesRegex(ValueError, 'exceeds 16 KiB'):
            C.normalize(request([page(query=query)]))

    def test_oversized_scope_cli_is_invalid_snapshot(self):
        query = {'modelVersionId': '101', 'withMeta': 'true', 'filter': ['x' * 1000] * 20}
        value = request([page(query=query)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            out = io.StringIO()
            with redirect_stdout(out):
                code = C.main([str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())['error']['code'], 'invalid_snapshot')

    def test_scope_just_under_bound_is_retained(self):
        expected = ['x' * 1000] * 14
        query = {'modelVersionId': '101', 'withMeta': 'true', 'filter': copy.deepcopy(expected)}
        result = C.normalize(request([page(query=query)]))
        self.assertEqual(result['image_observations'][0]['source_scope']['query']['filter'], expected)

    def test_pagination_keys_do_not_count_toward_bound(self):
        # About 15.2 KB of filter scope; the 1,000-character cursor and the limit would push it past 16 KiB if counted.
        query = {'modelVersionId': '101', 'withMeta': 'true', 'filter': ['x' * 1000] * 15, 'cursor': 'y' * 1000, 'limit': 'z' * 1000}
        result = C.normalize(request([page(query=query)]))
        self.assertEqual(len(result['image_observations']), 1)
        self.assertNotIn('cursor', result['image_observations'][0]['source_scope']['query'])


if __name__ == '__main__': unittest.main()

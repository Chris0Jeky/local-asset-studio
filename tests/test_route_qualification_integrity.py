"""Malformed graph/pin evidence must not acquire a successful route identity."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_workflow import qualification as q


def fixture():
    def read(relative):
        return json.loads((ROOT / relative).read_text(encoding='utf-8'))
    preset = next(p for p in read('presets/catalog.json')['presets'] if p['id'] == 'anime')
    return preset, read(preset['graph']), read('models/library.json'), read('research/prompt-studio/profiles.json')


def connection(graph):
    for node_id, node in graph.items():
        for field, value in node['inputs'].items():
            if isinstance(value, list):
                return node_id, field, value
    raise AssertionError('The real graph needs a connection')


def target(inputs):
    return next(a for a in inputs[2]['assets'] if a['id'] == 'sdxl-animagine-40-opt')


class QualificationIntegrityTests(unittest.TestCase):
    def test_invalid_graph_links_refuse_including_disconnected_nodes(self):
        cases = ([], ['valid-node'], ['valid-node', 0, 'extra'], ['missing-node', 0],
                 ['valid-node', True], ['valid-node', False], ['valid-node', 0.0], ['valid-node', -1],
                 ['valid-node', 256], [1, 0], [[], 0], [{}, 0])
        for value in cases:
            for disconnected in (False, True):
                with self.subTest(value=value, disconnected=disconnected):
                    inputs = fixture()
                    node_id, field, original = connection(inputs[1])
                    if disconnected:
                        node_id, field = 'isolated-invalid', 'model'
                        inputs[1][node_id] = {'class_type': 'UnknownTransform', 'inputs': {}}
                    replacement = copy.deepcopy(value)
                    if replacement and replacement[0] == 'valid-node':
                        replacement[0] = original[0]
                    inputs[1][node_id]['inputs'][field] = replacement
                    with self.assertRaisesRegex(ValueError, 'graph link'):
                        q.inspect_route(*inputs)

    def test_invalid_graph_cli_has_a_refusal_envelope_not_a_success_report(self):
        inputs = fixture()
        node_id, field, value = connection(inputs[1])
        inputs[1][node_id]['inputs'][field] = ['missing-node', 0]
        documents = {'presets/catalog.json': {'presets': [inputs[0]]},
                     'models/library.json': inputs[2],
                     'research/prompt-studio/profiles.json': inputs[3],
                     inputs[0]['graph']: inputs[1]}
        def read(root, relative):
            return documents[relative], {'path': relative, 'sha256': 'a' * 64, 'bytes': 1}
        stream = io.StringIO()
        with patch.object(q, '_read', side_effect=read), contextlib.redirect_stdout(stream):
            code = q.main(['--root', str(ROOT), '--preset', 'anime'])
        self.assertEqual(code, 2)
        envelope = json.loads(stream.getvalue())
        self.assertEqual(set(envelope), {'error', 'generation_submitted', 'qualification_complete'})
        self.assertFalse(envelope['generation_submitted'])
        self.assertFalse(envelope['qualification_complete'])

    def test_invalid_pin_fields_are_retained_but_unresolved(self):
        cases = [('id', x) for x in ('BAD-ID', 'bad id', 'under_score', '', None, [])]
        cases += [('url', x) for x in (None, [], True, 'https://example.com/model',
                    'http://civitai.com/api/download/models/1', 'https://civitai.com.evil/model')]
        cases += [('bytes', x) for x in (True, False, 0, -1, 1.0)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                inputs = fixture()
                asset = target(inputs)
                asset[field] = value
                before = copy.deepcopy(inputs)
                report = q.inspect_route(*inputs)
                row = next(r for r in report['components'] if r['file'] == asset['file'])
                self.assertEqual(row['identity'], 'invalid_catalog_pin')
                self.assertIsNone(row['pin_sha256'])
                self.assertIsNone(row['library_declaration'])
                self.assertEqual(row['library_candidates'], [asset])
                self.assertTrue(any(d['code'] == 'unresolved_component_identity' and
                                    d['file'] == asset['file'] for d in report['diagnostics']))
                self.assertEqual(inputs, before)

    def test_unsourced_pin_requires_an_actual_explanation(self):
        for terms in (None, '', '   ', True, []):
            with self.subTest(terms=terms):
                inputs = fixture()
                asset = target(inputs)
                asset.update(url='', terms=terms)
                report = q.inspect_route(*inputs)
                row = next(r for r in report['components'] if r['file'] == asset['file'])
                self.assertEqual(row['identity'], 'invalid_catalog_pin')
                self.assertIsNone(row['pin_sha256'])

    def test_duplicate_pin_identity_is_not_resolved_by_a_different_file(self):
        inputs = fixture()
        asset = target(inputs)
        other = copy.deepcopy(asset)
        other['file'] = 'checkpoints/unrelated.safetensors'
        inputs[2]['assets'].append(other)
        row = next(r for r in q.inspect_route(*inputs)['components'] if r['file'] == asset['file'])
        self.assertEqual(row['identity'], 'invalid_catalog_pin')
        self.assertIsNone(row['library_declaration'])

    def test_wrong_suffix_does_not_become_a_pin(self):
        inputs = fixture()
        asset = target(inputs)
        old = asset['file']
        asset['file'] = 'checkpoints/model.txt'
        for node in inputs[1].values():
            if node['inputs'].get('ckpt_name') == old.split('/', 1)[1]:
                node['inputs']['ckpt_name'] = 'model.txt'
        if 'model_files' in inputs[0]:
            inputs[0]['model_files'] = [asset['file'] if p == old else p for p in inputs[0]['model_files']]
        row = next(r for r in q.inspect_route(*inputs)['components'] if r['file'] == asset['file'])
        self.assertEqual(row['identity'], 'invalid_catalog_pin')
        self.assertIsNone(row['pin_sha256'])

    def test_valid_pin_source_claims_do_not_grant_install_or_execution_authority(self):
        for url, terms in (('', 'Explicit manual copy; no transfer endpoint pinned'),
                           ('https://civitai.red/models/123?modelVersionId=456', ''),
                           ('https://huggingface.co/owner/repo/resolve/pin/model.safetensors', '')):
            with self.subTest(url=url):
                inputs = fixture()
                asset = target(inputs)
                asset.update(url=url, terms=terms)
                row = next(r for r in q.inspect_route(*inputs)['components'] if r['file'] == asset['file'])
                self.assertEqual(row['identity'], 'catalog_pin')
                self.assertEqual(row['library_declaration'], asset)
                self.assertEqual(row['pin_sha256'], asset['sha256'])

    def test_eight_valid_routes_remain_read_only(self):
        report = q.inspect_repository(ROOT, ['anima-portrait', 'anima-v1-baseline',
            'anime', 'pony', 'noob', 'qwen-1ref', 'qwen-2ref', 'qwen-3ref'])
        self.assertEqual(len(report['routes']), 8)
        self.assertFalse(report['generation_submitted'])
        for route in report['routes']:
            self.assertFalse(route['qualification_complete'])
            self.assertTrue(route['components'])
            self.assertIsNone(route['evidence']['installed'])


if __name__ == '__main__':
    unittest.main()

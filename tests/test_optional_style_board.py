"""Empty optional IP-Adapter boards retain the independently owned source. No inference."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_references import ref
import test_continuation as continuation_fixture

ROOT = Path(__file__).resolve().parents[1]


def optional_wai():
    preset = next(p for p in json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']
                  if p['id'] == 'restyle-wai')
    preset['reference_board']['min'] = 0  # Fixture only: the owner has not changed q-27.
    return preset, json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))


class OptionalBoardCompilerTests(unittest.TestCase):
    def test_empty_board_bypasses_both_model_consumers_without_losing_the_source(self):
        preset, graph = optional_wai()
        original = copy.deepcopy(graph)
        with patch.object(ref, 'image_record', side_effect=AssertionError('Empty board read bytes')):
            records = ref.compile_references(preset, graph, [], Path('unused'))
        removed = {'10', '30', '31', '19', '20', '21', '22', '14', '12', '13'}
        self.assertEqual(set(original) - set(graph), removed)
        self.assertEqual(graph['5']['inputs']['model'], ['9', 0])
        self.assertEqual(graph['51']['inputs']['model'], ['9', 0])
        for key in set(graph) - {'5', '51'}:
            self.assertEqual(graph[key], original[key], key)
        self.assertEqual([(r['slot'], r['file'], r['pruned']) for r in records],
                         [(1, None, True), (2, None, True), (3, None, True)])
        cap = continuation_fixture.continuation.capability(preset, graph)
        self.assertEqual((cap['consumes_source'], cap['source_input'], cap['board_min']),
                         (True, 'last_reference', 0))
        # Persisted positional placeholders recompile to exactly the same graph.
        _, restored = optional_wai()
        self.assertEqual(ref.compile_references(preset, restored, records, Path('unused')), records)
        self.assertEqual(restored, graph)

    def test_required_empty_board_still_refuses_before_mutation(self):
        preset, graph = optional_wai()
        preset['reference_board']['min'] = 1
        original = copy.deepcopy(graph)
        with self.assertRaisesRegex(ValueError, 'at least 1 picture'):
            ref.compile_references(preset, graph, [], Path('unused'))
        self.assertEqual(graph, original)

    def test_minimum_is_a_bounded_integer_not_truthiness(self):
        preset, _ = optional_wai()
        self.assertEqual(ref.board_spec(preset)['minimum'], 0)
        for bad in (False, True, -1, 4, 0.0, '0', None):
            with self.subTest(minimum=bad):
                preset['reference_board']['min'] = bad
                with self.assertRaisesRegex(ValueError, 'minimum'):
                    ref.board_spec(preset)

    def test_unknown_or_shared_graph_paths_refuse_without_partial_mutation(self):
        cases = {
            'board loader is also named source': lambda p, g: p.update(last_reference=['10', 'image']),
            'named source uses owned encoder': lambda p, g: p.update(last_reference=['19', 'image']),
            'independent negative embedding': lambda p, g: g['14']['inputs'].update(neg_embed=['15', 0]),
            'duplicate slot loader': lambda p, g: p['reference_slots'][1].update(binding=['10', 'image']),
            'unsupported dependent': lambda p, g: g.update(extra={'class_type':'SaveImage', 'inputs':{'images':['10', 0]}}),
            'shared combiner': lambda p, g: g['22']['inputs'].update(embed4=['11', 0]),
            'missing upstream model': lambda p, g: g['14']['inputs'].update(model=['gone', 0]),
            'non-link upstream model': lambda p, g: g['14']['inputs'].update(model='example-model'),
            'cyclic upstream model': lambda p, g: g['14']['inputs'].update(model=['5', 0]),
            'unknown adapter output': lambda p, g: g['51']['inputs'].update(model=['14', 1]),
            'non-image slot binding': lambda p, g: p['reference_slots'][0].update(binding=['10', 'mask']),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                preset, graph = optional_wai()
                mutate(preset, graph)
                before = copy.deepcopy(graph)
                with self.assertRaisesRegex(ValueError, 'optional board'):
                    ref.compile_references(preset, graph, [], Path('unused'))
                self.assertEqual(graph, before)

    def test_shared_auxiliary_loaders_are_kept_and_node_order_does_not_matter(self):
        preset, graph = optional_wai()
        graph['shared'] = {'class_type':'AnotherEncoder', 'inputs':{'ipadapter':['12', 0], 'clip_vision':['13', 0]}}
        reversed_graph = dict(reversed(list(copy.deepcopy(graph).items())))
        ref.compile_references(preset, graph, None, Path('unused'))
        ref.compile_references(preset, reversed_graph, None, Path('unused'))
        self.assertEqual(graph, reversed_graph)
        self.assertIn('12', graph)
        self.assertIn('13', graph)
        self.assertEqual(graph['shared']['inputs'], {'ipadapter':['12', 0], 'clip_vision':['13', 0]})

    def test_populated_optional_boards_keep_existing_compilation_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'style.png').write_bytes(continuation_fixture.png())
            for supplied in ([{}, {'file':'style.png'}, {}], [{'file':'style.png'}] * 3):
                with self.subTest(supplied=supplied):
                    optional, graph = optional_wai()
                    required, expected = optional_wai()
                    required['reference_board']['min'] = 1
                    result = ref.compile_references(optional, graph, supplied, root)
                    self.assertEqual(result, ref.compile_references(required, expected, supplied, root))
                    self.assertEqual(graph, expected)
                    self.assertIn('14', graph)
                    self.assertEqual(graph['14']['inputs']['weight'], 0.0)


class OptionalBoardContinuationTests(unittest.TestCase):
    # Reuse the retained-asset/SQLite fixture, not its tests or another server owner.
    setUp = continuation_fixture.ContinuationTests.setUp

    def test_prepare_and_runtime_recheck_preserve_the_named_source_and_its_claim(self):
        preset, _ = optional_wai()
        graph_path = self.root / preset['graph']
        shutil.copyfile(ROOT / preset['graph'], graph_path)
        catalog_path = self.root / 'presets/catalog.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        catalog['presets'].append(preset)
        catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
        claim = dict(self.claim, intent='restyle', preset_id=preset['id'],
                     template_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest())
        payload = dict(preset_id=preset['id'], parent_assets=[self.asset_id],
                       continuation=claim, references=[],
                       controls={'positive': 'An adult traveller holding a lantern.',
                                 'last_reference': self.attachment['file']})
        result = self.studio.preview(payload)
        self.assertFalse(result['submitted'])
        self.assertEqual(result['workflow']['11']['inputs']['image'], self.attachment['file'])
        self.assertNotIn('14', result['workflow'])
        for declared in (None, [{}], [{}, {}, {}]):
            self.assertEqual(self.studio.preview(dict(payload, references=declared))['workflow'], result['workflow'])
        # A short declaration is not permission to retain an authored board example.
        _, forged = optional_wai()
        with self.assertRaisesRegex(ValueError, 'empty style-board slot'):
            continuation_fixture.continuation.validate(self.studio, payload, preset, forged)
        # Preparation's existing zero-strength LoRA pass still owns the later 9 -> 8 bypass.
        self.assertEqual(result['workflow']['5']['inputs']['model'], ['8', 0])
        self.assertEqual(result['workflow']['51']['inputs']['model'], ['8', 0])
        job = self.studio.jobs[self.studio.create_job(payload, enqueue=False)['id']]
        self.assertEqual(job['continuation'], claim)
        self.assertEqual(job['parent_assets'], [self.asset_id])
        preset['_prepared_references'] = job['references']
        self.assertEqual(continuation_fixture.continuation.validate(
            self.studio, job, preset, job['graph'], check_runtime=True), claim)
        # Empty board is not permission to use the authored source, change parent or accept stale bytes.
        altered = copy.deepcopy(payload)
        altered['controls'].pop('last_reference')
        with self.assertRaisesRegex(ValueError, 'declared source input'):
            self.studio.prepare(altered)
        altered.pop('continuation')
        with self.assertRaisesRegex(ValueError, 'authored example picture cannot be queued'):
            self.studio.prepare(altered)
        altered = copy.deepcopy(payload)
        altered['parent_assets'] = []
        with self.assertRaisesRegex(ValueError, 'missing from lineage'):
            self.studio.prepare(altered)
        (self.studio.comfy_root / 'input' / self.attachment['file']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            continuation_fixture.continuation.validate(self.studio, job, preset, job['graph'], check_runtime=True)


class OptionalBoardFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is unavailable')
    def test_frontend_optional_board_contracts(self):
        result = subprocess.run(['node', '--test', str(ROOT / 'tests/optional_style_board.cjs')],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('# pass 5', result.stdout)

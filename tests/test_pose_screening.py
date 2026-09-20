"""Contracts for the corrected-pose screening plan; these tests never submit generation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_screening


def digest(char):
    return char * 64


def route(route_id, mechanism, representation, seed_base):
    pins = {
        'model': digest('1'),
        'encoder': digest('2'),
        'vae': digest('3'),
        'graph': digest('4'),
        'nodes': digest('5'),
        'runtime': digest('6'),
        'reference_transform': digest('7'),
        'prompt_dialect': digest('c'),
    }
    if mechanism == 'klein-geometry-reference':
        pins['renderer'] = digest('8')
        detector_behavior = 'not-applicable'
    elif mechanism == 'copy-pose-rgb':
        pins['lora'] = digest('9')
        detector_behavior = 'not-applicable'
    else:
        pins['controlnet'] = digest('a')
        pins['renderer'] = digest('b')
        detector_behavior = 'bypass-precomputed-guide'
    return {
        'id': route_id,
        'mechanism': mechanism,
        'input_representation': representation,
        'backend_id': 'primary',
        'detector_behavior': detector_behavior,
        'pins': pins,
        'noise_seeds': {
            'replicate_a': seed_base + 1,
            'replicate_b': seed_base + 2,
            'counterfactual': seed_base + 3,
        },
    }


CASE_ROWS = (
    ('familiar-difficult-bend', 'development', 'replicated-seeds', ('body_pose', 'camera')),
    ('unseen-crossed-legs', 'held-out', 'replicated-seeds', ('body_pose', 'anatomy_occlusion')),
    ('seated-support', 'held-out', 'replicated-seeds', ('body_pose', 'hands_contact_support')),
    ('overhead-reach', 'held-out', 'replicated-seeds', ('body_pose', 'anatomy_occlusion')),
    ('strong-camera-foreshortening', 'held-out', 'replicated-seeds', ('body_pose', 'camera')),
    ('hand-prop-contact', 'held-out', 'replicated-seeds', ('body_pose', 'hands_contact_support')),
    ('second-character-unseen-pose', 'held-out', 'replicated-seeds', ('body_pose', 'identity', 'outfit')),
    ('irrelevant-donor-counterfactual', 'held-out', 'paired-counterfactual', ('body_pose', 'ignored_facet_leakage')),
)


def manifest():
    cases = []
    for ordinal, (case_id, scope, slot_mode, observations) in enumerate(CASE_ROWS, 1):
        row = {
            'id': case_id,
            'ordinal': ordinal,
            'title': case_id.replace('-', ' '),
            'scope': scope,
            'slot_mode': slot_mode,
            'required_observations': list(observations),
        }
        if slot_mode == 'paired-counterfactual':
            row['pair_labels'] = ['baseline', 'variant']
            row['source_refs'] = {
                'baseline': 'local-source-8-baseline',
                'variant': 'local-source-8-variant',
            }
        else:
            row['source_ref'] = 'local-source-' + str(ordinal)
        cases.append(row)
    return {
        'schema': pose_screening.MANIFEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'campaign_id': 'corrected-pose-screening-synthetic',
        'candidate_cap': 48,
        'additional_image_attempt_cap': 0,
        'same_defect_repeat_limit': 2,
        'routes': [
            route('klein-geometry', 'klein-geometry-reference', 'precomputed-skeleton', 1000),
            route('copy-pose', 'copy-pose-rgb', 'rgb-pose-donor', 2000),
            route('sdxl-corrected-skeleton', 'sdxl-precomputed-skeleton', 'precomputed-skeleton', 3000),
        ],
        'cases': cases,
        'review_axes': list(pose_screening.REVIEW_AXES),
        'stop_conditions': list(pose_screening.STOP_CONDITIONS),
    }


class PoseScreeningTests(unittest.TestCase):
    def test_compiles_exact_48_cells_and_keeps_case_eight_paired(self):
        source = manifest()
        plan = pose_screening.compile_plan(source)
        self.assertEqual(plan['schema'], pose_screening.PLAN_SCHEMA)
        self.assertEqual(plan['candidate_count'], 48)
        self.assertEqual(plan['candidate_cap'], 48)
        self.assertEqual(len(plan['cells']), 48)
        self.assertEqual(len({cell['id'] for cell in plan['cells']}), 48)
        self.assertEqual(plan['authority'], 'none')
        self.assertFalse(plan['execution_authorized'])
        self.assertFalse(plan['generation_submitted'])
        self.assertEqual(plan['additional_image_attempt_cap'], 0)
        for route_id in ('klein-geometry', 'copy-pose', 'sdxl-corrected-skeleton'):
            cells = [cell for cell in plan['cells'] if cell['route_id'] == route_id]
            self.assertEqual(len(cells), 16)
            for ordinal in range(1, 8):
                pair = [cell for cell in cells if cell['case_ordinal'] == ordinal]
                self.assertEqual([cell['slot'] for cell in pair], ['replicate-a', 'replicate-b'])
                self.assertNotEqual(pair[0]['seed'], pair[1]['seed'])
                self.assertIsNone(pair[0]['pair_group'])
            pair = [cell for cell in cells if cell['case_ordinal'] == 8]
            self.assertEqual([cell['slot'] for cell in pair], ['baseline', 'variant'])
            self.assertEqual([cell['source_ref'] for cell in pair], [
                source['cases'][7]['source_refs']['baseline'],
                source['cases'][7]['source_refs']['variant'],
            ])
            self.assertNotEqual(pair[0]['source_ref'], pair[1]['source_ref'])
            self.assertEqual(pair[0]['seed'], pair[1]['seed'])
            self.assertEqual(pair[0]['pair_group'], pair[1]['pair_group'])

    def test_plan_is_deterministic_and_validates_against_manifest(self):
        source = manifest()
        first = pose_screening.compile_plan(source)
        second = pose_screening.compile_plan(copy.deepcopy(source))
        self.assertEqual(first, second)
        self.assertRegex(first['manifest_sha256'], r'^[0-9a-f]{64}$')
        self.assertRegex(first['plan_id'], r'^[0-9a-f]{64}$')
        self.assertEqual(pose_screening.validate_plan(first, source), first)
        changed = copy.deepcopy(first); changed['cells'][0]['seed'] += 1
        with self.assertRaisesRegex(ValueError, 'plan'):
            pose_screening.validate_plan(changed, source)

    def test_rejects_authority_or_hidden_attempt_budget(self):
        for patch in (
            {'authority': 'execute'},
            {'execution_authorized': True},
            {'generation_submitted': True},
            {'candidate_cap': 49},
            {'additional_image_attempt_cap': 1},
            {'same_defect_repeat_limit': 3},
        ):
            source = manifest(); source.update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                pose_screening.compile_plan(source)

    def test_rejects_case_protocol_drift_duplicates_and_unknown_axes(self):
        variants = []
        source = manifest(); source['cases'].pop(); variants.append(source)
        source = manifest(); source['cases'][7]['slot_mode'] = 'replicated-seeds'; source['cases'][7].pop('pair_labels'); variants.append(source)
        source = manifest(); source['cases'][0]['slot_mode'] = 'paired-counterfactual'; source['cases'][0]['pair_labels'] = ['baseline', 'variant']; variants.append(source)
        source = manifest(); source['cases'][1]['id'] = source['cases'][0]['id']; variants.append(source)
        source = manifest(); source['cases'][2]['ordinal'] = 2; variants.append(source)
        source = manifest(); source['cases'][3]['required_observations'] = ['body_pose', 'body_pose']; variants.append(source)
        source = manifest(); source['review_axes'].append('beauty_score'); variants.append(source)
        source = manifest(); source['stop_conditions'] = source['stop_conditions'][:-1]; variants.append(source)
        for source in variants:
            with self.subTest(case=source['cases'][-1]['id']), self.assertRaises(ValueError):
                pose_screening.compile_plan(source)

    def test_rejects_route_mismatch_unpinned_components_and_seed_aliasing(self):
        variants = []
        source = manifest(); source['routes'][1]['id'] = source['routes'][0]['id']; variants.append(source)
        source = manifest(); source['routes'][0]['pins']['model'] = 'bad'; variants.append(source)
        source = manifest(); del source['routes'][1]['pins']['lora']; variants.append(source)
        source = manifest(); source['routes'][2]['detector_behavior'] = 'route-native'; variants.append(source)
        source = manifest(); source['routes'][2]['input_representation'] = 'rgb-pose-donor'; variants.append(source)
        source = manifest(); source['routes'][0]['noise_seeds']['replicate_b'] = source['routes'][0]['noise_seeds']['replicate_a']; variants.append(source)
        source = manifest(); source['routes'][0]['noise_seeds']['counterfactual'] = True; variants.append(source)
        source = manifest(); source['routes'][0]['pins']['unexpected'] = digest('c'); variants.append(source)
        source = manifest(); source['routes'][0]['backend_id'] = 'primry'; variants.append(source)
        source = manifest(); source['routes'][0]['detector_behavior'] = 'route-native'; variants.append(source)
        source = manifest(); source['routes'][0]['input_representation'] = 'skeleton'; variants.append(source)
        for source in variants:
            with self.subTest(route=source['routes'][0]['id']), self.assertRaises(ValueError):
                pose_screening.compile_plan(source)

    def test_refuses_unbounded_or_noncanonical_manifest_data(self):
        variants = []
        source = manifest(); source['campaign_id'] = '../escape'; variants.append(source)
        source = manifest(); source['cases'][0]['source_ref'] = 'C:\\private\\source.png'; variants.append(source)
        source = manifest(); source['cases'][0]['title'] = 'x' * 201; variants.append(source)
        source = manifest(); source['routes'][0]['backend_id'] = ''; variants.append(source)
        source = manifest(); source['routes'].append(copy.deepcopy(source['routes'][0])); variants.append(source)
        for source in variants:
            with self.assertRaises(ValueError): pose_screening.compile_plan(source)

    def test_v1_manifest_requires_explicit_regeneration(self):
        source = manifest(); source['schema'] = pose_screening.LEGACY_MANIFEST_SCHEMA
        with self.assertRaisesRegex(ValueError, 'regenerate.*v2'):
            pose_screening.compile_plan(source)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/pose_screening.py'), *map(str, args)],
                              cwd=tempfile.gettempdir(), text=True, capture_output=True, timeout=15)

    def test_cli_writes_one_plan_without_overwrite_or_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'manifest.json'; output = root / 'plan.json'
            source.write_text(json.dumps(manifest()), encoding='utf-8')
            result = self.cli('plan', source, '--out', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout); saved = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(receipt['plan_id'], saved['plan_id'])
            self.assertEqual(receipt['candidate_count'], 48)
            self.assertFalse(receipt['generation_submitted'])
            before = output.read_bytes(); again = self.cli('plan', source, '--out', output)
            self.assertEqual(again.returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            self.assertFalse(json.loads(again.stderr)['generation_submitted'])

    def test_cli_validation_detects_tamper_and_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'manifest.json'; output = root / 'plan.json'
            source.write_text(json.dumps(manifest()), encoding='utf-8')
            result = self.cli('validate', source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['candidate_count'], 48)
            result = self.cli('plan', source, '--out', output); self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(output.read_text()); saved['cells'][0]['seed'] += 1
            output.write_text(json.dumps(saved), encoding='utf-8')
            result = self.cli('validate-plan', source, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn('plan', json.loads(result.stderr)['error'])


if __name__ == '__main__':
    unittest.main()

"""Offline design-contract tests; no images, model calls or live approval."""
from __future__ import annotations

import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.repair_proposal import ContractError, assess, read_proposal, transform


def proposal():
    return {
        'schema': 'studio.repair-proposal/v0',
        'source': {'sha256': 'a' * 64, 'revision': 'b' * 64, 'size': [640, 480]},
        'mode': 'localized',
        'context': {'box': [100, 80, 220, 240], 'scale': [4, 1],
                    'padding': [0, 0, 0, 0], 'alignment': 16},
        'instances': [{'id': 'actor-a', 'kind': 'character'}],
        'targets': ['actor-a'],
        'references': [{'instance_id': 'actor-a', 'role': 'identity', 'sha256': 'c' * 64}],
        'contacts': [],
        'masks': {'encoding': 'source-L-coverage-v1', 'edit': 'd' * 64,
                  'write': 'e' * 64, 'protect': 'f' * 64, 'subject': None},
        'intent': {'kind': 'anatomy', 'visibility': 'visible',
                   'synthesize_unseen': False, 'description': 'Reconnect the hand to its wrist.'},
        'limits': {'max_candidates': 2, 'max_analysis_calls': 1},
        'strategies': ['masked', 'native'],
    }


class RepairProposalTests(unittest.TestCase):
    def reject(self, value, code):
        with self.assertRaises(ContractError) as caught:
            assess(value)
        self.assertEqual(caught.exception.code, code)

    def test_valid_is_never_executable_or_approved(self):
        report = assess(proposal())
        self.assertFalse(report['executable'])
        self.assertEqual(report['authority'], 'none')
        self.assertEqual(report['pixel_validation'], 'not_performed')
        self.assertIn('actual-mask-support', report['required_runtime_checks'])

    def test_input_is_unchanged(self):
        original = proposal()
        before = copy.deepcopy(original)
        assess(original)
        self.assertEqual(original, before)

    def test_hash_is_key_order_independent(self):
        value = proposal()
        reordered = json.loads(json.dumps(value, sort_keys=True))
        self.assertEqual(assess(value)['proposal_sha256'], assess(reordered)['proposal_sha256'])

    def test_effective_change_changes_identity(self):
        value = proposal()
        first = assess(value)['proposal_sha256']
        value['masks']['write'] = '9' * 64
        self.assertNotEqual(first, assess(value)['proposal_sha256'])

    def test_unknown_field_cannot_assert_authority(self):
        for key in ['approved', 'execute', 'workflow', 'shell']:
            value = proposal()
            value[key] = True
            self.reject(value, 'fields')

    def test_missing_field_is_not_defaulted(self):
        value = proposal()
        del value['masks']['write']
        self.reject(value, 'fields')

    def test_version_is_explicit(self):
        value = proposal()
        value['schema'] = 'studio.repair-proposal/v1'
        self.reject(value, 'schema')

    def test_masks_cannot_be_inverse_alpha_by_accident(self):
        value = proposal()
        value['masks']['encoding'] = 'RGBA-inverse-alpha'
        self.reject(value, 'mask_encoding')

    def test_mask_hash_is_not_a_path(self):
        value = proposal()
        value['masks']['write'] = '../../private.png'
        self.reject(value, 'sha256')

    def test_required_mask_cannot_be_null(self):
        value = proposal()
        value['masks']['write'] = None
        self.reject(value, 'sha256')

    def test_optional_mattes_are_not_required(self):
        value = proposal()
        value['masks']['protect'] = None
        self.assertFalse(assess(value)['executable'])

    def test_boolean_is_not_an_integer(self):
        for section, field, replacement in [('source', 'size', [True, 480]),
                                             ('limits', 'max_candidates', True),
                                             ('context', 'scale', [True, 1])]:
            value = proposal()
            value[section][field] = replacement
            self.reject(value, 'integer')

    def test_large_source_is_bounded(self):
        value = proposal()
        value['source']['size'] = [10000, 10000]
        self.reject(value, 'pixels')

    def test_crop_bounds(self):
        for box in [[-1, 0, 50, 50], [0, 0, 641, 480], [4, 4, 4, 10], [0, 0, 10]]:
            value = proposal()
            value['context']['box'] = box
            self.reject(value, 'box')

    def test_fraction_and_padding_contract(self):
        result = transform([100, 100], {'box': [3, 5, 10, 14], 'scale': [3, 2],
                                      'padding': [2, 1, 3, 1], 'alignment': 1})
        self.assertEqual(result['resized_size'], [11, 14])
        self.assertEqual(result['work_size'], [16, 16])
        self.assertEqual(result['pixel_centres'], 'integer-centres-half-pixel-resize')

    def test_forward_inverse_coordinates_are_exact_rationals(self):
        for numerator in range(1, 8):
            for denominator in range(1, 6):
                result = transform([100, 100], {'box': [3, 5, 10, 14],
                    'scale': [numerator, denominator], 'padding': [2, 1, 3, 1], 'alignment': 1})
                for axis in ['x', 'y']:
                    scale = Fraction(*result['mapping'][axis]['scale'])
                    offset = Fraction(*result['mapping'][axis]['offset'])
                    for x in [Fraction(0), Fraction(7, 3), Fraction(99)]:
                        self.assertEqual(((x * scale + offset) - offset) / scale, x)

    def test_invalid_scale_and_alignment(self):
        for field, replacement, code in [('scale', [1, 0], 'integer'),
                                         ('scale', [1, 1000], 'rounded_size'),
                                         ('alignment', 7, 'alignment'),
                                         ('padding', [0, -1, 0, 0], 'integer')]:
            value = proposal()
            value['context'][field] = replacement
            self.reject(value, code)

    def test_padded_shape_must_match_declared_alignment(self):
        value = proposal()
        value['context']['padding'][0] = 1
        self.reject(value, 'alignment')

    def test_work_canvas_is_bounded(self):
        value = proposal()
        value['context']['scale'] = [64, 1]
        self.reject(value, 'pixels')

    def test_duplicate_instances_rejected(self):
        value = proposal()
        value['instances'].append(copy.deepcopy(value['instances'][0]))
        self.reject(value, 'duplicate')

    def test_unknown_target_and_reference_rejected(self):
        value = proposal()
        value['targets'] = ['other']
        self.reject(value, 'instance')
        value = proposal()
        value['references'][0]['instance_id'] = 'other'
        self.reject(value, 'instance')

    def test_reference_roles_not_relabelled(self):
        value = proposal()
        value['references'][0]['role'] = 'everything'
        self.reject(value, 'role')

    def test_reference_order_participates_in_identity(self):
        value = proposal()
        value['references'].append({'instance_id': 'actor-a', 'role': 'style', 'sha256': '8' * 64})
        before = assess(value)['proposal_sha256']
        value['references'].reverse()
        self.assertNotEqual(before, assess(value)['proposal_sha256'])

    def test_contact_requires_known_distinct_participants(self):
        value = proposal()
        value['contacts'] = [{'participants': ['actor-a', 'actor-a'], 'box': [100, 90, 130, 130]}]
        self.reject(value, 'contact')

    def test_contact_edit_requires_coupled_targets(self):
        value = proposal()
        value['instances'].append({'id': 'actor-b', 'kind': 'character'})
        value['contacts'] = [{'participants': ['actor-a', 'actor-b'], 'box': [100, 90, 130, 130]}]
        value['intent']['kind'] = 'contact'
        self.reject(value, 'contact_scope')
        value['targets'].append('actor-b')
        self.assertFalse(assess(value)['executable'])

    def test_contact_region_must_fit_context(self):
        value = proposal()
        value['instances'].append({'id': 'prop-a', 'kind': 'prop'})
        value['targets'].append('prop-a')
        value['contacts'] = [{'participants': ['actor-a', 'prop-a'], 'box': [0, 0, 20, 20]}]
        value['intent']['kind'] = 'contact'
        self.reject(value, 'contact_scope')

    def test_contact_edit_needs_declared_contact(self):
        value = proposal()
        value['intent']['kind'] = 'contact'
        self.reject(value, 'contact_scope')

    def test_outpainting_is_not_local_restoration(self):
        value = proposal()
        value['intent']['kind'] = 'outpaint'
        self.reject(value, 'preservation_conflict')
        value['mode'] = 'reconstruction'
        value['intent']['synthesize_unseen'] = True
        self.assertIn('reconstruction-scope', assess(value)['review_required'])

    def test_hidden_anatomy_requires_review_not_invented_certainty(self):
        value = proposal()
        value['intent']['visibility'] = 'occluded'
        self.assertIn('visibility', assess(value)['review_required'])

    def test_unseen_synthesis_requires_reconstruction_mode(self):
        value = proposal()
        value['intent']['synthesize_unseen'] = True
        self.reject(value, 'preservation_conflict')

    def test_global_upscale_is_not_local_exact_preservation(self):
        value = proposal()
        value['strategies'] = ['upscale']
        self.reject(value, 'preservation_conflict')
        value['mode'] = 'remaster'
        self.assertFalse(assess(value)['executable'])

    def test_zero_candidate_cap_is_a_valid_non_neural_proposal(self):
        value = proposal()
        value['strategies'] = ['preserve', 'native']
        value['limits']['max_candidates'] = 0
        self.assertFalse(assess(value)['executable'])

    def test_candidate_route_needs_positive_declared_cap(self):
        value = proposal()
        value['limits']['max_candidates'] = 0
        self.reject(value, 'budget')

    def test_limits_and_description_are_bounded(self):
        for section, field, replacement, code in [('limits', 'max_candidates', 65, 'integer'),
                  ('intent', 'description', 'x' * 2049, 'text')]:
            value = proposal()
            value[section][field] = replacement
            self.reject(value, code)

    def test_duplicate_json_keys_and_nonfinite_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for text in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}']:
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ContractError):
                    read_proposal(path)

    def test_oversized_and_deep_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for text in [' ' * (262144 + 1), '[' * 100 + '0' + ']' * 100]:
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ContractError):
                    read_proposal(path)

    def test_cli_has_no_execute_command(self):
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/repair_proposal.py'), 'execute'],
                             text=True, capture_output=True, cwd=tempfile.gettempdir())
        self.assertNotEqual(run.returncode, 0)

    def test_cli_validate_and_describe_from_other_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proposal.json'
            path.write_text(json.dumps(proposal()), encoding='utf-8')
            before = path.read_bytes()
            for args in [['describe'], ['validate', str(path)]]:
                run = subprocess.run([sys.executable, str(ROOT / 'scripts/repair_proposal.py'), *args],
                                     text=True, capture_output=True, cwd=directory)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertFalse(json.loads(run.stdout)['executable'])
            self.assertEqual(list(Path(directory).iterdir()), [path])
            self.assertEqual(path.read_bytes(), before)

    def test_cli_invalid_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proposal.json'
            path.write_text('{}', encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/repair_proposal.py'), 'validate', str(path)],
                                 text=True, capture_output=True, cwd=directory)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(json.loads(run.stdout)['executable'])
            self.assertEqual(json.loads(run.stdout)['error']['code'], 'fields')


if __name__ == '__main__':
    unittest.main()

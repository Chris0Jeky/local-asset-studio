"""Saved Looks must still bind, and one broken shipped seed must not poison its peers."""
import copy
import json
import unittest

import test_looks as fixture


class LookValidationTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp
    create = fixture.LookTests.create

    def test_metadata_keys_are_never_treated_as_bound_controls(self):
        for key in ('graph', 'defaults', 'choices', 'description', 'backend'):
            with self.subTest(key=key):
                preset = dict(fixture.TEXT, **{key: ['1', 'steps']})
                with self.assertRaisesRegex(fixture.WorkspaceError, 'not bound'):
                    fixture.looks.validate_body(dict(fixture.BODY, controls={key: 1}), preset)

    def test_control_bindings_require_a_nonempty_node_input_pair(self):
        for binding in (True, '1.steps', ['1'], ['1', 'steps', 'extra'], [None, 'steps'], ['1', ''], {'node': '1'}, 7):
            with self.subTest(binding=binding), self.assertRaisesRegex(fixture.WorkspaceError, 'not bound'):
                fixture.looks.validate_body(dict(fixture.BODY, controls={'steps': 3}), dict(fixture.TEXT, steps=binding))

    def test_extra_bindings_obey_the_same_pair_and_control_rules(self):
        preset = dict(fixture.TEXT, bindings_extra={'lora6_name': ['1', 'adapter'], 'graph': ['1', 'steps']})
        body = dict(fixture.BODY, controls={'lora6_name': 'kept.safetensors'})
        self.assertEqual(fixture.looks.validate_body(body, preset)['controls'], body['controls'])
        for extra in ({'lora6_name': 'wrong'}, {'lora6_name': [False, 'adapter']}, ['not-a-map']):
            with self.subTest(extra=extra), self.assertRaises(fixture.WorkspaceError):
                fixture.looks.validate_body(body, dict(fixture.TEXT, bindings_extra=extra))
        with self.assertRaisesRegex(fixture.WorkspaceError, 'not bound'):
            fixture.looks.validate_body(dict(body, controls={'graph': 2}), preset)

    def test_allowed_controls_match_the_existing_server_contract(self):
        self.assertEqual(set(fixture.looks.CONTROL_KEYS), set(fixture.server.CONTROL_KEYS) - fixture.looks.NOT_CONTROLS)

    def test_each_bad_seed_is_reported_without_preventing_the_good_seed(self):
        good = {'id': 'look-good', 'kind': 'look', 'name': 'Good', 'body': copy.deepcopy(fixture.BODY)}
        bad = [dict(good, id='../bad'), dict(good, id=123), dict(good, name=''), dict(good, name=12),
               dict(good, name='x'*121), dict(good, body=['not-a-body']), dict(good, body='bad'), dict(good, body=7)]
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': [*bad, good]}), encoding='utf-8')
        errors = fixture.looks.ensure_seeds(self.studio)
        self.assertEqual(len(errors), len(bad))
        self.assertEqual([card['id'] for card in self.studio.assets.cards('look')], ['look-good'])
        self.assertEqual(fixture.looks.ensure_seeds(self.studio), errors)
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_listing_rechecks_saved_controls_against_current_recipe(self):
        card = self.create()
        self.studio.catalog = lambda: {'presets': [dict(fixture.TEXT, seed=None)]}
        listed = next(row for row in fixture.looks.listing(self.studio)['looks'] if row['id'] == card['id'])
        self.assertFalse(listed['usable'])
        self.assertIn('seed is not bound', listed['unusable_reason'])
        with self.assertRaisesRegex(fixture.WorkspaceError, 'seed is not bound'):
            fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a quiet room'})
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_seed_container_shape_is_reported_not_silently_ignored(self):
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': {'id': 'not-a-list'}}))
        self.assertTrue(fixture.looks.ensure_seeds(self.studio))
        self.assertEqual(self.studio.assets.cards('look'), [])

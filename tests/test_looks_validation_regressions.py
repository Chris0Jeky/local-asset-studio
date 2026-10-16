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

    # Pinned to the public surface of app/looks.py; the caller named
    # behaviours but supplied no exact values, so each assertion pins the
    # observed contract below.
    def test_prepare_refuses_a_look_whose_recipe_left_the_catalog(self):
        card = self.create()
        self.studio.catalog = lambda: {'presets': []}
        with self.assertRaisesRegex(fixture.WorkspaceError, 'This look.s recipe is not in the recipe library'):
            fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a quiet room'})
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_prepare_revalidates_the_stored_body_against_the_current_recipe(self):
        card = self.create()
        self.studio.catalog = lambda: {'presets': [dict(fixture.TEXT, seed=None)]}
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a quiet room'})
        self.assertEqual(str(caught.exception), 'seed is not bound on Text only')
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_lineage_rejects_a_bad_role(self):
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_lineage([{'role': 'owner'}])
        self.assertEqual(str(caught.exception), 'Each lineage entry names its role: anchor, evidence, canon')
        for lineage in ([{}], ['anchor'], [{'sha256': 'c' * 64}]):
            with self.subTest(lineage=lineage), self.assertRaisesRegex(fixture.WorkspaceError, 'names its role'):
                fixture.looks.validate_lineage(lineage)
        kept = [{'role': 'anchor'}, {'role': 'evidence'}, {'role': 'canon'}]
        self.assertIs(fixture.looks.validate_lineage(kept), kept)

    def test_lineage_rejects_a_bad_sha256(self):
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_lineage([{'role': 'anchor', 'sha256': 'ABC'}])
        self.assertEqual(str(caught.exception), 'A lineage sha256 is 64 lowercase hexadecimal characters')
        digest = 'c22b723c65198b896ff9e542b05745742a447b62e91a7e5cfb8c0f593df7dfa9'
        for sha in ('C' + digest[1:], digest[:-1], digest + 'aa', 123, None):
            with self.subTest(sha=repr(sha)[:20]), self.assertRaisesRegex(fixture.WorkspaceError, 'sha256'):
                fixture.looks.validate_lineage([{'role': 'anchor', 'sha256': sha}])
        kept = [{'role': 'anchor', 'sha256': digest}]
        self.assertIs(fixture.looks.validate_lineage(kept), kept)
        bare = [{'role': 'evidence'}]
        self.assertIs(fixture.looks.validate_lineage(bare), bare)

    def test_lineage_rejects_more_than_20_entries(self):
        entries = [{'role': 'evidence'} for _ in range(21)]
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_lineage(entries)
        self.assertEqual(str(caught.exception), 'Lineage must be a list of up to 20 entries')
        with self.assertRaisesRegex(fixture.WorkspaceError, 'up to 20'):
            fixture.looks.validate_lineage({'role': 'evidence'})
        kept = [{'role': 'evidence'} for _ in range(20)]
        result = fixture.looks.validate_lineage(kept)
        self.assertIs(result, kept)
        self.assertEqual(len(result), 20)

    def test_lineage_rejects_over_long_values(self):
        digest = 'c22b723c65198b896ff9e542b05745742a447b62e91a7e5cfb8c0f593df7dfa9'
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_lineage([{'role': 'anchor', 'sha256': digest, 'evidence': 'x' * 501}])
        self.assertEqual(str(caught.exception), 'Lineage values are short text or numbers')
        with self.assertRaisesRegex(fixture.WorkspaceError, 'short text or numbers'):
            fixture.looks.validate_lineage([{'role': 'anchor', 'note': {'nested': True}}])
        with self.assertRaisesRegex(fixture.WorkspaceError, 'short text or numbers'):
            fixture.looks.validate_lineage([{'role': 'anchor', 'note': ['a']}])
        kept = [{'role': 'anchor', 'sha256': digest, 'evidence': 'x' * 500}]
        self.assertIs(fixture.looks.validate_lineage(kept), kept)

    def test_body_rejects_a_control_string_over_300_chars(self):
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(dict(fixture.BODY, controls={'seed': 'x' * 301}), fixture.TEXT)
        self.assertEqual(str(caught.exception), 'seed must be up to 300 characters')
        kept = fixture.looks.validate_body(dict(fixture.BODY, controls={'seed': 'x' * 300}), fixture.TEXT)
        self.assertEqual(kept['controls'], {'seed': 'x' * 300})

    def test_body_rejects_more_than_40_controls(self):
        controls = {'key%d' % index: index for index in range(41)}
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(dict(fixture.BODY, controls=controls), fixture.TEXT)
        self.assertEqual(str(caught.exception), 'Look controls must be an object of up to 40 settings')
        with self.assertRaisesRegex(fixture.WorkspaceError, 'up to 40'):
            fixture.looks.validate_body(dict(fixture.BODY, controls=['not-a-dict']), fixture.TEXT)

    def test_body_rejects_a_non_string_control_key(self):
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(dict(fixture.BODY, controls={7: 1}), fixture.TEXT)
        self.assertEqual(str(caught.exception), '7 is not a look setting')
        with self.assertRaisesRegex(fixture.WorkspaceError, 'is not a look setting'):
            fixture.looks.validate_body(dict(fixture.BODY, controls={None: 1}), fixture.TEXT)

    def test_body_accepts_a_control_bound_only_through_bindings_extra(self):
        preset = dict(fixture.TEXT, bindings_extra={'cfg': ['1', 'cfg']})
        body = dict(fixture.BODY, controls={'cfg': 2})
        self.assertEqual(fixture.looks.validate_body(body, preset)['controls'], {'cfg': 2})
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(body, fixture.TEXT)
        self.assertEqual(str(caught.exception), 'cfg is not bound on Text only')

    def test_recipe_without_positive_binding_takes_no_wording(self):
        preset = dict(fixture.TEXT, id='no-words', name='No words', positive=None)
        self.assertEqual(fixture.looks.recipe_problem(preset), 'This recipe takes no wording, so a look cannot write it.')
        self.assertIsNone(fixture.looks.recipe_problem(fixture.TEXT))
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(dict(fixture.BODY, preset_id='no-words'), preset)
        self.assertEqual(str(caught.exception), 'This recipe takes no wording, so a look cannot write it.')

    def test_seeds_report_an_unreadable_seed_file_and_store_nothing(self):
        (self.root/'presets/looks.json').write_text('{not json', encoding='utf-8')
        errors = fixture.looks.ensure_seeds(self.studio)
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith('presets/looks.json is unreadable: '), errors)
        self.assertEqual(self.studio.assets.cards('look'), [])
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_seeds_report_a_non_list_looks_container(self):
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': {'id': 'not-a-list'}}), encoding='utf-8')
        self.assertEqual(fixture.looks.ensure_seeds(self.studio), ['presets/looks.json looks must be a list'])
        self.assertEqual(self.studio.assets.cards('look'), [])

    def test_seeds_report_a_bad_id_or_kind(self):
        good = {'id': 'look-good', 'kind': 'look', 'name': 'Good', 'body': copy.deepcopy(fixture.BODY)}
        entries = [dict(good, kind='character'), dict(good, id='../bad'), dict(good, id=123)]
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': entries}), encoding='utf-8')
        self.assertEqual(fixture.looks.ensure_seeds(self.studio),
                         ['look-good: not a look', '../bad: Invalid seed card id', '123: Invalid seed card id'])
        self.assertEqual(self.studio.assets.cards('look'), [])

    def test_seeds_report_a_bad_supersedes_list(self):
        digest = 'c22b723c65198b896ff9e542b05745742a447b62e91a7e5cfb8c0f593df7dfa9'
        base = {'kind': 'look', 'name': 'Seed', 'body': copy.deepcopy(fixture.BODY), 'lineage': []}
        ok = dict(base, id='look-sup-ok', supersedes=[digest])
        bad_shape = dict(base, id='look-sup-bad-shape', supersedes=['not-a-digest'])
        bad_type = dict(base, id='look-sup-bad-type', supersedes='not-a-list')
        bad_long = dict(base, id='look-sup-bad-long', supersedes=[digest] * 21)
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': [bad_shape, bad_type, bad_long, ok]}), encoding='utf-8')
        self.assertEqual(
            fixture.looks.ensure_seeds(self.studio),
            ['look-sup-bad-shape: supersedes is a list of up to 20 sha256 digests of earlier shipped versions',
             'look-sup-bad-type: supersedes is a list of up to 20 sha256 digests of earlier shipped versions',
             'look-sup-bad-long: supersedes is a list of up to 20 sha256 digests of earlier shipped versions'])
        self.assertEqual([card['id'] for card in self.studio.assets.cards('look')], ['look-sup-ok'])

    def test_seeds_run_once_per_studio(self):
        first_entry = {'id': 'look-cache-a', 'kind': 'look', 'name': 'A', 'body': copy.deepcopy(fixture.BODY)}
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': [first_entry]}), encoding='utf-8')
        first = fixture.looks.ensure_seeds(self.studio)
        self.assertEqual(first, [])
        self.assertEqual([card['id'] for card in self.studio.assets.cards('look')], ['look-cache-a'])
        second_entry = {'id': 'look-cache-b', 'kind': 'look', 'name': 'B', 'body': copy.deepcopy(fixture.BODY)}
        (self.root/'presets/looks.json').write_text(json.dumps({'looks': [first_entry, second_entry]}), encoding='utf-8')
        raw = (self.root/'presets/looks.json').read_text(encoding='utf-8')
        self.assertIn('look-cache-b', raw)
        second = fixture.looks.ensure_seeds(self.studio)
        self.assertIs(second, first)
        self.assertEqual([card['id'] for card in self.studio.assets.cards('look')], ['look-cache-a'])

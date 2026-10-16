"""Saved Looks must still bind, and one broken shipped seed must not poison its peers."""
import copy
import json
import unittest

import test_looks as fixture


class LookValidationTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp
    create = fixture.LookTests.create
    route = fixture.LookTests.route

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

    def test_saved_controls_obey_the_ranges_and_choices_jobs_enforce(self):
        # A look control /api/jobs would refuse is refused when the look is saved, and again when it is prepared.
        preset = dict(fixture.TEXT, cfg=['1', 'steps'], sampler=['1', 'steps'], lora=['1', 'steps'], lora_name=['1', 'steps'],
                      dimension_limits=[256, 1024], dimension_multiple=64, choices={'sampler': ['euler']})
        for key, bad in (('steps', 0), ('steps', 151), ('steps', 2.5), ('steps', 'many'), ('seed', -1), ('seed', 2**63), ('cfg', 31),
                         ('lora', 2.5), ('lora', -0.1), ('lora', 'style.ckpt'), ('lora_name', '../x.safetensors'), ('lora_name', 'x.ckpt'),
                         ('width', 1344), ('width', 300), ('width', 128), ('sampler', 'dpmpp_9m')):
            with self.subTest(key=key, bad=bad), self.assertRaisesRegex(fixture.WorkspaceError, key):
                fixture.looks.validate_body(dict(fixture.BODY, controls={key: bad}), preset)
        good = {'steps': '30', 'seed': 0, 'cfg': 7.5, 'lora': 1.2, 'lora_name': 'style.safetensors', 'width': 832 - 832 % 64, 'sampler': 'euler'}
        self.assertEqual(fixture.looks.validate_body(dict(fixture.BODY, controls=good), preset)['controls'], good)
        self.assertIsNotNone(fixture.looks.control_problem(dict(preset, choices={}), 'sampler', 'anything'), 'jobs refuse a choice when none are offered')
        card = self.create()
        self.studio.catalog = lambda: {'presets': [dict(fixture.TEXT, dimension_limits=[256, 1024])]}
        with self.assertRaisesRegex(fixture.WorkspaceError, 'width must be'):
            fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a quiet room'})
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_every_numeric_control_refuses_text_and_nonfinite_values_at_save(self):
        ranges = dict(fixture.looks.NUMBER_RANGES, width=(64, 1536, True), height=(64, 1536, True))
        self.assertEqual(set(ranges), fixture.looks.CONTROL_KEYS - {'sampler', 'scheduler', *(key for key in fixture.looks.CONTROL_KEYS if key.endswith('_name'))})
        for key, (lo, hi, integer) in ranges.items():
            preset = dict(fixture.TEXT, **{key: ['1', 'steps']})
            for bad in ('many', '100 ms', 'NaN', 'Infinity', '-Infinity', True, lo - 1, hi + 1, *([1.5] if integer else [])):
                with self.subTest(key=key, bad=bad), self.assertRaisesRegex(fixture.WorkspaceError, key):
                    fixture.looks.validate_body(dict(fixture.BODY, controls={key: bad}), preset)
            good = str(512 if key in ('width', 'height') else lo)
            self.assertEqual(fixture.looks.validate_body(dict(fixture.BODY, controls={key: good}), preset)['controls'], {key: good})

    def test_saved_sampler_and_scheduler_require_an_offered_choice(self):
        for key, value in (('sampler', 'euler'), ('scheduler', 'normal')):
            for choices in (None, {}, {key: []}, {key: ['other']}):
                preset = dict(fixture.TEXT, **{key: ['1', key]})
                if choices is not None: preset['choices'] = choices
                with self.subTest(key=key, choices=choices), self.assertRaisesRegex(fixture.WorkspaceError, key):
                    fixture.looks.validate_body(dict(fixture.BODY, controls={key: value}), preset)
            preset['choices'] = {key: [value]}
            self.assertEqual(fixture.looks.validate_body(dict(fixture.BODY, controls={key: value}), preset)['controls'], {key: value})

    def sampler_recipe(self, sampler=('euler', 'dpmpp_2m'), scheduler=('normal', 'karras')):
        """Rewrite the catalog on disk: a recipe whose graph authors euler/normal and which offers the given choices (#1456 reversal)."""
        graph = {'1': {'inputs': dict(fixture.GRAPH['1']['inputs'], sampler_name='euler', scheduler='normal')}}
        preset = dict(fixture.TEXT, sampler=['1', 'sampler_name'], scheduler=['1', 'scheduler'], choices={'sampler': list(sampler), 'scheduler': list(scheduler)})
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': [preset]}))

    def test_an_unoffered_sampler_or_scheduler_becomes_the_recipe_default_with_a_notice(self):
        # Owner, 16 Oct 2026: swap it for the recipe's authored default on Prepare and say so; the look stays usable.
        self.sampler_recipe()
        self.assertEqual(self.studio.catalog()['presets'][0]['defaults']['sampler'], 'euler', 'the default is the graph value Studio.catalog reads back')
        card = fixture.looks.command(self.studio, {'action': 'create', 'kind': 'look', 'name': 'Swap', 'body': dict(fixture.BODY, controls={'seed': 77, 'steps': 12, 'sampler': 'dpmpp_2m', 'scheduler': 'karras'})})
        self.assertNotIn('notices', card, 'offered choices raise no notice')
        self.sampler_recipe(sampler=('euler', 'heun'), scheduler=('normal',))
        listed = next(row for row in fixture.looks.listing(self.studio)['looks'] if row['id'] == card['id'])
        self.assertTrue(listed['usable'], listed['unusable_reason'])
        prepared = fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a quiet room'})
        self.assertEqual((prepared['controls']['sampler'], prepared['controls']['scheduler']), ('euler', 'normal'))
        self.assertEqual((prepared['controls']['seed'], prepared['controls']['steps']), (77, 12))
        self.assertEqual(prepared['notices'], ["This look's sampler dpmpp_2m is no longer offered by Text only; using the recipe's default euler.",
                                               "This look's scheduler karras is no longer offered by Text only; using the recipe's default normal."])
        self.assertEqual(self.studio.assets.card(card['id'])['revision'], card['revision'], 'Prepare reads only')
        status, body = self.route('POST', '/api/looks/prepare', {'id': card['id'], 'scene': 'a quiet room'})
        self.assertEqual((status, body['controls']['sampler'], len(body['notices'])), (200, 'euler', 2))
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))
        # An offered choice is left alone and carries no notice.
        self.sampler_recipe()
        self.assertNotIn('notices', fixture.looks.prepare(self.studio, {'id': card['id'], 'scene': 'a quiet room'}))

    def test_saving_an_unoffered_sampler_stores_the_default_and_returns_the_notice(self):
        self.sampler_recipe()
        body = dict(fixture.BODY, controls={'seed': 77, 'sampler': 'dpmpp_3m'})
        card = fixture.looks.command(self.studio, {'action': 'create', 'kind': 'look', 'name': 'Saved', 'body': body})
        self.assertEqual(card['body']['controls'], {'seed': 77, 'sampler': 'euler'})
        self.assertEqual(card['notices'], ["This look's sampler dpmpp_3m is no longer offered by Text only; using the recipe's default euler."])
        self.assertEqual(self.studio.assets.card(card['id'])['body']['controls']['sampler'], 'euler')
        edited = fixture.looks.command(self.studio, {'action': 'edit', 'id': card['id'], 'expected_revision': card['revision'], 'body': dict(body, controls={'scheduler': 'exponential'})})
        self.assertEqual((edited['body']['controls'], len(edited['notices'])), ({'scheduler': 'normal'}, 1))

    def test_other_control_validation_stays_strict_next_to_a_swapped_sampler(self):
        self.sampler_recipe()
        for controls in ({'sampler': 'gone', 'steps': 0}, {'sampler': 'gone', 'seed': -1}, {'scheduler': 'gone', 'lora_name': 'x.ckpt'}):
            with self.subTest(controls=controls), self.assertRaises(fixture.WorkspaceError):
                fixture.looks.command(self.studio, {'action': 'create', 'kind': 'look', 'name': 'Bad', 'body': dict(fixture.BODY, controls=controls)})
        self.assertEqual(self.studio.assets.cards('look'), [])

    def test_no_swap_when_the_recipe_default_is_not_itself_offered(self):
        # Without an authored default that is offered, the swap would only move the jobs refusal: keep the plain reason.
        base = dict(fixture.TEXT, sampler=['1', 'sampler_name'], choices={'sampler': ['euler']})
        for defaults in (None, {}, {'sampler': ''}, {'sampler': 'ghost'}, {'sampler': 5}):
            preset = dict(base, **({'defaults': defaults} if defaults is not None else {}))
            with self.subTest(defaults=defaults), self.assertRaisesRegex(fixture.WorkspaceError, 'sampler dpmpp is not offered'):
                fixture.looks.validate_body(dict(fixture.BODY, controls={'sampler': 'dpmpp'}), preset)
        notices = []
        kept = fixture.looks.validate_body(dict(fixture.BODY, controls={'sampler': 'dpmpp'}), dict(base, defaults={'sampler': 'euler'}), notices)
        self.assertEqual((kept['controls'], len(notices)), ({'sampler': 'euler'}, 1))

    def test_a_filename_is_a_lora_slot_value_only_where_the_recipe_slot_holds_a_filename(self):
        # /api/jobs takes a filename for a slot only when the graph input it binds holds one (older presets); a strength slot refuses it.
        strength = dict(fixture.TEXT, lora=['1', 'steps'], defaults={'lora': 1.0})
        with self.assertRaisesRegex(fixture.WorkspaceError, 'lora must be a number'):
            fixture.looks.validate_body(dict(fixture.BODY, controls={'lora': 'style.safetensors'}), strength)
        with self.assertRaisesRegex(fixture.WorkspaceError, 'lora must be a number'):
            fixture.looks.validate_body(dict(fixture.BODY, controls={'lora': 'style.safetensors'}), dict(strength, defaults={}))
        filename = dict(strength, defaults={'lora': 'authored.safetensors'})
        self.assertEqual(fixture.looks.validate_body(dict(fixture.BODY, controls={'lora': 'style.safetensors'}), filename)['controls'], {'lora': 'style.safetensors'})
        for bad in (0.5, '../x.safetensors', 'x.ckpt'):
            with self.subTest(bad=bad), self.assertRaisesRegex(fixture.WorkspaceError, 'lora must be'):
                fixture.looks.validate_body(dict(fixture.BODY, controls={'lora': bad}), filename)

    def test_saved_control_ranges_match_the_job_route(self):
        self.assertEqual({k: v for k, v in fixture.looks.NUMBER_RANGES.items() if k in dict((r[0], r) for r in fixture.server.NUMBER_RANGES)},
                         {r[0]: r[1:] for r in fixture.server.NUMBER_RANGES})

    def test_model_of_names_the_one_loader_and_its_text_encoders(self):
        # Make's Tune offers another model only when loader and encoders match; a graph with no or two loaders offers none.
        graph = {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'base.safetensors'}},
                 '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'te.safetensors', 'type': 'x'}},
                 '3': {'class_type': 'DualCLIPLoader', 'inputs': {'clip_name1': 'b.safetensors', 'clip_name2': 'a.safetensors'}}}
        self.assertEqual(fixture.looks.model_of(graph), {'file': 'base.safetensors', 'loader': 'UNETLoader', 'encoders': ['a.safetensors', 'b.safetensors', 'te.safetensors']})
        self.assertEqual(fixture.looks.model_of({'1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'sdxl.safetensors'}}})['encoders'], [])
        for bad in ({}, {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': ['9', 0]}}}, dict(graph, **{'4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'x.safetensors'}}})):
            with self.subTest(bad=bad): self.assertIsNone(fixture.looks.model_of(bad))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(dict(fixture.GRAPH, **graph)))
        self.assertEqual(self.studio.catalog()['presets'][0]['model']['file'], 'base.safetensors')

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
        # A text-valued setting; numeric ones such as seed are refused as non-numbers first.
        preset = dict(fixture.TEXT, sampler=['1', 'sampler_name'], choices={'sampler': ['x' * 300]})
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(dict(fixture.BODY, controls={'sampler': 'x' * 301}), preset)
        self.assertEqual(str(caught.exception), 'sampler must be up to 300 characters')
        kept = fixture.looks.validate_body(dict(fixture.BODY, controls={'sampler': 'x' * 300}), preset)
        self.assertEqual(kept['controls'], {'sampler': 'x' * 300})

    def test_body_rejects_more_than_40_controls(self):
        controls = {'key%d' % index: index for index in range(41)}
        with self.assertRaises(fixture.WorkspaceError) as caught:
            fixture.looks.validate_body(dict(fixture.BODY, controls=controls), fixture.TEXT)
        self.assertEqual(str(caught.exception), 'Look controls must be an object of up to 40 settings')
        with self.assertRaisesRegex(fixture.WorkspaceError, 'up to 40'):
            fixture.looks.validate_body(dict(fixture.BODY, controls=['not-a-dict']), fixture.TEXT)

    def test_free_text_fields_refuse_one_character_over_their_maxima_and_keep_the_maximum(self):
        maxima = {'template': 4000, 'negative': 4000, 'scene_example': 1000, 'source_prompt': 8000, 'notes': 4000}
        self.assertEqual(fixture.looks.TEXT_LIMITS, maxima)   # pinned literally: a changed constant must fail here, not move the test
        for field, maximum in maxima.items():
            fits = ('{scene}' + 'x' * (maximum - 7)) if field == 'template' else 'x' * maximum
            with self.subTest(field=field):
                with self.assertRaisesRegex(fixture.WorkspaceError, f'up to {maximum} characters'):
                    fixture.looks.validate_body(dict(fixture.BODY, preset_id='with-negative', **{field: 'x' * (maximum + 1)}), fixture.WITH_NEGATIVE)
                kept = fixture.looks.validate_body(dict(fixture.BODY, preset_id='with-negative', **{field: fits}), fixture.WITH_NEGATIVE)
                self.assertEqual(kept[field], fits)

    def test_negative_last_reference_mode_and_positive_are_never_look_settings(self):
        """NOT_CONTROLS is checked before binding: even a recipe that binds these keys cannot store them as look settings."""
        preset = dict(fixture.WITH_NEGATIVE, bindings_extra={'mode': ['1', 'text'], 'last_reference': ['1', 'text']})
        for key in ('negative', 'last_reference', 'mode', 'reference', 'positive'):
            with self.subTest(key=key), self.assertRaisesRegex(fixture.WorkspaceError, f'^{key} is not a look setting$'):
                fixture.looks.validate_body(dict(fixture.BODY, preset_id='with-negative', controls={key: 'x'}), preset)

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

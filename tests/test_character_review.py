"""Explicit character decisions through real inert Production and the saved collector."""
import copy
import json
import unittest
from unittest.mock import patch

import test_character_study_results as fixtures
from scripts import character_study as study
from scripts import character_study_results as results


class CharacterReviewTests(unittest.TestCase):
    character_preflight = fixtures.CollectionTests.character_preflight
    payload = fixtures.CollectionTests.payload
    project = fixtures.CollectionTests.project
    execute = fixtures.CollectionTests.execute
    collect = fixtures.CollectionTests.collect

    def setUp(self):
        fixtures.CollectionTests.setUp(self)
        self.project_id = self.project()['id']
        self.job = self.execute({'id': self.project_id})
        self.state = self.command('open')
        self.alias = self.state['candidates'][0]['alias']
        self.checks = {key: 'pass' for key in self.plan['cases'][0]['required_checks']}

    def command(self, action, **payload):
        if hasattr(self, 'state') and action not in ('open', 'inspect'): payload['expected_revision'] = self.state['revision']
        self.state = self.studio.production.review(self.project_id, dict(action=action, **payload))
        return self.state

    def rate(self, **payload):
        return self.command('rate', alias=self.alias, assessment={'verdict': 'keep', 'observations': {'constraints': 'pass'}}, **payload)

    def finalize(self, decision='accepted', reviewer='local-user'):
        self.rate(character_checks=self.checks)
        self.command('reveal')
        return self.command('finalize', selected=self.alias, notes='Synthetic explicit character assessment.',
                            character_decision=decision, reviewer=reviewer)

    def summary(self, name='collected-v1'):
        self.destination = self.workspace/name
        self.collect()
        return study.read_json(self.destination/'summary.json'), study.read_json(self.destination/'records.json')

    def test_explicit_human_decision_reaches_summary_and_view_retains_its_revision(self):
        self.assertEqual(self.state['character_context']['required_checks'],
                         {key: self.plan['canon']['checks'][key] for key in self.checks})
        self.assertEqual(set(self.state['candidates'][0]['character_checks'].values()), {'uncertain'})
        before = (copy.deepcopy(self.studio.jobs), len(self.studio.requests), self.studio.production.get(self.project_id)['budget'])
        self.finalize(); receipt = copy.deepcopy(self.state['character_review'])
        self.command('view', crop=[0, 0, 10000, 10000], background='light')
        self.assertEqual(self.state['character_review'], receipt)
        self.assertLess(receipt['review_revision'], self.state['revision'])
        with patch.object(self.studio, '_request', side_effect=AssertionError('Review collection contacted a runtime')):
            summary, records = self.summary()
        self.assertEqual((summary['selected_cases'], summary['human_accepted_cases']), (1, 1))
        self.assertEqual(records[0]['review'], receipt['review'])
        self.assertEqual(records[0]['output']['sha256'], receipt['review']['output_sha256'])
        self.assertEqual(before, (self.studio.jobs, len(self.studio.requests), self.studio.production.get(self.project_id)['budget']))

    def test_generic_finalization_stays_unreviewed_for_the_character_study(self):
        self.rate(); self.command('reveal')
        self.command('finalize', selected=self.alias, notes='Generic keeper only.')
        summary, records = self.summary()
        self.assertEqual(summary['human_accepted_cases'], 0)
        self.assertIsNone(records[0]['review'])

    def test_accepted_candidate_attaches_through_the_existing_asset_handoff(self):
        self.finalize(); asset_id = self.job['outputs'][0]['asset_id']
        before = (copy.deepcopy(self.studio.jobs), len(self.studio.requests), self.studio.production.get(self.project_id)['budget'])
        attached = self.studio.asset_reference(asset_id)
        self.assertEqual(attached['parent_asset'], asset_id)
        self.assertEqual(attached['context']['asset_id'], asset_id)
        self.assertEqual(attached['context']['sha256'], self.state['character_review']['review']['output_sha256'])
        self.assertEqual((self.studio.experiments/'uploads'/attached['file']).read_bytes(), self.studio.assets.file(asset_id).read_bytes())
        self.assertEqual(before, (self.studio.jobs, len(self.studio.requests), self.studio.production.get(self.project_id)['budget']))

    def test_agent_can_select_but_cannot_attest_human_acceptance(self):
        self.finalize('selected', 'local-agent')
        summary, _ = self.summary()
        self.assertEqual((summary['selected_cases'], summary['human_accepted_cases']), (1, 0))
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'human|local-user'):
            self.command('finalize', selected=self.alias, notes='Agent cannot accept.', character_decision='accepted', reviewer='local-agent')
        self.assertEqual(self.studio.production.review(self.project_id, {'action': 'inspect'}), before)

    def test_exact_checks_and_known_observations_are_required(self):
        for checks in ({}, dict(self.checks, invented='pass'), {key: True for key in self.checks}, {key: 'not_assessed' for key in self.checks}):
            with self.subTest(checks=checks), self.assertRaises(ValueError): self.rate(character_checks=checks)
        self.assertEqual(self.state['revision'], 0)

    def test_nonpassing_or_unobserved_checks_cannot_be_selected_or_accepted(self):
        self.command('reveal')
        for observation in ('fail', 'not_visible', 'uncertain'):
            self.rate(character_checks={key: observation for key in self.checks})
            for decision in ('selected', 'accepted'):
                with self.subTest(observation=observation, decision=decision), self.assertRaisesRegex(ValueError, 'pass'):
                    self.command('finalize', selected=self.alias, notes='Not all checks passed.', character_decision=decision, reviewer='local-user')

    def test_acceptance_requires_explicit_reviewer_candidate_and_note(self):
        self.rate(character_checks=self.checks); self.command('reveal')
        for payload in ({'selected': self.alias, 'notes': 'No reviewer declaration.'},
                        {'selected': None, 'notes': 'No selected candidate.', 'reviewer': 'local-user'},
                        {'selected': self.alias, 'notes': '  ', 'reviewer': 'local-user'}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.command('finalize', character_decision='accepted', **payload)
        self.assertIsNone(self.state['character_review'])

    def test_stale_character_assessment_does_not_change_a_saved_acceptance(self):
        self.finalize(); before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.studio.production.review(self.project_id, {'action': 'rate', 'expected_revision': 0, 'alias': self.alias,
                'assessment': {'verdict': 'reject'}, 'character_checks': {key: 'fail' for key in self.checks}})
        self.assertEqual(self.studio.production.review(self.project_id, {'action': 'inspect'}), before)

    def test_edit_and_restore_clear_acceptance_but_retain_the_finalization_event(self):
        self.finalize(); accepted_revision = self.state['revision']
        self.rate(character_checks={key: 'uncertain' for key in self.checks})
        self.assertIsNone(self.state['character_review'])
        summary, _ = self.summary()
        self.assertEqual(summary['human_accepted_cases'], 0)
        self.command('restore', source_revision=1)
        self.assertEqual(self.state['candidates'][0]['character_checks'], self.checks)
        self.assertIsNone(self.state['character_review'])
        with self.studio.production.connect() as db:
            event = json.loads(db.execute('SELECT event FROM comparison_review_events WHERE project_id=? AND revision=?',
                                         (self.project_id, accepted_revision)).fetchone()['event'])
        self.assertEqual(event['details']['character_review']['review']['decision'], 'accepted')

    def test_changed_output_bytes_or_retained_review_source_cannot_be_collected(self):
        self.finalize()
        asset_id = self.job['outputs'][0]['asset_id']; original = self.studio.assets.file(asset_id)
        with self.studio.production.connect() as db:
            document = json.loads(db.execute('SELECT document FROM comparison_reviews WHERE project_id=?', (self.project_id,)).fetchone()['document'])
        snapshot = self.studio.production.root/self.project_id/document['candidates'][0]['source_path']
        for path in (original, snapshot):
            old = path.read_bytes()
            try:
                path.write_bytes(b'X'*len(old))
                with self.subTest(path=path.name), self.assertRaisesRegex(ValueError, 'bytes changed'): self.collect()
            finally: path.write_bytes(old)
        self.assertFalse(self.destination.exists())

    def test_wrong_case_output_or_checks_in_saved_receipt_cannot_be_counted(self):
        self.finalize()
        with self.studio.production.connect() as db:
            original = db.execute('SELECT document FROM comparison_reviews WHERE project_id=?', (self.project_id,)).fetchone()['document']
        for mutate in (lambda value: value.update(case_id=self.plan['cases'][1]['id']),
                       lambda value: value['review'].update(output_sha256='0'*64),
                       lambda value: value['review'].update(checks={key: 'uncertain' for key in self.checks})):
            document = json.loads(original); mutate(document['character_review'])
            with self.studio.production.connect() as db:
                db.execute('UPDATE comparison_reviews SET document=? WHERE project_id=?', (json.dumps(document), self.project_id))
            with self.assertRaises(ValueError): self.collect()
        self.assertFalse(self.destination.exists())

    def test_legacy_generic_review_can_opt_into_character_checks_without_inferred_acceptance(self):
        self.rate(); self.command('reveal'); self.command('finalize', selected=self.alias, notes='Earlier generic review.')
        self.command('inspect')
        self.assertIsNone(self.state['character_review'])
        self.assertEqual(set(self.state['candidates'][0]['character_checks'].values()), {'uncertain'})
        self.rate(character_checks=self.checks)
        self.command('finalize', selected=self.alias, notes='Explicit new character review.', character_decision='accepted', reviewer='local-user')
        summary, _ = self.summary()
        self.assertEqual(summary['human_accepted_cases'], 1)

    def test_changed_acceptance_event_is_rejected_by_collection(self):
        self.finalize()
        with self.studio.production.connect() as db:
            row = db.execute('SELECT event FROM comparison_review_events WHERE project_id=? AND revision=?', (self.project_id, self.state['revision'])).fetchone()
            event = json.loads(row['event']); event['reviewer'] = 'local-agent'
            db.execute('UPDATE comparison_review_events SET event=? WHERE project_id=? AND revision=?', (json.dumps(event), self.project_id, self.state['revision']))
        with self.assertRaisesRegex(ValueError, 'review|Review'): self.collect()

    def test_review_changes_during_collection_leave_an_incomplete_snapshot(self):
        self.finalize(); original = results._copy_asset
        def copy_then_edit(*args):
            original(*args); self.rate()
        with patch.object(results, '_copy_asset', side_effect=copy_then_edit):
            with self.assertRaisesRegex(ValueError, 'changed during collection'): self.collect()
        self.assertTrue((self.destination/'.incomplete').exists())
        self.assertFalse((self.destination/'collection.json').exists())


if __name__ == '__main__': unittest.main()

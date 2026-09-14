"""Offline gate for the UX use-case suite: the authored cases and the runner's pure scoring.

No browser, no server, no Playwright import. `python tests/studio_use_cases.py` is the
measured run; this file guards the parts that must stay correct without one.
"""
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import studio_use_cases as runner

CASES = runner.load_cases()
REQUIRED = {'id', 'goal', 'starting_view', 'success_condition', 'steps'}


class Cases(unittest.TestCase):
    def test_document_shape(self):
        self.assertEqual(CASES['version'], 1)
        self.assertEqual(CASES['refs'], '#278')
        self.assertIsInstance(CASES['starting_views'], list)
        self.assertTrue(8 <= len(CASES['cases']) <= 10, 'the brief asks for 8-10 use cases')

    def test_unique_ids(self):
        ids = [case['id'] for case in CASES['cases']]
        self.assertEqual(len(ids), len(set(ids)))
        for identifier in ids: self.assertRegex(identifier, r'^[a-z][a-z0-9-]{4,48}$')

    def test_required_fields_and_known_starting_views(self):
        known = set(CASES['starting_views'])
        for case in CASES['cases']:
            self.assertLessEqual(REQUIRED, set(case), case.get('id'))
            self.assertIn(case['starting_view'], known, case['id'])
            self.assertTrue(case['goal'].endswith('.'), case['id'])
            self.assertGreaterEqual(len(case['goal'].split()), 8, case['id'])
            self.assertGreaterEqual(len(case['success_condition'].split()), 6, case['id'])

    def test_steps_are_intents_not_selectors(self):
        for case in CASES['cases']:
            self.assertGreaterEqual(len(case['steps']), 5, case['id'])
            for step in case['steps']:
                self.assertEqual({'intent', 'expect'}, set(step), case['id'])
                for value in step.values():
                    self.assertTrue(value.strip(), case['id'])
                    self.assertNotRegex(value, r'[#.][A-Za-z][A-Za-z0-9_-]*\s*(\{|\[|>)|data-[a-z-]+=|querySelector',
                                        case['id'] + ': steps must read as intents, not selectors')

    def test_one_case_carries_the_deliberate_wrong_turn(self):
        wrong = [case for case in CASES['cases'] if case.get('wrong_turn')]
        self.assertTrue(wrong, 'at least one case must take a deliberate wrong turn')
        joined = ' '.join(step['intent'] for step in wrong[0]['steps'])
        self.assertIn('text-only', joined)

    def test_every_case_has_a_driver(self):
        for case in CASES['cases']: self.assertIn(case['id'], runner.DRIVERS, case['id'])

    def test_owner_journeys_are_covered(self):
        ids = {case['id'] for case in CASES['cases']}
        for expected in ('first-image-from-brief', 'reference-edit-one-source',
                         'three-reference-identity-pose-style', 'compare-settings-from-recipe',
                         'review-and-keep-winner', 'reuse-keeper-as-reference',
                         'prompt-lab-to-create', 'guided-edit-or-preserve-character',
                         'build-and-prepare-node-workflow', 'frames-to-native-export'):
            self.assertIn(expected, ids)


class WordCounting(unittest.TestCase):
    def test_empty_and_none(self):
        for value in (None, '', '   ', '  \n\t '): self.assertEqual(runner.count_words(value), 0)

    def test_punctuation_is_not_a_word(self):
        self.assertEqual(runner.count_words('Keep the face. Change the cloak!'), 6)
        self.assertEqual(runner.count_words('— · ✕ …'), 0)

    def test_hyphens_apostrophes_and_accents_stay_one_word(self):
        self.assertEqual(runner.count_words("the recipe's text-only façade"), 4)

    def test_digits_and_units_count(self):
        self.assertEqual(runner.count_words('832 × 1216, 15 steps'), 4)


class DeadEnds(unittest.TestCase):
    def test_no_dead_end_on_a_healthy_step(self):
        self.assertIsNone(runner.dead_end({'enabled': True, 'control_missing': False, 'error_status': ''}))

    def test_missing_control_wins(self):
        self.assertEqual(runner.dead_end({'control_missing': True, 'enabled': False, 'error_status': 'boom'}), 'missing-control')

    def test_present_but_unrendered_counts_as_missing(self):
        self.assertEqual(runner.dead_end({'control_missing': False, 'control_hidden': True, 'enabled': True}), 'missing-control')

    def test_disabled_without_a_reason(self):
        self.assertEqual(runner.dead_end({'enabled': False, 'disabled_reason': '   '}), 'unexplained-disabled')

    def test_disabled_with_a_reason_is_not_a_dead_end(self):
        self.assertIsNone(runner.dead_end({'enabled': False, 'disabled_reason': 'Attach a reference first.'}))

    def test_error_status_is_a_dead_end(self):
        self.assertEqual(runner.dead_end({'enabled': True, 'error_status': 'Fixture route not found'}), 'error-status')

    def test_enabled_unknown_is_not_a_dead_end(self):
        self.assertIsNone(runner.dead_end({'enabled': None, 'disabled_reason': ''}))

    def test_kinds_are_the_documented_set(self):
        self.assertEqual(set(runner.DEAD_END_KINDS), {'missing-control', 'unexplained-disabled', 'error-status'})


class Totals(unittest.TestCase):
    def rows(self):
        return [{'action': 'goto', 'performed': True, 'page': '/', 'view': 'homeView', 'panel': 'homeView', 'instruction_words': 10},
                {'action': 'click', 'performed': True, 'page': '/', 'view': 'createView', 'panel': 'createView', 'instruction_words': 20, 'dead_end': None},
                {'action': 'click', 'performed': True, 'page': '/', 'view': 'createView', 'panel': 'createView', 'instruction_words': 5, 'dead_end': 'unexplained-disabled'},
                {'action': 'fill', 'performed': True, 'page': '/', 'view': 'createView', 'panel': 'createView', 'instruction_words': 0},
                {'action': 'click', 'performed': False, 'skipped_live': 'deny-list id: generate', 'page': '/', 'view': 'createView', 'panel': 'experimentDialog', 'instruction_words': 1, 'dead_end': 'missing-control'}]

    def test_counters(self):
        totals = runner.case_totals(self.rows())
        self.assertEqual(totals['steps_taken'], 5)
        self.assertEqual(totals['clicks'], 2, 'a skipped click is not a click')
        self.assertEqual(totals['page_switches'], 1)
        self.assertEqual(totals['dead_ends'], 2)
        self.assertEqual(totals['unexplained_disabled'], 1)
        self.assertEqual(totals['instruction_words'], 31, 'a panel is charged once, when it first comes up')
        self.assertEqual(totals['instruction_words_peak'], 20)
        self.assertEqual(totals['skipped_live'], 1)

    def test_empty_case(self):
        empty = runner.case_totals([])
        self.assertEqual(empty['page_switches'], 0)
        self.assertEqual(empty['instruction_words'], 0)
        self.assertEqual(empty['instruction_words_peak'], 0)

    def test_revisiting_a_panel_is_charged_again(self):
        rows = [{'page': '/', 'panel': 'a', 'instruction_words': 4}, {'page': '/', 'panel': 'b', 'instruction_words': 3},
                {'page': '/', 'panel': 'a', 'instruction_words': 4}]
        self.assertEqual(runner.case_totals(rows)['instruction_words'], 11)

    def test_friction_ranks_dead_ends_before_clicks_then_id(self):
        rows = [{'id': 'b', 'dead_ends': 0, 'clicks': 9}, {'id': 'a', 'dead_ends': 2, 'clicks': 1},
                {'id': 'c', 'dead_ends': 2, 'clicks': 5}, {'id': 'd', 'dead_ends': 0, 'clicks': 9}]
        self.assertEqual([row['id'] for row in runner.friction_points(rows)], ['c', 'a', 'b', 'd'])


class LiveGuard(unittest.TestCase):
    def test_generate_is_denied_by_id(self):
        self.assertIn('deny-list id', runner.deny_reason('generate', 'Generate'))

    def test_denied_labels(self):
        for label in ('Start comparison', 'Render preview', 'Save to Workspace', 'Move to Trash',
                      'Switch backend', 'Download native source pack', 'Install model', 'Choose A'):
            self.assertTrue(runner.deny_reason('', label), label)

    def test_form_submit_is_denied(self):
        self.assertIn('form submit', runner.deny_reason('someButton', 'Apply', (), True))

    def test_state_creating_attributes_are_denied(self):
        self.assertTrue(runner.deny_reason('x', 'Keep it', ('data-choose-candidate',)))

    def test_plain_navigation_is_allowed(self):
        self.assertEqual(runner.deny_reason('studioJump', 'Jump to a tool'), '')
        self.assertEqual(runner.live_allows('click', True, 'studioJump', 'Jump to a tool'), '')

    def test_live_mode_refuses_non_navigation_clicks(self):
        self.assertIn('read-only', runner.live_allows('click', False, 'blindComparison', 'Hide settings while comparing'))

    def test_live_mode_allows_typing_and_reading(self):
        for action in ('read', 'goto', 'fill', 'type'):
            self.assertEqual(runner.live_allows(action, False, 'positive', 'Describe the result'), '')

    def test_deny_list_beats_navigation(self):
        self.assertIn('deny-list', runner.live_allows('click', True, 'generate', 'Generate'))


class Table(unittest.TestCase):
    def test_table_has_a_row_per_case(self):
        rows = [{'id': 'alpha', 'steps_intended': 3, 'steps_taken': 3, 'clicks': 1, 'page_switches': 0,
                 'dead_ends': 0, 'unexplained_disabled': 0, 'instruction_words': 12, 'passed': True}]
        text = runner.table(rows)
        self.assertIn('alpha', text)
        self.assertIn('PASS', text)
        self.assertEqual(len(text.splitlines()), 3)


if __name__ == '__main__': unittest.main()

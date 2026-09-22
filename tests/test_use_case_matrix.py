"""Offline gate for the UX use-case suite: the authored cases and the runner's pure scoring.

No browser, no server, no Playwright import. `python tests/studio_use_cases.py` is the
measured run; this file guards the parts that must stay correct without one.
"""
import inspect
import json
import tempfile
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
        self.assertTrue(8 <= len(CASES['cases']) <= 15, 'the original journeys plus Restyle, Combine, the same-pair experiment loop and the drawn pose')

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
                         'reference-analysis-review-and-apply', 'prompt-lab-to-create',
                         'guided-edit-or-preserve-character',
                         'build-and-prepare-node-workflow', 'frames-to-native-export',
                         'restyle-recent-output-with-a-look'):
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

    def test_peak_and_skips(self):
        totals = runner.case_totals(self.rows())
        self.assertEqual(totals['instruction_words_peak'], 20)
        self.assertEqual(totals['skipped_live'], 1)

    def test_every_generation_capable_route_counts_as_a_submission(self):
        for path in ('/api/jobs', '/api/production/abc/start', '/api/production/abc/resume', '/api/jobs/abc/resume', '/api/workflow-studio/document-runs/abc/run', '/api/av/projects/abc/render'):
            self.assertTrue(runner.GENERATION_ROUTE.search(path), path)
        for path in ('/api/production', '/api/workspace', '/api/prompt/compile', '/api/estimate'):
            self.assertFalse(runner.GENERATION_ROUTE.search(path), path)

    def test_drawing_a_pose_guide_is_not_counted_as_a_submission(self):
        # It ends in /render, so the pattern still matches it; only the named drawing route is excused.
        self.assertTrue(runner.GENERATION_ROUTE.search('/api/pose/render'))
        observed = ['/api/pose/render', '/api/upload', '/api/jobs', '/api/av/projects/abc/render']
        self.assertEqual(runner.submissions(observed), ['/api/jobs', '/api/av/projects/abc/render'])
        self.assertEqual(runner.submissions(['/api/pose/render']), [])

    def test_empty_case(self):
        empty = runner.case_totals([])
        self.assertEqual(empty['page_switches'], 0)
        self.assertEqual(empty['instruction_words'], 0)
        self.assertEqual(empty['instruction_words_peak'], 0)

    def test_revisiting_a_panel_is_not_charged_again(self):
        rows = [{'page': '/', 'panel': 'a', 'instruction_words': 4}, {'page': '/', 'panel': 'b', 'instruction_words': 3},
                {'page': '/', 'panel': 'a', 'instruction_words': 4}]
        self.assertEqual(runner.case_totals(rows)['instruction_words'], 7, 'a panel is charged once per case, however often it is revisited')

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

    def test_reading_a_denied_control_is_still_measured(self):
        self.assertEqual(runner.live_allows('read', False, 'generate', 'Generate'), '',
                         'measuring a control must never be blocked; only doing is')
        self.assertTrue(runner.deny_reason('generate', 'Generate'), 'the deny list itself still names it')

    def test_deny_list_beats_navigation(self):
        self.assertIn('deny-list', runner.live_allows('click', True, 'generate', 'Generate'))

    def test_a_listed_local_control_skips_the_label_heuristic(self):
        """#486: a recipe card's description says 'one run of this recipe'; picking it only loads the recipe."""
        label = 'Qwen Atelier - 1 Reference Heavy 20B edit: one run of this recipe'
        self.assertIn('deny-list label', runner.live_allows('click', False, '#presetList [data-id="qwen-1ref"]', label))
        self.assertEqual(runner.live_allows('click', False, '#presetList [data-id="qwen-1ref"]', label, (), False,
                                            '#presetList [data-id="qwen-1ref"]'), '')

    def test_id_and_attribute_deny_lists_beat_the_local_list(self):
        self.assertIn('deny-list id', runner.live_allows('click', True, 'generate', 'Generate', (), False, '#presetList [data-id="x"]'))
        self.assertIn('deny-list attribute', runner.live_allows('click', True, 'x', 'Keep', ('data-choose-candidate',), False, '[data-asset-open="x"]'))

    def test_the_local_list_covers_clicks_only(self):
        self.assertIn('read-only', runner.live_allows('press', False, 'workshopReview', 'Review checks', (), False, '#workshopReview'))

    def test_no_local_control_is_a_denied_id_and_every_one_says_why(self):
        for selector, why in runner.LOCAL_CONTROLS.items():
            self.assertEqual(runner.control_kind(selector), selector, 'keys are value-free: ' + selector)
            self.assertNotIn(selector.lstrip('#'), runner.DENY_IDS, selector)
            self.assertTrue(why.strip(), selector)

    def test_writing_controls_stay_off_the_local_list(self):
        for selector in ('#uxPrepareHandoff', '[data-ux-pull="a"]', '#productionDetail [data-choose-candidate="a"]',
                         '#prepareExperiment', '#nativeExport', '#saveSharedWorkflow', '#generate'):
            self.assertNotIn(runner.control_kind(selector), runner.LOCAL_CONTROLS, selector)
            control_id = selector[1:] if selector.startswith('#') and ' ' not in selector else selector
            self.assertTrue(runner.live_allows('click', False, control_id, 'x', (), False, selector), selector)

    def test_pulling_a_saved_picture_is_denied_by_attribute(self):
        self.assertIn('data-ux-pull', runner.deny_reason('x', 'A picture', ('data-ux-pull',)))

    def test_control_kind_strips_attribute_values_only(self):
        self.assertEqual(runner.control_kind('#productionList [data-project="ab\\"c"]'), '#productionList [data-project]')
        self.assertEqual(runner.control_kind(' #gallery .reference-output[data-job="j"][data-index="0"] '),
                         '#gallery .reference-output[data-job][data-index]')
        self.assertEqual(runner.control_kind('#workshopReview'), '#workshopReview')


class LiveOutcomes(unittest.TestCase):
    """#486: live journeys end with a named STOP or SKIP instead of a fake missing-control dead end."""

    def test_the_fixture_id_wins_when_the_live_page_lists_it(self):
        self.assertEqual(runner.choose_live_value(['newest', 'asset-1', 'older'], 'asset-1'), 'asset-1')

    def test_otherwise_the_first_the_page_lists(self):
        self.assertEqual(runner.choose_live_value(['newest-live', 'older-live'], 'asset-1'), 'newest-live')
        self.assertEqual(runner.choose_live_value(['newest-live', 'older-live'], 'asset-1', nth=1), 'older-live')
        self.assertIsNone(runner.choose_live_value(['only-one'], 'asset-1', nth=1))

    def test_blank_duplicate_non_text_and_unsafe_values_are_ignored(self):
        self.assertEqual(runner.choose_live_value(['', '  ', None, 7, 'a"]', 'x' * 200, 'newest', 'newest', 'older'], nth=1), 'older')
        self.assertIsNone(runner.choose_live_value(['', None, '   ']))
        self.assertIsNone(runner.choose_live_value(None))

    def test_a_skip_needs_a_bounded_named_reason_and_a_known_kind(self):
        for bad in ('', '   ', 'x' * 301):
            with self.assertRaises(ValueError): runner.LiveCaseSkip(bad)
        with self.assertRaises(ValueError): runner.LiveCaseSkip('no asset', 'maybe')
        skip = runner.LiveCaseSkip('  no image   asset ', 'read-only')
        self.assertEqual((str(skip), skip.reason, skip.kind), ('no image asset', 'no image asset', 'read-only'))

    def test_results_and_counts(self):
        rows = [{'passed': True}, {'passed': False, 'skip_kind': 'read-only'}, {'passed': False, 'skip_kind': 'missing'}, {'passed': False}]
        self.assertEqual([runner.case_result(row) for row in rows], ['PASS', 'STOP', 'SKIP', 'FAIL'])
        self.assertEqual(runner.outcome_counts(rows), {'passed': 1, 'stopped': 1, 'skipped': 1, 'failed': 1, 'reached': 2})

    def run_stub(self, live, kind):
        case_id = 'live-outcome-stub'
        def stub(case): raise runner.LiveCaseSkip('no image asset in the Asset library', kind)
        runner.DRIVERS[case_id] = stub
        spec = {'id': case_id, 'goal': 'g', 'starting_view': 'assets', 'success_condition': 's', 'steps': []}
        try:
            with tempfile.TemporaryDirectory() as temporary:
                return runner.run_case(spec, object(), 'http://127.0.0.1:8191', live, Path(temporary))
        finally: runner.DRIVERS.pop(case_id, None)

    def test_a_live_skip_is_named_and_is_neither_a_failure_nor_a_dead_end(self):
        for kind, result, prefix in (('missing', 'SKIP', 'skipped: '), ('read-only', 'STOP', 'stopped: ')):
            row = self.run_stub(True, kind)
            self.assertEqual((row['passed'], row['failure'], row['dead_ends'], row['steps_taken']), (False, '', 0, 0))
            self.assertEqual((row['skip_kind'], row['skip_reason'], row['result']), (kind, 'no image asset in the Asset library', result))
            self.assertEqual(row['detail'], prefix + 'no image asset in the Asset library')
            self.assertIn(result, runner.table([row]))
            self.assertEqual(runner.verdict({'mode': 'live-readonly', 'rows': [row], 'generation_submissions': 0, 'page_errors': []}), [])

    def test_fixture_mode_never_skips(self):
        row = self.run_stub(False, 'missing')
        self.assertEqual((row['passed'], row['skip_kind'], row['result']), (False, '', 'FAIL'))
        self.assertIn('fixture mode never skips', row['failure'])
        self.assertTrue(runner.verdict({'mode': 'fixture', 'rows': [row], 'generation_submissions': 0, 'page_errors': []}))

    def test_journeys_that_named_fixture_ids_resolve_live_ones_and_stop_before_writing(self):
        for driver in (runner._one_reference, runner._three_references, runner._review, runner._reuse, runner._native_export):
            self.assertIn('c.pick(', inspect.getsource(driver), driver.__name__)
        for driver in (runner._restyle, runner._combine, runner._draw_pose):
            self.assertIn('c.pick_output()', inspect.getsource(driver), driver.__name__)
        for driver in (runner._one_reference, runner._three_references, runner._compare, runner._review, runner._reuse,
                       runner._native_export, runner._restyle, runner._combine, runner._draw_pose):
            self.assertIn('c.stop_before(', inspect.getsource(driver), driver.__name__)
        self.assertNotIn("== 'asset-1'", inspect.getsource(runner._reuse))


class Table(unittest.TestCase):
    def test_table_has_a_row_per_case(self):
        rows = [{'id': 'alpha', 'steps_intended': 3, 'steps_taken': 3, 'clicks': 1, 'page_switches': 0,
                 'dead_ends': 0, 'unexplained_disabled': 0, 'instruction_words': 12, 'passed': True}]
        text = runner.table(rows)
        self.assertIn('alpha', text)
        self.assertIn('PASS', text)
        self.assertEqual(len(text.splitlines()), 3)


class Verdict(unittest.TestCase):
    """The runner's exit contract. `main()` returned 0 whatever it measured until #611, so a failing
    journey was a green CI check; the two lanes carried hand-copied gate steps instead."""

    def matrix(self, **overrides):
        base = {'mode': 'fixture', 'cases': 1, 'passed': 1, 'generation_submissions': 0, 'page_errors': [],
                'rows': [{'id': 'alpha', 'passed': True}]}
        base.update(overrides)
        return base

    def test_a_clean_run_is_green(self):
        self.assertEqual(runner.verdict(self.matrix()), [])

    def test_a_failed_journey_is_red_and_names_itself(self):
        reasons = runner.verdict(self.matrix(cases=2, passed=1, rows=[{'id': 'alpha', 'passed': True}, {'id': 'beta', 'passed': False}]))
        self.assertEqual(len(reasons), 1)
        self.assertIn('beta', reasons[0])
        self.assertNotIn('alpha', reasons[0])

    def test_a_page_error_is_red(self):
        reasons = runner.verdict(self.matrix(page_errors=['alpha: TypeError: x is not a function']))
        self.assertEqual(len(reasons), 1)
        self.assertIn('TypeError', reasons[0])

    def test_a_generation_submission_is_red(self):
        reasons = runner.verdict(self.matrix(generation_submissions=1))
        self.assertEqual(len(reasons), 1)
        self.assertIn('submitted a generation', reasons[0])

    def test_measuring_nothing_is_red_not_green(self):
        """Zero failures out of zero cases reads exactly like a clean pass; it is not one."""
        reasons = runner.verdict(self.matrix(cases=0, passed=0, rows=[]))
        self.assertEqual(len(reasons), 1)
        self.assertIn('nothing was measured', reasons[0])

    def test_every_reason_is_reported_not_just_the_first(self):
        reasons = runner.verdict(self.matrix(generation_submissions=2, page_errors=['boom'], rows=[{'id': 'beta', 'passed': False}]))
        self.assertEqual(len(reasons), 3)

    def test_a_missing_key_does_not_read_as_green(self):
        self.assertTrue(runner.verdict({}), 'an empty or truncated matrix must not pass')

    def test_a_truncated_report_is_red_by_absence_not_green_by_default(self):
        """The deleted CI steps subscripted these keys and crashed when they were absent; reading them
        with .get() would otherwise score a hand-edited or partial artifact as a clean pass."""
        for key in runner.REPORT_KEYS:
            partial = self.matrix(); partial.pop(key)
            reasons = runner.verdict(partial)
            self.assertTrue(any('missing ' + key in reason for reason in reasons), key)

    def test_live_mode_journey_results_are_advisory(self):
        """Live mode is read-only: the deny list refuses most deciding clicks on purpose, so the
        documented `--base-url` run must not report a healthy Studio as a failure."""
        self.assertEqual(runner.verdict(self.matrix(mode='live-readonly', cases=2, passed=1,
                                                    rows=[{'id': 'alpha', 'passed': True}, {'id': 'beta', 'passed': False}])), [])

    def test_live_mode_still_binds_everything_else(self):
        for override in ({'generation_submissions': 1}, {'page_errors': ['boom']}, {'rows': []}):
            self.assertTrue(runner.verdict(self.matrix(mode='live-readonly', **override)), override)

    def test_the_process_exit_code_is_the_verdict(self):
        """Returning 1 only gates CI if the entry point propagates it; nothing else can test that line."""
        source = (ROOT / 'tests/studio_use_cases.py').read_text(encoding='utf-8')
        self.assertIn("if __name__ == '__main__': raise SystemExit(main())", source)


class CaseSelection(unittest.TestCase):
    def test_an_unknown_case_id_is_refused_rather_than_filtered_away(self):
        """Filtering to an id no manifest carries used to run zero cases and exit 0 (#611). This also
        pins that the refusal stays above the playwright import: the offline lane has no browser."""
        with self.assertRaises(SystemExit) as caught: runner.main(['--case', 'no-such-journey'])
        self.assertIn('no-such-journey', str(caught.exception))

    def test_one_unknown_id_among_real_ones_is_still_refused(self):
        with self.assertRaises(SystemExit) as caught: runner.main(['--case', CASES['cases'][0]['id'], '--case', 'no-such-journey'])
        self.assertIn('no-such-journey', str(caught.exception))
        self.assertNotIn(CASES['cases'][0]['id'], str(caught.exception))


if __name__ == '__main__': unittest.main()

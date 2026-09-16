"""Refuse an ambiguous numeric combo before the UI can propose the wrong JSON type."""
import argparse
from pathlib import Path
import unittest
from playwright.sync_api import expect
import workflow_control_preview_browser as fixture
from test_workflow_control_preview import fixture as request_fixture

class NumericChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.ControlPreviewBrowserTests.setUpClass()
    @classmethod
    def tearDownClass(cls): fixture.ControlPreviewBrowserTests.tearDownClass()
    def test_integer_valued_float_choice_is_not_silently_proposed_as_int(self):
        harness=fixture.ControlPreviewBrowserTests('test_combo_preserves_boolean_vs_integer_choice')
        harness.setUp(); self.addCleanup(harness.doCleanups)
        harness.value,harness.info=request_fixture(first=[[1.0,1,'safe']],second=[[1.0,1,'safe']])
        harness.open();harness.add();harness.add('b')
        harness.page.locator('#controlProposedValue').select_option('0')
        harness.page.locator('#controlPreviewButton').click()
        expect(harness.page.locator('#controlPreviewStatus')).to_contain_text('int versus float')
        self.assertEqual(harness.requests,[])
        expect(harness.page.locator('#controlProposedValue option').nth(0)).to_contain_text('use SDK')
        harness.page.locator('#controlProposedValue').select_option('2')
        harness.page.locator('#controlPreviewButton').click();harness.state('ready')
        self.assertEqual(harness.requests[-1]['value'],'safe')

if __name__=='__main__':
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--browser-path');parser.add_argument('--out',type=Path)
    args,rest=parser.parse_known_args();fixture.BROWSER=args.browser_path;fixture.OUT=args.out
    if args.out:args.out.mkdir(parents=True,exist_ok=True)
    unittest.main(argv=[__file__,*rest])

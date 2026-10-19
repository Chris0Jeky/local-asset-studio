"""Browser-driver result and encoding contracts, without Playwright or a model."""
import argparse
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import asset_detail_browser as driver
import asset_detail_driver_probe as probe


class Page:
    async def expose_function(self, name, callback): pass
    async def set_content(self, markup): self.markup=markup


class BrowserDriverTests(unittest.TestCase):
    def test_baseline_tolerates_expectation_failure_only(self):
        driver.check_result([{'status':'fail'}], [], baseline=True)
        with self.assertRaises(SystemExit) as raised:
            driver.check_result([{'status':'fail'}], [], baseline=False)
        self.assertEqual(raised.exception.code, 1)

    def test_javascript_errors_are_fatal_even_with_baseline_and_passing_checks(self):
        for baseline in (False, True):
            with self.subTest(baseline=baseline), self.assertRaises(SystemExit) as raised:
                driver.check_result([{'status':'pass'}], ['Synthetic JavaScript exception'], baseline)
            self.assertEqual(raised.exception.code, 1)

    def test_clean_checks_succeed_in_both_modes(self):
        for baseline in (False, True):
            driver.check_result([{'status':'pass'}], [], baseline)

    def test_inert_assets_decode_utf8_under_a_legacy_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'index.html').write_text('<head><title>景色 →</title><link rel="stylesheet" href="/static/qa.css"></head><script src="/static/qa.js"></script>',encoding='utf-8')
            (root/'qa.js').write_text("window.label='α · 藍';",encoding='utf-8')
            (root/'qa.css').write_text('/* 模型 · → */',encoding='utf-8')
            read=Path.read_text
            def legacy_read(path,*args,**kwargs):
                kwargs.setdefault('encoding','cp1252')
                return read(path,*args,**kwargs)
            page=Page()
            with patch.object(driver,'STATIC',root), patch.object(Path,'read_text',legacy_read):
                asyncio.run(driver.inert_page(page,1))
            self.assertIn('景色 →',page.markup)
            self.assertIn("window.label='α · 藍';",page.markup)
            self.assertIn('/* 模型 · → */',page.markup)

    def test_delay_bounds(self):
        for value in ('0','400','2000'):self.assertEqual(driver.delay_milliseconds(value),int(value))
        for value in ('-1','2001'):
            with self.assertRaises(argparse.ArgumentTypeError):driver.delay_milliseconds(value)


class DriverProbeReceiptTests(unittest.TestCase):
    def run_probe(self, overrides=None):
        fixtures={
            'page-error':{'returncode':1,'pass':47,'fail':1,'errors':['intentional QA probe exception']},
            'expectation':{'returncode':0,'pass':46,'fail':2,'errors':[]},
        }
        for case,changes in (overrides or {}).items():fixtures[case].update(changes)
        cases=[]
        def child(command, **kwargs):
            case=command[command.index('--case')+1];cases.append(case)
            directory=Path(command[command.index('--out')+1]);directory.mkdir(parents=True)
            result=fixtures[case]
            (directory/'receipt.json').write_text(json.dumps({k:result[k] for k in ('pass','fail','errors')}),encoding='utf-8')
            return SimpleNamespace(returncode=result['returncode'],stdout='',stderr='')
        with tempfile.TemporaryDirectory() as directory, patch.object(probe.sys,'argv',['probe','--out',directory]), patch.object(probe.subprocess,'run',side_effect=child):
            result=probe.main()
        return result,cases

    def test_current_complete_receipts_preserve_both_baseline_exit_contracts(self):
        result,cases=self.run_probe()
        self.assertEqual(result,0)
        self.assertEqual(cases,['page-error','expectation'])

    def test_incomplete_receipt_is_rejected_for_either_probe(self):
        for case,passes in [('page-error',46),('expectation',45)]:
            with self.subTest(case=case), self.assertRaisesRegex(RuntimeError,'incomplete or unexpected scenario failures'):
                self.run_probe({case:{'pass':passes}})

    def test_probe_requires_the_expected_exit_and_only_the_injected_fault(self):
        for case,changes,reason in [
            ('page-error',{'returncode':0},'expected exit 1'),
            ('expectation',{'returncode':1},'expected exit 0'),
            ('page-error',{'errors':[]},'JavaScript error evidence'),
            ('expectation',{'errors':['unexpected']},'JavaScript error evidence'),
            ('page-error',{'pass':46,'fail':2},'unexpected scenario failures'),
            ('expectation',{'pass':47,'fail':1},'unexpected scenario failures'),
        ]:
            with self.subTest(case=case,changes=changes), self.assertRaisesRegex(RuntimeError,reason):
                self.run_probe({case:changes})


if __name__=='__main__':unittest.main()

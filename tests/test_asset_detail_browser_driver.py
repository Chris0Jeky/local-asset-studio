"""Browser-driver result and encoding contracts, without Playwright or a model."""
import argparse
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import asset_detail_browser as driver


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


if __name__=='__main__':unittest.main()

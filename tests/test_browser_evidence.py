"""Evidence timeouts never replace behavioural results; other capture errors still fail."""
import contextlib
import io
import unittest
from unittest.mock import AsyncMock, Mock

from browser_ports import evidence_screenshot
try:
    from playwright.sync_api import TimeoutError as ScreenshotTimeout
except ImportError:
    ScreenshotTimeout = None


@unittest.skipIf(ScreenshotTimeout is None, 'Playwright is not installed')
class BrowserEvidenceTests(unittest.TestCase):
    def test_timeout_prints_skip_and_returns(self):
        page = Mock(); page.screenshot.side_effect = ScreenshotTimeout('slow Windows capture')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(evidence_screenshot(page, path='final.png', full_page=True))
        self.assertIn('evidence screenshot skipped: slow Windows capture', output.getvalue())
        page.screenshot.assert_called_once_with(path='final.png', full_page=True, timeout=30000, animations='disabled')

    def test_success_preserves_screenshot(self):
        page = Mock(); page.screenshot.return_value = b'png'
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(evidence_screenshot(page, path='final.png'), b'png')
        self.assertEqual(output.getvalue(), '')

    def test_other_errors_stay_strict(self):
        page = Mock(); page.screenshot.side_effect = ValueError('bad path')
        with self.assertRaisesRegex(ValueError, 'bad path'): evidence_screenshot(page, path='final.png')


@unittest.skipIf(ScreenshotTimeout is None, 'Playwright is not installed')
class AsyncBrowserEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_prints_skip_and_returns(self):
        page = Mock(); page.screenshot = AsyncMock(side_effect=ScreenshotTimeout('slow Windows capture'))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(await evidence_screenshot(page, path='final.png', full_page=True))
        self.assertIn('evidence screenshot skipped: slow Windows capture', output.getvalue())
        page.screenshot.assert_awaited_once_with(path='final.png', full_page=True, timeout=30000, animations='disabled')

    async def test_success_preserves_screenshot(self):
        page = Mock(); page.screenshot = AsyncMock(return_value=b'png')
        self.assertEqual(await evidence_screenshot(page, path='final.png'), b'png')

    async def test_other_errors_stay_strict(self):
        page = Mock(); page.screenshot = AsyncMock(side_effect=ValueError('bad path'))
        with self.assertRaisesRegex(ValueError, 'bad path'): await evidence_screenshot(page, path='final.png')

"""#907 spike: the unchanged Python static handler serves the committed Vue island, and the flag-off page is unchanged."""
import hashlib
import importlib.util
import io
import json
import re
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'app/static/ui-dist'
SPEC = importlib.util.spec_from_file_location('ui_island_server', ROOT / 'app/server.py')
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
JS_TYPES = ('text/javascript', 'application/javascript')  # both are valid module-script MIME types; Windows and 3.12 differ


def get(path, host='127.0.0.1:8191'):
    handler = server.Handler.__new__(server.Handler)
    handler.studio = None  # static routes never touch Studio state
    handler.path = path
    handler.headers = {'Host': host}
    calls = {'status': None, 'headers': {}}
    body = io.BytesIO()
    handler.send_response = lambda status: calls.update(status=status)
    handler.send_header = lambda key, value: calls['headers'].__setitem__(key, value)
    handler.end_headers = lambda: None
    handler.wfile = Mock(); handler.wfile.write.side_effect = body.write
    handler.do_GET()
    return calls['status'], calls['headers'], body.getvalue()


class UiIslandStaticTests(unittest.TestCase):
    def test_island_assets_are_served_with_module_and_css_types(self):
        status, headers, body = get('/static/ui-dist/island.js')
        self.assertEqual(status, 200)
        self.assertIn(headers['Content-Type'].split(';')[0], JS_TYPES)
        self.assertEqual(body, (DIST / 'island.js').read_bytes())
        status, headers, body = get('/static/ui-dist/island.css')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'].split(';')[0], 'text/css')
        self.assertEqual(body, (DIST / 'island.css').read_bytes())

    def test_output_is_servable_matches_its_manifest_and_stays_in_budget(self):
        manifest = json.loads((DIST / 'manifest.json').read_text(encoding='utf-8'))
        served = sorted(p.name for p in DIST.iterdir() if p.name != 'manifest.json')
        self.assertEqual(served, sorted(manifest['files']))
        for name, record in manifest['files'].items():
            self.assertRegex(name, r'^[a-z-]+\.(js|css)$')  # the static handler serves .html/.js/.css only
            self.assertEqual(hashlib.sha256((DIST / name).read_bytes()).hexdigest(), record['sha256'], name)
        self.assertLessEqual(manifest['budget']['gzipTotalBytes'], manifest['budget']['gzipLimitBytes'])
        self.assertLessEqual(manifest['budget']['gzipLimitBytes'], 150 * 1024)
        # The manifest is a build/CI record, not a runtime lookup: the unchanged handler does not serve JSON.
        self.assertEqual(get('/static/ui-dist/manifest.json')[0], 404)

    def test_island_has_no_remote_fetches_or_source_maps(self):
        js = (DIST / 'island.js').read_text(encoding='utf-8')
        self.assertNotIn('sourceMappingURL', js)
        self.assertNotRegex(js, r'fetch\(\s*[`"\']https?:')
        self.assertNotRegex(js, r'import\(\s*[`"\']https?:')
        self.assertNotRegex((DIST / 'island.css').read_text(encoding='utf-8'), r'url\(|@import|@font-face')

    def test_host_guard_is_not_widened_for_the_island(self):
        self.assertEqual(get('/static/ui-dist/island.js', host='127.0.0.1:5173')[0], 403)
        self.assertEqual(get('/static/ui-dist/island.js', host='localhost:5173')[0], 403)

    def test_flag_off_page_is_unchanged(self):
        status, _, body = get('/')
        self.assertEqual(status, 200)
        self.assertEqual(body, (ROOT / 'app/static/index.html').read_bytes())
        self.assertNotIn(b'ui-dist', body)
        shell = (ROOT / 'app/static/studio-shell.js').read_text(encoding='utf-8')
        # The only reference to the island is the loader, and it returns unless ?ui=island is present.
        self.assertEqual(shell.count('ui-dist'), 2)
        loader = re.search(r"const loadIsland=\(\)=>\{(.*?)\};\n", shell)
        self.assertIsNotNone(loader)
        self.assertTrue(loader.group(1).startswith("if(new URLSearchParams(location.search).get('ui')!=='island'"))
        for name in ('index.html', 'workshop.js', 'app.js', 'studio-workbench.js'):
            self.assertNotIn('ui-dist', (ROOT / 'app/static' / name).read_text(encoding='utf-8'), name)


if __name__ == '__main__':
    unittest.main()

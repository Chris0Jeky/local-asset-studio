"""Node presentation contracts, included in the normal offline suite."""
import base64
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkshopFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is unavailable')
    def test_presentation_contracts(self):
        result = subprocess.run(['node', '--test', 'tests/workshop_contracts.cjs'], cwd=ROOT,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skin_heading_art_is_inlined_because_static_handler_refuses_svg(self):
        css = (ROOT / 'app/static/workshop.css').read_text(encoding='utf-8')
        self.assertNotIn("url('workshop-assets/", css)
        self.assertGreaterEqual(css.count('data:image/svg+xml;base64,'), 2)
        self.assertIn('[data-workshop-skin="arcade"] .ux-create-heading', css)
        self.assertIn('[data-workshop-skin="sakura"] .ux-create-heading', css)

    def test_immersive_ambience_art_is_local_inert_and_inlined(self):
        entrypoint = (ROOT / 'app/static/workshop-immersive.css').read_text(encoding='utf-8')
        core = (ROOT / 'app/static/workshop-immersive-core.css').read_text(encoding='utf-8')
        css = core + '\n' + entrypoint
        workshop = (ROOT / 'app/static/workshop.js').read_text(encoding='utf-8')
        self.assertIn("@import url('workshop-immersive-core.css');", entrypoint)
        self.assertNotIn('/static/workshop-assets/', css)
        self.assertEqual(css.count('data:image/svg+xml;base64,'), 2)
        self.assertIn("css.href = '/static/workshop-immersive.css'", workshop)
        self.assertIn('repeat(auto-fit,minmax(min(100%,280px),1fr))', entrypoint)
        self.assertIn('grid-template-columns:minmax(0,1.15fr)', entrypoint)
        payloads = re.findall(r'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)', core)
        self.assertEqual(len(payloads), 2)
        for payload in payloads:
            rendered = base64.b64decode(payload, validate=True).decode('utf-8')
            lowered = rendered.lower()
            self.assertIn('<svg', lowered)
            self.assertNotIn('<script', lowered)
            self.assertNotIn('<foreignobject', lowered)
            self.assertIsNone(re.search(r'\bhref\s*=', lowered))
            self.assertIn('xmlns="http://www.w3.org/2000/svg"', lowered)
            self.assertEqual(lowered.count('http://'), 1)
            self.assertNotIn('https://', lowered)

    def test_job_problems_render_into_a_host_outside_recent_runs(self):
        workshop = (ROOT / 'app/static/workshop.js').read_text(encoding='utf-8')
        app = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        host = workshop.index("problemsHost.id = 'jobProblemsHost'")
        results = workshop.index("disclosure('workshopResults'")
        append = workshop.index('create.append(problemsHost, results)')
        self.assertLess(host, results)
        self.assertLess(results, append)
        self.assertIn("document.getElementById?.('jobProblemsHost')", app)
        self.assertIn('if(host)host.innerHTML=problemMarkup;', app)
        self.assertIn("host?'':problemMarkup", app)
        self.assertIn("problemsHost.onclick = q('#gallery')?.onclick;", workshop)

    def test_i2v_hold_note_is_not_grouped_into_two_column_fieldset(self):
        js = (ROOT / 'app/static/workshop.js').read_text(encoding='utf-8')
        css = (ROOT / 'app/static/workshop.css').read_text(encoding='utf-8')
        fixture = (ROOT / 'tests/workshop_fixture.html').read_text(encoding='utf-8')
        body = js[js.index('function groupControls()'):js.index('function applyPresentation()')]
        self.assertIn("if (label.querySelector('#i2vMode')) continue;", body)
        self.assertIn('id="i2vMode"', fixture)
        self.assertIn('id="i2vModeNote"', fixture)
        self.assertIn('.workshop #controls>label:has(#i2vMode)', css)

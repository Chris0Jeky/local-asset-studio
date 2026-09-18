import json
from pathlib import Path

CASE_ID = 'reference-analysis-review-and-apply'

# Register the selector-free owner journey immediately before the existing Prompt Lab bridge case.
manifest_path = Path('research/ux/use-cases.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
if not any(case['id'] == CASE_ID for case in manifest['cases']):
    case = {
        'id': CASE_ID,
        'goal': 'Review exported reference analysis against the exact original pictures and apply only the approved facets to the Prompt Lab draft.',
        'starting_view': 'prompt-lab',
        'success_condition': 'The originals match by content, the prepared diff is reviewed before Apply, the applied draft keeps its references and visible diff, and no generation is submitted.',
        'wrong_turn': False,
        'steps': [
            {'intent': 'open Prompt Lab at the reference review workspace',
             'expect': 'the ordinary prompt fields and the reference review panel are shown'},
            {'intent': 'load an exported reference analysis for review',
             'expect': 'the analysis summary and editable reference facets appear'},
            {'intent': 'match the analysis to the exact original pictures',
             'expect': 'the panel confirms every original by content rather than filename'},
            {'intent': 'edit and approve the style facet that should influence the draft',
             'expect': 'the reviewed style wording is selected for the prepared change'},
            {'intent': 'preview the reviewed reference changes without applying them',
             'expect': 'a prepared result is created while the current Prompt Lab draft stays unchanged'},
            {'intent': 'inspect the before and after diff before applying anything',
             'expect': 'the diff names the reference changes and Apply becomes available'},
            {'intent': 'apply the prepared reference changes explicitly',
             'expect': 'the approved style and reference records enter the current draft'},
            {'intent': 'confirm the applied draft and its review evidence remain visible',
             'expect': 'the references and applied diff remain present and no generation request was sent'},
        ],
    }
    index = next(i for i, existing in enumerate(manifest['cases']) if existing['id'] == 'prompt-lab-to-create')
    manifest['cases'].insert(index, case)
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

# Keep the offline manifest gate aligned with the newly registered journey.
test_path = Path('tests/test_use_case_matrix.py')
test_source = test_path.read_text(encoding='utf-8')
test_source = test_source.replace("8 <= len(CASES['cases']) <= 14", "8 <= len(CASES['cases']) <= 15")
needle = "                         'prompt-lab-to-create', 'guided-edit-or-preserve-character',"
replacement = "                         'reference-analysis-review-and-apply', 'prompt-lab-to-create',\n                         'guided-edit-or-preserve-character',"
if needle not in test_source and replacement not in test_source:
    raise SystemExit('owner journey tuple changed')
test_source = test_source.replace(needle, replacement)
test_path.write_text(test_source, encoding='utf-8')

# Serve the production reference-review HTTP extension from the existing synthetic use-case server.
runner_path = Path('tests/studio_use_cases.py')
runner = runner_path.read_text(encoding='utf-8')
import_marker = "    from studio_workflow.core import catalog, new_document, compile_document\n"
import_replacement = import_marker + "    from studio_prompt.http_extension import extend_handler\n"
if 'from studio_prompt.http_extension import extend_handler' not in runner:
    if runner.count(import_marker) != 1:
        raise SystemExit('build_handler import marker changed')
    runner = runner.replace(import_marker, import_replacement)

class_marker = "    class Handler(fixture.Handler):\n"
class_replacement = """    class PromptFixtureBase(fixture.Handler):
        studio = None

        def _json(self, status, value):
            return self.json(value, status)

        def _safe_host(self):
            return self.headers.get('Host') == '127.0.0.1:%s' % self.server.server_port

        def _safe_mutation(self):
            return self._safe_host() and self.headers.get('Origin') == 'http://127.0.0.1:%s' % self.server.server_port

        def _content_length(self, limit):
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= length <= limit:
                raise ValueError('Request too large')
            return length

    class Handler(extend_handler(PromptFixtureBase)):
"""
if 'class PromptFixtureBase(fixture.Handler):' not in runner:
    if runner.count(class_marker) != 1:
        raise SystemExit('fixture handler marker changed')
    runner = runner.replace(class_marker, class_replacement)

# The measured driver uses deterministic synthetic analysis and image bytes, while the production
# panel, draft owner and HTTP preview implementation remain real.
driver_marker = "@driver('prompt-lab-to-create')\n"
driver_source = r'''@driver('reference-analysis-review-and-apply')
def _reference_analysis_review(c):
    import base64
    from test_reference_review import ReferenceReviewTests

    c.goto('/prompt-lab.html', note='reference review workspace')
    try:
        c.page.wait_for_selector('#profile option', state='attached', timeout=8000)
    except Exception:
        pass

    if c.live:
        c.act('#rr-analysis', 'read', note='live mode does not load a synthetic analysis')
        c.act('#rr-originals', 'read', note='live mode does not attach synthetic originals')
        c.act('#rr-cards', 'read', note='facet cards appear after an analysis is loaded')
        c.act('#rr-preview', 'read', note='preview is measured but not posted in live read-only mode')
        c.act('#rr-diff', 'read', note='the prepared before/after review surface')
        c.act('#rr-apply', 'read', note='Apply is measured but never pressed in live read-only mode')
        c.observe('reference review is registered without generation', True,
                  'full deterministic preview/apply evidence runs in fixture mode')
        return True, 'live read-only controls registered; fixture mode owns preview/apply evidence'

    fixture = ReferenceReviewTests()
    fixture.setUp()
    analysis = {
        'name': 'reference-analysis.json',
        'mimeType': 'application/json',
        'buffer': json.dumps({'analysis': fixture.report}).encode('utf-8'),
    }
    c.page.locator('#rr-analysis').set_input_files(analysis)
    try:
        c.page.wait_for_function("document.querySelector('#rr-summary').textContent.trim().length > 0", timeout=8000)
    except Exception:
        pass
    summary_ok = c.page.locator('#rr-summary').inner_text().strip() == fixture.report['answer']['summary']
    c.observe('the analysis summary and editable facets are shown', summary_ok,
              'analysis summary did not match the imported report')

    originals = []
    for index, source in enumerate(fixture.images):
        originals.append({
            'name': 'renamed-%d.png' % index,
            'mimeType': source.get('media_type') or 'image/png',
            'buffer': base64.b64decode(source['media_base64']),
        })
    c.page.locator('#rr-originals').set_input_files(list(reversed(originals)))
    try:
        c.page.wait_for_function("document.querySelector('#rr-source-status').textContent.includes('originals matched')", timeout=8000)
    except Exception:
        pass
    matched = '2 originals matched' in c.page.locator('#rr-source-status').inner_text()
    c.observe('the exact originals are matched by content', matched,
              c.page.locator('#rr-source-status').inner_text())

    style_selector = '[data-reference="picture-1"] [data-facet="style"] textarea'
    c.act(style_selector, 'fill', typed='bold expressive ink')
    checkbox = c.page.locator('[data-reference="picture-1"] [data-facet="style"] input')
    if checkbox.count() and not checkbox.is_checked():
        checkbox.check()

    before = c.page.locator('#brief').input_value()
    c.act('#rr-preview')
    try:
        c.page.wait_for_function("!document.querySelector('#rr-apply').disabled", timeout=8000)
    except Exception:
        pass
    prepared = (c.page.locator('#rr-apply').is_enabled() and
                bool(c.page.locator('#rr-diff').inner_text().strip()) and
                c.page.locator('#brief').input_value() == before)
    c.observe('the prepared before and after diff', prepared,
              'Apply enabled=%s, draft unchanged=%s' % (
                  c.page.locator('#rr-apply').is_enabled(), c.page.locator('#brief').input_value() == before))

    c.act('#rr-apply')
    applied_style = c.page.locator('#style').input_value()
    references = c.page.evaluate('StudioPromptDraft.capture().intent.references.length')
    retained_diff = c.page.locator('#rr-diff').inner_text().strip()
    applied = applied_style == 'bold expressive ink' and references == 2 and bool(retained_diff)
    c.observe('the applied reference draft and retained diff', applied,
              'style=%r, references=%s, diff retained=%s' % (applied_style, references, bool(retained_diff)))
    return applied and prepared and matched and summary_ok, \
        'summary=%s, originals=%s, prepared=%s, references=%s, retained diff=%s' % (
            summary_ok, matched, prepared, references, bool(retained_diff))


'''
if "@driver('reference-analysis-review-and-apply')" not in runner:
    if runner.count(driver_marker) != 1:
        raise SystemExit('Prompt Lab driver marker changed')
    runner = runner.replace(driver_marker, driver_source + driver_marker)
runner_path.write_text(runner, encoding='utf-8')

# Document what the new row measures, without rewriting historical matrix measurements.
docs_path = Path('docs/UX-USE-CASE-MATRIX.md')
docs = docs_path.read_text(encoding='utf-8')
section = """## Reference analysis review and Apply — 18 September 2026

`reference-analysis-review-and-apply` now registers the Prompt Lab reference-review pipeline as an
owner-shaped journey. In fixture mode it loads deterministic exported analysis, supplies the same
original image bytes under renamed files, edits an approved style facet, prepares the real before/after
diff through the production reference-review HTTP extension, applies explicitly, and verifies that the
applied references and diff remain visible. The journey records every step and the global use-case
harness still rejects any generation-capable request.

This is interface and data-contract evidence, not evidence that a vision model described a real owner
image well. `tests/reference_review_browser.py` remains the deeper two-viewport proof for undo,
stale-response handling, receipt export, exact-original refusal and text-zoom layout. The focused CI
lane runs both that proof and this measured matrix case.

"""
heading = '# UX use-case matrix\n\n'
if '`reference-analysis-review-and-apply`' not in docs:
    if docs.count(heading) != 1:
        raise SystemExit('UX matrix heading changed')
    docs = docs.replace(heading, heading + section, 1)
docs_path.write_text(docs, encoding='utf-8')

# Keep the measured journey and the richer dedicated browser proof in a focused CI lane.
workflow = """name: Reference review use case
on:
  pull_request:
    paths:
      - 'app/static/prompt-lab.html'
      - 'app/static/prompt-lab.js'
      - 'app/static/reference-review.js'
      - 'studio_prompt/**'
      - 'research/ux/use-cases.json'
      - 'docs/UX-USE-CASE-MATRIX.md'
      - 'tests/studio_use_cases.py'
      - 'tests/reference_review_browser.py'
      - 'tests/test_reference_review*.py'
      - '.github/workflows/reference-review-use-case.yml'
permissions:
  contents: read
jobs:
  reference-review-journey:
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install pillow playwright==1.57.0
      - run: python -m playwright install --with-deps chromium
      - name: Offline registration and reference-review contracts
        run: |
          python -m unittest discover -s tests -p 'test_reference_review*.py' -v
          python -m unittest tests/test_use_case_matrix.py -v
      - name: Measured matrix journey
        run: python tests/studio_use_cases.py --case reference-analysis-review-and-apply --out .runtime/reference-review-use-case.json
      - name: Two-viewport production-panel proof
        run: python tests/reference_review_browser.py --output .runtime/reference-review/browser
      - run: python scripts/validate-repo.py
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: reference-review-use-case-proof
          path: |
            .runtime/reference-review-use-case.json
            .runtime/ux-use-cases/reference-analysis-review-and-apply/
            .runtime/reference-review/browser/
          if-no-files-found: ignore
          retention-days: 7
"""
Path('.github/workflows/reference-review-use-case.yml').write_text(workflow, encoding='utf-8')

"""Owner-shaped end-to-end UX use cases, measured in a real browser. Fixture mode never contacts ComfyUI;
live mode only reaches the loopback Studio, whose own health probe reads ComfyUI system stats.

    python tests/studio_use_cases.py                      # fixture mode (default), full run
    python tests/studio_use_cases.py --case first-image-from-brief
    python tests/studio_use_cases.py --base-url http://127.0.0.1:8191   # live, read-only

Fixture mode reuses tests/studio_browser_smoke.py's synthetic API server (imported, not
copied) and adds only the extra read routes the deeper journeys touch. Live mode is
read-only navigation and typing: every click is checked against an explicit deny list
first, and anything that would create server state is recorded as skipped, never pressed.

Intents live in research/ux/use-cases.json (selector-free, owner's words). The selectors
live here, one driver per case id, so the matrix reports the pipeline, not the markup.
Writes research/ux/use-case-matrix.json and .runtime/ux-use-cases/<case>/NN.png.

Exit code: 0 only when every measured journey reached its success condition with no page
error, no generation submitted and at least one case run. In live mode the journey results are
advisory - the deny list refuses most deciding clicks by design - but a submitted generation, a
page exception or an empty run are still red. The report is written either way, so a red run
still leaves its evidence; see verdict() and tests/test_use_case_matrix.py.
"""
import argparse
import copy
import json
import os
import re
import shutil
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASES_PATH = ROOT / 'research/ux/use-cases.json'
MATRIX_PATH = ROOT / 'research/ux/use-case-matrix.json'
SHOTS_ROOT = ROOT / '.runtime/ux-use-cases'

# --------------------------------------------------------------------------------------
# Pure scoring helpers. No browser, no network: tests/test_use_case_matrix.py covers these.
# --------------------------------------------------------------------------------------
# Letters and digits only: × ÷ — · ✕ and other symbols are not words a reader has to read.
WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
DEAD_END_KINDS = ('missing-control', 'unexplained-disabled', 'error-status')
CLICK_ACTIONS = ('click', 'check', 'select')


def count_words(text):
    """Instruction words a reader actually has to read. Punctuation and digits-only runs are not words."""
    return len(WORD.findall(text or ''))


def dead_end(record):
    """Name the dead end in one step record, or None. Order is the order a user meets them.

    A control that is present in the DOM but not rendered counts as missing: the person
    looking for it cannot see, scroll to or press it, which is the same dead end.
    """
    if record.get('control_missing') or record.get('control_hidden'): return 'missing-control'
    if record.get('enabled') is False and not str(record.get('disabled_reason') or '').strip(): return 'unexplained-disabled'
    if str(record.get('error_status') or '').strip(): return 'error-status'
    return None


# Any route that can start or resume engine work, not only direct job creation: comparison
# start/resume, job resume, saved-workflow runs, scene and voice renders.
OBSERVED_POSTS = []  # every POST the browser sent, both modes; the fixture's own log is not available live
GENERATION_ROUTE = re.compile(r'^/api/jobs$|^/api/[a-z0-9_/-]+/(start|resume|run|render|generate)$')
# One route ends in /render without being engine work: the pose editor rasterises a drawn skeleton with
# Pillow into the Studio's own uploads folder. tests/test_pose_guide.py proves it reaches no model, creates
# no job and queues nothing, so it is named here rather than left to read as a submission.
DRAWING_ROUTES = ('/api/pose/render',)


def submissions(paths):
    """The observed POSTs that could have started engine work."""
    return [path for path in paths if path not in DRAWING_ROUTES and GENERATION_ROUTE.search(path)]


def case_totals(records):
    """Roll one case's step records up into the matrix row counters.

    Instruction words count what the person newly has to read: a panel's words are
    charged once, when that panel first comes up, not again on every step inside it.
    """
    dead = [r for r in records if r.get('dead_end')]
    unexplained = [r for r in records if r.get('dead_end') == 'unexplained-disabled']
    clicks = len([r for r in records if r.get('action') in CLICK_ACTIONS and r.get('performed')])
    switches, words, previous, charged = 0, 0, None, set()
    for record in records:
        where = (record.get('page'), record.get('view'))
        if previous is not None and where != previous: switches += 1
        previous = where
        panel = (record.get('page'), record.get('panel'))
        if panel not in charged: words += int(record.get('instruction_words') or 0); charged.add(panel)
    return {'steps_taken': len(records), 'clicks': clicks, 'page_switches': switches,
            'dead_ends': len(dead), 'unexplained_disabled': len(unexplained),
            'instruction_words': words,
            'instruction_words_peak': max([int(r.get('instruction_words') or 0) for r in records] or [0]),
            'skipped_live': len([r for r in records if r.get('skipped_live')])}


def friction_points(rows):
    """Rank cases by dead ends first, then clicks. Stable on id so a rerun prints the same order."""
    def key(row): return (-row.get('dead_ends', 0), -row.get('clicks', 0), row.get('id', ''))
    return sorted(rows, key=key)


REPORT_KEYS = ('mode', 'rows', 'generation_submissions', 'page_errors')


def verdict(matrix):
    """Every reason this measured run must not count as green, worst first; empty means green.

    The exit code is this list, so a red journey cannot pass as a green check (#611). A run that
    measured nothing is red too: filtering to an unknown case id used to leave zero rows, and zero
    failures out of zero cases reads exactly like a clean pass. A report missing the keys this reads
    is red rather than green by absence.

    Live mode is the one carve-out: it is read-only, so the deny list refuses most journeys' deciding
    click on purpose and a row that stopped short there is the guard working. Everything else still
    binds in live mode — a submitted generation, a page exception, an empty run."""
    reasons = []
    missing = [key for key in REPORT_KEYS if key not in matrix]
    if missing: reasons.append('The report is missing ' + ', '.join(missing) + ', so it cannot be read as green.')
    if matrix.get('generation_submissions'): reasons.append('A use case submitted a generation; that must never happen.')
    failed = [str(row.get('id')) for row in matrix.get('rows') or () if not row.get('passed')]
    if failed and matrix.get('mode') != 'live-readonly': reasons.append('Use cases that did not reach their success condition: ' + ', '.join(failed))
    if matrix.get('page_errors'): reasons.append('The page raised exceptions: ' + '; '.join(str(error) for error in matrix['page_errors']))
    if not matrix.get('rows'): reasons.append('No use case ran, so nothing was measured.')
    return reasons


# --------------------------------------------------------------------------------------
# Live-mode guard. Checked before every click in every mode; enforced in live mode.
# --------------------------------------------------------------------------------------
DENY_IDS = {
    'generate', 'prepareExperiment', 'prepareNative', 'prepareArticulated', 'newExperiment',
    'planComparison', 'switchBackend', 'importAssets', 'importWorkflow', 'importRecipe',
    'saveAssetDetails', 'save', 'assetTrash', 'assetDownload', 'nativeExport', 'createScene',
    'saveSharedWorkflow', 'copySharedWorkflow', 'retrySharedWorkflow', 'prepareSavedRun',
    'exportGraph', 'saveWorkflow', 'refreshModels', 'retryRecovery', 'uxPrepareHandoff',
    'uxImportDraftButton', 'uxExportDraft', 'compare', 'newCollection', 'deleteCollection',
    'uxPoseUse',
}
DENY_LABELS = re.compile(
    r'\b(generate|start\s+(comparison|export|voice|take)|render|save\s+to\s+workspace|'
    r'move\s+to\s+trash|trash|switch\s+backend|download|install|delete|prepare|submit|'
    r'run\b|resume|stop|branch\s+this|needs\s+another\s+pass|choose\s+[a-z]\b)', re.I)
DENY_ATTRS = ('data-project-action', 'data-choose-candidate', 'data-bulk', 'data-ux-review', 'data-ux-rerun', 'download')


def deny_reason(control_id='', label='', attributes=(), submits=False):
    """Why this control must not be clicked against a live Studio. Empty string means allowed."""
    if control_id and control_id in DENY_IDS: return 'deny-list id: ' + control_id
    if label and DENY_LABELS.search(label): return 'deny-list label: ' + ' '.join(label.split())[:60]
    for attribute in attributes:
        if attribute in DENY_ATTRS: return 'deny-list attribute: ' + attribute
    if submits: return 'deny-list: form submit would create server state'
    return ''


def live_allows(action, navigation, control_id='', label='', attributes=(), submits=False):
    """Live mode default: read-only navigation and typing. Returns '' when allowed.

    Reading a control touches nothing, so the deny list never blocks a measurement —
    it blocks doing. Everything else is denied first, then allowed only for typing
    and for clicks the driver declared as navigation.
    """
    if action == 'read': return ''
    reason = deny_reason(control_id, label, attributes, submits)
    if reason: return reason
    if action in ('goto', 'fill', 'type'): return ''
    if action in CLICK_ACTIONS and navigation: return ''
    return 'live mode is read-only: ' + action + ' is not navigation or typing'


# --------------------------------------------------------------------------------------
# Fixture server: studio_browser_smoke's data plus the extra read routes these journeys need.
# --------------------------------------------------------------------------------------
def build_handler():
    import studio_browser_smoke as fixture
    from studio_workflow.guides import guides
    from studio_workflow.core import catalog, new_document, compile_document
    from studio_prompt.http_extension import extend_handler
    from test_server import server

    info = {'Sink': {'input': {'required': {'text': ['STRING', {}], 'seed': ['INT', {'min': 0, 'max': 2 ** 64 - 1}]}}, 'output': [], 'output_node': True}}
    schema = catalog(info, 'primary')
    document = new_document({'1': {'class_type': 'Sink', 'inputs': {'text': 'Synthetic use-case fixture', 'seed': 42}}}, schema)

    # One extra comparison plan: the smoke fixture's plans carry no stages, and reviewing a
    # finished comparison is one of the owner's journeys. Additive; the smoke data is untouched.
    keeper = dict(id='c' * 32, name='Lantern keeper · finished comparison', kind='comparison',
                  state={'status': 'awaiting_review', 'message': 'Synthetic finished comparison; no model ran.'},
                  axis='cfg', values=[3.5, 5.0], budget={'allowance': 4, 'reserved': 2},
                  stages=[{'label': 'A', 'operation': 'generate', 'attempt': {'job_id': 'fixture-job'},
                           'job': dict(fixture.JOBS[0], id='candidate-a', elapsed_seconds=12.0,
                                       outputs=[{'filename': 'a.png', 'asset_id': 'asset-0', 'media_type': 'image', 'seed': 42}])},
                          {'label': 'B', 'operation': 'generate', 'attempt': {'job_id': 'fixture-job'},
                           'job': dict(fixture.JOBS[0], id='candidate-b', elapsed_seconds=13.0,
                                       outputs=[{'filename': 'b.png', 'asset_id': 'asset-1', 'media_type': 'image', 'seed': 43}])}])
    if not any(plan['id'] == keeper['id'] for plan in fixture.PLANS): fixture.PLANS.insert(0, keeper)

    class PromptFixtureBase(fixture.Handler):
        studio = None
        # Production's own length guard; its host/origin guards hard-code :8191 and this fixture
        # binds an ephemeral port, so they are restated against the port actually served.
        _content_length = server.Handler._content_length

        def _safe_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def _safe_mutation(self):
            origin = self.headers.get('Origin')
            return self._safe_host() and origin in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}')

        def _json(self, status, value):
            return self.json(value, status)

    class Handler(extend_handler(PromptFixtureBase)):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/workflow-studio/guides': return self.json(guides())
            if path == '/api/workflow-studio/nodes': return self.json(schema)
            if path == '/api/workflow-studio/capabilities':
                return self.json({'version': 1, 'run': {'available': False, 'reason': 'The use-case fixture never executes graphs.'}, 'generation_submitted': False})
            if path == '/api/workflow-studio/documents': return self.json({'documents': []})
            if path == '/api/workflow-studio/document-runs': return self.json({'runs': []})
            if path.startswith('/api/workflow-studio/presets/'):
                return self.json({'document': dict(document, source={'preset_id': path.rsplit('/', 1)[-1], 'authoring_only': True}), 'generation_submitted': False})
            if path == '/api/health':
                return self.json({'online': True, 'worker_alive': True, 'schema_available': True, 'missing_models': {}, 'devices': [], 'comfy_url': 'fixture://none'})
            if path.startswith('/api/jobs/') and path.endswith('/recipe'):
                job = next(j for j in fixture.JOBS if j['id'] == path.split('/')[3])
                return self.json(dict(version=2, preset_id=job['preset_id'], controls=job['controls'],
                                      continuation=job.get('continuation'), references=job.get('references', []),
                                      parent_assets=job.get('parent_assets', []), batch_count=1))
            if path.startswith('/api/jobs/'):
                return self.json(next((job for job in fixture.JOBS if job['id'] == path.rsplit('/', 1)[-1]), {'error': 'Missing synthetic job'}))
            return super().do_GET()

        def do_POST(self):
            path = urlsplit(self.path).path
            length = int(self.headers.get('Content-Length', '0'))
            if path in ('/api/workflow-studio/compile', '/api/workflow-studio/nodes/refresh'):
                raw = json.loads(self.rfile.read(length) or b'{}')
                fixture.POSTS.append({'path': path, 'data': {}})
                return self.json(schema if path.endswith('/refresh') else compile_document(raw['document'], schema))
            if path == '/api/upload':
                self.rfile.read(length); fixture.POSTS.append({'path': path, 'data': {}})
                return self.json({'file': 'f' * 32 + '_upload.png', 'sha256': 'a' * 64, 'width': 512, 'height': 768})
            if path == '/api/pose/render':
                # The same shape app/pose_guide.py accepts, so the journey proves what the page sends.
                data = json.loads(self.rfile.read(length) or b'{}'); fixture.POSTS.append({'path': path, 'data': {}})
                if not isinstance(data, dict) or set(data) != {'width', 'height', 'keypoints'} or len(data['keypoints']) != 18:
                    return self.json({'error': 'The fixture accepts one 18-joint pose and nothing else'}, 400)
                return self.json({'file': 'f' * 32 + '_drawn-pose.png', 'sha256': 'd' * 64, 'bytes': 2048,
                                  'width': data['width'], 'height': data['height'], 'original_name': 'drawn-pose',
                                  'artifact_id': 'e' * 64, 'renderer': 'studio.coco18-lines/v1', 'generation_submitted': False})
            if path == '/api/recipe-check':
                data = json.loads(self.rfile.read(length)); fixture.POSTS.append({'path': path, 'data': data})
                preset = next(p for p in fixture.CATALOG['presets'] if p['id'] == data['preset_id'])
                return self.json({'template_sha256': preset['continuation_capability']['template_sha256']})
            if path == '/api/assets/update':
                data = json.loads(self.rfile.read(length)); fixture.POSTS.append({'path': path, 'data': data})
                if data.get('action') != 'edit' or set(data) != {'action', 'ids', 'review', 'workspace_id', 'expected_revisions', 'request_id'}:
                    return self.json({'error': 'Only explicit tile review is supported by this fixture'}, 400)
                assets = [next(a for a in fixture.ASSETS if a['id'] == identifier) for identifier in data['ids']]
                if any(a['metadata_revision'] != data['expected_revisions'][a['id']] for a in assets):
                    return self.json({'error': 'Synthetic metadata conflict'}, 409)
                for asset in assets: asset.update(review=data['review'], metadata_revision=asset['metadata_revision'] + 1)
                return self.json(dict(status='applied', workspace_id=data['workspace_id'], request_id=data['request_id'],
                                      action='edit', updated=data['ids'], revisions={a['id']: a['metadata_revision'] for a in assets},
                                      applied={'review': data['review']}, current=copy.deepcopy(assets)))
            if path == '/api/preview':
                self.rfile.read(length); fixture.POSTS.append({'path': path, 'data': {}})
                return self.json({'graph': {'note': 'Synthetic resolved recipe; no generation submitted.'}})
            if path == '/api/production':
                data = json.loads(self.rfile.read(length) or b'{}'); fixture.POSTS.append({'path': path, 'data': data})
                plan = dict(id='d' * 32, name=data.get('name') or 'Prepared comparison', kind='comparison',
                            state={'status': 'planned', 'message': 'Prepared in the fixture. Preparing is not starting.'},
                            axis=data.get('axis') or 'cfg', values=data.get('values') or [], stages=[],
                            budget={'allowance': int(data.get('max_generations') or 2), 'reserved': 0})
                fixture.PLANS.insert(0, plan); return self.json(plan)
            if path == '/api/production-export':
                data = json.loads(self.rfile.read(length) or b'{}'); fixture.POSTS.append({'path': path, 'data': data})
                plan = dict(id='e' * 32, name='Prepared native export', kind='native',
                            state={'status': 'planned', 'message': 'Export prepared in the fixture. Start it explicitly.'},
                            stages=[], budget={'allowance': 0, 'reserved': 0})
                fixture.PLANS.insert(0, plan); return self.json(plan)
            if path.startswith('/api/production/') and path.endswith('/review'):
                data = json.loads(self.rfile.read(length) or b'{}'); fixture.POSTS.append({'path': path, 'data': data})
                identifier = path.split('/')[3]
                for plan in fixture.PLANS:
                    if plan['id'] == identifier:
                        plan['state'] = dict(plan['state'], status='reviewed', message='Choice recorded in the fixture.',
                                             review={'asset_id': data.get('asset_id'), 'notes': data.get('notes'), 'reviewer': data.get('reviewer')})
                        return self.json(plan)
                return self.json({'error': 'Unknown fixture study'}, 404)
            return super().do_POST()

    return Handler, fixture


# --------------------------------------------------------------------------------------
# Browser-side probes.
# --------------------------------------------------------------------------------------
PROBE_ELEMENT = """(el) => {
  const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
  const shown = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  const text = t => (t || '').replace(/\\s+/g, ' ').trim();
  const name = text(el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.getAttribute('placeholder') || el.id);
  const disabled = el.disabled === true || el.getAttribute('aria-disabled') === 'true';
  const reasons = [];
  const described = el.getAttribute('aria-describedby');
  if (described) for (const id of described.split(/\\s+/)) reasons.push(text(document.getElementById(id)?.textContent));
  reasons.push(text(el.getAttribute('title')));
  for (const sibling of [el.previousElementSibling, el.nextElementSibling]) if (sibling && !sibling.matches('button,input,select,textarea,a')) reasons.push(text(sibling.textContent));
  const holder = el.closest('label,article,section,fieldset,div,dialog,form');
  if (holder) for (const hint of holder.querySelectorAll('small,.muted,.hint,[role=status],[role=alert],p'))
    if (!hint.contains(el)) reasons.push(text(hint.textContent));
  const attributes = [...el.attributes].map(a => a.name);
  const submits = el.type === 'submit' || (el.form != null && el.tagName === 'BUTTON' && el.type !== 'button');
  return {shown, name, disabled, attributes, submits,
    in_viewport: shown && rect.top >= 0 && rect.left >= 0 && rect.bottom <= innerHeight && rect.right <= innerWidth,
    reason: reasons.filter(Boolean).join(' | ').slice(0, 400)};
}"""

PROBE_PAGE = """() => {
  const text = t => (t || '').replace(/\\s+/g, ' ').trim();
  const dialog = [...document.querySelectorAll('dialog')].find(d => d.open);
  const views = [...document.querySelectorAll('section.view')].filter(v => !v.hidden && v.getBoundingClientRect().height > 0);
  const panel = dialog || views[0] || document.querySelector('main') || document.body;
  const seen = new Set();
  for (const node of panel.querySelectorAll('p,small,label,legend,summary,figcaption,.muted,.hint,.callout,[role=status],[role=alert]')) {
    if (!node.offsetParent && node !== panel) continue;
    const own = [...node.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ');
    const value = text(own || (node.children.length ? '' : node.textContent));
    if (value) seen.add(value);
  }
  const errors = [];
  for (const node of document.querySelectorAll('[role=alert], .error')) {
    if (!node.offsetParent) continue;
    const value = text(node.textContent);
    if (value) errors.push(value);
  }
  return {view: views[0]?.id || (dialog ? dialog.id : '') || '', dialog: dialog?.id || '',
    panel: dialog?.id || views[0]?.id || 'page', instructions: [...seen].join(' '),
    error: errors.join(' | ').slice(0, 400), hash: location.hash, path: location.pathname};
}"""


class CaseRun:
    """Drives one use case, recording a measurement per intended step."""

    def __init__(self, spec, page, origin, live, screenshots):
        self.spec, self.page, self.origin, self.live = spec, page, origin, live
        self.dir = screenshots / spec['id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', spec['id']): raise ValueError('Unsafe case id: %r' % (spec['id'],))
        if self.dir.exists(): shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.records, self.cursor, self.notes = [], 0, []

    # -- step plumbing -----------------------------------------------------------------
    def _intent(self):
        steps = self.spec['steps']
        step = steps[self.cursor] if self.cursor < len(steps) else {'intent': 'unplanned step taken by the driver', 'expect': ''}
        self.cursor += 1
        return step

    def _page_state(self):
        try: return self.page.evaluate(PROBE_PAGE)
        except Exception as error: return {'view': '', 'dialog': '', 'panel': '', 'instructions': '', 'error': 'probe failed: ' + str(error), 'hash': '', 'path': ''}

    def _shot(self, index):
        name = '%02d.png' % index
        try: self.page.screenshot(path=str(self.dir / name))
        except Exception: return ''
        return str((self.dir / name).relative_to(ROOT)).replace('\\', '/')

    def _finish(self, record):
        state = self._page_state()
        record.update(page=state['path'] or '/', view=state['view'] or state['panel'], panel=state['panel'],
                      hash=state['hash'], url=self.page.url,
                      instruction_words=count_words(state['instructions']),
                      error_status=state['error'] if record.get('performed') else '')
        record['dead_end'] = dead_end(record)
        record['screenshot'] = self._shot(len(self.records) + 1)
        self.records.append(record)
        return record

    # -- actions -----------------------------------------------------------------------
    def act(self, selector, action='click', typed=None, navigation=False, note='', timeout=3000, wait=250, supplementary=False):
        # Extra disclosure actions are measured without shifting the owner's task intents.
        step = {'intent': note, 'expect': 'The requested surface is available.'} if supplementary else self._intent()
        record = {'index': len(self.records) + 1, 'intent': step['intent'], 'expect': step.get('expect', ''),
                  'action': action, 'selector': selector, 'typed': typed, 'note': note,
                  'control': '', 'control_name': '', 'control_missing': False, 'control_hidden': False,
                  'enabled': None, 'visible_before_scroll': None, 'disabled_reason': '', 'performed': False,
                  'skipped_live': '', 'failure': ''}
        locator = self.page.locator(selector).first
        try: locator.wait_for(state='attached', timeout=timeout)
        except Exception:
            record['control_missing'] = True
            return self._finish(record)
        try: probe = locator.evaluate(PROBE_ELEMENT)
        except Exception as error:
            record['control_missing'] = True; record['failure'] = str(error)[:200]
            return self._finish(record)
        record.update(control=self._identity(selector), control_name=probe['name'],
                      control_hidden=not probe['shown'],
                      enabled=not probe['disabled'], visible_before_scroll=bool(probe['in_viewport']),
                      disabled_reason=probe['reason'] if probe['disabled'] else '')
        blocked = live_allows(action, navigation, self._identity(selector), probe['name'], probe['attributes'], probe['submits']) if self.live else ''
        if blocked:
            record['skipped_live'] = blocked
            return self._finish(record)
        if action == 'read' or record['control_hidden']:
            if record['control_hidden']: record['failure'] = record['failure'] or 'control is present but not rendered'
            return self._finish(record)
        try:
            if action == 'click': locator.click(timeout=timeout)
            elif action == 'fill': locator.fill(typed or '', timeout=timeout)
            elif action == 'select': locator.select_option(typed, timeout=timeout)
            elif action == 'check': locator.check(timeout=timeout)
            else: raise ValueError('Unknown action: ' + action)
            record['performed'] = True
        except Exception as error:
            record['failure'] = str(error).splitlines()[0][:200]
        self.page.wait_for_timeout(wait)
        return self._finish(record)

    def _identity(self, selector):
        match = re.match(r'^#([A-Za-z0-9_-]+)$', selector.strip())
        return match.group(1) if match else selector

    def goto(self, url, note='', wait=400):
        step = self._intent()
        record = {'index': len(self.records) + 1, 'intent': step['intent'], 'expect': step.get('expect', ''),
                  'action': 'goto', 'selector': url, 'typed': None, 'note': note, 'control': url,
                  'control_name': url, 'control_missing': False, 'control_hidden': False, 'enabled': True,
                  'visible_before_scroll': True, 'disabled_reason': '', 'performed': True,
                  'skipped_live': '', 'failure': ''}
        try:
            self.page.goto(url if url.startswith('http') else self.origin + url)
            self.page.wait_for_timeout(wait)
        except Exception as error:
            record['failure'] = str(error).splitlines()[0][:200]; record['performed'] = False
        return self._finish(record)

    def observe(self, description, ok, detail='', note=''):
        """A read-only verification step: no control is pressed, the screen is measured."""
        step = self._intent()
        record = {'index': len(self.records) + 1, 'intent': step['intent'], 'expect': step.get('expect', ''),
                  'action': 'read', 'selector': description, 'typed': None, 'note': note or detail,
                  'control': description, 'control_name': description, 'control_missing': not ok,
                  'control_hidden': False, 'enabled': None, 'visible_before_scroll': None, 'disabled_reason': '',
                  'performed': True, 'skipped_live': '', 'failure': '' if ok else detail}
        return self._finish(record)

    # -- helpers used by drivers --------------------------------------------------------
    def boot(self, route='#home'):
        self.page.goto(self.origin + '/' + route)
        self.page.wait_for_function('!!window.selected || !!document.querySelector("#homeView")', timeout=15000)
        self.page.wait_for_timeout(400)

    def select_preset(self, preset_id):
        self.page.evaluate('selectPreset("%s")' % preset_id); self.page.wait_for_timeout(250)

    def ready(self):
        try: return self.page.locator('#generate').is_enabled()
        except Exception: return False

    def studies(self):
        """Ids currently listed in Runs & review, so 'a study appeared' means a NEW one."""
        try: return set(self.page.eval_on_selector_all('#productionList [data-project]', 'nodes => nodes.map(n => n.dataset.project)'))
        except Exception: return set()

    def wait_for_new_study(self, before, timeout=10000):
        """Wait until Runs & review lists a study that was not there before the prepare."""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            fresh = self.studies() - before
            if fresh: return fresh
            self.page.wait_for_timeout(250)
        return self.studies() - before

    def wait_for_studies(self, timeout=10000):
        """Wait for Runs & review to actually render a study.

        Preparing posts, switches view and refreshes; a fixed sleep is a flake on a
        slower machine (hosted CI, 14 Sep 2026). Returns the rendered study count.
        """
        try: self.page.wait_for_function("document.querySelectorAll('#productionList [data-project]').length > 0", timeout=timeout)
        except Exception: pass
        return self.page.locator('#productionList [data-project]').count()

    def dialog_status(self, selector):
        """Whatever a prepare dialog last reported, so a failure explains itself."""
        try: return ' '.join(self.page.locator(selector).inner_text().split())[:120]
        except Exception: return ''


# --------------------------------------------------------------------------------------
# Drivers. One per case id; the call order must match the intents in use-cases.json.
# --------------------------------------------------------------------------------------
DRIVERS = {}


def driver(case_id):
    def register(function): DRIVERS[case_id] = function; return function
    return register


BRIEF = ('A lanternkeeper of the deep wood: a young elf with silver-grey hair, a patched green '
         'travelling cloak and a brass lantern, standing among tall pines at dusk.')


@driver('first-image-from-brief')
def _first_image(c):
    c.boot('#home')
    c.act('#uxJourneys, #uxRecent', 'read', note='overview starting points')
    c.act('[data-studio-route="create"]', navigation=True)
    c.act('#workshopRecipeChange', note='open the recipe picker', supplementary=True)
    c.act('#presetSearch', 'fill', typed='anima')
    c.act('#presetList button.preset', note='first matching recipe')
    c.act('#positive', 'fill', typed=BRIEF)
    c.act('#negativeWrap > summary', note='open optional exclusions', supplementary=True)
    c.act('#negative', 'fill', typed='blurry, extra fingers, watermark')
    c.act('#generate', 'read', note='readiness only; never pressed')
    return c.ready(), 'run control enabled=%s' % c.ready()


@driver('reference-edit-one-source')
def _one_reference(c):
    c.boot('#create')
    c.act('#workshopRecipeChange', note='open the recipe picker', supplementary=True)
    c.act('#presetList [data-id="anima-portrait"]', note='a text-only illustration recipe')
    c.act('#uxPullAsset', note='deliberate wrong turn: text-only recipe has no reference slot')
    c.act('#uxSourcePicker[open], #referenceHint, #uxNotice', 'read', note='what the screen says after the wrong turn')
    c.act('#workshopRecipeChange', note='open the recipe picker', supplementary=True)
    c.act('#presetSearch', 'fill', typed='Atelier')
    c.act('#presetList [data-id="qwen-1ref"]', note='the one-reference Qwen Atelier recipe')
    c.act('#uxPullAsset')
    if c.page.locator('#uxSourcePicker[open]').count():
        if c.live: c.act('[data-ux-pull="asset-0"]', 'read', note='live mode: pulling a reference writes server state; not clicked')
        else:
            try: c.page.click('[data-ux-pull="asset-0"]', timeout=4000); c.page.wait_for_timeout(500)
            except Exception: pass
    c.act('#positive', 'fill', typed='Change the cloak to deep blue. Keep the face, hair and lantern exactly as they are.')
    c.act('#generate', 'read', note='readiness only; never pressed')
    return c.ready(), 'run control enabled=%s' % c.ready()


@driver('three-reference-identity-pose-style')
def _three_references(c):
    c.boot('#create')
    c.act('#workshopRecipeChange', note='open the recipe picker', supplementary=True)
    c.act('#presetList [data-id="qwen-3ref"]', note='the three-reference Qwen Atelier recipe')
    for index, (role, asset) in enumerate([('identity', 'asset-0'), ('pose', 'asset-1'), ('style', 'asset-4')]):
        c.act('[data-ref-role="%d"]' % index, 'select', typed=role)
        c.act('#uxPullAsset', note='attach picture %d' % (index + 1))
        picked = False
        if c.page.locator('#uxSourcePicker[open]') .count() and c.live: c.act('[data-ux-pull="%s"]' % asset, 'read', note='live mode: pulling a reference writes server state; not clicked')
        elif c.page.locator('#uxSourcePicker[open]').count():
            try:
                c.page.select_option('#uxSourceSlot', str(index), timeout=3000)
                c.page.click('[data-ux-pull="%s"]' % asset, timeout=4000); c.page.wait_for_timeout(600); picked = True
            except Exception: pass
        if not picked and c.page.locator('#uxSourcePicker[open]').count():
            try: c.page.click('[data-ux-close="uxSourcePicker"]', timeout=2000)
            except Exception: pass
    c.act('[data-ref-contribution="0"]', 'fill', typed='Face, hair colour and the brass lantern.')
    c.act('#positive', 'fill', typed='Same character, seated and reading. Keep the face and lantern unchanged.')
    c.act('#generate', 'read', note='readiness only; never pressed')
    filled = c.page.evaluate('referenceRecords.filter(r=>r.file).length')
    return c.ready() and filled == 3, '%d/3 slots attached, run control enabled=%s' % (filled, c.ready())


@driver('compare-settings-from-recipe')
def _compare(c):
    c.boot('#create')
    c.act('#workshopRecipeChange', note='open the recipe picker', supplementary=True)
    c.act('#presetList [data-id="anima-portrait"]', note='the baseline recipe')
    c.act('#positive', 'fill', typed=BRIEF)
    c.act('#workshopReview', note='open run details', supplementary=True)
    c.act('#planComparison')
    c.act('#experimentAxis', 'select', typed='cfg')
    c.act('#experimentValues', 'read', note='proposed candidate values')
    # The planner sizes the allowance up to the proposed values (never down); the driver still sets
    # the total by hand so the step it measures stays the same across runs.
    proposed = len([v for v in (c.page.locator('#experimentValues').input_value() or '').split(',') if v.strip()])
    before = c.studies()
    c.act('#experimentBudget', 'fill', typed=str(max(proposed, 1)), note='%d proposed values need at least %d runs' % (proposed, proposed))
    c.act('#prepareExperiment')
    fresh = c.wait_for_new_study(before)
    status = c.dialog_status('#experimentStatus')
    detail = '%d new study listed (allowance %d for %d values)%s' % (len(fresh), max(proposed, 1), proposed, '; planner said: ' + status if status else '')
    c.act('#productionList', 'read', note=detail)
    return bool(fresh), detail


@driver('review-and-keep-winner')
def _review(c):
    c.boot('#production')
    c.act('#productionList', 'read', note='%d studies listed' % c.wait_for_studies())
    c.act('#productionList [data-project="%s"]' % ('c' * 32), note='the finished comparison')
    c.act('#blindComparison', note='reveal candidate settings')
    c.act('#productionDetail [data-candidate-open]', note='open a candidate at full size')
    if c.page.locator('#assetDialog[open]').count():
        try: c.page.click('#closeAssetDialog', timeout=3000); c.page.wait_for_timeout(300)
        except Exception: pass
    c.act('#productionNotes', 'fill', typed='Candidate A keeps the silhouette and the lantern glow; B loses the face.')
    c.act('#productionDetail [data-choose-candidate]', note='keep the winner')
    c.page.wait_for_timeout(600)
    recorded = 'reviewed' in (c.page.locator('#productionDetail').inner_text().lower() if c.page.locator('#productionDetail').count() else '')
    c.act('#productionDetail', 'read', note='choice recorded=%s' % recorded)
    return recorded, 'study state shows reviewed=%s' % recorded


@driver('reuse-keeper-as-reference')
def _reuse(c):
    c.boot('#assets')
    c.page.wait_for_timeout(600)
    c.act('#assetGrid', 'read', note='saved pictures listed')
    c.act('[data-asset-open="asset-1"]', note='open the keeper')
    c.act('[data-ux-handoff="asset-1"]', note='continue with this picture')
    c.act('#uxDestination', 'select', typed='qwen-1ref')
    c.act('#uxPrepareHandoff')
    c.page.wait_for_timeout(800)
    lineage = c.page.evaluate('typeof parentAssets !== "undefined" ? parentAssets[0] : null')
    c.act('#uxContinuation', 'read', note='lineage parent=%s' % lineage)
    c.act('#positive', 'fill', typed='Same character at dawn. Keep the face, cloak and lantern unchanged.')
    c.act('#generate', 'read', note='readiness only; never pressed')
    return lineage == 'asset-1', 'lineage parent=%s, run control enabled=%s' % (lineage, c.ready())


@driver('restyle-recent-output-with-a-look')
def _restyle(c):
    """The owner's 14 Sep 2026 report: a liked output, a second picture with the wanted look, no idea which recipe."""
    c.boot('#create')
    c.page.wait_for_timeout(600)
    c.act('#workshopResults > summary', note='open recent runs', supplementary=True)
    c.act('#gallery .reference-output', note='continue with a recent output')
    c.act('#uxHandoffIntents [data-ux-destination="restyle"]', note='the route that borrows a look')
    c.act('#uxHandoffDetails', 'read', note='what Restyle does with this picture')
    try: c.page.click('#uxHandoff details:has(#uxHandoffPrompt) > summary', timeout=2000)
    except Exception: pass
    c.act('#uxHandoffPrompt', 'read', note='the wording prepared for this pass')
    c.act('#uxPrepareHandoff')
    c.page.wait_for_timeout(800)
    board = c.page.evaluate('typeof selected !== "undefined" && !!(selected.continuation_capability && selected.continuation_capability.board_min)')
    if board:
        c.act('#uxBlockers', 'read', note='what is still missing after preparing')
        c.act('#uxPullAsset', note='add the picture whose look is wanted')
        if c.page.locator('#uxSourcePicker[open]').count():
            try: c.page.select_option('#uxSourceSlot', '0', timeout=3000)
            except Exception: pass
            c.act('[data-ux-pull="asset-4"]', note='live mode never pulls: it writes server state' if c.live else 'a saved picture for Picture 1')
            if c.page.locator('#uxSourcePicker[open]').count():
                try: c.page.click('[data-ux-close="uxSourcePicker"]', timeout=2000)
                except Exception: pass
        else: c.act('#referenceCards', 'read', note='the picker did not open; board state as found')
    else:
        c.act('#uxContinuation', 'read', note='the source panel: nothing missing, no board to fill')
        c.act('#positive', 'read', note='the prepared wording: the finish, what to keep, the source description')
    c.page.wait_for_timeout(400)
    c.act('#generate', 'read', note='readiness only; never pressed')
    attached = c.page.evaluate('typeof lastUploaded !== "undefined" && !!lastUploaded' if board else 'typeof uploaded !== "undefined" && !!uploaded')
    filled = c.page.evaluate('typeof referenceRecords !== "undefined" ? referenceRecords.filter(r=>r.file).length : 0') if board else 0
    words = c.page.evaluate('(document.querySelector("#positive").value || "").trim().split(/\\s+/).filter(Boolean).length')
    done = c.ready() and attached and (filled >= 1 if board else words >= 20)
    return done, 'source attached=%s, board recipe=%s, %d board picture(s), %d prepared words, run control enabled=%s' % (attached, board, filled, words, c.ready())


@driver('combine-character-with-another-pose')
def _combine(c):
    """The owner's 14 Sep 2026 attempt: 'the pose of the second image' typed into a one-picture recipe gave the same picture."""
    c.boot('#create')
    c.page.wait_for_timeout(600)
    c.act('#workshopResults > summary', note='open recent runs', supplementary=True)
    c.act('#gallery .reference-output', note='continue with a recent output')
    c.act('#uxHandoffIntents [data-ux-destination="combine"]', note='the route that combines two pictures')
    c.act('#uxHandoffDetails', 'read', note='what Combine does with this picture')
    try: c.page.click('#uxHandoff details:has(#uxHandoffPrompt) > summary', timeout=2000)
    except Exception: pass
    c.act('#uxHandoffPrompt', 'read', note='the wording prepared for this pass: image 1, image 2, the bracketed fills')
    c.act('#uxPrepareHandoff')
    c.page.wait_for_timeout(800)
    c.act('#uxBlockers', 'read', note='what is still missing after preparing: Picture 1 and the fills')
    c.act('#uxPullAsset', note='add the picture whose pose is wanted')
    if c.page.locator('#uxSourcePicker[open]').count():
        try: c.page.select_option('#uxSourceSlot', '0', timeout=3000)
        except Exception: pass
        c.act('[data-ux-pull="asset-1"]', note='live mode never pulls: it writes server state' if c.live else 'a saved picture for Picture 1')
        if c.page.locator('#uxSourcePicker[open]').count():
            try: c.page.click('[data-ux-close="uxSourcePicker"]', timeout=2000)
            except Exception: pass
    else: c.act('#referenceCards', 'read', note='the picker did not open; board state as found')
    c.act('#uxPair', 'read', note='the two pictures side by side, in the order the model reads them')
    wording = c.page.evaluate('(document.querySelector("#positive").value || "")')
    filled_wording = wording
    # Every bracketed fill the leading Combine recipe carries (who, the pose, the clothes and colours), whichever recipe leads.
    answers = (('who is in image', 'the witch in the black and red robe'), ('pose', 'leaning forward, one hand on her hip, the other held out'), ('clothes', 'a black and red robe with gold trim, a wide-brimmed black hat'))
    fields = c.page.evaluate('[...document.querySelectorAll("#uxFills:not([hidden]) [data-ux-fill]")].map(i => i.dataset.uxFill)')
    if fields:
        # Slice A of #422: three short named fields write the wording; the paragraph is read, not edited.
        for index, placeholder in enumerate(fields):
            words = next((words for key, words in answers if key in placeholder), 'the witch')
            c.act('[data-ux-fill="%s"]' % placeholder.replace('"', '\\"'), 'fill', typed=words, note='field %d of %d' % (index + 1, len(fields)))
        c.page.wait_for_timeout(400)
        filled_wording = c.page.evaluate('(document.querySelector("#positive").value || "")')
    else:
        for _ in range(6):
            start = filled_wording.find('['); end = filled_wording.find(']', start)
            if start < 0 or end < start: break
            words = next((words for key, words in answers if key in filled_wording[start:end]), 'the witch')
            filled_wording = filled_wording[:start] + words + filled_wording[end + 1:]
        c.act('#positive', 'fill', typed=filled_wording)
        c.page.wait_for_timeout(400)
    c.act('#generate', 'read', note='readiness only; never pressed')
    attached = c.page.evaluate('typeof lastUploaded !== "undefined" && !!lastUploaded')
    filled = c.page.evaluate('typeof referenceRecords !== "undefined" ? referenceRecords.filter(r=>r.file).length : 0')
    brackets = c.page.evaluate('((document.querySelector("#positive").value || "").match(/\\[/g) || []).length')
    done = c.ready() and attached and filled >= 1 and brackets == 0 and 'image 2' in filled_wording
    return done, 'source attached=%s, %d board picture(s), %d bracket(s) left, run control enabled=%s' % (attached, filled, brackets, c.ready())


@driver('draw-a-pose-for-combine')
def _draw_pose(c):
    """#444: the stick figure the skeleton recipe needs is drawn on the page, and drawing it submits nothing."""
    import studio_browser_smoke as fixture
    c.boot('#create')
    c.page.wait_for_timeout(600)
    c.act('#workshopResults > summary', note='open recent runs', supplementary=True)
    c.act('#gallery .reference-output', note='continue with a recent output')
    c.act('#uxHandoffIntents [data-ux-destination="combine"]', note='the route that combines two pictures')
    c.act('#uxDestination', 'select', typed='combine-klein-9b-skeleton', note='the recipe whose image 1 is a drawn skeleton')
    c.act('#uxPrepareHandoff')
    c.page.wait_for_timeout(800)
    c.act('#uxPoseEditor', 'read', note='the pose is drawn here, beside the two pictures')
    if c.live or not c.page.locator('#uxPoseCanvas').count():
        return False, 'Needs the prepared fixture pair; live mode never renders a guide (it writes a file). '
    c.act('#uxPoseStart', 'select', typed='bent', note='start from the research figure, then correct it')
    c.act('[data-ux-joint="4"]', note='pick one joint for the keyboard')
    before = c.page.evaluate('document.querySelector("#uxPoseCanvas").toDataURL()')
    for key in ('ArrowRight', 'ArrowRight', 'Shift+ArrowUp'): c.page.keyboard.press(key)
    c.page.wait_for_timeout(200)
    nudged = c.page.evaluate('document.querySelector("#uxPoseCanvas").toDataURL()') != before
    c.observe('the arrow keys moved the picked joint', nudged, 'the drawing did not change under the keyboard')
    c.act('#uxPoseUnknown', note='leave one joint, and its limbs, out of the guide')
    posts = len(fixture.POSTS)
    c.act('#uxPoseUse')
    c.page.wait_for_function('!!(typeof referenceRecords !== "undefined" && referenceRecords[0] && referenceRecords[0].file)', timeout=10000)
    state = c.page.evaluate('({preset:selected.id,file:(referenceRecords[0]||{}).file,missing:!!(referenceRecords[0]||{}).missing,'
                            'sha:(referenceRecords[0]||{}).sha256,keep:typeof lastUploaded!=="undefined"?lastUploaded:null})')
    routes = [post['path'] for post in fixture.POSTS[posts:]]
    drawn = bool(state['file']) and not state['missing'] and state['preset'] == 'combine-klein-9b-skeleton'
    c.observe('Picture 1 holds the drawing and nothing was generated', drawn and routes == ['/api/pose/render'],
              'routes after the drawing: %s; board state: %s' % (routes or 'none', state))
    c.act('#generate', 'read', note='readiness only; never pressed')
    return drawn and nudged and routes == ['/api/pose/render'] and bool(state['keep']), \
        'skeleton recipe kept, Picture 1 = %s (sha %s), character kept=%s, routes=%s' % (
            state['file'], str(state['sha'])[:12], bool(state['keep']), routes)


@driver('combine-same-pair-second-engine')
def _combine_loop(c):
    """Real page controls over synthetic completed jobs; recipe switches and reruns never submit."""
    ready, detail = _combine(c)
    if not ready or c.live: return False, 'Needs the prepared fixture pair; live attachment is deliberately skipped. ' + detail
    import studio_browser_smoke as fixture
    initial = c.page.evaluate('({preset_id:selected.id,controls:values(),continuation:continuationState,references:attachedReferencePayload(),parent_assets:parentAssets})')
    preset = next(p for p in fixture.CATALOG['presets'] if p['id'] == initial['preset_id'])
    added = []
    for index, status in enumerate(('completed', 'completed', 'uncertain')):
        job = dict(copy.deepcopy(initial), id='combine-loop-' + str(index), status=status,
                   preset_name=preset['name'], elapsed_seconds=80 + index, batch_count=1,
                   message='Synthetic ' + status + ' receipt; no model ran.',
                   outputs=[dict(filename='fixture.png', asset_id='asset-' + str(index + 2), media_type='image', seed=42 + index)])
        added.append(job)
    unrelated = copy.deepcopy(added[0]); unrelated['id'] = 'combine-other-pair'
    unrelated['references'][0]['sha256'] = 'b' * 64
    fixture.JOBS[:0] = [unrelated] + added
    try:
        c.page.evaluate('refreshJobs()')
        c.page.wait_for_selector('#uxPairResults .ux-result-tile')
        c.act('#uxPairResults', 'read', note='three matching outputs; the changed pose bytes are excluded')
        assert c.page.locator('#uxPairResults .ux-result-tile').count() == 3
        assert c.page.locator('[data-ux-rerun][data-job="combine-loop-2"]:disabled').count() == 2
        assert c.page.locator('#jobProblems').evaluate('(el) => !el.open')
        assert c.page.locator('[data-ux-engine="combine-klein-9b-skeleton"]').is_disabled()
        custom = c.page.locator('#positive').input_value() + ' Keep the red ribbon.'
        c.act('#positive', 'fill', typed=custom, note='a hand edit stays with its recipe')
        before_attach = len([p for p in fixture.POSTS if p['path'] == '/api/assets/reference'])
        c.act('[data-ux-engine="combine-klein"]', note='same-screen second engine; no reattachment or fill entry')
        c.page.wait_for_function('selected.id === "combine-klein"')
        state = c.page.evaluate('({preset:selected.id,claim:continuationState,refs:attachedReferencePayload(),parents:parentAssets,controls:values(),hash:selected.continuation_capability.template_sha256})')
        assert state['claim']['template_sha256'] == state['hash']
        assert state['claim']['reference_file'] == initial['continuation']['reference_file']
        assert state['refs'][0]['file'] == initial['references'][0]['file']
        assert state['parents'] == initial['parent_assets']
        assert 'leaning forward' in state['controls']['positive'] and 'gold trim' in state['controls']['positive']
        assert not c.page.locator('#uxFillsNote').is_visible()
        assert c.ready()
        c.act('#uxPairResults', 'read', note='results stay grouped across the recipe switch')
        assert c.page.locator('#uxPairResults .ux-result-tile').count() == 3
        c.act('[data-ux-engine="%s"]' % initial['preset_id'], note='return to the previous recipe and its exact edited wording')
        assert c.page.locator('#positive').input_value() == custom
        assert len([p for p in fixture.POSTS if p['path'] == '/api/assets/reference']) == before_attach
        c.act('[data-ux-review="selected"][data-asset="asset-2"]', note='record a review through Workspace revisions')
        c.page.wait_for_function('assetState.assets.find(a=>a.id === "asset-2").review === "selected"')
        c.act('[data-ux-review="needs_work"][data-asset="asset-3"]', note='independent review for the other seed')
        c.page.wait_for_function('assetState.assets.find(a=>a.id === "asset-3").review === "needs_work"')
        c.act('[data-ux-rerun="same"][data-job="combine-loop-0"]', note='stage the exact recorded seed, without running it')
        c.page.wait_for_function('getControl("seed").value === "42" && !referencePending')
        assert c.page.locator('#positive').input_value() == initial['controls']['positive']
        c.act('[data-ux-rerun="new"][data-job="combine-loop-0"]', note='stage another seed while retaining the same pair and recipe')
        c.page.wait_for_function('getControl("seed").value !== "42" && !referencePending')
        assert c.page.evaluate('lastUploaded') == initial['controls']['last_reference']
        assert c.page.evaluate('referenceRecords[0].file') == initial['references'][0]['file']
        assert not [p for p in fixture.POSTS if p['path'] == '/api/jobs']
        c.act('#generate', 'read', note='the only generation action still requires a separate explicit click')
        return c.ready(), 'second engine in one click; sources, fills, edited wording and results retained; two reviews saved; same/new seeds prepared; zero generation requests'
    finally:
        fixture.JOBS[:] = [job for job in fixture.JOBS if not job['id'].startswith(('combine-loop-', 'combine-other-pair'))]


@driver('reference-analysis-review-and-apply')
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


@driver('prompt-lab-to-create')
def _prompt_lab(c):
    c.goto('/prompt-lab.html', note='wording workspace')
    try: c.page.wait_for_selector('#profile option', state='attached', timeout=8000)
    except Exception: pass
    options = c.page.eval_on_selector_all('#profile option', 'nodes => nodes.map(n => n.value)')
    c.act('#profile', 'select', typed=options[0] if options else '')
    c.act('#brief', 'fill', typed=BRIEF)
    c.act('#subject', 'fill', typed='elf lanternkeeper, silver-grey hair, patched green cloak')
    c.act('#compile')
    c.act('#studioSendPrompt', navigation=True)
    try: c.page.wait_for_selector('#uxTransfer:not([hidden])', timeout=8000)
    except Exception: pass
    c.act('#uxTransferPreview', 'read', note='transferred text reviewed before applying')
    c.act('#uxApplyPrompt')
    c.page.wait_for_timeout(400)
    applied = c.page.locator('#positive').input_value() if c.page.locator('#positive').count() else ''
    return bool(applied.strip()), 'brief field holds %d characters' % len(applied)


@driver('guided-edit-or-preserve-character')
def _guided(c):
    c.goto('/workflow-studio.html#journeys', note='guided paths')
    try: c.page.wait_for_selector('.wf-goal', timeout=8000)
    except Exception: pass
    c.act('#goalCards', 'read', note='%d paths listed' % c.page.locator('.wf-goal').count())
    card = c.page.locator('.wf-goal').filter(has_text='Edit or preserve a character')
    href = card.locator('a').first.get_attribute('href') if card.count() else None
    c.act('.wf-goal:has-text("Edit or preserve a character") a', navigation=True, note='start the path')
    reached = []
    for _ in range(5):
        try: c.page.wait_for_selector('.studio-guide-panel', timeout=6000)
        except Exception: pass
        stage = c.page.evaluate("new URLSearchParams(location.search).get('stage')")
        reached.append(stage)
        c.act('.studio-guide-panel button:has-text("Next step")', navigation=True, note='stage=%s' % stage)
    final = c.page.evaluate("new URLSearchParams(location.search).get('stage')")
    reached.append(final)
    submitted = submissions(OBSERVED_POSTS)
    c.act('body', 'read', note='stages reached: %s; generation posts: %d' % (','.join(str(x) for x in reached), len(submitted)))
    complete = len([x for x in reached if x]) >= 6 and not submitted
    return complete, 'stages reached=%s, start href=%s, generation posts=%d' % (reached, href, len(submitted))


@driver('build-and-prepare-node-workflow')
def _workflow(c):
    c.goto('/workflow-studio.html#builder', note='workflow builder')
    try: c.page.wait_for_selector('#loadNodes', timeout=8000)
    except Exception: pass
    c.act('#schemaState', 'read', note='catalog state before anything is loaded')
    c.act('#loadNodes')
    try: c.page.wait_for_function("document.querySelector('#nodeCount').textContent.includes('installed')", timeout=8000)
    except Exception: pass
    options = c.page.eval_on_selector_all('#presetChoice option', 'nodes => nodes.map(n => n.value).filter(Boolean)')
    if options:
        try: c.page.select_option('#presetChoice', options[0], timeout=3000)
        except Exception: pass
    c.act('#loadPreset')
    c.page.wait_for_timeout(500)
    c.act('#compileWorkflow')
    c.page.wait_for_timeout(500)
    c.act('#exportGraph', 'read', note='export availability after the check')
    c.act('#saveSharedWorkflow', 'read', note='save to Workspace')
    c.act('#prepareSavedRun', 'read', note='prepare a run from a saved revision')
    runs = submissions(OBSERVED_POSTS)
    c.act('#workflowStatus', 'read', note='%d run requests sent' % len(runs))
    exportable = c.page.locator('#exportGraph').count() and not c.page.locator('#exportGraph').is_disabled()
    return bool(exportable) and not runs, 'export available=%s, run requests=%d' % (bool(exportable), len(runs))


@driver('frames-to-native-export')
def _native_export(c):
    c.boot('#assets')
    c.page.wait_for_timeout(600)
    c.act('#assetGrid', 'read', note='saved pictures listed')
    c.act('#assetType', 'select', typed='image', note='images only')
    c.act('[data-asset-check="asset-0"]', 'check')
    c.act('[data-asset-check="asset-1"]', 'check')
    c.act('#nativeExport')
    c.act('#nativeKind', 'select', typed='atlas')
    c.act('#nativeAssetList input[data-native-duration]', 'fill', typed='120')
    before = c.studies()
    c.act('#prepareNative')
    fresh = c.wait_for_new_study(before)
    status = c.dialog_status('#nativeStatus')
    detail = '%d new study listed%s' % (len(fresh), '; export dialog said: ' + status if status else '')
    c.act('#productionList', 'read', note=detail)
    return bool(fresh), detail


# --------------------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------------------
def repo_path(path):
    """Report a path relative to the repository when it lives there, else absolutely."""
    path = Path(path).resolve()
    try: return str(path.relative_to(ROOT)).replace(os.sep, '/')
    except ValueError: return str(path).replace(os.sep, '/')


def load_cases(path=CASES_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def run_case(spec, page, origin, live, screenshots):
    run = CaseRun(spec, page, origin, live, screenshots)
    passed, detail, failure = False, '', ''
    try: passed, detail = DRIVERS[spec['id']](run)
    except Exception as error: failure = type(error).__name__ + ': ' + str(error).splitlines()[0][:200]
    row = {'id': spec['id'], 'goal': spec['goal'], 'starting_view': spec['starting_view'],
           'success_condition': spec['success_condition'], 'wrong_turn': bool(spec.get('wrong_turn')),
           'steps_intended': len(spec['steps']), 'passed': bool(passed) and not failure,
           'detail': detail, 'failure': failure}
    row.update(case_totals(run.records))
    row['steps'] = run.records
    return row


def table(rows):
    header = ['case', 'int', 'took', 'clk', 'sw', 'dead', 'unexp', 'words', 'result']
    body = [[row['id'][:34], str(row['steps_intended']), str(row['steps_taken']), str(row['clicks']),
             str(row['page_switches']), str(row['dead_ends']), str(row['unexplained_disabled']),
             str(row['instruction_words']), 'PASS' if row['passed'] else 'FAIL'] for row in rows]
    widths = [max(len(header[i]), *(len(line[i]) for line in body)) for i in range(len(header))] if body else [len(h) for h in header]
    out = ['  '.join(header[i].ljust(widths[i]) for i in range(len(header))),
           '  '.join('-' * widths[i] for i in range(len(header)))]
    out += ['  '.join(line[i].ljust(widths[i]) for i in range(len(header))) for line in body]
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', help='Drive a live Studio instead of the fixture. Read-only: navigation and typing only.')
    parser.add_argument('--case', action='append', help='Run only these case ids (repeatable).')
    parser.add_argument('--out', type=Path, default=MATRIX_PATH)
    parser.add_argument('--screenshots', type=Path, default=SHOTS_ROOT)
    parser.add_argument('--chromium', help='Chromium executable path.')
    args = parser.parse_args(argv)

    data = load_cases()
    known = {case['id'] for case in data['cases']}
    # Stays above the playwright import below: the offline lane runs this refusal with no browser installed.
    unknown = [case_id for case_id in (args.case or ()) if case_id not in known]
    if unknown: raise SystemExit('No such use case in research/ux/use-cases.json: ' + ', '.join(unknown))
    cases = [case for case in data['cases'] if not args.case or case['id'] in args.case]
    missing = [case['id'] for case in cases if case['id'] not in DRIVERS]
    if missing: raise SystemExit('No driver registered for: ' + ', '.join(missing))
    args.out = args.out.resolve(); args.screenshots = args.screenshots.resolve()
    args.screenshots.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright
    server = thread = None
    live = bool(args.base_url)
    if live:
        origin = args.base_url.rstrip('/')
        if not re.match(r'^https?://(127\.0\.0\.1|localhost)(:\d+)?$', origin):
            raise SystemExit('Live mode is loopback only: pass http://127.0.0.1:<port>')
        fixture = None
    else:
        Handler, fixture = build_handler()
        server = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('STUDIO_UX_TEST_PORT', '0'))), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)

    rows, errors = [], []
    started = time.time()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'],
                                                 executable_path=args.chromium or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None)
            context = browser.new_context(viewport={'width': 1536, 'height': 1060}, device_scale_factor=1, reduced_motion='reduce')
            for spec in cases:
                page = context.new_page()
                page.set_default_timeout(6000)
                page.on('pageerror', lambda error, case=spec['id']: errors.append(case + ': ' + str(error)[:200]))
                page.on('request', lambda request: OBSERVED_POSTS.append(urlsplit(request.url).path) if request.method == 'POST' else None)
                print('--- ' + spec['id'], flush=True)
                rows.append(run_case(spec, page, origin, live, args.screenshots))
                print(('PASS ' if rows[-1]['passed'] else 'FAIL ') + spec['id'] + ' · ' + (rows[-1]['detail'] or rows[-1]['failure']), flush=True)
                page.close()
            browser.close()
    finally:
        if server: server.shutdown(); server.server_close()
        if thread: thread.join(timeout=5)

    submitted = submissions(OBSERVED_POSTS)
    matrix = {'version': 1, 'refs': data.get('refs'), 'mode': 'live-readonly' if live else 'fixture',
              'origin': origin if live else 'fixture server', 'seconds': round(time.time() - started, 1),
              'cases': len(rows), 'passed': len([row for row in rows if row['passed']]),
              'generation_submissions': len(submitted), 'posts_observed': len(OBSERVED_POSTS), 'page_errors': errors,
              'screenshots': str(args.screenshots.relative_to(ROOT)).replace('\\', '/') if args.screenshots.is_relative_to(ROOT) else str(args.screenshots),
              'rows': rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(matrix, indent=2) + '\n', encoding='utf-8')
    print()
    print(table(rows))
    print()
    print('Top friction (dead ends, then clicks):')
    for row in friction_points(rows)[:5]:
        print('  %-34s dead=%d clicks=%d unexplained=%d words=%d' % (row['id'], row['dead_ends'], row['clicks'], row['unexplained_disabled'], row['instruction_words']))
    print()
    print('mode=%s cases=%d passed=%d generation submissions=%d of %d browser POSTs observed, page errors=%d' % (matrix['mode'], matrix['cases'], matrix['passed'], matrix['generation_submissions'], len(OBSERVED_POSTS), len(errors)))
    print('matrix -> ' + str(args.out))
    reasons = verdict(matrix)
    for reason in reasons: print('FAILED: ' + reason, file=sys.stderr, flush=True)
    return 1 if reasons else 0


if __name__ == '__main__': raise SystemExit(main())

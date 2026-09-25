"""Opt-in Chromium: actual collection dialog/scripts, HTTP and temporary SQLite.

Native same-origin HTTP, sessionStorage and WebCrypto are the default. --inert
explicitly substitutes browser transport, storage, digest and reload with a
Python bridge/test doubles for managed environments; it is not native evidence.
Run: python tests/collection_command_browser.py [--inert]
"""
import copy
import hashlib
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from types import SimpleNamespace
import unittest

INERT = '--inert' in sys.argv
if INERT: sys.argv.remove('--inert')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'app'))
from workspace import AssetWorkspace
from studio_workflow.collection_http import extend_handler
from studio_workflow.core import canonical

HTML = '''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<style>dialog{max-width:calc(100vw - 50px)}input,textarea{display:block;max-width:100%;box-sizing:border-box}</style>
<button id="recoverCollections">Recover</button><button id="newCollection">New collection</button><button id="renameCollection">Edit</button><button id="deleteCollection">Delete</button>
<dialog id="collectionDialog"><h2 id="collectionDialogTitle"></h2><form id="collectionForm">
<select id="collectionRecoveredTargets" aria-label="Local recovery" hidden></select><label>Name<input id="collectionName"></label><label>Description<textarea id="collectionDescription"></textarea></label>
<button id="saveCollection" type="submit">Save</button><button id="removeCollection" type="button">Remove</button>
<button id="showSavedCollection" type="button">Show</button><button id="cancelCollection" type="button">Close</button>
<pre id="collectionComparison" hidden style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>
<button type="button" id="restoreCollectionDraft" hidden>Restore</button>
<button type="button" id="inspectCollectionCommand" hidden>Inspect</button>
<button type="button" id="retryCollectionCommand" hidden>Retry</button>
<button type="button" id="discardCollectionDraft" hidden>Discard</button>
</form><p id="collectionStatus" role="status"></p></dialog><p id="message"></p>
<script>
const $=selector=>document.querySelector(selector);
let assetState=INITIAL,collectionEditing=null,assetScope='all';
const assetSelection=new Set(['retained-selection']);
function assetMessage(text){$('#message').textContent=text;}
function setAssetScope(value){assetScope=value;}
async function api(path,options){const response=await fetch(path,options);const value=await response.json();
if(!response.ok){const e=Error(value.error);e.status=response.status;e.data=value;throw e;}return value;}
async function refreshAssets(){assetState=await api('/api/assets');}
window.confirm=()=>true;
</script><script src="/collection-recovery.js"></script><script src="/collection-editor.js"></script>'''


class CollectionEditorProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(executable_path=shutil.which('chromium') or None,
                                                        headless=True, args=['--no-sandbox'])
        except Exception:
            cls.playwright.stop(); raise
        print('Chromium:', cls.browser.version, 'mode:', 'INERT (substituted origin/storage/transport/digest)' if INERT else 'native HTTP/storage/WebCrypto')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = AssetWorkspace(self.temp.name)
        self.studio = studio = SimpleNamespace(assets=self.workspace)
        self.flags = flags = {'lose': False, 'mismatch': False, 'delay': None}
        self.arrived = threading.Event()
        arrived = self.arrived
        self.writes = writes = []
        self.bodies = bodies = []
        class Base(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers.get('Host', '')
            def _content_length(self, cap):
                size = int(self.headers['Content-Length'])
                if not 0 <= size <= cap: raise ValueError('Body too large')
                return size
            def _bytes(self, raw, content_type, status=200):
                self.send_response(status); self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def _json(self, status, value):
                if self.path == '/api/collections':
                    writes.append(copy.deepcopy(value)); arrived.set()
                    if flags['delay'] is not None: flags['delay'].wait(5)
                    if status == 200 and flags['lose']:
                        flags['lose'] = False; self.close_connection = True; self.connection.shutdown(socket.SHUT_RDWR); return
                    if status == 200 and flags['mismatch']:
                        value = {**value, 'request_id': 'different-request'}
                return self._bytes(canonical(value), 'application/json', status)
            def do_GET(self):
                if self.path == '/': return self._bytes(HTML.replace('INITIAL', json.dumps(studio.assets.snapshot())).encode(), 'text/html')
                if self.path == '/collection-recovery.js': return self._bytes((ROOT / 'app/static/collection-recovery.js').read_bytes(), 'text/javascript')
                if self.path == '/collection-editor.js': return self._bytes((ROOT / 'app/static/collection-editor.js').read_bytes(), 'text/javascript')
                if self.path == '/api/assets': return self._json(200, studio.assets.snapshot())
                return self._json(404, {'error': 'Unknown fixture path'})
            def do_POST(self): return self._json(404, {'error': 'Unclaimed write'})
        class Handler(extend_handler(Base)):
            def do_POST(self):
                if self.path == '/api/collections':
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    bodies.append(raw); self.rfile = io.BytesIO(raw)
                return super().do_POST()
        handler = Handler; handler.studio = studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start(); self.addCleanup(self.close_server)
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page(); self.page.set_default_timeout(5000); self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.load_page(self.page)

    def load_page(self, page, retained=None):
        if not INERT:
            # Cold-runner first load gets its own budget (#911); interactions keep 5 s.
            page.goto(self.origin, timeout=20000)
            page.wait_for_function('typeof openCollection === "function"', timeout=20000)
            return
        # Explicit inert fixture; do not mistake this for browser origin/storage proof.
        def bridge(path, options=None):
            options = options or {}
            headers = {'Origin': self.origin, **options.get('headers', {})}
            data = options.get('body')
            request = Request(self.origin + path, data=data.encode() if data is not None else None, headers=headers)
            try:
                with urlopen(request, timeout=10) as response: return {'status': response.status, 'value': json.load(response)}
            except HTTPError as error: return {'status': error.code, 'value': json.loads(error.read())}
        if not getattr(page, '_las_bridge', False):
            page.expose_function('fixtureAPI', bridge)
            page.expose_function('fixtureDigest', lambda data: list(hashlib.sha256(bytes(data)).digest()))
            page._las_bridge = True
        # set_content does not replace the JS realm; a fresh inert document does.
        page.goto('about:blank')
        html = HTML.replace('INITIAL', json.dumps(self.studio.assets.snapshot()))
        for script in ['collection-recovery', 'collection-editor']:
            html = html.replace('<script src="/'+script+'.js"></script>', '')
        page.set_content(html)
        page.evaluate("""entries => {
          const data=new Map(entries);
          Object.defineProperty(window,'sessionStorage',{configurable:true,value:{
            get length(){return data.size;},key:i=>[...data.keys()][i]??null,
            getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k)}});
          Object.defineProperty(crypto,'subtle',{configurable:true,value:{
            digest:async(_,raw)=>new Uint8Array(await fixtureDigest([...new Uint8Array(raw)])).buffer}});
          api=async(path,options)=>{const reply=await fixtureAPI(path,options);
            if(reply.status>=400){const e=Error(reply.value.error);e.status=reply.status;e.data=reply.value;throw e;}return reply.value;};
        }""", retained or [])
        page.evaluate("values=>{let i=0;crypto.randomUUID=()=>values[i++];}", [str(uuid.uuid4()) for _ in range(40)])
        for script in ['collection-recovery', 'collection-editor']:
            page.add_script_tag(content=(ROOT / ('app/static/'+script+'.js')).read_text())

    def reload_page(self, page=None):
        page = page or self.page
        if INERT:
            retained = page.evaluate('Array.from({length:sessionStorage.length},(_,i)=>{const k=sessionStorage.key(i);return [k,sessionStorage.getItem(k)];})')
            self.load_page(page, retained)
        else:
            page.reload(); page.wait_for_function('typeof openCollection === "function"')

    def restore(self, page=None):
        page = page or self.page
        page.click('#recoverCollections'); page.click('#restoreCollectionDraft')

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def close_server(self):
        if self.flags['delay'] is not None: self.flags['delay'].set()
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)

    def save(self, name):
        self.page.fill('#collectionName', name)
        self.page.click('#saveCollection')
        self.page.wait_for_function('!collectionSession?.busy')

    def create(self):
        self.page.click('#newCollection'); self.save('Created')
        rows = self.workspace.snapshot()['collections']
        self.assertEqual(len(rows), 1, self.page.locator('#collectionStatus').inner_text())
        self.assertFalse(self.page.evaluate('collectionSession.uncertain'))
        self.assertEqual(self.page.evaluate('collectionSession.revision'), 1)
        return rows[0]['id']

    def test_keyboard_create_rename_delete_uses_monotonic_revisions(self):
        key = self.create()
        self.page.fill('#collectionDescription', 'New description')
        self.page.focus('#collectionName'); self.page.keyboard.press('Enter')
        self.page.wait_for_function('!collectionSession.busy')
        self.assertEqual(self.workspace.snapshot()['collections'][0]['revision'], 2)
        self.assertEqual(self.page.evaluate('collectionSession.revision'), 2)
        self.page.click('#removeCollection')
        self.page.wait_for_function('!document.querySelector("#collectionDialog").open')
        self.assertEqual(self.workspace.snapshot()['collections'], [])
        self.assertEqual([value['receipt']['result']['revision'] for value in self.writes], [1, 2, 3])
        self.assertEqual(len({value['request_id'] for value in self.writes}), 3)
        self.assertEqual(self.page.evaluate('[...assetSelection]'), ['retained-selection'])
        self.assertEqual(self.errors, [])

    def test_concurrent_rename_refuses_without_discarding_the_local_draft(self):
        key = self.create()
        self.workspace.collection({'id': key, 'action': 'rename', 'name': 'Another editor', 'description': 'Current'})
        self.save('My retained draft')
        self.assertEqual(self.page.input_value('#collectionName'), 'My retained draft')
        self.assertFalse(self.page.evaluate('collectionSession.uncertain'))
        self.assertEqual(self.workspace.snapshot()['collections'][0]['name'], 'Another editor')
        self.assertEqual(self.writes[-1]['code'], 'collection_revision_conflict')
        self.assertEqual(self.page.evaluate('collectionSession.revision'), 1)

    def test_missing_revision_never_downgrades_to_legacy(self):
        self.create(); before = len(self.writes)
        self.page.evaluate('collectionSession.revision=undefined')
        self.page.fill('#collectionName', 'Retain me'); self.page.evaluate("saveCollectionChange('save')")
        self.assertEqual(len(self.writes), before)
        self.assertEqual(self.page.input_value('#collectionName'), 'Retain me')
        self.assertRegex(self.page.locator('#collectionStatus').inner_text().lower(), 'revision|recovery')

    def test_lost_response_blocks_repeat_but_retains_the_committed_receipt(self):
        self.flags['lose'] = True
        self.page.click('#newCollection'); self.save('Response lost')
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)
        self.assertTrue(self.page.evaluate('collectionSession.uncertain'))
        self.assertTrue(self.page.is_disabled('#saveCollection'))
        self.page.evaluate("saveCollectionChange('save')")
        self.assertEqual(len(self.writes), 1)
        original = self.writes[0]
        status = self.workspace.collection_status(original['request_id'], original['workspace_id'])
        self.assertEqual(status['receipt_json'], original['receipt_json'])
        self.assertEqual(self.page.input_value('#collectionName'), 'Response lost')

    def test_newer_typing_survives_the_earlier_successful_snapshot(self):
        self.page.click('#newCollection')
        self.page.evaluate("""()=>{const send=api;api=async(...args)=>{const response=await send(...args);await new Promise(resolve=>window.releaseReply=resolve);return response;};}""")
        self.page.fill('#collectionName', 'Clicked snapshot'); self.page.click('#saveCollection')
        self.page.wait_for_function('typeof releaseReply==="function"')
        self.page.fill('#collectionName', 'Newer typing'); self.page.evaluate('releaseReply()')
        self.page.wait_for_function('!collectionSession.busy')
        self.assertEqual(self.workspace.snapshot()['collections'][0]['name'], 'Clicked snapshot')
        self.assertEqual(self.page.input_value('#collectionName'), 'Newer typing')
        self.assertEqual(self.page.evaluate('collectionSession.baseline.name'), 'Clicked snapshot')
        self.assertEqual(self.page.evaluate('collectionSession.revision'), 1)
        self.assertFalse(self.page.is_disabled('#saveCollection'))

    def test_mismatched_response_is_not_adopted_as_saved_state(self):
        self.flags['mismatch'] = True
        self.page.click('#newCollection'); self.save('Unconfirmed')
        self.assertTrue(self.page.evaluate('collectionSession.uncertain'))
        self.assertIsNone(self.page.evaluate('collectionSession.id'))
        self.assertEqual(self.page.evaluate('collectionSession.baseline.name'), '')
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)

    def test_reload_unsaved_draft_is_explicit_and_zero_writes(self):
        self.page.click('#newCollection'); self.page.fill('#collectionName', 'Unsent <draft>')
        self.reload_page(); self.restore()
        self.assertEqual(self.page.input_value('#collectionName'), 'Unsent <draft>')
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'collectionName')
        self.assertEqual(self.bodies, [])
        self.assertEqual(self.workspace.snapshot()['collections'], [])
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))

    def test_lost_committed_response_reload_status_resolves_once(self):
        self.flags['lose'] = True
        self.page.click('#newCollection'); self.save('Lost create')
        original = self.bodies[0]
        self.reload_page(); self.restore()
        self.page.click('#inspectCollectionCommand'); self.page.wait_for_function('!collectionSession.busy')
        self.assertIsNone(self.page.evaluate('collectionSession.pending'))
        self.assertEqual(self.bodies, [original])
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)
        self.assertEqual(self.page.input_value('#collectionName'), 'Lost create')

    def test_unknown_reload_retry_uses_identical_bytes(self):
        self.page.click('#newCollection')
        self.page.evaluate("()=>{api=async()=>{throw Error('Fixture: dispatch outcome unavailable before server receives it')}}")
        self.save('Unknown create')
        body = self.page.evaluate('collectionSession.pending.body')
        self.assertEqual(self.bodies, [])
        self.reload_page(); self.restore()
        self.page.click('#inspectCollectionCommand'); self.page.wait_for_function('!collectionSession.busy')
        self.assertIsNotNone(self.page.evaluate('collectionSession.pending'))
        self.page.click('#retryCollectionCommand'); self.page.wait_for_function('!collectionSession.busy')
        self.assertEqual(self.bodies, [body.encode()])
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)
        self.assertIsNone(self.page.evaluate('collectionSession.pending'))

    def test_two_tabs_keep_their_drafts_and_stale_cas_cannot_overwrite(self):
        key = self.create()
        other = self.context.new_page(); other.set_default_timeout(5000)
        self.addCleanup(other.close); self.load_page(other)
        other.evaluate('id=>openCollection(id)', key)
        other.fill('#collectionName', 'Second tab draft')
        self.save('First tab won')
        other.click('#saveCollection'); other.wait_for_function('!collectionSession.busy')
        self.assertEqual(self.workspace.snapshot()['collections'][0]['name'], 'First tab won')
        self.assertEqual(other.input_value('#collectionName'), 'Second tab draft')
        self.assertTrue(other.is_disabled('#saveCollection'))
        self.assertIn('First tab won', other.inner_text('#collectionComparison'))
        self.reload_page(other); self.restore(other)
        self.assertEqual(other.input_value('#collectionName'), 'Second tab draft')
        self.assertEqual(self.page.input_value('#collectionName'), 'First tab won')

    def test_discard_then_close_then_reload_does_not_restore_discarded_text(self):
        self.page.click('#newCollection'); self.page.fill('#collectionName', 'Discard locally')
        self.page.click('#discardCollectionDraft'); self.page.click('#cancelCollection')
        self.reload_page(); self.page.click('#newCollection')
        self.assertTrue(self.page.is_hidden('#restoreCollectionDraft'))
        self.assertEqual(self.bodies, [])

    def test_foreign_workspace_cannot_adopt_an_old_pending_envelope(self):
        self.flags['lose'] = True
        self.page.click('#newCollection'); self.save('Retain old identity')
        old = self.studio.assets
        self.studio.assets = AssetWorkspace(Path(self.temp.name) / 'replacement')
        self.reload_page(); self.page.click('#newCollection')
        self.assertTrue(self.page.is_hidden('#restoreCollectionDraft'))
        self.assertEqual(self.studio.assets.snapshot()['collections'], [])
        self.studio.assets = AssetWorkspace(self.temp.name)  # reopen persisted original store
        self.reload_page(); self.restore()
        self.page.click('#inspectCollectionCommand'); self.page.wait_for_function('!collectionSession.busy')
        self.assertIsNone(self.page.evaluate('collectionSession.pending'))
        self.assertEqual(len(self.bodies), 1)
        self.assertEqual(len(old.snapshot()['collections']), 1)

    def test_disabled_storage_refuses_dispatch_and_keeps_visible_text(self):
        self.page.click('#newCollection')
        self.page.evaluate("Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem(){throw Error('fixture storage unavailable')}}});collectionSession.journal.storage=sessionStorage")
        self.page.fill('#collectionName', 'Copy this text')
        self.page.evaluate("saveCollectionChange('save')")
        self.assertEqual(self.page.input_value('#collectionName'), 'Copy this text')
        self.assertEqual(self.bodies, [])
        self.assertTrue(self.page.is_disabled('#saveCollection'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

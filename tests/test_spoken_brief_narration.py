"""Real loopback HTTP and coordinator tests with fictional text and synthetic PCM."""
import http.client
import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import socket
import threading
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from spoken_brief_fixture import Fixture
from studio_spoken.http import extend_handler


class NarrationFixture(Fixture):
    def __init__(self, root):
        self.root = root
        self.lose_create = False; self.lose_start = 0; self.traffic = []
        super().__init__()

    def handler(self, base=None, extension=extend_handler):
        fixture = self; producer = super().handler()
        class Routes(base or producer):
            def do_GET(self):
                if self.path == '/api/identity' or self.path.startswith('/api/production/'):
                    return producer.do_GET(self)
                return super().do_GET()
            def do_POST(self):
                if self.path == '/api/voice-baseline' or self.path.startswith('/api/production/'):
                    return producer.do_POST(self)
                return super().do_POST()
        class Handler(extension(Routes)):
            studio = SimpleNamespace(root=ROOT, config={'spoken_briefs': {'archive_root': str(fixture.root)}})
            def do_GET(self): fixture.traffic.append(('GET', self.path)); return super().do_GET()
            def do_POST(self): fixture.traffic.append(('POST', self.path)); return super().do_POST()
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers['Host']
            def _json(self, status, value):
                starts = sum(method == 'POST' and path.endswith('/start') for method, path, _, _ in fixture.requests)
                if (self.path == '/api/voice-baseline' and fixture.lose_create) or (
                        self.path.endswith('/start') and self.path.startswith('/api/production/') and starts == fixture.lose_start):
                    self.close_connection = True; self.connection.shutdown(socket.SHUT_RDWR); return
                return super()._json(status, value)
        return Handler

    def close(self):
        manager = getattr(self.server, 'spoken_narrations', None)
        if manager:
            for thread in list(manager.threads.values()): thread.join(5)
        super().close()

    def request(self, route, query=None, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        path = '/api/spoken-briefs' + route + ('?' + urlencode(query) if query else '')
        try:
            connection.request('GET' if body is None else 'POST', path,
                body=None if body is None else json.dumps(body),
                headers={'Origin': self.base_url, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally: connection.close()

    @contextmanager
    def change_during_capture(self, key, change, *, filename='state.json', every_read=False, phase='opening'):
        """Schedule a real file change at a deterministic snapshot boundary."""
        import studio_spoken.narration as narration
        path = self.root / key / filename
        checked, lstat = narration.checked_json, Path.lstat
        reads = []; current = {'thread': None, 'stats': 0, 'changing': False}
        def capture(target):
            if target != path: return checked(target)
            reads.append(target); current.update(thread=threading.get_ident(), stats=0)
            try: return checked(target)
            finally: current['thread'] = None
        def before_open(target, *args, **kwargs):
            before = lstat(target, *args, **kwargs)
            if target == path and current['thread'] == threading.get_ident() and not current['changing']:
                current['stats'] += 1
                if current['stats'] == (2 if phase == 'opening' else 3) and (len(reads) == 1 or every_read):
                    current['changing'] = True
                    try: change(target)
                    finally: current['changing'] = False
            return before
        with patch.object(narration, 'checked_json', capture), patch.object(Path, 'lstat', before_open):
            yield reads


class NarrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'COMPRESSED.md'
        self.source.write_text('# Lantern\n\nKeep the lantern blue.', encoding='utf-8')
        self.f = NarrationFixture(self.root); self.addCleanup(self.f.close)
        self.root_id = self.f.request('/capabilities')[1]['source_root_id']

    def preview(self):
        code, value = self.f.request('/source-preview', {'key': '.', 'root_id': self.root_id})
        self.assertEqual(code, 200, value)
        return value

    def start(self, preview=None):
        value = preview or self.preview()
        return self.f.request('/narration/start', body={
            'key': '.', 'root_id': self.root_id, 'manifest_sha256': value['manifest']['manifest_sha256'],
            'preview_sha256': value['preview_sha256']})

    def settled(self, key):
        for thread in list(self.f.server.spoken_narrations.threads.values()):
            thread.join(5); self.assertFalse(thread.is_alive(), 'Coordinator did not finish its bounded fixture')
        code, value = self.f.request('/narration', {'key': key, 'root_id': self.root_id})
        self.assertEqual(code, 200, value)
        return value

    def posts(self): return [(path, body) for method, path, _, body in self.f.requests if method == 'POST']

    def recover(self, value):
        code, result = self.f.request('/narration/recover', body={
            'key': value['key'], 'root_id': self.root_id, 'manifest_sha256': value['manifest_sha256']})
        self.assertEqual(code, 202, result)
        return self.settled(value['key'])

    def held_create(self):
        entered, release = threading.Event(), threading.Event()
        def hold(project):
            entered.set()
            if not release.wait(5): raise AssertionError('Test did not release its synthetic create response')
        self.f.after_create = hold; self.addCleanup(release.set)
        code, value = self.start()
        self.assertEqual(code, 202, value); self.assertTrue(entered.wait(3))
        return value, release

    def inspect_during_change(self, value, change, *, filename='state.json', every_read=False, phase='opening'):
        """Change a real file after its baseline stat or after its handle was read."""
        with self.f.change_during_capture(value['key'], change, filename=filename,
                every_read=every_read, phase=phase) as reads:
            result = self.f.request('/narration', {'key': value['key'], 'root_id': self.root_id})
        return result, len(reads)

    def test_live_coordinator_state_replacement_gets_one_fresh_observation(self):
        starting, release_start = threading.Event(), threading.Event(); self.addCleanup(release_start.set)
        def hold_start(project):
            starting.set()
            if not release_start.wait(5): raise AssertionError('Test did not release its synthetic Start response')
        self.f.after_start = hold_start
        value, release_create = self.held_create()
        def advance(path):
            release_create.set(); self.assertTrue(starting.wait(3))
        try:
            (code, observed), reads = self.inspect_during_change(value, advance)
            self.assertEqual(code, 200, observed)
            self.assertTrue(observed['active']); self.assertEqual(reads, 2)
        finally: release_start.set()
        self.assertEqual(self.settled(value['key'])['status'], 'completed')
        self.assertEqual([path for path, _ in self.posts()], ['/api/voice-baseline',
            '/api/production/00000000000000000000000000000001/start'])

    def test_coordinator_finishing_during_capture_still_gets_one_fresh_observation(self):
        self.check_finished_coordinator_replacement('opening')

    def test_state_replaced_after_handle_read_gets_one_fresh_observation(self):
        self.check_finished_coordinator_replacement('reading')

    def check_finished_coordinator_replacement(self, phase):
        value, release = self.held_create()
        manager = self.f.server.spoken_narrations
        thread = manager.threads[(self.root_id, value['key'])]
        def complete(path):
            release.set(); thread.join(5)
            self.assertFalse(thread.is_alive()); self.assertFalse(manager.threads)
        (code, observed), reads = self.inspect_during_change(value, complete, phase=phase)
        self.assertEqual(code, 200, observed)
        self.assertEqual(observed['status'], 'completed'); self.assertFalse(observed['active'])
        self.assertEqual(reads, 2)
        self.assertEqual([path for path, _ in self.posts()], ['/api/voice-baseline',
            '/api/production/00000000000000000000000000000001/start'])

    def test_persistent_state_replacement_exhausts_the_single_fresh_observation(self):
        from spoken_brief_transport import write_bytes
        value, release = self.held_create(); before = self.posts()
        def replace(path): write_bytes(path, path.read_bytes())
        (code, error), reads = self.inspect_during_change(value, replace, every_read=True)
        self.assertEqual(code, 400, error); self.assertEqual(reads, 2)
        self.assertIn('File changed while opening', error['error'])
        self.assertEqual(self.posts(), before)
        release.set(); self.assertEqual(self.settled(value['key'])['status'], 'completed')
        self.assertEqual(len(self.posts()), 2)

    def test_fresh_observation_rechecks_root_record_manifest_and_state(self):
        from spoken_brief_transport import write_bytes, write_json
        value, release = self.held_create(); before = self.posts()
        directory = self.root / value['key']; config = self.f.server.RequestHandlerClass.studio.config
        original_config = config['spoken_briefs']; other = self.root / 'different-root'; other.mkdir()
        originals = {name: (directory / name).read_bytes() for name in ('state.json', 'manifest.json', 'studio-start.json')}
        for kind, status, message in [('root', 409, 'Source root changed'),
                ('record', 409, 'Retained narration identity differs'),
                ('manifest', 409, 'Retained narration identity differs'),
                ('state', 409, 'manifest'), ('malformed', 400, 'JSON')]:
            with self.subTest(kind=kind):
                def change(path):
                    if kind not in ('state', 'malformed'): write_bytes(path, originals['state.json'])
                    if kind == 'root': config['spoken_briefs'] = {'archive_root': str(other)}
                    elif kind == 'record':
                        record = json.loads(originals['studio-start.json']); record['root_id'] = '0' * 64
                        write_json(directory / 'studio-start.json', record)
                    elif kind == 'manifest':
                        manifest = json.loads(originals['manifest.json']); manifest['manifest_sha256'] = '0' * 64
                        write_json(directory / 'manifest.json', manifest)
                    elif kind == 'state':
                        state = json.loads(originals['state.json']); state['manifest_sha256'] = '0' * 64
                        write_json(path, state)
                    else: write_bytes(path, b'{ invalid JSON')
                try:
                    (code, error), reads = self.inspect_during_change(value, change)
                    self.assertEqual(code, status, error); self.assertIn(message, error['error'])
                    self.assertEqual(reads, 1 if kind == 'root' else 2)
                    self.assertEqual(self.posts(), before); self.assertFalse(list(other.iterdir()))
                finally:
                    config['spoken_briefs'] = original_config
                    for name, raw in originals.items(): write_bytes(directory / name, raw)
        release.set(); self.assertEqual(self.settled(value['key'])['status'], 'completed')
        self.assertEqual(len(self.posts()), 2)

    def test_other_file_and_in_place_changes_are_not_retried(self):
        from spoken_brief_transport import write_bytes
        value, release = self.held_create(); before = self.posts()
        for name in ('manifest.json', 'studio-start.json', 'state.json'):
            with self.subTest(filename=name):
                original = (self.root / value['key'] / name).read_bytes()
                def change(path):
                    if name == 'state.json':
                        # Same inode, changed size: not the coordinator's atomic writer.
                        with path.open('ab') as stream: stream.write(b' ')
                    else: write_bytes(path, original)
                try:
                    (code, error), reads = self.inspect_during_change(value, change, filename=name)
                    self.assertEqual(code, 400, error); self.assertEqual(reads, 1)
                    self.assertIn('File changed while opening', error['error'])
                    self.assertEqual(self.posts(), before)
                finally: write_bytes(self.root / value['key'] / name, original)
        release.set(); self.assertEqual(self.settled(value['key'])['status'], 'completed')
        self.assertEqual(len(self.posts()), 2)

    def test_state_replacement_without_an_owned_live_coordinator_is_not_retried(self):
        from spoken_brief_transport import write_bytes
        value = self.settled(self.start()[1]['key']); before = self.posts()
        self.assertFalse(self.f.server.spoken_narrations.threads)
        (code, error), reads = self.inspect_during_change(value, lambda path: write_bytes(path, path.read_bytes()))
        self.assertEqual(code, 400, error); self.assertEqual(reads, 1)
        self.assertIn('File changed while opening', error['error']); self.assertEqual(self.posts(), before)

    def test_state_replacement_does_not_retry_a_parent_reparse_refusal(self):
        from spoken_brief_transport import write_bytes
        value, release = self.held_create(); before = self.posts()
        directory = self.root / value['key']; original = Path.lstat; linked = {'value': False}
        def reparse(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == directory and linked['value']:
                return SimpleNamespace(st_mode=info.st_mode, st_dev=info.st_dev, st_ino=info.st_ino, st_file_attributes=0x400)
            return info
        def change(path):
            write_bytes(path, path.read_bytes()); linked['value'] = True
        with patch.object(Path, 'lstat', reparse):
            (code, error), reads = self.inspect_during_change(value, change)
        self.assertEqual(code, 400, error); self.assertEqual(reads, 1)
        self.assertIn('Symlink/reparse point refused', error['error']); self.assertEqual(self.posts(), before)
        release.set(); self.assertEqual(self.settled(value['key'])['status'], 'completed')
        self.assertEqual(len(self.posts()), 2)

    def test_explicit_start_accepts_exact_preview_without_preview_inference(self):
        value = self.preview()
        self.assertFalse(self.f.requests)
        self.assertFalse((self.root / '_spoken').exists())
        code, result = self.start(value)
        self.assertEqual(code, 202, result)
        self.assertEqual(result['manifest_sha256'], value['manifest']['manifest_sha256'])
        result = self.settled(result['key'])
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(len(self.posts()), 2)
        self.assertEqual([b['project_id'] for b in result['state']['batches']], list(self.f.projects))
        archive = self.f.request('/archive', {'key': result['key']})[1]
        self.assertEqual(archive['archive_sha256'], result['archive_sha256'])
        connection = http.client.HTTPConnection('127.0.0.1', self.f.server.server_port)
        query = urlencode({'key': result['key'], 'archive_sha256': result['archive_sha256'], 'target': 'master', 'download': '1'})
        connection.request('GET', '/api/spoken-briefs/audio?' + query)
        response = connection.getresponse(); raw = response.read(); connection.close()
        self.assertEqual(response.status, 200); self.assertEqual(raw[:4], b'RIFF')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), archive['archive']['master']['sha256'])
        before = self.posts(); self.assertTrue(self.start(value)[1]['reused']); self.assertEqual(self.posts(), before)

    def test_stale_source_profile_and_producer_refuse_before_files_or_requests(self):
        import voice_profile
        preview = self.preview(); original = self.source.read_bytes()
        self.source.write_bytes(b'Changed source.'); self.assertEqual(self.start(preview)[0], 409)
        self.source.write_bytes(original)
        resolve = voice_profile.resolve_profile
        def changed(*args, **kwargs):
            value = resolve(*args, **kwargs); value['name'] = 'Changed profile'; return value
        with patch.object(voice_profile, 'resolve_profile', side_effect=changed):
            self.assertEqual(self.start(preview)[0], 409)
        self.f.server.RequestHandlerClass.studio.config['ffmpeg'] = 'changed'
        self.assertEqual(self.start(preview)[0], 409)
        self.assertFalse(self.posts()); self.assertFalse((self.root / '_spoken').exists())

    def test_concurrent_duplicate_start_has_one_create_and_one_start(self):
        preview = self.preview()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.start(preview), range(4)))
        self.assertEqual([x[0] for x in results], [202] * 4, results)
        self.assertEqual(len({x[1]['key'] for x in results}), 1)
        self.assertEqual(self.settled(results[0][1]['key'])['status'], 'completed')
        self.assertEqual(len(self.posts()), 2)

    def test_start_and_coordinator_preserve_prepared_manifest_identity(self):
        from spoken_brief_runtime import plan
        manifest = Path(plan(self.source)['manifest'])
        before = manifest.stat()
        code, value = self.start()
        self.assertEqual(code, 202, value)
        self.assertEqual(self.settled(value['key'])['status'], 'completed')
        after = manifest.stat()
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns))
        self.assertEqual(len(self.posts()), 2)

    def test_duplicate_admission_does_not_read_changing_progress(self):
        import studio_spoken.narration as narration
        from spoken_brief_compile import SpokenBriefError
        value = self.settled(self.start()[1]['key']); before = self.posts()
        checked = narration.checked_json
        def changing_progress(path):
            if path.name == 'state.json': raise SpokenBriefError('File changed while reading: state.json')
            return checked(path)
        with patch.object(narration, 'checked_json', side_effect=changing_progress):
            code, result = self.start()
            self.assertEqual(code, 202, result); self.assertTrue(result['reused'])
            code, result = self.f.request('/narration', {'key': value['key'], 'root_id': self.root_id})
            self.assertEqual(code, 400, result)
            self.assertIn('File changed while reading', result['error'])
        self.assertEqual(self.posts(), before)

    def test_lost_create_reply_never_creates_replacement_on_reload_or_recovery(self):
        from studio_spoken.narration import Narrations
        self.f.lose_create = True; preview = self.preview()
        value = self.settled(self.start(preview)[1]['key'])
        self.assertEqual(value['status'], 'uncertain'); self.assertEqual(len(self.posts()), 1)
        self.assertIsNone(value['state']['batches'][0]['project_id'])
        self.f.server.spoken_narrations = Narrations(lambda: self.f.server.RequestHandlerClass.studio.config, self.f.base_url)
        self.assertEqual(self.settled(value['key'])['status'], 'uncertain')
        self.assertTrue(self.start(preview)[1]['reused'])
        self.assertEqual(self.recover(value)['status'], 'uncertain'); self.assertEqual(len(self.posts()), 1)

    def test_lost_start_reply_can_observe_completed_child_without_posting_again(self):
        self.f.lose_start = 1
        value = self.settled(self.start()[1]['key'])
        self.assertEqual(value['status'], 'uncertain'); before = self.posts()
        self.assertEqual(self.recover(value)['status'], 'completed'); self.assertEqual(self.posts(), before)

    def test_lost_start_reply_and_planned_observation_never_authorize_replay(self):
        self.f.lose_start = 1
        self.f.after_start = lambda project: project['state'].update(status='planned')
        value = self.settled(self.start()[1]['key']); before = self.posts()
        self.assertEqual(value['status'], 'uncertain')
        self.assertEqual(self.recover(value)['status'], 'uncertain'); self.assertEqual(self.posts(), before)

    def test_start_attempt_is_durable_before_the_child_receives_post(self):
        preview = self.preview(); observed = []
        def started(project):
            state = json.loads((self.root / preview['run_key'] / 'state.json').read_text())
            observed.append((state['batches'][0]['project_id'], state['batches'][0]['status']))
        self.f.after_start = started
        result = self.settled(self.start(preview)[1]['key'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(observed, [(next(iter(self.f.projects)), 'starting')])

    def test_restart_after_partial_completion_retains_segments_and_assembles_by_get_only(self):
        from studio_spoken.narration import Narrations
        self.source.write_text('\n\n'.join(f'Fictional section {i} stays in source order.' for i in range(9)), encoding='utf-8')
        self.f.lose_start = 2
        value = self.settled(self.start()[1]['key'])
        self.assertEqual(value['state']['batches'][0]['status'], 'completed')
        self.assertEqual(value['status'], 'uncertain'); before = self.posts()
        files = {p: p.read_bytes() for p in (self.root / value['key'] / 'segments').glob('*.wav')}
        self.assertTrue(files)
        self.f.server.spoken_narrations = Narrations(lambda: self.f.server.RequestHandlerClass.studio.config, self.f.base_url)
        result = self.recover(value)
        self.assertEqual(result['status'], 'completed', result); self.assertEqual(self.posts(), before)
        self.assertEqual(files, {p: p.read_bytes() for p in files})

    def test_changed_source_after_create_keeps_acknowledged_child_and_blocks_start(self):
        self.f.after_create = lambda project: self.source.write_bytes(b'Changed after Create.')
        value = self.settled(self.start()[1]['key'])
        self.assertEqual(value['status'], 'blocked', value)
        self.assertEqual(value['state']['batches'][0]['project_id'], next(iter(self.f.projects)))
        self.assertEqual(len(self.posts()), 1)
        before = {p: p.read_bytes() for p in (self.root / value['key']).rglob('*') if p.is_file()}
        self.recover(value)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(before[self.root / value['key'] / 'manifest.json'], (self.root / value['key'] / 'manifest.json').read_bytes())

    def test_escape_and_linked_output_directory_refuse_without_writes(self):
        self.assertEqual(self.f.request('/source-preview', {'key': '../escape', 'root_id': self.root_id})[0], 400)
        preview = self.preview()
        outside = self.root / 'outside'; outside.mkdir()
        link = self.root / '_spoken'
        try: os.symlink(outside, link, target_is_directory=True)
        except OSError as exc: self.skipTest(f'Creating a real directory symlink is unavailable: {exc}')
        self.assertEqual(self.start(preview)[0], 400)
        self.assertFalse(list(outside.iterdir())); self.assertFalse(self.posts())

    def test_windows_reparse_attribute_on_output_parent_is_refused(self):
        preview = self.preview(); directory = self.root / '_spoken'; directory.mkdir()
        original = Path.lstat
        def reparse(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path == directory:
                return SimpleNamespace(st_mode=value.st_mode, st_dev=value.st_dev, st_ino=value.st_ino, st_file_attributes=0x400)
            return value
        with patch.object(Path, 'lstat', reparse):
            self.assertEqual(self.start(preview)[0], 400)
        self.assertFalse(list(directory.iterdir())); self.assertFalse(self.posts())

    def test_unreceipted_master_is_preserved_without_submission(self):
        preview = self.preview(); directory = self.root / preview['run_key']; directory.mkdir(parents=True)
        output = directory / 'COMPRESSED.spoken.wav'; output.write_bytes(b'Prior unreceipted evidence')
        value = self.settled(self.start(preview)[1]['key'])
        self.assertEqual(value['status'], 'blocked'); self.assertIn('unreceipted', value['message'])
        self.assertEqual(output.read_bytes(), b'Prior unreceipted evidence'); self.assertFalse(self.posts())

    def test_root_configuration_change_after_create_keeps_child_in_original_run(self):
        preview = self.preview(); other = self.root / 'different'; other.mkdir()
        config = self.f.server.RequestHandlerClass.studio.config
        self.f.after_create = lambda project: config.update(spoken_briefs={'archive_root': str(other)})
        _, admission = self.start(preview)
        for thread in list(self.f.server.spoken_narrations.threads.values()): thread.join(5)
        state = json.loads((self.root / admission['key'] / 'state.json').read_text())
        self.assertEqual(state['batches'][0]['project_id'], next(iter(self.f.projects)))
        self.assertEqual(len(self.posts()), 1); self.assertFalse(list(other.iterdir()))


if __name__ == '__main__': unittest.main()

"""Explicit admission and observation of the existing durable CLI coordinator."""
from __future__ import annotations

import os
from pathlib import Path
import threading
import time

from .core import ArchiveAccess, AccessError, _key, digest, fields
from spoken_brief_archive import checked_json, inspect_run
from spoken_brief_compile import batch_segments, canonical_digest, run_directory
from spoken_brief_exports import _claim, _json_bytes, _new_file
from spoken_brief_inbox import _capture, _lineage
from spoken_brief_runtime import run
from spoken_brief_transport import initial_state, prepare_directory, validate_state, write_json
from voice_profile import require_executable


class Narrations:
    def __init__(self, config, base_url):
        self.config = config; self.base_url = base_url
        self.lock = threading.Lock(); self.threads = {}

    def access(self): return ArchiveAccess(self.config().get('spoken_briefs'))

    def _producer_pin(self):
        config = self.config(); path = config.get('voice_baseline_bundle')
        raw = None
        if isinstance(path, str) and Path(path).is_file():
            raw = _capture(Path(path).absolute(), 64 * 1024)[1][-1]
        return canonical_digest({'bundle': path, 'manifest_sha256': raw, 'ffmpeg': config.get('ffmpeg')})

    def preview(self, key, root_id):
        access = self.access()
        with access._directory('.') as root:
            lineage = _lineage(root)
            value = access.source_preview(key, root_id)
            value['producer_config_sha256'] = self._producer_pin()
            value['preview_sha256'] = canonical_digest({
                'manifest_sha256': value['manifest']['manifest_sha256'], 'root_id': root_id,
                'root_lineage': lineage, 'producer_config_sha256': value['producer_config_sha256']})
        return value

    def _load(self, key, root_id):
        access = self.access(); digest(root_id)
        if access.status()['source_root_id'] != root_id: raise AccessError('Source root changed; refresh source access', 409)
        with access._directory(key) as directory:
            record = checked_json(directory / 'studio-start.json')[0]
            manifest = checked_json(directory / 'manifest.json')[0]
            state = checked_json(directory / 'state.json')[0]
            try:
                fields(record, ('schema_version', 'kind', 'root_id', 'source_key', 'manifest_sha256', 'preview_sha256', 'started_at'))
                if (record['schema_version'] != 1 or record['kind'] != 'spoken-brief' or record['root_id'] != root_id
                        or record['manifest_sha256'] != manifest['manifest_sha256']
                        or canonical_digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'}) != manifest['manifest_sha256']):
                    raise AccessError('Retained narration identity differs', 409)
                source = Path(manifest['source']['path'])
                _key(source.relative_to(access._root()).as_posix())
                if run_directory(source, manifest['manifest_sha256']) != directory:
                    raise AccessError('Narration directory differs from its manifest', 409)
                digest(record['preview_sha256']); validate_state(state, manifest, batch_segments(manifest['segments']))
            except (KeyError, TypeError, ValueError) as exc:
                raise AccessError('Invalid retained narration: ' + str(exc), 409) from exc
            return directory, record, manifest, state

    def inspect(self, key, root_id):
        directory, record, manifest, state = self._load(key, root_id)
        thread = self.threads.get((root_id, key)); active = bool(thread and thread.is_alive())
        observation = checked_json(directory / 'studio-observation.json')[0] if (directory / 'studio-observation.json').exists() else {}
        archive = inspect_run(directory) if (directory / 'receipt.json').exists() else None
        uncertain = any(b['status'] in ('creating', 'create-unconfirmed', 'starting', 'start-unconfirmed') for b in state['batches'])
        status = ('completed' if archive else 'uncertain' if uncertain else 'running' if active else
                  'partial' if any(b['status'] == 'completed' for b in state['batches']) else
                  'prepared' if not observation and state['status'] == 'planned' else 'blocked')
        message = observation.get('error') or state.get('last_error') or (
            'Verified WAV is ready to inspect and play.' if archive else
            'Following the retained Voice projects.' if active else
            'Recover retained progress to observe known children. Recovery never creates or starts a take.')
        return {'key': key, 'root_id': root_id, 'kind': 'spoken-brief', 'manifest_sha256': manifest['manifest_sha256'],
                'manifest': manifest, 'state': state, 'status': status, 'active': active, 'message': message,
                'archive_sha256': archive['chapters_sha256'] if archive else None,
                'observation_only': True}

    def _launch(self, key, record, manifest, *, observe_only):
        root_id = record['root_id']; access = self.access(); root = access._root(); lineage = _lineage(root)
        if access.status()['source_root_id'] != root_id: raise AccessError('Configured source root changed', 409)
        directory = root.joinpath(*_key(key)); directory_lineage = _lineage(directory)

        def directory_guard():
            if _lineage(root) != lineage or _lineage(directory) != directory_lineage:
                raise AccessError('Source root or narration directory changed', 409)
            targets = [directory / name for name in ('manifest.json', 'state.json', 'receipt.json', '.spoken-brief.lock', 'segments')]
            targets += [directory / 'segments' / (s['id'] + '.wav') for s in manifest['segments']]
            targets.append(directory / (Path(manifest['source']['path']).stem + '.spoken.wav'))
            for path in targets:
                if os.path.lexists(path): _lineage(path)

        def guard():
            directory_guard()
            if self.access().status()['source_root_id'] != root_id:
                raise AccessError('Configured source root changed; retained children remain in their original run', 409)
            if self.preview(record['source_key'], root_id)['preview_sha256'] != record['preview_sha256']:
                raise AccessError('Source, profile or producer configuration changed; retained work is preserved', 409)

        def coordinate():
            try:
                run(manifest['source']['path'], base_url=self.base_url,
                    expected_manifest_sha256=record['manifest_sha256'], observe_only=observe_only, guard=directory_guard, before_request=guard)
                outcome = {'error': None, 'observe_only': observe_only}
            except Exception as exc:
                outcome = {'error': str(exc)[:800], 'observe_only': observe_only}
            try: write_json(directory / 'studio-observation.json', outcome, guard=directory_guard)
            except (OSError, ValueError): pass  # Retain state if the configured root itself became unsafe.
            finally:
                with self.lock: self.threads.pop((root_id, key), None)

        thread = threading.Thread(target=coordinate, name='spoken-brief-observer', daemon=True)
        self.threads[(root_id, key)] = thread
        try: thread.start()
        except Exception:
            self.threads.pop((root_id, key), None); raise

    def start(self, value):
        fields(value, ('key', 'root_id', 'manifest_sha256', 'preview_sha256'))
        digest(value['manifest_sha256']); digest(value['preview_sha256'])
        with self.lock:
            preview = self.preview(value['key'], value['root_id']); manifest = preview['manifest']
            if (manifest['manifest_sha256'] != value['manifest_sha256'] or preview['preview_sha256'] != value['preview_sha256']):
                raise AccessError('Source, profile or producer changed since preview; preview again before Start', 409)
            require_executable(manifest['voice_profile'])
            key = preview['run_key']; root = self.access()._root(); directory = root.joinpath(*_key(key))
            if (directory / 'studio-start.json').exists():
                self._load(key, value['root_id'])
                return {'key': key, 'root_id': value['root_id'], 'manifest_sha256': value['manifest_sha256'], 'reused': True}
            if self.threads: raise AccessError('Another narration is being followed; inspect its retained progress first', 409)
            prepare_directory(directory)
            with _claim(directory, value['manifest_sha256']) as verify:
                if (directory / 'studio-start.json').exists():
                    self._load(key, value['root_id'])
                    return {'key': key, 'root_id': value['root_id'], 'manifest_sha256': value['manifest_sha256'], 'reused': True}
                if self.preview(value['key'], value['root_id'])['preview_sha256'] != value['preview_sha256']:
                    raise AccessError('Preview changed before admission', 409)
                retained = (directory / 'state.json').exists()
                if (directory / 'manifest.json').exists() and checked_json(directory / 'manifest.json')[0] != manifest:
                    raise AccessError('Retained manifest differs; no files replaced', 409)
                write_json(directory / 'manifest.json', manifest, guard=verify)
                if not retained: write_json(directory / 'state.json', initial_state(manifest), guard=verify)
                record = {'schema_version': 1, 'kind': 'spoken-brief', 'root_id': value['root_id'],
                          'source_key': value['key'], 'manifest_sha256': value['manifest_sha256'],
                          'preview_sha256': value['preview_sha256'], 'started_at': time.time()}
                verify()
                if self.preview(value['key'], value['root_id'])['preview_sha256'] != value['preview_sha256']:
                    raise AccessError('Preview changed before Start commitment', 409)
                _new_file(directory / 'studio-start.json', _json_bytes(record))
            self._launch(key, record, manifest, observe_only=retained)
            return {'key': key, 'root_id': value['root_id'], 'manifest_sha256': value['manifest_sha256'], 'reused': False}

    def recover(self, value):
        fields(value, ('key', 'root_id', 'manifest_sha256'))
        with self.lock:
            directory, record, manifest, state = self._load(value['key'], value['root_id'])
            if record['manifest_sha256'] != value['manifest_sha256']: raise AccessError('Selected narration changed', 409)
            if not self.threads and not (directory / 'receipt.json').exists():
                self._launch(value['key'], record, manifest, observe_only=True)
            return {'key': value['key'], 'root_id': value['root_id'], 'manifest_sha256': value['manifest_sha256'], 'reused': True}

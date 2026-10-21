"""Bounded, digest-addressed provider metadata evidence, separate from the GET cache."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
import uuid

from ._adult_illustration_source_transport_cache import (
    SnapshotResponseCache, _parse_stored_at, _validate_response_routes,
)
from ._adult_illustration_source_transport_common import (
    AUTHORITY, MAX_PROVIDER_RESPONSE_BYTES, SHA256, HttpRequest, HttpResponse,
    cached_headers, parse_cache_json, parse_provider_json, request_identity,
    request_key, validate_base_request, validate_json_media_type,
)

STORE_SCHEMA = 'studio.adult-illustration-source-evidence/v1'
REF_SCHEMA = 'studio.adult-illustration-source-payload-ref/v1'
MAX_PROVENANCE_BYTES = 131_072
BUSY_SECONDS = 2.0
_CAPTURE_ID = re.compile(r'[0-9a-f]{32}')
_STATES = {'retained', 'disabled', 'quota_exceeded', 'publication_failed', 'corrupt', 'pruned'}


class _StoreChanged(ValueError): pass


def _pruned_state(value):
    try: _parse_stored_at(value)
    except ValueError: return 'corrupt'
    return 'pruned'


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


@dataclass(frozen=True)
class EvidencePolicy:
    """Logical body/provenance budgets; the database also has a page allocation cap."""
    max_total_bytes: int = 67_108_864
    max_payloads: int = 1_024
    max_observations: int = 4_096

    def __post_init__(self):
        for name, maximum in (('max_total_bytes', 268_435_456), ('max_payloads', 100_000), ('max_observations', 100_000)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f'{name} must be an integer between 1 and {maximum}')

    @property
    def database_bytes(self):
        # B-tree/index/page overhead is bounded separately from retained logical bytes.
        # DELETE journaling can temporarily need additional disk space; disk faults are explicit.
        return 2 * self.max_total_bytes + 1_048_576


def payload_reference(digest, byte_count, cache_key, state, *, store_id=None, observation_id=None, detail=None):
    return {'schema': REF_SCHEMA, 'sha256': digest, 'body_bytes': byte_count,
            'cache_key': cache_key, 'store_id': store_id, 'observation_id': observation_id,
            'retention_state': state, 'detail': detail}


def _resolution(ref, state, *, source='immutable-evidence-store', detail=None, body=None, provenance=None):
    return {'schema': 'studio.adult-illustration-source-evidence-resolution/v1',
            'state': state, 'source': source, 'sha256': ref.get('sha256'), 'detail': detail,
            'body_base64': base64.b64encode(body).decode('ascii') if body is not None else None,
            'provenance': provenance, 'executable': False, 'authority': 'none', **AUTHORITY}


def _validate_ref(ref):
    fields = {'schema', 'sha256', 'body_bytes', 'cache_key', 'store_id', 'observation_id', 'retention_state', 'detail'}
    if not isinstance(ref, dict) or set(ref) != fields or ref.get('schema') != REF_SCHEMA:
        raise ValueError('Invalid raw payload evidence reference')
    if not isinstance(ref['sha256'], str) or SHA256.fullmatch(ref['sha256']) is None:
        raise ValueError('Invalid raw payload SHA-256')
    if type(ref['body_bytes']) is not int or not 0 <= ref['body_bytes'] <= MAX_PROVIDER_RESPONSE_BYTES:
        raise ValueError('Invalid raw payload byte count')
    if not isinstance(ref['cache_key'], str) or SHA256.fullmatch(ref['cache_key']) is None:
        raise ValueError('Invalid request identity in payload reference')
    if not isinstance(ref['retention_state'], str) or ref['retention_state'] not in _STATES:
        raise ValueError('Invalid raw payload retention state')
    if ref['store_id'] is not None and (not isinstance(ref['store_id'], str) or _CAPTURE_ID.fullmatch(ref['store_id']) is None):
        raise ValueError('Invalid evidence store identity')
    if ref['observation_id'] is not None and (not isinstance(ref['observation_id'], str) or SHA256.fullmatch(ref['observation_id']) is None):
        raise ValueError('Invalid evidence observation identity')
    if ref['retention_state'] == 'retained' and (ref['store_id'] is None or ref['observation_id'] is None):
        raise ValueError('Retained evidence requires store and observation identities')
    if ref['detail'] is not None and (not isinstance(ref['detail'], str) or len(ref['detail']) > 300):
        raise ValueError('Invalid raw evidence detail')


def _provenance(request, response, receipt, capture_id, captured_at):
    provider = validate_base_request(request)
    if not isinstance(response, HttpResponse) or response.status != 200 or response.request_url != request.url:
        raise ValueError('Evidence requires an exact successful metadata response')
    _validate_response_routes(request, response.final_url, response.redirect_chain)
    validate_json_media_type(response.headers)
    parse_provider_json(response.body, MAX_PROVIDER_RESPONSE_BYTES)
    digest = hashlib.sha256(response.body).hexdigest()
    if (not isinstance(receipt, dict) or receipt.get('provider') != provider
            or receipt.get('request_key') != request_key(request)
            or receipt.get('request_url') != request.url
            or receipt.get('response_payload_sha256') != digest
            or receipt.get('effective_status') != 200
            or type(receipt.get('network_performed')) is not bool
            or receipt.get('wire_status') not in (200, 304)
            or any(receipt.get(key) is not value for key, value in AUTHORITY.items())):
        raise ValueError('Evidence provenance does not match the owned response')
    if not isinstance(capture_id, str) or _CAPTURE_ID.fullmatch(capture_id) is None:
        raise ValueError('Invalid evidence capture identity')
    _parse_stored_at(captured_at)
    state = receipt.get('cache_state')
    if state == 'hit' and not receipt['network_performed'] and receipt['wire_status'] == 200:
        acquisition = 'cache-hit'
    elif state == 'revalidated' and receipt['network_performed'] and receipt['wire_status'] == 304:
        acquisition = 'revalidated-304'
    elif state in ('disabled', 'miss', 'refreshed') and receipt['network_performed'] and receipt['wire_status'] == 200:
        acquisition = 'network-200'
    else: raise ValueError('Evidence acquisition state is inconsistent')
    document = {'schema': STORE_SCHEMA, 'capture_id': capture_id, 'captured_at': captured_at,
                'acquisition': acquisition, 'provider': provider, 'request': request_identity(request),
                'request_key': request_key(request), 'sha256': digest, 'body_bytes': len(response.body),
                'response': {'status': 200, 'final_url': response.final_url,
                             'redirect_chain': list(response.redirect_chain), 'headers': cached_headers(response.headers)},
                'network_performed': receipt['network_performed'], 'wire_status': receipt['wire_status'],
                'cache_stored_at': receipt.get('cache_stored_at'),
                'executable': False, 'authority': 'none', **AUTHORITY}
    raw = _json(document)
    return document, raw


class SnapshotEvidenceStore:
    """One bounded SQLite transaction publishes raw bytes and their source provenance.

    No implicit pruning, cache fallback, network, or overwrite of an existing digest.
    A pruning tombstone remains until the operator archives/removes the whole store.
    """
    def __init__(self, root: str | Path, *, policy: EvidencePolicy | None = None, create: bool = True):
        if policy is not None and not isinstance(policy, EvidencePolicy): raise TypeError('policy must be EvidencePolicy')
        if type(create) is not bool: raise TypeError('create must be boolean')
        self.root = Path(root)
        if self.root.is_symlink(): raise ValueError('Evidence root cannot be a symlink')
        if create: self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir(): raise ValueError('Evidence root is unavailable')
        self.root = self.root.resolve(strict=True); self.path = self.root/'payload-evidence.sqlite3'
        self.policy = policy or EvidencePolicy()
        self._opening = True
        try:
            with self._connection(create=create) as db:
                if create:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('CREATE TABLE IF NOT EXISTS evidence_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),schema TEXT NOT NULL,store_id TEXT NOT NULL,policy TEXT NOT NULL)')
                record = db.execute('SELECT substr(schema,1,128),substr(store_id,1,64),substr(policy,1,1025) FROM evidence_meta WHERE singleton=1').fetchone()
                if record is None:
                    if not create: raise ValueError('Evidence store has no identity')
                    self.store_id = uuid.uuid4().hex
                    db.execute('INSERT INTO evidence_meta VALUES (1,?,?,?)', (STORE_SCHEMA, self.store_id, _json(asdict(self.policy)).decode('utf-8')))
                    db.execute('CREATE TABLE payloads(sha256 TEXT PRIMARY KEY,byte_count INTEGER NOT NULL,body BLOB,pruned_at TEXT)')
                    db.execute('CREATE TABLE observations(id TEXT PRIMARY KEY,payload_sha TEXT NOT NULL REFERENCES payloads(sha256),document TEXT NOT NULL)')
                else:
                    schema, self.store_id, saved = record
                    if (schema != STORE_SCHEMA or not isinstance(self.store_id, str)
                            or _CAPTURE_ID.fullmatch(self.store_id) is None or not isinstance(saved, str) or len(saved) > 1_024):
                        raise ValueError('Invalid evidence store metadata')
                    parsed = parse_cache_json(saved.encode('utf-8'))
                    if set(parsed) != set(asdict(EvidencePolicy())): raise ValueError('Invalid evidence quota policy')
                    persisted = EvidencePolicy(**parsed)
                    if policy is not None and policy != persisted: raise ValueError('Evidence policy differs from the persisted store policy')
                    self.policy = persisted
                self._opening = False
                self._check_file()
                if create:
                    page_size = db.execute('PRAGMA page_size').fetchone()[0]
                    db.execute(f'PRAGMA max_page_count={max(1, self.policy.database_bytes // page_size)}')
                    db.commit()
        except sqlite3.Error as exc: raise ValueError('Evidence store cannot be opened or initialized') from exc
        finally: self._opening = False

    def _check_file(self):
        if self.root.is_symlink() or self.path.is_symlink(): raise ValueError('Evidence store cannot be a symlink')
        maximum = 537_919_488 if self._opening else self.policy.database_bytes
        if self.path.exists() and (not self.path.is_file() or self.path.stat().st_size > maximum):
            raise ValueError('Evidence database is unavailable or oversized')

    @contextmanager
    def _connection(self, *, create=False, write=False):
        self._check_file()
        mode = 'rwc' if create else ('rw' if write else 'ro')
        db = sqlite3.connect(self.path.as_uri()+f'?mode={mode}', uri=True, timeout=BUSY_SECONDS, isolation_level=None)
        try:
            if not self._opening:
                identity = db.execute('SELECT substr(schema,1,128),substr(store_id,1,64),substr(policy,1,1025) FROM evidence_meta WHERE singleton=1').fetchone()
                if identity != (STORE_SCHEMA, self.store_id, _json(asdict(self.policy)).decode('utf-8')):
                    raise _StoreChanged('Evidence store identity or policy changed')
            db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA cache_size=-1024')
            if create or write:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('PRAGMA journal_mode=DELETE')
                if not self._opening:
                    size = db.execute('PRAGMA page_size').fetchone()[0]
                    db.execute(f'PRAGMA max_page_count={max(1, self.policy.database_bytes // size)}')
            yield db
        finally: db.close()  # Closing an uncommitted transaction rolls it back.

    @staticmethod
    def _commit(db):
        db.commit()

    @staticmethod
    def _stats(db):
        payloads, available, body_bytes = db.execute('SELECT count(*),count(body),coalesce(sum(length(body)),0) FROM payloads').fetchone()
        observations, document_bytes = db.execute('SELECT count(*),coalesce(sum(length(CAST(document AS BLOB))),0) FROM observations').fetchone()
        return {'payloads': payloads, 'available_payloads': available, 'observations': observations,
                'total_bytes': body_bytes + document_bytes}

    def stats(self):
        with self._connection() as db:
            return dict(self._stats(db), schema=STORE_SCHEMA, store_id=self.store_id,
                        policy=asdict(self.policy), executable=False, authority='none', **AUTHORITY)

    def retain(self, request, response, receipt, *, capture_id, captured_at):
        document, raw = _provenance(request, response, receipt, capture_id, captured_at)
        digest = document['sha256']; observation_id = hashlib.sha256(raw).hexdigest()
        def ref(state, detail=None):
            return payload_reference(digest, len(response.body), request_key(request), state,
                store_id=self.store_id, observation_id=observation_id if state == 'retained' else None, detail=detail)
        if len(raw) > MAX_PROVENANCE_BYTES:
            return ref('quota_exceeded', 'Source provenance exceeds the 128 KiB evidence budget')
        try:
            with self._connection(write=True) as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT byte_count,length(body),pruned_at FROM payloads WHERE sha256=?', (digest,)).fetchone()
                if existing:
                    count, length, pruned = existing
                    if count != len(response.body): return ref('corrupt')
                    if length is None: return ref(_pruned_state(pruned))
                    if pruned is not None: return ref('corrupt')
                    if length != count or length > MAX_PROVIDER_RESPONSE_BYTES:
                        return ref('corrupt', 'Existing evidence bytes do not match their identity')
                    body = db.execute('SELECT substr(body,1,?) FROM payloads WHERE sha256=?', (MAX_PROVIDER_RESPONSE_BYTES+1, digest)).fetchone()[0]
                    if not isinstance(body, bytes) or hashlib.sha256(body).hexdigest() != digest: return ref('corrupt')
                previous = db.execute('SELECT length(document) FROM observations WHERE id=?', (observation_id,)).fetchone()
                if previous:
                    if not 0 <= previous[0] <= MAX_PROVENANCE_BYTES: return ref('corrupt')
                    text = db.execute('SELECT substr(document,1,?) FROM observations WHERE id=?', (MAX_PROVENANCE_BYTES+1, observation_id)).fetchone()[0]
                    return ref('retained' if isinstance(text, str) and text.encode('utf-8') == raw and existing else 'corrupt')
                stats = self._stats(db)
                added = len(raw) + (0 if existing else len(response.body))
                if (stats['total_bytes'] + added > self.policy.max_total_bytes
                        or stats['observations'] >= self.policy.max_observations
                        or (not existing and stats['payloads'] >= self.policy.max_payloads)):
                    return ref('quota_exceeded', 'Declared evidence retention quota is full; nothing was evicted')
                if not existing: db.execute('INSERT INTO payloads VALUES (?,?,?,NULL)', (digest, len(response.body), response.body))
                db.execute('INSERT INTO observations VALUES (?,?,?)', (observation_id, digest, raw.decode('utf-8')))
                self._commit(db)
                return ref('retained')
        except (OSError, sqlite3.Error) as exc:
            corrupt = getattr(exc, 'sqlite_errorcode', None) in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB)
            return ref('corrupt' if corrupt else 'publication_failed', 'Evidence transaction could not be confirmed')
        except ValueError: return ref('corrupt', 'Evidence store is unavailable or invalid')

    def resolve(self, ref):
        _validate_ref(ref)
        if ref['retention_state'] != 'retained': return _resolution(ref, ref['retention_state'], detail=ref['detail'])
        if ref['store_id'] not in (None, self.store_id): return _resolution(ref, 'store_mismatch')
        try:
            with self._connection() as db:
                db.execute('BEGIN')  # One consistent payload/provenance/pruning view.
                row = db.execute('SELECT byte_count,length(body),pruned_at FROM payloads WHERE sha256=?', (ref['sha256'],)).fetchone()
                if row is None: return _resolution(ref, 'missing', detail='Historical payload is missing')
                count, length, pruned = row
                if count != ref['body_bytes']: return _resolution(ref, 'corrupt')
                if length is None: return _resolution(ref, _pruned_state(pruned))
                if pruned is not None: return _resolution(ref, 'corrupt')
                if length != count or not 0 <= length <= MAX_PROVIDER_RESPONSE_BYTES:
                    return _resolution(ref, 'corrupt')
                saved = db.execute('SELECT payload_sha,length(document) FROM observations WHERE id=?', (ref['observation_id'],)).fetchone()
                if saved is None: return _resolution(ref, 'missing', detail='Source provenance is missing')
                if saved[0] != ref['sha256'] or not 0 <= saved[1] <= MAX_PROVENANCE_BYTES: return _resolution(ref, 'corrupt')
                body = db.execute('SELECT substr(body,1,?) FROM payloads WHERE sha256=?', (MAX_PROVIDER_RESPONSE_BYTES+1, ref['sha256'])).fetchone()[0]
                text = db.execute('SELECT substr(document,1,?) FROM observations WHERE id=?', (MAX_PROVENANCE_BYTES+1, ref['observation_id'])).fetchone()[0]
                if not isinstance(body, bytes) or not isinstance(text, str): return _resolution(ref, 'corrupt')
                raw = text.encode('utf-8')
                if (hashlib.sha256(body).hexdigest() != ref['sha256'] or len(raw) > MAX_PROVENANCE_BYTES
                        or hashlib.sha256(raw).hexdigest() != ref['observation_id']): return _resolution(ref, 'corrupt')
                document = parse_cache_json(raw)
                if (document.get('schema') != STORE_SCHEMA or document.get('sha256') != ref['sha256']
                        or document.get('request_key') != ref['cache_key'] or document.get('body_bytes') != len(body)
                        or document.get('executable') is not False or document.get('authority') != 'none'
                        or any(document.get(key) is not value for key, value in AUTHORITY.items())):
                    return _resolution(ref, 'corrupt')
                request = HttpRequest(**document['request'])
                if validate_base_request(request) != document.get('provider') or request_key(request) != ref['cache_key']:
                    return _resolution(ref, 'corrupt')
                response = document['response']
                if response.get('status') != 200 or cached_headers(response['headers']) != response['headers']:
                    return _resolution(ref, 'corrupt')
                validate_json_media_type(response['headers'])
                _validate_response_routes(request, response['final_url'], response['redirect_chain'])
                parse_provider_json(body, MAX_PROVIDER_RESPONSE_BYTES)
                return _resolution(ref, 'available', body=body, provenance=document)
        except _StoreChanged: return _resolution(ref, 'store_mismatch')
        except sqlite3.Error as exc:
            corrupt = getattr(exc, 'sqlite_errorcode', None) in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB)
            return _resolution(ref, 'corrupt' if corrupt else 'unavailable', detail='Evidence store could not be read')
        except (OSError, ValueError, TypeError, KeyError, UnicodeError): return _resolution(ref, 'corrupt')

    def prune(self, digest):
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None: raise ValueError('Invalid prune payload SHA-256')
        try:
            with self._connection(write=True) as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT pruned_at FROM payloads WHERE sha256=?', (digest,)).fetchone()
                if row is None: state = 'missing'
                else:
                    state = 'pruned'
                    db.execute('UPDATE payloads SET body=NULL,pruned_at=? WHERE sha256=?',
                               (row[0] or datetime.now(timezone.utc).isoformat(), digest))
                self._commit(db)
        except (OSError, sqlite3.Error): state = 'publication_failed'
        except ValueError: state = 'corrupt'
        return {'schema': STORE_SCHEMA, 'state': state, 'sha256': digest, 'store_id': self.store_id,
                'executable': False, 'authority': 'none', **AUTHORITY}


def resolve_payload_reference(ref, *, evidence_store=None, cache=None, request=None):
    """Resolve immutable refs, or verify old cache-only refs without inventing history."""
    if not isinstance(ref, dict): raise ValueError('Payload reference must be an object')
    if 'schema' in ref:
        _validate_ref(ref)
        if evidence_store is not None:
            if not isinstance(evidence_store, SnapshotEvidenceStore): raise TypeError('evidence_store must be SnapshotEvidenceStore')
            return evidence_store.resolve(ref)
        return _resolution(ref, ref['retention_state'] if ref['retention_state'] != 'retained' else 'unavailable', detail='No evidence store supplied')
    if (set(ref) != {'sha256', 'cache_key', 'retained_in_cache'} or type(ref.get('retained_in_cache')) is not bool
            or any(not isinstance(ref.get(key), str) or SHA256.fullmatch(ref[key]) is None for key in ('sha256', 'cache_key'))):
        raise ValueError('Invalid legacy raw payload reference')
    source = 'legacy-mutable-cache'
    if cache is None or request is None: return _resolution(ref, 'legacy_unavailable', source=source, detail='Legacy evidence needs its original request and cache')
    if not isinstance(cache, SnapshotResponseCache): raise TypeError('cache must be SnapshotResponseCache')
    validate_base_request(request)
    if request_key(request) != ref['cache_key']: return _resolution(ref, 'legacy_unavailable', source=source, detail='Legacy request identity differs')
    try: response = cache.load(request)
    except (OSError, ValueError): return _resolution(ref, 'corrupt', source=source)
    if response is None or hashlib.sha256(response.body).hexdigest() != ref['sha256']:
        return _resolution(ref, 'legacy_unavailable', source=source, detail='Historical cache bytes are missing or have changed')
    return _resolution(ref, 'available', source=source, body=response.body,
                       detail='Verified legacy cache bytes; immutable retention and original observation time are not established')
